#!/bin/bash
set -euo pipefail

# ============================================================================
# Uninstall Script for OpenVPN GUI
# ============================================================================

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Root-Check
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[ERROR]${NC} Dieses Script muss mit sudo ausgeführt werden"
    exit 1
fi

echo -e "${YELLOW}OpenVPN GUI Deinstallation${NC}"
echo "=============================="

# Variablen
SERVICE_NAME="openvpn-gui"
BIN_PATH="/usr/local/bin/${SERVICE_NAME}"
HELPER_PATH="/usr/local/bin/${SERVICE_NAME}-helper"
INSTALL_DIR="/usr/local/share/${SERVICE_NAME}"
DESKTOP_FILE="/usr/share/applications/${SERVICE_NAME}.desktop"
SUDOERS_FILE="/etc/sudoers.d/${SERVICE_NAME}-sudo"

# Prozesse beenden
echo "Beende laufende Prozesse..."
pkill -f "${SERVICE_NAME}" 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true

# Binärdateien entfernen
if [ -f "${BIN_PATH}" ]; then
    echo "Entferne Wrapper-Skript..."
    rm -v "${BIN_PATH}"
fi
if [ -f "${HELPER_PATH}" ]; then
    echo "Entferne Helper-Skript..."
    rm -v "${HELPER_PATH}"
fi

# Installationsverzeichnis entfernen
if [ -d "${INSTALL_DIR}" ]; then
    echo "Entferne Installationsverzeichnis..."
    rm -rv "${INSTALL_DIR}"
fi

# Desktop-Einträge entfernen
if [ -f "${DESKTOP_FILE}" ]; then
    echo "Entferne Desktop-Eintrag..."
    rm -v "${DESKTOP_FILE}"
    update-desktop-database /usr/share/applications/ 2>/dev/null || true
fi

# Sudoers-Regel entfernen
if [ -f "${SUDOERS_FILE}" ]; then
    echo "Entferne Sudoers-Regel..."
    rm -v "${SUDOERS_FILE}"
fi

echo ""
echo -e "${GREEN}Deinstallation abgeschlossen!${NC}"
echo ""
echo "Folgende Ressourcen wurden NICHT entfernt:"
echo "  - Ihre VPN-Konfigurationsdateien"
echo "  - Ihre Benutzer-Konfiguration unter ~/.config/openvpn-gui/"
echo "  - Ihre gespeicherten Anmeldedaten im System-Schlüsselbund"