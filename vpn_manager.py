# vpn_manager.py
import subprocess
import logging
import signal
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import constants as C

logger = logging.getLogger(__name__)


class VPNManager(QObject):
    state_changed = pyqtSignal(C.VpnState)
    log_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._process = None
        self._current_config_path: Optional[Path] = None
        self._state = C.VpnState.NO_CONFIG_SELECTED
        self._ever_connected = False

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(2000)  # Check status every 2 seconds
        self._status_timer.timeout.connect(self.check_connection_status)

    def _set_state(self, state: C.VpnState):
        if self._state != state:
            logger.info(
                f"VPN state changing from {self._state.name} to {state.name}"
            )
            self._state = state
            self.state_changed.emit(self._state)

    def _emit_log_snippet(self, header: str = "Startup error log excerpt:", max_lines: int = 25):
        """Emit the last lines of the OpenVPN log to help diagnose startup issues."""
        try:
            content = C.LOG_FILE_PATH.read_text()
            lines = content.splitlines()
            snippet = "\n".join(lines[-max_lines:])
            if snippet.strip():
                self.log_received.emit(f"{header}\n{snippet}")
        except Exception:
            # If we can't read the log, ignore silently
            pass

    def connect(self, config_path: str, username: str, password: str):
        if (
            self._state == C.VpnState.CONNECTING
            or self._state == C.VpnState.CONNECTED
        ):
            self.log_received.emit("Already connected or connecting.")
            return

        self._current_config_path = Path(config_path)
        self._set_state(C.VpnState.CONNECTING)
        self.log_received.emit(
            f"Connecting to {self._current_config_path.name}..."
        )
        self._ever_connected = False

        # Clear previous log file to avoid reading old status messages
        try:
            if C.LOG_FILE_PATH.exists():
                C.LOG_FILE_PATH.unlink()
        except Exception as e:
            logger.warning(f"Could not clear log file: {e}")

        try:
            command = [
                "sudo",
                "-n",
                str(C.HELPER_SCRIPT_PATH),
                "start",
                str(self._current_config_path),
                str(C.LOG_FILE_PATH),
            ]

            auth_input = f"{username}\n{password}\n"

            self._process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                stdout, stderr = self._process.communicate(input=auth_input, timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                stdout, stderr = self._process.communicate()
                raise RuntimeError("Helper script timed out")

            if self._process.returncode != 0:
                error_message = stderr.strip()
                logger.error(f"Helper script failed: {error_message}")
                # Provide a clearer hint when sudo requires a password or askpass failed
                lower_err = error_message.lower()
                if (
                    "a password is required" in lower_err
                    or "askpass" in lower_err
                    or "ein passwort ist notwendig" in lower_err
                    or "passwort" in lower_err and "sudo" in lower_err
                ):
                    error_message += (
                        "\nHinweis: Füge deinen Benutzer der Gruppe 'openvpn' hinzu und melde dich neu an (oder starte neu). "
                        "Die App nutzt eine NOPASSWD-sudoers-Regel für den Helper."
                    )
                raise RuntimeError(error_message)

            self.log_received.emit("VPN process started via helper.")
            self._status_timer.start()

        except subprocess.TimeoutExpired:
            self.log_received.emit("Connection timeout - helper script did not respond")
            self._cleanup(error=True)
        except Exception as e:
            self.log_received.emit(f"Error connecting: {e}")
            self._cleanup(error=True)

    def disconnect(self):
        if not self._current_config_path:
            self.log_received.emit(
                "Not currently connected or no config selected."
            )
            return

        self._set_state(C.VpnState.DISCONNECTING)
        self.log_received.emit("Disconnecting...")

        try:
            command = [
                "sudo",
                "-n",
                str(C.HELPER_SCRIPT_PATH),
                "stop",
                self._current_config_path.name,
                str(C.LOG_FILE_PATH),
            ]
            result = subprocess.run(
                command, check=True, capture_output=True, text=True
            )
            self.log_received.emit(
                "Disconnect command sent. Helper output: "
                f"{result.stdout.strip()}"
            )

        except subprocess.CalledProcessError as e:
            self.log_received.emit(
                f"Error during disconnect: {e.stderr.strip()}"
            )
        except Exception as e:
            self.log_received.emit(
                "An unexpected error occurred during disconnect: " f"{e}"
            )
        finally:
            self._cleanup()

    def check_connection_status(self):
        if not self._current_config_path:
            self._cleanup()
            return

        try:
            command = [
                "sudo",
                "-n",
                str(C.HELPER_SCRIPT_PATH),
                "status",
                self._current_config_path.name,
            ]
            result = subprocess.run(
                command, check=True, capture_output=True, text=True
            )
            status_str = result.stdout.strip()

            if status_str == "connected":
                if self._state != C.VpnState.CONNECTED:
                    try:
                        log_content = C.LOG_FILE_PATH.read_text()
                        if "Initialization Sequence Completed" in log_content:
                            self.log_received.emit(
                                "Connection successfully established."
                            )
                            self._set_state(C.VpnState.CONNECTED)
                            self._ever_connected = True
                        # else, stay in CONNECTING state
                    except FileNotFoundError:
                        pass  # Log not yet available, stay in CONNECTING state

            elif status_str == "error":
                # Try to determine if this was an authentication failure
                auth_failed = False
                try:
                    log_content = C.LOG_FILE_PATH.read_text()
                    if any(x in log_content.upper() for x in ["AUTH_FAILED", "AUTH FAILURE", "AUTH FAILED", "AUTHENTICATION FAILED"]):
                        auth_failed = True
                except Exception:
                    pass

                if auth_failed:
                    self.log_received.emit("Authentication failed.")
                    self._set_state(C.VpnState.AUTH_FAILED)
                    self._emit_log_snippet()
                else:
                    self.log_received.emit(
                        "VPN connection failed or is in an error state."
                    )
                    self._emit_log_snippet()
                self._cleanup(error=True)
            else:  # disconnected or not yet active
                if self._state == C.VpnState.CONNECTED:
                    self.log_received.emit("VPN terminated.")
                    self._cleanup()
                elif self._state == C.VpnState.CONNECTING:
                    # If the process died early, try to infer likely cause from the log.
                    try:
                        log_upper = C.LOG_FILE_PATH.read_text().upper()
                        auth_markers = [
                            "AUTH_FAILED",
                            "AUTH FAILURE",
                            "AUTH FAILED",
                            "AUTHENTICATION FAILED",
                        ]
                        fatal_markers = [
                            "FATAL",
                            "TLS ERROR",
                            "VERIFY ERROR",
                            "CANNOT RESOLVE",
                            "NETWORK IS UNREACHABLE",
                            "EXITING DUE TO FATAL ERROR",
                            "OPTIONS ERROR",
                            "RESOLVE:",
                        ]
                        if any(m in log_upper for m in auth_markers):
                            self.log_received.emit("Authentication failed.")
                            self._set_state(C.VpnState.AUTH_FAILED)
                            self._emit_log_snippet()
                            self._cleanup(error=True)
                        elif any(m in log_upper for m in fatal_markers):
                            self.log_received.emit("VPN startup failed. See log for details.")
                            self._emit_log_snippet()
                            self._cleanup(error=True)
                        # else, keep waiting for next poll
                    except Exception:
                        # Log not yet available; keep waiting.
                        pass
                else:
                    self._cleanup()

        except Exception as e:
            self.log_received.emit(f"Could not check VPN status: {e}")
            self._cleanup(error=True)

    def _cleanup(self, error=False):
        self._status_timer.stop()
        self._process = None

        if error:
            # Preserve AUTH_FAILED state if already set
            if self._state != C.VpnState.AUTH_FAILED:
                self._set_state(C.VpnState.ERROR)
        else:
            # If the state was DISCONNECTING, the final state should be
            # DISCONNECTED
            if self._state == C.VpnState.DISCONNECTING:
                self._set_state(C.VpnState.DISCONNECTED)
            else:
                self._set_state(C.VpnState.DISCONNECTED)

        self._current_config_path = None
