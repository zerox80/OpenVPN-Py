import sys
from pathlib import Path

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QSystemTrayIcon, QMenu, QMessageBox)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QThread

import constants as C
from ui.config_list import ConfigList
from ui.control_panel import ControlPanel
from ui.log_viewer import LogViewer
from vpn_manager import VPNManager
from config_manager import ConfigManager
from credentials_dialog import CredentialsDialog
import credentials_manager
from translation import install_translator

class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.config_manager = ConfigManager()
        self.vpn_manager = VPNManager()

        self.init_ui()
        self.create_tray_icon()
        self.connect_signals()
        
        self.on_state_changed(C.VpnState.NO_CONFIG)
        self.config_list.load_configs()
        
        if not self.check_sudo_permissions():
            QMessageBox.critical(
                self,
                _("Permission Error"),
                _("Sudo permissions for the helper script are not configured correctly. "
                  "Please run the install.sh script or configure it manually.")
            )
            sys.exit(1)

    def init_ui(self):
        self.setWindowTitle(C.APP_NAME)
        self.setWindowIcon(QIcon("icon.svg"))
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.config_list = ConfigList(self.config_manager)
        self.control_panel = ControlPanel()
        self.log_viewer = LogViewer()

        layout.addWidget(self.config_list)
        layout.addWidget(self.control_panel)
        layout.addWidget(self.log_viewer)

    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.update_tray_icon(C.VpnState.DISCONNECTED)

        tray_menu = QMenu()
        self.show_action = QAction(_("Show"), self)
        self.show_action.triggered.connect(self.show)
        tray_menu.addAction(self.show_action)

        self.quit_action = QAction(_("Quit"), self)
        self.quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(self.quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def connect_signals(self):
        self.control_panel.connect_button.clicked.connect(self.connect_vpn)
        self.control_panel.disconnect_button.clicked.connect(self.disconnect_vpn)
        self.config_list.config_selected.connect(self.on_config_selected)

        self.vpn_manager.state_changed.connect(self.on_state_changed)
        self.vpn_manager.log_received.connect(self.log_viewer.add_log)
        self.vpn_manager.connection_terminated.connect(self.on_connection_terminated)
        
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

    def on_config_selected(self, config_path: str):
        self.current_config_path = config_path
        self.log_viewer.clear_log()
        self.log_viewer.add_log(_(f"Selected configuration: {config_path}"))
        if self.vpn_manager.state not in [C.VpnState.CONNECTING, C.VpnState.CONNECTED]:
            self.on_state_changed(C.VpnState.DISCONNECTED)

    def connect_vpn(self):
        if not hasattr(self, 'current_config_path') or not self.current_config_path:
            QMessageBox.warning(self, _("Warning"), _("Please select a configuration file first."))
            return
            
        if not Path(self.current_config_path).exists():
            QMessageBox.critical(self, _("Error"), _("The selected configuration file does not exist anymore."))
            self.config_list.load_configs() # Refresh the list
            return

        self.get_credentials_and_connect()

    def get_credentials_and_connect(self):
        username, password = credentials_manager.get_credentials(self.current_config_path)

        if username is None or password is None:
            keyring_available = credentials_manager.is_keyring_available()
            dialog = CredentialsDialog(self, keyring_available)
            if dialog.exec():
                username, password, save = dialog.get_credentials()
                if save:
                    credentials_manager.save_credentials(self.current_config_path, username, password)
            else:
                return  # User canceled

        self.vpn_manager.connect(self.current_config_path, username, password)
        
    def disconnect_vpn(self):
        self.vpn_manager.disconnect()

    def on_state_changed(self, state: C.VpnState):
        self.control_panel.update_state(state)
        self.config_list.setEnabled(state in [C.VpnState.DISCONNECTED, C.VpnState.ERROR, C.VpnState.NO_CONFIG])
        self.update_tray_icon(state)
        
        status_text = _(state.name.replace("_", " ").title())
        self.control_panel.set_status(status_text)
        
        if state == C.VpnState.NO_CONFIG:
            self.control_panel.set_status(_("Please Select a Configuration"))

    def on_connection_terminated(self):
        self.log_viewer.add_log(_("Connection terminated."))
    
    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()

    def update_tray_icon(self, state: C.VpnState):
        icon_map = {
            C.VpnState.DISCONNECTED: "icon_disconnected.svg",
            C.VpnState.CONNECTING: "icon_connecting.svg",
            C.VpnState.CONNECTED: "icon_connected.svg",
            C.VpnState.DISCONNECTING: "icon_connecting.svg",
            C.VpnState.ERROR: "icon_error.svg",
            C.VpnState.NO_CONFIG: "icon_disconnected.svg",
        }
        icon_path = icon_map.get(state, "icon_disconnected.svg")
        self.tray_icon.setIcon(QIcon(icon_path))
        self.tray_icon.setToolTip(f"{C.APP_NAME} - {_(state.name.replace('_', ' ').title())}")
    
    def check_sudo_permissions(self):
        try:
            # We test the helper script with a non-existent action to see if we can run it
            command = ["sudo", "-n", str(C.HELPER_SCRIPT_PATH), "test"]
            proc = subprocess.run(command, capture_output=True, text=True)
            # The script will exit with 1 on "Unknown action", which is what we expect.
            # If it fails with a password prompt (exit code not 1, stderr contains password prompt), permissions are wrong.
            return "password" not in proc.stderr.lower()
        except Exception:
            return False

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            _("Application Minimized"),
            _("OpenVPN-Py is still running in the background."),
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def quit_application(self):
        self.log_viewer.add_log(_("Quitting application..."))
        if self.vpn_manager.is_running:
            self.vpn_manager.disconnect()
        self.app.quit()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Install translator
    translator = install_translator(app)

    main_win = MainWindow(app)
    main_win.show()
    sys.exit(app.exec())