# src/ui/central_pages/all_banks_page.py
"""
Tüm Şubelerin Kasa & Banka Yönetimi - Genel Merkez Görünümü
3 Sekmeli Birleşik Finans Merkezi:
- Sekme 1: 💳 Tüm Şube Hesapları & Bakiyeler
- Sekme 2: 💸 Tüm Para Hareketleri & Transferler
- Sekme 3: 📋 Tüm Yevmiye Defteri (Genel Muhasebe)
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QComboBox,
    QGraphicsDropShadowEffect, QHeaderView, QTabWidget, QDateEdit
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont
from datetime import datetime

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles


class AllBanksPage(QWidget):
    """Tüm şubelerin birleşik kasa & banka yönetim merkezi"""

    def __init__(self, user: User, central_window=None):
        super().__init__()
        self.user = user
        self.central_window = central_window

        self.init_ui()
        self.load_all_data()

    def init_ui(self):
        self.setObjectName("AllBanksPage")
        self.setStyleSheet(f"#AllBanksPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # Üst Başlık
        header = self.create_header()
        layout.addWidget(header)

        # Sekmeler
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {AppStyles.BORDER};
                border-radius: 10px;
                background-color: {AppStyles.BG_MEDIUM};
                padding: 12px;
            }}
            QTabBar::tab {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_SECONDARY};
                padding: 10px 22px;
                border: 1px solid {AppStyles.BORDER};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
                font-size: 10pt;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.PRIMARY};
                border-bottom: 2px solid {AppStyles.PRIMARY};
            }}
        """)

        # Sekme 1: Hesaplar
        self.accounts_tab = self.create_accounts_tab()
        self.tabs.addTab(self.accounts_tab, "💳 Tüm Şube Hesapları & Bakiyeler")

        # Sekme 2: Para Hareketleri
        self.transfers_tab = self.create_transfers_tab()
        self.tabs.addTab(self.transfers_tab, "💸 Tüm Para Hareketleri")

        # Sekme 3: Yevmiye Defteri
        self.journal_tab = self.create_journal_tab()
        self.tabs.addTab(self.journal_tab, "📋 Tüm Yevmiye Defteri (Genel Muhasebe)")

        layout.addWidget(self.tabs)

    def create_header(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)

        left = QVBoxLayout()
        left.setSpacing(2)

        title = QLabel("🏦 Tüm Kasa & Bankalar (Genel Merkez)")
        title.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)

        subtitle = QLabel("Tüm perakende şubelerin ve imalathanenin konsolide kasa, banka ve muhasebe hareketleri")
        subtitle.setStyleSheet(f"font-size: 9.5pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)

        layout.addLayout(left)
        layout.addStretch()

        return header

    # ==================== SEKME 1: HESAPLAR ====================

    def create_accounts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 8, 0, 0)

        # Kart & Filtre
        top_h = QHBoxLayout()

        total_card = QFrame()
        total_card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.PURPLE});
                border-radius: 10px;
                padding: 12px 20px;
            }}
        """)
        c_lay = QVBoxLayout(total_card)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(2)

        lbl = QLabel("💰 TÜM ŞUBELERİN TOPLAM BAKİYESİ")
        lbl.setStyleSheet("font-size: 8.5pt; font-weight: bold; color: rgba(255,255,255,0.8);")
        c_lay.addWidget(lbl)

        self.total_balance = QLabel("0,00 ₺")
        self.total_balance.setStyleSheet("font-size: 20pt; font-weight: bold; color: white;")
        c_lay.addWidget(self.total_balance)

        top_h.addWidget(total_card)
        top_h.addStretch()

        f_lay = QHBoxLayout()
        f_lay.addWidget(QLabel("Şube:"))
        self.acc_branch_combo = QComboBox()
        self.acc_branch_combo.addItem("Tüm Şubeler", None)
        branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY id ASC")
        for b in branches:
            self.acc_branch_combo.addItem(b['name'], b['id'])
        self.acc_branch_combo.currentIndexChanged.connect(self.load_accounts_data)
        self.acc_branch_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
            }}
        """)
        f_lay.addWidget(self.acc_branch_combo)
        top_h.addLayout(f_lay)

        layout.addLayout(top_h)

        self.acc_table = QTableWidget()
        self.acc_table.setColumnCount(7)
        self.acc_table.setHorizontalHeaderLabels([
            'Şube', 'Hesap Adı', 'Banka / Tür', 'Hesap No', 'IBAN', 'Bakiye', 'Durum'
        ])
        self.acc_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.acc_table.verticalHeader().setDefaultSectionSize(44)
        self.acc_table.verticalHeader().setVisible(False)
        self.acc_table.setStyleSheet(self._table_style())
        layout.addWidget(self.acc_table)

        return widget

    # ==================== SEKME 2: PARA HAREKETLERİ ====================

    def create_transfers_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 8, 0, 0)

        f_bar = QHBoxLayout()
        f_bar.addWidget(QLabel("Şube:"))
        self.trans_branch_combo = QComboBox()
        self.trans_branch_combo.addItem("Tüm Şubeler", None)
        branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY id ASC")
        for b in branches:
            self.trans_branch_combo.addItem(b['name'], b['id'])
        self.trans_branch_combo.currentIndexChanged.connect(self.load_transfers_data)
        self.trans_branch_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
            }}
        """)
        f_bar.addWidget(self.trans_branch_combo)
        f_bar.addStretch()
        layout.addLayout(f_bar)

        self.trans_table = QTableWidget()
        self.trans_table.setColumnCount(7)
        self.trans_table.setHorizontalHeaderLabels([
            'Tarih', 'Şube', 'Hesap Adı', 'İşlem Tipi', 'Tutar', 'Açıklama', 'Referans'
        ])
        self.trans_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.trans_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.trans_table.verticalHeader().setDefaultSectionSize(44)
        self.trans_table.verticalHeader().setVisible(False)
        self.trans_table.setStyleSheet(self._table_style())
        layout.addWidget(self.trans_table)

        return widget

    # ==================== SEKME 3: YEVMİYE DEFTERİ ====================

    def create_journal_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 8, 0, 0)

        f_bar = QHBoxLayout()
        f_bar.addWidget(QLabel("Tarih Aralığı:"))
        self.j_start_date = QDateEdit(QDate.currentDate().addDays(-30))
        self.j_start_date.setCalendarPopup(True)
        self.j_start_date.dateChanged.connect(self.load_journal_data)
        f_bar.addWidget(self.j_start_date)

        self.j_end_date = QDateEdit(QDate.currentDate())
        self.j_end_date.setCalendarPopup(True)
        self.j_end_date.dateChanged.connect(self.load_journal_data)
        f_bar.addWidget(self.j_end_date)

        f_bar.addSpacing(10)
        f_bar.addWidget(QLabel("Şube:"))
        self.j_branch_combo = QComboBox()
        self.j_branch_combo.addItem("Tüm Şubeler", None)
        branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY id ASC")
        for b in branches:
            self.j_branch_combo.addItem(b['name'], b['id'])
        self.j_branch_combo.currentIndexChanged.connect(self.load_journal_data)
        f_bar.addWidget(self.j_branch_combo)

        f_bar.addStretch()
        layout.addLayout(f_bar)

        self.journal_table = QTableWidget()
        self.journal_table.setColumnCount(8)
        self.journal_table.setHorizontalHeaderLabels([
            'Tarih', 'Şube', 'Fiş No', 'Hesap Kodu', 'Hesap Adı', 'Açıklama', 'Borç (₺)', 'Alacak (₺)'
        ])
        self.journal_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.journal_table.verticalHeader().setDefaultSectionSize(44)
        self.journal_table.verticalHeader().setVisible(False)
        self.journal_table.setStyleSheet(self._table_style())
        layout.addWidget(self.journal_table)

        return widget

    # ==================== VERİ YÜKLEME ====================

    def load_all_data(self):
        self.load_accounts_data()
        self.load_transfers_data()
        self.load_journal_data()

    def load_accounts_data(self):
        try:
            b_id = self.acc_branch_combo.currentData()
            sql = """
                SELECT ba.*, b.name as branch_name 
                FROM BankAccounts ba
                LEFT JOIN Branches b ON b.id = ba.branch_id
                WHERE ba.is_active = TRUE
            """
            params = []
            if b_id:
                sql += " AND ba.branch_id = %s"
                params.append(b_id)
            sql += " ORDER BY ba.branch_id ASC, ba.id ASC"

            accounts = db.fetch_all(sql, tuple(params)) if params else db.fetch_all(sql)
            total = sum(float(a.get('balance', 0)) for a in accounts)
            self.total_balance.setText(f"{total:,.2f} ₺")

            self.acc_table.setRowCount(len(accounts))
            for row, a in enumerate(accounts):
                self.acc_table.setItem(row, 0, QTableWidgetItem(f"🏢 {a.get('branch_name') or 'Şube'}"))
                self.acc_table.setItem(row, 1, QTableWidgetItem(a.get('account_name') or '-'))
                self.acc_table.setItem(row, 2, QTableWidgetItem(a.get('bank_name') or 'Kasa'))
                self.acc_table.setItem(row, 3, QTableWidgetItem(a.get('account_no') or '-'))
                self.acc_table.setItem(row, 4, QTableWidgetItem(a.get('iban') or '-'))

                b_item = QTableWidgetItem(f"{float(a.get('balance', 0)):,.2f} ₺")
                b_item.setForeground(QColor(AppStyles.SUCCESS if float(a.get('balance', 0)) >= 0 else AppStyles.RED))
                self.acc_table.setItem(row, 5, b_item)

                status_item = QTableWidgetItem("🟢 Aktif")
                status_item.setForeground(QColor(AppStyles.SUCCESS))
                self.acc_table.setItem(row, 6, status_item)
        except Exception as e:
            logger.error(f"AllBanksPage load_accounts_data hatası: {e}")

    def load_transfers_data(self):
        try:
            b_id = self.trans_branch_combo.currentData()
            sql = """
                SELECT bt.*, ba.account_name, b.name as branch_name
                FROM BankTransactions bt
                LEFT JOIN BankAccounts ba ON ba.id = bt.bank_account_id
                LEFT JOIN Branches b ON b.id = bt.branch_id
                WHERE 1=1
            """
            params = []
            if b_id:
                sql += " AND bt.branch_id = %s"
                params.append(b_id)
            sql += " ORDER BY bt.transaction_date DESC, bt.id DESC LIMIT 100"

            trans = db.fetch_all(sql, tuple(params)) if params else db.fetch_all(sql)
            self.trans_table.setRowCount(len(trans))
            for row, t in enumerate(trans):
                dt_str = t['transaction_date'].strftime('%d.%m.%Y') if hasattr(t['transaction_date'], 'strftime') else str(t['transaction_date'])
                self.trans_table.setItem(row, 0, QTableWidgetItem(dt_str))
                self.trans_table.setItem(row, 1, QTableWidgetItem(f"🏢 {t.get('branch_name') or 'Şube'}"))
                self.trans_table.setItem(row, 2, QTableWidgetItem(t.get('account_name') or '-'))

                is_dep = t.get('transaction_type') == 'Deposit'
                type_item = QTableWidgetItem("🟢 Giriş" if is_dep else "🔴 Çıkış")
                type_item.setForeground(QColor(AppStyles.SUCCESS if is_dep else AppStyles.RED))
                self.trans_table.setItem(row, 3, type_item)

                amt_item = QTableWidgetItem(f"{float(t.get('amount', 0)):,.2f} ₺")
                amt_item.setForeground(QColor(AppStyles.SUCCESS if is_dep else AppStyles.RED))
                self.trans_table.setItem(row, 4, amt_item)

                self.trans_table.setItem(row, 5, QTableWidgetItem(t.get('description') or '-'))
                self.trans_table.setItem(row, 6, QTableWidgetItem(t.get('reference_no') or '-'))
        except Exception as e:
            logger.error(f"AllBanksPage load_transfers_data hatası: {e}")

    def load_journal_data(self):
        try:
            start_str = self.j_start_date.date().toString('yyyy-MM-dd')
            end_str = self.j_end_date.date().toString('yyyy-MM-dd')
            b_id = self.j_branch_combo.currentData()

            sql = """
                SELECT je.*, b.name as branch_name 
                FROM JournalEntries je
                LEFT JOIN Branches b ON b.id = je.branch_id
                WHERE je.entry_date BETWEEN %s AND %s
            """
            params = [start_str, end_str]
            if b_id:
                sql += " AND je.branch_id = %s"
                params.append(b_id)
            sql += " ORDER BY je.entry_date DESC, je.id DESC LIMIT 150"

            rows = db.fetch_all(sql, tuple(params))
            self.journal_table.setRowCount(len(rows))
            for row, r in enumerate(rows):
                dt_str = r['entry_date'].strftime('%d.%m.%Y') if hasattr(r['entry_date'], 'strftime') else str(r['entry_date'])
                self.journal_table.setItem(row, 0, QTableWidgetItem(dt_str))
                self.journal_table.setItem(row, 1, QTableWidgetItem(f"🏢 {r.get('branch_name') or 'Şube'}"))
                self.journal_table.setItem(row, 2, QTableWidgetItem(str(r.get('entry_no') or r.get('id'))))
                self.journal_table.setItem(row, 3, QTableWidgetItem(r.get('account_code') or '-'))
                self.journal_table.setItem(row, 4, QTableWidgetItem(r.get('account_name') or '-'))
                self.journal_table.setItem(row, 5, QTableWidgetItem(r.get('explanation') or '-'))

                debit = float(r.get('debit', 0))
                credit = float(r.get('credit', 0))
                self.journal_table.setItem(row, 6, QTableWidgetItem(f"{debit:,.2f} ₺" if debit > 0 else "-"))
                self.journal_table.setItem(row, 7, QTableWidgetItem(f"{credit:,.2f} ₺" if credit > 0 else "-"))
        except Exception as e:
            logger.error(f"AllBanksPage load_journal_data hatası: {e}")

    def _table_style(self) -> str:
        return f"""
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                gridline-color: {AppStyles.BORDER};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_SECONDARY};
                font-weight: bold;
                border: none;
                border-bottom: 1px solid {AppStyles.BORDER};
                padding: 8px;
            }}
            QTableWidget::item {{
                padding: 6px;
            }}
        """