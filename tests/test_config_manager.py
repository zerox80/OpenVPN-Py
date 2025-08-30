import os
import sys
from pathlib import Path
import shutil
import tempfile
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import ConfigManager, ConfigImportError, ConfigExistsError, VpnConfig
import constants as C


def test_discover_configs_empty(tmp_path, monkeypatch):
    """Test discovering configs when no config files exist."""
    # Redirect user configs to a temp dir to avoid touching real home config
    user_cfg = tmp_path / "user_configs"
    user_cfg.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(C, "USER_CONFIGS_DIR", user_cfg)

    cm = ConfigManager()
    # Use temporary directories for search paths
    cm.config_dirs = [tmp_path]
    configs = cm.discover_configs()
    assert configs == []
    assert len(configs) == 0


def test_import_and_delete_config(tmp_path, monkeypatch):
    """Test importing and deleting a config file."""
    # Redirect user configs to a temp dir
    user_cfg = tmp_path / "user_configs"
    user_cfg.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(C, "USER_CONFIGS_DIR", user_cfg)

    cm = ConfigManager()
    cm.config_dirs = [user_cfg]
    
    # Create a dummy config file
    dummy_conf = tmp_path / "sample.ovpn"
    dummy_conf.write_text("# Sample OpenVPN config\nclient\ndev tun\n")
    
    # Import the config
    cm.import_config(str(dummy_conf))
    imported = C.USER_CONFIGS_DIR / dummy_conf.name
    assert imported.exists()
    assert imported.read_text() == dummy_conf.read_text()
    
    # Delete the config
    cm.delete_config(VpnConfig(dummy_conf.name, imported))
    assert not imported.exists()


def test_import_duplicate_config(tmp_path, monkeypatch):
    """Test that importing a duplicate config raises an error."""
    user_cfg = tmp_path / "user_configs"
    user_cfg.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(C, "USER_CONFIGS_DIR", user_cfg)

    cm = ConfigManager()
    dummy_conf = tmp_path / "sample.ovpn"
    dummy_conf.write_text("config")
    
    # First import should succeed
    cm.import_config(str(dummy_conf))
    
    # Second import should raise ConfigExistsError
    with pytest.raises(ConfigExistsError):
        cm.import_config(str(dummy_conf))


def test_discover_multiple_configs(tmp_path, monkeypatch):
    """Test discovering multiple config files."""
    user_cfg = tmp_path / "user_configs"
    user_cfg.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(C, "USER_CONFIGS_DIR", user_cfg)

    # Create multiple config files
    (user_cfg / "config1.ovpn").write_text("config1")
    (user_cfg / "config2.conf").write_text("config2")
    (user_cfg / "config3.ovpn").write_text("config3")
    
    cm = ConfigManager()
    cm.config_dirs = [user_cfg]
    configs = cm.discover_configs()
    
    assert len(configs) == 3
    config_names = [c.name for c in configs]
    assert "config1.ovpn" in config_names
    assert "config2.conf" in config_names
    assert "config3.ovpn" in config_names
    
    # Check that configs are sorted
    assert configs[0].name == "config1.ovpn"
    assert configs[1].name == "config2.conf"
    assert configs[2].name == "config3.ovpn"


def test_delete_system_config_denied(tmp_path, monkeypatch):
    """Test that deleting system configs is not allowed."""
    user_cfg = tmp_path / "user_configs"
    user_cfg.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(C, "USER_CONFIGS_DIR", user_cfg)
    
    # Create a fake system config
    system_cfg = tmp_path / "system_configs"
    system_cfg.mkdir(parents=True, exist_ok=True)
    system_conf = system_cfg / "system.ovpn"
    system_conf.write_text("system config")
    
    cm = ConfigManager()
    
    # Try to delete a system config (not in user dir)
    with pytest.raises(PermissionError):
        cm.delete_config(VpnConfig("system.ovpn", system_conf))


def test_import_nonexistent_file(tmp_path, monkeypatch):
    """Test that importing a non-existent file raises an error."""
    user_cfg = tmp_path / "user_configs"
    user_cfg.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(C, "USER_CONFIGS_DIR", user_cfg)
    
    cm = ConfigManager()
    
    with pytest.raises(ConfigImportError, match="Source file not found"):
        cm.import_config("/nonexistent/file.ovpn")
