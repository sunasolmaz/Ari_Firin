# src/ui/central_pages/all_transfers_page.py
"""
Tüm Şubelerin Transfer Bilgileri - Genel Merkez Görünümü
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QComboBox,
    QGraphicsDropShadowEffect, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from datetime import datetime, timedelta

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles


class AllTransfersPage(QWidget):
    """Tüm şubelerin transfer bilgileri"""

    def __init__(self, user: User, central_window=None):
        super().__init__()
        self.user = user
        self.central_window = central_window

        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setObjectName("AllTransfersPage")
        self.setStyleSheet(f"#AllTransfersPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)

        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(3)
        title = QLabel("💸 Tüm Para Hareketleri")
        title.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)
        subtitle = QLabel("Tüm şubelerin banka para giriş/çıkış hareketleri")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        top_bar.addLayout(left)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # İstatistik kartları
        stats = self.create_stats_cards()
        layout.addLayout(stats)

        # Filtreler
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("☕ Şube:"))
        self.branch_combo = QComboBox()
        self.branch_combo.setMinimumHeight(42)
        self.branch_combo.addItem("Tüm Şubeler", None)
        branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY name")
        for b in branches:
            self.branch_combo.addItem(b['name'], b['id'])
        self.branch_combo.currentIndexChanged.connect(self.load_data)
        filter_layout.addWidget(self.branch_combo)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

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
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            'Şube', 'Tarih', 'Hesap', 'Tip', 'Tutar', 'Açıklama'
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

        self.total_label = QLabel("Toplam: 0 hareket")
        self.total_label.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; padding: 10px;")
        table_layout.addWidget(self.total_label)

        table_frame.setLayout(table_layout)
        layout.addWidget(table_frame)

        self.setLayout(layout)

    def create_stats_cards(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(15)

        try:
            # Toplam işlem
            total_stats = db.fetch_one("""
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(CASE WHEN transaction_type = 'Deposit' THEN amount END), 0) as deposits,
                    COALESCE(SUM(CASE WHEN transaction_type = 'Withdrawal' THEN amount END), 0) as withdrawals
                FROM BankTransactions
            """)

            # Bugünkü işlem
            today = datetime.now().date().strftime('%Y-%m-%d')
            today_stats = db.fetch_one("""
                SELECT COUNT(*) as count
                FROM BankTransactions
                WHERE transaction_date = %s
            """, (today,))

            total_count = int(total_stats['total']) if total_stats else 0
            deposits = float(total_stats['deposits']) if total_stats else 0.0
            withdrawals = float(total_stats['withdrawals']) if total_stats else 0.0
            today_count = int(today_stats['count']) if today_stats else 0

            cards = [
                ("📊", "Toplam İşlem", str(total_count), AppStyles.PRIMARY),
                ("💰", "Para Girişi", f"{deposits:,.0f} ₺", AppStyles.GREEN),
                ("💸", "Para Çıkışı", f"{withdrawals:,.0f} ₺", AppStyles.RED),
                # ✅ "Transfer" yerine "Bugünkü İşlem"
                ("📅", "Bugünkü İşlem", str(today_count), AppStyles.CYAN),
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
            branch_id = self.branch_combo.currentData()

            query = """
                SELECT bt.*, b.name as branch_name, ba.bank_name, ba.account_name
                FROM BankTransactions bt
                LEFT JOIN Branches b ON b.id = bt.branch_id
                LEFT JOIN BankAccounts ba ON ba.id = bt.bank_account_id
                WHERE 1=1
            """
            params = []

            if branch_id:
                query += " AND bt.branch_id = %s"
                params.append(branch_id)

            query += " ORDER BY bt.transaction_date DESC LIMIT 500"

            transfers = db.fetch_all(query, tuple(params))

            self.table.setRowCount(0)
            for i, t in enumerate(transfers):
                self.table.insertRow(i)

                # 0. Şube
                self.table.setItem(i, 0, QTableWidgetItem(str(t.get('branch_name') or '')))

                # 1. Tarih
                self.table.setItem(i, 1, QTableWidgetItem(str(t.get('transaction_date') or '')))

                # 2. Hesap
                self.table.setItem(i, 2, QTableWidgetItem(
                    f"{t.get('bank_name') or ''} - {t.get('account_name') or ''}"
                ))

                # 3. Tip
                trans_type = t.get('transaction_type') or ''
                type_text = {
                    'Deposit': 'Giriş',
                    'Withdrawal': 'Çıkış',
                    'Transfer': 'Transfer (Eski Kayıt)'
                }.get(trans_type, trans_type)
                type_item = QTableWidgetItem(type_text)
                type_item.setForeground(QColor(
                    AppStyles.GREEN if trans_type == 'Deposit' else
                    AppStyles.RED if trans_type == 'Withdrawal' else
                    AppStyles.PRIMARY
                ))
                self.table.setItem(i, 3, type_item)

                # 4. Tutar (sağa hizalı)
                amount = float(t.get('amount') or 0)
                amount_item = QTableWidgetItem(f"{amount:,.2f} ₺")
                amount_item.setForeground(QColor(AppStyles.GREEN if trans_type == 'Deposit' else AppStyles.RED))
                amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 4, amount_item)

                # 5. Açıklama
                self.table.setItem(i, 5, QTableWidgetItem(str(t.get('description') or '')[:50]))

            self.total_label.setText(f"Toplam: {len(transfers)} hareket")
        except Exception as e:
            logger.error(f"Transfer yükleme hatası: {e}")