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
)
from PyQt6.QtCore import Qt, pyqtSignal
from typing import Optional
import constants as C
from ui.config_list import ConfigList
from ui.control_panel import ControlPanel
from ui.log_viewer import LogViewer
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

        # --- Manager Classes ---
        self.config_manager = ConfigManager()
        self.vpn_manager = VPNManager()
        self.credentials_manager = CredentialsManager()

        # --- UI Widgets ---
        self.config_list = ConfigList()
        self.control_panel = ControlPanel()
        self.log_viewer = LogViewer()

        # --- State Variables ---
        self.selected_config_path: Optional[str] = None

        self.init_ui()
        self.connect_signals()

        # Load initial configurations
        self.load_configs()
        self.control_panel.update_state(C.VpnState.NO_CONFIG_SELECTED)

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
        self.vpn_manager.log_received.connect(self.log_viewer.add_log)

    def load_configs(self):
        self.config_list.clear_configs()
        try:
            configs = self.config_manager.discover_configs()
            for config in configs:
                self.config_list.add_config(config)
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

        if username is None or password is None:
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
                self.load_configs()
                self.selected_config_path = None
                self.control_panel.update_state(C.VpnState.NO_CONFIG_SELECTED)
            except Exception as e:
                logger.error(f"Failed to delete config: {e}")
                self.show_error_message(self.tr("Deletion Failed"), str(e))

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
