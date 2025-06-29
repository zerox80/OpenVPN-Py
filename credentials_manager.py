# credentials_manager.py
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple

try:
    import keyring
    from keyring.errors import NoKeyringError
except ImportError:
    keyring = None
    NoKeyringError = Exception

from constants import Constants as C

logger = logging.getLogger(__name__)


class CredentialsManager:
    def __init__(self):
        self.keyring_available = keyring is not None
        if not self.keyring_available:
            logger.warning("`keyring` library is not installed. Passwords will not be saved.")

    def _get_config_key(self, config_path: Path) -> str:
        """Creates a stable service name for keyring based on the config path."""
        # Use a hash to avoid storing raw paths in keyring service names
        # and to ensure a consistent length.
        return hashlib.sha256(str(config_path.resolve()).encode()).hexdigest()

    def get_credentials(self, config_path: Path) -> Tuple[Optional[str], Optional[str]]:
        """Retrieves username and password for a given config path from the keyring."""
        if not self.keyring_available:
            return None, None

        service_name = f"{C.APP_NAME}-{self._get_config_key(config_path)}"
        try:
            username = keyring.get_password(service_name, "username")
            password = keyring.get_password(service_name, "password")
            if username or password:
                logger.info(f"Retrieved credentials for {config_path.name}")
            return username, password
        except NoKeyringError:
            logger.warning("No keyring backend found. Cannot retrieve credentials.")
            self.keyring_available = False
            return None, None
        except Exception as e:
            logger.exception(f"Failed to retrieve credentials: {e}")
            return None, None

    def save_credentials(self, config_path: Path, username: str, password: str) -> None:
        """Saves username and password to the keyring."""
        if not self.keyring_available:
            return

        service_name = f"{C.APP_NAME}-{self._get_config_key(config_path)}"
        try:
            keyring.set_password(service_name, "username", username)
            keyring.set_password(service_name, "password", password)
            logger.info(f"Saved credentials for {config_path.name}")
        except NoKeyringError:
            logger.warning("No keyring backend found. Cannot save credentials.")
            self.keyring_available = False
        except Exception as e:
            logger.exception(f"Failed to save credentials: {e}")

    def delete_credentials(self, config_path: Path) -> None:
        """Deletes credentials for a given config path from the keyring."""
        if not self.keyring_available:
            return

        service_name = f"{C.APP_NAME}-{self._get_config_key(config_path)}"
        try:
            keyring.delete_password(service_name, "username")
            keyring.delete_password(service_name, "password")
            logger.info(f"Deleted credentials for {config_path.name}")
        except NoKeyringError:
            pass  # Nothing to delete
        except Exception as e:
            logger.exception(f"Failed to delete credentials: {e}")