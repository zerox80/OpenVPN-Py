# config_manager.py
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List
import logging

import constants as C

logger = logging.getLogger(__name__)

class ConfigImportError(Exception):
    pass

class ConfigExistsError(ConfigImportError):
    pass

@dataclass
class VpnConfig:
    name: str
    path: Path

class ConfigManager:
    def __init__(self):
        # Search for configs in user dir and system dirs
        self.config_dirs = [C.USER_CONFIGS_DIR] + C.SYSTEM_CONFIG_DIRS
        logger.info(f"ConfigManager initialized. Search paths: {self.config_dirs}")

    def discover_configs(self) -> List[VpnConfig]:
        """Discovers .ovpn and .conf files in all defined directories."""
        discovered_configs = []
        seen_names = set()
        for config_dir in self.config_dirs:
            if not config_dir.is_dir():
                continue
            
            for extension in ["*.ovpn", "*.conf"]:
                for config_file in config_dir.glob(extension):
                    config = VpnConfig(name=config_file.name, path=config_file)
                    if config.name not in seen_names:
                        discovered_configs.append(config)
                        seen_names.add(config.name)
        
        discovered_configs.sort(key=lambda x: x.name)
        logger.info(f"{len(discovered_configs)} VPN configurations found.")
        return discovered_configs

    def import_config(self, source_path: str):
        """Copies a selected configuration file to the user's config directory."""
        source = Path(source_path)
        if not source.is_file():
            raise ConfigImportError(f"Source file not found: {source_path}")

        destination = C.USER_CONFIGS_DIR / source.name
        if destination.exists():
            raise ConfigExistsError(f"A configuration named '{source.name}' already exists.")

        try:
            shutil.copy(source, destination)
            logger.info(f"Configuration imported from '{source}' to '{destination}'.")
        except IOError as e:
            logger.error(f"Error copying configuration file: {e}")
            raise ConfigImportError(f"Could not import configuration: {e}")

    def delete_config(self, config: VpnConfig):
        """
        Deletes a configuration file from the user's directory.
        Deletion from system directories is not supported for security reasons.
        """
        # Ensure we are only deleting from the user's config directory
        if not str(config.path).startswith(str(C.USER_CONFIGS_DIR)):
            logger.warning(f"Attempt to delete non-user config denied: {config.path}")
            raise PermissionError("Only configurations in the user directory can be deleted.")
        
        try:
            config.path.unlink()
            logger.info(f"Configuration deleted: {config.path}")
        except FileNotFoundError:
            logger.warning(f"Config to be deleted was not found (already deleted?): {config.path}")
        except OSError as e:
            logger.error(f"Error deleting configuration '{config.path}': {e}")
            raise
