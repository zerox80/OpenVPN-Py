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
        # Some systemd versions prepend a bullet (●) as the first column. Extract the UNIT column robustly.
        systemctl list-units --all --type=service --no-legend --no-pager 2>/dev/null \
        | awk '{ if ($1 == "●") print $2; else print $1 }' || true
    )"

    while IFS= read -r unit; do
        # Match exact and suffixed forms: base.service or base-*.service
        if [[ "$unit" == "${base_unit_name}.service" || "$unit" == ${base_unit_name}-*.service ]]; then
            matches+=("$unit")
        fi
    done <<< "$list_output"

    printf '%s\n' "${matches[@]:-}"
}

# Directory for credential files (root-only) – AppArmor-friendly location
AUTH_DIR="/etc/openvpn/openvpn-py"
# Directory for transient logs readable by GUI via symlink
LOG_DIR="/run/openvpn"

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

# Determine OpenVPN version (for feature gating like DOMAIN-ROUTE)
OVPN_VER_RAW="$($OPENVPN_BIN --version 2>/dev/null | head -n1 | sed -E 's/.*OpenVPN[[:space:]]+([0-9]+)\.([0-9]+)(\.[0-9]+)?[[:space:]].*/\1 \2/;t;d')"
OVPN_VER_MAJ=0
OVPN_VER_MIN=0
if [[ -n "$OVPN_VER_RAW" ]]; then
    # shellcheck disable=SC2206
    parts=( $OVPN_VER_RAW )
    OVPN_VER_MAJ="${parts[0]:-0}"
    OVPN_VER_MIN="${parts[1]:-0}"
fi
# DOMAIN-ROUTE dhcp-option is supported since OpenVPN 2.5
SUPPORTS_DOMAIN_ROUTE=0
if [[ "$OVPN_VER_MAJ" -gt 2 ]] || { [[ "$OVPN_VER_MAJ" -eq 2 ]] && [[ "$OVPN_VER_MIN" -ge 5 ]]; }; then
    SUPPORTS_DOMAIN_ROUTE=1
fi

COMMAND=$1
shift

