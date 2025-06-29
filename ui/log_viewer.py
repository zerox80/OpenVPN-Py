from PyQt6.QtWidgets import QTextEdit, QSizePolicy
from PyQt6.QtCore import Qt

MAX_LOG_LINES = 200

class LogViewer(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #2b2b2b; color: #a9b7c6; font-family: Monospace;")

    def add_log(self, message: str):
        # Check if the scrollbar is at the bottom before appending text
        scrollbar = self.verticalScrollBar()
        scroll_at_bottom = scrollbar.value() >= scrollbar.maximum()

        # Efficiently remove old lines if max is reached
        doc = self.document()
        if doc.blockCount() > MAX_LOG_LINES:
            blocks_to_delete = doc.blockCount() - MAX_LOG_LINES
            cursor = self.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.NextBlock, cursor.MoveMode.KeepAnchor, blocks_to_delete)
            cursor.removeSelectedText()
            # A final clean block operation for safety
            cursor.deleteChar() 

        self.append(message)

        if scroll_at_bottom:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def clear_log(self):
        self.clear()