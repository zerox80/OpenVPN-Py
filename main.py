#!/usr/bin/env python3

import sys
import subprocess
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTranslator, QLocale
from constants import APP_NAME, HELPER_PATH
from ui.control_panel import ControlPanel
from translation import load_translator

class MainApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName(APP_NAME)
        self.setQuitOnLastWindowClosed(False)

        self.translator = load_translator()
        if self.translator:
            self.installTranslator(self.translator)

        if not self.check_sudo_permissions():
            sys.exit(1)

        self.control_panel = ControlPanel()
        self.control_panel.show()

    def check_sudo_permissions(self):
        """
        Checks if the helper script can be run with passwordless sudo.
        If not, shows a detailed error message.
        """
        try:
            # Use sudo -n to run the command without prompting for a password.
            # If a password is required, it will fail.
            subprocess.run(
                ['sudo', '-n', HELPER_PATH, 'check'],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            title = self.tr("Sudo Permissions Required")
            intro = self.tr(
                "This application requires passwordless sudo access for its helper script '{helper_path}' to manage VPN connections."
            ).format(helper_path=HELPER_PATH)
            
            instructions_title = self.tr("How to fix this:")
            instructions = self.tr(
                "1. Open the sudoers file by running 'sudo visudo' in a terminal.\n"
                "2. Add the following line at the end of the file, replacing 'YOUR_USERNAME' with your actual username:\n\n"
                "   YOUR_USERNAME ALL=(ALL) NOPASSWD: {helper_path}\n\n"
                "3. Save the file and exit the editor."
            ).format(helper_path=HELPER_PATH)
            
            full_message = f"<p>{intro}</p>" \
                           f"<b>{instructions_title}</b>" \
                           f"<pre><code>{instructions}</code></pre>"
            
            QMessageBox.critical(None, title, full_message)
            return False

if __name__ == '__main__':
    app = MainApp(sys.argv)
    sys.exit(app.exec())