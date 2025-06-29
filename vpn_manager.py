# /vpn_manager.py

import subprocess
import time
import logging
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import constants as C

class VPNManager(QObject):
    """
    Manages the OpenVPN connection lifecycle.
    This object is intended to be moved to a separate thread.
    """
    state_changed = pyqtSignal(C.VpnState)
    log_received = pyqtSignal(str)
    connection_terminated = pyqtSignal()
    
    def __init__(self, credentials_manager):
        super().__init__()
        self.state = C.VpnState.DISCONNECTED
        self.process = None
        self.credentials_manager = credentials_manager
        self.current_config_path = None
        self.log_file_path = "/tmp/openvpn_gui_log.log" # Path used in helper script

        # Timer to periodically check the connection status
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.check_connection_status)

    @property
    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def _set_state(self, new_state: C.VpnState):
        if self.state != new_state:
            self.state = new_state
            self.state_changed.emit(self.state)
            logging.info(f"VPN state changed to: {new_state.name}")

    def connect(self, config_path: str):
        if self.is_running:
            self.log_received.emit("Already connected or a process is running.")
            return

        self.current_config_path = config_path
        self._set_state(C.VpnState.CONNECTING)
        self.log_received.emit(f"Connecting to {config_path}...")
        
        try:
            # Clear previous log file
            with open(self.log_file_path, "w") as f:
                f.write("--- Log started ---\n")

            command = ["sudo", "-A", str(C.HELPER_SCRIPT_PATH), "start", config_path]
            
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            
            # The process starts, now we monitor it
            self.status_timer.start(1000) # Check every second

        except FileNotFoundError:
            self.log_received.emit("Error: Helper script not found or sudo is not installed.")
            self._set_state(C.VpnState.ERROR)
            self.process = None
        except Exception as e:
            self.log_received.emit(f"An unexpected error occurred: {e}")
            self._set_state(C.VpnState.ERROR)
            self.process = None

    def disconnect(self):
        if not self.is_running:
            self.log_received.emit("Not connected.")
            return

        self._set_state(C.VpnState.DISCONNECTING)
        self.log_received.emit("Disconnecting...")
        
        try:
            pid = self.process.pid
            command = ["sudo", "-A", str(C.HELPER_SCRIPT_PATH), "stop", str(pid)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            
            # Ensure process is terminated
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            
            self.log_received.emit("Disconnected successfully.")

        except subprocess.CalledProcessError as e:
            self.log_received.emit(f"Error during disconnect: {e.stderr}")
            self._set_state(C.VpnState.ERROR)
        except Exception as e:
            self.log_received.emit(f"An unexpected error occurred during disconnect: {e}")
            self._set_state(C.VpnState.ERROR)
        finally:
            self.process = None
            self._set_state(C.VpnState.DISCONNECTED)
            self.status_timer.stop()
            self.connection_terminated.emit()

    def check_connection_status(self):
        if not self.is_running:
            # Process terminated unexpectedly
            self.log_received.emit("Connection process terminated unexpectedly.")
            self._set_state(C.VpnState.ERROR)
            self.status_timer.stop()
            self.connection_terminated.emit()
            return
        
        # Read the OpenVPN log file for status
        try:
            with open(self.log_file_path, "r") as f:
                log_content = f.read()
            
            # Very basic log checks
            if "Initialization Sequence Completed" in log_content:
                if self.state != C.VpnState.CONNECTED:
                    self._set_state(C.VpnState.CONNECTED)
                    self.log_received.emit("Connection established successfully.")
            elif "AUTH_FAILED" in log_content:
                self.log_received.emit("Authentication failed. Please check your credentials.")
                self._set_state(C.VpnState.AUTH_FAILED)
                self.disconnect() # Clean up the failed attempt
        except FileNotFoundError:
            # Log file might not be created yet, that's fine.
            pass
        except Exception as e:
            self.log_received.emit(f"Error reading log file: {e}")