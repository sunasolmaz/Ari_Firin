# src/ui/central_window.py
"""
Genel Merkez Paneli
Tüm şubelerin toplu verilerini gösterir
"""

import os
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox, QFrame, QStackedWidget,
    QScrollArea, QGraphicsDropShadowEffect, QGridLayout, QDialog,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication
from datetime import datetime

from ..models.user import User
from ..models.branch import Branch
from ..core.database import db
from ..core.logger import logger
from .styles import AppStyles

# Genel merkez sayfaları
from .central_pages.all_dashboard_page import AllDashboardPage
from .central_pages.all_customers_page import AllCustomersPage
from .central_pages.all_invoices_page import AllInvoicesPage
from .central_pages.all_products_page import AllProductsPage
from .central_pages.all_banks_page import AllBanksPage
from .central_pages.all_transactions_page import AllTransactionsPage
from .central_pages.all_transfers_page import AllTransfersPage
from .central_pages.all_reports_page import AllReportsPage
from .central_pages.all_people_page import AllPeoplePage
from .central_pages.warehouse_page import WarehousePage
from .pages.settings_page import SettingsPage
from .pages.production_hub_page import ProductionHubPage
from .pages.payment_plans_page import PaymentPlansPage
from .update_banner import UpdateBanner
from ..services.updater_service import updater


