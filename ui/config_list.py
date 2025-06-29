# /ui/config_list.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListView, QPushButton, QHBoxLayout, QAbstractItemView
from PyQt6.QtCore import QStringListModel, pyqtSignal
from config_manager import VpnConfig

class ConfigList(QWidget):
    config_selected = pyqtSignal(str)
    import_config_requested = pyqtSignal()
    delete_config_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = QStringListModel(self)
        self.configs: list[VpnConfig] = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_view.selectionModel().selectionChanged.connect(self.on_selection_changed)

        button_layout = QHBoxLayout()
        import_button = QPushButton(self.tr("Import"))
        self.delete_button = QPushButton(self.tr("Delete"))
        
        import_button.clicked.connect(self.import_config_requested)
        self.delete_button.clicked.connect(self.on_delete_clicked)
        self.delete_button.setEnabled(False)

        button_layout.addWidget(import_button)
        button_layout.addWidget(self.delete_button)

        layout.addWidget(self.list_view)
        layout.addLayout(button_layout)
        
    def add_config(self, config: VpnConfig):
        self.configs.append(config)
        self.update_view()

    def clear_configs(self):
        self.configs.clear()
        self.update_view()

    def update_view(self):
        config_names = [c.name for c in self.configs]
        self.model.setStringList(config_names)
        self.delete_button.setEnabled(False)

    def on_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if not indexes:
            self.delete_button.setEnabled(False)
            return

        selected_config_name = self.model.stringList()[indexes[0].row()]
        selected_config = next((c for c in self.configs if c.name == selected_config_name), None)
        if selected_config:
            self.config_selected.emit(str(selected_config.path))
            self.delete_button.setEnabled(True)

    def on_delete_clicked(self):
        selected_indexes = self.list_view.selectedIndexes()
        if not selected_indexes:
            return
        
        selected_config_name = self.model.stringList()[selected_indexes[0].row()]
        selected_config = next((c for c in self.configs if c.name == selected_config_name), None)
        if selected_config:
            self.delete_config_requested.emit(str(selected_config.path))
