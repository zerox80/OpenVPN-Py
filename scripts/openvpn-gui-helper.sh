#!/bin/bash
# Strict mode for more safety and better error detection
set -euo pipefail

# --- Helper Functions ---
log() {
    # Logs to the log file provided as an argument to the script
    local log_file_path="$1"
    local message="$2"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - HELPER: ${message}" >> "$log_file_path"
}

handle_error() {
    # Since we can't be sure which log file to use, error to stderr
    local exit_code=$?
    echo "ERROR: Line $1: Command failed with exit code $exit_code." >&2
    exit "$exit_code"
}

# Escape instance names for systemd unit safety
escape_instance() {
    local inst="$1"
    if command -v systemd-escape >/dev/null 2>&1; then
        systemd-escape -- "$inst"
    else
        # Fallback: replace problematic characters with '-'
        echo "$inst" | sed 's/[^A-Za-z0-9._@-]/-/g'
    fi
}

# List all unit names matching a base service (exact and suffixed variants)
list_matching_units() {
    local base_unit_name="$1"   # e.g. openvpn-py-gui@myconfig
    local matches=()
    # Capture list-units output safely to avoid aborting under 'set -euo pipefail'
    # on systems without systemd or when systemctl returns non-zero.
    local list_output
    list_output="$(
        systemctl list-units --all --type=service --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
    )"

    while IFS= read -r unit; do
        # Match exact and suffixed forms: base.service or base-*.service
        if [[ "$unit" == "${base_unit_name}.service" || "$unit" == ${base_unit_name}-*.service ]]; then
            matches+=("$unit")
        fi
    done <<< "$list_output"

    printf '%s\n' "${matches[@]:-}"
}

# Directory for transient credential files (root-only). Use path allowed by OpenVPN/AppArmor.
AUTH_DIR="/run/openvpn"

# Setup error trap
trap 'handle_error $LINENO' ERR

# --- Main Logic ---

# Check for root privileges
if [[ $EUID -ne 0 ]]; then
   echo "ERROR: This script must be run as root." >&2
   exit 1
fi

# Resolve openvpn binary dynamically (systemd-run has limited PATH)
OPENVPN_BIN="$(command -v openvpn || true)"
if [[ -z "$OPENVPN_BIN" ]]; then
    # Fallback to common path
    if [[ -x "/usr/sbin/openvpn" ]]; then
        OPENVPN_BIN="/usr/sbin/openvpn"
    elif [[ -x "/usr/bin/openvpn" ]]; then
        OPENVPN_BIN="/usr/bin/openvpn"
    else
        echo "ERROR: 'openvpn' binary not found. Please install OpenVPN (e.g., 'sudo apt install openvpn')." >&2
        exit 1
    fi
fi

COMMAND=$1
shift

