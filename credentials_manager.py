import json
import logging
import hashlib
import keyring
from keyring.errors import NoKeyringError
import constants as C

logger = logging.getLogger(__name__)

class CredentialsManager:
    def __init__(self):
        """Verwaltet Anmeldedaten sicher über den System-Schlüsselbund."""
        self.service_name = C.APP_TITLE
        try:
            # Testen, ob ein Backend verfügbar ist
            keyring.get_keyring()
            self.keyring_available = True
            logger.info("System-Schlüsselbund (Secret Service) erfolgreich initialisiert.")
        except NoKeyringError:
            self.keyring_available = False
            logger.warning("Kein System-Schlüsselbund gefunden. Das Speichern von Anmeldedaten ist nicht möglich.")

    def _get_config_key(self, config_path):
        """Generiert einen stabilen Schlüssel für den angegebenen Konfigurationspfad."""
        return hashlib.sha256(str(config_path).encode('utf-8')).hexdigest()

    def save_credentials(self, config_path, username, password):
        """Speichert Anmeldedaten im System-Schlüsselbund."""
        if not self.keyring_available:
            logger.error("Speichern nicht möglich, da kein Schlüsselbund verfügbar ist.")
            return

        try:
            config_key = self._get_config_key(config_path)
            # Speichere Username und Passwort als JSON-String
            credentials_json = json.dumps({'username': username, 'password': password})
            keyring.set_password(self.service_name, config_key, credentials_json)
            logger.info(f"Anmeldedaten für Konfiguration {config_path} sicher im Schlüsselbund gespeichert.")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Anmeldedaten im Schlüsselbund: {e}")

    def get_credentials(self, config_path):
        """Lädt gespeicherte Anmeldedaten aus dem System-Schlüsselbund."""
        if not self.keyring_available:
            return None, None
            
        try:
            config_key = self._get_config_key(config_path)
            credentials_json = keyring.get_password(self.service_name, config_key)
            
            if credentials_json:
                creds = json.loads(credentials_json)
                logger.info(f"Anmeldedaten für {config_path} aus dem Schlüsselbund geladen.")
                return creds.get('username'), creds.get('password')
                
        except Exception as e:
            logger.error(f"Fehler beim Laden der Anmeldedaten aus dem Schlüsselbund: {e}")
        
        return None, None

    def delete_credentials(self, config_path):
        """Löscht gespeicherte Anmeldedaten aus dem System-Schlüsselbund."""
        if not self.keyring_available:
            return False
            
        try:
            config_key = self._get_config_key(config_path)
            # Prüfen, ob Passwort existiert, bevor man es löscht
            if keyring.get_password(self.service_name, config_key) is not None:
                keyring.delete_password(self.service_name, config_key)
                logger.info(f"Anmeldedaten für {config_path} aus dem Schlüsselbund gelöscht.")
                return True
            else:
                logger.info(f"Keine Anmeldedaten für {config_path} im Schlüsselbund gefunden.")
                return False
        except Exception as e:
            logger.error(f"Fehler beim Löschen der Anmeldedaten aus dem Schlüsselbund: {e}")
        
        return False