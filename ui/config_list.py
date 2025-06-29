# /ui/config_list.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListView, QPushButton, QHBoxLayout, QAbstractItemView
from PyQt6.QtCore import QStringListModel, pyqtSignal
from config_manager import VpnConfig # Corrected import
from translation import _

class ConfigList(QWidget):
    config_selected = pyqtSignal(str)
    import_config_requested = pyqtSignal()
    delete_config_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = QStringListModel(self)
        self.configs = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_view.clicked.connect(self.on_config_clicked)

        button_layout = QHBoxLayout()
        import_button = QPushButton(_("Import"))
        self.delete_button = QPushButton(_("Delete"))
        
        import_button.clicked.connect(self.import_config_requested)
        self.delete_button.clicked.connect(self.on_delete_clicked)
        self.delete_button.setEnabled(False)

        button_layout.addWidget(import_button)
        button_layout.addWidget(self.delete_button)

        layout.addWidget(self.list_view)
        layout.addLayout(button_layout)

    def add_config(self, config: VpnConfig): # Corrected type hint
        self.configs.append(config)
        self.update_view()

    def remove_config(self, config_path: str):
        self.configs = [c for c in self.configs if c.path != config_path]
        self.update_view()

    def update_view(self):
        config_names = [c.name for c in self.configs]
        self.model.setStringList(config_names)
        self.delete_button.setEnabled(False)

    def on_config_clicked(self, index):
        selected_config_name = self.model.stringList()[index.row()]
        selected_config = next((c for c in self.configs if c.name == selected_config_name), None)
        if selected_config:
            self.config_selected.emit(selected_config.path)
            self.delete_button.setEnabled(True)

    def on_delete_clicked(self):
        selected_indexes = self.list_view.selectedIndexes()
        if not selected_indexes:
            return
        
        selected_config_name = self.model.stringList()[selected_indexes[0].row()]
        selected_config = next((c for c in self.configs if c.name == selected_config_name), None)
        if selected_config:
            self.delete_config_requested.emit(selected_config.path)