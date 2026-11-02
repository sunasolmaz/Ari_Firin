# src/ui/warehouse_window.py
"""
Merkez Depo & Lojistik Özel Alan Penceresi
Tıpkı şube ve imalathane gibi bağımsız çalışan, özel sidebar ve menü öğelerine sahip depo yönetim ekranı.
"""

import os
from datetime import datetime, date
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QDoubleSpinBox, QMessageBox, QFileDialog, QHeaderView,
    QGraphicsDropShadowEffect, QScrollArea, QTabWidget, QDialog,
    QDateEdit, QTextEdit, QDialogButtonBox, QCheckBox, QStackedWidget,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont
import pandas as pd

from ..models.user import User
from ..models.branch import Branch
from ..core.database import db
from ..core.logger import logger
from ..services.warehouse_service import warehouse_service
from .styles import AppStyles
from .components.sidebar_button import SidebarButton
from .central_pages.warehouse_page import (
    AddWarehouseProductDialog, EditWarehouseProductDialog,
    StockInDialog, StockOutDialog, DispatchDialog, EditMovementDialog
)
from .pages.people_page import PeoplePage


class WarehouseWindow(QMainWindow):
    """Merkez Depo & Lojistik Bağımsız Yönetim Penceresi"""

    def __init__(self, user: User, initial_page: str = "dashboard"):
        super().__init__()
        self.user = user

        # Multi-Tenant İzolasyon
        try:
            schema = self.user.get_tenant_schema() if hasattr(self.user, 'get_tenant_schema') else db.get_tenant_schema_for_user(self.user.id)
            db.set_tenant(schema)
            db.ensure_tenant_schema(schema)
        except Exception as e:
            logger.warning(f"WarehouseWindow tenant ayarlanamadı: {e}")

        # Depo Şube Kimliği (branch_id)
        self.branch_id = None
        try:
            depo_row = db.fetch_one("SELECT id FROM Branches WHERE branch_type = 'warehouse' OR LOWER(name) LIKE '%%depo%%' LIMIT 1")
            if depo_row:
                self.branch_id = depo_row['id']
        except Exception as e:
            logger.warning(f"Depo branch_id alınamadı: {e}")

        self.pages = {}
        self.menu_buttons = []
        self._is_switching = False

        self.init_ui()
        self.navigate_to(initial_page)

    def init_ui(self):
        self.setWindowTitle("🏬 ARI FIRIN - Merkez Depo & Lojistik Yönetimi")
        self.setMinimumSize(1200, 750)
        self.showMaximized()
        self.setStyleSheet(AppStyles.get_main_style())

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sol Sidebar
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar, 1)

        # Sağ İçerik Alanı
        content_area = self.create_content_area()
        main_layout.addWidget(content_area, 4)

        central_widget.setLayout(main_layout)

    # ==================== SIDEBAR ====================

    def create_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("warehouseSidebar")
        sidebar.setMinimumWidth(240)
        sidebar.setMaximumWidth(320)
        sidebar.setStyleSheet(f"""
            QWidget#warehouseSidebar {{
                background-color: {AppStyles.SIDEBAR_BG};
                border-right: 1px solid {AppStyles.BORDER};
            }}
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)

        # 1. Logo
        logo_container = QWidget()
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(6, 0, 0, 0)
        logo_layout.setSpacing(8)

        logo_icon = QLabel("🏬")
        logo_icon.setAlignment(Qt.AlignCenter)
        logo_icon.setFixedSize(34, 34)
        logo_icon.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {AppStyles.WARNING}, stop:1 {AppStyles.PRIMARY});
            border-radius: 17px;
            font-size: 16pt;
            border: none;
        """)
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

        # 2. Aktif Alan Kartı (Merkez Depo)
        area_info = QFrame()
        area_info.setObjectName("mainWarehouseInfo")
        area_info.setStyleSheet(f"""
            QFrame#mainWarehouseInfo {{
                background-color: {AppStyles.SIDEBAR_HOVER};
                border-radius: 10px;
                padding: 10px 10px;
                margin: 6px 0;
                border: 1px solid {AppStyles.WARNING}60;
            }}
        """)
        area_layout = QVBoxLayout(area_info)
        area_layout.setSpacing(3)
        area_layout.setContentsMargins(0, 0, 0, 0)

        header_layout = QHBoxLayout()
        area_label = QLabel("🏬 AKTİF ALAN")
        area_label.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.WARNING}; font-weight: bold; letter-spacing: 0.5px;")
        header_layout.addWidget(area_label)
        header_layout.addStretch()

        if self.user and self.user.has_permission('branch_switch'):
            change_btn = QPushButton("Değiştir ▾")
            change_btn.setCursor(Qt.PointingHandCursor)
            change_btn.clicked.connect(self.open_branch_selector)
            change_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {AppStyles.WARNING}25;
                    color: {AppStyles.WARNING};
                    border: 1px solid {AppStyles.WARNING}50;
                    border-radius: 5px;
                    font-size: 8.5pt;
                    font-weight: bold;
                    padding: 2px 6px;
                }}
                QPushButton:hover {{
                    background: {AppStyles.WARNING};
                    color: black;
                }}
            """)
            header_layout.addWidget(change_btn)

        area_layout.addLayout(header_layout)

        area_title = QLabel("Merkez Depo & Lojistik")
        area_title.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        area_layout.addWidget(area_title)

        area_sub = QLabel("Hammadde, Un & Şube Dağıtım")
        area_sub.setStyleSheet("font-size: 8.5pt; color: #94a3b8;")
        area_layout.addWidget(area_sub)
        layout.addWidget(area_info)

        # 3. Genel Merkez Butonu
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

        # 4. Menü Başlığı
        menu_title = QLabel("DEPO MENÜSÜ")
        menu_title.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_MUTED}; font-weight: bold; letter-spacing: 0.5px; padding: 4px 8px;")
        layout.addWidget(menu_title)

        # 5. Özel Depo Menü Öğeleri
        menu_items = [
            ("📊", "Depo Özeti & Panel", "dashboard"),
            ("📦", "Envanter & Stok Durumu", "inventory"),
            ("🚚", "Şubelere Sevkiyat Takibi", "dispatches"),
            ("📥", "Malzeme Kabul & Giriş", "stock_in"),
            ("📤", "Fire & Zayiat Çıkışı", "stock_out"),
            ("👥", "Tedarikçi Carileri", "suppliers"),
            ("📈", "Depo Hareket Raporu", "movements"),
        ]

        for icon, text, key in menu_items:
            btn = SidebarButton(icon, text)
            btn.clicked.connect(lambda checked, k=key: self.navigate_to(k))
            layout.addWidget(btn)
            self.menu_buttons.append((key, btn))

        layout.addStretch()

        # 6. Şube / Alan Seç Butonu
        if self.user and self.user.has_permission('branch_switch'):
            branch_select_btn = QPushButton("🏢  ŞUBE / ALAN SEÇ")
            branch_select_btn.clicked.connect(self.open_branch_selector)
            branch_select_btn.setCursor(Qt.PointingHandCursor)
            branch_select_btn.setMinimumHeight(38)
            branch_select_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 10pt;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
                }}
            """)
            layout.addWidget(branch_select_btn)
            layout.addSpacing(6)

        # 7. Kullanıcı Kartı
        user_card = QFrame()
        user_card.setObjectName("warehouseUserCard")
        user_card.setStyleSheet(f"""
            QFrame#warehouseUserCard {{
                background-color: {AppStyles.SIDEBAR_HOVER};
                border-radius: 10px;
                padding: 8px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        u_lay = QHBoxLayout(user_card)
        u_lay.setSpacing(8)
        u_lay.setContentsMargins(0, 0, 0, 0)

        avatar = QLabel(self.user.full_name[0].upper() if self.user.full_name else "U")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {AppStyles.WARNING}, stop:1 {AppStyles.PRIMARY});
            color: white; border-radius: 16px; font-weight: bold; font-size: 12pt;
        """)
        u_lay.addWidget(avatar)

        u_info = QVBoxLayout()
        u_info.setSpacing(1)
        name_lbl = QLabel(self.user.full_name)
        name_lbl.setStyleSheet("font-size: 9pt; font-weight: bold; color: white;")
        u_info.addWidget(name_lbl)
        role_lbl = QLabel("Merkez Depo Sorumlusu" if self.user.role == "Admin" else self.user.role)
        role_lbl.setStyleSheet("font-size: 8pt; color: #94a3b8;")
        u_info.addWidget(role_lbl)
        u_lay.addLayout(u_info)
        layout.addWidget(user_card)

        # 8. Çıkış Butonu
        logout_btn = QPushButton("🚪  Çıkış Yap")
        logout_btn.clicked.connect(self.logout)
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.setMinimumHeight(34)
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {AppStyles.RED};
                border: 1px solid {AppStyles.RED};
                border-radius: 6px;
                font-weight: bold;
                font-size: 9pt;
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
        content = QWidget()
        content.setStyleSheet(f"background-color: {AppStyles.BG_DARK};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet(f"background-color: {AppStyles.BG_DARK};")
        layout.addWidget(self.stacked_widget)

        return content

    def navigate_to(self, page_key: str):
        for key, btn in self.menu_buttons:
            btn.setChecked(key == page_key)

        if page_key in self.pages:
            self.stacked_widget.setCurrentWidget(self.pages[page_key])
            if hasattr(self.pages[page_key], 'load_data'):
                self.pages[page_key].load_data()
            return

        try:
            page = self.create_page(page_key)
            if page:
                self.pages[page_key] = page
                self.stacked_widget.addWidget(page)
                self.stacked_widget.setCurrentWidget(page)
                logger.info(f"🏬 Depo sayfası açıldı: {page_key}")
        except Exception as e:
            logger.error(f"❌ Depo sayfası açma hatası ({page_key}): {e}")
            QMessageBox.critical(self, "Hata", f"Depo sayfası açılamadı:\n{str(e)}")

    def create_page(self, page_key: str) -> QWidget:
        if page_key == "dashboard":
            return WarehouseDashboardView(self.user, self)
        elif page_key == "inventory":
            return WarehouseInventoryView(self.user, self)
        elif page_key == "dispatches":
            return WarehouseDispatchesView(self.user, self)
        elif page_key == "stock_in":
            return WarehouseStockInOutView(self.user, movement_type='IN', parent=self)
        elif page_key == "stock_out":
            return WarehouseStockInOutView(self.user, movement_type='OUT', parent=self)
        elif page_key == "suppliers":
            return PeoplePage(self.user, self.branch_id, self, default_type="Tedarikçi", title_override="👥 Depo Tedarikçi Carileri")
        elif page_key == "movements":
            return WarehouseStockInOutView(self.user, movement_type='ALL', parent=self)
        return QWidget()

    def open_branch_selector(self):
        from .central_window import BranchSelectorDialog
        dialog = BranchSelectorDialog(self.user, self)
        dialog.exec_()

    def go_to_central(self):
        reply = QMessageBox.question(
            self, "Genel Merkez",
            "Genel Merkez Paneline dönmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            from .central_window import CentralWindow
            self._is_switching = True
            self.central_win = CentralWindow(self.user)
            self.central_win.show()
            self.close()

    def logout(self):
        reply = QMessageBox.question(
            self, "Çıkış",
            "Oturumunuzu kapatmak istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                db.clear_tenant()
            except Exception as e:
                logger.warning(f"Tenant temizlenirken hata: {e}")
            from .login_window import LoginWindow
            self._is_switching = True
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
            from .central_window import CentralWindow
            self._next_win = CentralWindow(new_user)
            self._next_win.show()
            if hasattr(self, 'login_window') and self.login_window:
                self.login_window.hide()
                self.login_window.close()
                self.login_window = None
        except Exception as e:
            logger.error(f"❌ Yeniden oturum açma hatası: {e}")
            QMessageBox.critical(None, "Hata", f"Yeni oturum açılamadı: {e}")


# ==================== DEPO SAYFA GÖRÜNÜMLERİ ====================

class WarehouseDashboardView(QWidget):
    """Depo Özeti, KPI Kartları ve Hızlı Aksiyon Paneli"""

    def __init__(self, user: User, main_window: WarehouseWindow):
        super().__init__()
        self.user = user
        self.main_window = main_window
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        # Başlık ve Hızlı Butonlar
        top_bar = QHBoxLayout()
        t_box = QVBoxLayout()
        title = QLabel("📊 Merkez Depo Kontrol Paneli")
        title.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        subtitle = QLabel("Hammadde stok dengeleri, kritik ürünler ve şubelere sevkiyat özeti")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 10pt;")
        t_box.addWidget(title)
        t_box.addWidget(subtitle)
        top_bar.addLayout(t_box)
        top_bar.addStretch()

        btn_dispatch = QPushButton("🚚 Yeni Sevkiyat Yap")
        btn_dispatch.setStyleSheet(f"background: {AppStyles.PRIMARY}; color: white; font-weight: bold; border-radius: 8px; padding: 10px 18px;")
        btn_dispatch.clicked.connect(self.quick_dispatch)
        top_bar.addWidget(btn_dispatch)

        btn_stock_in = QPushButton("📥 Malzeme Kabul (Giriş)")
        btn_stock_in.setStyleSheet("background: #10b981; color: white; font-weight: bold; border-radius: 8px; padding: 10px 18px;")
        btn_stock_in.clicked.connect(self.quick_stock_in)
        top_bar.addWidget(btn_stock_in)

        layout.addLayout(top_bar)

        # KPI Kartları
        self.kpi_layout = QHBoxLayout()
        self.kpi_layout.setSpacing(14)
        self.kpi_prods = self._create_kpi_card("📦 Ürün Çeşidi", "0", "Aktif Stok Kalemi", "#3b82f6")
        self.kpi_stock = self._create_kpi_card("📊 Toplam Stok Adedi", "0", "Mevcut Depo Varlığı", "#10b981")
        self.kpi_crit = self._create_kpi_card("⚠️ Kritik Seviyedeki Ürünler", "0", "Acil Tedarik Gereken", "#ef4444")
        self.kpi_dispatch = self._create_kpi_card("🚚 Bugün Şubelere Sevk", "0", "Günlük Dağıtım", "#f59e0b")

        self.kpi_layout.addWidget(self.kpi_prods)
        self.kpi_layout.addWidget(self.kpi_stock)
        self.kpi_layout.addWidget(self.kpi_crit)
        self.kpi_layout.addWidget(self.kpi_dispatch)
        layout.addLayout(self.kpi_layout)

        # Alt Bölüm: Kritik Stoklar Tablosu & Son Hareketler
        grid = QHBoxLayout()
        grid.setSpacing(16)

        # Sol: Kritik Stok Takibi
        crit_box = QFrame()
        crit_box.setStyleSheet(f"background-color: {AppStyles.BG_MEDIUM}; border: 1px solid {AppStyles.BORDER}; border-radius: 10px; padding: 14px;")
        crit_lay = QVBoxLayout(crit_box)
        crit_title = QLabel("⚠️ Kritik Stok Uyarıları (Acil Sipariş Edilmesi Gerekenler)")
        crit_title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #ef4444;")
        crit_lay.addWidget(crit_title)

        self.crit_table = QTableWidget()
        self.crit_table.setColumnCount(4)
        self.crit_table.setHorizontalHeaderLabels(["Ürün Adı", "Kategori", "Mevcut Stok", "Kritik Eşik"])
        self.crit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.crit_table.verticalHeader().setDefaultSectionSize(42)
        self.crit_table.verticalHeader().setVisible(False)
        self.crit_table.setStyleSheet(f"""
            QTableWidget {{ background: {AppStyles.BG_DARK}; color: white; border: 1px solid {AppStyles.BORDER}; border-radius: 6px; }}
            QHeaderView::section {{ background: {AppStyles.BG_LIGHT}; color: white; font-weight: bold; padding: 6px; border: none; }}
        """)
        crit_lay.addWidget(self.crit_table)
        grid.addWidget(crit_box, 3)

        # Sağ: Hızlı Kısayollar & Şube Dağıtım Özeti
        quick_box = QFrame()
        quick_box.setStyleSheet(f"background-color: {AppStyles.BG_MEDIUM}; border: 1px solid {AppStyles.BORDER}; border-radius: 10px; padding: 14px;")
        quick_lay = QVBoxLayout(quick_box)
        q_title = QLabel("⚡ Hızlı Depo İşlemleri")
        q_title.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        quick_lay.addWidget(q_title)

        actions = [
            ("📦 Tüm Envanter Listesine Git", "inventory", "#3b82f6"),
            ("🚚 Şube Sevkiyat Kayıtları", "dispatches", "#f59e0b"),
            ("📥 Tedarikçiden Malzeme Girişi", "stock_in", "#10b981"),
            ("📤 Bozulma / Fire Kaydı Gir", "stock_out", "#ef4444"),
            ("👥 Tedarikçi Cari Hesapları", "suppliers", "#8b5cf6"),
        ]
        for act_title, target_page, color in actions:
            btn = QPushButton(act_title)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {AppStyles.BG_DARK};
                    color: white;
                    border: 1px solid {color}50;
                    border-left: 4px solid {color};
                    border-radius: 6px;
                    padding: 10px;
                    text-align: left;
                    font-size: 9.5pt;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {AppStyles.BG_LIGHT};
                    border-color: {color};
                }}
            """)
            btn.clicked.connect(lambda ch, p=target_page: self.main_window.navigate_to(p))
            quick_lay.addWidget(btn)

        quick_lay.addStretch()
        grid.addWidget(quick_box, 2)

        layout.addLayout(grid)

    def _create_kpi_card(self, title: str, val: str, sub: str, accent: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-left: 4px solid {accent};
                border-radius: 8px;
                padding: 12px 14px;
            }}
        """)
        l = QVBoxLayout(card)
        l.setSpacing(4)
        l.setContentsMargins(0, 0, 0, 0)
        t = QLabel(title)
        t.setStyleSheet("color: #94a3b8; font-size: 9.5pt; font-weight: 500;")
        l.addWidget(t)
        v = QLabel(val)
        v.setObjectName("val_label")
        v.setStyleSheet(f"color: {accent}; font-size: 16pt; font-weight: bold;")
        l.addWidget(v)
        s = QLabel(sub)
        s.setObjectName("sub_label")
        s.setStyleSheet("color: #64748b; font-size: 8.5pt;")
        l.addWidget(s)
        return card

    def _update_kpi(self, card: QFrame, val: str, sub: str):
        v = card.findChild(QLabel, "val_label")
        if v:
            v.setText(val)
        s = card.findChild(QLabel, "sub_label")
        if s:
            s.setText(sub)

    def load_data(self):
        stats = warehouse_service.get_warehouse_stats()
        tot_prods = stats.get('total_products', 0)
        tot_stock = stats.get('total_stock', 0.0)
        crit_count = stats.get('critical_count', 0)
        today_dispatch = stats.get('today_dispatch_qty', 0.0)

        self._update_kpi(self.kpi_prods, str(tot_prods), f"{tot_prods} Aktif hammadde & ürün")
        self._update_kpi(self.kpi_stock, f"{tot_stock:,.0f} Birim", "Toplam fiziki miktar")
        self._update_kpi(self.kpi_crit, f"{crit_count} Ürün", "Kritik eşik altında!" if crit_count > 0 else "Stoklar yeterli")
        self._update_kpi(self.kpi_dispatch, f"{today_dispatch:,.0f} Kalem", "Bugün şubelere gönderilen")

        # Kritik ürünleri listele
        low_prods = warehouse_service.get_products(low_stock_only=True)
        self.crit_table.setRowCount(len(low_prods))
        for r_idx, p in enumerate(low_prods):
            self.crit_table.setItem(r_idx, 0, QTableWidgetItem(p.get('name') or "-"))
            self.crit_table.setItem(r_idx, 1, QTableWidgetItem(p.get('category') or "-"))
            qty_item = QTableWidgetItem(f"{float(p.get('stock_quantity') or 0):,.2f} {p.get('unit','')}")
            qty_item.setForeground(QColor("#ef4444"))
            qty_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.crit_table.setItem(r_idx, 2, qty_item)
            self.crit_table.setItem(r_idx, 3, QTableWidgetItem(f"{float(p.get('critical_stock') or 0):,.2f} {p.get('unit','')}"))

    def quick_dispatch(self):
        dlg = DispatchDialog(self.user, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def quick_stock_in(self):
        dlg = StockInDialog(self.user, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()


class WarehouseInventoryView(QWidget):
    """Depodaki tüm ürün ve hammaddelerin detaylı envanter tablosu"""

    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self.user = user
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        t_box = QVBoxLayout()
        title = QLabel("📦 Merkez Depo Envanter & Stok Durumu")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        subtitle = QLabel("Depoda yer alan un, susam, katkı maddeleri, ambalaj ve toptan ürünlerin listesi")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        t_box.addWidget(title)
        t_box.addWidget(subtitle)
        header.addLayout(t_box)
        header.addStretch()

        btn_add = QPushButton("➕ Yeni Ürün / Hammadde")
        btn_add.setStyleSheet("background: #10b981; color: white; font-weight: bold; border-radius: 8px; padding: 10px 16px;")
        btn_add.clicked.connect(self.add_product)
        header.addWidget(btn_add)

        btn_excel = QPushButton("📊 Excel'e Aktar")
        btn_excel.setStyleSheet(AppStyles.btn_secondary())
        btn_excel.clicked.connect(self.export_excel)
        header.addWidget(btn_excel)

        layout.addLayout(header)

        # Filtreleme
        filter_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Ürün adı veya kodu ara...")
        self.search_input.textChanged.connect(self.load_data)
        self.search_input.setStyleSheet(f"background: {AppStyles.BG_MEDIUM}; color: white; border: 1px solid {AppStyles.BORDER}; border-radius: 6px; padding: 6px 12px;")
        filter_bar.addWidget(self.search_input, 2)

        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["Tümü", "Hammadde", "Ambalaj", "Katkı Maddesi", "Mamül", "Yarı Mamül", "Temizlik / Sarf"])
        self.cat_combo.currentTextChanged.connect(self.load_data)
        self.cat_combo.setStyleSheet(f"background: {AppStyles.BG_MEDIUM}; color: white; border: 1px solid {AppStyles.BORDER}; border-radius: 6px; padding: 6px 10px;")
        filter_bar.addWidget(self.cat_combo, 1)

        self.crit_check = QCheckBox("Yalnızca Kritik Stoktakiler")
        self.crit_check.setStyleSheet("color: #ef4444; font-weight: bold;")
        self.crit_check.stateChanged.connect(self.load_data)
        filter_bar.addWidget(self.crit_check)

        layout.addLayout(filter_bar)

        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Kod", "Ürün Adı", "Kategori", "Mevcut Stok", "Birim", "Kritik Eşik", "Alış Fiyatı (₺)", "Toplam Değer (₺)", "İşlemler"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed)
        self.table.setColumnWidth(8, 105)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background: {AppStyles.BG_MEDIUM}; color: white; border: 1px solid {AppStyles.BORDER}; border-radius: 8px; }}
            QHeaderView::section {{ background: {AppStyles.BG_LIGHT}; color: white; font-weight: bold; padding: 8px; border: none; }}
        """)
        layout.addWidget(self.table)

    def load_data(self):
        search = self.search_input.text().strip()
        cat = self.cat_combo.currentText()
        crit = self.crit_check.isChecked()

        products = warehouse_service.get_products(search=search, category=cat, low_stock_only=crit)
        self.table.setRowCount(len(products))

        for idx, p in enumerate(products):
            self.table.setItem(idx, 0, QTableWidgetItem(p.get('product_code') or "-"))
            self.table.setItem(idx, 1, QTableWidgetItem(p.get('name') or "-"))
            self.table.setItem(idx, 2, QTableWidgetItem(p.get('category') or "-"))

            qty = float(p.get('stock_quantity') or 0.0)
            crit_q = float(p.get('critical_stock') or 0.0)
            qty_item = QTableWidgetItem(f"{qty:,.2f}")
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if qty <= crit_q:
                qty_item.setForeground(QColor("#ef4444"))
                qty_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            else:
                qty_item.setForeground(QColor("#10b981"))
            self.table.setItem(idx, 3, qty_item)

            self.table.setItem(idx, 4, QTableWidgetItem(p.get('unit') or "Adet"))

            crit_item = QTableWidgetItem(f"{crit_q:,.2f}")
            crit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(idx, 5, crit_item)

            p_price = float(p.get('purchase_price') or 0.0)
            price_item = QTableWidgetItem(f"{p_price:,.2f} ₺")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(idx, 6, price_item)

            tot_val = qty * p_price
            tot_item = QTableWidgetItem(f"{tot_val:,.2f} ₺")
            tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tot_item.setForeground(QColor("#f59e0b"))
            self.table.setItem(idx, 7, tot_item)

            # İşlemler Butonları
            act_w = QWidget()
            act_w.setStyleSheet("background: transparent;")
            a_lay = QHBoxLayout(act_w)
            a_lay.setContentsMargins(2, 2, 2, 2)
            a_lay.setSpacing(6)
            a_lay.setAlignment(Qt.AlignCenter)

            btn_edit = QPushButton("✏️")
            btn_edit.setToolTip("Düzenle")
            btn_edit.setFixedSize(36, 30)
            btn_edit.setStyleSheet("background: #334155; color: white; border-radius: 5px; font-size: 10pt;")
            btn_edit.clicked.connect(lambda ch, pid=p['id']: self.edit_product(pid))

            btn_del = QPushButton("🗑️")
            btn_del.setToolTip("Sil")
            btn_del.setFixedSize(36, 30)
            btn_del.setStyleSheet("background: #ef4444; color: white; border-radius: 5px; font-size: 10pt;")
            btn_del.clicked.connect(lambda ch, pid=p['id']: self.delete_product(pid))

            a_lay.addWidget(btn_edit)
            a_lay.addWidget(btn_del)
            self.table.setCellWidget(idx, 8, act_w)

    def add_product(self):
        dlg = AddWarehouseProductDialog(self.user, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def edit_product(self, product_id: int):
        product = warehouse_service.get_product(product_id)
        if not product:
            QMessageBox.warning(self, "Hata", "Ürün bulunamadı!")
            return
        dlg = EditWarehouseProductDialog(self.user, product, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def delete_product(self, product_id: int):
        reply = QMessageBox.question(self, "Sil", "Bu ürünü depodan silmek istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, msg = warehouse_service.delete_product(product_id)
            if success:
                self.load_data()
            else:
                QMessageBox.critical(self, "Hata", msg)

    def export_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Excel Olarak Kaydet", "depo_envanter.xlsx", "Excel (*.xlsx)")
        if path:
            success, msg = warehouse_service.export_products_to_excel(path)
            if success:
                QMessageBox.information(self, "Başarılı", msg)
            else:
                QMessageBox.critical(self, "Hata", msg)


class WarehouseDispatchesView(QWidget):
    """Şubelere Yapılan Sevkiyatların Takibi ve Yeni Sevkiyat"""

    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self.user = user
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        t_box = QVBoxLayout()
        title = QLabel("🚚 Şubelere Sevkiyat & Dağıtım Takibi")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        subtitle = QLabel("Merkez depodan Armada, Çobançeşme, Rumeli, Orion ve İmalathaneye sevk edilen malzemelerin takibi")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        t_box.addWidget(title)
        t_box.addWidget(subtitle)
        header.addLayout(t_box)
        header.addStretch()

        btn_dispatch = QPushButton("🚚 Yeni Sevkiyat Yap")
        btn_dispatch.setStyleSheet("background: #f59e0b; color: white; font-weight: bold; border-radius: 8px; padding: 10px 18px;")
        btn_dispatch.clicked.connect(self.new_dispatch)
        header.addWidget(btn_dispatch)

        layout.addLayout(header)

        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "İrsaliye No", "Tarih", "Hedef Şube", "Ürün", "Kategori", "Miktar", "Birim", "Açıklama", "İşlemler"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed)
        self.table.setColumnWidth(8, 100)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background: {AppStyles.BG_MEDIUM}; color: white; border: 1px solid {AppStyles.BORDER}; border-radius: 8px; }}
            QHeaderView::section {{ background: {AppStyles.BG_LIGHT}; color: white; font-weight: bold; padding: 8px; border: none; }}
        """)
        layout.addWidget(self.table)

    def load_data(self):
        dispatches = warehouse_service.get_dispatches()
        self.table.setRowCount(len(dispatches))
        for idx, d in enumerate(dispatches):
            self.table.setItem(idx, 0, QTableWidgetItem(d.get('document_no') or "-"))
            dt_str = str(d.get('movement_date') or d.get('dispatch_date') or "")[:10]
            self.table.setItem(idx, 1, QTableWidgetItem(dt_str))

            br_item = QTableWidgetItem(d.get('branch_name') or "-")
            br_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            br_item.setForeground(QColor("#38bdf8"))
            self.table.setItem(idx, 2, br_item)

            self.table.setItem(idx, 3, QTableWidgetItem(d.get('product_name') or "-"))
            self.table.setItem(idx, 4, QTableWidgetItem(d.get('category') or "-"))

            q = float(d.get('quantity') or 0.0)
            q_item = QTableWidgetItem(f"{q:,.2f}")
            q_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(idx, 5, q_item)

            self.table.setItem(idx, 6, QTableWidgetItem(d.get('unit') or "Adet"))
            self.table.setItem(idx, 7, QTableWidgetItem(d.get('description') or ""))

            # 8. İşlemler (Düzenle & Sil)
            act_w = QWidget()
            act_w.setStyleSheet("background: transparent;")
            a_lay = QHBoxLayout(act_w)
            a_lay.setContentsMargins(2, 2, 2, 2)
            a_lay.setSpacing(6)
            a_lay.setAlignment(Qt.AlignCenter)

            btn_edit = QPushButton("✏️")
            btn_edit.setToolTip("Sevkiyatı Düzenle")
            btn_edit.setFixedSize(36, 30)
            btn_edit.setStyleSheet("background: #f59e0b; color: white; border-radius: 5px; font-size: 10pt;")
            btn_edit.clicked.connect(lambda ch, disp=d: self.edit_dispatch(disp))

            btn_del = QPushButton("🗑️")
            btn_del.setToolTip("Sevkiyatı Sil & Stoğu İade Et")
            btn_del.setFixedSize(36, 30)
            btn_del.setStyleSheet("background: #ef4444; color: white; border-radius: 5px; font-size: 10pt;")
            btn_del.clicked.connect(lambda ch, disp=d: self.delete_dispatch(disp))

            a_lay.addWidget(btn_edit)
            a_lay.addWidget(btn_del)
            self.table.setCellWidget(idx, 8, act_w)

    def edit_dispatch(self, dispatch: dict):
        m_id = dispatch.get('id')
        full_mov = warehouse_service.get_stock_movement(m_id) or dispatch
        dlg = EditMovementDialog(self.user, full_mov, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def delete_dispatch(self, dispatch: dict):
        m_id = dispatch.get('id')
        p_name = dispatch.get('product_name') or 'Ürün'
        qty = float(dispatch.get('quantity') or 0.0)
        unit = dispatch.get('unit') or ''
        b_name = dispatch.get('branch_name') or 'Şube'
        reply = QMessageBox.question(
            self, "Sevkiyatı Sil & Geri Al",
            f"<b>{p_name}</b> ürününe ait bu sevkiyatı silmek istediğinize emin misiniz?<br><br>"
            f"<b>Miktar:</b> {qty:,.2f} {unit}<br>"
            f"<b>Hedef Şube:</b> {b_name}<br><br>"
            f"⚠️ <i>İşlem onaylandığında sevk edilen miktar Merkez Depo stoğuna geri eklenecek "
            f"ve hedef şubenin stoğundan otomatik olarak düşülecektir.</i>",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = warehouse_service.delete_stock_movement(m_id, user_id=getattr(self.user, 'id', None))
            if success:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_data()
            else:
                QMessageBox.critical(self, "Hata", msg)

    def new_dispatch(self):
        dlg = DispatchDialog(self.user, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()


class WarehouseStockInOutView(QWidget):
    """Depo Malzeme Kabul (Giriş), Fire/Zayiat (Çıkış) ve Hareket Geçmişi"""

    def __init__(self, user: User, movement_type: str = 'ALL', parent=None):
        super().__init__(parent)
        self.user = user
        self.movement_type = movement_type  # 'IN', 'OUT', 'ALL'
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        t_box = QVBoxLayout()
        if self.movement_type == 'IN':
            t_text = "📥 Depo Malzeme Kabul & Stok Girişleri"
            sub_text = "Tedarikçilerden depoya kabul edilen hammadde ve malzemeler"
        elif self.movement_type == 'OUT':
            t_text = "📤 Depo Fire, Zayiat & Stok Çıkışları"
            sub_text = "Bozulma, son kullanım veya fire nedeniyle stoktan düşülen kalemler"
        else:
            t_text = "📈 Depo Stok Hareketleri & Denetim Günlüğü"
            sub_text = "Giriş, çıkış, sayım farkı ve sevkiyat dahil tüm depo hareketleri"

        title = QLabel(t_text)
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        subtitle = QLabel(sub_text)
        subtitle.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        t_box.addWidget(title)
        t_box.addWidget(subtitle)
        header.addLayout(t_box)
        header.addStretch()

        if self.movement_type == 'IN':
            btn_act = QPushButton("📥 Yeni Malzeme Kabulü")
            btn_act.setStyleSheet("background: #10b981; color: white; font-weight: bold; border-radius: 8px; padding: 10px 18px;")
            btn_act.clicked.connect(self.new_entry)
            header.addWidget(btn_act)
        elif self.movement_type == 'OUT':
            btn_act = QPushButton("📤 Yeni Fire / Zayiat Çıkışı")
            btn_act.setStyleSheet("background: #ef4444; color: white; font-weight: bold; border-radius: 8px; padding: 10px 18px;")
            btn_act.clicked.connect(self.new_entry)
            header.addWidget(btn_act)

        layout.addLayout(header)

        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Tarih", "Tür", "Ürün Adı", "Miktar", "Firma / Tedarikçi",
            "Eski Stok", "Yeni Stok", "Belge / Fatura", "Açıklama", "İşlemler"
        ])
        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 135)
        h_header.setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 95)
        h_header.setSectionResizeMode(2, QHeaderView.Stretch)
        h_header.setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 110)
        h_header.setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.setColumnWidth(4, 160)
        h_header.setSectionResizeMode(5, QHeaderView.Interactive)
        self.table.setColumnWidth(5, 100)
        h_header.setSectionResizeMode(6, QHeaderView.Interactive)
        self.table.setColumnWidth(6, 100)
        h_header.setSectionResizeMode(7, QHeaderView.Interactive)
        self.table.setColumnWidth(7, 125)
        h_header.setSectionResizeMode(8, QHeaderView.Stretch)
        h_header.setSectionResizeMode(9, QHeaderView.Fixed)
        self.table.setColumnWidth(9, 100)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background: {AppStyles.BG_MEDIUM}; color: white; border: 1px solid {AppStyles.BORDER}; border-radius: 8px; }}
            QHeaderView::section {{ background: {AppStyles.BG_LIGHT}; color: white; font-weight: bold; padding: 6px; border: none; }}
        """)
        layout.addWidget(self.table)

    def load_data(self):
        m_type = None if self.movement_type == 'ALL' else self.movement_type
        movements = warehouse_service.get_stock_movements(movement_type=m_type)
        self.table.setRowCount(len(movements))

        for idx, m in enumerate(movements):
            # 0. Tarih
            dt_raw = m.get('created_at') or m.get('movement_date')
            if hasattr(dt_raw, 'strftime'):
                dt_str = dt_raw.strftime('%d.%m.%Y %H:%M')
            else:
                dt_str = str(dt_raw or "")[:16]
            d_item = QTableWidgetItem(dt_str)
            d_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 0, d_item)

            # 1. Tür
            m_t = m.get('movement_type') or ""
            t_item = QTableWidgetItem(m_t)
            t_item.setTextAlignment(Qt.AlignCenter)
            if m_t == 'IN':
                t_item.setText("📥 GİRİŞ")
                t_item.setForeground(QColor("#10b981"))
            elif m_t == 'OUT':
                t_item.setText("📤 ÇIKIŞ")
                t_item.setForeground(QColor("#ef4444"))
            elif m_t == 'DISPATCH':
                t_item.setText("🚚 SEVKİYAT")
                t_item.setForeground(QColor("#38bdf8"))
            else:
                t_item.setText(m_t)
            t_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(idx, 1, t_item)

            # 2. Ürün Adı
            p_code = m.get('product_code')
            p_name = m.get('product_name') or "-"
            disp_name = f"{p_name} ({p_code})" if p_code else p_name
            name_item = QTableWidgetItem(disp_name)
            name_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(idx, 2, name_item)

            # 3. Miktar & Birim
            q = float(m.get('quantity') or 0.0)
            unit_str = m.get('unit') or ""
            q_item = QTableWidgetItem(f"{q:,.2f} {unit_str}".strip())
            q_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            q_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            q_item.setForeground(QColor("#10b981" if m_t == 'IN' else "#ef4444" if m_t == 'OUT' else "#38bdf8"))
            self.table.setItem(idx, 3, q_item)

            # 4. Firma / Tedarikçi
            supp = m.get('supplier_name')
            if not supp and m_t == 'DISPATCH':
                supp = f"Şube: {m.get('branch_name') or '-'}"
            supp_item = QTableWidgetItem(supp or "-")
            if supp:
                supp_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                supp_item.setForeground(QColor("#f1f5f9"))
            else:
                supp_item.setForeground(QColor(AppStyles.TEXT_MUTED))
            supp_item.setTextAlignment(Qt.AlignCenter if not supp else Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(idx, 4, supp_item)

            # 5. Eski Stok
            old_s = float(m.get('previous_stock') or 0.0)
            old_item = QTableWidgetItem(f"{old_s:,.2f}")
            old_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            old_item.setForeground(QColor(AppStyles.TEXT_SECONDARY))
            self.table.setItem(idx, 5, old_item)

            # 6. Yeni Stok
            new_s = float(m.get('new_stock') or 0.0)
            new_item = QTableWidgetItem(f"{new_s:,.2f}")
            new_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            new_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(idx, 6, new_item)

            # 7. Belge / Fatura
            doc_item = QTableWidgetItem(m.get('document_no') or "-")
            doc_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 7, doc_item)

            # 8. Açıklama
            self.table.setItem(idx, 8, QTableWidgetItem(m.get('description') or ""))

            # 9. İşlemler Butonları (Düzenle & Sil)
            act_w = QWidget()
            act_w.setStyleSheet("background: transparent;")
            a_lay = QHBoxLayout(act_w)
            a_lay.setContentsMargins(2, 2, 2, 2)
            a_lay.setSpacing(6)
            a_lay.setAlignment(Qt.AlignCenter)

            btn_edit = QPushButton("✏️")
            btn_edit.setToolTip("Hareketi Düzenle")
            btn_edit.setFixedSize(36, 30)
            btn_edit.setStyleSheet("background: #f59e0b; color: white; border-radius: 5px; font-size: 10pt;")
            btn_edit.clicked.connect(lambda ch, mov=m: self.edit_movement(mov))

            btn_del = QPushButton("🗑️")
            btn_del.setToolTip("Hareketi Sil & Stoğu Geri Al")
            btn_del.setFixedSize(36, 30)
            btn_del.setStyleSheet("background: #ef4444; color: white; border-radius: 5px; font-size: 10pt;")
            btn_del.clicked.connect(lambda ch, mov=m: self.delete_movement(mov))

            a_lay.addWidget(btn_edit)
            a_lay.addWidget(btn_del)
            self.table.setCellWidget(idx, 9, act_w)

    def edit_movement(self, movement: dict):
        m_id = movement.get('id')
        full_mov = warehouse_service.get_stock_movement(m_id) or movement
        dlg = EditMovementDialog(self.user, full_mov, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def delete_movement(self, movement: dict):
        m_id = movement.get('id')
        p_name = movement.get('product_name') or 'Ürün'
        qty = float(movement.get('quantity') or 0.0)
        unit = movement.get('unit') or ''
        m_t = movement.get('movement_type') or ''
        t_label = "Giriş (Malzeme Kabul)" if m_t == 'IN' else "Çıkış (Fire/Zayiat)" if m_t == 'OUT' else "Sevkiyat"

        reply = QMessageBox.question(
            self, "Hareketi Sil & Geri Al",
            f"<b>{p_name}</b> ürününe ait bu <b>{t_label}</b> hareketini silmek istediğinize emin misiniz?<br><br>"
            f"<b>Miktar:</b> {qty:,.2f} {unit}<br><br>"
            f"⚠️ <i>İşlem onaylandığında ilgili depo ve şube stokları otomatik olarak ters işlemle eski haline getirilecektir.</i>",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = warehouse_service.delete_stock_movement(m_id, user_id=getattr(self.user, 'id', None))
            if success:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_data()
            else:
                QMessageBox.critical(self, "Hata", msg)

    def new_entry(self):
        if self.movement_type == 'IN':
            dlg = StockInDialog(self.user, parent=self)
        else:
            dlg = StockOutDialog(self.user, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()
