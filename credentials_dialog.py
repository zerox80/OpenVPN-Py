from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QLabel, 
                             QPushButton, QCheckBox, QDialogButtonBox)
from PyQt6.QtCore import Qt

class CredentialsDialog(QDialog):
    def __init__(self, parent=None, keyring_available=True):
        super().__init__(parent)
        self.setWindowTitle(_("Enter Credentials"))
        self.setModal(True)

        layout = QVBoxLayout(self)

        self.username_label = QLabel(_("Username:"))
        self.username_input = QLineEdit()
        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)

        self.password_label = QLabel(_("Password:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)

        self.save_checkbox = QCheckBox(_("Save for this configuration"))
        self.save_checkbox.setChecked(keyring_available)
        self.save_checkbox.setEnabled(keyring_available)
        if not keyring_available:
            self.save_checkbox.setToolTip(_("Cannot save credentials. The 'keyring' library is not properly installed or configured."))
        layout.addWidget(self.save_checkbox)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_credentials(self):
        return self.username_input.text(), self.password_input.text(), self.save_checkbox.isChecked()