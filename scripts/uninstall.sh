#!/bin/bash
set -euo pipefail

# Define installation paths to remove
INSTALL_DIR="/usr/local/share/openvpn-py"
BIN_DIR="/usr/local/bin"
APP_NAME="openvpn-py"
HELPER_SCRIPT_NAME="openvpn-gui-helper.sh"
DESKTOP_ENTRY_NAME="openvpn-py.desktop"
SUDOERS_FILE_NAME="openvpn-py-sudoers"

# Check for root privileges
if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root. Please use 'sudo'."
  exit 1
fi

echo "Starting OpenVPN-Py uninstallation..."

# --- Stop any running VPN connection managed by the application ---
echo "Attempting to stop any active OpenVPN connections..."
# Find all transient services created by the GUI and stop them (including suffixed forms)
declare -a OVPN_GUI_UNITS=()
mapfile -t OVPN_GUI_UNITS < <(systemctl list-units --all --type=service --no-legend --no-pager | awk '{print $1}' | grep -E '^openvpn-py-gui@[^ ]+\.service(|$)|^openvpn-py-gui@[^ ]+-[0-9]+-[0-9]+\.service$' || true)
if [ ${#OVPN_GUI_UNITS[@]} -gt 0 ]; then
  for u in "${OVPN_GUI_UNITS[@]}"; do
    systemctl stop "$u" || true
    systemctl reset-failed "$u" || true
    if [ -f "/run/systemd/transient/$u" ]; then
      rm -f "/run/systemd/transient/$u" || true
    fi
  done
  systemctl daemon-reload || true
else
  echo "No running GUI-managed OpenVPN services found."
fi

# Also kill any remaining openvpn processes that include our unit hint (very best-effort)
pgrep -a openvpn | grep -E 'openvpn-py-gui@' | awk '{print $1}' | xargs -r kill || true

# --- Remove sudoers file ---
SUDOERS_FILE="/etc/sudoers.d/$SUDOERS_FILE_NAME"
if [ -f "$SUDOERS_FILE" ]; then
    echo "Removing sudoers file: $SUDOERS_FILE"
    rm -f "$SUDOERS_FILE"
else
    echo "Sudoers file not found, skipping."
fi

# --- Remove .desktop file ---
DESKTOP_FILE="/usr/share/applications/$DESKTOP_ENTRY_NAME"
if [ -f "$DESKTOP_FILE" ]; then
    echo "Removing .desktop entry: $DESKTOP_FILE"
    rm -f "$DESKTOP_FILE"
else
    echo ".desktop entry not found, skipping."
fi

# --- Remove binaries and symlinks ---
LAUNCHER_FILE="$BIN_DIR/$APP_NAME"
if [ -f "$LAUNCHER_FILE" ]; then
    echo "Removing launcher: $LAUNCHER_FILE"
    rm -f "$LAUNCHER_FILE"
else
    echo "Launcher not found, skipping."
fi

HELPER_SYMLINK="$BIN_DIR/$HELPER_SCRIPT_NAME"
if [ -L "$HELPER_SYMLINK" ]; then
    echo "Removing helper script symlink: $HELPER_SYMLINK"
    rm -f "$HELPER_SYMLINK"
else
    echo "Helper script symlink not found, skipping."
fi

# --- Remove sanitized configs and credentials directory created by helper ---
ETC_DIR="/etc/openvpn/openvpn-py"
if [ -d "$ETC_DIR" ]; then
    echo "Removing helper etc directory: $ETC_DIR"
    rm -rf "$ETC_DIR"
fi

# --- Remove installation directory ---
if [ -d "$INSTALL_DIR" ]; then
    echo "Removing installation directory: $INSTALL_DIR"
    rm -rf "$INSTALL_DIR"
else
    echo "Installation directory not found, skipping."
fi

# --- Remove transient auth directory (if any) ---
if [ -d "/run/openvpn-py" ]; then
    echo "Removing transient auth directory: /run/openvpn-py"
    rm -rf "/run/openvpn-py"
fi

# --- Remove logs created in /run/openvpn by helper ---
# Only remove our helper's transient logs: openvpn-py-gui@*.service.log
find /run/openvpn -maxdepth 1 -type f -name 'openvpn-py-gui@*.service.log' -exec rm -f {} + 2>/dev/null || true

# --- Remove user-visible log symlinks and dirs in Documents/Dokumente ---
cleanup_user_logs() {
  local user_home="$1"
  for d in "Documents" "Dokumente"; do
    local base_dir="$user_home/$d/OpenVPN-Py"
    if [ -d "$base_dir" ]; then
      echo "Cleaning log symlinks in: $base_dir"
      rm -f "$base_dir"/openvpn-current.log 2>/dev/null || true
      rm -f "$base_dir"/openvpn-last.log 2>/dev/null || true
      # Remove only symlinks for per-config logs, keep archived real files intact
      find "$base_dir" -maxdepth 1 -type l -name 'openvpn-*.log' -exec rm -f {} + 2>/dev/null || true
      # Attempt to remove dir if empty
      rmdir "$base_dir" 2>/dev/null || true
    fi
  done
}

# Prefer removing for all users under /home
for H in /home/*; do
  [ -d "$H" ] || continue
  cleanup_user_logs "$H"
done

# Also remove for the installing user (covers non-standard homes)
if [ -n "${SUDO_USER:-}" ]; then
  user_home=$(getent passwd "$SUDO_USER" | cut -d: -f6)
  [ -n "$user_home" ] && [ -d "$user_home" ] && cleanup_user_logs "$user_home"
fi

# --- Reload systemd one last time ---
systemctl daemon-reload || true

echo ""
echo "Uninstallation complete."
echo "NOTE: User-specific configuration files in ~/.config/openvpn-py have not been removed."

exit 0
