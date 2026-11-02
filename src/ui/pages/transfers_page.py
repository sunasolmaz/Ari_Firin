# src/ui/pages/transfers_page.py
"""
Para Transferleri Sayfası
Banka hesaplarına para girişi ve para çıkışı işlemleri
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QMessageBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QTextEdit, QGraphicsDropShadowEffect, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from datetime import datetime

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles


class TransfersPage(QWidget):
    """Para transferleri sayfası"""

    def __init__(self, user: User, branch_id: int, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window
        self._has_accounts = False

        self.init_ui()
        self.load_transfers()

    def init_ui(self):
        self.setObjectName("TransfersPage")
        self.setStyleSheet(f"#TransfersPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)

        # Üst bar
        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(3)
        title = QLabel("💸 Para Hareketleri")
        title.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)
        subtitle = QLabel("Banka hesaplarına para girişi ve çıkışı işlemleri")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        top_bar.addLayout(left)
        top_bar.addStretch()

        self.new_btn = QPushButton("➕  Yeni İşlem")
        self.new_btn.clicked.connect(self.new_transfer)
        self.new_btn.setCursor(Qt.PointingHandCursor)
        self.new_btn.setMinimumHeight(42)
        self.new_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                color: white; border: none; border-radius: 8px;
                font-weight: bold; font-size: 11pt; padding: 0 25px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
            }}
            QPushButton:disabled {{
                background: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_MUTED};
            }}
        """)
        top_bar.addWidget(self.new_btn)
        layout.addLayout(top_bar)

        # Uyarı kartı (hesap yoksa görünür)
        self.no_accounts_warning = QFrame()
        self.no_accounts_warning.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(245, 158, 11, 0.1);
                border: 1px solid {AppStyles.ORANGE};
                border-radius: 10px;
                padding: 14px;
            }}
        """)
        warn_layout = QHBoxLayout(self.no_accounts_warning)
        warn_layout.setContentsMargins(12, 8, 12, 8)

        warn_icon = QLabel("⚠️")
        warn_icon.setStyleSheet("font-size: 16pt; background: transparent; border: none;")
        warn_layout.addWidget(warn_icon)

        warn_text = QLabel(
            "Henüz banka hesabı eklenmemiş. İşlem yapabilmek için önce "
            "«🏦 Banka Hesapları» sayfasından bir hesap ekleyin."
        )
        warn_text.setStyleSheet(f"font-size: 10pt; color: {AppStyles.ORANGE}; background: transparent; border: none;")
        warn_text.setWordWrap(True)
        warn_layout.addWidget(warn_text, 1)
        self.no_accounts_warning.setVisible(False)
        layout.addWidget(self.no_accounts_warning)

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
            'Tarih', 'Hesap', 'Tip', 'Tutar', 'Açıklama', 'Referans'
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent; border: none;
                gridline-color: {AppStyles.BORDER}; color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{ padding: 12px; border: none; }}
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

        table_frame.setLayout(table_layout)
        layout.addWidget(table_frame)

        self.setLayout(layout)

    def load_transfers(self):
        """Transfer kayıtlarını yükle"""
        try:
            # Banka hesabı var mı kontrol et
            account_check = db.fetch_one(
                "SELECT COUNT(*) as cnt FROM BankAccounts WHERE branch_id = %s AND is_active = TRUE",
                (self.branch_id,)
            )
            self._has_accounts = bool(account_check and account_check['cnt'] > 0)

            # UI'yı güncelle
            if not self._has_accounts:
                self.new_btn.setEnabled(False)
                self.new_btn.setToolTip("Önce banka hesabı eklemelisiniz")
                self.no_accounts_warning.setVisible(True)
            else:
                self.new_btn.setEnabled(True)
                self.new_btn.setToolTip("")
                self.no_accounts_warning.setVisible(False)

            # Kayıtları getir
            transfers = db.fetch_all("""
                SELECT bt.*, ba.account_name, ba.bank_name
                FROM BankTransactions bt
                LEFT JOIN BankAccounts ba ON ba.id = bt.bank_account_id
                WHERE bt.branch_id = %s
                ORDER BY bt.transaction_date DESC, bt.id DESC
                LIMIT 200
            """, (self.branch_id,))

            self.table.setRowCount(0)
            for i, t in enumerate(transfers):
                self.table.insertRow(i)
                self.table.setItem(i, 0, QTableWidgetItem(str(t.get('transaction_date', ''))))
                self.table.setItem(i, 1, QTableWidgetItem(f"{t.get('bank_name') or ''} - {t.get('account_name') or ''}"))

                trans_type = t.get('transaction_type', '')
                type_text = {'Deposit': 'Giriş', 'Withdrawal': 'Çıkış', 'Transfer': 'Transfer'}.get(trans_type, trans_type)
                type_item = QTableWidgetItem(type_text)
                type_item.setForeground(QColor(
                    AppStyles.GREEN if trans_type == 'Deposit' else
                    AppStyles.RED if trans_type == 'Withdrawal' else
                    AppStyles.PRIMARY
                ))
                self.table.setItem(i, 2, type_item)

                amount = float(t.get('amount', 0))
                amount_item = QTableWidgetItem(f"{amount:,.2f} ₺")
                amount_item.setForeground(QColor(AppStyles.GREEN if trans_type == 'Deposit' else AppStyles.RED))
                amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 3, amount_item)

                self.table.setItem(i, 4, QTableWidgetItem(str(t.get('description') or '')[:40]))
                self.table.setItem(i, 5, QTableWidgetItem(str(t.get('reference_no') or '')))
        except Exception as e:
            logger.error(f"Transfer yükleme hatası: {e}")

    def new_transfer(self):
        """Yeni transfer dialog'unu aç"""
        if not self._has_accounts:
            QMessageBox.warning(
                self, "Banka Hesabı Yok",
                "Önce bir banka hesabı eklemelisiniz.\n\n"
                "Sol menüden «🏦 Banka Hesapları» sayfasına giderek yeni bir hesap ekleyin."
            )
            return

        dialog = TransferDialog(self.user, self.branch_id, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_transfers()


class TransferDialog(QDialog):
    def __init__(self, user, branch_id, parent=None):
        super().__init__(parent)
        self.user = user
        self.branch_id = branch_id

        self.setWindowTitle("Yeni Para İşlemi")
        self.setMinimumSize(520, 520)
        self.setStyleSheet(AppStyles.get_main_style())

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("💸 Yeni Para İşlemi")
        title.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        layout.addWidget(title)

        form = QGridLayout()
        form.setSpacing(12)

        row = 0
        form.addWidget(QLabel("Hesap *"), row, 0)
        self.account_combo = QComboBox()
        self.account_combo.setMinimumHeight(38)
        self.load_accounts()
        form.addWidget(self.account_combo, row, 1)

        row += 1
        form.addWidget(QLabel("İşlem Tipi *"), row, 0)
        self.type_combo = QComboBox()
        # ✅ Sadece Giriş ve Çıkış — "Transfer" kaldırıldı
        self.type_combo.addItems(["Para Girişi", "Para Çıkışı"])
        self.type_combo.setMinimumHeight(38)
        form.addWidget(self.type_combo, row, 1)

        row += 1
        form.addWidget(QLabel("Tutar *"), row, 0)
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0, 99999999)
        self.amount_input.setPrefix("₺ ")
        self.amount_input.setDecimals(2)
        self.amount_input.setMinimumHeight(38)
        form.addWidget(self.amount_input, row, 1)

        row += 1
        form.addWidget(QLabel("Açıklama"), row, 0)
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(100)
        form.addWidget(self.description_input, row, 1)

        row += 1
        form.addWidget(QLabel("Referans No"), row, 0)
        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText("Boş bırakılırsa otomatik üretilir")
        self.reference_input.setMinimumHeight(38)
        form.addWidget(self.reference_input, row, 1)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Save).setText("💾 Kaydet")
        btn_box.button(QDialogButtonBox.Cancel).setText("❌ İptal")
        btn_box.accepted.connect(self.save_transfer)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.setLayout(layout)

    def load_accounts(self):
        """Banka hesaplarını combobox'a yükle"""
        try:
            accounts = db.fetch_all(
                "SELECT id, bank_name, account_name, balance FROM BankAccounts "
                "WHERE branch_id = %s AND is_active = TRUE ORDER BY account_name",
                (self.branch_id,)
            )
            self.account_combo.clear()
            for a in accounts:
                label = f"{a.get('bank_name') or ''} - {a.get('account_name') or ''} (Bakiye: {float(a.get('balance', 0)):,.2f} ₺)"
                self.account_combo.addItem(label, a.get('id'))
        except Exception as e:
            logger.error(f"Hesap yükleme hatası: {e}")

    def save_transfer(self):
        """Transfer kaydet — atomik transaction + bakiye kontrolü"""
        account_id = self.account_combo.currentData()
        amount = self.amount_input.value()

        if not account_id:
            QMessageBox.warning(self, "Uyarı", "Hesap seçiniz!")
            return

        if amount <= 0:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir tutar giriniz (0'dan büyük)!")
            return

        type_map = {"Para Girişi": "Deposit", "Para Çıkışı": "Withdrawal"}
        trans_type = type_map.get(self.type_combo.currentText(), "Deposit")

        try:
            # ✅ Atomik transaction
            with db.transaction():
                # Hesap mevcut mu ve bakiyesi ne?
                account = db.fetch_one(
                    "SELECT id, balance, account_name FROM BankAccounts WHERE id = %s AND branch_id = %s FOR UPDATE",
                    (account_id, self.branch_id)
                )
                if not account:
                    raise ValueError("Seçili hesap bulunamadı!")

                current_balance = float(account.get('balance') or 0)

                # ✅ Yetersiz bakiye kontrolü (sadece çıkışta)
                if trans_type == 'Withdrawal' and amount > current_balance:
                    raise ValueError(
                        f"Yetersiz bakiye!\n\n"
                        f"Hesap: {account.get('account_name', '')}\n"
                        f"Mevcut Bakiye: {current_balance:,.2f} ₺\n"
                        f"Çıkış Tutarı: {amount:,.2f} ₺"
                    )

                # Referans no üret
                reference_no = self.reference_input.text().strip()
                if not reference_no:
                    prefix = "TAH" if trans_type == "Deposit" else "ODM"
                    now_str = datetime.now().strftime('%Y%m%d%H%M%S')
                    reference_no = f"{prefix}-{now_str}"

                # BankTransaction kaydı
                db.execute_query("""
                    INSERT INTO BankTransactions 
                    (branch_id, bank_account_id, transaction_date, transaction_type,
                     amount, description, reference_no, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.branch_id, account_id, datetime.now().date(),
                    trans_type, amount,
                    self.description_input.toPlainText().strip(),
                    reference_no, self.user.id
                ))

                # ✅ Bakiye güncelle (aynı transaction içinde)
                if trans_type == 'Deposit':
                    db.execute_query(
                        "UPDATE BankAccounts SET balance = balance + %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (amount, account_id)
                    )
                else:  # Withdrawal
                    db.execute_query(
                        "UPDATE BankAccounts SET balance = balance - %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (amount, account_id)
                    )

            logger.info(f"✅ Transfer kaydedildi: {trans_type} {amount:,.2f} ₺ (Hesap ID: {account_id})")
            QMessageBox.information(self, "Başarılı", f"İşlem başarıyla kaydedildi!\n\nReferans: {reference_no}")
            self.accept()

        except ValueError as ve:
            QMessageBox.warning(self, "İşlem Reddedildi", str(ve))
        except Exception as e:
            logger.error(f"Transfer kaydetme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Kayıt hatası:\n{str(e)}")