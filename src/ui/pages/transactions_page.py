# src/ui/pages/transactions_page.py
"""
Muhasebe Hareketleri (Yevmiye) Sayfası
JournalEntries tablosundaki tüm muhasebe kayıtlarını gösterir
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QDateEdit, QComboBox,
    QGraphicsDropShadowEffect, QHeaderView
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles


class TransactionsPage(QWidget):
    """Muhasebe hareketleri (yevmiye) sayfası"""

    def __init__(self, user: User, branch_id: int, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window

        self.init_ui()
        self.load_transactions()

    def init_ui(self):
        self.setObjectName("TransactionsPage")
        self.setStyleSheet(f"#TransactionsPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)

        # Üst bar
        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(3)
        # ✅ Düzeltilmiş başlık
        title = QLabel("📋 Muhasebe Hareketleri (Yevmiye)")
        title.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)
        subtitle = QLabel("Muhasebe yevmiye kayıtları — Borç/Alacak dökümü")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        top_bar.addLayout(left)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Filtreler
        filters = QFrame()
        filters.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                border: 1px solid {AppStyles.BORDER};
                padding: 15px;
            }}
        """)
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("📅 Başlangıç:"))
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd.MM.yyyy")
        self.start_date.setMinimumHeight(40)
        filter_layout.addWidget(self.start_date)

        filter_layout.addWidget(QLabel("📅 Bitiş:"))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("dd.MM.yyyy")
        self.end_date.setMinimumHeight(40)
        filter_layout.addWidget(self.end_date)

        filter_layout.addWidget(QLabel("📌 Tip:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Tümü", "Borç", "Alacak"])
        self.type_combo.setMinimumHeight(40)
        filter_layout.addWidget(self.type_combo)

        search_btn = QPushButton("🔍 Filtrele")
        search_btn.clicked.connect(self.load_transactions)
        search_btn.setMinimumHeight(40)
        search_btn.setStyleSheet(
            f"background-color: {AppStyles.PRIMARY}; color: white; "
            "border: none; border-radius: 8px; font-weight: bold; padding: 0 20px;"
        )
        filter_layout.addWidget(search_btn)

        filter_layout.addStretch()
        filters.setLayout(filter_layout)
        layout.addWidget(filters)

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
            'Tarih', 'Hesap Kodu', 'Hesap Adı', 'Açıklama', 'Borç', 'Alacak'
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent; border: none;
                gridline-color: {AppStyles.BORDER}; color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{ padding: 10px; border: none; }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARKEST};
                color: {AppStyles.TEXT_SECONDARY};
                padding: 12px; border: none;
                border-bottom: 1px solid {AppStyles.BORDER};
                font-weight: 600;
            }}
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.table)

        # Toplamlar
        totals_layout = QHBoxLayout()
        self.total_debit = QLabel("Toplam Borç: 0,00 ₺")
        self.total_debit.setStyleSheet(f"color: {AppStyles.RED}; font-weight: bold; font-size: 11pt;")
        totals_layout.addWidget(self.total_debit)

        totals_layout.addSpacing(20)

        self.total_credit = QLabel("Toplam Alacak: 0,00 ₺")
        self.total_credit.setStyleSheet(f"color: {AppStyles.GREEN}; font-weight: bold; font-size: 11pt;")
        totals_layout.addWidget(self.total_credit)

        totals_layout.addSpacing(20)

        self.balance_label = QLabel("Fark: 0,00 ₺")
        self.balance_label.setStyleSheet(f"color: {AppStyles.PRIMARY}; font-weight: bold; font-size: 11pt;")
        totals_layout.addWidget(self.balance_label)

        totals_layout.addStretch()
        table_layout.addLayout(totals_layout)

        table_frame.setLayout(table_layout)
        layout.addWidget(table_frame)

        self.setLayout(layout)

    def load_transactions(self):
        """Hareketleri yükle"""
        try:
            start = self.start_date.date().toString("yyyy-MM-dd")
            end = self.end_date.date().toString("yyyy-MM-dd")
            type_filter = self.type_combo.currentText()

            query = """
                SELECT * FROM JournalEntries 
                WHERE branch_id = %s AND entry_date BETWEEN %s AND %s
            """
            params = [self.branch_id, start, end]

            if type_filter == "Borç":
                query += " AND debit > 0"
            elif type_filter == "Alacak":
                query += " AND credit > 0"

            query += " ORDER BY entry_date DESC, id DESC LIMIT 500"

            transactions = db.fetch_all(query, tuple(params))

            self.table.setRowCount(0)
            total_debit = 0.0
            total_credit = 0.0

            for i, t in enumerate(transactions):
                self.table.insertRow(i)
                self.table.setItem(i, 0, QTableWidgetItem(str(t.get('entry_date', ''))))
                self.table.setItem(i, 1, QTableWidgetItem(str(t.get('account_code', ''))))
                self.table.setItem(i, 2, QTableWidgetItem(str(t.get('account_name', ''))))
                self.table.setItem(i, 3, QTableWidgetItem(str(t.get('explanation') or '')[:40]))

                debit = float(t.get('debit') or 0)
                credit = float(t.get('credit') or 0)

                debit_item = QTableWidgetItem(f"{debit:,.2f} ₺" if debit > 0 else "-")
                debit_item.setForeground(QColor(AppStyles.RED))
                debit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 4, debit_item)

                credit_item = QTableWidgetItem(f"{credit:,.2f} ₺" if credit > 0 else "-")
                credit_item.setForeground(QColor(AppStyles.GREEN))
                credit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 5, credit_item)

                total_debit += debit
                total_credit += credit

            self.total_debit.setText(f"Toplam Borç: {total_debit:,.2f} ₺")
            self.total_credit.setText(f"Toplam Alacak: {total_credit:,.2f} ₺")

            balance = total_debit - total_credit
            self.balance_label.setText(f"Fark: {balance:,.2f} ₺")
            self.balance_label.setStyleSheet(
                f"color: {AppStyles.GREEN if abs(balance) < 0.01 else AppStyles.RED}; "
                "font-weight: bold; font-size: 11pt;"
            )
        except Exception as e:
            logger.error(f"Hareket yükleme hatası: {e}")