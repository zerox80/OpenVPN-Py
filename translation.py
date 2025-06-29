import os
from PySide6.QtCore import QTranslator, QLocale, QLibraryInfo, QCoreApplication


def install_translator(app_name):
    translator = QTranslator()
    locale = QLocale.system().name()

    # Look for translation files in the resource system
    # The path should match the alias in the .qrc file
    if translator.load(f":/i18n/{app_name}_{locale}.qm"):
        QCoreApplication.installTranslator(translator)
    else:
        print(f"Warning: Could not load translation for locale {locale}")

    return translator
