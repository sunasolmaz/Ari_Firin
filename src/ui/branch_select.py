# src/ui/branch_select.py
"""
Modern Şube Seçim Ekranı - Koyu Tema
(Eğer doğrudan çağrılırsa diye düzeltilmiş sürüm)
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QMessageBox, QFrame, QScrollArea,
    QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from ..core.database import db
from ..core.logger import logger
from ..models.user import User
from ..models.branch import Branch
from .styles import AppStyles


class BranchSelectWindow(QMainWindow):
    """Modern koyu tema şube seçim ekranı"""

    def __init__(self, user: User):
        super().__init__()
        self.user = user

        try:
            schema = user.get_tenant_schema()
            db.set_tenant(schema)
            db.ensure_tenant_schema(schema)
        except Exception as e:
            logger.warning(f"Tenant şeması ayarlanamadı: {e}")

        self.setWindowTitle(f"☕ Şube Seçimi - {user.full_name}")
        self.setMinimumSize(1000, 700)
        self.showMaximized()
        
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {AppStyles.BG_DARK};
            }}
        """ + AppStyles.get_main_style())

        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        central_widget.setStyleSheet(f"QWidget#centralWidget {{ background-color: {AppStyles.BG_DARK}; }}")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(40, 20, 40, 20)

        top_bar = self.create_top_bar()
        main_layout.addWidget(top_bar)

        title = QLabel(f"👋 Hoş Geldiniz, {user.full_name}")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; "
            "background: transparent; border: none;"
        )
        main_layout.addWidget(title)

        subtitle = QLabel("İşlem yapmak istediğiniz şubeyi seçin")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            f"font-size: 14px; color: {AppStyles.TEXT_SECONDARY}; "
            "background: transparent; border: none; margin-bottom: 15px;"
        )
        main_layout.addWidget(subtitle)

        branches = Branch.get_all(active_only=True)

        if branches:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {AppStyles.BG_DARK}; }}")

            scroll_widget = QWidget()
            scroll_widget.setStyleSheet(f"background-color: {AppStyles.BG_DARK};")

            branches_layout = QGridLayout()
            branches_layout.setSpacing(20) 
            branches_layout.setContentsMargins(20, 10, 20, 20)
            branches_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

            col_count = 2
            
            for i, branch in enumerate(branches):
                card = self.create_branch_card(branch)
                row = i // col_count
                col = i % col_count
                branches_layout.addWidget(card, row, col)

            wh_card = self.create_warehouse_card()
            wh_row = len(branches) // col_count
            wh_col = len(branches) % col_count
            branches_layout.addWidget(wh_card, wh_row, wh_col)

            scroll_widget.setLayout(branches_layout)
            scroll.setWidget(scroll_widget)
            main_layout.addWidget(scroll)

        central_widget.setLayout(main_layout)

    def create_top_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()

        logout_btn = QPushButton("🚪 Çıkış Yap")
        logout_btn.clicked.connect(self.logout)
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {AppStyles.RED};
                border: 1px solid {AppStyles.RED};
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.RED};
                color: white;
            }}
        """)
        layout.addWidget(logout_btn)

        bar.setLayout(layout)
        return bar

    def create_branch_card(self, branch: Branch) -> QFrame:
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

        layout = QVBoxLayout()
        layout.setSpacing(12) 
        layout.setContentsMargins(20, 20, 20, 20)

        is_imalat = "imalat" in (branch.name or "").lower()

        icon_container = QFrame()
        icon_container.setFixedSize(56, 56)
        grad = f"stop:0 {AppStyles.SUCCESS}, stop:1 {AppStyles.CYAN}" if is_imalat else f"stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.PURPLE}"
        icon_container.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, {grad});
                border-radius: 28px;
                border: none;
            }}
        """)

        icon_layout = QVBoxLayout()
        icon_layout.setContentsMargins(0, 0, 0, 0)

        icon = QLabel("🏭" if is_imalat else "☕")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-family: 'Segoe UI Emoji', 'Segoe UI', sans-serif; font-size: 24px; background: transparent; border: none;")
        icon_layout.addWidget(icon)
        icon_container.setLayout(icon_layout)

        icon_wrapper = QHBoxLayout()
        icon_wrapper.addStretch()
        icon_wrapper.addWidget(icon_container)
        icon_wrapper.addStretch()
        layout.addLayout(icon_wrapper)

        name = QLabel(branch.name)
        name.setAlignment(Qt.AlignCenter)
        name.setWordWrap(True)
        name.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; "
            "background: transparent; border: none; margin-top: 5px;"
        )
        layout.addWidget(name)

        city_text = "🥖 Üretim & Dağıtım Merkezi" if is_imalat else (f"📍 {branch.city}" if branch.city else "")
        if city_text:
            city = QLabel(city_text)
            city.setAlignment(Qt.AlignCenter)
            city.setStyleSheet(
                f"color: {AppStyles.CYAN if is_imalat else AppStyles.TEXT_SECONDARY}; font-size: 12px; font-weight: 500; "
                "background: transparent; border: none; margin-bottom: 5px;"
            )
            layout.addWidget(city)

        stats_frame = QFrame()
        stats_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border-radius: 8px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setSpacing(8)
        stats_layout.setContentsMargins(15, 12, 15, 12)

        if is_imalat:
            try:
                from ..services.production_service import production_service
                hub_stats = production_service.get_hub_stats()
                stats_items = [
                    ("🥖", "Günün Üretimi", f"{hub_stats.get('total_produced', 0):,.0f} Adet"),
                    ("🚚", "Şubelere Sevk", f"{hub_stats.get('total_shipped', 0):,.0f} Adet"),
                    ("🛒", "Dış Satış", f"{hub_stats.get('ext_sales_total', 0):,.2f} ₺"),
                ]
            except Exception:
                 stats_items = [("⚠️", "Veri Hatası", "-")]
        else:
            stats = self.get_branch_stats(branch.id)
            stats_items = [
                ("👥", "Müşteri Sayısı", f"{stats.get('customer_count', 0)}"),
                ("📄", "Fatura Sayısı", f"{stats.get('invoice_count', 0)}"),
                ("💰", "Toplam Ciro", f"{stats.get('total_revenue', 0):,.2f} ₺"),
            ]

        for icon_txt, label, value in stats_items:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)

            lbl = QLabel(f"{icon_txt} {label}")
            lbl.setStyleSheet(f"""
                font-size: 12px;
                color: {AppStyles.TEXT_SECONDARY};
                font-weight: 500;
                background: transparent;
                border: none;
            """)
            row_layout.addWidget(lbl)

            row_layout.addStretch()

            val = QLabel(value)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet(f"""
                font-size: 13px;
                font-weight: bold;
                color: {AppStyles.TEXT_PRIMARY};
                background: transparent;
                border: none;
            """)
            row_layout.addWidget(val)

            stats_layout.addWidget(row_widget)

        layout.addWidget(stats_frame)
        layout.addStretch()

        btn_text = "🏭 İmalathaneye Git" if is_imalat else "Şubeye Gir"
        select_btn = QPushButton(btn_text)
        select_btn.clicked.connect(lambda: self.select_branch(branch))
        select_btn.setMinimumHeight(45)
        select_btn.setCursor(Qt.PointingHandCursor)
        btn_grad = f"stop:0 {AppStyles.SUCCESS}, stop:1 {AppStyles.CYAN}" if is_imalat else f"stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN}"
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, {btn_grad});
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        layout.addWidget(select_btn)

        card.setLayout(layout)
        return card

    def get_branch_stats(self, branch_id: int) -> dict:
        try:
            stats = db.fetch_one("""
                SELECT 
                    (SELECT COUNT(*) FROM Customers WHERE branch_id = %s AND is_active = TRUE) as customer_count,
                    (SELECT COUNT(*) FROM Invoices WHERE branch_id = %s AND (status IS NULL OR status != 'Cancelled')) as invoice_count,
                    (SELECT COALESCE(SUM(grand_total), 0) FROM Invoices WHERE branch_id = %s AND (LOWER(invoice_type) IN ('sales', 'satış', 'satis') OR invoice_type IS NULL) AND (status IS NULL OR status != 'Cancelled')) as total_revenue
            """, (branch_id, branch_id, branch_id))
            return stats if stats else {}
        except Exception as e:
            logger.error(f"İstatistik hatası: {e}")
            return {}

    def select_branch(self, branch: Branch):
        try:
            logger.info(f"✅ Şube seçildi: {branch.name}")
            is_imalat = "imalat" in (branch.name or "").lower()
            initial_pg = "production_hub" if is_imalat else "dashboard"

            from .main_window import MainWindow
            self.main_window = MainWindow(self.user, branch.id, initial_page=initial_pg)
            self.main_window.show()
            self.close()
        except Exception as e:
            logger.error(f"Şube seçme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Şube açılamadı:\n{str(e)}")

    def create_warehouse_card(self) -> QFrame:
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
                border: 1px solid {AppStyles.WARNING};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 5)
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        icon_container = QFrame()
        icon_container.setFixedSize(56, 56)
        icon_container.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {AppStyles.WARNING}, stop:1 {AppStyles.PRIMARY});
                border-radius: 28px;
                border: none;
            }}
        """)
        icon_layout = QVBoxLayout()
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon = QLabel("🏬")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-family: 'Segoe UI Emoji', 'Segoe UI', sans-serif; font-size: 24px; background: transparent; border: none;")
        icon_layout.addWidget(icon)
        icon_container.setLayout(icon_layout)

        icon_wrapper = QHBoxLayout()
        icon_wrapper.addStretch()
        icon_wrapper.addWidget(icon_container)
        icon_wrapper.addStretch()
        layout.addLayout(icon_wrapper)

        name = QLabel("Merkez Depo & Lojistik")
        name.setAlignment(Qt.AlignCenter)
        name.setWordWrap(True)
        name.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {AppStyles.WARNING}; "
            "background: transparent; border: none; margin-top: 5px;"
        )
        layout.addWidget(name)

        desc = QLabel("📦 Hammadde, Un & Dağıtım")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet(
            f"color: {AppStyles.TEXT_SECONDARY}; font-size: 12px; font-weight: 500; "
            "background: transparent; border: none; margin-bottom: 5px;"
        )
        layout.addWidget(desc)

        stats_frame = QFrame()
        stats_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border-radius: 8px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setSpacing(8)
        stats_layout.setContentsMargins(15, 12, 15, 12)

        stats = self.get_warehouse_stats()
        stats_items = [
            ("📦", "Toplam Malzeme", f"{stats.get('total_products', 0)} Çeşit"),
            ("⚠️", "Kritik Stok", f"{stats.get('critical_count', 0)} Kalem"),
            ("🚚", "Bugün Sevk", f"{stats.get('today_dispatches', 0)} İşlem"),
        ]

        for icon_txt, label, value in stats_items:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)

            lbl = QLabel(f"{icon_txt} {label}")
            lbl.setStyleSheet(f"""
                font-size: 12px;
                color: {AppStyles.TEXT_SECONDARY};
                font-weight: 500;
                background: transparent;
                border: none;
            """)
            row_layout.addWidget(lbl)

            row_layout.addStretch()

            val = QLabel(value)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet(f"""
                font-size: 13px;
                font-weight: bold;
                color: {AppStyles.TEXT_PRIMARY};
                background: transparent;
                border: none;
            """)
            row_layout.addWidget(val)

            stats_layout.addWidget(row_widget)

        layout.addWidget(stats_frame)
        layout.addStretch()

        select_btn = QPushButton("🏬 Depoya Gir")
        select_btn.clicked.connect(self.select_warehouse)
        select_btn.setMinimumHeight(45)
        select_btn.setCursor(Qt.PointingHandCursor)
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.WARNING}, stop:1 {AppStyles.PRIMARY});
                color: black;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        layout.addWidget(select_btn)

        card.setLayout(layout)
        return card

    def get_warehouse_stats(self) -> dict:
        try:
            stats = db.fetch_one("""
                SELECT 
                    (SELECT COUNT(*) FROM WarehouseProducts WHERE is_active = TRUE) as total_products,
                    (SELECT COUNT(*) FROM WarehouseProducts WHERE is_active = TRUE AND stock_quantity <= critical_stock) as critical_count,
                    (SELECT COUNT(*) FROM WarehouseStockMovements WHERE movement_type = 'dispatch' AND DATE(created_at) = CURRENT_DATE) as today_dispatches
            """)
            return stats if stats else {}
        except Exception as e:
            logger.error(f"Depo istatistik hatası: {e}")
            return {}

    def select_warehouse(self):
        try:
            logger.info("🏬 Merkez Depo seçildi")
            from .warehouse_window import WarehouseWindow
            self.warehouse_window = WarehouseWindow(self.user)
            self.warehouse_window.show()
            self.close()
        except Exception as e:
            logger.error(f"Depo seçme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Depo açılamadı:\n{str(e)}")

    def logout(self):
        reply = QMessageBox.question(
            self, "Çıkış", "Çıkış yapmak istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                db.clear_tenant()
            except Exception:
                pass
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