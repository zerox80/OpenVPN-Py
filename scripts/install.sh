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
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================================
# Globale Variablen
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/usr/local/share/openvpn-gui"
LOG_FILE="/tmp/openvpn-gui-install-$(date +%Y%m%d-%H%M%S).log"

# ============================================================================
# Fehlerbehandlung
# ============================================================================

cleanup_on_error() {
    local exit_code=$?
    log_error "Installation fehlgeschlagen (Exit Code: $exit_code)"
    log_error "Siehe Log-Datei: $LOG_FILE"
    
    log_info "Bereinige teilweise Installation..."
    
    # Entferne installierte Dateien
    [[ -f /usr/local/bin/openvpn-gui ]] && rm -f /usr/local/bin/openvpn-gui
    [[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR"
    [[ -f /usr/share/applications/openvpn-gui.desktop ]] && rm -f /usr/share/applications/openvpn-gui.desktop
    [[ -f /etc/polkit-1/rules.d/50-openvpn-gui.rules ]] && rm -f /etc/polkit-1/rules.d/50-openvpn-gui.rules
    [[ -f /etc/sudoers.d/openvpn-gui-sudo ]] && rm -f /etc/sudoers.d/openvpn-gui-sudo
    
    exit $exit_code
}

trap cleanup_on_error ERR

# Logging in Datei aktivieren
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

# ============================================================================
# Voraussetzungen prüfen
# ============================================================================

log_info "Prüfe Voraussetzungen..."

# Root-Rechte prüfen
if [[ $EUID -ne 0 ]]; then
    log_error "Dieses Script muss mit sudo ausgeführt werden"
    log_info "Verwendung: sudo $0"
    exit 1
fi

# Prüfe ob im richtigen Verzeichnis
if [[ ! -f "$PROJECT_DIR/main.py" ]]; then
    log_error "main.py nicht gefunden. Bitte führen Sie das Script aus dem 'scripts' Verzeichnis aus."
    exit 1
fi

# Ubuntu-Version prüfen
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    if [[ "$ID" != "ubuntu" ]] && [[ "$ID_LIKE" != *"ubuntu"* ]]; then
        log_warning "Nicht-Ubuntu System erkannt: $PRETTY_NAME"
        read -p "Die Installation wurde für Ubuntu entwickelt. Trotzdem fortfahren? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    log_info "System: $PRETTY_NAME"
fi

# User ermitteln
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)

if [[ -z "$TARGET_USER" || "$TARGET_USER" == "root" ]]; then
    log_error "Konnte Ziel-User nicht ermitteln. Bitte mit 'sudo' als normaler Benutzer ausführen."
    exit 1
fi

log_info "Installiere für User: $TARGET_USER (Home: $TARGET_HOME)"

# Python-Version prüfen
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 8 ]]; then
    log_error "Python 3.8 oder höher erforderlich (gefunden: $PYTHON_VERSION)"
    exit 1
fi
log_info "Python-Version: $PYTHON_VERSION"

# ============================================================================
# System-Abhängigkeiten installieren
# ============================================================================

log_info "Aktualisiere Paketquellen..."
apt-get update -qq

log_info "Installiere System-Abhängigkeiten..."

# Basis-Pakete
PACKAGES=(
    python3
    python3-pip
    python3-venv
    python3-dev
    openvpn
    policykit-1
    libxcb-cursor0
    libxcb-xinerama0
)

# Ubuntu-Version spezifische Pakete
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    if [[ "${VERSION_ID}" == "22.04" ]] || [[ "${VERSION_ID}" == "23.10" ]] || [[ "${VERSION_ID}" == "24.04" ]]; then
        PACKAGES+=(python3-pyqt6)
    fi
fi

# DNS-Resolver Script
if [[ -f /etc/openvpn/update-resolv-conf ]]; then
    log_info "DNS-Resolver Script bereits vorhanden"
else
    PACKAGES+=(openvpn-systemd-resolved)
