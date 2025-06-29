# translation.py
import logging
from PyQt6.QtCore import QTranslator, QLocale, QLibraryInfo, QCoreApplication

logger = logging.getLogger(__name__)

def install_translator(app_name: str) -> QTranslator:
    """
    Loads and installs a translator for the application.
    Note: For translations to work, UI elements must use self.tr("Text").
    """
    translator = QTranslator()
    locale = QLocale.system().name()  # e.g., "de_DE"

    # The .qm files should be compiled and placed alongside the code,
    # or in a resource file. Here we assume they are in an i18n subdirectory.
    # Note: Adjust the path if using a resource system (e.g., ":/i18n/")
    translation_path = f"i18n/{locale}.qm"
    
    if translator.load(translation_path):
        QCoreApplication.installTranslator(translator)
        logger.info(f"Successfully loaded translation for locale {locale}")
    else:
        logger.warning(f"Could not load translation file from path: {translation_path}")

    return translator
