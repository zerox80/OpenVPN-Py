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
INSTALL_DIR="/usr/local/share/${SERVICE_NAME}"
DESKTOP_FILE="/usr/share/applications/${SERVICE_NAME}.desktop"
POLKIT_RULE="/etc/polkit-1/rules.d/50-openvpn-gui.rules"

# Prozesse beenden
echo "Beende laufende Prozesse..."
pkill -f "openvpn-gui" 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true

# Binärdatei entfernen
if [ -f "${BIN_PATH}" ]; then
    echo "Entferne Programm..."
    rm -v "${BIN_PATH}"
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

# Polkit-Regel entfernen
if [ -f "${POLKIT_RULE}" ]; then
    echo "Entferne Polkit-Regel..."
    rm -v "${POLKIT_RULE}"
    systemctl restart polkit
fi

# Benutzer-Desktop-Einträge entfernen
for USER_HOME in /home/*; do
    if [ -d "$USER_HOME" ]; then
        USER_DESKTOP="${USER_HOME}/.local/share/applications/${SERVICE_NAME}.desktop"
        if [ -f "${USER_DESKTOP}" ]; then
            echo "Entferne Desktop-Eintrag für ${USER_HOME}"
            rm -v "${USER_DESKTOP}"
        fi
    fi
done

echo ""
echo -e "${GREEN}Deinstallation abgeschlossen!${NC}"
echo ""
echo "Folgende Ressourcen wurden NICHT entfernt:"
echo "  - VPN-Konfigurationsdateien: /etc/openvpn/client/"
echo "  - Benutzer-Konfiguration: ~/.config/openvpn-gui/"
echo "  - OpenVPN-Gruppe und Gruppenmitgliedschaften"
echo ""
echo "Um diese zu entfernen, führen Sie aus:"
echo "  sudo rm -rf /etc/openvpn/client"
echo "  rm -rf ~/.config/openvpn-gui"
echo "  sudo groupdel openvpn"