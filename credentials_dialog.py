from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QLabel, QVBoxLayout, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from pathlib import Path
import constants as C

class CredentialsDialog(QDialog):
    def __init__(self, config_name=None, parent=None):
        super().__init__(parent)
        self.config_name = config_name
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(C.CRED_DIALOG_TITLE)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(C.CRED_DIALOG_MIN_WIDTH)
        
        # Icon setzen
        icon_path = Path(__file__).parent / "resources" / C.DEFAULT_VPN_ICON_FILENAME
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        layout = QVBoxLayout()
        
        # Info-Label
        if self.config_name:
            info_label = QLabel(f"{C.CRED_DIALOG_INFO_LABEL_PREFIX}{self.config_name}")
            info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(info_label)

        # Formular
        form_layout = QFormLayout()

        # Benutzername
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText(C.CRED_DIALOG_USERNAME_PLACEHOLDER)
        form_layout.addRow(QLabel(C.CRED_DIALOG_USERNAME_LABEL), self.username_edit)

        # Passwort
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText(C.CRED_DIALOG_PASSWORD_PLACEHOLDER)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow(QLabel(C.CRED_DIALOG_PASSWORD_LABEL), self.password_edit)

        # Passwort anzeigen
        self.show_password_cb = QCheckBox(C.CRED_DIALOG_SHOW_PASSWORD_CHECKBOX)
        self.show_password_cb.toggled.connect(self.toggle_password_visibility)
        form_layout.addRow("", self.show_password_cb)

        # Speichern-Option
        self.save_credentials_cb = QCheckBox(C.CRED_DIALOG_SAVE_CREDENTIALS_CHECKBOX)
        self.save_credentials_cb.setChecked(True)
        form_layout.addRow("", self.save_credentials_cb)

        layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)
        self.setLayout(layout)

        # Focus auf Benutzername
        self.username_edit.setFocus()

    def toggle_password_visibility(self, checked):
        if checked:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def validate_and_accept(self):
        """Validiert Eingaben vor dem Akzeptieren"""
        if not self.username_edit.text().strip():
            QMessageBox.warning(self, C.CRED_DIALOG_VALIDATION_ERROR_TITLE, C.CRED_DIALOG_VALIDATION_EMPTY_USERNAME_MSG)
            self.username_edit.setFocus()
            return
            
        if not self.password_edit.text():
            QMessageBox.warning(self, C.CRED_DIALOG_VALIDATION_ERROR_TITLE, C.CRED_DIALOG_VALIDATION_EMPTY_PASSWORD_MSG)
            self.password_edit.setFocus()
            return
            
        self.accept()

    def get_credentials(self):
        """Gibt die eingegebenen Anmeldedaten zurück"""
        return (
            self.username_edit.text().strip(),
            self.password_edit.text(),
            self.save_credentials_cb.isChecked()
        )