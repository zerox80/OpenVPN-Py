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
        self._disconnecting = False
        self.process_group_id = None
        self._ipv6_disabled = False
        self.up_script = None
        self.down_script = None

    def connect(self, config_path, username=None, password=None):
        """Stellt VPN-Verbindung her"""
        if self.is_connected() or self._connecting:
            logger.warning("VPN bereits verbunden oder Verbindung läuft")
            return

        self._connecting = True
        self._disconnecting = False
        self.status_changed.emit(C.VPN_STATE_CONNECTING)

        try:
            # Erstelle temporäre Auth-Datei
            if username and password:
                self.auth_file = self._create_auth_file(username, password)

            # Erstelle Leak-Protect-Scripts
            self._create_leak_protect_scripts()

            # Baue OpenVPN-Kommando
            cmd = self._build_command(config_path, self.auth_file)
            
            # Starte OpenVPN-Prozess
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                start_new_session=True  # Wichtig für Prozessgruppe!
            )
            
            # Speichere Prozessgruppen-ID
            self.process_group_id = os.getpgid(self.process.pid)
            logger.info(f"Prozess gestartet mit PID: {self.process.pid}, PGID: {self.process_group_id}")

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

    def _create_leak_protect_scripts(self):
        """Creates up/down wrapper scripts for DNS update and IPv6 leak protection"""
        try:
            # Up script: DNS update + disable IPv6 via /proc
            up_fd, up_path = tempfile.mkstemp(prefix='ovpn_up_', suffix='.sh')
            with os.fdopen(up_fd, 'w') as f:
                f.write('#!/bin/sh\n')
                f.write(f'{C.UPDATE_RESOLV_CONF_PATH} "$@"\n')
                f.write('for f in /proc/sys/net/ipv6/conf/*/disable_ipv6; do echo 1 > "$f"; done\n')
            os.chmod(up_path, 0o700)
            # Down script: DNS update + re-enable IPv6 via /proc
            down_fd, down_path = tempfile.mkstemp(prefix='ovpn_down_', suffix='.sh')
            with os.fdopen(down_fd, 'w') as f:
                f.write('#!/bin/sh\n')
                f.write(f'{C.UPDATE_RESOLV_CONF_PATH} "$@"\n')
                f.write('for f in /proc/sys/net/ipv6/conf/*/disable_ipv6; do echo 0 > "$f"; done\n')
            os.chmod(down_path, 0o700)
            
            self.up_script = up_path
            self.down_script = down_path
        except Exception as e:
            logger.error(f"Fehler beim Erstellen der Leak-Protect-Scripts: {e}")

    def _build_command(self, config_path, auth_file):
        """Baut das OpenVPN-Kommando und erzwingt IPv4"""
        # Grundkommando
        cmd = ['sudo', 'openvpn']
        # Ermittele Protokoll aus Konfig und überschreibe auf IPv4 only
        try:
            with open(config_path, 'r') as f:
                for l in f:
                    if l.strip().startswith('proto '):
                        proto = l.strip().split()[1].lower()
                        if proto.startswith('udp'):
                            cmd.extend(['--proto', 'udp4'])
                        elif proto.startswith('tcp'):
                            cmd.extend(['--proto', 'tcp4'])
                        break
        except Exception:
            pass
        # Restliche Optionen
        cmd.extend([
            '--config', config_path,
            '--auth-nocache',
            '--verb', '3'  # Verbosity level
        ])

        if auth_file:
            cmd.extend(['--auth-user-pass', auth_file])

        # Zusätzliche Sicherheitsoptionen
        cmd.extend([
            '--script-security', '2',
            '--up', self.up_script or C.UPDATE_RESOLV_CONF_PATH,
            '--down', self.down_script or C.UPDATE_RESOLV_CONF_PATH,
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
                    self._disable_ipv6()
                    
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
            self._enable_ipv6()

    def disconnect(self):
        """Trennt die VPN-Verbindung ohne Passwortabfrage"""
        if not self.process or self._disconnecting:
            return

        logger.info("Trenne VPN-Verbindung...")
        self._disconnecting = True
        self.status_changed.emit(C.VPN_STATE_DISCONNECTING)

        try:
            # Sende Signal an gesamte Prozessgruppe
            if self.process_group_id:
                logger.info(f"Sende SIGTERM an Prozessgruppe {self.process_group_id} mittels sudo")
                term_result = subprocess.run(['sudo', 'kill', '-SIGTERM', '--', f'-{self.process_group_id}'], capture_output=True, text=True)
                if term_result.returncode != 0:
                    logger.warning(f"sudo kill SIGTERM fehlgeschlagen: {term_result.stderr.strip()}")

            else:
                logger.warning("Keine Prozessgruppen-ID verfügbar, sende SIGTERM an Prozess mittels sudo")
                if self.process:
                    term_result = subprocess.run(['sudo', 'kill', '-SIGTERM', '--', str(self.process.pid)], capture_output=True, text=True)
                    if term_result.returncode != 0:
                        logger.warning(f"sudo kill SIGTERM für PID {self.process.pid} fehlgeschlagen: {term_result.stderr.strip()}")
                else:
                    logger.warning("Kein Prozessobjekt zum Beenden vorhanden.")


            # Warte auf Beendigung mit Timeout
            wait_start = time.time()
            process_terminated = False
            while time.time() - wait_start < 5:  # Max 5 Sekunden warten
                if self.process is None or self.process.poll() is not None:
                    process_terminated = True
                    break
                time.sleep(0.2)
            
            if not process_terminated:
                logger.warning("Prozess reagierte nicht auf SIGTERM, sende SIGKILL mittels sudo")
                if self.process_group_id:
                    kill_result = subprocess.run(['sudo', 'kill', '-SIGKILL', '--', f'-{self.process_group_id}'], capture_output=True, text=True)
                    if kill_result.returncode != 0:
                        logger.error(f"sudo kill SIGKILL für PGID {self.process_group_id} fehlgeschlagen: {kill_result.stderr.strip()}")
                elif self.process:
                    kill_result = subprocess.run(['sudo', 'kill', '-SIGKILL', '--', str(self.process.pid)], capture_output=True, text=True)
                    if kill_result.returncode != 0:
                        logger.error(f"sudo kill SIGKILL für PID {self.process.pid} fehlgeschlagen: {kill_result.stderr.strip()}")
                else:
                    logger.warning("Kein Prozessobjekt für SIGKILL vorhanden.")
                
                # Kurze Wartezeit nach SIGKILL
                time.sleep(0.5)


            # Finale Überprüfung ohne Exception
            if self.process is None or self.process.poll() is None: # Check if process still exists and is running
                # If self.process is None, it might have been cleaned up by _monitor_output already
                # if it exited due to the signal before this check.
                # A more robust check might be needed if self.process can become None elsewhere during disconnect.
                # For now, if self.process is not None and poll() is None, it means it's still running.
                if self.process is not None:
                    logger.warning("Prozess konnte nicht beendet werden, auch nicht mit sudo kill.")
                    self.error_occurred.emit("OpenVPN-Prozess konnte nicht zuverlässig beendet werden.")
                # If self.process is None, assume it terminated.
                # This part needs careful review of how self.process is handled in _monitor_output on signal.
                # If _monitor_output cleans up and sets self.process to None, then this is fine.
                # However, if the process was killed by sudo, _monitor_output might not have a chance to do its full cleanup logic
                # for a graceful exit.

            else:
                logger.info("OpenVPN-Prozess erfolgreich beendet.")
                self._connected = False
                self.status_changed.emit(C.VPN_STATE_DISCONNECTED)
                logger.info("VPN-Verbindung erfolgreich getrennt")

        except ProcessLookupError:
            logger.info("Prozess bereits beendet")
            self._connected = False
            self.status_changed.emit(C.VPN_STATE_DISCONNECTED)
        except Exception as e:
            logger.error(f"Fehler beim Trennen: {e}")
            self.error_occurred.emit(f"Fehler beim Trennen: {e}")
        finally:
            self._cleanup()
            self._enable_ipv6()
            self._connecting = False
            self._disconnecting = False
            self.process_group_id = None

    def _cleanup(self):
        """Räumt temporäre Dateien auf"""
        if self.auth_file and os.path.exists(self.auth_file):
            try:
                os.unlink(self.auth_file)
                logger.debug(f"Auth-Datei gelöscht: {self.auth_file}")
            except Exception as e:
                logger.error(f"Fehler beim Löschen der Auth-Datei: {e}")
            self.auth_file = None
        # Entferne Leak-Protect-Scripts
        if self.up_script and os.path.exists(self.up_script):
            try:
                os.unlink(self.up_script)
                logger.debug(f"Up-Script gelöscht: {self.up_script}")
            except Exception:
                pass
            self.up_script = None
        if self.down_script and os.path.exists(self.down_script):
            try:
                os.unlink(self.down_script)
                logger.debug(f"Down-Script gelöscht: {self.down_script}")
            except Exception:
                pass
            self.down_script = None

        # Setze Prozess und Prozessgruppen-ID zurück
        self.process = None
        self.process_group_id = None

    def _disable_ipv6(self):
        """Deaktiviere IPv6, um Lecks zu verhindern"""
        try:
            # IPv6-Leak-Schutz via ip6tables: nur tun0 und lo erlauben
            rules = [
                ['sudo', 'ip6tables', '-A', 'OUTPUT', '-o', 'lo', '-j', 'ACCEPT', '-m', 'comment', '--comment', 'ovpn-leak-prot'],
                ['sudo', 'ip6tables', '-A', 'OUTPUT', '-o', 'tun0', '-j', 'ACCEPT', '-m', 'comment', '--comment', 'ovpn-leak-prot'],
                ['sudo', 'ip6tables', '-A', 'OUTPUT', '-j', 'DROP', '-m', 'comment', '--comment', 'ovpn-leak-prot']
            ]
            for cmd in rules:
                subprocess.run(cmd, check=True)
            self._ipv6_disabled = True
            logger.info("IPv6-Leak-Schutz aktiviert")
        except Exception as e:
            logger.error(f"Fehler beim Aktivieren des IPv6-Leak-Schutzes: {e}")

    def _enable_ipv6(self):
        """Aktiviere IPv6 nach VPN-Trennung wieder"""
        if not self._ipv6_disabled:
            return
        try:
            # Entferne IPv6-Leak-Schutz-Regeln
            rules = [
                ['sudo', 'ip6tables', '-D', 'OUTPUT', '-o', 'lo', '-j', 'ACCEPT', '-m', 'comment', '--comment', 'ovpn-leak-prot'],
                ['sudo', 'ip6tables', '-D', 'OUTPUT', '-o', 'tun0', '-j', 'ACCEPT', '-m', 'comment', '--comment', 'ovpn-leak-prot'],
                ['sudo', 'ip6tables', '-D', 'OUTPUT', '-j', 'DROP', '-m', 'comment', '--comment', 'ovpn-leak-prot']
            ]
            for cmd in rules:
                subprocess.run(cmd, check=False)
            self._ipv6_disabled = False
            logger.info("IPv6-Leak-Schutz deaktiviert")
        except Exception as e:
            logger.error(f"Fehler beim Deaktivieren des IPv6-Leak-Schutzes: {e}")

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
            
        # Prüfe sudo
        if shutil.which('sudo') is None:
            issues.append("sudo nicht installiert oder nicht im PATH")
            
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
