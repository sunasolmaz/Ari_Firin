# src/ui/central_pages/all_transactions_page.py
"""
Tüm Şubelerin Hesap Hareketleri - Genel Merkez Görünümü
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QDateEdit, QComboBox,
    QGraphicsDropShadowEffect, QHeaderView, QPushButton
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles


class AllTransactionsPage(QWidget):
    """Tüm şubelerin hesap hareketleri"""
    
    def __init__(self, user: User, central_window=None):
        super().__init__()
        self.user = user
        self.central_window = central_window
        
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        self.setObjectName("AllTransactionsPage")
        self.setStyleSheet(f"#AllTransactionsPage {{ background-color: {AppStyles.BG_DARK}; }}")
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)
        
        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(3)
        title = QLabel("📋 Tüm Hareketler")
        title.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)
        subtitle = QLabel("Tüm şubelerin hesap hareketleri")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        top_bar.addLayout(left)
        top_bar.addStretch()
        layout.addLayout(top_bar)
        
        # Filtreler
        filter_frame = QFrame()
        filter_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                padding: 15px;
                border: 1px solid {AppStyles.BORDER};
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
        
        filter_layout.addWidget(QLabel("☕ Şube:"))
        self.branch_combo = QComboBox()
        self.branch_combo.setMinimumHeight(40)
        self.branch_combo.addItem("Tüm Şubeler", None)
        branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY name")
        for b in branches:
            self.branch_combo.addItem(b['name'], b['id'])
        filter_layout.addWidget(self.branch_combo)
        
        search_btn = QPushButton("🔍 Filtrele")
        search_btn.clicked.connect(self.load_data)
        search_btn.setMinimumHeight(40)
        search_btn.setStyleSheet(f"background-color: {AppStyles.PRIMARY}; color: white; border: none; border-radius: 8px; font-weight: bold; padding: 0 20px;")
        filter_layout.addWidget(search_btn)
        
        filter_layout.addStretch()
        filter_frame.setLayout(filter_layout)
        layout.addWidget(filter_frame)
        
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
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            'Şube', 'Tarih', 'Hesap Kodu', 'Hesap Adı', 'Açıklama', 'Borç', 'Alacak'
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
        
        totals_layout = QHBoxLayout()
        self.total_debit = QLabel("Toplam Borç: 0,00 ₺")
        self.total_debit.setStyleSheet(f"color: {AppStyles.RED}; font-weight: bold; font-size: 11pt;")
        totals_layout.addWidget(self.total_debit)
        
        totals_layout.addSpacing(20)
        
        self.total_credit = QLabel("Toplam Alacak: 0,00 ₺")
        self.total_credit.setStyleSheet(f"color: {AppStyles.GREEN}; font-weight: bold; font-size: 11pt;")
        totals_layout.addWidget(self.total_credit)
        
        totals_layout.addStretch()
        
        self.total_label = QLabel("Toplam: 0 hareket")
        self.total_label.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY};")
        totals_layout.addWidget(self.total_label)
        
        table_layout.addLayout(totals_layout)
        table_frame.setLayout(table_layout)
        layout.addWidget(table_frame)
        
        self.setLayout(layout)
    
    def load_data(self):
        try:
            start = self.start_date.date().toString("yyyy-MM-dd")
            end = self.end_date.date().toString("yyyy-MM-dd")
            branch_id = self.branch_combo.currentData()
            
            query = """
                SELECT je.*, b.name as branch_name
                FROM JournalEntries je
                LEFT JOIN Branches b ON b.id = je.branch_id
                WHERE je.entry_date BETWEEN %s AND %s
            """
            params = [start, end]
            
            if branch_id:
                query += " AND je.branch_id = %s"
                params.append(branch_id)
            
            query += " ORDER BY je.entry_date DESC LIMIT 1000"
            
            transactions = db.fetch_all(query, tuple(params))
            
            self.table.setRowCount(0)
            total_debit = 0
            total_credit = 0
            
            for i, t in enumerate(transactions):
                self.table.insertRow(i)
                self.table.setItem(i, 0, QTableWidgetItem(str(t.get('branch_name', ''))))
                self.table.setItem(i, 1, QTableWidgetItem(str(t.get('entry_date', ''))))
                self.table.setItem(i, 2, QTableWidgetItem(str(t.get('account_code', ''))))
                self.table.setItem(i, 3, QTableWidgetItem(str(t.get('account_name', ''))))
                self.table.setItem(i, 4, QTableWidgetItem(str(t.get('explanation', ''))[:35]))
                
                debit = float(t.get('debit', 0))
                credit = float(t.get('credit', 0))
                
                debit_item = QTableWidgetItem(f"{debit:,.2f} ₺" if debit > 0 else "-")
                debit_item.setForeground(QColor(AppStyles.RED))
                self.table.setItem(i, 5, debit_item)
                
                credit_item = QTableWidgetItem(f"{credit:,.2f} ₺" if credit > 0 else "-")
                credit_item.setForeground(QColor(AppStyles.GREEN))
                self.table.setItem(i, 6, credit_item)
                
                total_debit += debit
                total_credit += credit
            
            self.total_debit.setText(f"Toplam Borç: {total_debit:,.2f} ₺")
            self.total_credit.setText(f"Toplam Alacak: {total_credit:,.2f} ₺")
            self.total_label.setText(f"Toplam: {len(transactions)} hareket")
        except Exception as e:
            logger.error(f"Hareket yükleme hatası: {e}")