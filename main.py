import sys
from PySide6.QtWidgets import QApplication
from constants import APP_NAME
from translation import install_translator
from ui.control_panel import ControlPanel


class MainApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName(APP_NAME)
        self.setQuitOnLastWindowClosed(False)

        # Main window
        self.control_panel = ControlPanel()

        # Connect the exit signal from the control panel to the application's quit method
        self.control_panel.exit_signal.connect(self.quit)


def main():
    # Create the application instance first
    app = QApplication(sys.argv)

    # Install the translator on the application instance
    translator = install_translator(APP_NAME)
    app.installTranslator(translator)

    # Now create the MainApp which holds the logic
    main_app = MainApp(sys.argv)
    
    # Show the main window
    main_app.control_panel.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
