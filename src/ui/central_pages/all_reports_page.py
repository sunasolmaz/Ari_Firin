# src/ui/central_pages/all_reports_page.py
"""
Tüm Şubelerin Raporları - Genel Merkez Görünümü
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QGraphicsDropShadowEffect,
    QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles


class AllReportsPage(QWidget):
    """Tüm şubelerin raporları"""

    def __init__(self, user: User, central_window=None):
        super().__init__()
        self.user = user
        self.central_window = central_window

        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setObjectName("AllReportsPage")
        self.setStyleSheet(f"#AllReportsPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)

        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(3)
        title = QLabel("📈 Tüm Raporlar")
        title.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)
        subtitle = QLabel("Tüm şubelerin karşılaştırmalı raporları")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        top_bar.addLayout(left)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Genel özet kartları
        summary = self.create_summary_cards()
        layout.addLayout(summary)

        # Şube bazlı karşılaştırma tablosu
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

        title2 = QLabel("☕ Şube Bazlı Karşılaştırma")
        title2.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; padding: 10px 0;")
        table_layout.addWidget(title2)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            'Şube', 'Cari Hesap', 'Fatura', 'Toplam Satış', 'Toplam Alış', 'Net'
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
            QTableWidget::item {{ padding: 12px; border: none; }}
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

        table_frame.setLayout(table_layout)
        layout.addWidget(table_frame)

        self.setLayout(layout)

    def create_summary_cards(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(15)

        try:
            # ✅ İki ayrı sorgu — FULL OUTER JOIN Kartezyen hatası çözüldü
            cust_stats = db.fetch_one("""
                SELECT COUNT(DISTINCT id) as total_customers
                FROM Customers
                WHERE is_active = TRUE
            """)

            inv_stats = db.fetch_one("""
                SELECT 
                    COUNT(DISTINCT id) as total_invoices,
                    COALESCE(SUM(CASE WHEN invoice_type IN ('Sales', 'Satış') THEN grand_total END), 0) as total_sales,
                    COALESCE(SUM(CASE WHEN invoice_type IN ('Purchase', 'Alış') THEN grand_total END), 0) as total_purchases
                FROM Invoices
            """)

            total_customers = int(cust_stats['total_customers']) if cust_stats else 0
            total_invoices = int(inv_stats['total_invoices']) if inv_stats else 0
            total_sales = float(inv_stats['total_sales']) if inv_stats else 0.0
            total_purchases = float(inv_stats['total_purchases']) if inv_stats else 0.0

            net = total_sales - total_purchases

            cards = [
                ("👥", "Tüm Cari", str(total_customers), AppStyles.PRIMARY),
                ("📄", "Tüm Fatura", str(total_invoices), AppStyles.CYAN),
                ("💰", "Toplam Satış", f"{total_sales:,.0f} ₺", AppStyles.GREEN),
                ("📊", "Net Kar", f"{net:,.0f} ₺", AppStyles.GREEN if net >= 0 else AppStyles.RED),
            ]

            for icon, title, value, color in cards:
                card = self.create_stat_card(icon, title, value, color)
                layout.addWidget(card)
        except Exception as e:
            logger.error(f"Özet hatası: {e}")

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
            branches = db.fetch_all("""
                SELECT 
                    b.id, b.name,
                    COUNT(DISTINCT c.id) as customer_count,
                    COUNT(DISTINCT i.id) as invoice_count,
                    COALESCE(SUM(CASE WHEN i.invoice_type IN ('Sales', 'Satış') THEN i.grand_total END), 0) as total_sales,
                    COALESCE(SUM(CASE WHEN i.invoice_type IN ('Purchase', 'Alış') THEN i.grand_total END), 0) as total_purchases
                FROM Branches b
                LEFT JOIN Customers c ON c.branch_id = b.id AND c.is_active = TRUE
                LEFT JOIN Invoices i ON i.branch_id = b.id
                WHERE b.is_active = TRUE
                GROUP BY b.id, b.name
                ORDER BY b.name
            """)

            self.table.setRowCount(0)
            for i, b in enumerate(branches):
                self.table.insertRow(i)

                # 0. Şube
                self.table.setItem(i, 0, QTableWidgetItem(str(b.get('name') or '')))

                # 1. Cari Hesap (sağa hizalı)
                cust_item = QTableWidgetItem(str(b.get('customer_count') or 0))
                cust_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, 1, cust_item)

                # 2. Fatura (sağa hizalı)
                inv_item = QTableWidgetItem(str(b.get('invoice_count') or 0))
                inv_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, 2, inv_item)

                # 3. Toplam Satış (sağa hizalı)
                sales = float(b.get('total_sales') or 0)
                sales_item = QTableWidgetItem(f"{sales:,.2f} ₺")
                sales_item.setForeground(QColor(AppStyles.GREEN))
                sales_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 3, sales_item)

                # 4. Toplam Alış (sağa hizalı)
                purchases = float(b.get('total_purchases') or 0)
                purchases_item = QTableWidgetItem(f"{purchases:,.2f} ₺")
                purchases_item.setForeground(QColor(AppStyles.RED))
                purchases_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 4, purchases_item)

                # 5. Net (sağa hizalı)
                net = sales - purchases
                net_item = QTableWidgetItem(f"{net:,.2f} ₺")
                net_item.setForeground(QColor(AppStyles.GREEN if net >= 0 else AppStyles.RED))
                net_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 5, net_item)
        except Exception as e:
            logger.error(f"Rapor yükleme hatası: {e}")