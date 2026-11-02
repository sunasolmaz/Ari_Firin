# src/ui/central_pages/all_products_page.py
"""
Tüm Şubelerin Ürünleri & Stokları - Genel Merkez Görünümü
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QGraphicsDropShadowEffect, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles


class AllProductsPage(QWidget):
    """Tüm şubelerin ürünleri & stokları"""

    def __init__(self, user: User, central_window=None):
        super().__init__()
        self.user = user
        self.central_window = central_window

        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setObjectName("AllProductsPage")
        self.setStyleSheet(f"#AllProductsPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)

        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(3)
        title = QLabel("🛍️ Tüm Ürünler & Stok")
        title.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)
        subtitle = QLabel("Tüm şubelerin ürünleri ve stok durumu")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        top_bar.addLayout(left)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # İstatistik kartları
        stats = self.create_stats_cards()
        layout.addLayout(stats)

        # Filtreler
        filters = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Ürün ara...")
        self.search_input.setMinimumHeight(42)
        self.search_input.textChanged.connect(self.load_data)
        filters.addWidget(self.search_input, 3)

        self.branch_combo = QComboBox()
        self.branch_combo.setMinimumHeight(42)
        self.branch_combo.addItem("Tüm Şubeler", None)
        branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY name")
        for b in branches:
            self.branch_combo.addItem(b['name'], b['id'])
        self.branch_combo.currentIndexChanged.connect(self.load_data)
        filters.addWidget(self.branch_combo, 1)

        layout.addLayout(filters)

        # Tablo
        table_frame = QFrame()
        table_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                border: 1px solid {AppStyles.BORDER};
                padding: 20px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 5)
        table_frame.setGraphicsEffect(shadow)

        table_layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            'Şube', 'Kod', 'Ürün Adı', 'Kategori', 'Birim', 'Alış', 'Satış', 'Stok'
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                border: none;
                gridline-color: {AppStyles.BORDER};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{ padding: 10px; border: none; }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARKEST};
                color: {AppStyles.TEXT_SECONDARY};
                padding: 12px;
                border: none;
                border-bottom: 1px solid {AppStyles.BORDER};
                font-weight: 600;
            }}
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.table)

        self.total_label = QLabel("Toplam: 0 ürün")
        self.total_label.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; padding: 10px;")
        table_layout.addWidget(self.total_label)

        table_frame.setLayout(table_layout)
        layout.addWidget(table_frame)

        self.setLayout(layout)

    def create_stats_cards(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(15)

        try:
            stats = db.fetch_one("""
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(stock_quantity), 0) as total_stock,
                    COALESCE(SUM(stock_quantity * purchase_price), 0) as stock_value,
                    SUM(CASE WHEN stock_quantity <= critical_stock THEN 1 ELSE 0 END) as critical
                FROM Products
                WHERE is_active = TRUE
            """)

            cards = [
                ("🛍️", "Toplam Ürün", str(stats.get('total', 0)), AppStyles.PRIMARY),
                ("📦", "Toplam Stok", f"{float(stats.get('total_stock', 0)):,.0f}", AppStyles.CYAN),
                ("💰", "Stok Değeri", f"{float(stats.get('stock_value', 0)):,.0f} ₺", AppStyles.GREEN),
                ("⚠️", "Kritik Stok", str(stats.get('critical', 0)), AppStyles.RED),
            ]

            for icon, title, value, color in cards:
                card = self.create_stat_card(icon, title, value, color)
                layout.addWidget(card)
        except Exception as e:
            logger.error(f"İstatistik hatası: {e}")

        return layout

    def create_stat_card(self, icon, title, value, color):
        card = QFrame()
        card.setMinimumHeight(100)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                border-left: 4px solid {color};
                padding: 15px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        layout.setSpacing(5)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 18pt; background: transparent; border: none;")
        layout.addWidget(icon_lbl)

        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {color}; background: transparent; border: none;")
        layout.addWidget(value_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY}; background: transparent; border: none;")
        layout.addWidget(title_lbl)

        card.setLayout(layout)
        return card

    def load_data(self):
        try:
            search = self.search_input.text().strip()
            branch_id = self.branch_combo.currentData()

            query = """
                SELECT p.*, b.name as branch_name
                FROM Products p
                LEFT JOIN Branches b ON b.id = p.branch_id
                WHERE p.is_active = TRUE
            """
            params = []

            if branch_id:
                query += " AND p.branch_id = %s"
                params.append(branch_id)

            if search:
                query += " AND (p.name ILIKE %s OR p.product_code ILIKE %s)"
                params.extend([f"%{search}%"] * 2)

            query += " ORDER BY p.name LIMIT 1000"

            products = db.fetch_all(query, tuple(params))

            self.table.setRowCount(0)
            for i, p in enumerate(products):
                self.table.insertRow(i)
                self.table.setItem(i, 0, QTableWidgetItem(str(p.get('branch_name') or '')))
                self.table.setItem(i, 1, QTableWidgetItem(str(p.get('product_code') or '')))
                self.table.setItem(i, 2, QTableWidgetItem(str(p.get('name') or '')))
                self.table.setItem(i, 3, QTableWidgetItem(str(p.get('category') or '')))
                self.table.setItem(i, 4, QTableWidgetItem(str(p.get('unit') or '')))

                # Alış (sağa hizalı)
                pur_item = QTableWidgetItem(f"{float(p.get('purchase_price') or 0):,.2f} ₺")
                pur_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 5, pur_item)

                # Satış (sağa hizalı)
                sale_item = QTableWidgetItem(f"{float(p.get('sale_price') or 0):,.2f} ₺")
                sale_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 6, sale_item)

                # Stok (ortalanmış, renkli)
                stock = float(p.get('stock_quantity') or 0)
                critical = float(p.get('critical_stock') or 0)
                stock_item = QTableWidgetItem(f"{stock:,.2f}")
                stock_item.setTextAlignment(Qt.AlignCenter)
                if stock <= 0:
                    stock_item.setForeground(QColor(AppStyles.RED))
                elif stock <= critical:
                    stock_item.setForeground(QColor(AppStyles.ORANGE))
                else:
                    stock_item.setForeground(QColor(AppStyles.GREEN))
                self.table.setItem(i, 7, stock_item)

            self.total_label.setText(f"Toplam: {len(products)} ürün")
        except Exception as e:
            logger.error(f"Ürün yükleme hatası: {e}")