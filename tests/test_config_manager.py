import os
from pathlib import Path
import shutil
import tempfile

from config_manager import ConfigManager, ConfigImportError, ConfigExistsError, VpnConfig
import constants as C


def test_discover_configs_empty(tmp_path):
    cm = ConfigManager()
    # Use temporary directories for search paths
    cm.config_dirs = [tmp_path]
    configs = cm.discover_configs()
    assert configs == []


def test_import_and_delete_config(tmp_path):
    cm = ConfigManager()
    cm.config_dirs = [tmp_path]
    dummy_conf = tmp_path / "sample.ovpn"
    dummy_conf.write_text("config")
    cm.import_config(str(dummy_conf))
    imported = C.USER_CONFIGS_DIR / dummy_conf.name
    assert imported.exists()
    # delete
    cm.delete_config(VpnConfig(dummy_conf.name, imported))
    assert not imported.exists()
