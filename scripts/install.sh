#!/bin/bash
set -euo pipefail

# Define installation paths
INSTALL_DIR="/usr/local/share/openvpn-py"
BIN_DIR="/usr/local/bin"
APP_NAME="openvpn-py"
HELPER_SCRIPT_NAME="openvpn-gui-helper.sh"
DESKTOP_ENTRY_NAME="openvpn-py.desktop"
SUDOERS_FILE_NAME="openvpn-py-sudoers"
ICON_NAME="openvpn-py.png"

# Check for root privileges
if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root. Please use 'sudo'."
  exit 1
fi

# --- Check for dependencies ---
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 could not be found. Please install it to continue."
    exit 1
fi
if ! command -v pip &> /dev/null; then
    echo "Error: pip for python3 could not be found. Please install it to continue."
    exit 1
fi


echo "Starting OpenVPN-Py installation..."

# Use parent directory of the script's location
SCRIPT_PARENT_DIR=$(dirname "$(dirname "$(realpath "$0")")")

# --- Install Python dependencies ---
echo "Installing Python dependencies from requirements.txt..."
pip install -r "$SCRIPT_PARENT_DIR/requirements.txt"

# --- Create directories ---
echo "Creating installation directories in $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/ui"
mkdir -p "$INSTALL_DIR/scripts"
mkdir -p "$INSTALL_DIR/i18n"
mkdir -p "$INSTALL_DIR/icons"

# --- Copy application files ---
echo "Copying application files..."
cp "$SCRIPT_PARENT_DIR"/*.py "$INSTALL_DIR/"
cp "$SCRIPT_PARENT_DIR"/ui/*.py "$INSTALL_DIR/ui/"
cp "$SCRIPT_PARENT_DIR"/scripts/$HELPER_SCRIPT_NAME "$INSTALL_DIR/scripts/"
cp "$SCRIPT_PARENT_DIR"/i18n/*.ts "$INSTALL_DIR/i18n/"
cp "$SCRIPT_PARENT_DIR"/icons/$ICON_NAME "$INSTALL_DIR/icons/"

# --- Compile translations ---
echo "Compiling translation files..."
# Check if lrelease is available
if ! command -v lrelease &> /dev/null; then
    echo "Warning: 'lrelease' command not found. Cannot compile translations."
    echo "Please install 'qt6-tools' or equivalent for your distribution."
else
    lrelease "$INSTALL_DIR/i18n/de.ts" -qm "$INSTALL_DIR/i18n/de.qm"
fi


# --- Create executable launcher ---
echo "Creating launcher script in $BIN_DIR/$APP_NAME..."
cat << EOF > "$BIN_DIR/$APP_NAME"
#!/bin/bash
# Launcher for OpenVPN-Py
cd "$INSTALL_DIR"
python3 main.py "\$@"
EOF
chmod +x "$BIN_DIR/$APP_NAME"

# --- Create helper script symlink ---
echo "Creating symlink for helper script in $BIN_DIR/$HELPER_SCRIPT_NAME..."
ln -sf "$INSTALL_DIR/scripts/$HELPER_SCRIPT_NAME" "$BIN_DIR/$HELPER_SCRIPT_NAME"

# --- Create .desktop file for application menu ---
echo "Creating .desktop entry..."
cat << EOF > "/usr/share/applications/$DESKTOP_ENTRY_NAME"
[Desktop Entry]
Version=1.0
Name=OpenVPN-Py
Comment=A Python GUI for OpenVPN
Exec=$BIN_DIR/$APP_NAME
Icon=$INSTALL_DIR/icons/$ICON_NAME
Terminal=false
Type=Application
Categories=Network;
EOF

# --- Set up sudoers rule for the helper script ---
echo "Setting up sudoers rule..."
SUDOERS_FILE="/etc/sudoers.d/$SUDOERS_FILE_NAME"
echo "# Allows users in the 'openvpn' group to run the helper script without a password" > "$SUDOERS_FILE"
echo "%openvpn ALL=(ALL) NOPASSWD: $BIN_DIR/$HELPER_SCRIPT_NAME *" >> "$SUDOERS_FILE"
# Set correct permissions for the sudoers file
chmod 0440 "$SUDOERS_FILE"

echo ""
echo "--------------------------------------------------------"
echo "Installation complete!"
echo ""
echo "IMPORTANT: For this application to work, the current user"
echo "must be a member of the 'openvpn' group."
echo "You can add the user with the command:"
echo "  sudo usermod -aG openvpn \$USER"
echo ""
echo "You may need to log out and log back in for the group"
echo "changes to take effect."
echo "--------------------------------------------------------"

exit 0
