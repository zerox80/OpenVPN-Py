# /ui/control_panel.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QFont
import constants as C

class ControlPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)

        # Status Display
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        status_layout = QVBoxLayout(status_frame)
        
        status_label_title = QLabel()
        font = QFont()
        font.setBold(True)
        status_label_title.setFont(font)
        status_label_title.setText(self.tr("Status")) # Use tr()
        
        self.status_label = QLabel()
        
        status_layout.addWidget(status_label_title)
        status_layout.addWidget(self.status_label)
        
        # Control Buttons
        self.connect_button = QPushButton()
        self.disconnect_button = QPushButton()
        
        layout.addWidget(status_frame)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.disconnect_button)
        layout.addStretch(1)

        self.update_state(C.VpnState.NO_CONFIG_SELECTED)

    @pyqtSlot(C.VpnState)
    def update_state(self, state: C.VpnState):
        status_map = {
            C.VpnState.DISCONNECTED: self.tr("Disconnected"),
            C.VpnState.CONNECTING: self.tr("Connecting..."),
            C.VpnState.CONNECTED: self.tr("Connected"),
            C.VpnState.DISCONNECTING: self.tr("Disconnecting..."),
            C.VpnState.ERROR: self.tr("Error"),
            C.VpnState.AUTH_FAILED: self.tr("Authentication Failed"),
            C.VpnState.NO_CONFIG_SELECTED: self.tr("Select a configuration")
        }
        self.status_label.setText(status_map.get(state, self.tr("Unknown")))

        # Update style based on state
        if state == C.VpnState.CONNECTED:
            self.status_label.setStyleSheet("color: green;")
        elif state == C.VpnState.ERROR or state == C.VpnState.AUTH_FAILED:
            self.status_label.setStyleSheet("color: red;")
        else:
            self.status_label.setStyleSheet("") # Reset to default color

        can_connect = state in [C.VpnState.DISCONNECTED, C.VpnState.ERROR, C.VpnState.AUTH_FAILED]
        has_selection = state != C.VpnState.NO_CONFIG_SELECTED
        
        self.connect_button.setEnabled(can_connect and has_selection)
        self.disconnect_button.setEnabled(state == C.VpnState.CONNECTED or state == C.VpnState.DISCONNECTING)

        # Update button text for better UX
        if state == C.VpnState.CONNECTING:
            self.connect_button.setText(self.tr("Connecting..."))
        else:
            self.connect_button.setText(self.tr("Connect"))

        if state == C.VpnState.DISCONNECTING:
            self.disconnect_button.setText(self.tr("Disconnecting..."))
        else:
            self.disconnect_button.setText(self.tr("Disconnect"))
