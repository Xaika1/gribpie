import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QIcon


COLOR_PRIMARY = "#00a8c6"
COLOR_LIGHT = "#8fbee0"


class GribPie(QMainWindow):
    def __init__(self):
        super().__init__()


        self.setWindowTitle("GribPie")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(800, 600)


        if hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
        else:
            icon_path = 'icon.ico'

        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://xaika.ru"))


        self.browser.page().profile().downloadRequested.connect(self.handle_download)
        self.browser.page().profile().setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 XaikaDesktop/1.0"
        )


        self.setCentralWidget(self.browser)

        self.browser.contextMenuEvent = lambda event: None


        self.show()

    def handle_download(self, download):
        """Обработка загрузок файлов"""
        download.accept()


def main():

    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("Xaika Desktop")
    app.setOrganizationName("Xaika")


    app.setStyle("Fusion")


    window = GribPie()


    sys.exit(app.exec())


if __name__ == "__main__":
    main()