class CentralSidebarButton(QPushButton):
    """Genel merkez sidebar butonu"""

    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(f"  {icon}   {text}", parent)
        self.setMinimumHeight(42)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {AppStyles.TEXT_SECONDARY};
                text-align: left;
                padding-left: 14px;
                border: none;
                border-radius: 8px;
                font-size: 10.5pt;
                font-weight: 500;
                margin: 1px 0;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.SIDEBAR_HOVER};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QPushButton:checked {{
                background-color: {AppStyles.SIDEBAR_ACTIVE};
                color: {AppStyles.PRIMARY};
                border-left: 3px solid {AppStyles.PRIMARY};
                font-weight: 600;
            }}
        """)


class CentralWindow(QMainWindow):
    """Genel Merkez Paneli - Tüm şubelerin toplu görünümü"""

    def __init__(self, user: User, start_page: str = "all_dashboard"):
        super().__init__()
        self.user = user
        self.start_page = start_page

        # RBAC Güvenlik Denetimi
        if not self.user or not self.user.has_permission('view_central'):
            logger.warning(f"🚨 YETKİSİZ ERİŞİM ENGELENDİ: '{getattr(user, 'username', 'anon')}' ({getattr(user, 'role', 'NoRole')}) Genel Merkez'e erişmeye çalıştı!")
            QMessageBox.critical(self, "Yetkisiz Erişim", "Genel Merkez paneline erişim yetkiniz bulunmamaktadır!\nBu panel yalnızca Genel Yönetici ve Şube Müdürleri içindir.")
            self._is_switching = True
            self.close()
            return

        # Multi-Tenant İzolasyon
        try:
            schema = self.user.get_tenant_schema() if hasattr(self.user, 'get_tenant_schema') else db.get_tenant_schema_for_user(self.user.id)
            db.set_tenant(schema)
            db.ensure_tenant_schema(schema)
        except Exception as e:
            logger.warning(f"CentralWindow tenant ayarlanamadı: {e}")

        self.pages = {}
        self.menu_buttons = []
        self._is_switching = False

        self.init_ui()
        self.navigate_to(start_page)

    def init_ui(self):
        """Arayüzü oluştur"""
        self.setWindowTitle(f"☕ Arı Fırın")
        self.setMinimumSize(1200, 750)
        self.setStyleSheet(AppStyles.get_main_style())

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(AppStyles.BG_DARK))
        palette.setColor(QPalette.Base, QColor(AppStyles.BG_DARK))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        central_widget = QWidget()
        central_widget.setAutoFillBackground(True)
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar, 1)
        main_layout.setStretch(0, 1)

        content_area = self.create_content_area()
        main_layout.addWidget(content_area, 4)
        main_layout.setStretch(1, 4)

        central_widget.setLayout(main_layout)

        self.show()
        QApplication.processEvents()
        self.setWindowState(Qt.WindowMaximized)

    # ==================== SIDEBAR ====================

    def create_sidebar(self) -> QWidget:
        """Sol sidebar"""
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(240)
        sidebar.setMaximumWidth(320)
        sidebar.setStyleSheet(f"""
            QWidget#sidebar {{
                background-color: {AppStyles.SIDEBAR_BG};
                border-right: 1px solid {AppStyles.BORDER};
            }}
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)

        # ==================== LOGO ====================
        logo_container = QWidget()
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(6, 0, 0, 0)
        logo_layout.setSpacing(8)

        logo_icon = QLabel()
        logo_icon.setAlignment(Qt.AlignCenter)
        logo_icon.setFixedSize(32, 32)
        logo_icon.setStyleSheet("background: transparent; border: none;")

        candidates = [
            os.path.join(os.path.dirname(__file__), "assets", "logo.png"),
            os.path.join(os.path.dirname(sys.executable), "src", "ui", "assets", "logo.png"),
            os.path.join(os.path.dirname(sys.executable), "_internal", "src", "ui", "assets", "logo.png"),
            os.path.join(getattr(sys, '_MEIPASS', ''), "src", "ui", "assets", "logo.png"),
            os.path.join(os.path.dirname(sys.executable), "resources", "icons", "app.png"),
            "src/ui/assets/logo.png",
            "resources/icons/app.png",
        ]
        icon_path = next((p for p in candidates if p and os.path.exists(p)), "")
        pixmap = AppStyles.load_colored_icon(icon_path, 30, "#ffffff") if icon_path else None
        if pixmap and not pixmap.isNull():
            logo_icon.setPixmap(pixmap)
        else:
            logo_icon.setText("☕")
            logo_icon.setStyleSheet("font-size: 22pt; color: #ffffff; background: transparent; border: none;")

        logo_layout.addWidget(logo_icon)

        logo_text = QLabel("ARI FIRIN")
        logo_text.setStyleSheet("""
            font-size: 14pt;
            font-weight: bold;
            font-family: "Brush Script MT", "Segoe UI", sans-serif;
            color: #ffffff;
            background: transparent;
            border: none;
        """)
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch()

        logo_container.setLayout(logo_layout)
        layout.addWidget(logo_container)

        # ==================== MERKEZ BİLGİSİ ====================
        branches = Branch.get_all(active_only=True)
        central_info = QFrame()
        central_info.setObjectName("centralInfoFrame")
        central_info.setCursor(Qt.PointingHandCursor)
        central_info.mousePressEvent = lambda e: self.navigate_to("all_dashboard")
        central_info.setStyleSheet(f"""
            QFrame#centralInfoFrame {{
                background-color: {AppStyles.SIDEBAR_HOVER};
                border-radius: 10px;
                padding: 10px 8px;
                margin: 6px 0;
                border: 1px solid {AppStyles.BORDER};
            }}
            QFrame#centralInfoFrame:hover {{
                border: 1px solid {AppStyles.PRIMARY};
            }}
            QFrame#centralInfoFrame QLabel {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """)
        central_layout = QVBoxLayout()
        central_layout.setSpacing(3)
        central_layout.setContentsMargins(0, 0, 0, 0)

        central_title = QLabel("🏠 GENEL MERKEZ")
        central_title.setStyleSheet(f"""
            font-size: 9pt;
            color: {AppStyles.TEXT_MUTED};
            letter-spacing: 0.5px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        central_layout.addWidget(central_title)

        central_name = QLabel("Ana Sayfa (Tüm Şubeler)")
        central_name.setStyleSheet(f"""
            font-size: 11pt;
            font-weight: bold;
            color: {AppStyles.PRIMARY};
            background: transparent;
            border: none;
        """)
        central_name.setWordWrap(True)
        central_layout.addWidget(central_name)

        branch_count_label = QLabel(f"🏢 Toplam {len(branches)} Aktif Şube")
        branch_count_label.setStyleSheet(f"""
            font-size: 9.5pt;
            color: {AppStyles.TEXT_MUTED};
            background: transparent;
            border: none;
        """)
        central_layout.addWidget(branch_count_label)

        central_info.setLayout(central_layout)
        layout.addWidget(central_info)

        # ==================== ŞUBE SEÇ BUTONU ====================
        branch_select_btn = QPushButton("🏢  Şube Seç")
        branch_select_btn.clicked.connect(self.open_branch_selector)
        branch_select_btn.setCursor(Qt.PointingHandCursor)
        branch_select_btn.setMinimumHeight(38)
        branch_select_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.PURPLE});
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 10pt;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PURPLE}, stop:1 {AppStyles.PRIMARY});
            }}
        """)
        layout.addWidget(branch_select_btn)

        layout.addSpacing(8)

        # ==================== MENÜ BAŞLIĞI ====================
        menu_title = QLabel("TÜM ŞUBELER")
        menu_title.setStyleSheet(f"""
            font-size: 9pt;
            color: {AppStyles.TEXT_MUTED};
            letter-spacing: 0.5px;
            font-weight: bold;
            padding: 4px 8px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(menu_title)

        # ==================== MENÜ ÖĞELERİ ====================
        menu_items = [
            ("🏠", "Ana Sayfa", "all_dashboard"),
            ("🏭", "Fırın İmalathanesi", "production_hub"),
            ("🏬", "Merkez Depo & Ambalaj", "warehouse"),
            ("👥", "Tüm Cari Hesaplar", "all_customers"),
            ("📄", "Tüm Faturalar", "all_invoices"),
            ("🛍️", "Tüm Ürünler & Stok", "all_products"),
            ("🏦", "Tüm Kasa & Bankalar", "all_banks"),
            #("💰", "Ödeme Planları & Personel", "payment_plans"),
            ("💼", "Şirket & Ortak Giderleri", "company_expenses"),
            ("📈", "Tüm Raporlar", "all_reports"),
            ("⚙️", "Ayarlar", "settings"),
        ]

        for icon, text, key in menu_items:
            btn = CentralSidebarButton(icon, text)
            btn.clicked.connect(lambda checked, k=key: self.navigate_to(k))
            layout.addWidget(btn)
            self.menu_buttons.append((key, btn))

        layout.addSpacing(8)
        layout.addStretch()

        # ==================== KULLANICI KARTI ====================
        user_card = QFrame()
        user_card.setObjectName("centralUserCard")
        user_card.setStyleSheet(f"""
            QFrame#centralUserCard {{
                background-color: {AppStyles.SIDEBAR_HOVER};
                border-radius: 10px;
                padding: 8px 6px;
                border: 1px solid {AppStyles.BORDER};
            }}
            QFrame#centralUserCard QLabel {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """)
        user_layout = QHBoxLayout()
        user_layout.setSpacing(8)
        user_layout.setContentsMargins(0, 0, 0, 0)

        avatar = QLabel(self.user.full_name[0].upper() if self.user.full_name else "U")
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.PURPLE});
            color: white;
            border-radius: 17px;
            font-size: 13pt;
            font-weight: bold;
            border: none;
        """)
        user_layout.addWidget(avatar)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(1)
        info_layout.setContentsMargins(0, 0, 0, 0)

        name = QLabel(self.user.full_name)
        name.setStyleSheet(f"""
            font-size: 9pt;
            font-weight: bold;
            color: {AppStyles.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)
        name.setWordWrap(True)
        info_layout.addWidget(name)

        role = QLabel("Genel Yönetici")
        role.setStyleSheet(f"""
            font-size: 8pt;
            color: {AppStyles.TEXT_SECONDARY};
            background: transparent;
            border: none;
        """)
        role.setWordWrap(True)
        info_layout.addWidget(role)

        user_layout.addLayout(info_layout)
        user_layout.addStretch()
        user_card.setLayout(user_layout)
        layout.addWidget(user_card)

        # ==================== GÜNCELLEME KONTROL BUTONU ====================
        update_btn = QPushButton(f"🔄 v{updater.current_version}")
        update_btn.setToolTip("Güncellemeleri Denetle")
        update_btn.clicked.connect(lambda: updater.check_for_updates(silent=False))
        update_btn.setCursor(Qt.PointingHandCursor)
        update_btn.setMinimumHeight(30)
        update_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                font-size: 8pt;
                padding: 2px 8px;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
                color: {AppStyles.PRIMARY};
                background-color: rgba(255, 255, 255, 0.04);
            }}
        """)
        layout.addWidget(update_btn)
        layout.addSpacing(4)

        # ==================== ÇIKIŞ BUTONU ====================
        logout_btn = QPushButton("🚪  Çıkış Yap")
        logout_btn.clicked.connect(self.logout)
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.setMinimumHeight(38)
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {AppStyles.RED};
                border: 1px solid {AppStyles.RED};
                border-radius: 8px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.RED};
                color: white;
            }}
        """)
        layout.addWidget(logout_btn)

        sidebar.setLayout(layout)
        return sidebar

    # ==================== İÇERİK ALANI ====================

    def create_content_area(self) -> QWidget:
        """Sağ içerik alanı"""
        content = QWidget()
        content.setStyleSheet(f"background-color: {AppStyles.BG_DARK};")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.update_banner = UpdateBanner(content)
        layout.addWidget(self.update_banner)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet(f"background-color: {AppStyles.BG_DARK};")
        layout.addWidget(self.stacked_widget)

        content.setLayout(layout)
        return content

    # ==================== SAYFA YÖNLENDİRME ====================

    def navigate_to(self, page_key: str):
        """Sayfaya git"""
        for key, btn in self.menu_buttons:
            btn.setChecked(key == page_key)

        if page_key in self.pages:
            self.stacked_widget.setCurrentWidget(self.pages[page_key])
            logger.info(f"📄 Sayfa değiştirildi: {page_key}")
            return

        try:
            page = self.create_page(page_key)
            if page:
                self.pages[page_key] = page
                self.stacked_widget.addWidget(page)
                self.stacked_widget.setCurrentWidget(page)
                logger.info(f"📄 Sayfa açıldı: {page_key}")
        except Exception as e:
            logger.error(f"❌ Sayfa açma hatası ({page_key}): {e}")
            QMessageBox.critical(self, "Hata", f"Sayfa açılamadı:\n{str(e)}")

    def create_page(self, page_key: str) -> QWidget:
        """Sayfa oluştur"""
        if page_key == "settings":
            return SettingsPage(self.user, branch_id=None, main_window=self)

        if page_key == "production_hub":
            return ProductionHubPage(self.user, branch_id=None, main_window=self)

        if page_key == "payment_plans":
            return PaymentPlansPage(self.user, branch_id=None, main_window=self)

        if page_key == "company_expenses":
            from .pages.company_expenses_page import CompanyExpensesPage
            return CompanyExpensesPage(self.user, branch_id=None, main_window=self)

        if page_key in ("all_transactions", "all_transfers"):
            return AllBanksPage(self.user, self)

        if page_key == "all_people":
            return AllCustomersPage(self.user, self)

        page_classes = {
            "all_dashboard": AllDashboardPage,
            "warehouse": WarehousePage,
            "all_customers": AllCustomersPage,
            "all_invoices": AllInvoicesPage,
            "all_products": AllProductsPage,
            "all_banks": AllBanksPage,
            "all_reports": AllReportsPage,
        }

        if page_key in page_classes:
            return page_classes[page_key](self.user, self)

        return None

    # ==================== ŞUBE SEÇİCİ ====================

    def open_branch_selector(self):
        """Şube seçici dialog aç"""
        dialog = BranchSelectorDialog(self.user, self)
        dialog.exec_()

    def switch_to_branch(self, branch_id: int, target_page: str = "invoices", target_filter: str = None):
        """Şubeye doğrudan geçiş yap"""
        try:
            from .main_window import MainWindow
            logger.info(f"🏢 Şubeye doğrudan geçiş yapılıyor: Şube ID={branch_id}, Sayfa={target_page}, Filtre={target_filter}")
            self._is_switching = True
            self.main_window = MainWindow(self.user, branch_id, initial_page=target_page, initial_filter=target_filter)
            self.main_window.show()
            self.close()
        except Exception as e:
            logger.error(f"Şube açma hatası: {e}")
            self._is_switching = False
            QMessageBox.critical(self, "Hata", f"Şube açılamadı:\n{str(e)}")

    # ==================== ÇIKIŞ ====================

    def logout(self):
        """Çıkış yap"""
        reply = QMessageBox.question(
            self, "Çıkış",
            "Çıkış yapmak istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if hasattr(self, 'user') and self.user:
                self.user.set_online(False)
            logger.info(f"👋 Kullanıcı çıkış yaptı: {self.user.username}")
            try:
                db.clear_tenant()
            except Exception as e:
                logger.warning(f"Tenant temizlenirken hata: {e}")
            self._is_switching = True
            from .login_window import LoginWindow
            self.login_window = LoginWindow()
            self.login_window.login_successful.connect(self._handle_relogin)
            self.login_window.show()
            self.close()

    def _handle_relogin(self, new_user):
        """Çıkış sonrası yeni oturum açıldığında çalışır"""
        try:
            logger.info(f"✅ Yeni kullanıcı giriş yaptı: {new_user.username}")
            schema = new_user.get_tenant_schema() if hasattr(new_user, 'get_tenant_schema') else db.get_tenant_schema_for_user(new_user.id)
            db.set_tenant(schema)
            db.ensure_tenant_schema(schema)
            if new_user.has_permission('view_central'):
                from .central_window import CentralWindow
                self._next_win = CentralWindow(new_user)
                self._next_win.show()
            else:
                branch_id = getattr(new_user, 'branch_id', None)
                if not branch_id:
                    row = db.fetch_one("SELECT id FROM Branches WHERE is_active = TRUE ORDER BY id LIMIT 1")
                    if row:
                        branch_id = row['id']
                        new_user.branch_id = branch_id
                if branch_id:
                    from .main_window import MainWindow
                    self._next_win = MainWindow(new_user, branch_id)
                    self._next_win.show()
                else:
                    from .branch_select import BranchSelectWindow
                    self._next_win = BranchSelectWindow(new_user)
                    self._next_win.show()
            if hasattr(self, 'login_window') and self.login_window:
                self.login_window.hide()
                self.login_window.close()
                self.login_window = None
        except Exception as e:
            logger.error(f"❌ Yeniden oturum açma hatası: {e}")
            QMessageBox.critical(None, "Hata", f"Yeni oturum açılamadı: {e}")

    def closeEvent(self, event):
        """Kapanış"""
        if getattr(self, '_is_switching', False):
            event.accept()
            return

        reply = QMessageBox.question(
            self, "Çıkış",
            "Uygulamadan çıkmak istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if hasattr(self, 'user') and self.user:
                self.user.set_online(False)
            logger.info(f"Uygulama kapatıldı: {self.user.username}")
            try:
                db.clear_tenant()
            except Exception:
                pass
            event.accept()
        else:
            event.ignore()


# ==================== ŞUBE SEÇİCİ DIALOG (DÜZELTİLMİŞ) ====================


class BranchSelectorDialog(QDialog):
    """Şube seçici dialog - hangi şubeye geçmek istediğini sorar"""

    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self.user = user

        self.setWindowTitle("🏢 Şube Seç")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(AppStyles.get_main_style())

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        # Başlık
        title = QLabel("🏢 Hangi Şubeye Gitmek İstersiniz?")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            font-size: 22px;
            font-weight: bold;
            color: {AppStyles.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)
        layout.addWidget(title)

        subtitle = QLabel("Aşağıdaki şubelerden birini seçerek o şubenin paneline geçebilirsiniz")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"""
            font-size: 14px;
            color: {AppStyles.TEXT_SECONDARY};
            background: transparent;
            border: none;
            margin-bottom: 15px;
        """)
        layout.addWidget(subtitle)

        branches = Branch.get_all(active_only=True)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: transparent;")

        # 2 Sütunlu Grid
        grid = QGridLayout()
        grid.setSpacing(20)
        grid.setContentsMargins(10, 10, 10, 10)

        col_count = 2

        for i, branch in enumerate(branches):
            card = self.create_branch_card(branch)
            row = i // col_count
            col = i % col_count
            grid.addWidget(card, row, col)

        # Merkez Depo Kartı
        depo_card = self.create_warehouse_card()
        next_idx = len(branches)
        row = next_idx // col_count
        col = next_idx % col_count
        grid.addWidget(depo_card, row, col)

        scroll_widget.setLayout(grid)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # İptal butonu
        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(40)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                font-weight: bold;
                padding: 0 30px;
            }}
            QPushButton:hover {{ background-color: {AppStyles.BG_LIGHT}; }}
        """)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def create_branch_card(self, branch: Branch) -> QFrame:
        """Şube kartı"""
        card = QFrame()
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        card.setMinimumWidth(400)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 5)
        card.setGraphicsEffect(shadow)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)

        is_imalat = "imalat" in (branch.name or "").lower()

        # Üst Kısım
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)

        icon = QLabel("🏭" if is_imalat else "🏢")
        icon.setFixedSize(50, 50)
        icon.setAlignment(Qt.AlignCenter)
        grad_colors = f"stop:0 {AppStyles.SUCCESS}, stop:1 {AppStyles.CYAN}" if is_imalat else f"stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.PURPLE}"
        icon.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, {grad_colors});
            border-radius: 25px;
            font-size: 22px;
            border: none;
        """)
        top_layout.addWidget(icon)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        b_title = f"{branch.name} (Üretim & Dağıtım)" if is_imalat else branch.name
        name = QLabel(b_title)
        name.setWordWrap(True)
        name.setStyleSheet(f"""
            font-size: 16px;
            font-weight: bold;
            color: {AppStyles.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)
        title_layout.addWidget(name)

        if branch.city:
            city = QLabel(f"📍 {branch.city}")
            city.setStyleSheet(f"""
                font-size: 12px;
                color: {AppStyles.TEXT_SECONDARY};
                background: transparent;
                border: none;
            """)
            title_layout.addWidget(city)
        
        top_layout.addLayout(title_layout)
        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        # Alt Kısım - İstatistik
        if is_imalat:
            stats_label = QLabel("🥖 Günlük Fırın İmalatı & 3 Şubeye Sevkiyat Merkezi")
            stats_label.setStyleSheet(f"""
                font-size: 12px;
                color: {AppStyles.CYAN};
                font-weight: 600;
                background: transparent;
                border: none;
                margin-top: 5px;
            """)
            main_layout.addWidget(stats_label)
        else:
            stats = self.get_branch_stats(branch.id)
            stats_label = QLabel(
                f"👥 {stats.get('customer_count', 0)} müşteri  •  "
                f"📄 {stats.get('invoice_count', 0)} fatura"
            )
            stats_label.setStyleSheet(f"""
                font-size: 12px;
                color: {AppStyles.TEXT_MUTED};
                background: transparent;
                border: none;
                margin-top: 5px;
            """)
            main_layout.addWidget(stats_label)

        main_layout.addStretch()

        # Buton
        select_btn = QPushButton("Şubeye Gir →")
        select_btn.clicked.connect(lambda: self.select_branch(branch))
        select_btn.setMinimumHeight(40)
        select_btn.setCursor(Qt.PointingHandCursor)
        btn_grad = f"stop:0 {AppStyles.SUCCESS}, stop:1 {AppStyles.CYAN}" if is_imalat else f"stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN}"
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, {btn_grad});
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        main_layout.addWidget(select_btn)

        card.setLayout(main_layout)
        card.mousePressEvent = lambda e, b=branch: self.select_branch(b)

        return card

    def get_branch_stats(self, branch_id: int) -> dict:
        """Şube istatistiklerini al"""
        try:
            stats = db.fetch_one("""
                SELECT 
                    (SELECT COUNT(*) FROM Customers WHERE branch_id = %s AND is_active = TRUE) as customer_count,
                    (SELECT COUNT(*) FROM Invoices WHERE branch_id = %s) as invoice_count
            """, (branch_id, branch_id))
            return stats if stats else {}
        except:
            return {}

    def select_branch(self, branch: Branch):
        """Şubeyi seç ve o şubenin paneline geç"""
        try:
            logger.info(f"✅ Şube seçildi: {branch.name}")
            is_imalat = "imalat" in (branch.name or "").lower()

            from .main_window import MainWindow
            initial_pg = "production_hub" if is_imalat else "dashboard"
            self.main_window = MainWindow(self.user, branch.id, initial_page=initial_pg)
            self.main_window.show()

            if self.parent():
                self.parent()._is_switching = True
                self.parent().close()

            self.accept()
        except Exception as e:
            logger.error(f"Şube seçme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Şube açılamadı:\n{str(e)}")

    def create_warehouse_card(self) -> QFrame:
        """Merkez Depo Özel Alan Kartı"""
        card = QFrame()
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        card.setMinimumWidth(400)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.WARNING}60;
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {AppStyles.WARNING};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 5)
        card.setGraphicsEffect(shadow)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)

        icon = QLabel("🏬")
        icon.setFixedSize(50, 50)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {AppStyles.WARNING}, stop:1 {AppStyles.PRIMARY});
            border-radius: 25px;
            font-size: 22px;
            border: none;
        """)
        top_layout.addWidget(icon)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        name = QLabel("Merkez Depo & Lojistik")
        name.setWordWrap(True)
        name.setStyleSheet(f"""
            font-size: 16px;
            font-weight: bold;
            color: {AppStyles.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)
        title_layout.addWidget(name)

        desc = QLabel("📦 Hammadde, Un, Ambalaj & Şube Dağıtımı")
        desc.setStyleSheet(f"""
            font-size: 12px;
            color: {AppStyles.WARNING};
            font-weight: 500;
            background: transparent;
            border: none;
        """)
        title_layout.addWidget(desc)

        top_layout.addLayout(title_layout)
        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        stats_label = QLabel("Toptan Stok Yönetimi • Şube Dağıtım & Sevkiyat")
        stats_label.setStyleSheet(f"""
            font-size: 12px;
            color: {AppStyles.TEXT_MUTED};
            background: transparent;
            border: none;
            margin-top: 5px;
        """)
        main_layout.addWidget(stats_label)

        main_layout.addStretch()

        select_btn = QPushButton("Depoya Gir →")
        select_btn.clicked.connect(self.select_warehouse)
        select_btn.setMinimumHeight(40)
        select_btn.setCursor(Qt.PointingHandCursor)
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.WARNING}, stop:1 {AppStyles.PRIMARY});
                color: black;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        main_layout.addWidget(select_btn)

        card.setLayout(main_layout)
        card.mousePressEvent = lambda e: self.select_warehouse()
        return card

    def select_warehouse(self):
        """Merkez Depo Bağımsız Alanına Geç"""
        try:
            logger.info("🏬 Merkez Depo seçildi")
            from .warehouse_window import WarehouseWindow
            self.warehouse_window = WarehouseWindow(self.user)
            self.warehouse_window.show()

            if self.parent():
                self.parent()._is_switching = True
                self.parent().close()

            self.accept()
        except Exception as e:
            logger.error(f"Depo seçme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Depo açılamadı:\n{str(e)}")