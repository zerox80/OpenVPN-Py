# OpenVPN GUI

## English

### Overview

OpenVPN GUI is a Linux desktop client for managing OpenVPN connections. It provides a simple and intuitive graphical interface for importing, connecting, and disconnecting VPN configurations, with system tray integration, encrypted credential storage, and leak protection.

### Features

- Import and manage multiple OpenVPN configuration files (`.ovpn`, `.conf`)
- Securely store VPN credentials encrypted on disk
- Connect and disconnect VPN sessions with a click
- System tray icon with real-time status and notifications
- Built-in log viewer to track connection events
- DNS leak protection via `update-resolv-conf`
- IPv6 leak prevention using `ip6tables`
- Optional systemd user service for automatic startup
- Cross-desktop integration with a `.desktop` entry

### Requirements

- Linux distribution (Ubuntu tested)
- Python 3.8 or higher
- OpenVPN and `sudo` installed and in `PATH`
- DNS update script at `/etc/openvpn/update-resolv-conf` (provided by `openvpn-systemd-resolved`)
- User in the `openvpn` group to manage VPN without password prompts
- Python packages: `PyQt6`, `cryptography` (install via `pip install -r requirements.txt`)

### Installation

1. Navigate to the project root directory:
   ```bash
   cd OpenVPN-Py
   ```
2. Run the installation script with superuser privileges:
   ```bash
   sudo ./scripts/install.sh
   ```
3. (Optional) Enable the systemd user service:
   ```bash
   sudo ./scripts/install.sh --with-service
   ```
4. Log out and log back in to apply group membership changes (user must be in the `openvpn` group).

### Usage

- Launch the application via your desktop menu (OpenVPN GUI) or command line:
  ```bash
  openvpn-gui
  ```
- In the main window:
  1. Import `.ovpn`/`.conf` files using the "Import Configuration" button
  2. Select a configuration from the list
  3. Click "Connect" to start the VPN session
  4. Enter credentials when prompted and choose whether to save them
  5. View real-time logs in the log viewer
- Use the system tray icon for quick connect/disconnect and status notifications.

### Configuration

- System-wide configurations: place `.ovpn`/`.conf` files in `/etc/openvpn/client/`
- User configurations: place files in `~/.config/openvpn/`
- Ensure each configuration file contains:
  ```text
  script-security 2
  up /etc/openvpn/update-resolv-conf
  down /etc/openvpn/update-resolv-conf
  ```

### Uninstallation

Run the uninstall script with superuser privileges:
```bash
sudo ./scripts/uninstall.sh
```
This removes installed files and desktop entries, but preserves VPN configurations and user data under `~/.config/openvpn-gui/`.

### Contributing

Contributions are welcome! Please open an issue or submit a pull request on the repository.

### License

No license specified. Please add a `LICENSE` file to clarify terms.

---

## Deutsch

### Übersicht

OpenVPN GUI ist ein Linux-Desktop-Client zur Verwaltung von OpenVPN-Verbindungen. Es bietet eine einfache grafische Oberfläche zum Importieren, Verbinden und Trennen von VPN-Konfigurationen mit Systemtray-Integration, verschlüsselter Speicherung von Zugangsdaten und Leckschutz.

### Funktionen

- Import und Verwaltung mehrerer OpenVPN-Konfigurationsdateien (`.ovpn`, `.conf`)
- Sichere, verschlüsselte Speicherung von VPN-Zugangsdaten
- Ein-Klick-Verbindung und -Trennung von VPN-Sitzungen
- Systemtray-Symbol mit Echtzeit-Status und Benachrichtigungen
- Integrierter Log-Viewer zur Überwachung von Verbindungsereignissen
- DNS-Leckschutz über `update-resolv-conf`
- IPv6-Leckschutz mit `ip6tables`
- Optionale systemd-Benutzerdienste für automatischen Start
- Desktop-Integration mit `.desktop`-Eintrag

### Voraussetzungen

- Linux-Distribution (getestet unter Ubuntu)
- Python 3.8 oder höher
- OpenVPN und `sudo` installiert und im `PATH`
- DNS-Update-Skript unter `/etc/openvpn/update-resolv-conf` (bereitgestellt von `openvpn-systemd-resolved`)
- Benutzer in der Gruppe `openvpn`, um VPN ohne Passwortabfrage zu verwalten
- Python-Pakete: `PyQt6`, `cryptography` (installieren über `pip install -r requirements.txt`)

### Installation

1. Wechseln Sie in das Projektverzeichnis:
   ```bash
   cd OpenVPN-Py
   ```
2. Führen Sie das Installationsskript mit Root-Rechten aus:
   ```bash
   sudo ./scripts/install.sh
   ```
3. (Optional) Aktivieren Sie den systemd-Benutzerdienst:
   ```bash
   sudo ./scripts/install.sh --with-service
   ```
4. Melden Sie sich ab und erneut an, damit die Gruppenmitgliedschaft wirksam wird (Benutzer muss in der Gruppe `openvpn` sein).

### Nutzung

- Starten Sie die Anwendung über das Startmenü (OpenVPN GUI) oder per Kommandozeile:
  ```bash
  openvpn-gui
  ```
- Im Hauptfenster:
  1. Importieren Sie `.ovpn`/`.conf` Dateien mit "Konfiguration importieren"
  2. Wählen Sie eine Konfiguration aus der Liste aus
  3. Klicken Sie auf "Verbinden", um die VPN-Sitzung zu starten
  4. Geben Sie Anmeldedaten ein und wählen Sie Speicheroption
  5. Verfolgen Sie die Verbindung in Echtzeit im Log-Viewer
- Verwenden Sie das Tray-Symbol für Schnellaktionen und Statusmeldungen.

### Konfiguration

- Systemweite Konfigurationen: Legen Sie `.ovpn`/`.conf` Dateien in `/etc/openvpn/client/` ab
- Benutzerkonfigurationen: Legen Sie Dateien in `~/.config/openvpn/` ab
- Jede Konfigurationsdatei muss enthalten:
  ```text
  script-security 2
  up /etc/openvpn/update-resolv-conf
  down /etc/openvpn/update-resolv-conf
  ```

### Deinstallation

Führen Sie das Uninstall-Skript mit Root-Rechten aus:
```bash
sudo ./scripts/uninstall.sh
```
Hierdurch werden installierte Dateien und Desktop-Einträge entfernt, VPN-Konfigurationen und Benutzerdaten in `~/.config/openvpn-gui/` bleiben erhalten.

### Mitwirken

Beiträge, Fehlerberichte und Feature-Anfragen sind willkommen. Bitte öffnen Sie ein Issue oder senden Sie einen Pull Request.

### Lizenz

Keine Lizenz angegeben. Bitte fügen Sie eine `LICENSE`-Datei hinzu, um die Nutzungsbedingungen zu klären. 
