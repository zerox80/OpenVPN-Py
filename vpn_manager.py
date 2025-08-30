# vpn_manager.py
import subprocess
import logging
import signal
import os
import time
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QCoreApplication
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
        # Track connection attempt timing and heuristics
        self._connect_started_at: Optional[float] = None
        self._connected_polls: int = 0

        # Timeout thresholds
        self._CONNECT_TIMEOUT_SECONDS = 90  # fail CONNECTING after this many seconds
        self._STATUS_CMD_TIMEOUT_SECONDS = 5
        self._DISCONNECT_CMD_TIMEOUT_SECONDS = 15

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(2000)  # Check status every 2 seconds
        self._status_timer.timeout.connect(self.check_connection_status)

        # Real-time log tailing
        self._log_timer = QTimer(self)
        self._log_timer.setInterval(800)  # poll ~1x/sec
        self._log_timer.timeout.connect(self._poll_log_file)
        self._log_file_pos = 0
        self._log_inode = None

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
        self._connect_started_at = time.monotonic()
        self._connected_polls = 0

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
                "--disable-external",
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
            # Start timers only if a Qt application exists (prevents test/headless crashes)
            self._start_timers_if_possible()

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
                command, check=True, capture_output=True, text=True, timeout=self._DISCONNECT_CMD_TIMEOUT_SECONDS
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

        # Guard: abort CONNECTING if we've exceeded a reasonable timeout
        if self._state == C.VpnState.CONNECTING and self._connect_started_at is not None:
            elapsed = time.monotonic() - self._connect_started_at
            if elapsed > self._CONNECT_TIMEOUT_SECONDS:
                self.log_received.emit(
                    f"Connection attempt timed out after {int(elapsed)}s."
                )
                self._emit_log_snippet(header="Timeout log excerpt:")
                # Ask helper to stop and archive last session log
                self._invoke_helper_stop_for_archive()
                self._cleanup(error=True)
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
                command, check=True, capture_output=True, text=True, timeout=self._STATUS_CMD_TIMEOUT_SECONDS
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
                            self._connected_polls = 0
                        else:
                            # Fallback: after several consecutive 'connected' reports, proceed
                            self._connected_polls += 1
                            if self._connected_polls >= 3:
                                self.log_received.emit(
                                    "Helper reports connected repeatedly; proceeding without the usual log marker."
                                )
                                self._set_state(C.VpnState.CONNECTED)
                                self._ever_connected = True
                                self._connected_polls = 0
                            # otherwise, stay in CONNECTING
                    except FileNotFoundError:
                        # Log not yet available, count towards heuristic
                        self._connected_polls += 1
                        if self._connected_polls >= 3:
                            self.log_received.emit(
                                "Helper reports connected repeatedly; proceeding though log not yet readable."
                            )
                            self._set_state(C.VpnState.CONNECTED)
                            self._ever_connected = True
                            self._connected_polls = 0

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
                # Ensure helper stops and archives the session log into Documents
                self._invoke_helper_stop_for_archive()
                self._cleanup(error=True)
            else:  # disconnected or not yet active
                if self._state == C.VpnState.CONNECTED:
                    self.log_received.emit("VPN terminated.")
                    # Archive last session log into Documents
                    self._invoke_helper_stop_for_archive()
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
                            # Archive last session log into Documents
                            self._invoke_helper_stop_for_archive()
                            self._cleanup(error=True)
                        elif any(m in log_upper for m in fatal_markers):
                            self.log_received.emit("VPN startup failed. See log for details.")
                            self._emit_log_snippet()
                            # Archive last session log into Documents
                            self._invoke_helper_stop_for_archive()
                            self._cleanup(error=True)
                        # else, keep waiting for next poll
                    except Exception:
                        # Log not yet available; keep waiting.
                        pass
                else:
                    # Ensure archiving if any transient log exists
                    self._invoke_helper_stop_for_archive()
                    self._cleanup()

        except Exception as e:
            self.log_received.emit(f"Could not check VPN status: {e}")
            self._cleanup(error=True)

    def _cleanup(self, error=False):
        self._status_timer.stop()
        self._log_timer.stop()
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
        self._connect_started_at = None
        self._connected_polls = 0

    # --- Internal: log tailing ---
    def _start_log_tail(self):
        try:
            # Reset pointers so we stream from start of fresh log
            self._log_file_pos = 0
            self._log_inode = None
            self._log_timer.start()
        except Exception:
            pass

    def _poll_log_file(self):
        log_path = C.LOG_FILE_PATH
        try:
            # Resolve current file status
            st = os.stat(log_path)
            inode = (st.st_dev, st.st_ino)
            # Handle rotation/symlink target change or truncation
            if self._log_inode != inode or self._log_file_pos > st.st_size:
                self._log_inode = inode
                self._log_file_pos = 0

            # Read any new data
            with open(log_path, "r", errors="ignore") as f:
                f.seek(self._log_file_pos)
                chunk = f.read(64 * 1024)
                if chunk:
                    self._log_file_pos = f.tell()
                    # Emit as-is; UI will append
                    self.log_received.emit(chunk.rstrip("\n"))
        except FileNotFoundError:
            # wait until helper creates the symlink/target
            return
        except PermissionError:
            # If unreadable (e.g., restrictive permissions), skip silently
            return
        except Exception:
            # Do not spam errors into UI; silent failure is fine here
            return

    def _invoke_helper_stop_for_archive(self):
        """Ask helper to run 'stop' to archive logs into Documents. Safe to call multiple times."""
        try:
            if not self._current_config_path:
                return
            command = [
                "sudo",
                "-n",
                str(C.HELPER_SCRIPT_PATH),
                "stop",
                self._current_config_path.name,
                str(C.LOG_FILE_PATH),
            ]
            subprocess.run(command, check=False, capture_output=True, text=True)
        except Exception:
            pass

    def _start_timers_if_possible(self):
        """Start status and log timers only if a Qt application exists.
        This avoids crashes in unit tests or headless environments without Q(Core)Application.
        """
        try:
            if QCoreApplication.instance() is None:
                return
            self._status_timer.start()
            # start log tailing from beginning of current log file
            self._start_log_tail()
        except Exception:
            # Never let timer issues break core logic
            pass
