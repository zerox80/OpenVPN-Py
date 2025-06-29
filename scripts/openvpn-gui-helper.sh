#!/bin/bash

# /scripts/openvpn-gui-helper.sh

# --- Configuration ---
LOG_FILE="/tmp/openvpn-gui-helper.log"
# Whitelisted directories for OpenVPN configs
ALLOWED_CONFIG_DIRS=(
    "/etc/openvpn/client"
    # User-specific path is now handled dynamically
)

# --- Functions ---

# Function to log messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Function to check if a config path is in a whitelisted directory
is_path_allowed() {
    local config_file_path=$1
    local config_dir

    # Resolve the real path to prevent traversal attacks (e.g., ../)
    config_dir=$(dirname "$(realpath "$config_file_path")")

    # Get the home directory of the user who invoked sudo
    if [[ -n "$SUDO_USER" ]]; then
        local target_home
        target_home=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        local user_config_dir_allowed="$target_home/.config/openvpn-gui/configs"
        ALLOWED_CONFIG_DIRS+=("$user_config_dir_allowed")
    else
        log "WARNING: SUDO_USER not set. User-specific config path will not be allowed."
    fi

    for allowed_dir in "${ALLOWED_CONFIG_DIRS[@]}"; do
        if [[ "$config_dir" == "$allowed_dir" ]]; then
            log "Path $config_file_path is in the allowed directory: $allowed_dir."
            return 0
        fi
    done

    log "ERROR: Path $config_file_path is NOT in any allowed directory."
    return 1
}

# --- Main Logic ---

# Ensure log file exists and has correct permissions
touch "$LOG_FILE"
chmod 644 "$LOG_FILE"

log "Helper script started. Command: $1, Config: $2"

case "$1" in
    start)
        CONFIG_FILE=$2
        if [[ -z "$CONFIG_FILE" ]]; then
            log "ERROR: No config file provided for start command."
            exit 1
        fi

        if ! is_path_allowed "$CONFIG_FILE"; then
            echo "Error: The specified configuration path is not allowed."
            exit 1
        fi

        log "Starting OpenVPN with config: $CONFIG_FILE"
        # Use --daemon to run in the background. OpenVPN will manage its own PID file.
        # Use --log to redirect OpenVPN logs
        # Use --auth-user-pass with a file if credentials are provided via stdin
        openvpn --config "$CONFIG_FILE" --daemon --log /tmp/openvpn_gui_log.log --auth-nocache
        log "OpenVPN start command issued."
        ;;

    stop)
        PID_TO_KILL=$2
        if [[ -z "$PID_TO_KILL" ]]; then
            log "ERROR: No PID provided for stop command."
            exit 1
        fi

        # Security check: Ensure the PID actually belongs to an openvpn process
        if ps -p "$PID_TO_KILL" -o comm= | grep -q "openvpn"; then
            log "Stopping OpenVPN process with PID: $PID_TO_KILL"
            kill "$PID_TO_KILL"
            # Cleanup DNS settings managed by systemd-resolved
            if command -v resolvectl &> /dev/null; then
                log "Reverting DNS settings for tun0 interface."
                resolvectl revert tun0
            fi
            log "OpenVPN process $PID_TO_KILL stopped."
        else
            log "ERROR: PID $PID_TO_KILL does not belong to an OpenVPN process. Not killing."
            exit 1
        fi
        ;;

    *)
        log "ERROR: Invalid command '$1'. Use 'start' or 'stop'."
        echo "Invalid command. Use 'start <config_path>' or 'stop <pid>'."
        exit 1
        ;;
esac

exit 0