case "$COMMAND" in
    start)
        CONFIG_PATH="$1"
        LOG_PATH="$2"
        shift 2 || true
        # Optional flags after LOG_PATH
        DISABLE_EXTERNAL_FLAG=0
        FORCE_PLUGIN_PATH=""
        while [ $# -gt 0 ]; do
            case "$1" in
                --disable-external)
                    DISABLE_EXTERNAL_FLAG=1
                    ;;
                --force-plugin=*)
                    FORCE_PLUGIN_PATH="${1#*=}"
                    ;;
                *)
                    # ignore unknown extras to stay compatible
                    ;;
            esac
            shift || true
        done

        log "$LOG_PATH" "Start command received for config: $CONFIG_PATH"

        if [ ! -f "$CONFIG_PATH" ]; then
            log "$LOG_PATH" "ERROR: Config file not found: $CONFIG_PATH"
            echo "ERROR: Config file not found: $CONFIG_PATH" >&2
            exit 1
        fi

        # Use the config filename (without extension) for the service name
        CONFIG_NAME=$(basename "$CONFIG_PATH")
        CONFIG_INSTANCE_RAW="${CONFIG_NAME%.*}"
        CONFIG_INSTANCE_ESC="$(escape_instance "$CONFIG_INSTANCE_RAW")"
        BASE_UNIT_PREFIX_RAW="openvpn-py-gui@${CONFIG_INSTANCE_RAW}"
        BASE_UNIT_PREFIX_ESC="openvpn-py-gui@${CONFIG_INSTANCE_ESC}"
        SERVICE_UNIT_NAME="$BASE_UNIT_PREFIX_ESC"
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
        chmod 700 "$AUTH_DIR"
        read -r username
        read -r password
        # Debug: log lengths only (never log secrets)
        ulen=${#username}
        plen=${#password}
        if [ "$ulen" -eq 0 ] || [ "$plen" -eq 0 ]; then
            log "$LOG_PATH" "ERROR: Received empty username or password from GUI. Aborting before starting OpenVPN."
            echo "ERROR: Empty credentials provided" >&2
            exit 1
        fi
        log "$LOG_PATH" "Received credentials: username_len=$ulen password_len=$plen"
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

        # Remove stale logs for this instance prefix (both raw and escaped) to avoid confusing status parsing
        rm -f "$LOG_DIR/${BASE_UNIT_PREFIX_ESC}.service.log" 2>/dev/null || true
        rm -f "$LOG_DIR/${BASE_UNIT_PREFIX_ESC}-"*.service.log 2>/dev/null || true
        rm -f "$LOG_DIR/${BASE_UNIT_PREFIX_RAW}.service.log" 2>/dev/null || true
        rm -f "$LOG_DIR/${BASE_UNIT_PREFIX_RAW}-"*.service.log 2>/dev/null || true

        # Use an AppArmor-allowed log location and symlink GUI log to it
        mkdir -p "$LOG_DIR"
        chmod 755 "$LOG_DIR" || true
        SERVICE_LOG="$LOG_DIR/${SERVICE_FULL}.log"
        # Ensure parent dir for GUI log exists and point it to the service log
        mkdir -p "$(dirname "$LOG_PATH")" || true
        # Pre-create the service log and set readable permissions so the GUI can read it even if systemd uses a restrictive umask
        : > "$SERVICE_LOG" || true
        chmod 0644 "$SERVICE_LOG" || true
        # Link GUI log to the target
        ln -sfn "$SERVICE_LOG" "$LOG_PATH" || true

        # Additionally, expose the live log in the invoking user's Documents folder for convenience
        if [ -n "${SUDO_USER:-}" ]; then
            USER_HOME="$(getent passwd "$SUDO_USER" | awk -F: '{print $6}' 2>/dev/null || true)"
            if [ -n "$USER_HOME" ] && [ -d "$USER_HOME" ]; then
                # Prefer localized Documents if present
                DOCS_DIR=""
                if [ -d "$USER_HOME/Documents" ]; then
                    DOCS_DIR="$USER_HOME/Documents"
                elif [ -d "$USER_HOME/Dokumente" ]; then
                    DOCS_DIR="$USER_HOME/Dokumente"
                else
                    # Default to Documents
                    DOCS_DIR="$USER_HOME/Documents"
                fi
                DOCS_APP_DIR="$DOCS_DIR/OpenVPN-Py"
                mkdir -p "$DOCS_APP_DIR" 2>/dev/null || true
                # Create per-config symlink and a 'current' symlink
                ln -sfn "$SERVICE_LOG" "$DOCS_APP_DIR/openvpn-${CONFIG_INSTANCE_RAW}.log" 2>/dev/null || true
                ln -sfn "$SERVICE_LOG" "$DOCS_APP_DIR/openvpn-current.log" 2>/dev/null || true
                # Ensure user owns the symlinks directory for convenience
                chown -R "$SUDO_USER":"$SUDO_USER" "$DOCS_APP_DIR" 2>/dev/null || true
            fi
        fi

        # Persist chosen unit name (escaped) for status checks even if the unit exits quickly
        echo "$SERVICE_FULL" > "$LOG_DIR/${BASE_UNIT_PREFIX_RAW}.lastunit" 2>/dev/null || true

        # Build up/down arguments and mitigate DNS hooks causing fatal exits
        # Start with no script-security setting; we will set it explicitly below
        UPDOWN_ARGS=()
        # By default use the original config. If we must disable or override scripts, we'll create a sanitized copy.
        EFFECTIVE_CONFIG="$CONFIG_PATH"
        SANITIZE_CONFIG=0

        # Detect if the config defines up/down hooks
        HAS_UPDOWN=0
        if grep -Eq '(^|[[:space:]])(up|down)[[:space:]]+' "$CONFIG_PATH"; then
            HAS_UPDOWN=1
        fi

        # Detect references to legacy or systemd-resolved scripts in config
        HAS_RESOLV_SCRIPTS=0
        if grep -Eq 'update-resolv-conf|update-systemd-resolved' "$CONFIG_PATH"; then
            HAS_RESOLV_SCRIPTS=1
        fi

        # Prefer systemd-resolved integration when available
        HAVE_RESOLVED_SCRIPT=0
        RESOLVED_SCRIPT=""
        for s in \
            "/etc/openvpn/update-systemd-resolved" \
            "/etc/openvpn/scripts/update-systemd-resolved" \
            "/usr/libexec/openvpn/update-systemd-resolved" \
            "/usr/lib/openvpn/plugins/update-systemd-resolved"; do
            if [ -x "$s" ]; then
                RESOLVED_SCRIPT="$s"
                HAVE_RESOLVED_SCRIPT=1
                break
            fi
        done

        # Try to locate the optional systemd-resolved OpenVPN plugin
        PLUGIN_PATH=""
        for p in \
            "/usr/lib/x86_64-linux-gnu/openvpn/plugins/openvpn-plugin-systemd-resolved.so" \
            "/usr/lib/openvpn/plugins/openvpn-plugin-systemd-resolved.so" \
            "/usr/lib64/openvpn/plugins/openvpn-plugin-systemd-resolved.so" \
            "/lib/openvpn/plugins/openvpn-plugin-systemd-resolved.so" \
            "/usr/lib64/openvpn/plugins/systemd-resolved/openvpn-plugin-systemd-resolved.so"; do
            if [ -f "$p" ]; then
                PLUGIN_PATH="$p"
                break
            fi
        done

        # Allow forcing a specific plugin path via environment or flag
        if [ -z "$PLUGIN_PATH" ] && [ -n "${OPENVPN_PY_FORCE_PLUGIN_PATH:-}" ] && [ -f "${OPENVPN_PY_FORCE_PLUGIN_PATH}" ]; then
            PLUGIN_PATH="${OPENVPN_PY_FORCE_PLUGIN_PATH}"
            log "$LOG_PATH" "OPENVPN_PY_FORCE_PLUGIN_PATH set; using plugin at $PLUGIN_PATH."
        fi
        if [ -z "$PLUGIN_PATH" ] && [ -n "$FORCE_PLUGIN_PATH" ] && [ -f "$FORCE_PLUGIN_PATH" ]; then
            PLUGIN_PATH="$FORCE_PLUGIN_PATH"
            log "$LOG_PATH" "--force-plugin flag set; using plugin at $PLUGIN_PATH."
        fi

        # Also detect legacy resolvconf integration script as a secondary fallback
        HAVE_RESOLVCONF_SCRIPT=0
        RESOLVCONF_SCRIPT=""
        for s in \
            "/etc/openvpn/update-resolv-conf" \
            "/usr/libexec/openvpn/update-resolv-conf" \
            "/etc/openvpn/scripts/update-resolv-conf"; do
            if [ -x "$s" ]; then
                RESOLVCONF_SCRIPT="$s"
                HAVE_RESOLVCONF_SCRIPT=1
                break
            fi
        done

        # Detect if AppArmor is enforcing OpenVPN profile; if so, running external scripts will likely be denied
        # Pragmatic default: if detection is uncertain, assume NOT enforcing to allow DNS integration.
        # Can be overridden by OPENVPN_PY_ASSUME_AA_ENFORCE=1
        APPARMOR_OPENVPN_ENFORCE=0
        OPENVPN_AA_PROFILE="/etc/apparmor.d/usr.sbin.openvpn"
        AA_STATUS_BIN="$(command -v aa-status 2>/dev/null || true)"
        if [[ -z "$AA_STATUS_BIN" && -x "/usr/sbin/aa-status" ]]; then
            AA_STATUS_BIN="/usr/sbin/aa-status"
        fi
        if [[ ! -e "$OPENVPN_AA_PROFILE" ]]; then
            # If there is no explicit OpenVPN AppArmor profile on disk, do not treat as enforcing
            APPARMOR_OPENVPN_ENFORCE=0
            log "$LOG_PATH" "AppArmor: No OpenVPN profile file at $OPENVPN_AA_PROFILE; treating as not enforcing."
        elif [[ -n "$AA_STATUS_BIN" ]]; then
            AA_OUT="$($AA_STATUS_BIN 2>/dev/null || true)"
            if echo "$AA_OUT" | grep -qE 'profiles are in enforce mode'; then
                # Check if openvpn is among the enforcing profiles section (match exact token or full path)
                if echo "$AA_OUT" | awk '/profiles are in enforce mode/{flag=1; next} /profiles are in complain mode/{flag=0} flag' | grep -qE '(^|[[:space:]])(/usr/sbin/openvpn|usr\.sbin\.openvpn)([[:space:]]|$)'; then
                    APPARMOR_OPENVPN_ENFORCE=1
                    log "$LOG_PATH" "AppArmor: OpenVPN profile is enforcing. External up/down scripts will be avoided."
                else
                    APPARMOR_OPENVPN_ENFORCE=0
                    log "$LOG_PATH" "AppArmor: No enforcing OpenVPN profile detected."
                fi
            else
                APPARMOR_OPENVPN_ENFORCE=0
                log "$LOG_PATH" "AppArmor: No profiles in enforce mode."
            fi
        else
            if [[ "${OPENVPN_PY_ASSUME_AA_ENFORCE:-0}" = "1" ]]; then
                APPARMOR_OPENVPN_ENFORCE=1
                log "$LOG_PATH" "AppArmor: aa-status not found; respecting OPENVPN_PY_ASSUME_AA_ENFORCE=1 (treating as enforcing)."
            else
                APPARMOR_OPENVPN_ENFORCE=0
                log "$LOG_PATH" "AppArmor: aa-status not found; assuming not enforcing to allow DNS integration. Set OPENVPN_PY_ASSUME_AA_ENFORCE=1 to override."
            fi
        fi

        # Decide DNS handling strategy
        DNS_ARGS=()
        if [ -n "$PLUGIN_PATH" ]; then
            # Prefer the systemd-resolved plugin when available
            UPDOWN_ARGS+=(--script-security 2 --plugin "$PLUGIN_PATH")
            log "$LOG_PATH" "Using systemd-resolved plugin: $PLUGIN_PATH (no external up/down scripts)."
            # Add DOMAIN-ROUTE . if supported and not already present in config to force DNS via VPN
            if [[ "$SUPPORTS_DOMAIN_ROUTE" -eq 1 ]]; then
                if ! grep -Eq '(^|[[:space:]])dhcp-option[[:space:]]+DOMAIN-ROUTE' "$CONFIG_PATH"; then
                    DNS_ARGS+=(--dhcp-option DOMAIN-ROUTE .)
                    log "$LOG_PATH" "Adding '--dhcp-option DOMAIN-ROUTE .' to ensure DNS goes via VPN with systemd-resolved."
                fi
            else
                log "$LOG_PATH" "OpenVPN < 2.5 detected; skipping DOMAIN-ROUTE dhcp-option."
            fi
            # Sanitize config if it defines any up/down or resolv scripts or plugin to avoid conflicts
            if [ "$HAS_UPDOWN" -eq 1 ] || [ "$HAS_RESOLV_SCRIPTS" -eq 1 ]; then
                SANITIZE_CONFIG=1
            fi
        elif { [ "$DISABLE_EXTERNAL_FLAG" != "1" ] && [ "${OPENVPN_PY_DISABLE_EXTERNAL:-0}" != "1" ]; } && [ "$HAVE_RESOLVED_SCRIPT" -eq 1 ] && [ "$APPARMOR_OPENVPN_ENFORCE" -eq 0 ]; then
            # Fallback: use update-systemd-resolved script when plugin is missing and AppArmor allows scripts
            UPDOWN_ARGS+=(--script-security 2 --up "$RESOLVED_SCRIPT" --down "$RESOLVED_SCRIPT" --down-pre)
            log "$LOG_PATH" "Using systemd-resolved script: $RESOLVED_SCRIPT."
            if [[ "$SUPPORTS_DOMAIN_ROUTE" -eq 1 ]]; then
                if ! grep -Eq '(^|[[:space:]])dhcp-option[[:space:]]+DOMAIN-ROUTE' "$CONFIG_PATH"; then
                    DNS_ARGS+=(--dhcp-option DOMAIN-ROUTE .)
                    log "$LOG_PATH" "Adding '--dhcp-option DOMAIN-ROUTE .' for systemd-resolved script."
                fi
            else
                log "$LOG_PATH" "OpenVPN < 2.5 detected; skipping DOMAIN-ROUTE dhcp-option (script fallback)."
            fi
            # Sanitize original config if it contains conflicting hooks
            if [ "$HAS_UPDOWN" -eq 1 ] || [ "$HAS_RESOLV_SCRIPTS" -eq 1 ]; then
                SANITIZE_CONFIG=1
            fi
        elif { [ "$DISABLE_EXTERNAL_FLAG" != "1" ] && [ "${OPENVPN_PY_DISABLE_EXTERNAL:-0}" != "1" ]; } && [ "$HAVE_RESOLVCONF_SCRIPT" -eq 1 ] && [ "$APPARMOR_OPENVPN_ENFORCE" -eq 0 ]; then
            # Secondary fallback: legacy resolvconf integration
            UPDOWN_ARGS+=(--script-security 2 --up "$RESOLVCONF_SCRIPT" --down "$RESOLVCONF_SCRIPT" --down-pre)
            log "$LOG_PATH" "Using resolvconf script: $RESOLVCONF_SCRIPT."
            # Sanitize original config if it contains conflicting hooks
            if [ "$HAS_UPDOWN" -eq 1 ] || [ "$HAS_RESOLV_SCRIPTS" -eq 1 ]; then
                SANITIZE_CONFIG=1
            fi
        else
            # No DNS integration available; disable external scripts
            UPDOWN_ARGS+=(--script-security 0)
            if [ -z "$PLUGIN_PATH" ]; then
                log "$LOG_PATH" "No systemd-resolved plugin found in standard paths. External scripts unavailable or blocked; disabling scripts. DNS may leak."
                log "$LOG_PATH" "Searched plugin paths: /usr/lib/x86_64-linux-gnu/openvpn/plugins/openvpn-plugin-systemd-resolved.so, /usr/lib/openvpn/plugins/openvpn-plugin-systemd-resolved.so, /usr/lib64/openvpn/plugins/openvpn-plugin-systemd-resolved.so, /lib/openvpn/plugins/openvpn-plugin-systemd-resolved.so, /usr/lib64/openvpn/plugins/systemd-resolved/openvpn-plugin-systemd-resolved.so"
            fi
            if [ "$HAS_UPDOWN" -eq 1 ] || [ "$HAS_RESOLV_SCRIPTS" -eq 1 ]; then
                log "$LOG_PATH" "Config contains up/down or resolv scripts but no compatible DNS integration found (or AppArmor enforcing). Disabling scripts and sanitizing config. DNS may leak."
                SANITIZE_CONFIG=1
            else
                log "$LOG_PATH" "No DNS integration (systemd-resolved plugin/script or resolvconf script) found; running with script-security 0. DNS may leak."
            fi
        fi

        # If scripts are disabled OR we override legacy hooks, sanitize the config by stripping any up/down/script-security
        if [ "$SANITIZE_CONFIG" -eq 1 ]; then
            # Write sanitized config to a stable location readable by OpenVPN and not subject to /run timing
            SANITIZED_DIR="/etc/openvpn/openvpn-py/sanitized"
            SANITIZED_CONFIG="$SANITIZED_DIR/${CONFIG_NAME}.sanitized.ovpn"
            mkdir -p "$SANITIZED_DIR" 2>/dev/null || true
            chmod 0750 "$SANITIZED_DIR" 2>/dev/null || true
            # Remove any lines defining up/down/down-pre or referencing update-resolv-conf/update-systemd-resolved; also drop any existing script-security
            # Additionally, remove OpenVPN's own logging/status directives so output is centralized in our log
            if sed -E '/(^|[[:space:]])(up|down|down-pre)[[:space:]]+|update-resolv-conf|update-systemd-resolved|^script-security[[:space:]]|^log-append[[:space:]]|^log[[:space:]]|^status[[:space:]]|^suppress-timestamps[[:space:]]|^plugin[[:space:]].*systemd-resolved/d' "$CONFIG_PATH" > "$SANITIZED_CONFIG" 2>/dev/null; then
                EFFECTIVE_CONFIG="$SANITIZED_CONFIG"
                log "$LOG_PATH" "Using sanitized config at $SANITIZED_CONFIG to avoid legacy external scripts."
            else
                log "$LOG_PATH" "Failed to create sanitized config; proceeding with original which may still fail due to script-security or legacy hooks."
            fi
        fi

        # Determine verbosity: default to very detailed unless config already sets 'verb'
        # Allow override via environment variable OPENVPN_PY_VERB
        VERB_ARGS=()
        VERB_DEFAULT="${OPENVPN_PY_VERB:-7}"
        if ! grep -Eq '(^|[[:space:]])verb[[:space:]]+[0-9]+' "$CONFIG_PATH"; then
            VERB_ARGS+=(--verb "$VERB_DEFAULT")
            log "$LOG_PATH" "No 'verb' found in config. Using --verb $VERB_DEFAULT for detailed logging."
        else
            log "$LOG_PATH" "Config defines 'verb'; leaving verbosity as configured."
        fi

        # Start OpenVPN as a transient service. Redirect stdout/stderr to our log via systemd
        # to avoid AppArmor denials when OpenVPN writes logs itself.
        # Do NOT use --collect so the unit remains in systemd and can be queried after exit
        systemd-run --unit "$SERVICE_UNIT_NAME" \
            --description "OpenVPN GUI client for $CONFIG_NAME" \
            --property=StandardOutput=append:"$SERVICE_LOG" \
            --property=StandardError=append:"$SERVICE_LOG" \
            "$OPENVPN_BIN" \
            --config "$EFFECTIVE_CONFIG" \
            "${VERB_ARGS[@]}" \
            "${DNS_ARGS[@]}" \
            "${UPDOWN_ARGS[@]}" \
            --auth-user-pass "$AUTH_FILE" \
            --auth-nocache

        log "$LOG_PATH" "systemd-run command issued for $SERVICE_UNIT_NAME."
        ;;
    stop)
        CONFIG_NAME="$1" # Expects just the filename, e.g., "my-vpn.ovpn"
        LOG_PATH="$2"
        CONFIG_INSTANCE_RAW="${CONFIG_NAME%.*}"
        CONFIG_INSTANCE_ESC="$(escape_instance "$CONFIG_INSTANCE_RAW")"
        BASE_UNIT_PREFIX_RAW="openvpn-py-gui@${CONFIG_INSTANCE_RAW}"
        BASE_UNIT_PREFIX_ESC="openvpn-py-gui@${CONFIG_INSTANCE_ESC}"
        SERVICE_UNIT_NAME="$BASE_UNIT_PREFIX_ESC"
        SERVICE_FULL="${SERVICE_UNIT_NAME}.service"

        log "$LOG_PATH" "Stop command received for service base: $SERVICE_UNIT_NAME"

        # Find and stop all matching instances
        declare -a MATCHING_UNITS=()
        mapfile -t MATCHING_UNITS < <(list_matching_units "$SERVICE_UNIT_NAME") || true
        if [ "${#MATCHING_UNITS[@]}" -eq 0 ]; then
            # Fallback to the base unit name
            MATCHING_UNITS=("$SERVICE_FULL")
        fi

        # If we persisted a specific last unit, include it as well
        LASTUNIT_FILE="$LOG_DIR/${BASE_UNIT_PREFIX_RAW}.lastunit"
        if [ -f "$LASTUNIT_FILE" ]; then
            LASTUNIT_NAME="$(cat "$LASTUNIT_FILE" 2>/dev/null || true)"
            if [ -n "$LASTUNIT_NAME" ]; then
                MATCHING_UNITS+=("$LASTUNIT_NAME")
            fi
        fi

        any_stopped=0

        # Prepare Documents folder for archiving logs
        DOCS_APP_DIR=""
        if [ -n "${SUDO_USER:-}" ]; then
            USER_HOME="$(getent passwd "$SUDO_USER" | awk -F: '{print $6}' 2>/dev/null || true)"
            if [ -n "$USER_HOME" ] && [ -d "$USER_HOME" ]; then
                if [ -d "$USER_HOME/Documents" ]; then
                    DOCS_DIR="$USER_HOME/Documents"
                elif [ -d "$USER_HOME/Dokumente" ]; then
                    DOCS_DIR="$USER_HOME/Dokumente"
                else
                    DOCS_DIR="$USER_HOME/Documents"
                fi
                DOCS_APP_DIR="$DOCS_DIR/OpenVPN-Py"
                mkdir -p "$DOCS_APP_DIR" 2>/dev/null || true
            fi
        fi

        for u in "${MATCHING_UNITS[@]}"; do
            if systemctl is-active --quiet "$u" 2>/dev/null; then
                systemctl stop "$u" 2>/dev/null || true
                any_stopped=1
                log "$LOG_PATH" "Service '$u' stopped."
            fi
            systemctl reset-failed "$u" 2>/dev/null || true
            if [ -f "/run/systemd/transient/$u" ]; then
                rm -f "/run/systemd/transient/$u" || true
            fi

            # Archive the last session log into Documents before removal
            if [ -n "$DOCS_APP_DIR" ] && [ -f "$LOG_DIR/${u}.log" ]; then
                ts="$(date +%Y%m%d-%H%M%S)"
                dest="$DOCS_APP_DIR/openvpn-${CONFIG_INSTANCE_RAW}-${ts}.log"
                cp -f "$LOG_DIR/${u}.log" "$dest" 2>/dev/null || true
                ln -sfn "$dest" "$DOCS_APP_DIR/openvpn-current.log" 2>/dev/null || true
                ln -sfn "$dest" "$DOCS_APP_DIR/openvpn-${CONFIG_INSTANCE_RAW}.log" 2>/dev/null || true
                chown -R "$SUDO_USER":"$SUDO_USER" "$DOCS_APP_DIR" 2>/dev/null || true
                log "$LOG_PATH" "Archived session log to $dest and updated Documents symlinks."

                # Prune older archives, keep most recent 20 for this config
                mapfile -t _archives < <(ls -1t "$DOCS_APP_DIR/openvpn-${CONFIG_INSTANCE_RAW}-"*.log 2>/dev/null || true)
                if [ "${#_archives[@]}" -gt 20 ]; then
                    to_delete=("${_archives[@]:20}")
                    for f in "${to_delete[@]}"; do
                        rm -f "$f" 2>/dev/null || true
                    done
                    log "$LOG_PATH" "Pruned ${#to_delete[@]} old archived logs for ${CONFIG_INSTANCE_RAW}, kept latest 20."
                fi
            fi
        done
        systemctl daemon-reload || true

        # Remove any auth files and transient logs associated with the unit(s)
        if [ "${#MATCHING_UNITS[@]}" -gt 0 ]; then
            for u in "${MATCHING_UNITS[@]}"; do
                rm -f "$AUTH_DIR/${u}.auth" || true
                rm -f "$LOG_DIR/${u}.log" || true
                # Cleanup legacy location if present
                rm -f "/run/openvpn-py/${u}.auth" || true
            done
            rmdir "$AUTH_DIR" 2>/dev/null || true
            rmdir "/run/openvpn-py" 2>/dev/null || true
        fi

        # Remove state file for this base instance (raw-based key)
        rm -f "$LOG_DIR/${BASE_UNIT_PREFIX_RAW}.lastunit" 2>/dev/null || true

        if [ $any_stopped -eq 0 ]; then
            log "$LOG_PATH" "No running matching services were found for base '$SERVICE_UNIT_NAME'."
            echo "INFO: Service was not running." >&2
        fi
        ;;
    status)
        CONFIG_NAME="$1" # Expects just the filename
        CONFIG_INSTANCE_RAW="${CONFIG_NAME%.*}"
        CONFIG_INSTANCE_ESC="$(escape_instance "$CONFIG_INSTANCE_RAW")"
        BASE_UNIT_PREFIX_RAW="openvpn-py-gui@${CONFIG_INSTANCE_RAW}"
        BASE_UNIT_PREFIX_ESC="openvpn-py-gui@${CONFIG_INSTANCE_ESC}"
        SERVICE_UNIT_NAME="$BASE_UNIT_PREFIX_ESC"
        SERVICE_FULL="${SERVICE_UNIT_NAME}.service"

        # Consider any matching instance
        declare -a MATCHING_UNITS=()
        mapfile -t MATCHING_UNITS < <(list_matching_units "$SERVICE_UNIT_NAME") || true
        if [ "${#MATCHING_UNITS[@]}" -eq 0 ]; then
            MATCHING_UNITS=("$SERVICE_FULL")
        fi

        # If we persisted a specific last unit, include it as well for direct queries
        LASTUNIT_FILE="$LOG_DIR/${BASE_UNIT_PREFIX_RAW}.lastunit"
        if [ -f "$LASTUNIT_FILE" ]; then
            LASTUNIT_NAME="$(cat "$LASTUNIT_FILE" 2>/dev/null || true)"
            if [ -n "$LASTUNIT_NAME" ]; then
                MATCHING_UNITS+=("$LASTUNIT_NAME")
            fi
        fi

        for u in "${MATCHING_UNITS[@]}"; do
            if systemctl is-active --quiet "$u" 2>/dev/null; then
                echo "connected"
                exit 0
            fi
        done

        # Use systemctl show to robustly detect failure without relying on name mangling
        for u in "${MATCHING_UNITS[@]}"; do
            # Fetch relevant fields safely
            # Parse properties without eval tricks; request values directly
            Result="$(systemctl show -p Result --value "$u" 2>/dev/null || true)"
            ActiveState="$(systemctl show -p ActiveState --value "$u" 2>/dev/null || true)"
            SubState="$(systemctl show -p SubState --value "$u" 2>/dev/null || true)"
            ExecMainStatus="$(systemctl show -p ExecMainStatus --value "$u" 2>/dev/null || true)"
            ExecMainCode="$(systemctl show -p ExecMainCode --value "$u" 2>/dev/null || true)"
            # Variables now: $Result, $ActiveState, $SubState, $ExecMainStatus, $ExecMainCode (may be empty)
            if [ "${ActiveState:-}" = "failed" ] || [ "${Result:-}" = "failed" ] || [ "${Result:-}" = "exit-code" ]; then
                echo "error"
                exit 0
            fi
            # If the service is inactive/dead but has a non-zero exit status, classify as error
            if [ "${ActiveState:-}" = "inactive" ] && [ "${SubState:-}" = "dead" ]; then
                if [ -n "${ExecMainStatus:-}" ] && [ "${ExecMainStatus:-}" != "0" ]; then
                    echo "error"
                    exit 0
                fi
                if [ -n "${ExecMainCode:-}" ] && [ "${ExecMainCode:-}" != "0" ]; then
                    echo "error"
                    exit 0
                fi
            fi
        done

        # Fallback: inspect latest log file for this instance prefix (check escaped first, then raw) to detect errors even if unit was GC'd
        BASE_UNIT_PREFIX_ESC="openvpn-py-gui@${CONFIG_INSTANCE_ESC}"
        BASE_UNIT_PREFIX_RAW="openvpn-py-gui@${CONFIG_INSTANCE_RAW}"
        latest_log="$(ls -t "$LOG_DIR/${BASE_UNIT_PREFIX_ESC}.service.log" "$LOG_DIR/${BASE_UNIT_PREFIX_ESC}-"*.service.log "$LOG_DIR/${BASE_UNIT_PREFIX_RAW}.service.log" "$LOG_DIR/${BASE_UNIT_PREFIX_RAW}-"*.service.log 2>/dev/null | head -n1 || true)"
        if [ -n "${latest_log:-}" ] && [ -f "$latest_log" ]; then
            # Read last lines and look for fatal/auth markers
            content_upper="$(tail -n 200 "$latest_log" 2>/dev/null | tr '[:lower:]' '[:upper:]' || true)"
            if echo "$content_upper" | grep -Eq "AUTH_FAILED|AUTH[ _]FAILURE|AUTH FAILED|AUTHENTICATION FAILED|FATAL|FAILED RUNNING COMMAND|ACCESS DENIED|TLS ERROR|VERIFY ERROR|CANNOT RESOLVE|NETWORK IS UNREACHABLE|EXITING DUE TO FATAL ERROR|OPTIONS ERROR|RESOLVE:"; then
                echo "error"
                exit 0
            fi
        fi

        echo "disconnected"
        ;;
    *)
        echo "ERROR: Invalid command '$COMMAND'." >&2
        exit 1
        ;;
esac

exit 0
