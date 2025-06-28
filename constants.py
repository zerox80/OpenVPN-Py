# constants.py
from pathlib import Path

# --- App Info ---
APP_TITLE = "OpenVPN GUI"
SHARED_MEMORY_KEY = "openvpn-gui-single-instance-lock"

# --- Pfade ---
HELPER_SCRIPT_PATH = "/usr/local/bin/openvpn-gui-helper"
UPDATE_RESOLV_CONF_PATH = "/etc/openvpn/update-resolv-conf"
CONFIG_DIR_SYSTEM = "/etc/openvpn/client"
CONFIG_DIR_USER_PARENT = ".config"
CONFIG_DIR_USER_APP_SPECIFIC = "openvpn-gui/configs" # Separater Ordner für importierte Konfigs
CRED_MANAGER_CONFIG_DIR_NAME = "openvpn-gui"
LOG_FILE_PATH = f"{CONFIG_DIR_USER_PARENT}/{CRED_MANAGER_CONFIG_DIR_NAME}/app.log"
DEFAULT_VPN_ICON_FILENAME = "vpn-icon.png"

# --- VPN States ---
VPN_STATE_DISCONNECTED = "disconnected"
VPN_STATE_CONNECTING = "connecting"
VPN_STATE_CONNECTED = "connected"
VPN_STATE_DISCONNECTING = "disconnecting"
VPN_STATE_ERROR = "error"
VPN_STATE_AUTH_FAILED = "auth_failed"
VPN_STATE_CONNECTION_FAILED = "connection_failed"
VPN_STATE_RESOLVE_FAILED = "resolve_failed"
VPN_STATE_FATAL_ERROR = "fatal_error"

# --- Farben ---
COLOR_DISCONNECTED = "#757575"
COLOR_CONNECTING = "#FF9800"
COLOR_CONNECTED = "#4CAF50"
COLOR_DISCONNECTING = "#FF9800"
COLOR_ERROR = "#F44336"
COLOR_WHITE = "white"
COLOR_LOG_BACKGROUND = "#1e1e1e"
COLOR_LOG_TEXT = "#d4d4d4"
COLOR_DEFAULT_ICON = "#2196F3"

# --- UI Texte (Deutsch) ---
# Status-Meldungen
STATUS_MSG_DISCONNECTED = "Nicht verbunden"
STATUS_MSG_CONNECTING = "Verbinde..."
STATUS_MSG_CONNECTED = "Verbunden"
STATUS_MSG_DISCONNECTING = "Trenne..."
STATUS_MSG_ERROR = "Fehler"
STATUS_MSG_AUTH_FAILED = "Authentifizierung fehlgeschlagen"

# Dialoge und Fenster
IMPORT_CONFIG_TITLE = "OpenVPN-Konfiguration auswählen"
IMPORT_CONFIG_FILTER = "OpenVPN-Konfiguration (*.ovpn *.conf);;Alle Dateien (*)"
ERROR_NO_CONFIG_SELECTED_TITLE = "Keine Konfiguration ausgewählt"
ERROR_NO_CONFIG_SELECTED_MSG = "Bitte wählen Sie zuerst eine VPN-Konfiguration aus der Liste aus."
CLEAR_CREDS_PROMPT_TITLE = "Anmeldedaten löschen"
CLEAR_CREDS_PROMPT_MSG = "Möchten Sie die gespeicherten Anmeldedaten für '{config_name}' wirklich aus dem System-Schlüsselbund löschen?"
CLOSE_EVENT_VPN_ACTIVE_TITLE = "VPN aktiv"
CLOSE_EVENT_VPN_ACTIVE_MSG = "Eine VPN-Verbindung ist aktiv. Soll die Anwendung in den System-Tray minimiert werden?"
QUIT_APP_VPN_DISCONNECT_PROMPT_TITLE = "VPN trennen?"
QUIT_APP_VPN_DISCONNECT_PROMPT_MSG = "Möchten Sie die aktive VPN-Verbindung vor dem Beenden trennen?"
MAIN_APP_ALREADY_RUNNING_TITLE = "Anwendung läuft bereits"
MAIN_APP_ALREADY_RUNNING_MSG = "Eine Instanz von OpenVPN GUI läuft bereits. Bitte prüfen Sie den System-Tray."

# Credentials Dialog
CRED_DIALOG_TITLE = "VPN-Anmeldedaten"
CRED_DIALOG_INFO_LABEL_PREFIX = "Anmeldedaten für: "
CRED_DIALOG_USERNAME_LABEL = "Benutzername:"
CRED_DIALOG_USERNAME_PLACEHOLDER = "Ihr VPN-Benutzername"
CRED_DIALOG_PASSWORD_LABEL = "Passwort:"
CRED_DIALOG_PASSWORD_PLACEHOLDER = "Ihr VPN-Passwort"
CRED_DIALOG_SHOW_PASSWORD_CHECKBOX = "Passwort anzeigen"
CRED_DIALOG_SAVE_CREDENTIALS_CHECKBOX = "Anmeldedaten sicher im System-Schlüsselbund speichern"
CRED_DIALOG_VALIDATION_ERROR_TITLE = "Eingabe erforderlich"
CRED_DIALOG_VALIDATION_EMPTY_USERNAME_MSG = "Bitte geben Sie einen Benutzernamen ein."
CRED_DIALOG_VALIDATION_EMPTY_PASSWORD_MSG = "Bitte geben Sie ein Passwort ein."

# Log-Meldungen
LOG_MSG_CONNECTING_TO = "Versuche, Verbindung mit {config_name} herzustellen..."
LOG_MSG_DISCONNECTING = "Trenne bestehende VPN-Verbindung..."
LOG_MSG_CONNECTED_SUCCESS = "✓ Verbindung erfolgreich hergestellt."
LOG_MSG_DISCONNECTED_SUCCESS = "✗ Verbindung wurde getrennt."
LOG_MSG_AUTH_FAILED = "✗ Authentifizierung fehlgeschlagen. Bitte prüfen Sie Ihre Anmeldedaten."
LOG_MSG_AUTH_FAILED_DETAIL = "Der eingegebene Benutzername oder das Passwort ist falsch."

# Status-Bar
STATUS_BAR_CLEARED_CREDS = "Gespeicherte Anmeldedaten wurden gelöscht."
STATUS_BAR_NO_CREDS_FOUND = "Keine gespeicherten Anmeldedaten für diese Konfiguration gefunden."

# Tray-Benachrichtigungen
TRAY_STATUS_PREFIX = "Status: "
TRAY_MSG_VPN_CONNECTED_TITLE = "VPN Verbunden"
TRAY_MSG_VPN_CONNECTED_MSG = "Erfolgreich verbunden mit {config_name}"
TRAY_MSG_MINIMIZED_TITLE = "OpenVPN GUI"
TRAY_MSG_MINIMIZED_MSG = "Anwendung läuft im Hintergrund weiter. Die VPN-Verbindung bleibt aktiv."

# Timings und Größen
STATUS_TIMER_INTERVAL_MS = 5000
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 550
LOG_TEXT_MAX_HEIGHT = 180
TRAY_MESSAGE_DURATION_MS = 3500

# Konfigurations-Management
CONFIG_VALIDATION_KEYWORDS = ["remote", "client"]
CONFIG_IMPORT_FILE_NOT_FOUND_MSG_PREFIX = "Quelldatei nicht gefunden: "
CONFIG_IMPORT_INVALID_CONFIG_MSG = "Dies scheint keine gültige OpenVPN-Konfigurationsdatei zu sein."