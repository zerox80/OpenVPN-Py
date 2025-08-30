# translation.py
import logging
from pathlib import Path
from PyQt6.QtCore import QTranslator, QLocale, QCoreApplication

logger = logging.getLogger(__name__)


def install_translator(app_name: str) -> QTranslator:
    """
    Loads and installs a translator for the application.
    Note: For translations to work, UI elements must use self.tr("Text").
    """
    translator = QTranslator()
    locale = QLocale.system().name()  # e.g., "de_DE"

    # Build a robust path relative to this file's location
    i18n_dir = Path(__file__).parent.resolve() / "i18n"

    # Get short language code, e.g., "de" from "de_DE"
    language_code = locale.split("_")[0] if "_" in locale else locale
    translation_path = i18n_dir / f"{language_code}.qm"
    
    # Fallback to .ts file if .qm doesn't exist
    if not translation_path.exists():
        ts_path = i18n_dir / f"{language_code}.ts"
        if ts_path.exists():
            logger.info(f"Translation .qm file not found, .ts file exists at {ts_path}")
            # Return empty translator but don't fail
            return translator

    if translator.load(str(translation_path)):
        QCoreApplication.installTranslator(translator)
        logger.info(
            f"Successfully loaded translation for locale {locale} "
            f"from {translation_path}"
        )
    else:
        logger.warning(
            "Could not load translation file from path: " f"{translation_path}"
        )

    return translator