case "$COMMAND" in
    start)
        CONFIG_PATH="$1"
        LOG_PATH="$2"

        log "$LOG_PATH" "Start command received for config: $CONFIG_PATH"

        if [ ! -f "$CONFIG_PATH" ]; then
            log "$LOG_PATH" "ERROR: Config file not found: $CONFIG_PATH"
            echo "ERROR: Config file not found: $CONFIG_PATH" >&2
            exit 1
        fi

        # Use the config filename (without extension) for the service name
        CONFIG_NAME=$(basename "$CONFIG_PATH")
        CONFIG_INSTANCE_RAW="${CONFIG_NAME%.*}"
        CONFIG_INSTANCE_ESCAPED="$(escape_instance "$CONFIG_INSTANCE_RAW")"
        SERVICE_UNIT_NAME="openvpn-py-gui@${CONFIG_INSTANCE_ESCAPED}"
        SERVICE_FULL="${SERVICE_UNIT_NAME}.service"

        log "$LOG_PATH" "Pre-cleaning possible stale unit: $SERVICE_FULL"
        systemctl stop "$SERVICE_FULL" || true
        systemctl kill "$SERVICE_FULL" || true
        systemctl reset-failed "$SERVICE_FULL" || true
        if [ -f "/run/systemd/transient/$SERVICE_FULL" ]; then
            rm -f "/run/systemd/transient/$SERVICE_FULL" || true
        fi
        systemctl daemon-reload || true

        # Detect persistent fragment conflict for this unit name
        if systemctl cat "$SERVICE_FULL" >/tmp/.ovpnpy.unit.$$ 2>/dev/null; then
            if grep -E '^#\s+/' /tmp/.ovpnpy.unit.$$ | grep -vq "/run/systemd/transient/"; then
                # Persistent or generated fragment exists; choose a unique transient name to avoid collision
                UNIQUE_SUFFIX="$(date +%s)-$$"
                SERVICE_UNIT_NAME="${SERVICE_UNIT_NAME}-${UNIQUE_SUFFIX}"
                SERVICE_FULL="${SERVICE_UNIT_NAME}.service"
                log "$LOG_PATH" "Detected persistent fragment conflict. Using unique unit: $SERVICE_FULL"
            fi
            rm -f /tmp/.ovpnpy.unit.$$ || true
        fi

        log "$LOG_PATH" "Starting OpenVPN service '$SERVICE_UNIT_NAME' using '$OPENVPN_BIN'..."

        # Read credentials from stdin and write to a root-only temp file
        mkdir -p "$AUTH_DIR"
        # Directory must be traversable by the user to read log via symlink; keep files themselves protected
        chmod 755 "$AUTH_DIR"
        read -r username
        read -r password
        AUTH_FILE="$AUTH_DIR/${SERVICE_FULL}.auth"
        umask 077
        printf "%s\n%s\n" "$username" "$password" > "$AUTH_FILE"

        # If config specifies an unprivileged user/group, chown the auth file accordingly
        CFG_USER="$(awk 'tolower($1)=="user"{print $2; exit}' "$CONFIG_PATH" 2>/dev/null || true)"
        CFG_GROUP="$(awk 'tolower($1)=="group"{print $2; exit}' "$CONFIG_PATH" 2>/dev/null || true)"
        if [ -n "${CFG_USER:-}" ] || [ -n "${CFG_GROUP:-}" ]; then
            # Default missing group to the user's primary group
            if [ -n "${CFG_USER:-}" ] && [ -z "${CFG_GROUP:-}" ]; then
                CFG_GROUP="$(id -gn "$CFG_USER" 2>/dev/null || echo "$CFG_USER")"
            fi
            chown "${CFG_USER:-root}":"${CFG_GROUP:-root}" "$AUTH_FILE" 2>/dev/null || true
            chmod 600 "$AUTH_FILE" || true
        fi

        # Use an AppArmor-allowed log location and symlink GUI log to it
        SERVICE_LOG="$AUTH_DIR/${SERVICE_FULL}.log"
        # Ensure parent dir for GUI log exists and point it to the service log
        mkdir -p "$(dirname "$LOG_PATH")" || true
        # Create/empty the service log and link GUI log to it (GUI must be able to read)
        : > "$SERVICE_LOG"
        chmod 644 "$SERVICE_LOG"
        ln -sfn "$SERVICE_LOG" "$LOG_PATH" || true

        # Build up/down arguments: only override if the config does not define its own
        UPDOWN_ARGS=(--script-security 2)
        if ! grep -Eq '(^|[[:space:]])(up|down)[[:space:]]+' "$CONFIG_PATH"; then
            UPDOWN_ARGS+=(--up /bin/true --down /bin/true)
        fi

        # Start OpenVPN as a transient service without attaching stdio (non-blocking)
        systemd-run --unit "$SERVICE_UNIT_NAME" \
                    --collect \
                    --description "OpenVPN GUI client for $CONFIG_NAME" \
                    "$OPENVPN_BIN" \
                        --config "$CONFIG_PATH" \
                        "${UPDOWN_ARGS[@]}" \
                        --auth-user-pass "$AUTH_FILE" \
                        --auth-nocache \
                        --log "$SERVICE_LOG"

        log "$LOG_PATH" "systemd-run command issued for $SERVICE_UNIT_NAME."
        ;;
    stop)
        CONFIG_NAME="$1" # Expects just the filename, e.g., "my-vpn.ovpn"
        LOG_PATH="$2"
        CONFIG_INSTANCE_RAW="${CONFIG_NAME%.*}"
        CONFIG_INSTANCE_ESCAPED="$(escape_instance "$CONFIG_INSTANCE_RAW")"
        SERVICE_UNIT_NAME="openvpn-py-gui@${CONFIG_INSTANCE_ESCAPED}"
        SERVICE_FULL="${SERVICE_UNIT_NAME}.service"

        log "$LOG_PATH" "Stop command received for service base: $SERVICE_UNIT_NAME"

        # Find and stop all matching instances
        declare -a MATCHING_UNITS=()
        mapfile -t MATCHING_UNITS < <(list_matching_units "$SERVICE_UNIT_NAME") || true
        if [ "${#MATCHING_UNITS[@]}" -eq 0 ]; then
            # Fallback to the base unit name
            MATCHING_UNITS=("$SERVICE_FULL")
        fi

        any_stopped=0
        for u in "${MATCHING_UNITS[@]}"; do
            if systemctl is-active --quiet "$u"; then
                systemctl stop "$u" || true
                any_stopped=1
                log "$LOG_PATH" "Service '$u' stopped."
            fi
            systemctl reset-failed "$u" || true
            if [ -f "/run/systemd/transient/$u" ]; then
                rm -f "/run/systemd/transient/$u" || true
            fi
        done
        systemctl daemon-reload || true

        # Remove any auth files and transient logs associated with the unit(s)
        if [ "${#MATCHING_UNITS[@]}" -gt 0 ]; then
            for u in "${MATCHING_UNITS[@]}"; do
                rm -f "$AUTH_DIR/${u}.auth" || true
                rm -f "$AUTH_DIR/${u}.log" || true
                # Cleanup legacy location if present
                rm -f "/run/openvpn-py/${u}.auth" || true
            done
            rmdir "$AUTH_DIR" 2>/dev/null || true
            rmdir "/run/openvpn-py" 2>/dev/null || true
        fi

        if [ $any_stopped -eq 0 ]; then
            log "$LOG_PATH" "No running matching services were found for base '$SERVICE_UNIT_NAME'."
            echo "INFO: Service was not running." >&2
        fi
        ;;
    status)
        CONFIG_NAME="$1" # Expects just the filename
        CONFIG_INSTANCE_RAW="${CONFIG_NAME%.*}"
        CONFIG_INSTANCE_ESCAPED="$(escape_instance "$CONFIG_INSTANCE_RAW")"
        SERVICE_UNIT_NAME="openvpn-py-gui@${CONFIG_INSTANCE_ESCAPED}"
        SERVICE_FULL="${SERVICE_UNIT_NAME}.service"

        # Consider any matching instance
        declare -a MATCHING_UNITS=()
        mapfile -t MATCHING_UNITS < <(list_matching_units "$SERVICE_UNIT_NAME") || true
        if [ "${#MATCHING_UNITS[@]}" -eq 0 ]; then
            MATCHING_UNITS=("$SERVICE_FULL")
        fi

        for u in "${MATCHING_UNITS[@]}"; do
            if systemctl is-active --quiet "$u"; then
                echo "connected"
                exit 0
            fi
        done
        for u in "${MATCHING_UNITS[@]}"; do
            if systemctl is-failed --quiet "$u"; then
                echo "error"
                exit 0
            fi
        done
        echo "disconnected"
        ;;
    *)
        echo "ERROR: Invalid command '$COMMAND'." >&2
        exit 1
        ;;
esac

exit 0
