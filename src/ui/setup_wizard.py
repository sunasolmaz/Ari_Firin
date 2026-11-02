# src/ui/setup_wizard.py
"""
İlk Kurulum & Teşhis Sihirbazı (Setup & Diagnostic Wizard)
Müşteri bilgisayarlarında veritabanı, lisans ve masaüstü kısayollarını
kolayca yapılandırmayı ve canlı test etmeyi sağlar.
"""

import os
import sys
import logging
import psycopg2
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QWidget, QFormLayout, QCheckBox,
    QMessageBox, QFrame, QProgressBar, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon

from src.core.config import config
from src.core.database import db
from src.utils.license_manager import LicenseManager
from src.utils.shortcut_utils import create_desktop_shortcut, create_start_menu_shortcut

logger = logging.getLogger(__name__)


class SetupWizardDialog(QDialog):
    """
    Arı Fırın İlk Kurulum ve Sistem Teşhis Sihirbazı
    """

    def __init__(self, parent=None, autotest: bool = False):
        super().__init__(parent)
        self.setWindowTitle("🐝 Arı Fırın • İlk Kurulum ve Bağlantı Sihirbazı")
        self.setMinimumSize(620, 520)
        self.resize(680, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        # Temel durum değişkenleri
        self.db_tested_success = False
        self.license_tested_success = False

        self._setup_styles()
        self._init_ui()
        self._load_current_config()

        # ✅ Autotest: DB + Lisans sırayla
        if autotest:
            QTimer.singleShot(500, self._on_test_db)
            QTimer.singleShot(1500, self._on_test_license)

    def _setup_styles(self):
        """Modern, kurumsal arayüz stilleri"""
        self.setStyleSheet("""
            QDialog {
                background-color: #0F172A;
                color: #F8FAFC;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #CBD5E1;
                font-size: 13px;
            }
            QLabel#TitleLabel {
                color: #F8FAFC;
                font-size: 18px;
                font-weight: bold;
            }
            QLabel#SubTitleLabel {
                color: #94A3B8;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                color: #F8FAFC;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #38BDF8;
                background-color: #0F172A;
            }
            QTabWidget::pane {
                border: 1px solid #334155;
                border-radius: 8px;
                background-color: #1E293B;
                padding: 12px;
            }
            QTabBar::tab {
                background: #0F172A;
                color: #94A3B8;
                padding: 10px 18px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: #1E293B;
                color: #38BDF8;
                font-weight: bold;
                border-bottom: 2px solid #38BDF8;
            }
            QPushButton {
                background-color: #334155;
                color: #F8FAFC;
                border: none;
                border-radius: 6px;
                padding: 9px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            QPushButton#PrimaryBtn {
                background-color: #0284C7;
                color: #FFFFFF;
            }
            QPushButton#PrimaryBtn:hover {
                background-color: #0369A1;
            }
            QPushButton#SuccessBtn {
                background-color: #059669;
                color: #FFFFFF;
            }
            QPushButton#SuccessBtn:hover {
                background-color: #047857;
            }
            QCheckBox {
                color: #E2E8F0;
                font-size: 13px;
                spacing: 8px;
            }
            QFrame#BadgeFrame {
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # --- Üst Başlık ve Logo Alanı ---
        header_layout = QHBoxLayout()
        icon_label = QLabel("🐝")
        icon_label.setStyleSheet("font-size: 36px;")
        header_layout.addWidget(icon_label)

        title_vbox = QVBoxLayout()
        title_lbl = QLabel("Arı Fırın • Sistem Kurulum & Bağlantı Sihirbazı")
        title_lbl.setObjectName("TitleLabel")
        sub_lbl = QLabel("Veritabanı bağlantınızı, merkezi lisansınızı ve masaüstü kısayollarını yapılandırın.")
        sub_lbl.setObjectName("SubTitleLabel")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(sub_lbl)
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # --- Sekmeler ---
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_db_tab(), "🗄️ Veritabanı Yapılandırması")
        self.tabs.addTab(self._build_license_tab(), "🔑 Lisans & Merkezi Sunucu")
        self.tabs.addTab(self._build_shortcuts_tab(), "🚀 Kısayollar ve Başlatma")
        main_layout.addWidget(self.tabs)

        # --- Alt Eylem Butonları ---
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("İptal / Çıkış")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        btn_layout.addStretch()

        self.btn_save_launch = QPushButton("💾 Ayarları Kaydet ve Uygulamayı Başlat")
        self.btn_save_launch.setObjectName("SuccessBtn")
        self.btn_save_launch.clicked.connect(self._on_save_and_launch)
        btn_layout.addWidget(self.btn_save_launch)

        main_layout.addLayout(btn_layout)

    def _build_db_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        info_lbl = QLabel("PostgreSQL sunucu bilgilerini girin. Yerel makine için 'localhost', yerel ağdaki ana bilgisayar için IP adresi yazın (örn: 192.168.1.100).")
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(info_lbl)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.txt_db_host = QLineEdit()
        self.txt_db_host.setPlaceholderText("localhost veya 192.168.1.xxx")
        form.addRow("Sunucu Adresi (Host):", self.txt_db_host)

        self.txt_db_port = QLineEdit()
        self.txt_db_port.setPlaceholderText("5432")
        form.addRow("Bağlantı Portu:", self.txt_db_port)

        self.txt_db_name = QLineEdit()
        self.txt_db_name.setPlaceholderText("accounting_db")
        form.addRow("Veritabanı Adı:", self.txt_db_name)

        self.txt_db_user = QLineEdit()
        self.txt_db_user.setPlaceholderText("postgres")
        form.addRow("Kullanıcı Adı:", self.txt_db_user)

        pass_layout = QHBoxLayout()
        self.txt_db_password = QLineEdit()
        self.txt_db_password.setEchoMode(QLineEdit.Password)
        self.txt_db_password.setPlaceholderText("Veritabanı şifresi")
        pass_layout.addWidget(self.txt_db_password)

        self.chk_show_pass = QCheckBox("Göster")
        self.chk_show_pass.stateChanged.connect(
            lambda state: self.txt_db_password.setEchoMode(
                QLineEdit.Normal if state == Qt.Checked else QLineEdit.Password
            )
        )
        pass_layout.addWidget(self.chk_show_pass)
        form.addRow("Veritabanı Şifresi:", pass_layout)

        layout.addLayout(form)

        self.db_status_lbl = QLabel("⚡ Bağlantı henüz test edilmedi.")
        self.db_status_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; padding: 6px; background-color: #0F172A; border-radius: 4px;")
        layout.addWidget(self.db_status_lbl)

        btn_bar = QHBoxLayout()
        self.btn_test_db = QPushButton("⚡ Bağlantıyı Canlı Test Et")
        self.btn_test_db.setObjectName("PrimaryBtn")
        self.btn_test_db.clicked.connect(self._on_test_db)
        btn_bar.addWidget(self.btn_test_db)

        self.btn_init_schema = QPushButton("🛠️ Tabloları & Şemayı Oluştur")
        self.btn_init_schema.clicked.connect(self._on_init_schema)
        btn_bar.addWidget(self.btn_init_schema)

        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        layout.addStretch()
        return widget

    def _build_license_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        info_lbl = QLabel("Merkezi yönetim ve güncelleme sunucusuna ait bilgileri tanımlayın. Bu ayar otomatik OTA güncellemelerini ve bulut yedeklemeyi yönetir.")
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(info_lbl)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.txt_server_url = QLineEdit()
        self.txt_server_url.setPlaceholderText("http://sunaos:8000")
        form.addRow("Merkezi Sunucu URL:", self.txt_server_url)

        self.txt_project_id = QLineEdit()
        self.txt_project_id.setPlaceholderText("ari_firin")
        form.addRow("Proje Kimliği:", self.txt_project_id)

        self.txt_license_key = QLineEdit()
        self.txt_license_key.setPlaceholderText("ARI-FIRIN-TEKIRDAG-2026")
        form.addRow("Lisans Anahtarı:", self.txt_license_key)

        layout.addLayout(form)

        self.lic_status_lbl = QLabel("🔑 Lisans henüz sorgulanmadı.")
        self.lic_status_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; padding: 6px; background-color: #0F172A; border-radius: 4px;")
        layout.addWidget(self.lic_status_lbl)

        lic_btn_bar = QHBoxLayout()
        self.btn_test_lic = QPushButton("🔍 Lisansı Sunucudan Doğrula")
        self.btn_test_lic.setObjectName("PrimaryBtn")
        self.btn_test_lic.clicked.connect(self._on_test_license)
        lic_btn_bar.addWidget(self.btn_test_lic)
        lic_btn_bar.addStretch()

        layout.addLayout(lic_btn_bar)
        layout.addStretch()
        return widget

    def _build_shortcuts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)

        info_lbl = QLabel("Kullanıcının programa masaüstünden ve başlat menüsünden tek tıkla erişebilmesi için kısayol tercihlerini belirleyin.")
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(info_lbl)

        self.chk_desktop_shortcut = QCheckBox("🖥️ Masaüstüne 'Arı Fırın' kısayolu oluştur")
        self.chk_desktop_shortcut.setChecked(True)
        layout.addWidget(self.chk_desktop_shortcut)

        self.chk_start_menu_shortcut = QCheckBox("📋 Başlat Menüsüne 'Arı Fırın' ekle")
        self.chk_start_menu_shortcut.setChecked(True)
        layout.addWidget(self.chk_start_menu_shortcut)

        summary_frame = QFrame()
        summary_frame.setStyleSheet("background-color: #0F172A; border: 1px solid #334155; border-radius: 6px; padding: 10px;")
        summary_layout = QVBoxLayout(summary_frame)
        summary_title = QLabel("📌 Kurulum Özeti & Çalışma Ortamı:")
        summary_title.setStyleSheet("color: #38BDF8; font-weight: bold;")
        summary_layout.addWidget(summary_title)

        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath("main.py")
        self.lbl_exec_path = QLabel(f"• Yürütülebilir Dosya: {exe_path}")
        self.lbl_exec_path.setStyleSheet("color: #CBD5E1; font-size: 11px;")
        summary_layout.addWidget(self.lbl_exec_path)

        self.lbl_cfg_path = QLabel(f"• Yapılandırma Dosyası: {config._config_path}")
        self.lbl_cfg_path.setStyleSheet("color: #CBD5E1; font-size: 11px;")
        summary_layout.addWidget(self.lbl_cfg_path)

        layout.addWidget(summary_frame)
        layout.addStretch()
        return widget

    def _load_current_config(self):
        """Mevcut yapılandırma değerlerini arayüze doldurur"""
        self.txt_db_host.setText(str(config.get("database.host", "localhost")))
        self.txt_db_port.setText(str(config.get("database.port", 5432)))
        self.txt_db_name.setText(str(config.get("database.database", "accounting_db")))
        self.txt_db_user.setText(str(config.get("database.user", "postgres")))
        self.txt_db_password.setText(str(config.get("database.password", "")))

        self.txt_server_url.setText(str(config.get("update.server_url", "http://sunaos:8000")))
        self.txt_project_id.setText(str(config.get("update.project_id", "ari_firin")))
        self.txt_license_key.setText(str(config.get("update.license_key", "ARI-FIRIN-TEKIRDAG-2026")))

    def _get_form_db_config(self) -> dict:
        try:
            port = int(self.txt_db_port.text().strip())
        except ValueError:
            port = 5432
        return {
            "host": self.txt_db_host.text().strip() or "localhost",
            "port": port,
            "database": self.txt_db_name.text().strip() or "accounting_db",
            "user": self.txt_db_user.text().strip() or "postgres",
            "password": self.txt_db_password.text()
        }

    def _on_test_db(self):
        """PostgreSQL sunucusuna canlı bağlantı testi gerçekleştirir"""
        cfg = self._get_form_db_config()
        self.db_status_lbl.setText("⏳ PostgreSQL sunucusuna bağlanılıyor...")
        self.db_status_lbl.setStyleSheet("color: #38BDF8; font-size: 12px; padding: 6px; background-color: #0F172A; border-radius: 4px;")
        self.btn_test_db.setEnabled(False)

        try:
            conn = psycopg2.connect(
                host=cfg["host"],
                port=cfg["port"],
                database=cfg["database"],
                user=cfg["user"],
                password=cfg["password"],
                connect_timeout=4
            )
            cur = conn.cursor()
            cur.execute("SELECT version();")
            ver = cur.fetchone()[0].split()[1]
            conn.close()

            self.db_tested_success = True
            self.db_status_lbl.setText(f"✅ Bağlantı Başarılı! (PostgreSQL v{ver} - {cfg['host']}:{cfg['port']})")
            self.db_status_lbl.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px; padding: 6px; background-color: #064E3B; border-radius: 4px;")
        except Exception as e:
            self.db_tested_success = False
            err_msg = str(e).strip()
            self.db_status_lbl.setText(f"❌ Bağlantı Başarısız: {err_msg}")
            self.db_status_lbl.setStyleSheet("color: #F87171; font-weight: bold; font-size: 12px; padding: 6px; background-color: #450A0A; border-radius: 4px;")
        finally:
            self.btn_test_db.setEnabled(True)

    def _on_init_schema(self):
        """Mevcut ayarlarla veritabanı tablolarını ve şemasını oluşturur"""
        if not self.db_tested_success:
            self._on_test_db()
            if not self.db_tested_success:
                QMessageBox.warning(self, "Önce Bağlantı Kurulmalı", "Lütfen önce geçerli bir veritabanı bağlantısı sağlayın!")
                return

        cfg = self._get_form_db_config()
        for k, v in cfg.items():
            config.set(f"database.{k}", v)

        try:
            db.initialize_database()
            QMessageBox.information(self, "Şema Hazır", "✅ Veritabanı şeması, tablolar ve indeksler başarıyla oluşturuldu!")
        except Exception as e:
            QMessageBox.critical(self, "Şema Hatası", f"Veritabanı tabloları oluşturulurken hata:\n{e}")

    def _on_test_license(self):
        """Merkezi sunucudan lisans doğrulaması yapar"""
        server_url = self.txt_server_url.text().strip()
        project_id = self.txt_project_id.text().strip()
        license_key = self.txt_license_key.text().strip()

        self.lic_status_lbl.setText("⏳ Merkezi lisans sunucusu sorgulanıyor...")
        self.lic_status_lbl.setStyleSheet("color: #38BDF8; font-size: 12px; padding: 6px; background-color: #0F172A; border-radius: 4px;")
        self.btn_test_lic.setEnabled(False)

        try:
            lm = LicenseManager()
            is_valid, msg = lm.verify_remote_license(server_url, project_id, license_key)
            if is_valid:
                self.license_tested_success = True
                self.lic_status_lbl.setText(f"✅ Lisans Doğrulandı: {msg}")
                self.lic_status_lbl.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px; padding: 6px; background-color: #064E3B; border-radius: 4px;")
            else:
                self.license_tested_success = False
                self.lic_status_lbl.setText(f"⚠️ Lisans Uyarısı: {msg}")
                self.lic_status_lbl.setStyleSheet("color: #F87171; font-weight: bold; font-size: 12px; padding: 6px; background-color: #450A0A; border-radius: 4px;")
        except Exception as e:
            self.license_tested_success = False
            self.lic_status_lbl.setText(f"❌ Sunucu Hatası: {e}")
            self.lic_status_lbl.setStyleSheet("color: #F87171; font-weight: bold; font-size: 12px; padding: 6px; background-color: #450A0A; border-radius: 4px;")
        finally:
            self.btn_test_lic.setEnabled(True)

    def _on_save_and_launch(self):
        """Ayarları kaydeder, kısayolları oluşturur ve sihirbazı tamamlar"""
        cfg = self._get_form_db_config()
        for k, v in cfg.items():
            config.set(f"database.{k}", v)

        config.set("update.server_url", self.txt_server_url.text().strip())
        config.set("update.project_id", self.txt_project_id.text().strip())
        config.set("update.license_key", self.txt_license_key.text().strip())
        config.save()
        logger.info("✅ Kurulum sihirbazı ayarları config.json'a kaydedildi.")

        target_exe = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath("main.py")
        icon_path = os.path.abspath("resources/icons/app.ico") if os.path.exists("resources/icons/app.ico") else None

        if self.chk_desktop_shortcut.isChecked():
            create_desktop_shortcut(target_exe, shortcut_name="Arı Fırın", icon_path=icon_path)

        if self.chk_start_menu_shortcut.isChecked():
            create_start_menu_shortcut(target_exe, shortcut_name="Arı Fırın", icon_path=icon_path)

        self.accept()