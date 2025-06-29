# /constants.py

from pathlib import Path
from enum import Enum, auto

APP_NAME = "OpenVPN-Py"
APP_VERSION = "1.0"
BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "configs"
UI_DIR = BASE_DIR / "ui"
I18N_DIR = BASE_DIR / "i18n"
SCRIPTS_DIR = BASE_DIR / "scripts"

HELPER_SCRIPT_PATH = SCRIPTS_DIR / "openvpn-gui-helper.sh"

# Use Enum for more robust state management
class VpnState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    DISCONNECTING = auto()
    AUTH_FAILED = auto()
    ERROR = auto()
    NO_CONFIG_SELECTED = auto()

# Log messages
LOG_LINE_SEPARATOR = "-" * 20