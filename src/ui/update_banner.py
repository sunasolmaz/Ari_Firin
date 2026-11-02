# src/ui/update_banner.py
"""
Arı Fırın - Uygulama İçi Canlı Güncelleme Bildirim Çubuğu (Update Banner)
Yeni sürüm çıktığında ekranın üst kısmında şık, interaktif bir bildirim gösterir.
Kullanıcı 'Şimdi İndir ve Kur' butonuna tıklayarak güncellemeyi doğrudan başlatabilir.
"""

from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QMessageBox
from PyQt5.QtCore import Qt
from .styles import AppStyles
from ..services.updater_service import updater


class UpdateBanner(QFrame):
    """Canlı OTA Güncelleme Bildirim Banner'ı"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.latest_version = ""
        self.download_url = ""
        self.release_notes = ""
        self.force_update = False

        self._setup_ui()
        self.setVisible(False)

        updater.bridge.update_found.connect(self.on_update_found)

        if updater.latest_update_info:
            info = updater.latest_update_info
            self.on_update_found(
                info["version"], info["download_url"],
                info["notes"], info["force"]
            )

    def _setup_ui(self):
        self.setFixedHeight(54)
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0f172a, stop:0.5 #1e293b, stop:1 #0f172a);
                border-bottom: 2px solid {AppStyles.PRIMARY};
                padding: 0px 16px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(14)

        self.lbl_text = QLabel("🚀 Yeni Güncelleme Yayında!")
        self.lbl_text.setStyleSheet(f"""
            color: #ffffff;
            font-size: 10pt;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.lbl_text)

        layout.addStretch()

        self.btn_notes = QPushButton("ℹ️ Yenilikleri Gör")
        self.btn_notes.setCursor(Qt.PointingHandCursor)
        self.btn_notes.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.08);
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.16);
                border-color: {AppStyles.PRIMARY};
                color: #ffffff;
            }}
        """)
        self.btn_notes.clicked.connect(self._show_notes)
        layout.addWidget(self.btn_notes)

        self.btn_download = QPushButton("📥 Şimdi İndir ve Güncelle")
        self.btn_download.setCursor(Qt.PointingHandCursor)
        self.btn_download.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                color: #080810;
                font-weight: bold;
                font-size: 9.5pt;
                border-radius: 6px;
                padding: 6px 16px;
                border: none;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
            }}
        """)
        self.btn_download.clicked.connect(self._start_download)
        layout.addWidget(self.btn_download)

        self.btn_close = QPushButton("✕")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                font-size: 11pt;
                border: none;
                border-radius: 14px;
            }
            QPushButton:hover {
                color: #ffffff;
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self.btn_close.clicked.connect(lambda: self.setVisible(False))
        layout.addWidget(self.btn_close)

    def on_update_found(self, latest_ver: str, download_url: str, notes: str, force: bool):
        self.latest_version = latest_ver
        self.download_url = download_url
        self.release_notes = notes
        self.force_update = force

        self.lbl_text.setText(f"🚀 Arı Fırın v{latest_ver} Güncellemesi Hazır! (Mevcut: v{updater.current_version})")
        self.btn_close.setVisible(not force)
        self.setVisible(True)

    def _show_notes(self):
        msg = f"📋 Arı Fırın v{self.latest_version} Yenilikleri:\n\n"
        msg += self.release_notes or "Genel performans iyileştirmeleri ve hata düzeltmeleri."
        QMessageBox.information(self, f"v{self.latest_version} Değişiklik Notları", msg)

    def _start_download(self):
        if not self.download_url:
            QMessageBox.information(
                self, "Bilgi",
                f"Yeni sürüm (v{self.latest_version}) sunucuda tanımlanmış ancak indirme paketi henüz yüklenmemiş."
            )
            return
        # ✅ Public metot kullan
        updater.start_download(self.download_url, self.latest_version)