fi

# Installiere Pakete
for package in "${PACKAGES[@]}"; do
    if dpkg -l | grep -q "^ii  $package "; then
        log_info "Paket bereits installiert: $package"
    else
        log_info "Installiere: $package"
        apt-get install -y "$package" || {
            log_error "Konnte $package nicht installieren"
            exit 1
        }
    fi
done

# ============================================================================
# OpenVPN Konfiguration
# ============================================================================

log_info "Konfiguriere OpenVPN..."

# Verzeichnisse erstellen
mkdir -p /etc/openvpn/client
chmod 0755 /etc/openvpn/client

# Gruppe erstellen/prüfen
if getent group openvpn > /dev/null 2>&1; then
    log_info "OpenVPN-Gruppe existiert bereits"
else
    groupadd --system openvpn
    log_success "OpenVPN-Gruppe erstellt"
fi

# User zur Gruppe hinzufügen
if id -nG "$TARGET_USER" | grep -qw "openvpn"; then
    log_info "User $TARGET_USER ist bereits in openvpn-Gruppe"
else
    usermod -aG openvpn "$TARGET_USER"
    log_success "User $TARGET_USER zur openvpn-Gruppe hinzugefügt"
    
    # Direkt die Gruppenmitgliedschaft aktualisieren für aktuelle Session
    log_warning "WICHTIG: User muss sich neu anmelden, damit Gruppenänderungen wirksam werden!"
fi

# ============================================================================
# Sudoers Konfiguration für passwortloses Starten/Stoppen
# ============================================================================

log_info "Konfiguriere sudoers für passwortloses Starten/Stoppen von OpenVPN..."

