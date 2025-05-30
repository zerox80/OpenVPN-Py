# constants.py

# VPN States
VPN_STATE_DISCONNECTED = "disconnected"
VPN_STATE_CONNECTING = "connecting"
VPN_STATE_CONNECTED = "connected"
VPN_STATE_DISCONNECTING = "disconnecting"
VPN_STATE_ERROR = "error"
VPN_STATE_AUTH_FAILED = "auth_failed"
VPN_STATE_CONNECTION_FAILED = "connection_failed"
VPN_STATE_RESOLVE_FAILED = "resolve_failed"
VPN_STATE_FATAL_ERROR = "fatal_error"

# UI Status Messages (German)
STATUS_MSG_DISCONNECTED = "Nicht verbunden"
STATUS_MSG_CONNECTING = "Verbinde..."
STATUS_MSG_CONNECTED = "Verbunden"
STATUS_MSG_DISCONNECTING = "Trenne..."
STATUS_MSG_ERROR = "Fehler"
STATUS_MSG_AUTH_FAILED = "Authentifizierung fehlgeschlagen"
STATUS_MSG_CONNECTION_FAILED = "Verbindung fehlgeschlagen"
STATUS_MSG_RESOLVE_FAILED = "Server nicht erreichbar"
STATUS_MSG_FATAL_ERROR = "Schwerwiegender Fehler"


# Colors
COLOR_DISCONNECTED = "#757575"
COLOR_CONNECTING = "#FF9800"
COLOR_CONNECTED = "#4CAF50"
COLOR_DISCONNECTING = "#FF9800"  # Same as connecting
COLOR_ERROR = "#F44336"
COLOR_DEFAULT_ICON = "#2196F3"
COLOR_WHITE = "white"
COLOR_LOG_BACKGROUND = "#1e1e1e"
COLOR_LOG_TEXT = "#d4d4d4"

# Logging
LOG_FILE_PATH = ".config/openvpn-gui/app.log" # Relative to home directory

# UI Texts (German)
APP_TITLE = "OpenVPN GUI"
IMPORT_CONFIG_TITLE = "OpenVPN-Konfiguration auswählen"
IMPORT_CONFIG_FILTER = "OpenVPN-Konfiguration (*.ovpn *.conf);;Alle Dateien (*)"
ERROR_NO_CONFIG_SELECTED_TITLE = "Keine Konfiguration"
ERROR_NO_CONFIG_SELECTED_MSG = "Bitte wählen Sie eine VPN-Konfiguration aus."
CLEAR_CREDS_PROMPT_TITLE = "Anmeldedaten löschen"
CLEAR_CREDS_PROMPT_MSG = "Möchten Sie die gespeicherten Anmeldedaten für \'{config_name}\' wirklich löschen?"
STATUS_BAR_CLEARED_CREDS = "Anmeldedaten gelöscht"
STATUS_BAR_NO_CREDS_FOUND = "Keine gespeicherten Anmeldedaten gefunden"
TRAY_MSG_VPN_CONNECTED_TITLE = "VPN Verbunden"
TRAY_MSG_VPN_CONNECTED_MSG = "Verbunden mit {config_name}" # Placeholder for config name
LOG_MSG_CONNECTING_TO = "Verbinde mit {config_name}..."
LOG_MSG_DISCONNECTING = "Trenne VPN-Verbindung..."
LOG_MSG_CONNECTED_SUCCESS = "✓ VPN-Verbindung hergestellt"
LOG_MSG_DISCONNECTED_SUCCESS = "✗ VPN-Verbindung getrennt"
LOG_MSG_AUTH_FAILED = "✗ Authentifizierung fehlgeschlagen"
LOG_MSG_AUTH_FAILED_DETAIL = "Benutzername oder Passwort ist falsch."
LOG_MSG_CONNECTION_FAILED = "✗ Verbindung fehlgeschlagen"
LOG_MSG_RESOLVE_FAILED = "✗ Server nicht erreichbar"
LOG_MSG_FATAL_ERROR = "✗ Schwerwiegender Fehler"
LOG_MSG_PEER_CONNECTION_INITIATED = "→ Verbindung wird aufgebaut..."
LOG_MSG_ROUTES_CONFIGURING = "→ Routen werden konfiguriert..."
LOG_MSG_TUN_TAP_CREATING = "→ Netzwerkinterface wird erstellt..."

# Default Icon settings
DEFAULT_ICON_SIZE = 64
DEFAULT_ICON_ELLIPSE_RECT = (8, 8, 48, 48) # x, y, w, h
DEFAULT_ICON_TEXT_PIXEL_SIZE = 20
DEFAULT_ICON_TEXT = "VPN"

