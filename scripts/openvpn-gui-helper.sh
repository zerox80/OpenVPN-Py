#!/bin/bash
# ============================================================================
# OpenVPN GUI Helper Script
# Führt privilegierte Operationen sicher aus.
# WIRD VOM INSTALLATIONSSKRIPT IN /usr/local/bin/openvpn-gui-helper ERSTELLT
# ============================================================================
set -euo pipefail

# --- Konfiguration ---
# Erlaubte Pfade für VPN-Konfigurationen. Muss mit install.sh übereinstimmen.
ALLOWED_CONFIG_DIRS=("/etc/openvpn/client" "/home/*/.config/openvpn-gui" "/home/*/.config/openvpn")
OPENVPN_PATH=$(command -v openvpn)
KILL_PATH=$(command -v kill)

# --- Hilfsfunktionen ---
log_error() {
    echo "HELPER-ERROR: $1" >&2
}

# --- Aktionen ---
ACTION="${1:-}"
shift

case "$ACTION" in
    start)
        CONFIG_PATH_ARG="--config"
        CONFIG_PATH=""

        # Finde den Wert des --config Arguments
        while [ "$#" -gt 0 ]; do
            if [ "$1" = "$CONFIG_PATH_ARG" ]; then
                CONFIG_PATH="$2"
                break
            fi
            shift
        done
        
        # Sicherheitsprüfung 1: Stellen Sie sicher, dass ein Konfigurationspfad vorhanden ist
        if [ -z "$CONFIG_PATH" ]; then
            log_error "Kein Konfigurationspfad angegeben."
            exit 1
        fi

        # Sicherheitsprüfung 2: Überprüfen Sie, ob der Pfad in der Whitelist ist
        path_allowed=false
        for dir in "${ALLOWED_CONFIG_DIRS[@]}"; do
            # Verwenden Sie case für Mustervergleich, um Wildcards zu ermöglichen
            case "$CONFIG_PATH" in
                $dir/*) path_allowed=true; break ;;
            esac
        done

        if [ "$path_allowed" = false ]; then
            log_error "Zugriff auf Konfigurationspfad '$CONFIG_PATH' verweigert."
            exit 1
        fi

        # Führen Sie OpenVPN aus.
        exec "$OPENVPN_PATH" "$@"
        ;;

    stop)
        PGID="$1"

        # Sicherheitsprüfung: Stellen Sie sicher, dass PGID eine positive Ganzzahl ist
        if ! [[ "$PGID" =~ ^[0-9]+$ ]] || [ "$PGID" -le 1 ]; then
            log_error "Ungültige oder unsichere Prozessgruppen-ID (PGID) '$PGID' angegeben."
            exit 1
        fi

        # Zuerst versuchen, sauber zu beenden
        if "$KILL_PATH" -SIGTERM -- -"$PGID" 2>/dev/null; then
            # Warte kurz, um dem Prozess Zeit zum Beenden zu geben
            sleep 1
        fi

        # Wenn die Prozessgruppe noch existiert, erzwinge das Beenden
        if pgrep -g "$PGID" > /dev/null; then
             "$KILL_PATH" -SIGKILL -- -"$PGID"
        fi
        ;;

    *)
        log_error "Unbekannte oder keine Aktion angegeben."
        exit 1
        ;;
esac