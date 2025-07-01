from PyQt6.QtWidgets import QTextEdit, QSizePolicy
from PyQt6.QtCore import Qt
import constants as C

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
        if doc.blockCount() > C.MAX_LOG_LINES_IN_VIEWER:
            blocks_to_delete = doc.blockCount() - C.MAX_LOG_LINES_IN_VIEWER
            cursor = self.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.NextBlock, cursor.MoveMode.KeepAnchor, blocks_to_delete)
            cursor.removeSelectedText()

        self.append(message)

        if scroll_at_bottom:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def clear_log(self):
        self.clear()
