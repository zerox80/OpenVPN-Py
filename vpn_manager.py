import os
import subprocess
import tempfile
import logging
import threading
import time
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
import shutil
import constants as C

logger = logging.getLogger(__name__)

class VPNManager(QObject):
    status_changed = pyqtSignal(str)
    output_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.process = None
        self.monitor_thread = None
        self.auth_file = None
        self.process_group_id = None
        
        self._lock = threading.Lock()
        self._state = C.VPN_STATE_DISCONNECTED
        self._shutdown_event = threading.Event()

    def get_state(self):
        with self._lock:
            return self._state

    def _set_state(self, new_state):
        with self._lock:
            if self._state == new_state:
                return
            self._state = new_state
            logger.info(f"VPN state changed to: {new_state}")
            self.status_changed.emit(new_state)

    def connect(self, config_path, username=None, password=None):
        """Stellt VPN-Verbindung über das sichere Helper-Skript her."""
        if self.get_state() != C.VPN_STATE_DISCONNECTED:
            logger.warning(f"Verbindung kann nicht hergestellt werden, aktueller Status: {self.get_state()}")
            return

        self._set_state(C.VPN_STATE_CONNECTING)
        self._shutdown_event.clear()

        try:
            self.auth_file = self._create_auth_file(username, password) if username and password else None
            cmd = self._build_command(config_path, self.auth_file)
            
            logger.info(f"Führe Befehl aus: {' '.join(cmd)}")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                start_new_session=True
            )
            
            self.process_group_id = os.getpgid(self.process.pid)
            logger.info(f"Prozess gestartet mit PID: {self.process.pid}, PGID: {self.process_group_id}")

            self.monitor_thread = threading.Thread(target=self._monitor_output, daemon=True)
            self.monitor_thread.start()

        except Exception as e:
            logger.error(f"Verbindungsfehler: {e}", exc_info=True)
            self._cleanup_after_error(str(e))

    def _build_command(self, config_path, auth_file):
        """Baut das OpenVPN-Kommando für das Helper-Skript."""
        cmd = ['sudo', C.HELPER_SCRIPT_PATH, 'start']
        cmd.extend(['--config', str(config_path), '--auth-nocache', '--verb', '3'])
        if auth_file:
            cmd.extend(['--auth-user-pass', str(auth_file)])

        # Erzwinge IPv4-Protokolle
        try:
            with open(config_path, 'r') as f:
                content = f.read().lower()
                if 'proto udp' in content: cmd.extend(['--proto', 'udp4'])
                elif 'proto tcp' in content: cmd.extend(['--proto', 'tcp4-client'])
        except Exception: pass

        cmd.extend([
            '--script-security', '2',
            '--up', C.UPDATE_RESOLV_CONF_PATH,
            '--down', C.UPDATE_RESOLV_CONF_PATH,
            '--down-pre'
        ])
        return cmd

    def disconnect(self):
        """Trennt die VPN-Verbindung sicher über das Helper-Skript."""
        if self.get_state() not in [C.VPN_STATE_CONNECTED, C.VPN_STATE_CONNECTING]:
            return
            
        logger.info("Trenne VPN-Verbindung...")
        self._set_state(C.VPN_STATE_DISCONNECTING)
        self._shutdown_event.set()

        try:
            if self.process_group_id:
                logger.info(f"Sende Stopp-Befehl an Helper für PGID {self.process_group_id}")
                cmd = ['sudo', C.HELPER_SCRIPT_PATH, 'stop', str(self.process_group_id)]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    logger.error(f"Helper-Skript meldet Fehler beim Stoppen: {result.stderr.strip()}")
            
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5.0)

        except Exception as e:
            logger.error(f"Fehler beim Trennen der Verbindung: {e}", exc_info=True)
        finally:
            self._cleanup()
            self._set_state(C.VPN_STATE_DISCONNECTED)
            logger.info("VPN-Verbindung getrennt.")

    def _monitor_output(self):
        """Überwacht die OpenVPN-Ausgabe in einem separaten Thread."""
        for line in iter(self.process.stdout.readline, ''):
            if self._shutdown_event.is_set(): break
            
            line = line.strip()
            if not line: continue
            self.output_received.emit(line)

            if "Initialization Sequence Completed" in line:
                self._set_state(C.VPN_STATE_CONNECTED)
            elif "AUTH_FAILED" in line:
                self._set_state(C.VPN_STATE_AUTH_FAILED)
                break
        
        self.process.wait()
        self._cleanup()
        # Setze finalen Status, falls nicht explizit getrennt wurde
        if not self._shutdown_event.is_set():
            self._set_state(C.VPN_STATE_DISCONNECTED)

    def _cleanup(self):
        """Räumt Ressourcen auf."""
        if self.auth_file:
            try: Path(self.auth_file).unlink(missing_ok=True)
            except Exception as e: logger.error(f"Fehler beim Löschen der Auth-Datei: {e}")
            self.auth_file = None
        if self.process:
            self.process.stdout.close()
            if self.process.poll() is None: self.process.kill()
            self.process = None
        self.process_group_id = None
        
    def _cleanup_after_error(self, error_message):
        """Spezifisches Cleanup bei Verbindungsfehler."""
        self._cleanup()
        self.error_occurred.emit(error_message)
        self._set_state(C.VPN_STATE_ERROR)

    def _create_auth_file(self, username, password):
        """Erstellt sichere temporäre Auth-Datei."""
        try:
            fd, path = tempfile.mkstemp(prefix='ovpn_auth_', text=True)
            with os.fdopen(fd, 'w') as f: f.write(f"{username}\n{password}")
            os.chmod(path, 0o600)
            return Path(path)
        except Exception as e:
            logger.error(f"Fehler beim Erstellen der Auth-Datei: {e}")
            raise

    def check_requirements(self):
        """Prüft, ob alle Voraussetzungen erfüllt sind."""
        issues = []
        if not shutil.which('openvpn'): issues.append("OpenVPN ist nicht installiert oder nicht im PATH.")
        if not shutil.which('sudo'): issues.append("sudo ist nicht installiert oder nicht im PATH.")
        if not Path(C.UPDATE_RESOLV_CONF_PATH).exists(): issues.append(f"DNS-Update-Skript fehlt: {C.UPDATE_RESOLV_CONF_PATH}")
        return issues