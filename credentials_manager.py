import os
import json
import logging
from pathlib import Path
from cryptography.fernet import Fernet
import hashlib
import constants as C

logger = logging.getLogger(__name__)

class CredentialsManager:
    def __init__(self):
        self.config_dir = Path.home() / C.CONFIG_DIR_USER_PARENT / C.CRED_MANAGER_CONFIG_DIR_NAME
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.creds_file = self.config_dir / C.CRED_MANAGER_CREDS_FILENAME
        self.key = self._get_or_create_key()

    def _get_or_create_key(self):
        """Erstellt oder lädt den Verschlüsselungsschlüssel"""
        key_file = self.config_dir / C.CRED_MANAGER_KEY_FILENAME
        
        if key_file.exists():
            try:
                with open(key_file, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Fehler beim Laden des Schlüssels: {e}")
        
        # Neuen Schlüssel generieren
        key = Fernet.generate_key()
        try:
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Schlüssels: {e}")
        
        return key

    def _get_cipher(self):
        """Erstellt Cipher-Objekt für Ver-/Entschlüsselung"""
        return Fernet(self.key)

    def _get_config_key(self, config_path):
        """Generiert einen stabilen Schlüssel für den angegebenen Konfigurationspfad."""
        return hashlib.sha256(str(config_path).encode('utf-8')).hexdigest()

    def save_credentials(self, config_path, username, password):
        """Speichert Anmeldedaten verschlüsselt"""
        try:
            # Lade existierende Credentials
            all_creds = self._load_all_credentials()
            
            # Aktualisiere oder füge hinzu
            config_key = self._get_config_key(config_path)
            all_creds[config_key] = {
                'username': username,
                'password': password
            }
            
            # Verschlüsseln und speichern
            cipher = self._get_cipher()
            encrypted_data = cipher.encrypt(json.dumps(all_creds).encode())
            
            with open(self.creds_file, 'wb') as f:
                f.write(encrypted_data)
            
            os.chmod(self.creds_file, 0o600)
            logger.info(f"Credentials für Konfigurations-Hash {config_key} gespeichert")
            
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Credentials: {e}")

    def get_credentials(self, config_path):
        """Lädt gespeicherte Anmeldedaten"""
        try:
            all_creds = self._load_all_credentials()
            config_key = self._get_config_key(config_path)
            
            if config_key in all_creds:
                creds = all_creds[config_key]
                return creds['username'], creds['password']
                
        except Exception as e:
            logger.error(f"Fehler beim Laden der Credentials: {e}")
        
        return None, None

    def _load_all_credentials(self):
        """Lädt alle gespeicherten Credentials"""
        if not self.creds_file.exists():
            return {}
        
        try:
            cipher = self._get_cipher()
            with open(self.creds_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
            
        except Exception as e:
            logger.error(f"Fehler beim Entschlüsseln der Credentials: {e}")
            return {}

    def delete_credentials(self, config_path):
        """Löscht gespeicherte Anmeldedaten"""
        try:
            all_creds = self._load_all_credentials()
            config_key = self._get_config_key(config_path)
            
            if config_key in all_creds:
                del all_creds[config_key]
                
                if all_creds:
                    # Speichere verbleibende Credentials
                    cipher = self._get_cipher()
                    encrypted_data = cipher.encrypt(json.dumps(all_creds).encode())
                    with open(self.creds_file, 'wb') as f:
                        f.write(encrypted_data)
                else:
                    # Lösche Datei wenn keine Credentials mehr vorhanden
                    self.creds_file.unlink(missing_ok=True)
                
                logger.info(f"Credentials für Konfigurations-Hash {config_key} gelöscht")
                return True
                
        except Exception as e:
            logger.error(f"Fehler beim Löschen der Credentials: {e}")
        
        return False