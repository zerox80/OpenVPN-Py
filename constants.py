import os
from enum import Enum
from pathlib import Path

# Application Info
APP_NAME = "OpenVPN-Py"
APP_VERSION = "1.0.0"

# User-specific paths
USER_HOME = Path.home()
APP_DATA_DIR = USER_HOME / ".config" / "openvpn-py"
USER_CONFIG_DIR = APP_DATA_DIR / "configs"
HELPER_SCRIPT_PATH = APP_DATA_DIR / "scripts/openvpn-gui-helper.sh"

# System-wide config paths (add more if needed)
SYSTEM_CONFIG_DIRS = [
    Path("/etc/openvpn/client"),
    Path("/etc/openvpn"),
]

# Runtime paths (using user's runtime directory for better isolation)
# This directory is typically /run/user/$(id -u)
RUNTIME_DIR = Path(os.getenv('XDG_RUNTIME_DIR', f"/run/user/{os.getuid()}"))
PID_DIR = RUNTIME_DIR / "openvpn-py-gui"
LOG_FILE_PATH = PID_DIR / "openvpn_gui_log.log"


class VpnState(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    DISCONNECTING = 3
    ERROR = 4
    NO_CONFIG = 5