# OpenVPN-Py

A simple Python-based GUI for OpenVPN, built with PyQt6. This application provides an easy way to manage and connect to OpenVPN configurations.

## Features

- **Import Configurations**: Easily import your `.ovpn` files.
- **Secure Credential Storage**: Uses the system's keyring (`secret-service` on Linux) to securely store your VPN passwords.
- **Connect/Disconnect**: Start and stop VPN connections with a single click.
- **System Tray Icon**: A tray icon indicates the current connection status (Disconnected, Connecting, Connected, Error).
- **Log Viewer**: View real-time logs from OpenVPN for troubleshooting.
- **Leak Protection**: Supports standard OpenVPN directives for DNS and IPv6 leak protection (`update-resolv-conf` and `block-outside-dns`).
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

---

## Usage

1. Launch the application from your system's application menu ("OpenVPN-Py").
2. **Import a Config**: Click "Import" and select your `.ovpn` configuration file.
3. **Select a Config**: Choose the desired configuration from the list.
4. **Connect**: Click the "Connect" button. You may be prompted for your sudo password and VPN password the first time. You can choose to save the VPN password securely in your system's keyring.
5. **Disconnect**: Click the "Disconnect" button to terminate the connection.

---

## Configuration for Leak Protection

To ensure DNS and IPv6 leaks are prevented, make sure your `.ovpn` files contain the following lines. This script relies on OpenVPN's native capabilities to manage routes and DNS.

```
# Example lines to add to your .ovpn file
# For DNS leak protection
up /etc/openvpn/update-resolv-conf
down /etc/openvpn/update-resolv-conf

# For blocking DNS servers on non-VPN interfaces
block-outside-dns

# To prevent IPv6 leaks if the VPN is IPv4-only
pull-filter ignore "route-ipv6"
pull-filter ignore "ifconfig-ipv6"
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
```