# /ui/log_viewer.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QFont
from translation import _

MAX_LOG_LINES = 200

class LogViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel(_("Logs"))
        font = QFont()
        font.setBold(True)
        title.setFont(font)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        layout.addWidget(title)
        layout.addWidget(self.log_text)

    @pyqtSlot(str)
    def add_log(self, message: str):
        # Check if scrollbar is at the bottom before adding new text
        scrollbar = self.log_text.verticalScrollBar()
        is_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 4)

        # Limit the number of lines to prevent memory issues
        doc = self.log_text.document()
        if doc.blockCount() > MAX_LOG_LINES:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar() # Remove the newline

        self.log_text.append(message.strip())
        
        # Scroll to bottom only if it was already at the bottom
        if is_at_bottom:
            scrollbar.setValue(scrollbar.maximum())

    @pyqtSlot()
    def clear_logs(self):
        self.log_text.clear()