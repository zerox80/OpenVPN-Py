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
VENV_DIR="$INSTALL_DIR/.venv"

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
# Ensure the 'venv' module is available (python3-venv on Debian/Ubuntu)
if ! python3 - <<'PY'
import venv
PY
then
    echo "Error: Python 'venv' module is not available. Please install it (e.g., 'sudo apt install python3-venv') and try again."
    exit 1
fi

# Check for openvpn availability (warn if missing)
if ! command -v openvpn &> /dev/null; then
    echo "Warning: 'openvpn' binary not found in PATH. Please install OpenVPN (e.g., 'sudo apt install openvpn')."
fi

# Check for systemd-run availability (required by helper)
if ! command -v systemd-run &> /dev/null; then
    echo "Error: 'systemd-run' not found. This application requires systemd."
    exit 1
fi

echo "Starting OpenVPN-Py installation..."

# Use parent directory of the script's location
SCRIPT_PARENT_DIR=$(dirname "$(dirname "$(realpath "$0")")")

# --- Create directories ---
echo "Creating installation directories in $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/ui"
mkdir -p "$INSTALL_DIR/scripts"
mkdir -p "$INSTALL_DIR/i18n"
mkdir -p "$INSTALL_DIR/icons"

# Ensure sanitized config directory exists for helper (stable path)
SANITIZED_DIR="/etc/openvpn/openvpn-py/sanitized"
mkdir -p "$SANITIZED_DIR"
chmod 0750 "$SANITIZED_DIR" || true

# --- Create Python virtual environment ---
echo "Creating Python virtual environment in $VENV_DIR..."
python3 -m venv "$VENV_DIR"

# --- Install Python dependencies into venv ---
echo "Installing Python dependencies into the virtual environment..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$SCRIPT_PARENT_DIR/requirements.txt"

# --- Copy application files ---
echo "Copying application files..."
cp "$SCRIPT_PARENT_DIR"/*.py "$INSTALL_DIR/"
cp "$SCRIPT_PARENT_DIR"/ui/*.py "$INSTALL_DIR/ui/"
cp "$SCRIPT_PARENT_DIR"/scripts/$HELPER_SCRIPT_NAME "$INSTALL_DIR/scripts/"
cp "$SCRIPT_PARENT_DIR"/i18n/*.ts "$INSTALL_DIR/i18n/"
cp "$SCRIPT_PARENT_DIR"/icons/$ICON_NAME "$INSTALL_DIR/icons/"

# Ensure helper script is executable
chmod +x "$INSTALL_DIR/scripts/$HELPER_SCRIPT_NAME"

# --- Optional: set up systemd-resolved integration for DNS (prevents DNS leaks) ---
echo "Checking for systemd-resolved OpenVPN integration..."
# Detect presence of update-systemd-resolved script or plugin
HAVE_RESOLVED_SCRIPT=0
for s in \
  "/etc/openvpn/update-systemd-resolved" \
  "/etc/openvpn/scripts/update-systemd-resolved" \
  "/usr/libexec/openvpn/update-systemd-resolved" \
  "/usr/lib/openvpn/plugins/update-systemd-resolved"; do
  if [ -x "$s" ]; then HAVE_RESOLVED_SCRIPT=1; break; fi
done

if [ $HAVE_RESOLVED_SCRIPT -eq 0 ]; then
  echo "systemd-resolved helper not found. Attempting to install 'openvpn-systemd-resolved'..."
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y openvpn-systemd-resolved || true
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y openvpn-systemd-resolved || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y openvpn-systemd-resolved || true
  elif command -v zypper >/dev/null 2>&1; then
    zypper --non-interactive install openvpn-systemd-resolved || true
  elif command -v pacman >/dev/null 2>&1; then
    pacman --noconfirm -S openvpn-systemd-resolved || true
  else
    echo "Note: Unknown package manager. Please install 'openvpn-systemd-resolved' manually to enable DNS integration."
  fi
fi

# Enable systemd-resolved service if present
if systemctl list-unit-files | grep -q '^systemd-resolved.service'; then
  echo "Enabling and starting systemd-resolved..."
  systemctl enable --now systemd-resolved || true
else
  echo "Note: systemd-resolved service not found. DNS integration may not activate."
fi

# --- Compile translations ---
echo "Compiling translation files..."
# Check if lrelease is available
if ! command -v lrelease &> /dev/null; then
    echo "Warning: 'lrelease' command not found. Cannot compile translations."
    echo "Please install 'qt6-tools' or equivalent for your distribution."
else
    for ts in "$INSTALL_DIR"/i18n/*.ts; do
        [ -f "$ts" ] || continue
        qm="${ts%.ts}.qm"
        lrelease "$ts" -qm "$qm" || true
    done
fi

# --- Create executable launcher ---
echo "Creating launcher script in $BIN_DIR/$APP_NAME..."
cat << EOF > "$BIN_DIR/$APP_NAME"
#!/bin/bash
# Launcher for OpenVPN-Py
cd "$INSTALL_DIR"
"$VENV_DIR/bin/python" main.py "\$@"
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
{
  echo "# Allows users in the 'openvpn' group to run the helper script without a password"
  echo "%openvpn ALL=(ALL) NOPASSWD: $BIN_DIR/$HELPER_SCRIPT_NAME *"
  if [ -n "${SUDO_USER:-}" ]; then
    echo "# Also allow the installing user to run it immediately (no relogin needed)"
    echo "$SUDO_USER ALL=(ALL) NOPASSWD: $BIN_DIR/$HELPER_SCRIPT_NAME *"
  fi
} > "$SUDOERS_FILE"
# Set correct permissions for the sudoers file
chmod 0440 "$SUDOERS_FILE"

# Validate sudoers file syntax
if ! visudo -cf "$SUDOERS_FILE" > /dev/null; then
  echo "Error: sudoers file validation failed. Reverting changes."
  rm -f "$SUDOERS_FILE"
  exit 1
fi

# Ensure 'openvpn' group exists and add invoking user to it
if ! getent group openvpn > /dev/null; then
  echo "Creating system group 'openvpn'..."
  groupadd --system openvpn
fi

if [ -n "${SUDO_USER:-}" ]; then
  echo "Adding user '$SUDO_USER' to group 'openvpn'..."
  usermod -aG openvpn "$SUDO_USER"
  ADDED_USER=1
else
  ADDED_USER=0
fi

echo ""
echo "--------------------------------------------------------"
echo "Installation complete!"
echo ""
echo "IMPORTANT: The helper is allowed via sudoers."
echo "- Users in group 'openvpn' can run the helper passwordless."
if [ "${ADDED_USER:-0}" -eq 1 ]; then
  echo "- User '$SUDO_USER' was added to 'openvpn' group."
  echo "- Additionally, a per-user sudoers entry was created for '$SUDO_USER' so you can use the app immediately without relogin."
else
  echo "- No installing user detected; only the group rule was added."
fi
echo ""
echo "Note: Group membership changes require re-login to take effect in new sessions."
echo "The per-user rule keeps the current user working right away."
echo "--------------------------------------------------------"

exit 0
