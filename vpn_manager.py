import os
import subprocess
import signal
import tempfile
import logging
import threading
import time
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
import grp
import pwd
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
        self._connected = False
        self._connecting = False

    def connect(self, config_path, username=None, password=None):
        """Stellt VPN-Verbindung her"""
        if self.is_connected() or self._connecting:
            logger.warning("VPN bereits verbunden oder Verbindung läuft")
            return

        self._connecting = True
        self.status_changed.emit(C.VPN_STATE_CONNECTING)

        try:
            # Erstelle temporäre Auth-Datei
            if username and password:
                self.auth_file = self._create_auth_file(username, password)

            # Baue OpenVPN-Kommando
            cmd = self._build_command(config_path, self.auth_file)
            
            # Starte OpenVPN-Prozess
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                preexec_fn=os.setsid  # Neue Session für Prozessgruppe
            )

            # Starte Monitoring-Thread
            self.monitor_thread = threading.Thread(
                target=self._monitor_output,
                daemon=True
            )
            self.monitor_thread.start()

        except Exception as e:
            logger.error(f"Verbindungsfehler: {e}")
            self._cleanup()
            self._connecting = False
            self.error_occurred.emit(str(e))
            self.status_changed.emit(C.VPN_STATE_ERROR)

    def _create_auth_file(self, username, password):
        """Erstellt sichere temporäre Auth-Datei"""
        try:
            fd, path = tempfile.mkstemp(prefix='ovpn_auth_', suffix='.tmp')
            with os.fdopen(fd, 'w') as f:
                f.write(f"{username}\n{password}")
            os.chmod(path, 0o600)
            return path
        except Exception as e:
            logger.error(f"Fehler beim Erstellen der Auth-Datei: {e}")
            raise

    def _build_command(self, config_path, auth_file):
        """Baut das OpenVPN-Kommando"""
        cmd = [
            'pkexec',  # Polkit für Rechteverwaltung
            'openvpn',
            '--config', config_path,
            '--auth-nocache',
            '--verb', '3'  # Verbosity level
        ]

        if auth_file:
            cmd.extend(['--auth-user-pass', auth_file])

        # Zusätzliche Sicherheitsoptionen
        cmd.extend([
            '--script-security', '2',
            '--up', C.UPDATE_RESOLV_CONF_PATH,
            '--down', C.UPDATE_RESOLV_CONF_PATH,
            '--down-pre'
        ])

        return cmd

    def _monitor_output(self):
        """Überwacht die OpenVPN-Ausgabe"""
        try:
            for line in iter(self.process.stdout.readline, ''):
                if not line:
                    break
                    
                line = line.strip()
                self.output_received.emit(line)
                
                # Status-Erkennung
                if "Initialization Sequence Completed" in line:
                    self._connected = True
                    self._connecting = False
                    self.status_changed.emit(C.VPN_STATE_CONNECTED)
                    logger.info("VPN-Verbindung hergestellt")
                    
                elif "AUTH_FAILED" in line:
                    self._connecting = False
                    self.error_occurred.emit(C.STATUS_MSG_AUTH_FAILED)
                    self.status_changed.emit(C.VPN_STATE_AUTH_FAILED)
                    
                elif "Connection reset" in line or "Connection refused" in line:
                    self._connecting = False
                    self.error_occurred.emit(C.STATUS_MSG_CONNECTION_FAILED)
                    self.status_changed.emit(C.VPN_STATE_CONNECTION_FAILED)
                    
                elif "RESOLVE: Cannot resolve host address" in line:
                    self._connecting = False
                    self.error_occurred.emit(C.STATUS_MSG_RESOLVE_FAILED)
                    self.status_changed.emit(C.VPN_STATE_RESOLVE_FAILED)
                    
                elif "Exiting due to fatal error" in line:
                    self._connecting = False
                    self.error_occurred.emit(C.STATUS_MSG_FATAL_ERROR)
                    self.status_changed.emit(C.VPN_STATE_FATAL_ERROR)

            # Prozess beendet
            return_code = self.process.wait()
            
            if return_code != 0 and self._connected:
                logger.warning(f"OpenVPN beendet mit Code {return_code}")
                
            self._connected = False
            self._connecting = False
            self.status_changed.emit(C.VPN_STATE_DISCONNECTED)
            
        except Exception as e:
            logger.error(f"Fehler beim Monitoring: {e}")
            self._connected = False
            self._connecting = False
            self.error_occurred.emit(str(e))
            
        finally:
            self._cleanup()

    def disconnect(self):
        """Trennt die VPN-Verbindung"""
        if not self.process:
            return

        logger.info("Trenne VPN-Verbindung...")
        self.status_changed.emit(C.VPN_STATE_DISCONNECTING)

        try:
            # Sende SIGTERM an Prozessgruppe
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            
            # Warte auf sauberes Beenden (max 10 Sekunden)
            for _ in range(20):
                if self.process.poll() is not None:
                    break
                time.sleep(0.5)
            else:
                # Erzwinge Beenden mit SIGKILL
                logger.warning("Erzwinge Beenden des VPN-Prozesses")
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait()

        except ProcessLookupError:
            # Prozess bereits beendet
            pass
        except Exception as e:
            logger.error(f"Fehler beim Trennen: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self._cleanup()
            self._connected = False
            self._connecting = False
            self.status_changed.emit(C.VPN_STATE_DISCONNECTED)

    def _cleanup(self):
        """Räumt temporäre Dateien auf"""
        if self.auth_file and os.path.exists(self.auth_file):
            try:
                os.unlink(self.auth_file)
                logger.debug(f"Auth-Datei gelöscht: {self.auth_file}")
            except Exception as e:
                logger.error(f"Fehler beim Löschen der Auth-Datei: {e}")
            self.auth_file = None

        self.process = None

    def is_connected(self):
        """Prüft ob VPN verbunden ist"""
        return self._connected and self.process and self.process.poll() is None

    def is_connecting(self):
        """Prüft ob Verbindung aufgebaut wird"""
        return self._connecting

    def get_connection_info(self):
        """Gibt Verbindungsinformationen zurück"""
        if not self.is_connected():
            return None

        try:
            # Versuche IP-Adresse zu ermitteln
            result = subprocess.run(
                ['ip', 'addr', 'show', 'tun0'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                # Parse IP aus Output
                for line in result.stdout.split('\n'):
                    if 'inet ' in line:
                        ip = line.strip().split()[1].split('/')[0]
                        return {'ip': ip, 'interface': 'tun0'}
                        
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Verbindungsinformationen: {e}")
            
        return None

    def check_requirements(self):
        """Prüft ob alle Voraussetzungen erfüllt sind"""
        issues = []

        # Prüfe OpenVPN
        if shutil.which('openvpn') is None:
            issues.append("OpenVPN nicht installiert oder nicht im PATH")
            
        # Prüfe pkexec
        if shutil.which('pkexec') is None:
            issues.append("PolicyKit (pkexec) nicht installiert oder nicht im PATH")
            
        # Prüfe update-resolv-conf
        if not os.path.exists(C.UPDATE_RESOLV_CONF_PATH):
            issues.append(f"DNS-Update-Script fehlt ({C.UPDATE_RESOLV_CONF_PATH})")

        # Prüfe Gruppenmitgliedschaft
        try:
            user = pwd.getpwuid(os.getuid()).pw_name
            groups = [g.gr_name for g in grp.getgrall() if user in g.gr_mem]
            if 'openvpn' not in groups:
                issues.append(f"Benutzer {user} nicht in openvpn-Gruppe")
        except Exception:
            issues.append("Konnte Gruppenmitgliedschaft nicht prüfen")

        return issues