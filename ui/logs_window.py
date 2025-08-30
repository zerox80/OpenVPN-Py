from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QApplication
from PyQt6.QtCore import Qt
from ui.log_viewer import LogViewer
import constants as C
from pathlib import Path


class LogsWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Logs"))
        self.setMinimumSize(700, 500)

        # Central layout
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Toolbar with Copy button
        toolbar = QHBoxLayout()
        self.copy_btn = QPushButton(self.tr("Copy All"))
        self.copy_btn.clicked.connect(self.copy_all)
        toolbar.addWidget(self.copy_btn)
        toolbar.addStretch(1)

        # Log viewer
        self.log_viewer = LogViewer()

        layout.addLayout(toolbar)
        layout.addWidget(self.log_viewer)

        # Load current log content if available
        self.load_from_file()

    def load_from_file(self):
        try:
            log_path: Path = C.LOG_FILE_PATH
            if log_path.exists():
                content = log_path.read_text(errors="ignore")
                self.log_viewer.setPlainText(content)
        except Exception:
            # ignore read errors, keep empty viewer
            pass

    def append_log(self, message: str):
        self.log_viewer.add_log(message)

    def copy_all(self):
        text = self.log_viewer.toPlainText()
        QApplication.clipboard().setText(text)
