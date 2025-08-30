# OpenVPN-Py

A simple Python-based GUI for OpenVPN, built with PyQt6. This application provides an easy way to manage and connect to OpenVPN configurations.

## Features

- **Import Configurations**: Easily import your `.ovpn` files.
- **Secure Credential Storage**: Uses the system's keyring (`secret-service` on Linux) to securely store your VPN passwords.
- **Connect/Disconnect**: Start and stop VPN connections with a single click.
- **System Tray Icon**: A tray icon indicates the current connection status (Disconnected, Connecting, Connected, Error).
- **Log Viewer**: View real-time logs from OpenVPN for troubleshooting.
- **Quick Logs Access**: Open the logs folder directly from the View menu or the tray icon.
- **Remembers Last Selection**: The app restores your last selected VPN configuration on startup.
- **Leak Protection**: Uses systemd-resolved integration when available (plugin preferred). Falls back to scripts if allowed. IPv6/DNS leak protection is applied accordingly.
- **Internationalization**: Available in English and German.

---

## Requirements

### 1. System Dependencies

- **OpenVPN**: The OpenVPN client must be installed.

  ```bash
  # On Debian/Ubuntu
  sudo apt-get update
  sudo apt-get install openvpn
  ```

- **Python**: Python 3.8+ and `pip`.
- **PyQt6**: The GUI is built with PyQt6. The installation script will attempt to install it.
- **Keyring**: For secure password storage. The installation script will attempt to install it.
- **systemd**: Required. The helper uses `systemd-run` to launch OpenVPN as a transient service. Systems without systemd are not supported.
- **qt6-tools** (Optional but Recommended): For compiling translation files.

  ```bash
  # On Debian/Ubuntu
  sudo apt-get install qt6-tools-dev
  ```

### 2. User Group

For the application to manage OpenVPN connections, the user running the GUI must be a member of the `openvpn` group.

```bash
# Add your user to the 'openvpn' group
sudo usermod -aG openvpn $USER
```

**Important**: You need to log out and log back in for this change to take effect.

---

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-username/OpenVPN-Py.git
   cd OpenVPN-Py
   ```

2. **Run the install script:**

   The script will copy files to system directories and set up necessary permissions. It must be run with `sudo`.

   ```bash
   sudo ./scripts/install.sh
   ```

   The script will:

   - Install Python dependencies (`PyQt6`, `keyring`) via `pip`.
   - Copy application files to `/usr/local/share/openvpn-py`.
   - Create a launcher at `/usr/local/bin/openvpn-py`.
   - Create a `.desktop` file for your application menu.
   - Create a `sudoers` rule to allow the app to run OpenVPN without a password prompt.
   - Attempt to install and enable systemd-resolved integration for DNS leak protection (`openvpn-systemd-resolved`).
   - If `systemd-resolved` is active, point `/etc/resolv.conf` to the stub resolver (backing up the original to `/etc/resolv.conf.backup-openvpn-py-<timestamp>`).

---

## Usage

1. Launch the application from your system's application menu ("OpenVPN-Py").
2. **Import a Config**: Click "Import" and select your `.ovpn` configuration file.
3. **Select a Config**: Choose the desired configuration from the list.
4. **Connect**: Click the "Connect" button. You may be prompted for your sudo password and VPN password the first time. You can choose to save the VPN password securely in your system's keyring.
5. **Disconnect**: Click the "Disconnect" button to terminate the connection.
6. **Logs**:
   - View live logs in the main window or open the dedicated Logs Window via View → "Open Logs Window".
   - Open the logs folder in your file manager via View → "Open Logs Folder" or from the tray icon.
   - The helper exposes logs in your Documents folder under `~/Documents/OpenVPN-Py/` (or localized `~/Dokumente/OpenVPN-Py/`). It creates:
     - `openvpn-<config>.log` → symlink to the current session log for that config
     - `openvpn-current.log` → symlink to the most recent session log (any config)
     - On disconnect, an archived copy: `openvpn-<config>-YYYYMMDD-HHMMSS.log`

---

## DNS and Leak Protection Details

- The helper (`scripts/openvpn-gui-helper.sh`) prefers the `openvpn-plugin-systemd-resolved.so` plugin. With OpenVPN ≥ 2.5 it adds `--dhcp-option DOMAIN-ROUTE .` automatically to route all DNS via VPN.
- If the plugin is unavailable, it falls back to `update-systemd-resolved` (and then to `update-resolv-conf`) when AppArmor allows external scripts.
- If neither plugin nor scripts are usable, scripts are disabled and DNS may leak. Install `openvpn-systemd-resolved` or allow one of the scripts to avoid leaks.
- AppArmor detection defaults to NOT enforcing if `aa-status` is missing. You can force conservative behavior by setting `OPENVPN_PY_ASSUME_AA_ENFORCE=1` in the environment before launching.

Tips for configs:
- You usually do not need to add DNS hooks manually. The helper sanitizes legacy `up`/`down` lines to avoid conflicts and applies the appropriate integration.
- For IPv6-only concerns, consider adding the usual `pull-filter ignore "route-ipv6"`/`"ifconfig-ipv6"` directives if your VPN is IPv4-only.

---

## Troubleshooting

- **No passwordless sudo for the helper**:
  - Ensure you are in the `openvpn` group and re-login:
    ```bash
    id -nG
    sudo usermod -aG openvpn "$USER" # then log out/in or run: newgrp openvpn
    ```
  - Verify the sudoers rule exists and is valid:
    ```bash
    sudo ls -l /etc/sudoers.d/openvpn-py-sudoers
    sudo visudo -cf /etc/sudoers.d/openvpn-py-sudoers
    ```
  - Quick check that sudoers allows the helper without prompting (should print a status word like "disconnected"):
    ```bash
    sudo -n /usr/local/bin/openvpn-gui-helper.sh status dummy.ovpn || echo "helper not allowed by sudoers"
    ```

- **Logs not appearing in Documents**:
  - The helper writes runtime logs to `/run/openvpn/` and creates symlinks in `~/Documents/OpenVPN-Py/` (or `~/Dokumente/OpenVPN-Py/`). Expected files:
    - `openvpn-<config>.log` (symlink to the live log for that config)
    - `openvpn-current.log` (symlink to the most recent session)
    - Archived files like `openvpn-<config>-YYYYMMDD-HHMMSS.log` after disconnect
  - Ensure the directory exists and is writable by your user:
    ```bash
    ls -l ~/Documents/OpenVPN-Py || ls -l ~/Dokumente/OpenVPN-Py
    ```

- **DNS leaks or name resolution issues**:
  - Install and enable `systemd-resolved` integration (preferred) or ensure one of the DNS helper scripts is available.
  - The helper prefers the `openvpn-plugin-systemd-resolved.so` plugin. If missing and AppArmor allows scripts, it falls back to `update-systemd-resolved` (then `update-resolv-conf`).
  - If AppArmor detection is uncertain and you want to force conservative behavior (avoid external scripts), launch the app with:
    ```bash
    OPENVPN_PY_ASSUME_AA_ENFORCE=1 openvpn-py
    ```

---

## Uninstallation

To remove the application and all its components from your system, run the `uninstall.sh` script with `sudo`.

```bash
cd OpenVPN-Py # Navigate back to the cloned directory
sudo ./scripts/uninstall.sh
```

**Note**: The uninstaller will not remove your personal configuration files, which are stored in `~/.config/openvpn-py`. You can remove them manually if desired.

```bash
rm -rf ~/.config/openvpn-py