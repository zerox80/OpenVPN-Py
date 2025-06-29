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

# Setup error trap
trap 'handle_error $LINENO' ERR

# --- Main Logic ---

# Check for root privileges
if [[ $EUID -ne 0 ]]; then
   echo "ERROR: This script must be run as root." >&2
   exit 1
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
        SERVICE_UNIT_NAME="openvpn-gui-client@${CONFIG_NAME%.*}"

        # Read username and password from stdin and store in a temporary file
        AUTH_FILE=$(mktemp)
        chmod 600 "$AUTH_FILE"
        read -r username
        read -r password
        echo "$username" > "$AUTH_FILE"
        echo "$password" >> "$AUTH_FILE"

        # The 'trap' line below is commented out to fix a bug.
        # It was deleting the temporary password file before OpenVPN could read it.
        # This fix will leave temporary credential files in the /tmp directory.
        # trap 'rm -f "$AUTH_FILE"' EXIT

        log "$LOG_PATH" "Starting OpenVPN service '$SERVICE_UNIT_NAME'..."

        # Use systemd-run to start openvpn as a transient service.
        # This is clean and manages the process well.
        # The service will automatically log to the journal, but --log redirects it.
        systemd-run --unit "$SERVICE_UNIT_NAME" \
                    --description "OpenVPN GUI client for $CONFIG_NAME" \
                    /usr/sbin/openvpn \
                        --config "$CONFIG_PATH" \
                        --auth-user-pass "$AUTH_FILE" \
                        --auth-nocache \
                        --log "$LOG_PATH"

        log "$LOG_PATH" "systemd-run command issued for $CONFIG_NAME."
        ;;

    stop)
        CONFIG_NAME="$1" # Expects just the filename, e.g., "my-vpn.ovpn"
        LOG_PATH="$2"
        SERVICE_UNIT_NAME="openvpn-gui-client@${CONFIG_NAME%.*}.service"

        log "$LOG_PATH" "Stop command received for service: $SERVICE_UNIT_NAME"

        if systemctl is-active --quiet "$SERVICE_UNIT_NAME"; then
            systemctl stop "$SERVICE_UNIT_NAME"
            log "$LOG_PATH" "Service '$SERVICE_UNIT_NAME' stopped successfully."
        else
            log "$LOG_PATH" "Service '$SERVICE_UNIT_NAME' was not running."
            echo "INFO: Service was not running." >&2
        fi
        ;;

    status)
        CONFIG_NAME="$1" # Expects just the filename
        SERVICE_UNIT_NAME="openvpn-gui-client@${CONFIG_NAME%.*}.service"

        if systemctl is-active --quiet "$SERVICE_UNIT_NAME"; then
            echo "connected"
        elif systemctl is-failed --quiet "$SERVICE_UNIT_NAME"; then
            echo "error"
        else
            echo "disconnected"
        fi
        ;;

    *)
        echo "ERROR: Invalid command '$COMMAND'." >&2
        exit 1
        ;;
esac

exit 0