SUDOERS_FILE_OPENVPN_GUI="/etc/sudoers.d/openvpn-gui-sudo"
# Robust detection of absolute paths for required binaries
OPENVPN_PATH=$(command -v openvpn || true)
if [ -z "$OPENVPN_PATH" ] || [[ ! "$OPENVPN_PATH" = /* ]]; then
    log_warning "Befehl 'openvpn' nicht gefunden oder nicht absolut. Verwende Fallback /usr/sbin/openvpn."
    OPENVPN_PATH="/usr/sbin/openvpn"
fi

# Prefer external kill binary over shell builtin
if [[ -x /bin/kill ]]; then
    KILL_PATH="/bin/kill"
elif [[ -x /usr/bin/kill ]]; then
    KILL_PATH="/usr/bin/kill"
else
    log_warning "Kein externer 'kill' Befehl gefunden. Sudoers-Regel für Stoppen könnte fehlschlagen. Verwende Fallback /bin/kill."
    KILL_PATH="/bin/kill"
fi

log_info "Verwende Pfad '$OPENVPN_PATH' für 'openvpn' in der Sudoers-Regel."
log_info "Verwende Pfad '$KILL_PATH' für 'kill' in der Sudoers-Regel."

# Erstelle Sudoers-Regel Inhalt
# TARGET_USER wird durch den Benutzernamen ersetzt, der das Skript ausführt (z.B. rujbin)
# Erlaube spezifische Kommandos:
# 1. openvpn mit beliebigen Argumenten (für das Starten der Verbindung)
# 2. kill -SIGTERM -<PGID> (um die Prozessgruppe sauber zu beenden)
# 3. kill -SIGKILL -<PGID> (um die Prozessgruppe hart zu beenden, falls SIGTERM fehlschlägt)
# 4. kill -SIGTERM <PID> (Fallback, falls PGID nicht verfügbar)
# 5. kill -SIGKILL <PID> (Fallback, falls PGID nicht verfügbar)
SUDOERS_CONTENT=$(cat <<EOF
# Erlaube $TARGET_USER, OpenVPN GUI Operationen ohne Passwort auszuführen
$TARGET_USER ALL=(root) NOPASSWD: $OPENVPN_PATH *
$TARGET_USER ALL=(root) NOPASSWD: $KILL_PATH -SIGTERM -*
$TARGET_USER ALL=(root) NOPASSWD: $KILL_PATH -TERM -*
$TARGET_USER ALL=(root) NOPASSWD: $KILL_PATH -15 -*
$TARGET_USER ALL=(root) NOPASSWD: $KILL_PATH -SIGKILL -*
$TARGET_USER ALL=(root) NOPASSWD: $KILL_PATH -KILL -*
$TARGET_USER ALL=(root) NOPASSWD: $KILL_PATH -9 -*
$TARGET_USER ALL=(root) NOPASSWD: $KILL_PATH -SIGTERM *
$TARGET_USER ALL=(root) NOPASSWD: $KILL_PATH -TERM *
$TARGET_USER ALL=(root) NOPASSWD: $KILL_PATH -15 *
$TARGET_USER ALL=(root) NOPASSWD: $KILL_PATH -SIGKILL *
$TARGET_USER ALL=(root) NOPASSWD: $KILL_PATH -KILL *
$TARGET_USER ALL=(root) NOPASSWD: $KILL_PATH -9 *
EOF
)

# Temporäre Datei für visudo Syntax-Check
TMP_SUDOERS_FILE=$(mktemp)
echo "$SUDOERS_CONTENT" > "$TMP_SUDOERS_FILE"

# Syntax prüfen
if visudo -cf "$TMP_SUDOERS_FILE"; then
    log_success "Sudoers-Syntax ist korrekt."
    # Sudoers-Datei schreiben
    echo "$SUDOERS_CONTENT" > "$SUDOERS_FILE_OPENVPN_GUI"
    chmod 0440 "$SUDOERS_FILE_OPENVPN_GUI"
    log_success "Sudoers-Regel in $SUDOERS_FILE_OPENVPN_GUI geschrieben."
else
    log_error "Sudoers-Syntax ist fehlerhaft. Bitte manuell prüfen: $TMP_SUDOERS_FILE"
    log_error "Die Regel wurde NICHT angewendet."
    # Hier könnten wir entscheiden, ob wir abbrechen oder mit Warnung fortfahren
    # Fürs Erste brechen wir ab, da dies ein kritisches Feature ist.
    rm -f "$TMP_SUDOERS_FILE"
    exit 1
fi

rm -f "$TMP_SUDOERS_FILE"

# ============================================================================
# Projekt-Dateien kopieren
# ============================================================================

log_info "Kopiere Projekt-Dateien..."

# Alte Installation entfernen
[[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR"

# Installationsverzeichnis erstellen
mkdir -p "$INSTALL_DIR"

# Dateien kopieren
REQUIRED_FILES=(
    "main.py"
    "config_manager.py"
    "credentials_manager.py"
    "credentials_dialog.py"
    "vpn_manager.py"
    "constants.py"
    "requirements.txt"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$PROJECT_DIR/$file" ]]; then
        cp "$PROJECT_DIR/$file" "$INSTALL_DIR/"
        log_info "Kopiert: $file"
    else
        log_error "Erforderliche Datei fehlt: $file"
        exit 1
    fi
done

# Kopiere optionale Verzeichnisse
for dir in "resources" "ui"; do
    if [[ -d "$PROJECT_DIR/$dir" ]]; then
        cp -r "$PROJECT_DIR/$dir" "$INSTALL_DIR/"
        log_info "Kopiert: $dir/"
    fi
done

# Berechtigungen setzen
chown -R root:root "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"
find "$INSTALL_DIR" -name "*.py" -exec chmod 644 {} \;

# ============================================================================
# Python-Virtuelle Umgebung einrichten
# ============================================================================

log_info "Richte Python virtuelle Umgebung ein..."

# Alte venv entfernen falls vorhanden
[[ -d "$INSTALL_DIR/venv" ]] && rm -rf "$INSTALL_DIR/venv"

# Virtuelle Umgebung erstellen
python3 -m venv "$INSTALL_DIR/venv" || {
    log_error "Konnte virtuelle Umgebung nicht erstellen"
    exit 1
}

# Aktiviere venv und installiere Pakete
source "$INSTALL_DIR/venv/bin/activate"

# Pip upgraden
pip install --upgrade pip setuptools wheel || {
    log_error "Konnte pip nicht upgraden"
    exit 1
}

# Requirements installieren
if [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
    pip install -r "$INSTALL_DIR/requirements.txt" || {
        log_error "Konnte Python-Abhängigkeiten nicht installieren"
        exit 1
    }
else
    # Fallback: Direkte Installation
    log_warning "requirements.txt nicht gefunden, installiere Pakete direkt"
    pip install PyQt6>=6.5.0 cryptography>=41.0.0 || {
        log_error "Konnte Python-Pakete nicht installieren"
        exit 1
    }
fi

deactivate
log_success "Virtuelle Umgebung eingerichtet"

# ============================================================================
# Wrapper-Skript erstellen
# ============================================================================

log_info "Erstelle Wrapper-Skript..."

cat > /usr/local/bin/openvpn-gui << 'EOF'
#!/bin/bash
# OpenVPN GUI Wrapper Script

# Setze Umgebungsvariablen
export QT_QPA_PLATFORM=xcb
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export PYTHONPATH="/usr/local/share/openvpn-gui:$PYTHONPATH"

# Aktiviere virtuelle Umgebung und starte Anwendung
source "/usr/local/share/openvpn-gui/venv/bin/activate"
exec python3 "/usr/local/share/openvpn-gui/main.py" "$@"
EOF

chmod 755 /usr/local/bin/openvpn-gui
log_success "Wrapper-Skript erstellt"

# ============================================================================
# Desktop-Integration
# ============================================================================

log_info "Konfiguriere Desktop-Integration..."

# Resources-Verzeichnis
RESOURCES_DIR="$INSTALL_DIR/resources"
mkdir -p "$RESOURCES_DIR"

# Icon erstellen falls nicht vorhanden
if [[ ! -f "$RESOURCES_DIR/vpn-icon.png" ]]; then
    log_info "Erstelle Standard-Icon..."
    
    # Prüfe ob ImageMagick installiert ist
    if command -v convert >/dev/null 2>&1; then
        convert -size 64x64 xc:transparent \
            -fill '#2196F3' -draw 'circle 32,32 32,8' \
            -fill white -font DejaVu-Sans-Bold -pointsize 20 \
            -gravity center -annotate +0+0 'VPN' \
            "$RESOURCES_DIR/vpn-icon.png" 2>/dev/null || {
            log_warning "Konnte Icon nicht mit ImageMagick erstellen"
        }
    fi
fi

# Desktop-Eintrag erstellen
cat > /usr/share/applications/openvpn-gui.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=OpenVPN GUI
GenericName=VPN Client
Comment=Manage OpenVPN connections
Comment[de]=OpenVPN-Verbindungen verwalten
Exec=/usr/local/bin/openvpn-gui %U
Icon=$RESOURCES_DIR/vpn-icon.png
Terminal=false
Categories=Network;Security;
Keywords=vpn;security;openvpn;network;privacy;
StartupNotify=true
StartupWMClass=openvpn-gui
Actions=Connect;Disconnect;

[Desktop Action Connect]
Name=Connect VPN
Exec=/usr/local/bin/openvpn-gui --connect

[Desktop Action Disconnect]
Name=Disconnect VPN
Exec=/usr/local/bin/openvpn-gui --disconnect
EOF

chmod 644 /usr/share/applications/openvpn-gui.desktop

# Desktop-Datenbank aktualisieren
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications/ 2>/dev/null || true
fi

log_success "Desktop-Integration abgeschlossen"

# ============================================================================
# Benutzer-Konfiguration
# ============================================================================

log_info "Erstelle Benutzer-Konfigurationsverzeichnisse..."

# Konfigurationsverzeichnisse für Target-User
USER_CONFIG_DIR="$TARGET_HOME/.config/openvpn-gui"
USER_VPN_DIR="$TARGET_HOME/.config/openvpn"

sudo -u "$TARGET_USER" mkdir -p "$USER_CONFIG_DIR"
sudo -u "$TARGET_USER" mkdir -p "$USER_VPN_DIR"
sudo -u "$TARGET_USER" chmod 700 "$USER_CONFIG_DIR"
sudo -u "$TARGET_USER" chmod 700 "$USER_VPN_DIR"

log_success "Benutzer-Konfiguration erstellt"

# ============================================================================
# Systemd User-Service (optional)
# ============================================================================

if command -v systemctl &> /dev/null && [[ -d "$TARGET_HOME/.config/systemd/user" || "$1" == "--with-service" ]]; then
    log_info "Erstelle Systemd User-Service..."
    
    # User-Service-Verzeichnis erstellen
    sudo -u "$TARGET_USER" mkdir -p "$TARGET_HOME/.config/systemd/user"
    
    # Service-Datei erstellen
    cat > "$TARGET_HOME/.config/systemd/user/openvpn-gui.service" << EOF
[Unit]
Description=OpenVPN GUI
Documentation=https://github.com/yourusername/openvpn-gui
After=graphical-session.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/openvpn-gui --minimized
Restart=on-failure
RestartSec=5
Environment="DISPLAY=:0"
Environment="XAUTHORITY=%h/.Xauthority"
Environment="XDG_RUNTIME_DIR=/run/user/%U"

# Sicherheitsoptionen
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=%h/.config/openvpn-gui %h/.config/openvpn

[Install]
WantedBy=default.target
EOF

    # Berechtigungen setzen
    chown "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.config/systemd/user/openvpn-gui.service"
    
    log_success "Systemd User-Service erstellt"
    log_info "Service kann aktiviert werden mit: systemctl --user enable openvpn-gui.service"
fi

# ============================================================================
# Post-Installation Tests
# ============================================================================

log_info "Führe Post-Installation Tests durch..."

# Test 1: Wrapper-Script
if [[ -x /usr/local/bin/openvpn-gui ]]; then
    log_success "✓ Wrapper-Script ausführbar"
else
    log_error "✗ Wrapper-Script nicht ausführbar"
fi

# Test 2: Python-Module
if source "$INSTALL_DIR/venv/bin/activate" 2>/dev/null; then
    if python3 -c "import PyQt6; import cryptography" 2>/dev/null; then
        log_success "✓ Python-Module korrekt installiert"
    else
        log_error "✗ Python-Module fehlen"
    fi
    deactivate
else
    log_error "✗ Virtuelle Umgebung nicht aktivierbar"
fi

# Test 3: Sudoers-Regel
if [[ -f /etc/sudoers.d/openvpn-gui-sudo ]]; then
    log_success "✓ Sudoers-Regel installiert"
else
    log_error "✗ Sudoers-Regel fehlt"
fi

# Test 4: OpenVPN
if command -v openvpn >/dev/null 2>&1; then
    OPENVPN_VERSION=$(openvpn --version 2>&1 | head -n1)
    log_success "✓ OpenVPN installiert: $OPENVPN_VERSION"
else
    log_error "✗ OpenVPN nicht gefunden"
fi

# ============================================================================
# Beispiel-Konfiguration erstellen
# ============================================================================

if [[ ! -f /etc/openvpn/client/example.ovpn.disabled ]]; then
    log_info "Erstelle Beispiel-Konfiguration..."
    
    cat > /etc/openvpn/client/example.ovpn.disabled << 'EOF'
# Beispiel OpenVPN Konfiguration
# Umbenennen Sie diese Datei zu .ovpn und passen Sie sie an

client
dev tun
proto udp
remote vpn.example.com 1194
resolv-retry infinite
nobind
persist-key
persist-tun

# Sicherheit
cipher AES-256-GCM
auth SHA256
key-direction 1
remote-cert-tls server

# DNS-Updates
script-security 2
up /etc/openvpn/update-resolv-conf
down /etc/openvpn/update-resolv-conf

# Logging
verb 3

# Zertifikate hier einfügen
<ca>
-----BEGIN CERTIFICATE-----
# CA-Zertifikat hier einfügen
-----END CERTIFICATE-----
</ca>

<cert>
-----BEGIN CERTIFICATE-----
# Client-Zertifikat hier einfügen
-----END CERTIFICATE-----
</cert>

<key>
-----BEGIN PRIVATE KEY-----
# Private Key hier einfügen
-----END PRIVATE KEY-----
</key>

<tls-auth>
-----BEGIN OpenVPN Static key V1-----
# TLS-Auth Key hier einfügen
-----END OpenVPN Static key V1-----
</tls-auth>
EOF
    
    chmod 644 /etc/openvpn/client/example.ovpn.disabled
    log_success "Beispiel-Konfiguration erstellt"
fi

# ============================================================================
# Zusammenfassung und Hinweise
# ============================================================================

echo
echo "============================================================================"
log_success "Installation erfolgreich abgeschlossen!"
echo "============================================================================"
echo

# Installierte Komponenten
log_info "Installierte Komponenten:"
echo "  • Anwendung:     $INSTALL_DIR"
echo "  • Executable:    /usr/local/bin/openvpn-gui"
echo "  • Desktop-Entry: /usr/share/applications/openvpn-gui.desktop"
echo "  • Sudoers-Regel: /etc/sudoers.d/openvpn-gui-sudo"
echo "  • Log-Datei:     $LOG_FILE"
echo

# Wichtige Hinweise
log_warning "WICHTIGE HINWEISE:"
echo
echo "1. NEUANMELDUNG ERFORDERLICH:"
echo "   Der Benutzer '$TARGET_USER' muss sich neu anmelden, damit die"
echo "   Gruppenmitgliedschaft in 'openvpn' wirksam wird!"
echo
echo "2. VPN-KONFIGURATION:"
echo "   • Kopieren Sie Ihre .ovpn Dateien nach: /etc/openvpn/client/"
echo "   • Oder nach: $TARGET_HOME/.config/openvpn/"
echo "   • Stellen Sie sicher, dass die Dateien diese Zeilen enthalten:"
echo "     script-security 2"
echo "     up /etc/openvpn/update-resolv-conf"
echo "     down /etc/openvpn/update-resolv-conf"
echo
echo "3. ANWENDUNG STARTEN:"
echo "   • Über das Anwendungsmenü: 'OpenVPN GUI'"
echo "   • Oder im Terminal: openvpn-gui"
echo "   • Mit Autostart: systemctl --user enable openvpn-gui.service"
echo
echo "4. FEHLERBEHEBUNG:"
echo "   • Logs prüfen: journalctl -xe"
echo "   • App-Logs: ~/.config/openvpn-gui/app.log"
echo "   • Installations-Log: $LOG_FILE"
echo

# Optionale Aktionen
if [[ "${1:-}" != "--no-prompt" ]]; then
    echo "Möchten Sie die Anwendung jetzt testen? (y/N)"
    read -r -n 1 response
    echo
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Starte OpenVPN GUI als $TARGET_USER..."
        sudo -u "$TARGET_USER" DISPLAY=:0 /usr/local/bin/openvpn-gui &
        log_info "OpenVPN GUI wurde gestartet. Prüfen Sie Ihren Desktop."
    fi
fi

log_success "Installation abgeschlossen. Viel Erfolg mit OpenVPN GUI!"

# ============================================================================
# Aufräumen
# ============================================================================

# Temporäre Dateien entfernen
[[ -f "$LOG_FILE.tmp" ]] && rm -f "$LOG_FILE.tmp"

exit 0
