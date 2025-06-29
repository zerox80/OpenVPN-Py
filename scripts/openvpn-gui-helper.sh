#!/bin/bash

# Strict-Modus für mehr Sicherheit und bessere Fehlererkennung
set -euo pipefail

# --- Konfiguration ---
LOG_FILE="/var/log/openvpn-gui.log"
OVPN_CONFIG_DIR="/etc/openvpn/client"

# --- Hilfsfunktionen ---

# Funktion zum Loggen von Nachrichten
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Funktion zur Fehlerbehandlung
handle_error() {
    local exit_code=$?
    local error_message="ERROR: Zeile $1: Befehl schlug mit Exit-Code $exit_code fehl."
    echo "$error_message" >&2 # Fehler nach stderr ausgeben
    log "$error_message"
    exit "$exit_code"
}

# Trap für Fehler einrichten
trap 'handle_error $LINENO' ERR

# --- Hauptlogik ---

# Überprüfen, ob das Skript mit Root-Rechten läuft
if [[ $EUID -ne 0 ]]; then
   echo "ERROR: Dieses Skript muss als root ausgeführt werden." >&2
   exit 1
fi

# Sicherstellen, dass die Log-Datei existiert und die richtigen Berechtigungen hat
touch "$LOG_FILE"
chown root:adm "$LOG_FILE"
chmod 640 "$LOG_FILE"

log "Helper-Skript gestartet mit Befehl: '$*'"

COMMAND=$1
shift || true # Fehler ignorieren, wenn keine weiteren Argumente vorhanden sind

case "$COMMAND" in
    start)
        CONFIG_NAME=$1
        # Sicherheitsprüfung: Verhindern von Path-Traversal-Angriffen
        if [[ "$CONFIG_NAME" != "$(basename "$CONFIG_NAME")" || -z "$CONFIG_NAME" ]]; then
            echo "ERROR: Ungültiger Konfigurationsname '$CONFIG_NAME'." >&2
            log "ERROR: Ungültiger Konfigurationsname '$CONFIG_NAME'."
            exit 1
        fi
        
        CONFIG_PATH="$OVPN_CONFIG_DIR/$CONFIG_NAME"
        
        if [ ! -f "$CONFIG_PATH" ]; then
            echo "ERROR: Konfigurationsdatei nicht gefunden: $CONFIG_PATH." >&2
            log "ERROR: Konfigurationsdatei nicht gefunden: $CONFIG_PATH."
            exit 1
        fi
        
        log "Starte OpenVPN-Dienst mit Konfiguration: $CONFIG_NAME"
        # --auth-nocache verhindert das Cachen des Passworts im Speicher
        systemd-run --unit "openvpn-gui-client@${CONFIG_NAME%.conf}" \
                    --description "OpenVPN GUI client for ${CONFIG_NAME%.conf}" \
                    /usr/sbin/openvpn --config "$CONFIG_PATH" --auth-nocache
        log "OpenVPN-Dienst für $CONFIG_NAME gestartet."
        ;;
    stop)
        CONFIG_NAME=$1
        # Sicherheitsprüfung
        if [[ "$CONFIG_NAME" != "$(basename "$CONFIG_NAME")" || -z "$CONFIG_NAME" ]]; then
            echo "ERROR: Ungültiger Konfigurationsname '$CONFIG_NAME'." >&2
            log "ERROR: Ungültiger Konfigurationsname '$CONFIG_NAME'."
            exit 1
        fi
        
        SERVICE_NAME="openvpn-gui-client@${CONFIG_NAME%.conf}.service"
        log "Stoppe OpenVPN-Dienst: $SERVICE_NAME"
        
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            systemctl stop "$SERVICE_NAME"
            log "Dienst $SERVICE_NAME erfolgreich gestoppt."
        else
            echo "INFO: Dienst $SERVICE_NAME lief nicht." >&2
            log "INFO: Dienst $SERVICE_NAME lief nicht, kein Stoppen erforderlich."
        fi
        ;;
    status)
        CONFIG_NAME=$1
        # Sicherheitsprüfung
        if [[ "$CONFIG_NAME" != "$(basename "$CONFIG_NAME")" || -z "$CONFIG_NAME" ]]; then
            # Still, aber nicht fehlerhaft beenden, wenn kein Name gegeben ist (z.B. beim Start)
            exit 1
        fi
        
        SERVICE_NAME="openvpn-gui-client@${CONFIG_NAME%.conf}.service"
        
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            echo "connected"
        elif systemctl is-failed --quiet "$SERVICE_NAME"; then
            echo "error"
        else
            echo "disconnected"
        fi
        ;;
    check)
        # Dieser Befehl dient nur zur Überprüfung, ob das Skript erfolgreich ausgeführt werden kann.
        log "Check-Befehl erfolgreich ausgeführt."
        echo "OK"
        ;;
    *)
        echo "ERROR: Ungültiger Befehl '$COMMAND'." >&2
        log "ERROR: Ungültiger Befehl '$COMMAND'."
        exit 1
        ;;
esac

exit 0