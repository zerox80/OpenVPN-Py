# translation.py
import gettext
from pathlib import Path
from PyQt6.QtCore import QTranslator, QLibraryInfo, QCoreApplication

# Konfiguriere gettext für eine Fallback-Übersetzung, falls Qt-Übersetzung fehlschlägt
# Dies ist eine robuste Methode, um sicherzustellen, dass immer eine Übersetzung vorhanden ist.
APP_NAME = "openvpn-gui"
LOCALE_DIR = Path(__file__).parent / "i18n"

# Initialisiere eine "leere" Übersetzungsfunktion
_ = gettext.gettext


def install_translator(app: QCoreApplication):
    """Installiert den Qt-Translator für die Anwendung."""
    global _
    translator = QTranslator(app)
    
    # Versuche, die .qm-Datei für die Systemsprache zu laden
    # Hinweis: .ts-Dateien müssen mit `lrelease i18n/de.ts` zu .qm-Dateien kompiliert werden.
    # Das install.sh-Skript kann dies übernehmen.
    locale = QCoreApplication.organizationDomain() # Systemsprache
    if translator.load(f"{APP_NAME}_{locale}", str(LOCALE_DIR)):
        app.installTranslator(translator)
    
    # Definiere die globale Übersetzungsfunktion
    # QCoreApplication.translate ist die korrekte Methode für Qt-Anwendungen.
    # Der Kontext "translation" kann beliebig sein.
    def translate_func(text):
        return QCoreApplication.translate("translation", text)

    _ = translate_func