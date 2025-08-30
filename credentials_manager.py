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
    NoKeyringError = type("NoKeyringError", (Exception,), {})

import constants as C

logger = logging.getLogger(__name__)


class CredentialsManager:
    def __init__(self):
        self.keyring_available = keyring is not None
        if not self.keyring_available:
            logger.warning(
                "`keyring` library is not installed. "
                "Passwords will not be saved."
            )

    def _get_service_name(self, config_path: Path) -> str:
        """Create a stable keyring service name for the config path."""
        # Use a hash of the resolved path to ensure consistency and avoid
        # special characters.
        config_id = hashlib.sha256(
            str(config_path.resolve()).encode()
        ).hexdigest()
        return f"{C.APP_NAME}-{config_id}"

    def get_credentials(
        self, config_path: Path
    ) -> Tuple[Optional[str], Optional[str]]:
        """Retrieve username and password for the given config path."""
        if not self.keyring_available:
            return None, None

        service_name = self._get_service_name(config_path)
        try:
            username = keyring.get_password(service_name, "username")
            password = keyring.get_password(service_name, "password")
            if username is not None or password is not None:
                logger.info(f"Retrieved credentials for {config_path.name}")
            return username, password
        except NoKeyringError:
            logger.warning(
                "No keyring backend found. Cannot retrieve credentials."
            )
            self.keyring_available = False
            return None, None
        except Exception as e:
            logger.error(f"Failed to retrieve credentials: {e}", exc_info=True)
            return None, None

    def save_credentials(
        self, config_path: Path, username: str, password: str
    ) -> None:
        """Saves username and password to the keyring."""
        if not self.keyring_available:
            return

        service_name = self._get_service_name(config_path)
        try:
            keyring.set_password(service_name, "username", username or "")
            keyring.set_password(service_name, "password", password or "")
            logger.info(f"Saved credentials for {config_path.name}")
        except NoKeyringError:
            logger.warning(
                "No keyring backend found. Cannot save credentials."
            )
            self.keyring_available = False
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}", exc_info=True)

    def delete_credentials(self, config_path: Path) -> None:
        """Deletes credentials for a given config path from the keyring."""
        if not self.keyring_available:
            return

        service_name = self._get_service_name(config_path)
        try:
            # It's safe to try to delete even if they don't exist
            try:
                keyring.delete_password(service_name, "username")
            except Exception:
                pass  # May not exist
            try:
                keyring.delete_password(service_name, "password")
            except Exception:
                pass  # May not exist
            logger.info(f"Deleted credentials for {config_path.name}")
        except NoKeyringError:
            pass  # Nothing to delete
        except Exception as e:
            logger.error(f"Failed to delete credentials: {e}", exc_info=True)
