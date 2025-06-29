import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List
import logging

from constants import Constants as C

# Logger einrichten
logger = logging.getLogger(__name__)

# Eigene Exception-Klassen für eine bessere Fehlerbehandlung
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
        # Liste aller Verzeichnisse, in denen nach Konfigurationen gesucht wird
        self.config_dirs = [C.USER_CONFIGS_PATH] + C.SYSTEM_CONFIG_PATHS
        self._ensure_user_config_dir_exists()
        logger.info(f"ConfigManager initialisiert. Suchpfade: {self.config_dirs}")

    def _ensure_user_config_dir_exists(self):
        """Stellt sicher, dass das Benutzer-Konfigurationsverzeichnis existiert."""
        try:
            C.USER_CONFIGS_PATH.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Benutzer-Konfigurationsverzeichnis sichergestellt: {C.USER_CONFIGS_PATH}")
        except OSError as e:
            logger.error(f"Konnte Benutzer-Konfigurationsverzeichnis nicht erstellen: {e}")
            # Hier könnte man eine Exception werfen, wenn das Verzeichnis kritisch ist.

    def discover_configs(self) -> List[VpnConfig]:
        """
        Sucht in allen definierten Verzeichnissen nach .ovpn- und .conf-Dateien.
        """
        discovered_configs = []
        for config_dir in self.config_dirs:
            if not config_dir.is_dir():
                continue
            
            # Suche nach .ovpn und .conf Dateien
            for extension in ["*.ovpn", "*.conf"]:
                for config_file in config_dir.glob(extension):
                    config = VpnConfig(name=config_file.stem, path=config_file)
                    # Vermeide Duplikate, falls dieselbe Config in mehreren Pfaden liegt
                    if config.name not in [c.name for c in discovered_configs]:
                        discovered_configs.append(config)
        
        # Sortiere die Liste alphabetisch nach dem Namen
        discovered_configs.sort(key=lambda x: x.name)
        logger.info(f"{len(discovered_configs)} VPN-Konfigurationen gefunden.")
        return discovered_configs

    def import_config(self, source_path: str):
        """
        Kopiert eine ausgewählte Konfigurationsdatei in das Benutzerverzeichnis.
        """
        source = Path(source_path)
        if not source.is_file():
            raise ConfigImportError(f"Quelldatei nicht gefunden: {source_path}")

        destination = C.USER_CONFIGS_PATH / source.name
        if destination.exists():
            raise ConfigExistsError(f"Eine Konfiguration mit dem Namen '{source.name}' existiert bereits.")

        try:
            shutil.copy(source, destination)
            logger.info(f"Konfiguration von '{source}' nach '{destination}' importiert.")
        except IOError as e:
            logger.error(f"Fehler beim Kopieren der Konfigurationsdatei: {e}")
            raise ConfigImportError(f"Konnte Konfiguration nicht importieren: {e}")

    def delete_config(self, config: VpnConfig):
        """
        Löscht eine Konfigurationsdatei aus dem Benutzerverzeichnis.
        Löschen aus Systemverzeichnissen wird aus Sicherheitsgründen nicht unterstützt.
        """
        if config.path.parent != C.USER_CONFIGS_PATH:
            logger.warning(f"Löschen von System-Konfigurationen ist nicht erlaubt: {config.path}")
            raise PermissionError("Nur Konfigurationen im Benutzerverzeichnis können gelöscht werden.")
        
        try:
            config.path.unlink()
            logger.info(f"Konfiguration gelöscht: {config.path}")
        except FileNotFoundError:
            logger.warning(f"Zu löschende Konfiguration wurde nicht gefunden (möglicherweise bereits gelöscht): {config.path}")
        except OSError as e:
            logger.error(f"Fehler beim Löschen der Konfiguration '{config.path}': {e}")
            raise