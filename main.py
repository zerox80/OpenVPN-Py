import sys
import os
import logging
import signal
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu,
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QLabel, QMessageBox, QFileDialog,
    QListWidgetItem, QGroupBox, QTextEdit, QSplitter
)
from PyQt6.QtGui import QIcon, QAction, QFont, QPixmap, QPainter, QBrush, QPen, QColor
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer, QSharedMemory

from config_manager import ConfigManager
from vpn_manager import VPNManager
from credentials_manager import CredentialsManager
from credentials_dialog import CredentialsDialog
import constants as C

# Logging konfigurieren
log_file_dir = Path.home() / Path(C.LOG_FILE_PATH).parent
log_file_dir.mkdir(parents=True, exist_ok=True)
log_file_full_path = Path.home() / C.LOG_FILE_PATH

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file_full_path)
    ]
)
logger = logging.getLogger(__name__)

class VPNWorker(QObject):
    """Worker für VPN-Operationen in separatem Thread"""
    finished = pyqtSignal()
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, vpn_manager, config_path, username, password):
        super().__init__()
        self.vpn_manager = vpn_manager
        self.config_path = config_path
        self.username = username
        self.password = password

    def connect(self):
        try:
            self.vpn_manager.connect(
                self.config_path,
                self.username,
                self.password
            )
        except Exception as e:
            logger.error(f"VPN-Verbindungsfehler: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.finished.emit()

    def disconnect(self):
        try:
            self.vpn_manager.disconnect()
        except Exception as e:
            logger.error(f"VPN-Trennungsfehler: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(C.APP_TITLE)
        self.setMinimumSize(C.MIN_WINDOW_WIDTH, C.MIN_WINDOW_HEIGHT)
        
        # Manager initialisieren
        self.config_manager = ConfigManager()
        self.vpn_manager = VPNManager()
        self.credentials_manager = CredentialsManager()
        
        # Status
        self.selected_config = None
        self.current_status = C.VPN_STATE_DISCONNECTED
        
        # UI Setup
        self.setup_ui()
        self.setup_tray()
        self.setup_signals()
        self.load_configurations()
        
        # Voraussetzungen prüfen
        self.check_requirements()
        
        # Status-Timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_connection_info)
        self.status_timer.start(C.STATUS_TIMER_INTERVAL_MS)

    def setup_ui(self):
        """Erstellt die Benutzeroberfläche"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Hauptlayout
        main_layout = QVBoxLayout(central_widget)
        
        # Splitter für Konfiguration und Log
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Oberer Bereich
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        
        # Linke Seite - Konfigurationsliste
        config_group = QGroupBox("VPN-Konfigurationen")
        config_layout = QVBoxLayout()
        
        self.config_list = QListWidget()
        self.config_list.setMinimumWidth(300)
        config_layout.addWidget(self.config_list)
        
        # Import-Button
        self.import_button = QPushButton("Konfiguration importieren...")
        self.import_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogNewFolder))
        config_layout.addWidget(self.import_button)
        
        config_group.setLayout(config_layout)
        top_layout.addWidget(config_group)
        
        # Rechte Seite - Status und Kontrollen
        control_group = QGroupBox("Verbindungskontrolle")
        control_layout = QVBoxLayout()
        
        # Status-Anzeige
        self.status_label = QLabel(f"{C.TRAY_STATUS_PREFIX}{C.STATUS_MSG_DISCONNECTED}")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                background-color: {C.COLOR_DISCONNECTED};
                color: {C.COLOR_WHITE};
            }}
        """)
        control_layout.addWidget(self.status_label)
        
        # Verbindungsinfo
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("padding: 5px;")
        control_layout.addWidget(self.info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.connect_button = QPushButton("Verbinden")
        self.connect_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogYesButton))
        self.connect_button.setMinimumHeight(40)
        
        self.disconnect_button = QPushButton("Trennen")
        self.disconnect_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogNoButton))
        self.disconnect_button.setMinimumHeight(40)
        self.disconnect_button.setEnabled(False)
        
        button_layout.addWidget(self.connect_button)
        button_layout.addWidget(self.disconnect_button)
        control_layout.addLayout(button_layout)
        
        # Credentials löschen
        self.clear_creds_button = QPushButton("Gespeicherte Anmeldedaten löschen")
        self.clear_creds_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_TrashIcon))
        control_layout.addWidget(self.clear_creds_button)
        
        control_layout.addStretch()
        control_group.setLayout(control_layout)
        top_layout.addWidget(control_group)
        
        splitter.addWidget(top_widget)
        
        # Unterer Bereich - Log
        log_group = QGroupBox("Verbindungsprotokoll")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(C.LOG_TEXT_MAX_HEIGHT)
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                font-family: monospace;
                font-size: 10px;
                background-color: {C.COLOR_LOG_BACKGROUND};
                color: {C.COLOR_LOG_TEXT};
            }}
        """)
        log_layout.addWidget(self.log_text)
        
        # Log-Kontrollen
        log_controls = QHBoxLayout()
        self.clear_log_button = QPushButton("Log löschen")
        self.clear_log_button.clicked.connect(self.log_text.clear)
        log_controls.addWidget(self.clear_log_button)
        log_controls.addStretch()
        log_layout.addLayout(log_controls)
        
        log_group.setLayout(log_layout)
        splitter.addWidget(log_group)
        
        main_layout.addWidget(splitter)
        
        # Statusbar
        self.statusBar().showMessage("Bereit")

    def setup_tray(self):
        """Erstellt das System-Tray-Icon"""
        self.tray_icon = QSystemTrayIcon(self)
        self.update_tray_icon(C.VPN_STATE_DISCONNECTED)
        
        # Tray-Menü
        self.tray_menu = QMenu()
        
        self.tray_status_action = self.tray_menu.addAction(f"{C.TRAY_STATUS_PREFIX}{C.STATUS_MSG_DISCONNECTED}")
        self.tray_status_action.setEnabled(False)
        self.tray_menu.addSeparator()
        
        self.tray_show_action = self.tray_menu.addAction("Fenster anzeigen")
        self.tray_show_action.triggered.connect(self.show_window)
        
        self.tray_menu.addSeparator()
        
        self.tray_connect_action = self.tray_menu.addAction("Verbinden")
        self.tray_disconnect_action = self.tray_menu.addAction("Trennen")
        self.tray_disconnect_action.setEnabled(False)
        
        self.tray_menu.addSeparator()
        
        self.tray_quit_action = self.tray_menu.addAction("Beenden")
        self.tray_quit_action.triggered.connect(self.quit_application)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def setup_signals(self):
        """Verbindet Signale mit Slots"""
        # UI-Signale
        self.connect_button.clicked.connect(self.connect_vpn)
        self.disconnect_button.clicked.connect(self.disconnect_vpn)
        self.import_button.clicked.connect(self.import_config)
        self.clear_creds_button.clicked.connect(self.clear_credentials)
        self.config_list.itemSelectionChanged.connect(self.config_selected)
        
        # Tray-Signale
        self.tray_connect_action.triggered.connect(self.connect_vpn)
        self.tray_disconnect_action.triggered.connect(self.disconnect_vpn)
        
        # VPN-Manager-Signale
        self.vpn_manager.status_changed.connect(self.handle_vpn_status)
        self.vpn_manager.output_received.connect(self.handle_vpn_output)
        self.vpn_manager.error_occurred.connect(self.handle_vpn_error)

    def load_configurations(self):
        """Lädt verfügbare VPN-Konfigurationen"""
        self.config_list.clear()
        try:
            configs = self.config_manager.get_configs()
            for config in configs:
                item = QListWidgetItem(config.name)
                item.setData(Qt.ItemDataRole.UserRole, config)
                self.config_list.addItem(item)
                
            if configs:
                self.config_list.setCurrentRow(0)
                
        except Exception as e:
            logger.error(f"Fehler beim Laden der Konfigurationen: {e}")
            self.show_error("Fehler beim Laden der Konfigurationen", str(e))

    def config_selected(self):
        """Wird aufgerufen wenn eine Konfiguration ausgewählt wird"""
        current_item = self.config_list.currentItem()
        if current_item:
            config = current_item.data(Qt.ItemDataRole.UserRole)
            self.selected_config = config
            self.statusBar().showMessage(f"Ausgewählt: {config.name}")

    def connect_vpn(self):
        """Stellt VPN-Verbindung her"""
        if not self.selected_config:
            self.show_error(C.ERROR_NO_CONFIG_SELECTED_TITLE, C.ERROR_NO_CONFIG_SELECTED_MSG)
            return

        # Credentials abrufen
        username, password = self.credentials_manager.get_credentials(self.selected_config.path)
        
        # Falls keine gespeichert, Dialog anzeigen
        if not username or not password:
            dialog = CredentialsDialog(self.selected_config.name, self)
            if dialog.exec():
                username, password, save = dialog.get_credentials()
                if save:
                    self.credentials_manager.save_credentials(
                        self.selected_config.path,
                        username,
                        password
                    )
            else:
                return

        # UI aktualisieren
        self.update_ui_state(C.VPN_STATE_CONNECTING)
        self.log_text.append(C.LOG_MSG_CONNECTING_TO.format(config_name=self.selected_config.name))

        # Verbindung in Thread starten
        self.vpn_thread = QThread()
        self.vpn_worker = VPNWorker(
            self.vpn_manager,
            str(self.selected_config.path),
            username,
            password
        )
        
        self.vpn_worker.moveToThread(self.vpn_thread)
        self.vpn_thread.started.connect(self.vpn_worker.connect)
        self.vpn_worker.finished.connect(self.vpn_thread.quit)
        self.vpn_worker.finished.connect(self.vpn_worker.deleteLater)
        self.vpn_thread.finished.connect(self.vpn_thread.deleteLater)
        
        self.vpn_thread.start()

    def disconnect_vpn(self):
        """Trennt VPN-Verbindung"""
        self.update_ui_state(C.VPN_STATE_DISCONNECTING)
        self.log_text.append(C.LOG_MSG_DISCONNECTING)
        
        # Trennung in Thread
        self.disconnect_thread = QThread()
        self.disconnect_worker = VPNWorker(
            self.vpn_manager,
            None, None, None
        )
        
        self.disconnect_worker.moveToThread(self.disconnect_thread)
        self.disconnect_thread.started.connect(self.disconnect_worker.disconnect)
        self.disconnect_worker.finished.connect(self.disconnect_thread.quit)
        self.disconnect_worker.finished.connect(self.disconnect_worker.deleteLater)
        self.disconnect_thread.finished.connect(self.disconnect_thread.deleteLater)
        
        self.disconnect_thread.start()

    def import_config(self):
        """Importiert neue VPN-Konfiguration"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            C.IMPORT_CONFIG_TITLE,
            str(Path.home()),
            C.IMPORT_CONFIG_FILTER
        )
        
        if file_path:
            try:
                new_config = self.config_manager.import_config(file_path)
                self.load_configurations()
                self.statusBar().showMessage(f"Konfiguration importiert: {new_config}")
                
                # Neue Konfiguration auswählen
                for i in range(self.config_list.count()):
                    item = self.config_list.item(i)
                    if item.text() == new_config:
                        self.config_list.setCurrentItem(item)
                        break
                        
            except Exception as e:
                logger.error(f"Fehler beim Import: {e}")
                self.show_error("Import fehlgeschlagen", str(e))

    def clear_credentials(self):
        """Löscht gespeicherte Anmeldedaten"""
        if not self.selected_config:
            self.show_error(C.ERROR_NO_CONFIG_SELECTED_TITLE, C.ERROR_NO_CONFIG_SELECTED_MSG)
            return
            
        reply = QMessageBox.question(
            self,
            C.CLEAR_CREDS_PROMPT_TITLE,
            C.CLEAR_CREDS_PROMPT_MSG.format(config_name=self.selected_config.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.credentials_manager.delete_credentials(self.selected_config.path):
                self.statusBar().showMessage(C.STATUS_BAR_CLEARED_CREDS)
            else:
                self.statusBar().showMessage(C.STATUS_BAR_NO_CREDS_FOUND)

    def handle_vpn_status(self, status):
        """Verarbeitet VPN-Statusänderungen"""
        logger.info(f"VPN-Status: {status}")
        self.current_status = status
        
        if status == C.VPN_STATE_CONNECTED:
            self.update_ui_state(C.VPN_STATE_CONNECTED)
            self.log_text.append(C.LOG_MSG_CONNECTED_SUCCESS)
            self.show_tray_message(C.TRAY_MSG_VPN_CONNECTED_TITLE, C.TRAY_MSG_VPN_CONNECTED_MSG.format(config_name=self.selected_config.name))
            
        elif status == C.VPN_STATE_DISCONNECTED:
            self.update_ui_state(C.VPN_STATE_DISCONNECTED)
            self.log_text.append(C.LOG_MSG_DISCONNECTED_SUCCESS)
            
        elif status == C.VPN_STATE_CONNECTING:
            self.update_ui_state(C.VPN_STATE_CONNECTING)
            
        elif status == C.VPN_STATE_DISCONNECTING:
            self.update_ui_state(C.VPN_STATE_DISCONNECTING)
            
        elif status == C.VPN_STATE_AUTH_FAILED:
            self.update_ui_state(C.VPN_STATE_ERROR)
            self.log_text.append(C.LOG_MSG_AUTH_FAILED)
            self.show_error(C.STATUS_MSG_AUTH_FAILED, C.LOG_MSG_AUTH_FAILED_DETAIL)
            
        elif status == C.VPN_STATE_CONNECTION_FAILED:
            self.update_ui_state(C.VPN_STATE_ERROR)
            self.log_text.append(C.LOG_MSG_CONNECTION_FAILED)
            
        elif status == C.VPN_STATE_RESOLVE_FAILED:
            self.update_ui_state(C.VPN_STATE_ERROR)
            self.log_text.append(C.LOG_MSG_RESOLVE_FAILED)
            
        elif status == C.VPN_STATE_FATAL_ERROR:
            self.update_ui_state(C.VPN_STATE_ERROR)
            self.log_text.append(C.LOG_MSG_FATAL_ERROR)

    def handle_vpn_output(self, output):
        """Zeigt VPN-Ausgabe im Log"""
        # Filtere unwichtige Meldungen
        if any(skip in output for skip in ["MANAGEMENT:", "PUSH:", "OPTIONS"]):
            return
            
        # Formatiere wichtige Meldungen
        if "Peer Connection Initiated" in output:
            self.log_text.append(C.LOG_MSG_PEER_CONNECTION_INITIATED)
        elif "routes" in output.lower():
            self.log_text.append(C.LOG_MSG_ROUTES_CONFIGURING)
        elif "TUN/TAP device" in output:
            self.log_text.append(C.LOG_MSG_TUN_TAP_CREATING)
        else:
            # Zeige andere Meldungen in grau
            self.log_text.append(f"  {output}")

    def handle_vpn_error(self, error):
        """Behandelt VPN-Fehler"""
        logger.error(f"VPN-Fehler: {error}")
        self.log_text.append(f"✗ Fehler: {error}")
        self.show_error("VPN-Fehler", error)

    def update_ui_state(self, state):
        """Aktualisiert UI basierend auf Verbindungsstatus"""
        states = {
            C.VPN_STATE_DISCONNECTED: {
                "status": C.STATUS_MSG_DISCONNECTED,
                "color": C.COLOR_DISCONNECTED,
                "connect": True,
                "disconnect": False
            },
            C.VPN_STATE_CONNECTING: {
                "status": C.STATUS_MSG_CONNECTING,
                "color": C.COLOR_CONNECTING,
                "connect": False,
                "disconnect": False
            },
            C.VPN_STATE_CONNECTED: {
                "status": C.STATUS_MSG_CONNECTED,
                "color": C.COLOR_CONNECTED,
                "connect": False,
                "disconnect": True
            },
            C.VPN_STATE_DISCONNECTING: {
                "status": C.STATUS_MSG_DISCONNECTING,
                "color": C.COLOR_DISCONNECTING,
                "connect": False,
                "disconnect": False
            },
            C.VPN_STATE_ERROR: {
                "status": C.STATUS_MSG_ERROR,
                "color": C.COLOR_ERROR,
                "connect": True,
                "disconnect": False
            }
        }
        
        state_info = states.get(state, states[C.VPN_STATE_DISCONNECTED])
        
        # Status-Label
        self.status_label.setText(f"{C.TRAY_STATUS_PREFIX}{state_info['status']}")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                background-color: {state_info['color']};
                color: {C.COLOR_WHITE};
            }}
        """)
        
        # Buttons
        self.connect_button.setEnabled(state_info['connect'])
        self.disconnect_button.setEnabled(state_info['disconnect'])
        
        # Tray
        self.tray_status_action.setText(f"{C.TRAY_STATUS_PREFIX}{state_info['status']}")
        self.tray_connect_action.setEnabled(state_info['connect'])
        self.tray_disconnect_action.setEnabled(state_info['disconnect'])
        self.update_tray_icon(state)
        
        # Statusbar
        if state == C.VPN_STATE_CONNECTED and self.selected_config:
            self.statusBar().showMessage(f"Verbunden mit {self.selected_config.name}")
        else:
            self.statusBar().showMessage(state_info['status'])

    def update_connection_info(self):
        """Aktualisiert Verbindungsinformationen"""
        if self.vpn_manager.is_connected():
            info = self.vpn_manager.get_connection_info()
            if info:
                self.info_label.setText(f"IP: {info['ip']} | Interface: {info['interface']}")
            else:
                self.info_label.setText("Verbunden")
        else:
            self.info_label.setText("")

    def update_tray_icon(self, state):
        """Aktualisiert das Tray-Icon basierend auf Status"""
        resources_dir = Path(__file__).parent / "resources"
        specific_icon_name = f"vpn-{state}.png"
        specific_icon_path = resources_dir / specific_icon_name
        default_icon_path = resources_dir / C.DEFAULT_VPN_ICON_FILENAME

        # Sicherstellen, dass Icons existieren, ggf. erstellen
        if not specific_icon_path.exists() or not default_icon_path.exists():
            self.create_default_icons()

        # Versuche spezifisches Icon zu laden, dann das Default-Icon
        final_icon_path = None
        if specific_icon_path.exists():
            final_icon_path = specific_icon_path
        elif default_icon_path.exists():
            final_icon_path = default_icon_path
        
        if final_icon_path:
            self.tray_icon.setIcon(QIcon(str(final_icon_path)))
        else:
            logger.error("Tray-Icon konnte nicht geladen oder erstellt werden. Fallback auf leeres Icon.")
            self.tray_icon.setIcon(QIcon())

    def create_default_icons(self):
        """Erstellt Standard-Icons wenn keine vorhanden"""
        resources_dir = Path(__file__).parent / "resources"
        resources_dir.mkdir(parents=True, exist_ok=True)
        
        # Erstelle einfache farbige Icons
        colors = {
            C.VPN_STATE_DISCONNECTED: C.COLOR_DISCONNECTED,
            C.VPN_STATE_CONNECTING: C.COLOR_CONNECTING,
            C.VPN_STATE_CONNECTED: C.COLOR_CONNECTED,
            C.VPN_STATE_DISCONNECTING: C.COLOR_DISCONNECTING,
            C.VPN_STATE_ERROR: C.COLOR_ERROR,
            "icon": C.COLOR_DEFAULT_ICON
        }
        
        for state_key, color_hex in colors.items():
            pixmap = QPixmap(C.DEFAULT_ICON_SIZE, C.DEFAULT_ICON_SIZE)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Zeichne Kreis
            painter.setBrush(QBrush(QColor(color_hex)))
            painter.setPen(QPen(Qt.GlobalColor.transparent))
            painter.drawEllipse(C.DEFAULT_ICON_ELLIPSE_RECT[0], C.DEFAULT_ICON_ELLIPSE_RECT[1], C.DEFAULT_ICON_ELLIPSE_RECT[2], C.DEFAULT_ICON_ELLIPSE_RECT[3])
            
            # Zeichne VPN-Text
            painter.setPen(QPen(QColor(C.COLOR_WHITE)))
            font = QFont()
            font.setPixelSize(C.DEFAULT_ICON_TEXT_PIXEL_SIZE)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, C.DEFAULT_ICON_TEXT)
            
            painter.end()
            
            icon_name = f"vpn-{state_key}.png" if state_key != "icon" else C.DEFAULT_VPN_ICON_FILENAME
            pixmap.save(str(resources_dir / icon_name))

    def show_window(self):
        """Zeigt das Hauptfenster"""
        self.show()
        self.raise_()
        self.activateWindow()

    def tray_activated(self, reason):
        """Behandelt Tray-Icon-Aktivierung"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def show_error(self, title, message):
        """Zeigt Fehlerdialog"""
        QMessageBox.critical(self, title, message)

    def show_tray_message(self, title, message):
        """Zeigt Tray-Benachrichtigung"""
        if self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                C.TRAY_MESSAGE_DURATION_MS
            )

    def check_requirements(self):
        """Prüft Systemvoraussetzungen"""
        issues = self.vpn_manager.check_requirements()
        
        if issues:
            message = C.CHECK_REQ_ISSUES_FOUND_INTRO
            message += "\n".join(f"• {issue}" for issue in issues)
            message += C.CHECK_REQ_ISSUES_SUFFIX
            
            QMessageBox.warning(self, C.CHECK_REQ_WARNING_TITLE, message)

    def closeEvent(self, event):
        """Behandelt das Schließen des Fensters"""
        if self.vpn_manager.is_connected():
            reply = QMessageBox.question(
                self,
                C.CLOSE_EVENT_VPN_ACTIVE_TITLE,
                C.CLOSE_EVENT_VPN_ACTIVE_MSG,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Minimieren in Tray
                event.ignore()
                self.hide()
                self.show_tray_message(
                    C.TRAY_MSG_MINIMIZED_TITLE,
                    C.TRAY_MSG_MINIMIZED_MSG
                )
                return
            elif reply == QMessageBox.StandardButton.No:
                # Beenden
                self.quit_application()
            else:
                # Abbrechen
                event.ignore()
                return
        
        event.accept()

    def quit_application(self):
        """Beendet die Anwendung sauber"""
        if self.vpn_manager.is_connected():
            reply = QMessageBox.question(
                self,
                C.QUIT_APP_VPN_DISCONNECT_PROMPT_TITLE,
                C.QUIT_APP_VPN_DISCONNECT_PROMPT_MSG,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.vpn_manager.disconnect()
                # Warte kurz auf Trennung
                QTimer.singleShot(C.VPN_WORKER_DISCONNECT_DELAY_MS, self._quit)
                return
        
        self._quit()

    def _quit(self):
        """Interne Quit-Funktion"""
        self.tray_icon.hide()
        QApplication.quit()


def main():
    """Hauptfunktion"""
    # Signal-Handler für sauberes Beenden
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication(sys.argv)
    app.setApplicationName(C.APP_TITLE)
    app.setOrganizationName(C.APP_TITLE)
    
    # Prüfe ob bereits eine Instanz läuft
    shared_memory = QSharedMemory(C.SHARED_MEMORY_KEY)
    if not shared_memory.create(1):
        QMessageBox.warning(
            None,
            C.MAIN_APP_ALREADY_RUNNING_TITLE,
            C.MAIN_APP_ALREADY_RUNNING_MSG
        )
        sys.exit(1)
    
    # Lade Anwendungs-Icon
    icon_path = Path(__file__).parent / "resources" / C.DEFAULT_VPN_ICON_FILENAME
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    # Erstelle und zeige Hauptfenster
    window = MainWindow()
    window.show()
    
    # Event-Loop starten
    sys.exit(app.exec())


if __name__ == "__main__":
    main()