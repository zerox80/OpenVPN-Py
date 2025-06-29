import subprocess
import time
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
import constants as C

class VPNManager(QObject):
    state_changed = pyqtSignal(C.VpnState)
    log_received = pyqtSignal(str)
    connection_terminated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.process = None
        self.pid_file_path = None
        self.is_running = False
        self.state = C.VpnState.DISCONNECTED

        # Timer to check connection status based on logs
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.check_connection_status)

    def _set_state(self, state: C.VpnState):
        if self.state != state:
            self.state = state
            self.state_changed.emit(self.state)

    def run_in_thread(self):
        thread = QThread.create(self._run)
        thread.start()

    def connect(self, config_path, username, password):
        if self.is_running:
            self.log_received.emit("Already connected or connecting.")
            return

        self.is_running = True
        self._set_state(C.VpnState.CONNECTING)
        self.log_received.emit(f"Connecting to {config_path}...")

        try:
            # Create the runtime directory if it doesn't exist
            C.PID_DIR.mkdir(parents=True, exist_ok=True)
            # Ensure the log file exists for tailing
            C.LOG_FILE_PATH.touch()

            command = ["sudo", "-A", str(C.HELPER_SCRIPT_PATH), "start", config_path, str(C.LOG_FILE_PATH)]
            
            # The credentials will be sent to the stdin of the openvpn process
            # which is started by our helper script
            auth_input = f"{username}\n{password}\n"

            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = self.process.communicate(input=auth_input)

            if self.process.returncode != 0:
                raise RuntimeError(f"Helper script failed: {stderr.strip()}")

            self.pid_file_path = stdout.strip()
            if not self.pid_file_path:
                 raise RuntimeError("Helper script did not return a PID file path.")

            self.log_received.emit(f"VPN process started. PID file: {self.pid_file_path}")
            self.status_timer.start(1000)  # Check status every second

        except Exception as e:
            self.log_received.emit(f"Error connecting: {e}")
            self._cleanup_after_termination()
            self._set_state(C.VpnState.ERROR)
            
    def disconnect(self):
        if not self.is_running:
            self.log_received.emit("Not currently connected.")
            return

        self._set_state(C.VpnState.DISCONNECTING)
        self.log_received.emit("Disconnecting...")
        
        try:
            if self.pid_file_path:
                command = ["sudo", "-A", str(C.HELPER_SCRIPT_PATH), "stop", self.pid_file_path, str(C.LOG_FILE_PATH)]
                result = subprocess.run(command, check=True, capture_output=True, text=True)
                self.log_received.emit(f"Disconnect command sent. Helper output: {result.stdout.strip()}")
            else:
                self.log_received.emit("Warning: No PID file path found to stop the process.")
        
        except subprocess.CalledProcessError as e:
            self.log_received.emit(f"Error during disconnect: {e.stderr.strip()}")
            self._set_state(C.VpnState.ERROR)
        except Exception as e:
            self.log_received.emit(f"An unexpected error occurred during disconnect: {e}")
            self._set_state(C.VpnState.ERROR)
        finally:
            self._cleanup_after_termination()


    def check_connection_status(self):
        if not self.is_running:
            self.status_timer.stop()
            return
            
        # Check if the process has terminated on its own
        if self.process and self.process.poll() is not None:
            self.log_received.emit("VPN process terminated unexpectedly.")
            self._cleanup_after_termination()
            return

        # Check log file for connection status
        try:
            with open(C.LOG_FILE_PATH, 'r') as f:
                log_content = f.read()
                if "Initialization Sequence Completed" in log_content:
                    if self.state != C.VpnState.CONNECTED:
                        self.log_received.emit("Connection successfully established.")
                        self._set_state(C.VpnState.CONNECTED)
                # You can add more checks for other states here
        except FileNotFoundError:
            # This can happen if the log file hasn't been created yet
            pass
        except Exception as e:
            self.log_received.emit(f"Could not read log file: {e}")

    def _cleanup_after_termination(self):
        self.status_timer.stop()
        self.process = None
        self.pid_file_path = None
        self.is_running = False
        self._set_state(C.VpnState.DISCONNECTED)
        self.connection_terminated.emit()
        # Optional: Clean up log file
        if C.LOG_FILE_PATH.exists():
            C.LOG_FILE_PATH.unlink()