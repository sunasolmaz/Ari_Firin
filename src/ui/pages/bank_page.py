# src/ui/pages/bank_page.py
"""
Kasa & Banka Yönetimi Sayfası (Birleştirilmiş & Modüler)
- Sekme 1: 💳 Banka & Kasa Hesaplarım (Hesap listesi, toplam bakiye, hesap ekleme/düzenleme)
- Sekme 2: 💸 Para Giriş / Çıkış & Transfer (Kasadan bankaya aktarım, para yatırma/çekme)
- Sekme 3: 📋 Hesap & Yevmiye Hareketleri (Tüm hesap hareketleri ve yevmiye borç/alacak dökümü)
"""

import re
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QMessageBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QTextEdit, QGraphicsDropShadowEffect, QHeaderView,
    QTabWidget, QDateEdit
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles

IBAN_RE = re.compile(r'^TR\d{24}$', re.IGNORECASE)


# ==================== DİYALOGLAR ====================

class NewAccountDialog(QDialog):
    """Yeni Kasa / Banka Hesabı Ekleme"""

    def __init__(self, user: User, branch_id: int, parent=None):
        super().__init__(parent)
        self.user = user
        self.branch_id = branch_id
        self.setWindowTitle("🏦 Yeni Hesap Ekle")
        self.setMinimumWidth(450)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
            QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 10pt;
            }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("🏦 Yeni Hesap Tanımla")
        title.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        layout.addWidget(title)

        form = QGridLayout()
        form.setSpacing(10)

        form.addWidget(QLabel("Hesap Türü:"), 0, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Banka Hesabı", "Kasa (Nakit Kasası)", "POS / Kredi Kartı Hesabı"])
        form.addWidget(self.type_combo, 0, 1)

        form.addWidget(QLabel("Hesap Adı *:"), 1, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: Ziraat Ticari, Merkez Kasa...")
        form.addWidget(self.name_input, 1, 1)

        form.addWidget(QLabel("Banka / Kurum:"), 2, 0)
        self.bank_input = QLineEdit()
        self.bank_input.setPlaceholderText("Örn: Ziraat, İş Bankası, Garanti veya Kasa")
        form.addWidget(self.bank_input, 2, 1)

        form.addWidget(QLabel("Hesap No:"), 3, 0)
        self.no_input = QLineEdit()
        form.addWidget(self.no_input, 3, 1)

        form.addWidget(QLabel("IBAN:"), 4, 0)
        self.iban_input = QLineEdit()
        self.iban_input.setPlaceholderText("TR ile başlayan 26 haneli IBAN")
        form.addWidget(self.iban_input, 4, 1)

        form.addWidget(QLabel("Açılış Bakiyesi:"), 5, 0)
        self.balance_input = QDoubleSpinBox()
        self.balance_input.setRange(0, 99999999)
        self.balance_input.setSuffix(" ₺")
        form.addWidget(self.balance_input, 5, 1)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Save).setText("💾 Kaydet")
        btn_box.button(QDialogButtonBox.Cancel).setText("İptal")
        btn_box.accepted.connect(self.save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Uyarı", "Hesap adı boş bırakılamaz!")
            return

        iban = self.iban_input.text().strip().replace(" ", "")
        if iban and not IBAN_RE.match(iban):
            QMessageBox.warning(self, "Uyarı", "Geçersiz IBAN formatı! 'TR' ile başlamalı ve 26 karakter olmalıdır.")
            return

        try:
            db.execute_query("""
                INSERT INTO BankAccounts (
                    branch_id, account_name, bank_name, account_no, iban,
                    balance, currency, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, 'TRY', TRUE)
            """, (
                self.branch_id, name, self.bank_input.text().strip(),
                self.no_input.text().strip(), iban, self.balance_input.value()
            ))
            self.accept()
        except Exception as e:
            logger.error(f"Hesap kaydetme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Hesap kaydedilemedi: {e}")


class EditAccountDialog(QDialog):
    """Hesap Düzenleme"""

    def __init__(self, account_data: dict, parent=None):
        super().__init__(parent)
        self.acc = account_data
        self.setWindowTitle("✏️ Hesap Düzenle")
        self.setMinimumWidth(450)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
            QLineEdit, QDoubleSpinBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QGridLayout()
        form.setSpacing(10)

        form.addWidget(QLabel("Hesap Adı *:"), 0, 0)
        self.name_input = QLineEdit(self.acc.get('account_name', ''))
        form.addWidget(self.name_input, 0, 1)

        form.addWidget(QLabel("Banka / Kurum:"), 1, 0)
        self.bank_input = QLineEdit(self.acc.get('bank_name', ''))
        form.addWidget(self.bank_input, 1, 1)

        form.addWidget(QLabel("Hesap No:"), 2, 0)
        self.no_input = QLineEdit(self.acc.get('account_no', ''))
        form.addWidget(self.no_input, 2, 1)

        form.addWidget(QLabel("IBAN:"), 3, 0)
        self.iban_input = QLineEdit(self.acc.get('iban', ''))
        form.addWidget(self.iban_input, 3, 1)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Save).setText("💾 Güncelle")
        btn_box.button(QDialogButtonBox.Cancel).setText("İptal")
        btn_box.accepted.connect(self.save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Uyarı", "Hesap adı boş bırakılamaz!")
            return

        iban = self.iban_input.text().strip().replace(" ", "")
        if iban and not IBAN_RE.match(iban):
            QMessageBox.warning(self, "Uyarı", "Geçersiz IBAN formatı!")
            return

        try:
            db.execute_query("""
                UPDATE BankAccounts 
                SET account_name = %s, bank_name = %s, account_no = %s, iban = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (name, self.bank_input.text().strip(), self.no_input.text().strip(), iban, self.acc['id']))
            self.accept()
        except Exception as e:
            logger.error(f"Hesap güncelleme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Güncellenemedi: {e}")


class NewTransferDialog(QDialog):
    """Para Giriş / Çıkış & Transfer Penceresi"""

    def __init__(self, user: User, branch_id: int, parent=None):
        super().__init__(parent)
        self.user = user
        self.branch_id = branch_id
        self.setWindowTitle("💸 Para İşlemi & Transfer")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
            QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("💸 Yeni Para Hareketi / Transfer")
        title.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {AppStyles.CYAN};")
        layout.addWidget(title)

        form = QGridLayout()
        form.setSpacing(10)

        form.addWidget(QLabel("İşlem Yapılacak Hesap *:"), 0, 0)
        self.account_combo = QComboBox()
        self.load_accounts()
        form.addWidget(self.account_combo, 0, 1)

        form.addWidget(QLabel("İşlem Yönü *:"), 1, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["🟢 Para Girişi (Tahsilat / Yatırma)", "🔴 Para Çıkışı (Ödeme / Çekme)"])
        form.addWidget(self.type_combo, 1, 1)

        form.addWidget(QLabel("Tutar *:"), 2, 0)
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.01, 99999999)
        self.amount_input.setSuffix(" ₺")
        self.amount_input.setDecimals(2)
        form.addWidget(self.amount_input, 2, 1)

        form.addWidget(QLabel("Açıklama:"), 3, 0)
        self.desc_input = QTextEdit()
        self.desc_input.setMaximumHeight(70)
        self.desc_input.setPlaceholderText("İşlem detayı, fatura veya makbuz bilgisi...")
        form.addWidget(self.desc_input, 3, 1)

        form.addWidget(QLabel("Referans No:"), 4, 0)
        self.ref_input = QLineEdit()
        self.ref_input.setPlaceholderText("İsteğe bağlı dekont/makbuz no")
        form.addWidget(self.ref_input, 4, 1)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Save).setText("💾 İşlemi Gerçekleştir")
        btn_box.button(QDialogButtonBox.Cancel).setText("İptal")
        btn_box.accepted.connect(self.save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def load_accounts(self):
        try:
            accounts = db.fetch_all(
                "SELECT id, bank_name, account_name, balance FROM BankAccounts "
                "WHERE branch_id = %s AND is_active = TRUE ORDER BY account_name",
                (self.branch_id,)
            )
            self.account_combo.clear()
            for a in accounts:
                lbl = f"{a.get('account_name')} ({float(a.get('balance', 0)):,.2f} ₺)"
                self.account_combo.addItem(lbl, a.get('id'))
        except Exception as e:
            logger.error(f"Hesap yükleme hatası: {e}")

    def save(self):
        account_id = self.account_combo.currentData()
        amount = self.amount_input.value()
        if not account_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir hesap seçiniz!")
            return
        if amount <= 0:
            QMessageBox.warning(self, "Uyarı", "Tutar 0'dan büyük olmalıdır!")
            return

        is_deposit = "Giriş" in self.type_combo.currentText()
        trans_type = "Deposit" if is_deposit else "Withdrawal"

        try:
            with db.transaction():
                account = db.fetch_one(
                    "SELECT id, balance, account_name FROM BankAccounts WHERE id = %s FOR UPDATE",
                    (account_id,)
                )
                if not account:
                    raise ValueError("Hesap bulunamadı!")

                current_bal = float(account.get('balance') or 0)
                if not is_deposit and amount > current_bal:
                    raise ValueError(f"Yetersiz Bakiye! Mevcut: {current_bal:,.2f} ₺, Çekilmek istenen: {amount:,.2f} ₺")

                new_bal = current_bal + amount if is_deposit else current_bal - amount

                db.execute_query("UPDATE BankAccounts SET balance = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_bal, account_id))

                ref = self.ref_input.text().strip() or f"ISL-{datetime.now().strftime('%y%m%d%H%M')}"
                desc = self.desc_input.toPlainText().strip() or ("Para Girişi" if is_deposit else "Para Çıkışı")

                db.execute_query("""
                    INSERT INTO BankTransactions (
                        branch_id, bank_account_id, transaction_date, transaction_type,
                        amount, description, reference_no, created_by
                    ) VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s, %s)
                """, (self.branch_id, account_id, trans_type, amount, desc, ref, self.user.id if self.user else None))

            self.accept()
        except Exception as e:
            logger.error(f"İşlem hatası: {e}")
            QMessageBox.critical(self, "Hata", str(e))


# ==================== ANA KASA & BANKA SAYFASI ====================

class BankPage(QWidget):
    """
    Kasa & Banka Yönetimi Sayfası
    Banka hesapları, para transferleri ve hesap hareketlerini tek ekranda sunar.
    """

    def __init__(self, user: User, branch_id: int, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window

        self.init_ui()
        self.load_all_data()

    def init_ui(self):
        self.setObjectName("BankPage")
        self.setStyleSheet(f"#BankPage {{ background-color: {AppStyles.BG_DARK}; }}")

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
            QTabBar::tab:hover:!selected {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
            }}
        """)

        # Sekme 1: Hesaplar
        self.accounts_tab = self.create_accounts_tab()
        self.tabs.addTab(self.accounts_tab, "💳 Banka & Kasa Hesaplarım")

        # Sekme 2: Para Transferi / Giriş-Çıkış
        self.transfers_tab = self.create_transfers_tab()
        self.tabs.addTab(self.transfers_tab, "💸 Para Giriş / Çıkış & Hareket")

        # Sekme 3: Yevmiye & Muhasebe Hareketleri
        self.journal_tab = self.create_journal_tab()
        self.tabs.addTab(self.journal_tab, "📋 Hesap Hareketleri & Yevmiye")

        layout.addWidget(self.tabs)

    def create_header(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)

        left = QVBoxLayout()
        left.setSpacing(2)

        title = QLabel("🏦 Kasa & Banka Yönetimi")
        title.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)

        subtitle = QLabel("Kasa hesapları, banka bakiyeleri, para hareketleri ve yevmiye kayıtları")
        subtitle.setStyleSheet(f"font-size: 9.5pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)

        layout.addLayout(left)
        layout.addStretch()

        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.load_all_data)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                color: {AppStyles.TEXT_PRIMARY};
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        layout.addWidget(refresh_btn)

        return header

    # ==================== SEKME 1: HESAPLAR ====================

    def create_accounts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 8, 0, 0)

        # Toplam Bakiye Kartı & Yeni Hesap Butonu
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

        lbl = QLabel("💰 TOPLAM KASA & BANKA BAKİYESİ")
        lbl.setStyleSheet("font-size: 8.5pt; font-weight: bold; color: rgba(255,255,255,0.8);")
        c_lay.addWidget(lbl)

        self.total_balance = QLabel("0,00 ₺")
        self.total_balance.setStyleSheet("font-size: 20pt; font-weight: bold; color: white;")
        c_lay.addWidget(self.total_balance)

        top_h.addWidget(total_card)
        top_h.addStretch()

        new_acc_btn = QPushButton("➕ Yeni Hesap Ekle")
        new_acc_btn.setCursor(Qt.PointingHandCursor)
        new_acc_btn.clicked.connect(self.open_new_account)
        new_acc_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                padding: 10px 20px;
            }}
        """)
        top_h.addWidget(new_acc_btn)

        layout.addLayout(top_h)

        # Hesaplar Tablosu
        self.acc_table = QTableWidget()
        self.acc_table.setColumnCount(7)
        self.acc_table.setHorizontalHeaderLabels([
            'ID', 'Hesap Adı', 'Banka / Tür', 'Hesap No', 'IBAN', 'Bakiye', 'İşlemler'
        ])
        self.acc_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.acc_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.acc_table.setColumnWidth(6, 175)
        self.acc_table.verticalHeader().setDefaultSectionSize(46)
        self.acc_table.verticalHeader().setVisible(False)
        self.acc_table.setStyleSheet(self._table_style())
        layout.addWidget(self.acc_table)

        return widget

    # ==================== SEKME 2: PARA TRANSFERLERİ ====================

    def create_transfers_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 8, 0, 0)

        bar = QHBoxLayout()
        desc = QLabel("Banka ve kasa hesaplarına para girişi, para çıkışı ve şube kasası işlemleri")
        desc.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9.5pt;")
        bar.addWidget(desc)
        bar.addStretch()

        new_trans_btn = QPushButton("💸 Yeni Para Hareketi")
        new_trans_btn.setCursor(Qt.PointingHandCursor)
        new_trans_btn.clicked.connect(self.open_new_transfer)
        new_trans_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                padding: 9px 18px;
            }}
        """)
        bar.addWidget(new_trans_btn)
        layout.addLayout(bar)

        self.trans_table = QTableWidget()
        self.trans_table.setColumnCount(6)
        self.trans_table.setHorizontalHeaderLabels([
            'Tarih', 'Hesap Adı', 'İşlem Tipi', 'Tutar', 'Açıklama', 'Referans No'
        ])
        self.trans_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.trans_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.trans_table.verticalHeader().setDefaultSectionSize(44)
        self.trans_table.verticalHeader().setVisible(False)
        self.trans_table.setStyleSheet(self._table_style())
        layout.addWidget(self.trans_table)

        return widget

    # ==================== SEKME 3: YEVMİYE HAREKETLERİ ====================

    def create_journal_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 8, 0, 0)

        # Filtre Barı
        f_bar = QHBoxLayout()
        f_bar.setSpacing(8)

        f_bar.addWidget(QLabel("Tarih Aralığı:"))
        self.j_start_date = QDateEdit(QDate.currentDate().addDays(-30))
        self.j_start_date.setCalendarPopup(True)
        self.j_start_date.dateChanged.connect(self.load_journal_data)
        f_bar.addWidget(self.j_start_date)

        self.j_end_date = QDateEdit(QDate.currentDate())
        self.j_end_date.setCalendarPopup(True)
        self.j_end_date.dateChanged.connect(self.load_journal_data)
        f_bar.addWidget(self.j_end_date)

        f_bar.addSpacing(12)
        f_bar.addWidget(QLabel("Hesap Kodu:"))
        self.j_code_combo = QComboBox()
        self.j_code_combo.addItem("Tüm Hesaplar", None)
        self.j_code_combo.addItem("100 - Kasa", "100")
        self.j_code_combo.addItem("102 - Bankalar", "102")
        self.j_code_combo.addItem("120 - Alıcılar (Müşteriler)", "120")
        self.j_code_combo.addItem("320 - Satıcılar (Tedarikçiler)", "320")
        self.j_code_combo.addItem("600 - Yurtiçi Satışlar", "600")
        self.j_code_combo.currentIndexChanged.connect(self.load_journal_data)
        f_bar.addWidget(self.j_code_combo)

        f_bar.addStretch()
        layout.addLayout(f_bar)

        self.journal_table = QTableWidget()
        self.journal_table.setColumnCount(7)
        self.journal_table.setHorizontalHeaderLabels([
            'Tarih', 'Fiş No', 'Hesap Kodu', 'Hesap Adı', 'Açıklama', 'Borç (₺)', 'Alacak (₺)'
        ])
        self.journal_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
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
            accounts = db.fetch_all("""
                SELECT id, account_name, bank_name, account_no, iban, balance 
                FROM BankAccounts 
                WHERE branch_id = %s AND is_active = TRUE 
                ORDER BY id ASC
            """, (self.branch_id,))

            total = sum(float(a.get('balance', 0)) for a in accounts)
            self.total_balance.setText(f"{total:,.2f} ₺")

            self.acc_table.setRowCount(len(accounts))
            for row, a in enumerate(accounts):
                self.acc_table.setItem(row, 0, QTableWidgetItem(str(a['id'])))
                self.acc_table.setItem(row, 1, QTableWidgetItem(a.get('account_name') or '-'))
                self.acc_table.setItem(row, 2, QTableWidgetItem(a.get('bank_name') or 'Kasa'))
                self.acc_table.setItem(row, 3, QTableWidgetItem(a.get('account_no') or '-'))
                self.acc_table.setItem(row, 4, QTableWidgetItem(a.get('iban') or '-'))

                b_item = QTableWidgetItem(f"{float(a.get('balance', 0)):,.2f} ₺")
                b_item.setForeground(QColor(AppStyles.SUCCESS if float(a.get('balance', 0)) >= 0 else AppStyles.RED))
                self.acc_table.setItem(row, 5, b_item)

                btn_widget = QWidget()
                btn_widget.setStyleSheet("background: transparent;")
                btn_lay = QHBoxLayout(btn_widget)
                btn_lay.setContentsMargins(2, 2, 2, 2)
                btn_lay.setSpacing(6)
                btn_lay.setAlignment(Qt.AlignCenter)

                edit_btn = QPushButton("✏️ Düzenle")
                edit_btn.setCursor(Qt.PointingHandCursor)
                edit_btn.setFixedSize(76, 30)
                edit_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {AppStyles.ORANGE};
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 4px 6px;
                        font-size: 8.5pt;
                        font-weight: 600;
                    }}
                    QPushButton:hover {{ background-color: #d97706; }}
                """)
                edit_btn.clicked.connect(lambda _, acc=a: self.open_edit_account(acc))
                btn_lay.addWidget(edit_btn)

                del_btn = QPushButton("🗑️ Sil")
                del_btn.setCursor(Qt.PointingHandCursor)
                del_btn.setFixedSize(68, 30)
                del_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {AppStyles.RED};
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 4px 6px;
                        font-size: 8.5pt;
                        font-weight: 600;
                    }}
                    QPushButton:hover {{ background-color: #dc2626; }}
                """)
                del_btn.clicked.connect(lambda _, aid=a['id']: self.delete_account(aid))
                btn_lay.addWidget(del_btn)

                self.acc_table.setCellWidget(row, 6, btn_widget)
        except Exception as e:
            logger.error(f"load_accounts_data hatası: {e}")

    def load_transfers_data(self):
        try:
            trans = db.fetch_all("""
                SELECT bt.*, ba.account_name 
                FROM BankTransactions bt
                LEFT JOIN BankAccounts ba ON ba.id = bt.bank_account_id
                WHERE bt.branch_id = %s 
                ORDER BY bt.transaction_date DESC, bt.id DESC 
                LIMIT 50
            """, (self.branch_id,))

            self.trans_table.setRowCount(len(trans))
            for row, t in enumerate(trans):
                dt_str = t['transaction_date'].strftime('%d.%m.%Y') if hasattr(t['transaction_date'], 'strftime') else str(t['transaction_date'])
                self.trans_table.setItem(row, 0, QTableWidgetItem(dt_str))
                self.trans_table.setItem(row, 1, QTableWidgetItem(t.get('account_name') or 'Hesap'))

                is_dep = t.get('transaction_type') == 'Deposit'
                type_item = QTableWidgetItem("🟢 Para Girişi" if is_dep else "🔴 Para Çıkışı")
                type_item.setForeground(QColor(AppStyles.SUCCESS if is_dep else AppStyles.RED))
                self.trans_table.setItem(row, 2, type_item)

                amt_item = QTableWidgetItem(f"{float(t.get('amount', 0)):,.2f} ₺")
                amt_item.setForeground(QColor(AppStyles.SUCCESS if is_dep else AppStyles.RED))
                self.trans_table.setItem(row, 3, amt_item)

                self.trans_table.setItem(row, 4, QTableWidgetItem(t.get('description') or '-'))
                self.trans_table.setItem(row, 5, QTableWidgetItem(t.get('reference_no') or '-'))
        except Exception as e:
            logger.error(f"load_transfers_data hatası: {e}")

    def load_journal_data(self):
        try:
            start_str = self.j_start_date.date().toString('yyyy-MM-dd')
            end_str = self.j_end_date.date().toString('yyyy-MM-dd')
            code = self.j_code_combo.currentData()

            sql = "SELECT * FROM JournalEntries WHERE branch_id = %s AND entry_date BETWEEN %s AND %s"
            params = [self.branch_id, start_str, end_str]
            if code:
                sql += " AND account_code = %s"
                params.append(code)
            sql += " ORDER BY entry_date DESC, id DESC LIMIT 100"

            rows = db.fetch_all(sql, tuple(params))
            self.journal_table.setRowCount(len(rows))
            for row, r in enumerate(rows):
                dt_str = r['entry_date'].strftime('%d.%m.%Y') if hasattr(r['entry_date'], 'strftime') else str(r['entry_date'])
                self.journal_table.setItem(row, 0, QTableWidgetItem(dt_str))
                self.journal_table.setItem(row, 1, QTableWidgetItem(str(r.get('entry_no') or r.get('id'))))
                self.journal_table.setItem(row, 2, QTableWidgetItem(r.get('account_code') or '-'))
                self.journal_table.setItem(row, 3, QTableWidgetItem(r.get('account_name') or '-'))
                self.journal_table.setItem(row, 4, QTableWidgetItem(r.get('explanation') or '-'))

                debit = float(r.get('debit', 0))
                credit = float(r.get('credit', 0))
                self.journal_table.setItem(row, 5, QTableWidgetItem(f"{debit:,.2f} ₺" if debit > 0 else "-"))
                self.journal_table.setItem(row, 6, QTableWidgetItem(f"{credit:,.2f} ₺" if credit > 0 else "-"))
        except Exception as e:
            logger.error(f"load_journal_data hatası: {e}")

    # ==================== EYLEMLER ====================

    def open_new_account(self):
        dlg = NewAccountDialog(self.user, self.branch_id, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_all_data()

    def open_edit_account(self, acc: dict):
        dlg = EditAccountDialog(acc, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_all_data()

    def delete_account(self, acc_id: int):
        reply = QMessageBox.question(
            self, "Onay", "Bu hesabı silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            db.execute_query("UPDATE BankAccounts SET is_active = FALSE WHERE id = %s", (acc_id,))
            self.load_all_data()

    def open_new_transfer(self):
        dlg = NewTransferDialog(self.user, self.branch_id, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_all_data()

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