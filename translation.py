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
    language_code = locale.split("_")[0]
    translation_path = i18n_dir / f"{language_code}.qm"

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
