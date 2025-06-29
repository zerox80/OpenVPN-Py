# /main.py

import sys
import os
import logging
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                             QSystemTrayIcon, QMenu, QMessageBox, QFileDialog,
                             QSplitter)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QThread, pyqtSlot

import constants as C
from ui.config_list import ConfigList
from ui.control_panel import ControlPanel
from ui.log_viewer import LogViewer
from config_manager import ConfigManager, ConfigExistsError, ConfigImportError
from vpn_manager import VPNManager
from credentials_manager import CredentialsManager
from translation import set_language, _

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager(C.CONFIG_DIR)
        self.credentials_manager = CredentialsManager()
        self.init_ui()
        self.init_vpn_manager_thread()
        self.init_tray_icon()
        self.load_configs()
        self.check_sudo_permissions()
        
        # Initial state
        self.on_state_changed(C.VpnState.NO_CONFIG_SELECTED)

    def init_ui(self):
        self.setWindowTitle(C.APP_NAME)
        self.setWindowIcon(QIcon.fromTheme("network-vpn", QIcon(str(C.UI_DIR / "icon.png"))))
        self.setGeometry(100, 100, 800, 600)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        splitter = QSplitter()
        main_layout.addWidget(splitter)
        
        # Left side (configs)
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        self.config_list = ConfigList()
        self.control_panel = ControlPanel()
        left_layout.addWidget(self.config_list)
        left_layout.addWidget(self.control_panel)

        # Right side (logs)
        self.log_viewer = LogViewer()

        splitter.addWidget(left_pane)
        splitter.addWidget(self.log_viewer)
        splitter.setSizes([250, 550])

        # Connect signals
        self.config_list.import_config_requested.connect(self.import_config)
        self.config_list.config_selected.connect(self.on_config_selected)
        self.config_list.delete_config_requested.connect(self.delete_config)
        self.control_panel.connect_button.clicked.connect(self.connect_vpn)
        self.control_panel.disconnect_button.clicked.connect(self.disconnect_vpn)
        
    def init_vpn_manager_thread(self):
        self.vpn_thread = QThread()
        self.vpn_manager = VPNManager(self.credentials_manager)
        self.vpn_manager.moveToThread(self.vpn_thread)

        # Connect signals between threads
        self.vpn_manager.state_changed.connect(self.on_state_changed)
        self.vpn_manager.log_received.connect(self.log_viewer.add_log)
        self.vpn_manager.connection_terminated.connect(self.on_connection_terminated)
        
        self.vpn_thread.start()

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.update_tray_icon(C.VpnState.DISCONNECTED)
        self.tray_icon.setVisible(True)

        tray_menu = QMenu()
        show_action = QAction(_("Show"), self)
        show_action.triggered.connect(self.show)
        quit_action = QAction(_("Quit"), self)
        quit_action.triggered.connect(self.quit_app)
        
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

    def load_configs(self):
        try:
            configs = self.config_manager.load_configs()
            for config in configs:
                self.config_list.add_config(config)
        except Exception as e:
            QMessageBox.critical(self, _("Error"), _("Could not load configurations: {}").format(e))
            
    def on_config_selected(self, config_path: str):
        self.current_config_path = config_path
        self.log_viewer.add_log(f"Selected: {os.path.basename(config_path)}")
        self.on_state_changed(self.vpn_manager.state) # Update UI based on current state

    @pyqtSlot(C.VpnState)
    def on_state_changed(self, state: C.VpnState):
        self.control_panel.update_state(state)
        self.update_tray_icon(state)
        # If no config is selected, the connect button should be disabled
        if not hasattr(self, 'current_config_path') or not self.current_config_path:
             self.control_panel.connect_button.setEnabled(False)
             self.control_panel.status_label.setText(_("Select a configuration"))

    def on_connection_terminated(self):
        # This can be used for cleanup after the connection process fully ends
        pass

    def connect_vpn(self):
        if not hasattr(self, 'current_config_path') or not self.current_config_path:
            QMessageBox.warning(self, _("Warning"), _("Please select a configuration file first."))
            return
        # This will trigger the connect method on the VPNManager in its thread
        self.vpn_manager.connect(self.current_config_path)

    def disconnect_vpn(self):
        # This will trigger the disconnect method on the VPNManager
        self.vpn_manager.disconnect()

    def import_config(self):
        file_path, _ = QFileDialog.getOpenFileName(self, _("Import OpenVPN Configuration"), "", "OpenVPN Files (*.ovpn)")
        if file_path:
            try:
                new_config = self.config_manager.import_config(file_path)
                self.config_list.add_config(new_config)
                self.log_viewer.add_log(_("Successfully imported {}").format(new_config.name))
            except ConfigExistsError:
                QMessageBox.warning(self, _("Warning"), _("This configuration has already been imported."))
            except ConfigImportError as e:
                QMessageBox.critical(self, _("Error"), _("Failed to import configuration: {}").format(e))

    def delete_config(self, config_path: str):
        reply = QMessageBox.question(self, _("Confirm Delete"), 
                                     _("Are you sure you want to delete {}?").format(os.path.basename(config_path)))
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.config_manager.delete_config(config_path)
                self.config_list.remove_config(config_path)
                self.log_viewer.add_log(_("Configuration deleted: {}").format(os.path.basename(config_path)))
                self.current_config_path = None
                self.on_state_changed(C.VpnState.NO_CONFIG_SELECTED)
            except Exception as e:
                 QMessageBox.critical(self, _("Error"), _("Failed to delete configuration: {}").format(e))

    def update_tray_icon(self, state: C.VpnState):
        if state == C.VpnState.CONNECTED:
            self.tray_icon.setIcon(QIcon.fromTheme("network-vpn", QIcon(str(C.UI_DIR / "icon-connected.png"))))
            self.tray_icon.setToolTip(_("Connected"))
        else:
            self.tray_icon.setIcon(QIcon.fromTheme("network-vpn-offline", QIcon(str(C.UI_DIR / "icon.png"))))
            self.tray_icon.setToolTip(_("Disconnected"))

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger: # Left click
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()

    def check_sudo_permissions(self):
        """Checks if the helper script can be run with sudo without a password."""
        try:
            # Use -n (non-interactive) to check if a password is required
            result = subprocess.run(
                ["sudo", "-n", str(C.HELPER_SCRIPT_PATH)],
                capture_output=True, text=True
            )
            if "a password is required" in result.stderr:
                QMessageBox.critical(
                    self, _("Permission Error"),
                    _("Sudo requires a password for the helper script. Please run the install.sh script to set up passwordless access.")
                )
                self.control_panel.connect_button.setEnabled(False)
        except FileNotFoundError:
             QMessageBox.critical(self, _("Error"), _("Helper script not found at {}").format(C.HELPER_SCRIPT_PATH))
             self.control_panel.connect_button.setEnabled(False)

    def closeEvent(self, event):
        if self.vpn_manager.state == C.VpnState.CONNECTED:
            reply = QMessageBox.question(self, _("Confirm Action"), 
                                         _("A VPN connection is active. Quitting will disconnect it. Minimize to tray instead?"),
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Yes)

            if reply == QMessageBox.StandardButton.Yes:
                self.hide()
                event.ignore()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
            else: # No
                self.quit_app()
        else:
            self.hide()
            event.ignore()
            
    def quit_app(self):
        self.log_viewer.add_log("Quitting application...")
        if self.vpn_manager.is_running:
            self.vpn_manager.disconnect()
        self.vpn_thread.quit()
        self.vpn_thread.wait()
        QApplication.instance().quit()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Set SUDO_ASKPASS for graphical sudo prompts if needed
    # This points to a script that can show a password dialog
    # For now, we rely on passwordless sudo setup by install.sh
    # os.environ["SUDO_ASKPASS"] = str(C.SCRIPTS_DIR / "askpass.sh")

    app = QApplication(sys.argv)
    set_language(app)
    
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())