#!/bin/bash

# Rigorose Fehlerprüfung
set -euo pipefail

# Logging-Funktion
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - HELPER: $1" >> "/tmp/openvpn-gui-helper.log"
}

# Funktion zur Überprüfung, ob ein Pfad sicher ist
is_path_allowed() {
    local path_to_check=$1
    local allowed_dir
    local real_path

    # Verhindert Path Traversal Attacken
    if [[ "$path_to_check" == *".."* ]]; then
        log "ERROR: Path contains '..', access denied: $path_to_check"
        return 1
    fi

    # Sicherstellen, dass die Datei im erlaubten Verzeichnis liegt
    real_path=$(realpath "$path_to_check")

    for allowed_dir in "/etc/openvpn" "$HOME/.config/openvpn-py/configs"; do
        if [[ "$(realpath "$allowed_dir")" == "$(dirname "$real_path")" ]]; then
            log "Path is allowed: $real_path"
            return 0
        fi
    done

    log "ERROR: Path is not in an allowed directory: $real_path"
    return 1
}

ACTION=$1
shift # Verschiebt die Argumente nach links ($2 wird zu $1 usw.)

log "Action: $ACTION"

case "$ACTION" in
    start)
        CONFIG_FILE=$1
        LOG_PATH=$2
        PID_DIR=$(dirname "$LOG_PATH") # Leitet das PID-Verzeichnis vom Log-Pfad ab

        if ! is_path_allowed "$CONFIG_FILE"; then
            exit 1
        fi
        
        # Erstellt das Laufzeitverzeichnis, falls es nicht existiert
        mkdir -p "$PID_DIR"
        
        # Eindeutige PID-Datei für diesen Prozess
        PID_FILE=$(mktemp "$PID_DIR/openvpn.pid.XXXXXX")
        
        log "Starting OpenVPN with config: $CONFIG_FILE"
        log "Log will be written to: $LOG_PATH"
        log "PID will be written to: $PID_FILE"

        # Startet OpenVPN als Daemon
        # --auth-nocache: Verhindert das Caching von Passwörtern im Speicher
        # --writepid: Schreibt die Prozess-ID in eine Datei
        openvpn --config "$CONFIG_FILE" \
                --daemon \
                --writepid "$PID_FILE" \
                --log "$LOG_PATH" \
                --auth-user-pass \
                --auth-nocache

        # Gibt den Pfad zur PID-Datei an die Python-Anwendung zurück
        echo "$PID_FILE"
        ;;

    stop)
        PID_FILE=$1
        
        # Sicherheitsprüfung: Stelle sicher, dass die PID-Datei im erwarteten Verzeichnis liegt
        PID_DIR=$(realpath "$(dirname "$PID_FILE")")
        ALLOWED_PID_DIR=$(realpath "$(dirname "$2")") # $2 ist der Log-Pfad, zur Verifizierung

        if [[ "$PID_DIR" != "$ALLOWED_PID_DIR" ]] || [[ "$PID_FILE" == *".."* ]]; then
            log "ERROR: Invalid PID file path provided: $PID_FILE"
            exit 1
        fi

        if [[ -f "$PID_FILE" ]]; then
            PID_TO_KILL=$(cat "$PID_FILE")
            log "Stopping OpenVPN process with PID $PID_TO_KILL from file $PID_FILE"
            # Überprüfen, ob der Prozess noch existiert und ein 'openvpn' Prozess ist
            if ps -p "$PID_TO_KILL" -o comm= | grep -q "openvpn"; then
                kill "$PID_TO_KILL"
                log "Process $PID_TO_KILL killed."
            else
                log "Process $PID_TO_KILL not found or not an OpenVPN process."
            fi
            rm -f "$PID_FILE"
            log "PID file $PID_FILE removed."
        else
            log "ERROR: PID file not found: $PID_FILE"
        fi
        ;;

    *)
        log "ERROR: Unknown action '$ACTION'"
        echo "Unknown action: $ACTION" >&2
        exit 1
        ;;
esac

exit 0