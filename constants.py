# constants.py
import logging
from pathlib import Path
from enum import Enum, auto

# Basic Application Info
APP_NAME = "OpenVPN-Py"
VERSION = "1.0.0"

# --- PATHS ---
# Using pathlib for robust path management.

# Base directory for user-specific files, e.g., ~/.config/openvpn-py
xdg_config_home = Path.home() / ".config"
USER_DATA_DIR = xdg_config_home / "openvpn-py"

# Directories for configs, logs, and runtime data
USER_CONFIGS_DIR = USER_DATA_DIR / "configs"
LOG_DIR = USER_DATA_DIR / "logs"

# Create user directories if they don't exist
USER_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# System-wide configuration paths to search for .ovpn files
SYSTEM_CONFIG_DIRS = [
    Path("/etc/openvpn/client"),
    Path("/etc/openvpn"),
]

# Path to the log file used by the helper and read by the GUI.
LOG_FILE_PATH = LOG_DIR / "openvpn-gui.log"

# Path to the helper script, consistent with install.sh
HELPER_SCRIPT_PATH = Path("/usr/local/bin/openvpn-gui-helper.sh")


# --- VPN State Management ---
# Enum for tracking the VPN connection state across the application.
class VpnState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    DISCONNECTING = auto()
    ERROR = auto()
    AUTH_FAILED = auto() # Specific error state
    NO_CONFIG_SELECTED = auto()

# --- Logging ---
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# --- UI ---
MAX_LOG_LINES_IN_VIEWER = 500
