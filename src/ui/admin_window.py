# src/ui/admin_window.py
"""
Bağımsız Yönetici (Admin) ve Denetim Paneli
Kullanıcı sayıları, aktif kullanıcı adları ve sistem istatistiklerini canlı izleme
"""

import os
from datetime import datetime
from typing import List, Dict

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QComboBox, QScrollArea, QDialog, QFormLayout
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPainter

from ..core.database import db
from ..core.logger import logger
from ..models.user import User
from .styles import AppStyles


class AdminPanelWindow(QMainWindow):
    """Modern Bağımsız Yönetici ve Denetim Paneli"""

    # ✅ Session timeout (5 dakika hareketsizlik)
    SESSION_TIMEOUT_SECONDS = 300

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🛡️ Arı Fırın - Yönetici & Canlı Denetim Paneli")
        self.setMinimumSize(1180, 750)
        self.resize(1366, 850)

        self.icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")

        self.auto_refresh_interval = 5
        self.countdown = self.auto_refresh_interval

        self._all_users_cache: List[Dict] = []
        self._current_filter = "ALL"

        # ✅ Hareketsizlik takibi
        self._last_activity = datetime.now()

        self.setup_ui()
        self.setup_timers()
        self.refresh_all_data()

    def _load_colored_icon(self, path: str, size: int = 44, color: str = "#22c55e") -> QPixmap:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return pixmap
        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        colored = QPixmap(pixmap.size())
        colored.fill(Qt.transparent)
        painter = QPainter(colored)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(colored.rect(), QColor(color))
        painter.end()
        return colored

    # ✅ Aktivite takibi
    def _mark_activity(self):
        self._last_activity = datetime.now()

    def mousePressEvent(self, event):
        self._mark_activity()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        self._mark_activity()
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        self._mark_activity()
        super().wheelEvent(event)

    def _check_inactivity(self):
        """Hareketsizlik kontrolü — 5 dakika geçtiyse paneli kapat"""
        try:
            elapsed = (datetime.now() - self._last_activity).total_seconds()
            if elapsed > self.SESSION_TIMEOUT_SECONDS:
                logger.info(f"⏱️ Admin paneli {self.SESSION_TIMEOUT_SECONDS}s hareketsizlik sonrası kapatıldı")
                QMessageBox.information(
                    self, "Oturum Zaman Aşımı",
                    "Güvenlik nedeniyle hareketsizlik sonrası yönetici paneli kapatıldı."
                )
                self.close()
        except Exception as e:
            logger.error(f"Hareketsizlik kontrolü hatası: {e}")

    def setup_ui(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {AppStyles.BG_DARKEST};
            }}
            QWidget {{
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTabWidget::pane {{
                border: 1px solid {AppStyles.BORDER};
                background-color: {AppStyles.BG_DARK};
                border-radius: 10px;
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: transparent;
                color: {AppStyles.TEXT_SECONDARY};
                padding: 10px 22px;
                margin-right: 6px;
                border: none;
                border-bottom: 2px solid transparent;
                font-size: 10pt;
                font-weight: 500;
            }}
            QTabBar::tab:selected {{
                color: {AppStyles.PRIMARY};
                border-bottom: 2px solid {AppStyles.PRIMARY};
                font-weight: bold;
                background-color: rgba(74, 158, 255, 0.08);
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QTabBar::tab:hover:!selected {{
                color: {AppStyles.TEXT_PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
        """)

        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        header_bar = self.create_header_bar()
        main_layout.addWidget(header_bar)

        self.hero_active_card = self.create_hero_active_card()
        main_layout.addWidget(self.hero_active_card)

        kpi_cards = self.create_kpi_cards()
        main_layout.addWidget(kpi_cards)

        tabs = self.create_tabs()
        main_layout.addWidget(tabs, 1)

        self.setCentralWidget(central_widget)

    def create_header_bar(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 12px;
                padding: 6px 14px;
            }}
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(16)

        logo_lbl = QLabel()
        logo_px = self._load_colored_icon(self.icon_path, 40, "#22c55e")
        if not logo_px.isNull():
            logo_lbl.setPixmap(logo_px)
        else:
            logo_lbl.setText("🛡️")
            logo_lbl.setStyleSheet("font-size: 24pt;")
        layout.addWidget(logo_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        main_title = QLabel("ARI FIRIN • Yönetici Paneli")
        main_title.setStyleSheet("font-size: 13.5pt; font-weight: bold; color: #ffffff;")
        sub_title = QLabel("Canlı Kullanıcı ve Sistem İzleme Merkezi")
        sub_title.setStyleSheet("font-size: 8.5pt; color: #94a3b8;")
        title_vbox.addWidget(main_title)
        title_vbox.addWidget(sub_title)
        layout.addLayout(title_vbox)

        layout.addStretch()

        status_badge = QLabel("🟢 Canlı PostgreSQL Bağlantısı")
        status_badge.setStyleSheet(f"""
            background-color: rgba(34, 197, 94, 0.12);
            color: #22c55e;
            border: 1px solid rgba(34, 197, 94, 0.3);
            border-radius: 14px;
            padding: 5px 12px;
            font-weight: 600;
            font-size: 8.5pt;
        """)
        layout.addWidget(status_badge)

        lbl_auto = QLabel("Otomatik Yenileme:")
        lbl_auto.setStyleSheet("color: #94a3b8; font-size: 8.5pt;")
        layout.addWidget(lbl_auto)

        self.refresh_combo = QComboBox()
        self.refresh_combo.addItems(["5 Saniye", "10 Saniye", "30 Saniye", "Kapalı (Manuel)"])
        self.refresh_combo.setCurrentIndex(0)
        self.refresh_combo.currentIndexChanged.connect(self.on_refresh_interval_changed)
        self.refresh_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 8px;
                color: #ffffff;
                font-size: 8.5pt;
                min-width: 100px;
            }}
            QComboBox::drop-down {{ border: none; }}
        """)
        layout.addWidget(self.refresh_combo)

        self.countdown_badge = QLabel(f"⏱️ {self.countdown}s")
        self.countdown_badge.setStyleSheet("""
            background-color: #262635;
            color: #4a9eff;
            border-radius: 6px;
            padding: 4px 8px;
            font-weight: bold;
            font-size: 8.5pt;
        """)
        layout.addWidget(self.countdown_badge)

        self.refresh_btn = QPushButton("🔄 Şimdi Yenile")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_all_data)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                color: #0d0d0f;
                font-weight: bold;
                font-size: 9pt;
                border-radius: 6px;
                padding: 5px 14px;
                border: none;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
            }}
        """)
        layout.addWidget(self.refresh_btn)

        return header

    def create_hero_active_card(self) -> QWidget:
        """Anlık Aktif Kullanıcı Adları Bölümü"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #101c15, stop:1 #15241b);
                border: 1.5px solid rgba(34, 197, 94, 0.4);
                border-radius: 12px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        title_lbl = QLabel("🟢 ŞU ANDA UYGULAMADAKİ AKTİF KULLANICILAR")
        title_lbl.setStyleSheet("font-size: 11pt; font-weight: bold; color: #22c55e; letter-spacing: 1px; background: transparent; border: none;")
        top_row.addWidget(title_lbl)

        self.hero_online_count_lbl = QLabel("0 Kullanıcı Çevrimiçi")
        self.hero_online_count_lbl.setStyleSheet("""
            background-color: rgba(34, 197, 94, 0.2);
            color: #ffffff;
            font-size: 8.5pt;
            font-weight: bold;
            padding: 3px 10px;
            border-radius: 10px;
            border: 1px solid rgba(34, 197, 94, 0.4);
        """)
        top_row.addWidget(self.hero_online_count_lbl)
        top_row.addStretch()

        self.last_updated_lbl = QLabel(f"Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}")
        self.last_updated_lbl.setStyleSheet("font-size: 8.5pt; color: #94a3b8; background: transparent; border: none;")
        top_row.addWidget(self.last_updated_lbl)

        layout.addLayout(top_row)

        self.active_users_container = QWidget()
        self.active_users_container.setStyleSheet("background: transparent; border: none;")
        self.active_users_layout = QHBoxLayout(self.active_users_container)
        self.active_users_layout.setContentsMargins(0, 4, 0, 4)
        self.active_users_layout.setSpacing(12)
        self.active_users_layout.setAlignment(Qt.AlignLeft)

        layout.addWidget(self.active_users_container)
        return card

    def create_kpi_cards(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.kpi_total_users = self._make_kpi_card("👥", "Toplam Kayıtlı", "0", "Aktif: 0 | Pasif: 0", "#3b82f6")
        self.kpi_online_users = self._make_kpi_card("🟢", "Çevrimiçi Kullanıcı", "0", "Aktif Oturum", "#22c55e")
        self.kpi_branches = self._make_kpi_card("🏢", "Aktif Şubeler", "0", "Sistem Şubeleri", "#a855f7")
        self.kpi_invoices = self._make_kpi_card("📑", "Toplam İşlem", "0", "Kayıtlı Fatura/İşlem", "#f59e0b")
        self.kpi_db_size = self._make_kpi_card("💾", "Veritabanı", "0.00 MB", "PostgreSQL Sağlıklı", "#06b6d4")

        layout.addWidget(self.kpi_total_users)
        layout.addWidget(self.kpi_online_users)
        layout.addWidget(self.kpi_branches)
        layout.addWidget(self.kpi_invoices)
        layout.addWidget(self.kpi_db_size)
        return container

    def _make_kpi_card(self, icon: str, title: str, value: str, subtitle: str, accent_color: str) -> QFrame:
        card = QFrame()
        card.setMinimumWidth(180)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 12px;
                padding: 10px 14px;
            }}
            QFrame:hover {{
                border-color: {accent_color};
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        top_h = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"font-size: 16pt; background: transparent; border: none;")
        top_h.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 9pt; color: #94a3b8; font-weight: 600; background: transparent; border: none;")
        top_h.addWidget(title_lbl)
        top_h.addStretch()
        layout.addLayout(top_h)

        val_lbl = QLabel(value)
        val_lbl.setObjectName("val_lbl")
        val_lbl.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {accent_color}; background: transparent; border: none;")
        layout.addWidget(val_lbl)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setObjectName("sub_lbl")
        sub_lbl.setStyleSheet("font-size: 8pt; color: #64748b; background: transparent; border: none;")
        layout.addWidget(sub_lbl)
        return card

    def create_tabs(self) -> QWidget:
        self.main_tabs = QTabWidget()

        self.user_tab = self.create_user_management_tab()
        self.main_tabs.addTab(self.user_tab, "Kullanıcı Yönetimi (Canlı)")

        self.system_tab = self.create_system_analytics_tab()
        self.main_tabs.addTab(self.system_tab, "Şube & Sistem Analitiği")

        self.security_tab = self.create_security_tab()
        self.main_tabs.addTab(self.security_tab, "Güvenlik & Oturumlar")

        return self.main_tabs

    def create_user_management_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Kullanıcı adı, isim, e-posta veya şube ile filtrele...")
        self.search_input.textChanged.connect(self.filter_users_table)
        self.search_input.setFixedHeight(38)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 0px 14px;
                color: #ffffff;
                font-size: 9.5pt;
            }}
            QLineEdit:focus {{ border-color: {AppStyles.PRIMARY}; }}
        """)
        filter_row.addWidget(self.search_input, 2)

        self.btn_filter_all = QPushButton("Tümü")
        self.btn_filter_online = QPushButton("🟢 Çevrimiçi")
        self.btn_filter_active = QPushButton("Aktif Hesaplar")
        self.btn_filter_inactive = QPushButton("Pasif / Dondurulmuş")

        self.filter_buttons = [
            (self.btn_filter_all, "ALL"),
            (self.btn_filter_online, "ONLINE"),
            (self.btn_filter_active, "ACTIVE"),
            (self.btn_filter_inactive, "INACTIVE"),
        ]

        for btn, f_type in self.filter_buttons:
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(38)
            btn.clicked.connect(lambda checked, t=f_type: self.set_active_filter(t))
            filter_row.addWidget(btn)

        self._update_filter_button_styles()
        layout.addLayout(filter_row)

        self.user_table = QTableWidget()
        self.user_table.setColumnCount(10)
        self.user_table.setHorizontalHeaderLabels([
            "Durum", "Kullanıcı Adı", "Ad Soyad", "E-Posta",
            "Telefon", "Şube", "Yetki Rolü", "Hesap Durumu",
            "Son Giriş Tarihi", "İşlemler"
        ])
        self.user_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.user_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.user_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.user_table.horizontalHeader().setSectionResizeMode(9, QHeaderView.Fixed)
        self.user_table.setColumnWidth(9, 185)
        self.user_table.verticalHeader().setDefaultSectionSize(44)
        self.user_table.verticalHeader().setVisible(False)
        self.user_table.setAlternatingRowColors(True)
        self.user_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.user_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.user_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                alternate-background-color: #171720;
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                gridline-color: #232330;
                font-size: 9.5pt;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_MEDIUM};
                color: #94a3b8;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid {AppStyles.BORDER};
                padding: 10px 8px;
                font-size: 9pt;
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid #1e1e28;
            }}
            QTableWidget::item:selected {{
                background-color: rgba(74, 158, 255, 0.2);
                color: #ffffff;
            }}
        """)
        layout.addWidget(self.user_table, 1)
        return tab

    def create_system_analytics_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(16)

        left_box = QFrame()
        left_box.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 10px;
                padding: 14px;
            }}
        """)
        left_layout = QVBoxLayout(left_box)
        branch_title = QLabel("🏢 Şubelere Göre Kullanıcı Dağılımı")
        branch_title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #4a9eff;")
        left_layout.addWidget(branch_title)

        self.branch_table = QTableWidget()
        self.branch_table.setColumnCount(4)
        self.branch_table.setHorizontalHeaderLabels(["Şube ID", "Şube Adı", "Kullanıcı Sayısı", "Çevrimiçi"])
        self.branch_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.branch_table.verticalHeader().setDefaultSectionSize(42)
        self.branch_table.verticalHeader().setVisible(False)
        self.branch_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                font-size: 9pt;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARK};
                color: #94a3b8;
                font-weight: bold;
                border: none;
                padding: 8px;
            }}
        """)
        left_layout.addWidget(self.branch_table)
        layout.addWidget(left_box, 1)

        right_box = QFrame()
        right_box.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 10px;
                padding: 14px;
            }}
        """)
        right_layout = QVBoxLayout(right_box)
        db_title = QLabel("💾 Veritabanı Tablo Kayıt Sayıları")
        db_title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #22c55e;")
        right_layout.addWidget(db_title)

        self.db_table = QTableWidget()
        self.db_table.setColumnCount(2)
        self.db_table.setHorizontalHeaderLabels(["Tablo Adı", "Kayıt Sayısı"])
        self.db_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.db_table.verticalHeader().setDefaultSectionSize(42)
        self.db_table.verticalHeader().setVisible(False)
        self.db_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                font-size: 9pt;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARK};
                color: #94a3b8;
                font-weight: bold;
                border: none;
                padding: 8px;
            }}
        """)
        right_layout.addWidget(self.db_table)
        layout.addWidget(right_box, 1)

        return tab

    def create_security_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        desc_card = QFrame()
        desc_card.setStyleSheet("""
            background-color: rgba(239, 68, 68, 0.08);
            border: 1px solid rgba(239, 68, 68, 0.25);
            border-radius: 10px;
            padding: 16px;
        """)
        desc_layout = QVBoxLayout(desc_card)
        sec_title = QLabel("⚠️ Sistem Oturum ve Güvenlik Denetimi")
        sec_title.setStyleSheet("font-size: 12pt; font-weight: bold; color: #ef4444;")
        sec_desc = QLabel(
            "Bu alandaki işlemler sistem genelini etkiler. Örneğin beklenmedik elektrik kesintileri "
            "veya kilitlenmeler sonucu açık kalan oturumları topluca sonlandırabilir ya da şifre yenileme işlemi yapabilirsiniz."
        )
        sec_desc.setStyleSheet("color: #cbd5e1; font-size: 9.5pt;")
        sec_desc.setWordWrap(True)
        desc_layout.addWidget(sec_title)
        desc_layout.addWidget(sec_desc)
        layout.addWidget(desc_card)

        actions_card = QFrame()
        actions_card.setStyleSheet(f"""
            background-color: {AppStyles.BG_DARK};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 10px;
            padding: 18px;
        """)
        act_layout = QVBoxLayout(actions_card)
        act_layout.setSpacing(14)

        row1 = QHBoxLayout()
        reset_sessions_btn = QPushButton("🔴 TÜM AÇIK OTURUMLARI SIFIRLA")
        reset_sessions_btn.setCursor(Qt.PointingHandCursor)
        reset_sessions_btn.setFixedHeight(44)
        reset_sessions_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                font-weight: bold;
                font-size: 10pt;
                border-radius: 8px;
                padding: 0px 20px;
                border: none;
            }
            QPushButton:hover { background-color: #dc2626; }
        """)
        reset_sessions_btn.clicked.connect(self.action_reset_all_sessions)
        row1.addWidget(reset_sessions_btn)

        lbl_reset_info = QLabel("Sistemdeki tüm 'çevrimiçi' durumlarını sıfırlar. Kullanıcılar bir sonraki işlemde yeniden giriş yapmalıdır.")
        lbl_reset_info.setStyleSheet("color: #94a3b8; font-size: 9pt;")
        lbl_reset_info.setWordWrap(True)
        row1.addWidget(lbl_reset_info, 1)
        act_layout.addLayout(row1)

        act_layout.addSpacing(10)

        pwd_box_title = QLabel("🔑 Kullanıcı Şifresi Belirleme / Sıfırlama")
        pwd_box_title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #4a9eff;")
        act_layout.addWidget(pwd_box_title)

        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(10)

        self.sec_user_combo = QComboBox()
        self.sec_user_combo.setFixedHeight(38)
        self.sec_user_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                color: #ffffff;
                font-size: 9.5pt;
                min-width: 200px;
            }}
        """)
        pwd_row.addWidget(self.sec_user_combo)

        self.sec_new_password = QLineEdit()
        self.sec_new_password.setPlaceholderText("Yeni Şifre girin (en az 8 karakter, büyük/küçük harf + rakam)...")
        self.sec_new_password.setFixedHeight(38)
        self.sec_new_password.setStyleSheet(f"""
            QLineEdit {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 0px 12px;
                color: #ffffff;
                font-size: 9.5pt;
            }}
        """)
        pwd_row.addWidget(self.sec_new_password, 1)

        set_pwd_btn = QPushButton("Şifreyi Güncelle")
        set_pwd_btn.setCursor(Qt.PointingHandCursor)
        set_pwd_btn.setFixedHeight(38)
        set_pwd_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.PRIMARY};
                color: #0d0d0f;
                font-weight: bold;
                font-size: 9.5pt;
                border-radius: 6px;
                padding: 0px 18px;
                border: none;
            }}
            QPushButton:hover {{ background-color: {AppStyles.CYAN}; }}
        """)
        set_pwd_btn.clicked.connect(self.action_set_user_password)
        pwd_row.addWidget(set_pwd_btn)

        act_layout.addLayout(pwd_row)
        layout.addWidget(actions_card)
        layout.addStretch()

        return tab

    def setup_timers(self):
        """1 saniyede bir çalışan geri sayım ve otomatik tetikleyici + hareketsizlik kontrolü"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)
        self.timer.start(1000)

        # ✅ Hareketsizlik kontrol zamanlayıcısı
        self._inactivity_timer = QTimer(self)
        self._inactivity_timer.timeout.connect(self._check_inactivity)
        self._inactivity_timer.start(60 * 1000)  # Her dakika

    def _on_timer_tick(self):
        if self.auto_refresh_interval <= 0:
            self.countdown_badge.setText("⏱️ Manuel")
            return

        self.countdown -= 1
        if self.countdown <= 0:
            self.countdown = self.auto_refresh_interval
            self.refresh_all_data()
        else:
            self.countdown_badge.setText(f"⏱️ {self.countdown}s")

    def on_refresh_interval_changed(self, index: int):
        intervals = [5, 10, 30, 0]
        self.auto_refresh_interval = intervals[index]
        self.countdown = self.auto_refresh_interval
        if self.auto_refresh_interval == 0:
            self.countdown_badge.setText("⏱️ Manuel")
        else:
            self.countdown_badge.setText(f"⏱️ {self.countdown}s")

    def set_active_filter(self, filter_type: str):
        self._current_filter = filter_type
        self._update_filter_button_styles()
        self.filter_users_table()

    def _update_filter_button_styles(self):
        for btn, f_type in self.filter_buttons:
            if f_type == self._current_filter:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {AppStyles.PRIMARY};
                        color: #0d0d0f;
                        font-weight: bold;
                        border-radius: 8px;
                        padding: 0px 14px;
                        border: none;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {AppStyles.BG_MEDIUM};
                        color: #94a3b8;
                        border-radius: 8px;
                        padding: 0px 14px;
                        border: 1px solid {AppStyles.BORDER};
                    }}
                    QPushButton:hover {{
                        color: #ffffff;
                        border-color: {AppStyles.PRIMARY};
                    }}
                """)

    def refresh_all_data(self):
        try:
            self.last_updated_lbl.setText(f"Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}")

            self._all_users_cache = User.get_all_with_details()
            self.update_hero_active_users()
            self.update_kpi_metrics()
            self.filter_users_table()
            self.update_system_analytics()
            self.update_security_user_combo()

        except Exception as e:
            logger.error(f"Admin paneli veri yenileme hatası: {e}")

    def update_hero_active_users(self):
        while self.active_users_layout.count() > 0:
            item = self.active_users_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        online_users = [u for u in self._all_users_cache if u.get('is_online') and u.get('is_active')]
        self.hero_online_count_lbl.setText(f"{len(online_users)} Kullanıcı Çevrimiçi")

        if not online_users:
            empty_lbl = QLabel("⚪ Şu anda uygulamada açık/çevrimiçi aktif kullanıcı bulunmuyor. (Tüm kullanıcılar çevrimdışı)")
            empty_lbl.setStyleSheet("""
                color: #94a3b8;
                font-size: 10pt;
                font-style: italic;
                padding: 10px 4px;
                background: transparent;
                border: none;
            """)
            self.active_users_layout.addWidget(empty_lbl)
        else:
            for u in online_users:
                user_card = QFrame()
                user_card.setStyleSheet("""
                    QFrame {
                        background-color: rgba(34, 197, 94, 0.14);
                        border: 1.5px solid rgba(34, 197, 94, 0.5);
                        border-radius: 10px;
                        padding: 6px 12px;
                    }
                    QFrame:hover {
                        background-color: rgba(34, 197, 94, 0.22);
                        border-color: #22c55e;
                    }
                """)
                card_h = QHBoxLayout(user_card)
                card_h.setContentsMargins(8, 4, 8, 4)
                card_h.setSpacing(10)

                dot = QLabel("🟢")
                dot.setStyleSheet("font-size: 12pt; background: transparent; border: none;")
                card_h.addWidget(dot)

                info_v = QVBoxLayout()
                info_v.setSpacing(2)

                uname_lbl = QLabel(f"@{u.get('username')}")
                uname_lbl.setStyleSheet("font-size: 11.5pt; font-weight: bold; color: #22c55e; background: transparent; border: none;")
                info_v.addWidget(uname_lbl)

                fname = u.get('full_name') or 'İsimsiz'
                bname = u.get('branch_name') or 'Merkez'
                sub_lbl = QLabel(f"👤 {fname} • 🏢 {bname}")
                sub_lbl.setStyleSheet("font-size: 8.5pt; color: #cbd5e1; background: transparent; border: none;")
                info_v.addWidget(sub_lbl)

                last_l = u.get('last_login')
                if last_l and isinstance(last_l, datetime):
                    time_str = last_l.strftime('%H:%M:%S')
                else:
                    time_str = "Bilinmiyor"

                time_lbl = QLabel(f"⏱️ Giriş: {time_str}")
                time_lbl.setStyleSheet("font-size: 8pt; color: #94a3b8; background: transparent; border: none;")
                info_v.addWidget(time_lbl)

                card_h.addLayout(info_v)

                logout_btn = QPushButton("Oturumu Kapat")
                logout_btn.setCursor(Qt.PointingHandCursor)
                logout_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(239, 68, 68, 0.2);
                        color: #ef4444;
                        border: 1px solid rgba(239, 68, 68, 0.6);
                        border-radius: 6px;
                        font-size: 8.5pt;
                        font-weight: bold;
                        padding: 5px 10px;
                    }
                    QPushButton:hover {
                        background-color: #ef4444;
                        color: #ffffff;
                    }
                """)
                uid = u.get('id')
                logout_btn.clicked.connect(lambda checked, user_id=uid: self.action_force_logout(user_id))
                card_h.addWidget(logout_btn)

                self.active_users_layout.addWidget(user_card)

        self.active_users_layout.addStretch()

    def update_kpi_metrics(self):
        stats = User.get_system_user_stats()
        if not stats:
            return

        total_u = stats.get('total_users', 0)
        online_u = stats.get('online_users', 0)
        active_u = stats.get('active_users', 0)
        inactive_u = stats.get('inactive_users', 0)

        v1 = self.kpi_total_users.findChild(QLabel, "val_lbl")
        s1 = self.kpi_total_users.findChild(QLabel, "sub_lbl")
        if v1: v1.setText(str(total_u))
        if s1: s1.setText(f"Aktif: {active_u} | Pasif: {inactive_u}")

        v2 = self.kpi_online_users.findChild(QLabel, "val_lbl")
        s2 = self.kpi_online_users.findChild(QLabel, "sub_lbl")
        if v2: v2.setText(str(online_u))
        if s2: s2.setText("Şu Anda Uygulamada")

        v3 = self.kpi_branches.findChild(QLabel, "val_lbl")
        if v3: v3.setText(str(stats.get('total_branches', 0)))

        v4 = self.kpi_invoices.findChild(QLabel, "val_lbl")
        if v4: v4.setText(str(stats.get('total_invoices', 0)))

        v5 = self.kpi_db_size.findChild(QLabel, "val_lbl")
        if v5: v5.setText(f"{stats.get('database_size_mb', 0.0):.2f} MB")

    def filter_users_table(self):
        search_query = self.search_input.text().strip().lower()
        filtered = []

        for u in self._all_users_cache:
            if self._current_filter == "ONLINE" and not (u.get('is_online') and u.get('is_active')):
                continue
            elif self._current_filter == "ACTIVE" and not u.get('is_active'):
                continue
            elif self._current_filter == "INACTIVE" and u.get('is_active'):
                continue

            if search_query:
                uname = (u.get('username') or '').lower()
                fname = (u.get('full_name') or '').lower()
                email = (u.get('email') or '').lower()
                branch = (u.get('branch_name') or '').lower()
                if search_query not in uname and search_query not in fname and search_query not in email and search_query not in branch:
                    continue

            filtered.append(u)

        self.populate_user_table(filtered)

    def populate_user_table(self, users: List[Dict]):
        self.user_table.setRowCount(len(users))

        for row, u in enumerate(users):
            is_online = u.get('is_online', False)
            is_active = u.get('is_active', True)
            user_id = u.get('id')

            status_item = QTableWidgetItem("🟢 Çevrimiçi" if (is_online and is_active) else "⚪ Çevrimdışı")
            if is_online and is_active:
                status_item.setForeground(QColor("#22c55e"))
            else:
                status_item.setForeground(QColor("#64748b"))
            status_item.setTextAlignment(Qt.AlignCenter)
            self.user_table.setItem(row, 0, status_item)

            uname_item = QTableWidgetItem(f"@{u.get('username')}")
            uname_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            uname_item.setForeground(QColor("#4a9eff" if not is_online else "#22c55e"))
            self.user_table.setItem(row, 1, uname_item)

            self.user_table.setItem(row, 2, QTableWidgetItem(u.get('full_name') or '-'))
            self.user_table.setItem(row, 3, QTableWidgetItem(u.get('email') or '-'))
            self.user_table.setItem(row, 4, QTableWidgetItem(u.get('phone') or '-'))
            self.user_table.setItem(row, 5, QTableWidgetItem(u.get('branch_name') or '-'))

            role_item = QTableWidgetItem(u.get('role') or 'User')
            role_item.setTextAlignment(Qt.AlignCenter)
            self.user_table.setItem(row, 6, role_item)

            act_item = QTableWidgetItem("Aktif" if is_active else "Dondurulmuş")
            act_item.setTextAlignment(Qt.AlignCenter)
            act_item.setForeground(QColor("#22c55e" if is_active else "#ef4444"))
            self.user_table.setItem(row, 7, act_item)

            last_l = u.get('last_login')
            l_str = last_l.strftime('%d.%m.%Y %H:%M') if isinstance(last_l, datetime) else '-'
            self.user_table.setItem(row, 8, QTableWidgetItem(l_str))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(6, 2, 6, 2)
            actions_layout.setAlignment(Qt.AlignCenter)
            actions_layout.setSpacing(8)

            if is_online and is_active:
                btn_logout = QPushButton("🚫 Düşür")
                btn_logout.setCursor(Qt.PointingHandCursor)
                btn_logout.setFixedHeight(26)
                btn_logout.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(239, 68, 68, 0.2);
                        color: #ef4444;
                        border: 1px solid rgba(239, 68, 68, 0.5);
                        border-radius: 4px;
                        font-size: 8.5pt;
                        padding: 2px 8px;
                    }
                    QPushButton:hover {
                        background-color: #ef4444;
                        color: #ffffff;
                    }
                """)
                btn_logout.clicked.connect(lambda checked, uid=user_id: self.action_force_logout(uid))
                actions_layout.addWidget(btn_logout)

            btn_toggle = QPushButton("Dondur" if is_active else "Aktifleştir")
            btn_toggle.setCursor(Qt.PointingHandCursor)
            btn_toggle.setFixedHeight(26)
            t_color = "#f59e0b" if is_active else "#10b981"
            btn_toggle.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {t_color};
                    border: 1px solid {t_color};
                    border-radius: 4px;
                    font-size: 8.5pt;
                    padding: 2px 10px;
                }}
                QPushButton:hover {{
                    background-color: {t_color};
                    color: #0d0d0f;
                }}
            """)
            btn_toggle.clicked.connect(lambda checked, uid=user_id, cur=is_active: self.action_toggle_user_status(uid, cur))
            actions_layout.addWidget(btn_toggle)

            self.user_table.setCellWidget(row, 9, actions_widget)

    def update_system_analytics(self):
        try:
            branch_stats = db.fetch_all("""
                SELECT b.id, b.name,
                       COUNT(u.id) as user_count,
                       COUNT(CASE WHEN u.is_online = TRUE AND u.is_active = TRUE THEN 1 END) as online_count
                FROM Branches b
                LEFT JOIN Users u ON u.branch_id = b.id
                WHERE b.is_active = TRUE
                GROUP BY b.id, b.name
                ORDER BY b.name
            """)
            self.branch_table.setRowCount(len(branch_stats))
            for r, bs in enumerate(branch_stats):
                self.branch_table.setItem(r, 0, QTableWidgetItem(str(bs.get('id'))))
                self.branch_table.setItem(r, 1, QTableWidgetItem(bs.get('name') or '-'))
                self.branch_table.setItem(r, 2, QTableWidgetItem(str(bs.get('user_count', 0))))
                on_lbl = QTableWidgetItem(f"🟢 {bs.get('online_count', 0)}")
                on_lbl.setForeground(QColor("#22c55e"))
                self.branch_table.setItem(r, 3, on_lbl)
        except Exception as e:
            logger.error(f"Şube analitiği hatası: {e}")

        try:
            tables = [
                ("Users", "Kullanıcılar"),
                ("Branches", "Şubeler"),
                ("Customers", "Müşteriler / Cariler"),
                ("Products", "Stok / Ürünler"),
                ("Invoices", "Faturalar"),
                ("InvoiceItems", "Fatura Kalemleri"),
                ("BankAccounts", "Banka Hesapları"),
                ("BankTransactions", "Banka Hareketleri"),
                ("JournalEntries", "Yevmiye Kayıtları"),
            ]
            self.db_table.setRowCount(len(tables))
            for r, (t_name, t_label) in enumerate(tables):
                count_res = db.fetch_one(f"SELECT COUNT(*) as cnt FROM {t_name}")
                cnt = count_res.get('cnt', 0) if count_res else 0
                self.db_table.setItem(r, 0, QTableWidgetItem(f"{t_label} ({t_name})"))
                cnt_item = QTableWidgetItem(str(cnt))
                cnt_item.setTextAlignment(Qt.AlignCenter)
                self.db_table.setItem(r, 1, cnt_item)
        except Exception as e:
            logger.error(f"Tablo metrikleri hatası: {e}")

    def update_security_user_combo(self):
        self.sec_user_combo.clear()
        for u in self._all_users_cache:
            uid = u.get('id')
            uname = u.get('username')
            fname = u.get('full_name') or ''
            self.sec_user_combo.addItem(f"@{uname} - {fname}", uid)

    # ==================== YÖNETİCİ EYLEMLERİ ====================

    def action_force_logout(self, user_id: int):
        reply = QMessageBox.question(
            self, "Oturumu Kapat",
            "Bu kullanıcının açık olan oturumunu sonlandırmak istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if User.force_logout(user_id):
                QMessageBox.information(self, "Başarılı", "Kullanıcının çevrimiçi oturumu sonlandırıldı.")
                self.refresh_all_data()
            else:
                QMessageBox.critical(self, "Hata", "Oturum sonlandırılamadı.")

    def action_toggle_user_status(self, user_id: int, current_active: bool):
        new_status = not current_active
        action_text = "dondurmak" if current_active else "aktifleştirmek"
        reply = QMessageBox.question(
            self, "Hesap Durumu Değiştir",
            f"Bu kullanıcının hesabını {action_text} istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if User.toggle_active_status(user_id, new_status):
                QMessageBox.information(self, "Başarılı", f"Kullanıcı hesabı başarıyla { 'aktifleştirildi' if new_status else 'donduruldu' }.")
                self.refresh_all_data()
            else:
                QMessageBox.critical(self, "Hata", "Hesap durumu güncellenemedi.")

    def action_reset_all_sessions(self):
        reply = QMessageBox.warning(
            self, "Tüm Oturumları Sıfırla",
            "⚠️ Sistemdeki tüm çevrimiçi oturumlar kapatılacak.\nDevam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if User.reset_all_online_status():
                QMessageBox.information(self, "Başarılı", "Tüm açık oturumlar sıfırlandı.")
                self.refresh_all_data()
            else:
                QMessageBox.critical(self, "Hata", "Oturumlar sıfırlanamadı.")

    def action_set_user_password(self):
        user_id = self.sec_user_combo.currentData()
        new_pwd = self.sec_new_password.text().strip()

        if not user_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir kullanıcı seçin.")
            return

        # ✅ Şifre politikası — User modelindeki tek kaynak
        is_strong, msg = User.validate_password_strength(new_pwd)
        if not is_strong:
            QMessageBox.warning(self, "Uyarı", f"Şifre politikası uyumsuz:\n{msg}")
            self.sec_new_password.setFocus()
            return

        user = User.get_by_id(user_id)
        if not user:
            QMessageBox.critical(self, "Hata", "Kullanıcı bulunamadı.")
            return

        reply = QMessageBox.question(
            self, "Şifre Güncelleme",
            f"@{user.username} kullanıcısının şifresi değiştirilecek. Onaylıyor musunuz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if user.reset_password(new_pwd):
                QMessageBox.information(self, "Başarılı", f"@{user.username} şifresi başarıyla güncellendi.")
                self.sec_new_password.clear()
            else:
                QMessageBox.critical(self, "Hata", "Şifre güncellenemedi.")