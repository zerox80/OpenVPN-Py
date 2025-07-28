# main.py
import sys
import logging
from PyQt6.QtWidgets import QApplication
import constants as C
from translation import install_translator
from main_window import MainWindow


def main():
    # Setup logging
    logging.basicConfig(level=logging.INFO, format=C.LOG_FORMAT)

    # Create the application instance
    app = QApplication(sys.argv)
    app.setApplicationName(C.APP_NAME)
    app.setApplicationVersion(C.VERSION)

    # The translator must be stored in a variable to avoid garbage collection
    translator = install_translator(C.APP_NAME)

    # Create and show the main window
    window = MainWindow()
    window.show()

    # Start the event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