# Tray messages
TRAY_STATUS_PREFIX = "Status: "
TRAY_MSG_MINIMIZED_TITLE = "OpenVPN GUI"
TRAY_MSG_MINIMIZED_MSG = "Anwendung wurde minimiert. VPN-Verbindung bleibt aktiv."

# Close event messages
CLOSE_EVENT_VPN_ACTIVE_TITLE = "VPN aktiv"
CLOSE_EVENT_VPN_ACTIVE_MSG = "Eine VPN-Verbindung ist aktiv. Möchten Sie die Anwendung minimieren oder beenden?"
QUIT_APP_VPN_DISCONNECT_PROMPT_TITLE = "VPN trennen?"
QUIT_APP_VPN_DISCONNECT_PROMPT_MSG = "Möchten Sie die VPN-Verbindung vor dem Beenden trennen?"

# Main function messages
MAIN_APP_ALREADY_RUNNING_TITLE = "OpenVPN GUI"
MAIN_APP_ALREADY_RUNNING_MSG = "Die Anwendung läuft bereits.\\n\\nBitte prüfen Sie das System-Tray."

# Check requirements messages
CHECK_REQ_ISSUES_FOUND_INTRO = "Folgende Probleme wurden gefunden:\\n\\n"
CHECK_REQ_ISSUES_SUFFIX = "\\n\\nDie Anwendung funktioniert möglicherweise nicht korrekt."
CHECK_REQ_WARNING_TITLE = "Systemprüfung"

# Status Timer
STATUS_TIMER_INTERVAL_MS = 5000

# Window settings
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 600

# Log text settings
LOG_TEXT_MAX_HEIGHT = 200

# Shared Memory Key
SHARED_MEMORY_KEY = "openvpn-gui-single-instance"

# VPN Worker related
VPN_WORKER_DISCONNECT_DELAY_MS = 1000

# Tray Message Duration
TRAY_MESSAGE_DURATION_MS = 3000

# OpenVPN specific paths
UPDATE_RESOLV_CONF_PATH = "/etc/openvpn/update-resolv-conf"

# Credentials Dialog UI Texts (German)
CRED_DIALOG_TITLE = "VPN-Anmeldedaten"
CRED_DIALOG_INFO_LABEL_PREFIX = "Anmeldedaten für: "
CRED_DIALOG_USERNAME_LABEL = "Benutzername:"
CRED_DIALOG_USERNAME_PLACEHOLDER = "VPN-Benutzername"
CRED_DIALOG_PASSWORD_LABEL = "Passwort:"
CRED_DIALOG_PASSWORD_PLACEHOLDER = "VPN-Passwort"
CRED_DIALOG_SHOW_PASSWORD_CHECKBOX = "Passwort anzeigen"
CRED_DIALOG_SAVE_CREDENTIALS_CHECKBOX = "Anmeldedaten speichern"
CRED_DIALOG_VALIDATION_ERROR_TITLE = "Fehler"
CRED_DIALOG_VALIDATION_EMPTY_USERNAME_MSG = "Bitte geben Sie einen Benutzernamen ein."
CRED_DIALOG_VALIDATION_EMPTY_PASSWORD_MSG = "Bitte geben Sie ein Passwort ein."

# General Icon Names (used in multiple places)
DEFAULT_VPN_ICON_FILENAME = "vpn-icon.png"

# Window settings (add dialog width)
CRED_DIALOG_MIN_WIDTH = 350

# Credentials Manager settings
CRED_MANAGER_CONFIG_DIR_NAME = "openvpn-gui"
CRED_MANAGER_KEY_FILENAME = ".key"
CRED_MANAGER_CREDS_FILENAME = "credentials.enc"

# Config Manager settings
CONFIG_DIR_SYSTEM = "/etc/openvpn/client" # Standard system path for OpenVPN client configs
CONFIG_DIR_USER_PARENT = ".config"
CONFIG_DIR_USER_APP_SPECIFIC = "openvpn-gui" # Subdirectory for app's configs, consistent with logging
CONFIG_VALIDATION_KEYWORDS = ["remote", "client"]
CONFIG_IMPORT_FILE_NOT_FOUND_MSG_PREFIX = "Datei nicht gefunden: "
CONFIG_IMPORT_INVALID_CONFIG_MSG = "Ungültige OpenVPN-Konfiguration"
CONFIG_GET_PATH_NOT_FOUND_MSG_PREFIX = "Konfiguration "
CONFIG_GET_PATH_NOT_FOUND_MSG_SUFFIX = " nicht gefunden" # Adjusted for proper spacing 