#!/bin/bash
set -euo pipefail

# ============================================================================
# OpenVPN GUI Installation Script (Python Version)
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

APP_NAME="openvpn-gui"
INSTALL_DIR="/usr/local/share/$APP_NAME"
HELPER_SCRIPT_PATH="/usr/local/bin/$APP_NAME-helper"
WRAPPER_SCRIPT_PATH="/usr/local/bin/$APP_NAME"
SUDOERS_FILE="/etc/sudoers.d/$APP_NAME-sudo"
DESKTOP_FILE="/usr/share/applications/$APP_NAME.desktop"
LOG_FILE="/tmp/$APP_NAME-install-$(date +%Y%m%d-%H%M%S).log"

cleanup_on_error() {
    local exit_code=$?
    log_error "Installation failed (Exit Code: $exit_code). See log file: $LOG_FILE"
    
    log_info "Cleaning up partial installation..."
    [[ -f "$WRAPPER_SCRIPT_PATH" ]] && rm -f "$WRAPPER_SCRIPT_PATH"
    [[ -f "$HELPER_SCRIPT_PATH" ]] && rm -f "$HELPER_SCRIPT_PATH"
    [[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR"
    [[ -f "$DESKTOP_FILE" ]] && rm -f "$DESKTOP_FILE"
    [[ -f "$SUDOERS_FILE" ]] && rm -f "$SUDOERS_FILE"
    
    exit $exit_code
}
trap cleanup_on_error ERR
exec &> >(tee -a "$LOG_FILE")

# ============================================================================
# Haupt-Skript
# ============================================================================
log_info "Checking prerequisites..."
if [[ $EUID -ne 0 ]]; then log_error "This script must be run with sudo."; exit 1; fi
if [[ ! -f "$PROJECT_DIR/main.py" ]]; then log_error "main.py not found. Please run from the project root."; exit 1; fi

TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
if [[ -z "$TARGET_USER" || "$TARGET_USER" == "root" ]]; then log_error "Could not determine target user."; exit 1; fi
log_info "Installing for user: $TARGET_USER"

log_info "Installing system dependencies..."
apt-get update -qq
# Nur absolute Basics per apt, Python Pakete werden via pip in der venv verwaltet
PACKAGES=(python3 python3-pip python3-venv openvpn policykit-1 libxcb-cursor0 pyqt6-dev-tools)
apt-get install -y "${PACKAGES[@]}"

log_info "Configuring OpenVPN group..."
if ! getent group openvpn > /dev/null 2>&1; then groupadd --system openvpn; fi
usermod -aG openvpn "$TARGET_USER"

log_info "Creating secure helper script at $HELPER_SCRIPT_PATH..."
if [[ ! -f "$PROJECT_DIR/scripts/openvpn-gui-helper.sh" ]]; then log_error "Helper script not found!"; exit 1; fi
cp "$PROJECT_DIR/scripts/openvpn-gui-helper.sh" "$HELPER_SCRIPT_PATH"
chmod 755 "$HELPER_SCRIPT_PATH"
chown root:root "$HELPER_SCRIPT_PATH"

log_info "Configuring sudoers for secure access..."
SUDOERS_CONTENT=$(cat <<EOF
# Allow $TARGET_USER to run OpenVPN GUI helper operations without a password
$TARGET_USER ALL=(root) NOPASSWD: $HELPER_SCRIPT_PATH start *
$TARGET_USER ALL=(root) NOPASSWD: $HELPER_SCRIPT_PATH stop *
EOF
)
echo "$SUDOERS_CONTENT" > "$SUDOERS_FILE"
chmod 0440 "$SUDOERS_FILE"
# Validate with visudo
visudo -cf "$SUDOERS_FILE"
log_success "Secure sudoers rule written to $SUDOERS_FILE."

log_info "Copying project files to $INSTALL_DIR..."
[[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
# Kopiere alles außer dem 'scripts' Verzeichnis
rsync -a --exclude 'scripts/' "$PROJECT_DIR/" "$INSTALL_DIR/"
chown -R root:root "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

log_info "Setting up Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$INSTALL_DIR/requirements.txt"
deactivate

log_info "Compiling translation files..."
if [ -d "$INSTALL_DIR/i18n" ]; then
    lrelease "$INSTALL_DIR/i18n"/*.ts
    log_success "Translations compiled."
fi

log_info "Creating wrapper script at $WRAPPER_SCRIPT_PATH..."
cat > "$WRAPPER_SCRIPT_PATH" << EOF
#!/bin/bash
export QT_QPA_PLATFORM=xcb
export PYTHONPATH="$INSTALL_DIR:\$PYTHONPATH"
source "$INSTALL_DIR/venv/bin/activate"
exec python3 "$INSTALL_DIR/main.py" "\$@"
EOF
chmod 755 "$WRAPPER_SCRIPT_PATH"

log_info "Configuring desktop integration..."
RESOURCES_DIR="$INSTALL_DIR/resources"
if [[ ! -f "$RESOURCES_DIR/vpn-icon.png" ]]; then log_warning "Icon file not found, app may have generic icon."; fi
cat > "$DESKTOP_FILE" << EOF
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
chmod 644 "$DESKTOP_FILE"
update-desktop-database /usr/share/applications/ 2>/dev/null || true

log_info "Creating user configuration directories..."
USER_CONFIG_DIR="$TARGET_HOME/.config/$APP_NAME"
sudo -u "$TARGET_USER" mkdir -p "$USER_CONFIG_DIR"
sudo -u "$TARGET_USER" chmod 700 "$USER_CONFIG_DIR"

echo
log_success "==========================================="
log_success "Installation successfully completed!"
log_success "==========================================="
echo
log_warning "IMPORTANT: User '$TARGET_USER' must log out and back in for group changes to take effect!"
log_info "Start the application from your desktop menu or by running: $APP_NAME"