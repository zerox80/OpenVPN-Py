#!/bin/bash
set -euo pipefail

# ============================================================================
# OpenVPN GUI Installation Script (Python Version)
# Sicher und robust für Ubuntu-Systeme
# ============================================================================

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging-Funktionen
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================================
# Globale Variablen
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/usr/local/share/openvpn-gui"
HELPER_SCRIPT_PATH="/usr/local/bin/openvpn-gui-helper"
WRAPPER_SCRIPT_PATH="/usr/local/bin/openvpn-gui"
SUDOERS_FILE="/etc/sudoers.d/openvpn-gui-sudo"
LOG_FILE="/tmp/openvpn-gui-install-$(date +%Y%m%d-%H%M%S).log"

# ============================================================================
# Fehlerbehandlung
# ============================================================================
cleanup_on_error() {
    local exit_code=$?
    log_error "Installation fehlgeschlagen (Exit Code: $exit_code)"
    log_error "Siehe Log-Datei: $LOG_FILE"
    
    log_info "Bereinige teilweise Installation..."
    [[ -f "$WRAPPER_SCRIPT_PATH" ]] && rm -f "$WRAPPER_SCRIPT_PATH"
    [[ -f "$HELPER_SCRIPT_PATH" ]] && rm -f "$HELPER_SCRIPT_PATH"
    [[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR"
    [[ -f /usr/share/applications/openvpn-gui.desktop ]] && rm -f /usr/share/applications/openvpn-gui.desktop
    [[ -f "$SUDOERS_FILE" ]] && rm -f "$SUDOERS_FILE"
    
    exit $exit_code
}
trap cleanup_on_error ERR
exec &> >(tee -a "$LOG_FILE")

# ============================================================================
# Hilfsfunktionen
# ============================================================================
create_helper_script() {
    log_info "Erstelle sicheres Helper-Skript unter $HELPER_SCRIPT_PATH..."
    if [[ ! -f "$PROJECT_DIR/scripts/openvpn-gui-helper.sh" ]]; then
        log_error "Helper-Skript 'openvpn-gui-helper.sh' nicht im 'scripts'-Verzeichnis gefunden!"
        exit 1
    fi
    cp "$PROJECT_DIR/scripts/openvpn-gui-helper.sh" "$HELPER_SCRIPT_PATH"
    chmod 755 "$HELPER_SCRIPT_PATH"
    chown root:root "$HELPER_SCRIPT_PATH"
}

create_sudoers_rule() {
    log_info "Konfiguriere sudoers für sicheren Zugriff..."
    SUDOERS_CONTENT=$(cat <<EOF
# Erlaube $TARGET_USER, OpenVPN GUI Helper-Operationen ohne Passwort auszuführen
$TARGET_USER ALL=(root) NOPASSWD: $HELPER_SCRIPT_PATH start *
$TARGET_USER ALL=(root) NOPASSWD: $HELPER_SCRIPT_PATH stop *
EOF
)
    TMP_SUDOERS_FILE=$(mktemp)
    echo "$SUDOERS_CONTENT" > "$TMP_SUDOERS_FILE"
    if visudo -cf "$TMP_SUDOERS_FILE"; then
        log_success "Sudoers-Syntax ist korrekt."
        echo "$SUDOERS_CONTENT" > "$SUDOERS_FILE"
        chmod 0440 "$SUDOERS_FILE"
        log_success "Sichere Sudoers-Regel in $SUDOERS_FILE geschrieben."
    else
        log_error "Sudoers-Syntax ist fehlerhaft. Breche Installation ab."
        rm -f "$TMP_SUDOERS_FILE"
        exit 1
    fi
    rm -f "$TMP_SUDOERS_FILE"
}

# ============================================================================
# Haupt-Skript
# ============================================================================
log_info "Prüfe Voraussetzungen..."
if [[ $EUID -ne 0 ]]; then log_error "Dieses Script muss mit sudo ausgeführt werden"; exit 1; fi
if [[ ! -f "$PROJECT_DIR/main.py" ]]; then log_error "main.py nicht gefunden. Bitte im 'scripts' Verzeichnis ausführen."; exit 1; fi

TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
if [[ -z "$TARGET_USER" || "$TARGET_USER" == "root" ]]; then log_error "Konnte Ziel-User nicht ermitteln."; exit 1; fi
log_info "Installiere für User: $TARGET_USER"

log_info "Installiere System-Abhängigkeiten..."
apt-get update -qq
PACKAGES=(python3 python3-pip python3-venv openvpn policykit-1 libxcb-cursor0 python3-keyring)
apt-get install -y "${PACKAGES[@]}"

log_info "Konfiguriere OpenVPN..."
mkdir -p /etc/openvpn/client
if ! getent group openvpn > /dev/null 2>&1; then groupadd --system openvpn; fi
usermod -aG openvpn "$TARGET_USER"

create_helper_script
create_sudoers_rule

log_info "Kopiere Projekt-Dateien..."
[[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp "$PROJECT_DIR"/*.py "$INSTALL_DIR/"
cp "$PROJECT_DIR"/requirements.txt "$INSTALL_DIR/"
[[ -d "$PROJECT_DIR/resources" ]] && cp -r "$PROJECT_DIR/resources" "$INSTALL_DIR/"
chown -R root:root "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

log_info "Richte Python virtuelle Umgebung ein..."
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$INSTALL_DIR/requirements.txt"
deactivate

log_info "Erstelle Wrapper-Skript..."
cat > "$WRAPPER_SCRIPT_PATH" << EOF
#!/bin/bash
export QT_QPA_PLATFORM=xcb
export PYTHONPATH="$INSTALL_DIR:\$PYTHONPATH"
source "$INSTALL_DIR/venv/bin/activate"
exec python3 "$INSTALL_DIR/main.py" "\$@"
EOF
chmod 755 "$WRAPPER_SCRIPT_PATH"

log_info "Konfiguriere Desktop-Integration..."
RESOURCES_DIR="$INSTALL_DIR/resources"
mkdir -p "$RESOURCES_DIR"
if [[ ! -f "$RESOURCES_DIR/vpn-icon.png" ]]; then log_warning "Kein Icon gefunden, wird ggf. erstellt."; fi
cat > /usr/share/applications/openvpn-gui.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=OpenVPN GUI
Comment=Manage OpenVPN connections
Exec=$WRAPPER_SCRIPT_PATH
Icon=$RESOURCES_DIR/vpn-icon.png
Terminal=false
Categories=Network;Security;
EOF
chmod 644 /usr/share/applications/openvpn-gui.desktop
update-desktop-database /usr/share/applications/ 2>/dev/null || true

log_info "Erstelle Benutzer-Konfigurationsverzeichnisse..."
USER_CONFIG_DIR="$TARGET_HOME/.config/openvpn-gui"
sudo -u "$TARGET_USER" mkdir -p "$USER_CONFIG_DIR"
sudo -u "$TARGET_USER" chmod 700 "$USER_CONFIG_DIR"

echo -e "\n${GREEN}==========================================="
log_success "Installation erfolgreich abgeschlossen!"
echo -e "===========================================${NC}\n"
log_warning "WICHTIG: User '$TARGET_USER' muss sich neu anmelden, damit Gruppenänderungen wirksam werden!"
log_info "Starten Sie die Anwendung über das Menü oder mit: openvpn-gui"