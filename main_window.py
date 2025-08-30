# main_window.py
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QSplitter,
    QFileDialog,
    QMenu,
    QSystemTrayIcon,
)
from PyQt6.QtGui import QIcon, QAction, QDesktopServices
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QSettings
from typing import Optional
import constants as C
from ui.config_list import ConfigList
from ui.control_panel import ControlPanel
from ui.log_viewer import LogViewer
from ui.logs_window import LogsWindow
from vpn_manager import VPNManager
from config_manager import ConfigManager, ConfigExistsError
from credentials_manager import CredentialsManager
from credentials_dialog import CredentialsDialog

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(C.APP_NAME)
        self.setMinimumSize(800, 600)
        try:
            self.setWindowIcon(QIcon(str(self._icon_path())))
        except Exception:
            pass

        # --- Manager Classes ---
        self.config_manager = ConfigManager()
        self.vpn_manager = VPNManager()
        self.credentials_manager = CredentialsManager()

        # --- UI Widgets ---
        self.config_list = ConfigList()
        self.control_panel = ControlPanel()
        self.log_viewer = LogViewer()

        # Logs window (lazy-created)
        self.logs_window = None

        # --- State Variables ---
        self.selected_config_path: Optional[str] = None

        self.init_ui()
        self.connect_signals()
        self._init_tray()

        # Load initial configurations
        self.load_configs()
        self.control_panel.update_state(C.VpnState.NO_CONFIG_SELECTED)
        # Ensure tray reflects initial state
        try:
            self._update_tray_from_state(C.VpnState.NO_CONFIG_SELECTED)
        except Exception:
            pass

    def init_ui(self):
        # --- Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.addWidget(self.config_list)
        left_layout.addWidget(self.control_panel)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_pane)
        splitter.addWidget(self.log_viewer)
        splitter.setSizes([250, 550])

        main_layout.addWidget(splitter)

        # Menu bar
        menubar = self.menuBar()
        view_menu = menubar.addMenu(self.tr("View"))
        self.open_logs_action = view_menu.addAction(self.tr("Open Logs Window"))
        self.open_logs_folder_action = view_menu.addAction(self.tr("Open Logs Folder"))

    def connect_signals(self):
        # ConfigList signals
        self.config_list.config_selected.connect(self.on_config_selected)
        self.config_list.import_config_requested.connect(self.on_import_config)
        self.config_list.delete_config_requested.connect(self.on_delete_config)

        # ControlPanel signals
        self.control_panel.connect_button.clicked.connect(
            self.on_connect_clicked
        )
        self.control_panel.disconnect_button.clicked.connect(
            self.vpn_manager.disconnect
        )

        # VPNManager signals
        self.vpn_manager.state_changed.connect(self.control_panel.update_state)
        self.vpn_manager.state_changed.connect(self.on_state_changed)
        self.vpn_manager.log_received.connect(self.on_log_received)

        # Actions
        self.open_logs_action.triggered.connect(self.open_logs_window)
        self.open_logs_folder_action.triggered.connect(self.open_logs_folder)

    def load_configs(self):
        self.config_list.clear_configs()
        try:
            configs = self.config_manager.discover_configs()
            for config in configs:
                self.config_list.add_config(config)
            # Try to restore last selected config
            try:
                settings = QSettings(C.APP_NAME, C.APP_NAME)
                last = settings.value("last_config_path", None)
                if isinstance(last, str) and last:
                    if not self.config_list.select_config_by_path(last):
                        # Remove stale setting if file no longer exists in list
                        settings.remove("last_config_path")
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to discover configs: {e}")
            self.show_error_message(
                self.tr("Error Loading Configurations"),
                self.tr("Could not load VPN configurations: {0}").format(
                    str(e)
                ),
            )

    def on_config_selected(self, config_path: str):
        logger.info(f"Config selected: {config_path}")
        self.selected_config_path = config_path
        self.control_panel.update_state(C.VpnState.DISCONNECTED)
        try:
            settings = QSettings(C.APP_NAME, C.APP_NAME)
            settings.setValue("last_config_path", config_path)
        except Exception:
            pass
        # Ensure tray reflects that a config is now selected
        try:
            self._update_tray_from_state(C.VpnState.DISCONNECTED)
        except Exception:
            pass

    def on_connect_clicked(self):
        if not self.selected_config_path:
            self.show_error_message(
                self.tr("No Configuration Selected"),
                self.tr("Please select a VPN configuration from the list."),
            )
            return

        username, password = self.credentials_manager.get_credentials(
            Path(self.selected_config_path)
        )

        # Ensure both present; otherwise, prompt
        if not username or not password:
            dialog = CredentialsDialog(
                self,
                keyring_available=self.credentials_manager.keyring_available,
            )
            if dialog.exec():
                username, password, save_creds = dialog.get_credentials()
                if save_creds:
                    self.credentials_manager.save_credentials(
                        Path(self.selected_config_path), username, password
                    )
            else:
                # User cancelled credentials dialog
                return

        self.vpn_manager.connect(self.selected_config_path, username, password)

    def on_state_changed(self, state):
        # If authentication failed, offer to re-enter and update saved credentials
        try:
            if state == C.VpnState.AUTH_FAILED and self.selected_config_path:
                dialog = CredentialsDialog(
                    self,
                    keyring_available=self.credentials_manager.keyring_available,
                )
                dialog.setWindowTitle(self.tr("Authentication failed - enter correct VPN credentials"))
                if dialog.exec():
                    username, password, save_creds = dialog.get_credentials()
                    if save_creds:
                        self.credentials_manager.save_credentials(
                            Path(self.selected_config_path), username, password
                        )
                    # Try reconnecting immediately with new credentials
                    self.vpn_manager.connect(self.selected_config_path, username, password)
            # Update tray tooltip and actions for any state change
            self._update_tray_from_state(state)
        except Exception:
            pass

    def on_import_config(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Import OpenVPN Configuration"),
            "",
            self.tr("OpenVPN Files (*.ovpn *.conf);;All Files (*)"),
        )
        if file_path:
            try:
                self.config_manager.import_config(file_path)
                self.load_configs()
            except ConfigExistsError as e:
                self.show_error_message(self.tr("Import Failed"), str(e))
            except Exception as e:
                logger.error(f"Error importing config: {e}")
                self.show_error_message(
                    self.tr("Import Failed"),
                    self.tr("An unexpected error occurred: {0}").format(e),
                )

    def on_delete_config(self, config_path_str: str):
        config_path = Path(config_path_str)
        reply = QMessageBox.question(
            self,
            self.tr("Confirm Deletion"),
            self.tr(
                "Are you sure you want to delete the configuration '{0}'?\n"
                "This will also remove any saved credentials for it."
            ).format(config_path.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                config_to_delete = next(
                    c
                    for c in self.config_list.configs
                    if str(c.path) == config_path_str
                )
                self.config_manager.delete_config(config_to_delete)
                self.credentials_manager.delete_credentials(config_path)
                # Clear persisted selection if it matches the deleted config
                try:
                    settings = QSettings(C.APP_NAME, C.APP_NAME)
                    last = settings.value("last_config_path", None)
                    if isinstance(last, str) and last == config_path_str:
                        settings.remove("last_config_path")
                except Exception:
                    pass
                self.load_configs()
                self.selected_config_path = None
                self.control_panel.update_state(C.VpnState.NO_CONFIG_SELECTED)
                # Update tray to disable connect action and clear tooltip suffix
                try:
                    self._update_tray_from_state(C.VpnState.NO_CONFIG_SELECTED)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Failed to delete config: {e}")
                self.show_error_message(self.tr("Deletion Failed"), str(e))

    def open_logs_window(self):
        if self.logs_window is None:
            self.logs_window = LogsWindow(self)
        # Refresh content from file on show
        self.logs_window.load_from_file()
        self.logs_window.show()
        self.logs_window.raise_()
        self.logs_window.activateWindow()

    def open_logs_folder(self):
        try:
            path = self._logs_documents_dir()
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception as e:
            logger.error(f"Failed to open logs folder: {e}")
            self.show_error_message(self.tr("Open Logs Folder"), str(e))

    def on_log_received(self, message: str):
        # Always append to inline viewer
        self.log_viewer.add_log(message)
        # Mirror to logs window if open
        try:
            if self.logs_window is not None and self.logs_window.isVisible():
                self.logs_window.append_log(message)
        except Exception:
            pass

    def show_error_message(self, title, text):
        QMessageBox.critical(self, title, text)

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            self.tr("Confirm Quit"),
            self.tr(
                "Are you sure you want to quit? "
                "Any active VPN connection will be disconnected."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.vpn_manager.disconnect()
            event.accept()
        else:
            event.ignore()

    # --- Utilities and Tray ---
    def _icon_path(self) -> Path:
        try:
            return Path(__file__).parent / "icons" / "openvpn-py.png"
        except Exception:
            return Path("icons/openvpn-py.png")

    def _logs_documents_dir(self) -> Path:
        home = Path.home()
        candidates = [home / "Documents" / "OpenVPN-Py", home / "Dokumente" / "OpenVPN-Py"]
        for p in candidates:
            try:
                p.mkdir(parents=True, exist_ok=True)
                return p
            except Exception:
                continue
        # Fallback to app log dir
        try:
            C.LOG_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return C.LOG_DIR

    def _init_tray(self):
        try:
            self.tray = QSystemTrayIcon(QIcon(str(self._icon_path())), self)
            self.tray.setToolTip(self.tr("Disconnected"))

            menu = QMenu(self)
            self.tray_show_action = QAction(self.tr("Show/Hide Window"), self)
            self.tray_connect_action = QAction(self.tr("Connect"), self)
            self.tray_logs_action = QAction(self.tr("Open Logs Folder"), self)
            self.tray_quit_action = QAction(self.tr("Quit"), self)

            self.tray_show_action.triggered.connect(self._toggle_window_visibility)
            self.tray_connect_action.triggered.connect(self._tray_connect_or_disconnect)
            self.tray_logs_action.triggered.connect(self.open_logs_folder)
            self.tray_quit_action.triggered.connect(self.close)

            menu.addAction(self.tray_show_action)
            menu.addSeparator()
            menu.addAction(self.tray_connect_action)
            menu.addAction(self.tray_logs_action)
            menu.addSeparator()
            menu.addAction(self.tray_quit_action)

            self.tray.setContextMenu(menu)
            self.tray.show()
        except Exception:
            # Tray may not be available in some environments
            pass

    def _update_tray_from_state(self, state):
        try:
            if not hasattr(self, "tray") or self.tray is None:
                return
            # Tooltip
            tip = state.name.replace("_", " ").title()
            if self.selected_config_path:
                tip = f"{tip} - {Path(self.selected_config_path).name}"
            self.tray.setToolTip(tip)
            # Connect/Disconnect action label
            if state in (C.VpnState.CONNECTED, C.VpnState.CONNECTING):
                self.tray_connect_action.setText(self.tr("Disconnect"))
            else:
                self.tray_connect_action.setText(self.tr("Connect"))
            # Enable connect only if a config is selected, except when connected/connecting where action is always valid
            should_enable = (
                state in (C.VpnState.CONNECTED, C.VpnState.CONNECTING)
                or bool(self.selected_config_path)
            )
            self.tray_connect_action.setEnabled(should_enable)
        except Exception:
            pass

    def _toggle_window_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _tray_connect_or_disconnect(self):
        try:
            state = getattr(self.vpn_manager, "_state", C.VpnState.DISCONNECTED)
            if state in (C.VpnState.CONNECTED, C.VpnState.CONNECTING):
                self.vpn_manager.disconnect()
            else:
                self.on_connect_clicked()
        except Exception:
            pass
