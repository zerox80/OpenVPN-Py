import os
import shutil
from pathlib import Path
import logging
import hashlib
import constants as C

logger = logging.getLogger(__name__)

class VPNConfig:
    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name
        self.hash = self.calculate_hash()
        self.is_valid = self.validate()

    def calculate_hash(self):
        try:
            with open(self.path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Fehler beim Berechnen des Hash für {self.path}: {e}")
            return ""

    def validate(self):
        """Validiert die OpenVPN-Konfiguration"""
        try:
            with open(self.path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                return all(keyword in content for keyword in C.CONFIG_VALIDATION_KEYWORDS)
        except Exception as e:
            logger.error(f"Fehler beim Validieren von {self.path}: {e}")
            return False

class ConfigManager:
    def __init__(self):
        # Define user config directory path first
        self.user_config_dir = Path.home() / C.CONFIG_DIR_USER_PARENT / C.CONFIG_DIR_USER_APP_SPECIFIC
        self._ensure_user_config_dir()
        self.config_dirs = self._get_config_dirs()

    def _get_config_dirs(self):
        """Ermittelt verfügbare Konfigurationsverzeichnisse"""
        dirs = []
        
        # System-weite Konfiguration
        system_dir = Path(C.CONFIG_DIR_SYSTEM)
        if system_dir.exists() and os.access(system_dir, os.R_OK):
            dirs.append(system_dir)
        
        # Benutzer-Konfiguration
        if self.user_config_dir not in dirs and self.user_config_dir.exists():
            dirs.append(self.user_config_dir)
        
        return dirs

    def _ensure_user_config_dir(self):
        """Stellt sicher, dass das Benutzer-Konfigurationsverzeichnis existiert"""
        try:
            self.user_config_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(self.user_config_dir, 0o700)
        except Exception as e:
            logger.error(f"Konnte Benutzer-Konfigurationsverzeichnis {self.user_config_dir} nicht erstellen: {e}")

    def get_configs(self):
        """Lädt alle verfügbaren VPN-Konfigurationen"""
        configs = []
        seen_names = set()
        
        for config_dir in self.config_dirs:
            try:
                for file in config_dir.iterdir():
                    if file.suffix.lower() in ('.ovpn', '.conf') and file.is_file():
                        config = VPNConfig(file)
                        if config.is_valid and config.name not in seen_names:
                            configs.append(config)
                            seen_names.add(config.name)
            except Exception as e:
                logger.error(f"Fehler beim Lesen von {config_dir}: {e}")
        
        return sorted(configs, key=lambda c: c.name.lower())

    def get_config_path(self, config_name):
        """Gibt den vollständigen Pfad einer Konfiguration zurück"""
        for config_dir in self.config_dirs:
            config_path = config_dir / config_name
            if config_path.exists():
                return str(config_path)
        raise FileNotFoundError(f"{C.CONFIG_GET_PATH_NOT_FOUND_MSG_PREFIX}{config_name}{C.CONFIG_GET_PATH_NOT_FOUND_MSG_SUFFIX}")

    def import_config(self, source_path):
        """Importiert eine neue VPN-Konfiguration"""
        source = Path(source_path)
        
        if not source.exists():
            raise FileNotFoundError(f"{C.CONFIG_IMPORT_FILE_NOT_FOUND_MSG_PREFIX}{source_path}")
        
        # Validierung
        config = VPNConfig(source)
        if not config.is_valid:
            raise ValueError(C.CONFIG_IMPORT_INVALID_CONFIG_MSG)
        
        # Zielverzeichnis
        dest_dir = self.user_config_dir
        
        # Eindeutigen Namen generieren falls nötig
        dest_name = source.name
        dest_path = dest_dir / dest_name
        counter = 1
        
        while dest_path.exists():
            name_parts = source.stem, source.suffix
            dest_name = f"{name_parts[0]}_{counter}{name_parts[1]}"
            dest_path = dest_dir / dest_name
            counter += 1
        
        # Kopieren und Berechtigungen setzen
        shutil.copy2(source, dest_path)
        os.chmod(dest_path, 0o600)
        
        logger.info(f"Konfiguration importiert: {dest_name}")
        return dest_name

    def delete_config(self, config_name):
        """Löscht eine Konfiguration (nur aus Benutzerverzeichnis)"""
        config_path = self.user_config_dir / config_name
        
        if config_path.exists():
            config_path.unlink()
            logger.info(f"Konfiguration gelöscht: {config_name}")
            return True
        
        return False