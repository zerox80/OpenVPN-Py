# vpn_manager.py
import subprocess
import logging
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import constants as C

logger = logging.getLogger(__name__)

class VPNManager(QObject):
    state_changed = pyqtSignal(C.VpnState)
    log_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._process = None
        self._current_config_path: Path | None = None
        self._state = C.VpnState.NO_CONFIG_SELECTED
        
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(2000)  # Check status every 2 seconds
        self._status_timer.timeout.connect(self.check_connection_status)

    def _set_state(self, state: C.VpnState):
        if self._state != state:
            logger.info(f"VPN state changing from {self._state.name} to {state.name}")
            self._state = state
            self.state_changed.emit(self._state)

    def connect(self, config_path: str, username: str, password: str):
        if self._status_timer.isActive():
            self.log_received.emit("Already connected or connecting.")
            return

        self._current_config_path = Path(config_path)
        self._set_state(C.VpnState.CONNECTING)
        self.log_received.emit(f"Connecting to {self._current_config_path.name}...")

        # Clear previous log file to avoid reading old status messages
        if C.LOG_FILE_PATH.exists():
            C.LOG_FILE_PATH.unlink()

        try:
            command = [
                "sudo", "-A", 
                str(C.HELPER_SCRIPT_PATH), 
                "start", 
                str(self._current_config_path), 
                str(C.LOG_FILE_PATH)
            ]
            
            auth_input = f"{username}\n{password}\n"

            self._process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = self._process.communicate(input=auth_input)

            if self._process.returncode != 0:
                error_message = stderr.strip()
                logger.error(f"Helper script failed: {error_message}")
                raise RuntimeError(error_message)

            self.log_received.emit("VPN process started via helper.")
            self._status_timer.start()

        except Exception as e:
            self.log_received.emit(f"Error connecting: {e}")
            self._cleanup(error=True)

    def disconnect(self):
        if not self._current_config_path:
            self.log_received.emit("Not currently connected.")
            return

        # Always try to stop, even if timer isn't active, to clean up stale services
        self._set_state(C.VpnState.DISCONNECTING)
        self.log_received.emit("Disconnecting...")
        
        try:
            command = [
                "sudo", "-A", 
                str(C.HELPER_SCRIPT_PATH), 
                "stop", 
                self._current_config_path.name,
                str(C.LOG_FILE_PATH)
            ]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            self.log_received.emit(f"Disconnect command sent. Helper output: {result.stdout.strip()}")
        
        except subprocess.CalledProcessError as e:
            self.log_received.emit(f"Error during disconnect: {e.stderr.strip()}")
        except Exception as e:
            self.log_received.emit(f"An unexpected error occurred during disconnect: {e}")
        finally:
            self._cleanup()

    def check_connection_status(self):
        if not self._current_config_path:
            self._cleanup()
            return
        
        try:
            command = [
                "sudo", "-A", 
                str(C.HELPER_SCRIPT_PATH), 
                "status", 
                self._current_config_path.name
            ]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            status_str = result.stdout.strip()

            if status_str == "connected":
                if self._state != C.VpnState.CONNECTED:
                    try:
                        log_content = C.LOG_FILE_PATH.read_text()
                        if "Initialization Sequence Completed" in log_content:
                            self.log_received.emit("Connection successfully established.")
                            self._set_state(C.VpnState.CONNECTED)
                        # else, stay in CONNECTING state
                    except FileNotFoundError:
                        pass # Log not yet available, stay in CONNECTING state

            elif status_str == "error":
                self.log_received.emit("VPN connection failed or is in an error state.")
                self._cleanup(error=True)
            else: # disconnected
                if self._state in (C.VpnState.CONNECTED, C.VpnState.CONNECTING):
                    self.log_received.emit("VPN terminated.")
                self._cleanup()

        except Exception as e:
            self.log_received.emit(f"Could not check VPN status: {e}")
            self._cleanup(error=True)

    def _cleanup(self, error=False):
        self._status_timer.stop()
        self._process = None
        
        if error:
            self._set_state(C.VpnState.ERROR)
        else:
            self._set_state(C.VpnState.DISCONNECTED)
