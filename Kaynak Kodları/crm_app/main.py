from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:
    package_parent = Path(__file__).resolve().parents[1]
    if str(package_parent) not in sys.path:
        sys.path.insert(0, str(package_parent))
    __package__ = "crm_app"

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QDialog

from .ai import AIEngine
from .arayuz import CRMMainWindow, LoginDialog
from .arayuz.styles import get_app_style
from .veritabani import DatabaseManager


# QApplication için temel masaüstü ayarları burada hazırlanır.
def build_app() -> QApplication:
    # Yüksek çözünürlüklü ekranlarda metin ve ikonların net görünmesini sağlar.
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)

    # Uygulamanın global adı, fontu, Qt stili ve ilk teması atanır.
    app.setApplicationName("NexCRM Pro")
    app.setOrganizationName("NexCRM")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(get_app_style(False))
    return app


# Ana çalışma akışı: uygulamayı kur, giriş ekranını aç, başarılıysa CRM'i başlat.
def main() -> int:
    app = build_app()

    # Veri katmanı ve AI motoru uygulama boyunca aynı örnekler üzerinden kullanılır.
    db = DatabaseManager()
    ai = AIEngine(db)
    app.aboutToQuit.connect(db.close)

    window: CRMMainWindow | None = None

    def open_login_and_create_window(previous_window: CRMMainWindow | None = None) -> bool:
        nonlocal window
        if previous_window:
            previous_window.hide()

        login = LoginDialog(db)
        if login.exec_() != QDialog.Accepted or not login.authenticated_user:
            if previous_window:
                previous_window.close()
            return False

        new_window = CRMMainWindow(db, ai, login.authenticated_user)
        new_window.logout_requested.connect(lambda: open_login_and_create_window(new_window) or app.quit())
        new_window.show()

        if previous_window:
            previous_window.close()
            previous_window.deleteLater()
        window = new_window
        return True

    # Kullanıcı doğrulanmadan ana CRM penceresi açılmaz.
    if not open_login_and_create_window():
        return 0

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
