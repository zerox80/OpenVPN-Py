# /ui/control_panel.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QFont
import constants as C
from translation import _

class ControlPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Status Display
        status_label_title = QLabel(_("Status"))
        font = QFont()
        font.setBold(True)
        status_label_title.setFont(font)
        self.status_label = QLabel(_("Disconnected"))
        
        status_frame = QFrame()
        status_layout = QVBoxLayout(status_frame)
        status_layout.addWidget(status_label_title)
        status_layout.addWidget(self.status_label)
        status_frame.setFrameShape(QFrame.Shape.StyledPanel)

        # Control Buttons
        self.connect_button = QPushButton(_("Connect"))
        self.disconnect_button = QPushButton(_("Disconnect"))
        
        layout.addWidget(status_frame)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.disconnect_button)
        layout.addStretch(1)

        self.update_state(C.VpnState.NO_CONFIG_SELECTED)

    @pyqtSlot(C.VpnState)
    def update_state(self, state: C.VpnState):
        status_text = {
            C.VpnState.DISCONNECTED: _("Disconnected"),
            C.VpnState.CONNECTING: _("Connecting..."),
            C.VpnState.CONNECTED: _("Connected"),
            C.VpnState.DISCONNECTING: _("Disconnecting..."),
            C.VpnState.ERROR: _("Error"),
            C.VpnState.AUTH_FAILED: _("Authentication Failed"),
            C.VpnState.NO_CONFIG_SELECTED: _("Select a configuration")
        }
        self.status_label.setText(status_text.get(state, _("Unknown")))
        
        is_disconnected = state in [C.VpnState.DISCONNECTED, C.VpnState.ERROR, C.VpnState.AUTH_FAILED, C.VpnState.NO_CONFIG_SELECTED]
        is_connecting = state == C.VpnState.CONNECTING
        is_connected = state == C.VpnState.CONNECTED
        
        self.connect_button.setEnabled(is_disconnected)
        self.disconnect_button.setEnabled(is_connected)

        # Update button text for better UX
        if is_connecting:
            self.connect_button.setText(_("Connecting..."))
        else:
            self.connect_button.setText(_("Connect"))