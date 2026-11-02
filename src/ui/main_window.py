import os
# src/ui/main_window.py
"""
Ana Pencere - Parabol Tarzı Sidebar + Sayfa Yönlendirme
Sol panel daraltıldı, üst kartlar düzeltildi
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox, QFrame, QStackedWidget,
    QScrollArea, QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, QDate
from PyQt5.QtGui import QFont, QColor, QIcon
from datetime import datetime

from ..models.user import User
from ..models.branch import Branch
from ..core.database import db
from ..core.logger import logger
from ..services.report_service import ReportService
from ..services.archiver_service import ArchiverService
from ..services.excel_service import ExcelService
from .styles import AppStyles

# Sayfaları import et
from .pages.dashboard_page import DashboardPage
from .pages.invoices_page import InvoicesPage
from .pages.products_page import ProductsPage
from .pages.bank_page import BankPage
from .pages.transactions_page import TransactionsPage
from .pages.transfers_page import TransfersPage
from .pages.people_page import PeoplePage
from .pages.reports_page import ReportsPage
from .pages.daily_turnover_page import DailyTurnoverPage
from .pages.payment_plans_page import PaymentPlansPage
from .pages.stock_count_page import StockCountPage
from .update_banner import UpdateBanner
from ..services.updater_service import updater


class SidebarButton(QPushButton):
    """Sidebar menü butonu"""

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


class MainWindow(QMainWindow):
    """Ana pencere - Parabol tarzı sidebar + içerik"""

    def __init__(self, user: User, branch_id: int, initial_page: str = "dashboard", initial_filter: str = None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id

        # Multi-Tenant İzolasyon: Giriş yapan kullanıcının özel şemasını aktif et
        try:
            schema = self.user.get_tenant_schema() if hasattr(self.user, 'get_tenant_schema') else db.get_tenant_schema_for_user(self.user.id)
            db.set_tenant(schema)
            db.ensure_tenant_schema(schema)
        except Exception as e:
            logger.warning(f"MainWindow tenant ayarlanamadı: {e}")

        self.report_service = ReportService()
        self.archiver = ArchiverService()
        self.excel_service = ExcelService()

        self.pages = {}
        self.menu_buttons = []
        self._is_switching = False

        self.init_ui()
        self.navigate_to(initial_page)

        if initial_page == "invoices":
            inv_page = self.pages.get("invoices")
            if inv_page:
                if hasattr(inv_page, 'start_date'):
                    inv_page.start_date.setDate(QDate.currentDate().addDays(-90))
                if hasattr(inv_page, 'end_date'):
                    inv_page.end_date.setDate(QDate.currentDate().addDays(60))
                if initial_filter and hasattr(inv_page, 'status_combo'):
                    idx = inv_page.status_combo.findText(initial_filter)
                    if idx >= 0:
                        inv_page.status_combo.setCurrentIndex(idx)
                inv_page.load_invoices()

    def init_ui(self):
        """Arayüzü oluştur"""
        branch = Branch.get_by_id(self.branch_id)
        self.setWindowTitle(f"☕ Muhasebe Uygulaması - {branch.name if branch else 'Şube'}")
        self.setMinimumSize(1200, 750)
        self.showMaximized()
        self.setStyleSheet(AppStyles.get_main_style())

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Ana layout (yatay: sidebar + içerik)
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ✅ Sol Sidebar (sabit dar genişlik)
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar, 1)
        main_layout.setStretch(0, 1)  # Sidebar: 1 birim

        # ✅ Sağ İçerik Alanı (geniş)
        content_area = self.create_content_area()
        main_layout.addWidget(content_area, 4)
        main_layout.setStretch(1, 4)  # İçerik: 4 birim (daha geniş)

        central_widget.setLayout(main_layout)

    # ==================== SIDEBAR ====================

    def create_sidebar(self) -> QWidget:
        """Sol sidebar oluştur"""
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        # ✅ Sabit genişlik — ana sayfa ile aynı
        sidebar.setFixedWidth(260)
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

        icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
        pixmap = AppStyles.load_colored_icon(icon_path, 30, "#ffffff")
        if not pixmap.isNull():
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

        # ==================== ŞUBE BİLGİSİ & SEÇİCİ ====================
        branch = Branch.get_by_id(self.branch_id)
        branch_info = QFrame()
        branch_info.setObjectName("mainBranchInfo")
        branch_info.setStyleSheet(f"""
            QFrame#mainBranchInfo {{
                background-color: {AppStyles.SIDEBAR_HOVER};
                border-radius: 10px;
                padding: 10px 10px;
                margin: 6px 0;
                border: 1px solid {AppStyles.BORDER};
            }}
            QFrame#mainBranchInfo QLabel {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """)
        branch_layout = QVBoxLayout()
        branch_layout.setSpacing(4)
        branch_layout.setContentsMargins(0, 0, 0, 0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        branch_label = QLabel("📍 AKTİF ŞUBE")
        branch_label.setStyleSheet(f"""
            font-size: 9pt;
            color: {AppStyles.TEXT_MUTED};
            letter-spacing: 0.5px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        header_layout.addWidget(branch_label)
        header_layout.addStretch()

        if self.user and self.user.has_permission('branch_switch'):
            change_branch_btn = QPushButton("Değiştir ▾")
            change_branch_btn.setCursor(Qt.PointingHandCursor)
            change_branch_btn.clicked.connect(self.open_branch_selector)
            change_branch_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {AppStyles.PRIMARY}25;
                    color: {AppStyles.PRIMARY};
                    border: 1px solid {AppStyles.PRIMARY}50;
                    border-radius: 5px;
                    font-size: 9pt;
                    font-weight: bold;
                    padding: 3px 8px;
                }}
                QPushButton:hover {{
                    background: {AppStyles.PRIMARY};
                    color: white;
                }}
            """)
            header_layout.addWidget(change_branch_btn)

        branch_layout.addLayout(header_layout)

        branch_name = QLabel(branch.name if branch else "Bilinmeyen")
        branch_name.setStyleSheet(f"""
            font-size: 11pt;
            font-weight: bold;
            color: {AppStyles.PRIMARY};
            background: transparent;
            border: none;
        """)
        branch_name.setWordWrap(True)
        branch_layout.addWidget(branch_name)

        branch_info.setLayout(branch_layout)
        layout.addWidget(branch_info)

        # ==================== GENEL MERKEZ BUTONU ====================
        if self.user and self.user.has_permission('view_central'):
            go_central_btn = QPushButton("🏢  Genel Merkez'e Dön")
            go_central_btn.setCursor(Qt.PointingHandCursor)
            go_central_btn.clicked.connect(self.go_to_central)
            go_central_btn.setMinimumHeight(38)
            go_central_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.PURPLE});
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 9.5pt;
                    padding: 0 12px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {AppStyles.PURPLE}, stop:1 {AppStyles.PRIMARY});
                }}
            """)
            layout.addWidget(go_central_btn)
            layout.addSpacing(6)

        # ==================== MENÜ BAŞLIĞI ====================
        menu_title = QLabel("ANA MENÜ")
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
        is_bakery = bool(branch and ("imalat" in (branch.name or "").lower() or getattr(branch, 'branch_type', '') == 'bakery'))
        if is_bakery:
            menu_items = [
                ("🏭", "Üretim & Dağıtım Hub'ı", "production_hub"),
                ("🚚", "Stok & Sevkiyat Takibi", "products"),
                ("🏷️", "İmalathane Fiyat Listesi", "bakery_prices"),
                ("👥", "Alıcı Kişiler & Cariler", "bakery_customers"),
                ("🥬", "Tedarik & Malzeme Kabul", "bakery_supplies"),
                ("📄", "Faturalar & İrsaliyeler", "invoices"),
                ("💰", "Ödeme Planları & Personel", "payment_plans"),
                ("🪙", "Günlük Ciro & Kasa", "daily_turnover"),
                ("📈", "İmalathane Raporları", "reports"),
                ("⚙️", "Ayarlar", "settings"),
            ]
        else:
            menu_items = [
                ("📊", "Panel", "dashboard"),
                ("🪙", "Günlük Ciro & Kasa", "daily_turnover"),
                ("📄", "Faturalar", "invoices"),
                ("📦", "Stok Sayımı", "stock_count"),
                ("🚚", "Stok & Sevkiyat Takibi", "products"),
                ("🏦", "Kasa & Banka", "bank"),
                ("👥", "Cari Hesaplar", "people"),
                ("💰", "Ödeme Planları & Personel", "payment_plans"),
                ("📈", "Gelişmiş Raporlar", "reports"),
                ("⚙️", "Ayarlar", "settings"),
            ]

        for icon, text, key in menu_items:
            btn = SidebarButton(icon, text)
            btn.clicked.connect(lambda checked, k=key: self.navigate_to(k))
            layout.addWidget(btn)
            self.menu_buttons.append((key, btn))

        layout.addStretch()

        # ==================== ŞUBE SEÇ BUTONU ====================
        if self.user and self.user.has_permission('branch_switch'):
            branch_select_btn = QPushButton("🏢  ŞUBE SEÇ")
            branch_select_btn.clicked.connect(self.open_branch_selector)
            branch_select_btn.setCursor(Qt.PointingHandCursor)
            branch_select_btn.setMinimumHeight(40)
            branch_select_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 10.5pt;
                    letter-spacing: 1px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
                }}
            """)
            layout.addWidget(branch_select_btn)
            layout.addSpacing(10)

        # ==================== KULLANICI KARTI ====================
        user_card = QFrame()
        user_card.setObjectName("mainUserCard")
        user_card.setStyleSheet(f"""
            QFrame#mainUserCard {{
                background-color: {AppStyles.SIDEBAR_HOVER};
                border-radius: 10px;
                padding: 8px 6px;
                border: 1px solid {AppStyles.BORDER};
            }}
            QFrame#mainUserCard QLabel {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """)
        user_layout = QHBoxLayout()
        user_layout.setSpacing(8)
        user_layout.setContentsMargins(0, 0, 0, 0)

        # Avatar (küçültüldü)
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

        # Bilgi
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

        role = QLabel(self.user.role)
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

        # OTA Canlı Güncelleme Banner'ı
        self.update_banner = UpdateBanner(content)
        layout.addWidget(self.update_banner)

        # Stacked widget (sayfalar arası geçiş)
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
        if page_key == "dashboard":
            return DashboardPage(self.user, self.branch_id, self)

        if page_key == "settings":
            from .pages.settings_page import SettingsPage
            return SettingsPage(self.user, self.branch_id, self)

        if page_key == "payment_plans":
            return PaymentPlansPage(self.user, self.branch_id, self)

        if page_key == "production_hub":
            from .pages.production_hub_page import ProductionHubPage
            return ProductionHubPage(self.user, self.branch_id, self)

        if page_key == "bakery_prices":
            from .pages.bakery_price_list_page import BakeryPriceListPage
            return BakeryPriceListPage(self.user, self.branch_id, self)

        if page_key == "bakery_supplies":
            from .pages.bakery_supplies_page import BakerySuppliesPage
            return BakerySuppliesPage(self.user, self.branch_id, self)

        if page_key == "bakery_customers":
            return PeoplePage(self.user, self.branch_id, self, default_type="Müşteri", title_override="👥 İmalathane Alıcı Kişileri")

        if page_key == "warehouse":
            from .central_pages.warehouse_page import WarehousePage
            return WarehousePage(self.user, self)

        if page_key == "company_expenses":
            from .pages.company_expenses_page import CompanyExpensesPage
            return CompanyExpensesPage(self.user, self.branch_id, self)

        # Geriye dönük uyumluluk: Birleşen Kasa & Banka ekranına yönlendir
        if page_key in ("transactions", "transfers"):
            return self.create_page("bank")

        page_classes = {
            "daily_turnover": DailyTurnoverPage,
            "invoices": InvoicesPage,
            "products": ProductsPage,
            "stock_count": StockCountPage,
            "bank": BankPage,
            "people": PeoplePage,
            "reports": ReportsPage,
        }

        if page_key in page_classes:
            return page_classes[page_key](self.user, self.branch_id, self)

        return None

    # ==================== YARDIMCI FONKSİYONLAR ====================

    def go_to_central(self):
        """Genel Merkez ana paneline dön"""
        if not self.user or not self.user.has_permission('view_central'):
            QMessageBox.warning(self, "Yetkisiz İşlem", "Genel Merkez paneline erişim yetkiniz bulunmamaktadır.")
            return
        from .central_window import CentralWindow
        self._is_switching = True
        self.central_window = CentralWindow(self.user)
        self.central_window.show()
        self.close()

    def go_to_imalathane(self):
        """İmalathane üretim merkezini aç"""
        self.navigate_to("production_hub")

    def open_branch_selector(self):
        """Şube seçici dialog aç"""
        if not self.user or not self.user.has_permission('branch_switch'):
            QMessageBox.warning(self, "Yetkisiz İşlem", "Şube değiştirme yetkiniz bulunmamaktadır.")
            return
        from .central_window import BranchSelectorDialog
        dialog = BranchSelectorDialog(self.user, self)
        dialog.exec_()

    def change_branch(self):
        """Şube değiştir"""
        from .branch_select import BranchSelectWindow
        self.branch_window = BranchSelectWindow(self.user)
        self.branch_window.show()
        self._is_switching = True
        self.close()

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
            # Veritabanı tenant oturumunu temizle
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