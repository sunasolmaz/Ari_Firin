# src/ui/pages/people_page.py
"""
Kişiler (Cari Hesaplar) Sayfası
"""

import re

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QMessageBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QTextEdit, QCheckBox, QScrollArea,
    QGraphicsDropShadowEffect, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ...models.customer import Customer
from ...services.customer_service import CustomerService
from ..styles import AppStyles

# ✅ Doğrulama regex'leri
EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
PHONE_RE = re.compile(r'^[0-9\s\-\+\(\)]{7,20}$')


class PeoplePage(QWidget):
    """Kişiler (Cari Hesaplar) sayfası"""

    def __init__(self, user: User, branch_id: int, main_window=None, default_type: str = None, title_override: str = None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window
        self.default_type = default_type
        self.title_override = title_override
        self.customer_service = CustomerService()
        self.current_page = 1
        self.total_pages = 1

        self.init_ui()
        if self.default_type:
            idx = self.type_combo.findText(self.default_type)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
        self.load_customers()

    def init_ui(self):
        self.setObjectName("PeoplePage")
        self.setStyleSheet(f"#PeoplePage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)

        # Üst bar
        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(3)
        page_title = self.title_override if self.title_override else "👥 Cari Hesaplar"
        title = QLabel(page_title)
        title.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)
        sub_text = "İmalathaneden alım yapan müşteri ve toptancı listesi" if self.title_override else "Müşteri ve tedarikçi cari hesap yönetimi"
        subtitle = QLabel(sub_text)
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        top_bar.addLayout(left)
        top_bar.addStretch()

        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setToolTip("Cari hesap listesini ve bakiyeleri yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setMinimumHeight(42)
        refresh_btn.clicked.connect(self.load_customers)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                font-weight: bold; font-size: 10.5pt; padding: 0 20px;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """)
        top_bar.addWidget(refresh_btn)

        new_btn = QPushButton("📄 Yeni Fatura Kes")
        new_btn.clicked.connect(self.new_customer)
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.setMinimumHeight(42)
        new_btn.setStyleSheet(f"""
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
        """)
        top_bar.addWidget(new_btn)
        layout.addLayout(top_bar)

        # Arama ve filtre
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Ad, vergi no veya telefon ile ara...")
        self.search_input.setMinimumHeight(42)
        self.search_input.textChanged.connect(self.search_customers)
        filter_layout.addWidget(self.search_input, 3)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Tümü", "Müşteri", "Tedarikçi"])
        self.type_combo.setMinimumHeight(42)
        self.type_combo.setMinimumWidth(150)
        self.type_combo.currentTextChanged.connect(self.load_customers)
        filter_layout.addWidget(self.type_combo, 1)
        layout.addLayout(filter_layout)

        # Tablo
        table_frame = QFrame()
        table_frame.setObjectName("peopleTableFrame")
        table_frame.setStyleSheet(f"""
            QFrame#peopleTableFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 5)
        table_frame.setGraphicsEffect(shadow)

        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(15, 15, 15, 15)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            'Kod', 'Ünvan', 'Vergi No', 'Telefon', 'Fatura', 'Bakiye', 'Bakiye Durumu', 'Tür', 'Email'
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemDoubleClicked.connect(self.edit_customer)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent; border: none;
                gridline-color: {AppStyles.BORDER}; color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{ padding: 8px 10px; border: none; }}
            QTableWidget::item:selected {{ background-color: {AppStyles.PRIMARY}30; }}
            QHeaderView {{
                background-color: #1e1e28;
                border: none;
            }}
            QHeaderView::section {{
                background-color: #1e1e28;
                color: #FFFFFF !important;
                padding: 4px 8px;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                border-right: 1px solid #282838;
                font-weight: bold;
                font-size: 9.5pt;
                height: 38px;
                min-height: 38px;
            }}
            QHeaderView::section:hover {{
                background-color: #282838;
                color: #FFFFFF !important;
            }}
        """)
        h_h = self.table.horizontalHeader()
        h_h.setVisible(True)
        h_h.setFixedHeight(38)
        h_h.setFont(QFont("Segoe UI", 9, QFont.Bold))
        h_h.setDefaultAlignment(Qt.AlignCenter) 
        h_h.setSectionResizeMode(QHeaderView.Stretch)
        h_h.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        table_layout.addWidget(self.table)

        # Alt butonlar
        btn_layout = QHBoxLayout()
        self.total_label = QLabel("Toplam: 0 kişi")
        self.total_label.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY};")
        btn_layout.addWidget(self.total_label)
        btn_layout.addStretch()

        edit_btn = QPushButton("✏️ Düzenle")
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.clicked.connect(self.edit_customer)
        edit_btn.setStyleSheet(
            f"background-color: {AppStyles.ORANGE}; color: white; border: none; "
            "border-radius: 6px; padding: 6px 18px; font-weight: bold; min-height: 32px;"
        )
        btn_layout.addWidget(edit_btn)

        delete_btn = QPushButton("🗑️ Sil")
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(self.delete_customer)
        delete_btn.setStyleSheet(
            f"background-color: {AppStyles.RED}; color: white; border: none; "
            "border-radius: 6px; padding: 6px 18px; font-weight: bold; min-height: 32px;"
        )
        btn_layout.addWidget(delete_btn)

        table_layout.addLayout(btn_layout)
        table_frame.setLayout(table_layout)
        layout.addWidget(table_frame)

        self.setLayout(layout)

    def load_customers(self):
        try:
            filter_type = self.type_combo.currentText()
            search = self.search_input.text().strip()

            query = """
                SELECT c.*, COUNT(i.id) as invoice_count,
                    COALESCE(SUM(CASE WHEN i.invoice_type IN ('Sales', 'Satış') AND (i.status IS NULL OR i.status != 'Cancelled') THEN 
                        CASE WHEN i.payment_status = 'Paid' THEN 0 
                             ELSE COALESCE(i.remaining_amount, i.grand_total - COALESCE(i.paid_amount, 0)) 
                        END ELSE 0 END), 0) as sales_unpaid,
                    COALESCE(SUM(CASE WHEN i.invoice_type IN ('Purchase', 'Alış') AND (i.status IS NULL OR i.status != 'Cancelled') THEN 
                        CASE WHEN i.payment_status = 'Paid' THEN 0 
                             ELSE COALESCE(i.remaining_amount, i.grand_total - COALESCE(i.paid_amount, 0)) 
                        END ELSE 0 END), 0) as purchase_unpaid
                FROM Customers c
                LEFT JOIN Invoices i ON i.customer_id = c.id AND i.branch_id = %s AND (i.status IS NULL OR i.status != 'Cancelled')
                WHERE c.branch_id = %s
                  AND c.is_active = TRUE
            """
            params = [self.branch_id, self.branch_id]

            if filter_type == "Müşteri":
                query += " AND c.is_supplier = FALSE"
            elif filter_type == "Tedarikçi":
                query += " AND c.is_supplier = TRUE"

            if search:
                query += " AND (c.title ILIKE %s OR c.tax_no ILIKE %s OR c.phone ILIKE %s)"
                params.extend([f"%{search}%"] * 3)

            query += """
                GROUP BY c.id, c.customer_code, c.title, c.tax_no, c.tax_office, c.phone, c.email, c.address, c.balance, c.credit_limit, c.is_supplier, c.is_active, c.notes, c.created_at, c.updated_at, c.branch_id
                ORDER BY c.title LIMIT 500
            """

            customers = db.fetch_all(query, tuple(params))

            self.table.setRowCount(0)
            tot_rec = 0.0
            tot_pay = 0.0

            for i, c in enumerate(customers):
                self.table.insertRow(i)
                self.table.setItem(i, 0, QTableWidgetItem(str(c.get('customer_code') or '')))
                self.table.setItem(i, 1, QTableWidgetItem(str(c.get('title') or '')))
                self.table.setItem(i, 2, QTableWidgetItem(str(c.get('tax_no') or '')))
                self.table.setItem(i, 3, QTableWidgetItem(str(c.get('phone') or '')))

                inv_cnt = int(c.get('invoice_count') or 0)
                inv_item = QTableWidgetItem(f"📄 {inv_cnt} Fatura")
                inv_item.setTextAlignment(Qt.AlignCenter)
                inv_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(i, 4, inv_item)

                is_supplier = c.get('is_supplier', False)
                s_unpaid = float(c.get('sales_unpaid') or 0)
                p_unpaid = float(c.get('purchase_unpaid') or 0)
                c_bal = float(c.get('balance') or 0)

                if inv_cnt > 0:
                    receivable = s_unpaid
                    payable = p_unpaid
                else:
                    if is_supplier:
                        payable = max(0.0, c_bal)
                        receivable = max(0.0, -c_bal)
                    else:
                        receivable = max(0.0, c_bal)
                        payable = max(0.0, -c_bal)

                tot_rec += receivable
                tot_pay += payable

                # ✅ Cari hesap bakiye mantığı:
                #   Müşteri (is_supplier = False):
                #     net > 0  → Müşteri bize borçlu (Alacağımız)
                #     net < 0  → Müşteri fazla ödemiş / avans vermiş (Borcumuz)
                #   Tedarikçi (is_supplier = True):
                #     net > 0  → Tedarikçiye borcumuz var (Borcumuz - Ödenecek)
                #     net < 0  → Tedarikçiye fazla ödedik / avans verdik (Alacağımız - Verilen Avans)
                if not is_supplier:  # Müşteri
                    net = receivable - payable
                    if net > 0.001:
                        balance_text = f"{net:,.2f} ₺"
                        status_text = "🟢 Alacağımız (Müşteri Borçlu)"
                        status_color = AppStyles.GREEN
                    elif net < -0.001:
                        balance_text = f"{abs(net):,.2f} ₺"
                        status_text = "🔴 Borcumuz (Avans / Fazla Ödeme)"
                        status_color = AppStyles.RED
                    else:
                        balance_text = "0.00 ₺"
                        status_text = "⚪ Hesap Kapalı (0.00 ₺)"
                        status_color = AppStyles.TEXT_SECONDARY
                else:  # Tedarikçi
                    net = payable - receivable
                    if net > 0.001:
                        balance_text = f"{net:,.2f} ₺"
                        status_text = "🔴 Borcumuz (Tedarikçiye Ödenecek)"
                        status_color = AppStyles.RED
                    elif net < -0.001:
                        balance_text = f"{abs(net):,.2f} ₺"
                        status_text = "🟢 Alacağımız (Verilen Avans)"
                        status_color = AppStyles.GREEN
                    else:
                        balance_text = "0.00 ₺"
                        status_text = "⚪ Hesap Kapalı (0.00 ₺)"
                        status_color = AppStyles.TEXT_SECONDARY

                balance_item = QTableWidgetItem(balance_text)
                balance_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                balance_item.setForeground(QColor(status_color))
                self.table.setItem(i, 5, balance_item)

                status_item = QTableWidgetItem(status_text)
                status_item.setForeground(QColor(status_color))
                self.table.setItem(i, 6, status_item)

                type_item = QTableWidgetItem("Tedarikçi" if is_supplier else "Müşteri")
                type_item.setForeground(QColor(AppStyles.ORANGE if is_supplier else AppStyles.PRIMARY))
                type_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, 7, type_item)

                self.table.setItem(i, 8, QTableWidgetItem(str(c.get('email') or '')))

                self.table.item(i, 0).setData(Qt.UserRole, c.get('id'))

            self.total_label.setText(
                f"Toplam: <b>{len(customers)}</b> Cari Hesap  |  "
                f"Toplam Alacağımız: <b style='color:{AppStyles.GREEN};'>{tot_rec:,.2f} ₺</b>  |  "
                f"Toplam Borcumuz: <b style='color:{AppStyles.RED};'>{tot_pay:,.2f} ₺</b>"
            )
        except Exception as e:
            logger.error(f"Kişi yükleme hatası: {e}")

    def search_customers(self):
        self.load_customers()

    def new_customer(self):
        if self.main_window and hasattr(self.main_window, 'navigate_to'):
            self.main_window.navigate_to("invoices")
        else:
            try:
                from .invoices_page import InvoiceDialog
                dialog = InvoiceDialog(self.user, self.branch_id, self)
                if dialog.exec_() == QDialog.Accepted:
                    self.load_customers()
            except Exception as e:
                logger.error(f"Fatura açma hatası: {e}")

    def edit_customer(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir kişi seçin!")
            return

        customer_id = self.table.item(row, 0).data(Qt.UserRole)
        c_title = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
        try:
            from .invoices_page import CustomerInvoicesDialog
            dlg = CustomerInvoicesDialog(self.user, self.branch_id, customer_id, c_title, self)
            dlg.exec_()
            self.load_customers()
        except Exception as e:
            logger.error(f"Firma detay açma hatası: {e}")

    def delete_customer(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir kişi seçin!")
            return

        customer_id = self.table.item(row, 0).data(Qt.UserRole)

        reply = QMessageBox.question(
            self, "Sil", "Kişiyi silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                db.execute_query(
                    "UPDATE Customers SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (customer_id,)
                )
                QMessageBox.information(self, "Başarılı", "Kişi silindi!")
                self.load_customers()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Silme hatası:\n{str(e)}")


class CustomerDialog(QDialog):
    def __init__(self, branch_id, parent=None, customer_id=None):
        super().__init__(parent)
        self.branch_id = branch_id
        self.customer_id = customer_id

        self.setWindowTitle("Yeni Kişi" if not customer_id else "Kişi Düzenle")
        self.setMinimumSize(550, 650)
        self.setStyleSheet(AppStyles.get_main_style())

        self.init_ui()
        if customer_id:
            self.load_customer()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("👥 " + ("Yeni Kişi" if not self.customer_id else "Kişi Düzenle"))
        title.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        layout.addWidget(title)

        form = QGridLayout()
        form.setSpacing(10)

        row = 0
        form.addWidget(QLabel("Ünvan *"), row, 0)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Firma veya kişi adı")
        form.addWidget(self.title_input, row, 1)

        row += 1
        form.addWidget(QLabel("Vergi No"), row, 0)
        self.tax_no_input = QLineEdit()
        form.addWidget(self.tax_no_input, row, 1)

        row += 1
        form.addWidget(QLabel("Vergi Dairesi"), row, 0)
        self.tax_office_input = QLineEdit()
        form.addWidget(self.tax_office_input, row, 1)

        row += 1
        form.addWidget(QLabel("Telefon"), row, 0)
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("05XX XXX XX XX")
        form.addWidget(self.phone_input, row, 1)

        row += 1
        form.addWidget(QLabel("Email"), row, 0)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("ornek@email.com")
        form.addWidget(self.email_input, row, 1)

        row += 1
        form.addWidget(QLabel("Adres"), row, 0)
        self.address_input = QTextEdit()
        self.address_input.setMaximumHeight(70)
        form.addWidget(self.address_input, row, 1)

        row += 1
        form.addWidget(QLabel("Bakiye"), row, 0)
        self.balance_input = QDoubleSpinBox()
        self.balance_input.setRange(-99999999, 99999999)
        self.balance_input.setPrefix("₺ ")
        form.addWidget(self.balance_input, row, 1)

        row += 1
        form.addWidget(QLabel("Kredi Limiti"), row, 0)
        self.credit_input = QDoubleSpinBox()
        self.credit_input.setRange(0, 99999999)
        self.credit_input.setPrefix("₺ ")
        form.addWidget(self.credit_input, row, 1)

        row += 1
        form.addWidget(QLabel("Tür"), row, 0)
        self.is_supplier_check = QCheckBox("Tedarikçi")
        form.addWidget(self.is_supplier_check, row, 1)

        row += 1
        form.addWidget(QLabel("Notlar"), row, 0)
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(70)
        form.addWidget(self.notes_input, row, 1)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Save).setText("💾 Kaydet")
        btn_box.button(QDialogButtonBox.Cancel).setText("❌ İptal")
        btn_box.accepted.connect(self.save_customer)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.setLayout(layout)

    def load_customer(self):
        try:
            c = db.fetch_one("SELECT * FROM Customers WHERE id = %s", (self.customer_id,))
            if c:
                self.title_input.setText(c.get('title') or '')
                self.tax_no_input.setText(c.get('tax_no') or '')
                self.tax_office_input.setText(c.get('tax_office') or '')
                self.phone_input.setText(c.get('phone') or '')
                self.email_input.setText(c.get('email') or '')
                self.address_input.setText(c.get('address') or '')
                self.balance_input.setValue(float(c.get('balance') or 0))
                self.credit_input.setValue(float(c.get('credit_limit') or 0))
                self.is_supplier_check.setChecked(c.get('is_supplier', False))
                self.notes_input.setText(c.get('notes') or '')
        except Exception as e:
            logger.error(f"Kişi yükleme hatası: {e}")

    def save_customer(self):
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Uyarı", "Ünvan zorunludur!")
            return

        # ✅ Email doğrulaması
        email = self.email_input.text().strip()
        if email and not EMAIL_RE.match(email):
            QMessageBox.warning(
                self, "Geçersiz Email",
                "Email formatı hatalı!\n\nÖrnek: ornek@email.com"
            )
            self.email_input.setFocus()
            return

        # ✅ Telefon doğrulaması (opsiyonel)
        phone = self.phone_input.text().strip()
        if phone and not PHONE_RE.match(phone):
            QMessageBox.warning(
                self, "Geçersiz Telefon",
                "Telefon formatı hatalı!\n\n"
                "Geçerli karakterler: 0-9, boşluk, tire, parantez, artı\n"
                "Örnek: 05XX XXX XX XX veya +90 5XX XXX XX XX"
            )
            self.phone_input.setFocus()
            return

        try:
            if self.customer_id:
                db.execute_query("""
                    UPDATE Customers SET 
                        title = %s, tax_no = %s, tax_office = %s, phone = %s,
                        email = %s, address = %s, balance = %s, credit_limit = %s,
                        is_supplier = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    title, self.tax_no_input.text().strip(), self.tax_office_input.text().strip(),
                    phone, email,
                    self.address_input.toPlainText().strip(), self.balance_input.value(),
                    self.credit_input.value(), self.is_supplier_check.isChecked(),
                    self.notes_input.toPlainText().strip(), self.customer_id
                ))
            else:
                db.execute_query("""
                    INSERT INTO Customers 
                    (branch_id, title, tax_no, tax_office, phone, email,
                     address, balance, credit_limit, is_supplier, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.branch_id, title, self.tax_no_input.text().strip(),
                    self.tax_office_input.text().strip(), phone, email,
                    self.address_input.toPlainText().strip(),
                    self.balance_input.value(), self.credit_input.value(),
                    self.is_supplier_check.isChecked(), self.notes_input.toPlainText().strip()
                ))

            self.accept()
        except Exception as e:
            logger.error(f"Kişi kaydetme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Kayıt hatası:\n{str(e)}")