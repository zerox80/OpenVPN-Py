from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QHBoxLayout,
    QDialogButtonBox,
)

import constants as C


class CredentialsDialog(QDialog):
    def __init__(self, config_name, stored_credentials=None, parent=None):
        super().__init__(parent)
        self.username = ""
        self.password = ""
        self.save_credentials = False
        self.stored_credentials = stored_credentials or {}
        self.config_name = config_name

        self.setup_ui()
        self.populate_fields()

    def setup_ui(self):
        """Initialisiert die Benutzeroberfläche des Dialogs."""
        self.setWindowTitle(self.tr("Enter Credentials"))
        # [FIX] Korrekte Konstante für das Icon verwenden
        self.setWindowIcon(QIcon(str(C.ICON_PATH)))

        layout = QVBoxLayout(self)

        label_text = self.tr("Please enter your credentials for:")
        info_label = QLabel(f"{label_text} <b>{self.config_name}</b>")
        layout.addWidget(info_label)

        # Username
        layout.addWidget(QLabel(self.tr("Username:")))
        self.username_input = QLineEdit()
        layout.addWidget(self.username_input)

        # Password
        layout.addWidget(QLabel(self.tr("Password:")))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)

        # Show/Save options
        options_layout = QHBoxLayout()
        self.show_password_checkbox = QCheckBox(self.tr("Show Password"))
        self.show_password_checkbox.toggled.connect(self.toggle_password_visibility)
        options_layout.addWidget(self.show_password_checkbox)

        self.save_credentials_checkbox = QCheckBox(self.tr("Save for this configuration"))
        options_layout.addWidget(self.save_credentials_checkbox, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(options_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def populate_fields(self):
        """Füllt die Felder mit gespeicherten Anmeldeinformationen, falls vorhanden."""
        if self.stored_credentials:
            self.username_input.setText(self.stored_credentials.get("username", ""))
            self.password_input.setText(self.stored_credentials.get("password", ""))
            self.save_credentials_checkbox.setChecked(True)

    def toggle_password_visibility(self, checked):
        """Schaltet die Sichtbarkeit des Passworts um."""
        if checked:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

    def accept(self):
        """Wird aufgerufen, wenn der Benutzer auf OK klickt."""
        self.username = self.username_input.text().strip()
        self.password = self.password_input.text()
        self.save_credentials = self.save_credentials_checkbox.isChecked()
        super().accept()

    def get_credentials(self):
        """Gibt die vom Benutzer eingegebenen Daten zurück."""
        return self.username, self.password, self.save_credentials