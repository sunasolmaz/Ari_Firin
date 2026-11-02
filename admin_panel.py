#!/usr/bin/env python3
# admin_panel.py
"""
Arı Fırın - Bağımsız Yönetici & Denetim Paneli (Admin Dashboard)
Ana uygulamadan bağımsız olarak çalışır ve canlı kullanıcıları,
özellikle o anda açık olan aktif kullanıcı adlarını izleme olanağı sunar.
"""

import sys
import os

# Proje ana dizinini Python yoluna ekle
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt

from src.core.logger import logger
from src.core.database import db
from src.ui.admin_window import AdminPanelWindow


def main():
    logger.info("============================================================")
    logger.info("🛡️ ARI FIRIN - YÖNETİCİ VE DENETİM PANELİ BAŞLATILIYOR")
    logger.info("============================================================")
    
    # Windows görev çubuğu gruplaması için App ID
    try:
        import ctypes
        myappid = 'arifirin.adminpanel.dashboard.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Varsayılan modern sistem yazı tipi
    app.setFont(QFont("Segoe UI", 10))

    # Veritabanı bağlantısı
    try:
        db.initialize_database()
        logger.info("✅ Veritabanı bağlantısı başarıyla sağlandı.")
    except Exception as e:
        logger.error(f"❌ Veritabanı başlatma hatası: {e}")
        QMessageBox.critical(
            None, "Bağlantı Hatası",
            f"Veritabanına bağlanılamadı!\nPostgreSQL servisinin çalıştığından emin olun.\n\nHata: {e}"
        )
        return 1

    # Pencereyi Başlat
    try:
        window = AdminPanelWindow()
        window.show()
        logger.info("🚀 Yönetici paneli arayüzü başarıyla açıldı.")
        exit_code = app.exec_()
        logger.info("👋 Yönetici paneli kapatıldı.")
        return exit_code
    except Exception as e:
        logger.error(f"❌ Yönetici paneli çalışma hatası: {e}")
        QMessageBox.critical(None, "Hata", f"Yönetici paneli çalışırken hata oluştu:\n{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
