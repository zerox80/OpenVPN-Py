import sys
import subprocess  # <-- BEHOBEN: Fehlender Import hinzugefügt
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt6.QtGui import QIcon, QAction
from constants import VpnState, APP_ICON
from ui.config_list import ConfigList
from ui.control_panel import ControlPanel
from ui.log_viewer import LogViewer
from vpn_manager import VpnManager
from config_manager import ConfigManager
from translation import set_language, _
from main_window import MainWindow


class OpenVpnPy(MainWindow):
    """
    Main application class for OpenVPN-Py.
    """

    def __init__(self):
        super().__init__()
        set_language()

        self.config_manager = ConfigManager()
        self.vpn_manager = VpnManager()

        self.init_ui()
        self.create_tray_icon()
        self.connect_signals()
        self.check_sudo_permissions()

    def init_ui(self):
        """
        Initializes the user interface.
        """
        self.config_list = ConfigList(self.config_manager)
        self.control_panel = ControlPanel()
        self.log_viewer = LogViewer()

        self.add_widget_to_left_layout(self.config_list)
        self.add_widget_to_left_layout(self.control_panel)
        self.add_widget_to_right_layout(self.log_viewer)

    def create_tray_icon(self):
        """
        Creates the system tray icon and its context menu.
        """
        self.tray_icon = QSystemTrayIcon(self)
        self.update_tray_icon(VpnState.DISCONNECTED)

        show_action = QAction(_("Show"), self)
        quit_action = QAction(_("Quit"), self)
        show_action.triggered.connect(self.show)
        quit_action.triggered.connect(self.quit_app)

        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def connect_signals(self):
        """
        Connects signals from managers to the UI slots.
        """
        self.vpn_manager.state_changed.connect(self.update_ui_state)
        self.vpn_manager.log_received.connect(self.log_viewer.append_log)
        self.control_panel.connect_button.clicked.connect(self.toggle_connection)
        self.config_list.import_button.clicked.connect(self.import_config)
        self.config_list.delete_button.clicked.connect(self.delete_config)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

    def toggle_connection(self):
        """
        Toggles the VPN connection state.
        """
        if self.vpn_manager.state in [VpnState.DISCONNECTED, VpnState.ERROR]:
            config_name = self.config_list.get_selected_config()
            if config_name:
                self.vpn_manager.connect_vpn(config_name)
            else:
                QMessageBox.warning(self, _("Warning"), _("Please select a configuration to connect."))
        else:
            self.vpn_manager.disconnect_vpn()

    def import_config(self):
        """
        Handles the import of a new VPN configuration.
        """
        try:
            if self.config_manager.import_config():
                self.config_list.update_configs()
        except Exception as e:
            QMessageBox.critical(self, _("Error"), str(e))

    def delete_config(self):
        """
        Handles the deletion of a selected VPN configuration.
        """
        config_name = self.config_list.get_selected_config()
        if config_name:
            reply = QMessageBox.question(self, _("Confirm Deletion"),
                                           _("Are you sure you want to delete the configuration '{0}'?").format(
                                               config_name),
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.config_manager.delete_config(config_name)
                self.config_list.update_configs()
        else:
            QMessageBox.warning(self, _("Warning"), _("Please select a configuration to delete."))

    def update_ui_state(self, state: VpnState):
        """
        Updates the UI elements based on the VPN state.
        """
        self.control_panel.update_state(state)
        self.update_tray_icon(state)
        self.config_list.setDisabled(state == VpnState.CONNECTING or state == VpnState.CONNECTED)

    def update_tray_icon(self, state: VpnState):
        """
        Updates the tray icon based on the VPN state.
        """
        icon_path = APP_ICON.get(state, APP_ICON[VpnState.DISCONNECTED])
        self.tray_icon.setIcon(QIcon(icon_path))
        self.tray_icon.setToolTip(f"OpenVPN-Py: {state.value}")

    def on_tray_icon_activated(self, reason):
        """
        Handles activation of the tray icon.
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Left click
            self.show()

    def check_sudo_permissions(self):
        """
        Checks if the sudo permissions for the helper script are set up correctly.
        """
        try:
            result = subprocess.run(['sudo', '-n', 'openvpn-gui-helper.sh', 'check'], capture_output=True, text=True)
            if result.returncode != 0:
                QMessageBox.warning(self, _("Sudo Permission Check"),
                                      _("Warning: The application may not have the necessary sudo permissions to manage OpenVPN connections. Please run the install script again or configure sudoers manually."))
        except FileNotFoundError:
            QMessageBox.warning(self, _("Sudo Permission Check"),
                                  _("Warning: The 'openvpn-gui-helper.sh' script was not found or sudo is not installed. VPN connection management may fail."))

    def quit_app(self):
        """
        Ensures a clean exit of the application.
        """
        self.vpn_manager.disconnect_vpn()
        QApplication.instance().quit()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = OpenVpnPy()
    ex.show()
    sys.exit(app.exec())