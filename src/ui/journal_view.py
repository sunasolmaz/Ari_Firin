# src/ui/journal_view.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QGroupBox, QDoubleSpinBox,
    QMessageBox, QDialog, QToolBar, QAction, QDateEdit, QHeaderView
)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QColor, QFont
from ..models.user import User
from ..core.database import db
from ..core.logger import logger


class JournalView(QWidget):
    """Muhasebe defteri görünümü"""

    def __init__(self, user: User, branch_id: int):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.current_page = 1
        self.page_size = 50
        self.selected_entry = None

        self.init_ui()
        self.load_entries()

    def init_ui(self):
        """Arayüzü oluştur"""
        layout = QVBoxLayout()
        layout.setSpacing(10)

        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)

        filter_layout = self.create_filters()
        layout.addLayout(filter_layout)

        self.table = self.create_table()
        layout.addWidget(self.table)

        self.total_widget = self.create_totals()
        layout.addWidget(self.total_widget)

        self.form_group = self.create_form()
        layout.addWidget(self.form_group)

        self.setLayout(layout)

    def create_toolbar(self):
        """Araç çubuğu"""
        toolbar = QToolBar()
        toolbar.setMovable(False)

        add_action = QAction("➕ Yeni Kayıt", self)
        add_action.triggered.connect(self.new_entry)
        toolbar.addAction(add_action)

        edit_action = QAction("✏️ Düzenle", self)
        edit_action.triggered.connect(self.edit_entry)
        toolbar.addAction(edit_action)

        delete_action = QAction("🗑️ Sil", self)
        delete_action.triggered.connect(self.delete_entry)
        toolbar.addAction(delete_action)

        toolbar.addSeparator()

        refresh_action = QAction("🔄 Yenile", self)
        refresh_action.triggered.connect(self.load_entries)
        toolbar.addAction(refresh_action)

        trial_action = QAction("⚖️ Deneme Bilançosu", self)
        trial_action.triggered.connect(self.show_trial_balance)
        toolbar.addAction(trial_action)

        return toolbar

    def create_filters(self):
        """Filtreler"""
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Tarih:"))

        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.start_date.setCalendarPopup(True)
        layout.addWidget(self.start_date)

        layout.addWidget(QLabel(" - "))

        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        layout.addWidget(self.end_date)

        layout.addWidget(QLabel("Hesap Kodu:"))
        self.account_input = QLineEdit()
        self.account_input.setPlaceholderText("Hesap kodu")
        self.account_input.setMaximumWidth(150)
        layout.addWidget(self.account_input)

        filter_btn = QPushButton("🔍 Filtrele")
        filter_btn.clicked.connect(self.load_entries)
        layout.addWidget(filter_btn)

        layout.addStretch()
        return layout

    def create_table(self):
        """Tablo oluştur"""
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            'Tarih', 'Hesap Kodu', 'Hesap Adı', 'Açıklama',
            'Borç', 'Alacak', 'Referans', 'Fatura No'
        ])

        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setDefaultSectionSize(44)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.itemClicked.connect(self.on_row_clicked)

        return table

    def create_totals(self):
        """Toplamlar widget'ı"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.total_debit_label = QLabel("Toplam Borç: 0.00 TL")
        self.total_debit_label.setStyleSheet("font-weight: bold; color: #ef4444;")
        layout.addWidget(self.total_debit_label)

        layout.addSpacing(20)

        self.total_credit_label = QLabel("Toplam Alacak: 0.00 TL")
        self.total_credit_label.setStyleSheet("font-weight: bold; color: #10b981;")
        layout.addWidget(self.total_credit_label)

        layout.addSpacing(20)

        self.balance_label = QLabel("Fark: 0.00 TL")
        self.balance_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.balance_label)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_form(self):
        """Kayıt formu"""
        group = QGroupBox("Muhasebe Kaydı")
        group.setVisible(False)
        layout = QGridLayout()
        layout.setSpacing(10)

        row = 0
        layout.addWidget(QLabel("Tarih:*"), row, 0)
        self.entry_date = QDateEdit()
        self.entry_date.setDate(QDate.currentDate())
        self.entry_date.setCalendarPopup(True)
        layout.addWidget(self.entry_date, row, 1)

        layout.addWidget(QLabel("Hesap Kodu:*"), row, 2)
        self.account_code = QLineEdit()
        self.account_code.setPlaceholderText("Örn: 100")
        layout.addWidget(self.account_code, row, 3)

        row += 1
        layout.addWidget(QLabel("Hesap Adı:*"), row, 0)
        self.account_name = QLineEdit()
        self.account_name.setPlaceholderText("Hesap adı")
        layout.addWidget(self.account_name, row, 1)

        layout.addWidget(QLabel("Açıklama:"), row, 2)
        self.explanation = QLineEdit()
        self.explanation.setPlaceholderText("Açıklama")
        layout.addWidget(self.explanation, row, 3)

        row += 1
        layout.addWidget(QLabel("Borç:"), row, 0)
        self.debit_input = QDoubleSpinBox()
        self.debit_input.setRange(0, 999999999)
        self.debit_input.setPrefix("₺ ")
        self.debit_input.valueChanged.connect(self.on_amount_changed)
        layout.addWidget(self.debit_input, row, 1)

        layout.addWidget(QLabel("Alacak:"), row, 2)
        self.credit_input = QDoubleSpinBox()
        self.credit_input.setRange(0, 999999999)
        self.credit_input.setPrefix("₺ ")
        self.credit_input.valueChanged.connect(self.on_amount_changed)
        layout.addWidget(self.credit_input, row, 3)

        row += 1
        layout.addWidget(QLabel("Referans No:"), row, 0)
        self.reference_no = QLineEdit()
        self.reference_no.setPlaceholderText("Referans numarası")
        layout.addWidget(self.reference_no, row, 1)

        self.balance_check = QLabel("✅ Kayıt Dengeli")
        self.balance_check.setStyleSheet("color: #10b981; font-weight: bold;")
        layout.addWidget(self.balance_check, row, 2, 1, 2)

        row += 1
        btn_layout = QHBoxLayout()

        self.save_btn = QPushButton("💾 Kaydet")
        self.save_btn.clicked.connect(self.save_entry)
        self.save_btn.setStyleSheet("background-color: #10b981;")
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("❌ İptal")
        self.cancel_btn.clicked.connect(self.cancel_form)
        self.cancel_btn.setStyleSheet("background-color: #ef4444;")
        btn_layout.addWidget(self.cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout, row, 0, 1, 4)

        group.setLayout(layout)
        return group

    def load_entries(self):
        """Muhasebe kayıtlarını yükle"""
        try:
            start_date = self.start_date.date().toString("yyyy-MM-dd")
            end_date = self.end_date.date().toString("yyyy-MM-dd")
            account_code = self.account_input.text().strip()

            query = """
                SELECT id, entry_date, account_code, account_name, explanation,
                       debit, credit, reference_no, invoice_id
                FROM JournalEntries 
                WHERE branch_id = %s 
                AND entry_date BETWEEN %s AND %s
            """
            params = [self.branch_id, start_date, end_date]

            if account_code:
                query += " AND account_code LIKE %s"
                params.append(f"{account_code}%")

            query += " ORDER BY entry_date DESC, id DESC"
            offset = (self.current_page - 1) * self.page_size
            query += " LIMIT %s OFFSET %s"
            params.extend([self.page_size, offset])

            results = db.fetch_all(query, tuple(params))

            # Toplam kayıt
            count_query = """
                SELECT COUNT(*) as total FROM JournalEntries 
                WHERE branch_id = %s 
                AND entry_date BETWEEN %s AND %s
            """
            count_params = [self.branch_id, start_date, end_date]
            if account_code:
                count_query += " AND account_code LIKE %s"
                count_params.append(f"{account_code}%")

            total_result = db.fetch_one(count_query, tuple(count_params))
            total = total_result['total'] if total_result else 0

            self.table.setRowCount(0)
            total_debit = 0
            total_credit = 0

            for row, entry in enumerate(results):
                self.table.insertRow(row)

                self.table.setItem(row, 0, QTableWidgetItem(str(entry.get('entry_date', ''))))
                self.table.setItem(row, 1, QTableWidgetItem(entry.get('account_code', '')))
                self.table.setItem(row, 2, QTableWidgetItem(entry.get('account_name', '')))
                self.table.setItem(row, 3, QTableWidgetItem(entry.get('explanation', '')))

                debit = float(entry.get('debit') or 0)
                credit = float(entry.get('credit') or 0)

                debit_item = QTableWidgetItem(f"{debit:,.2f} TL")
                debit_item.setForeground(QColor(231, 76, 60))
                self.table.setItem(row, 4, debit_item)

                credit_item = QTableWidgetItem(f"{credit:,.2f} TL")
                credit_item.setForeground(QColor(46, 204, 113))
                self.table.setItem(row, 5, credit_item)

                total_debit += debit
                total_credit += credit

                self.table.setItem(row, 6, QTableWidgetItem(entry.get('reference_no') or ''))
                self.table.setItem(row, 7, QTableWidgetItem(str(entry.get('invoice_id') or '')))

                # ✅ ID'yi gizli olarak sakla (silme/güncelleme için)
                self.table.item(row, 0).setData(Qt.UserRole, entry.get('id'))

            self.total_debit_label.setText(f"Toplam Borç: {total_debit:,.2f} TL")
            self.total_credit_label.setText(f"Toplam Alacak: {total_credit:,.2f} TL")

            balance = total_debit - total_credit
            self.balance_label.setText(f"Fark: {balance:,.2f} TL")
            if abs(balance) < 0.01:
                self.balance_label.setStyleSheet("font-weight: bold; color: #10b981;")
            else:
                self.balance_label.setStyleSheet("font-weight: bold; color: #ef4444;")

            self.total_widget.setVisible(total > 0)

        except Exception as e:
            logger.error(f"Muhasebe kayıtları yüklenirken hata: {e}")
            QMessageBox.critical(self, "Hata", f"Veriler yüklenemedi: {str(e)}")

    def on_row_clicked(self, item):
        """Satır seçildiğinde — ID'yi de sakla"""
        row = item.row()

        def _parse_amount(text: str) -> float:
            """'1.234,56 TL' formatını float'a çevirir"""
            try:
                return float(
                    text.replace(' TL', '')
                        .replace('.', '')
                        .replace(',', '.')
                        .strip()
                )
            except Exception:
                return 0.0

        try:
            id_item = self.table.item(row, 0)
            entry_id = id_item.data(Qt.UserRole) if id_item else None

            self.selected_entry = {
                'id': entry_id,  # ✅ KRİTİK
                'date': self.table.item(row, 0).text(),
                'account_code': self.table.item(row, 1).text(),
                'account_name': self.table.item(row, 2).text(),
                'explanation': self.table.item(row, 3).text(),
                'debit': _parse_amount(self.table.item(row, 4).text()),
                'credit': _parse_amount(self.table.item(row, 5).text()),
                'reference_no': self.table.item(row, 6).text(),
            }
        except Exception as e:
            logger.error(f"Satır seçme hatası: {e}")

    def on_amount_changed(self):
        """Tutar değiştiğinde denge kontrolü"""
        debit = self.debit_input.value()
        credit = self.credit_input.value()

        if abs(debit - credit) < 0.01:
            self.balance_check.setText("✅ Kayıt Dengeli")
            self.balance_check.setStyleSheet("color: #10b981; font-weight: bold;")
        elif debit > credit:
            self.balance_check.setText(f"⚠️ Borç fazlası: {debit - credit:.2f} TL")
            self.balance_check.setStyleSheet("color: #f59e0b; font-weight: bold;")
        else:
            self.balance_check.setText(f"⚠️ Alacak fazlası: {credit - debit:.2f} TL")
            self.balance_check.setStyleSheet("color: #f59e0b; font-weight: bold;")

    def new_entry(self):
        """Yeni kayıt"""
        self.selected_entry = None
        self.clear_form()
        self.form_group.setVisible(True)
        self.save_btn.setText("➕ Yeni Kayıt")
        self.entry_date.setFocus()

    def edit_entry(self):
        """Kayıt düzenle"""
        if not self.selected_entry or not self.selected_entry.get('id'):
            QMessageBox.warning(self, "Uyarı", "Lütfen bir kayıt seçin!")
            return

        self.form_group.setVisible(True)
        self.save_btn.setText("💾 Güncelle")

        try:
            self.entry_date.setDate(QDate.fromString(self.selected_entry['date'], "yyyy-MM-dd"))
            self.account_code.setText(self.selected_entry['account_code'])
            self.account_name.setText(self.selected_entry['account_name'])
            self.explanation.setText(self.selected_entry['explanation'])
            self.debit_input.setValue(self.selected_entry['debit'])
            self.credit_input.setValue(self.selected_entry['credit'])
            self.reference_no.setText(self.selected_entry['reference_no'] or '')
        except Exception as e:
            logger.error(f"Düzenleme formu doldurma hatası: {e}")

    def delete_entry(self):
        """Kayıt sil — ID ile sil (DELETE LIMIT sorunu çözüldü)"""
        if not self.selected_entry or not self.selected_entry.get('id'):
            QMessageBox.warning(self, "Uyarı", "Lütfen bir kayıt seçin!")
            return

        reply = QMessageBox.question(
            self, "Silme Onayı",
            "Bu muhasebe kaydını silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # ✅ ID ile sil — PostgreSQL uyumlu
                db.execute_query(
                    "DELETE FROM JournalEntries WHERE id = %s AND branch_id = %s",
                    (self.selected_entry['id'], self.branch_id)
                )
                QMessageBox.information(self, "Başarılı", "Kayıt silindi!")
                self.load_entries()
                self.cancel_form()

            except Exception as e:
                logger.error(f"Muhasebe kaydı silme hatası: {e}")
                QMessageBox.critical(self, "Hata", f"Silme hatası: {str(e)}")

    def save_entry(self):
        """Kaydı kaydet — INSERT veya UPDATE"""
        account_code = self.account_code.text().strip()
        account_name = self.account_name.text().strip()

        if not account_code:
            QMessageBox.warning(self, "Uyarı", "Hesap kodu giriniz!")
            return

        if not account_name:
            QMessageBox.warning(self, "Uyarı", "Hesap adı giriniz!")
            return

        debit = self.debit_input.value()
        credit = self.credit_input.value()

        if debit == 0 and credit == 0:
            QMessageBox.warning(self, "Uyarı", "Borç veya alacak giriniz!")
            return

        try:
            entry_date = self.entry_date.date().toString("yyyy-MM-dd")
            explanation = self.explanation.text().strip()
            reference_no = self.reference_no.text().strip()

            if self.selected_entry and self.selected_entry.get('id'):
                # ✅ GÜNCELLE
                db.execute_query("""
                    UPDATE JournalEntries 
                    SET entry_date = %s, account_code = %s, account_name = %s,
                        explanation = %s, debit = %s, credit = %s, reference_no = %s
                    WHERE id = %s AND branch_id = %s
                """, (entry_date, account_code, account_name,
                      explanation, debit, credit, reference_no,
                      self.selected_entry['id'], self.branch_id))
                QMessageBox.information(self, "Başarılı", "Muhasebe kaydı güncellendi!")
            else:
                # ✅ YENİ EKLE
                db.execute_query("""
                    INSERT INTO JournalEntries 
                    (branch_id, entry_date, account_code, account_name, 
                     explanation, debit, credit, reference_no, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (self.branch_id, entry_date, account_code, account_name,
                      explanation, debit, credit, reference_no, self.user.id))
                QMessageBox.information(self, "Başarılı", "Muhasebe kaydı eklendi!")

            self.load_entries()
            self.cancel_form()

        except Exception as e:
            logger.error(f"Muhasebe kaydı hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Kayıt hatası: {str(e)}")

    def cancel_form(self):
        """Formu iptal et"""
        self.form_group.setVisible(False)
        self.clear_form()
        self.selected_entry = None

    def clear_form(self):
        """Formu temizle"""
        self.entry_date.setDate(QDate.currentDate())
        self.account_code.clear()
        self.account_name.clear()
        self.explanation.clear()
        self.debit_input.setValue(0)
        self.credit_input.setValue(0)
        self.reference_no.clear()
        self.balance_check.setText("✅ Kayıt Dengeli")
        self.balance_check.setStyleSheet("color: #10b981; font-weight: bold;")

    def show_trial_balance(self):
        """Deneme bilançosu göster"""
        end_date = self.end_date.date().toString("yyyy-MM-dd")

        try:
            results = db.fetch_all("""
                SELECT 
                    account_code,
                    account_name,
                    COALESCE(SUM(debit), 0) as total_debit,
                    COALESCE(SUM(credit), 0) as total_credit,
                    COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as balance
                FROM JournalEntries 
                WHERE branch_id = %s 
                AND entry_date <= %s
                GROUP BY account_code, account_name
                ORDER BY account_code
            """, (self.branch_id, end_date))

            if not results:
                QMessageBox.information(self, "Bilgi", "Kayıt bulunamadı!")
                return

            dialog = QDialog(self)
            dialog.setWindowTitle("Deneme Bilançosu")
            dialog.setGeometry(200, 200, 800, 500)

            layout = QVBoxLayout()

            title = QLabel(f"📊 Deneme Bilançosu - {end_date}")
            title.setAlignment(Qt.AlignCenter)
            layout.addWidget(title)

            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(['Hesap Kodu', 'Hesap Adı', 'Borç', 'Alacak'])
            table.setColumnWidth(0, 120)
            table.setColumnWidth(1, 250)
            table.setColumnWidth(2, 150)
            table.setColumnWidth(3, 150)
            table.verticalHeader().setDefaultSectionSize(40)
            table.verticalHeader().setVisible(False)

            total_debit = 0
            total_credit = 0

            for row, entry in enumerate(results):
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(entry['account_code']))
                table.setItem(row, 1, QTableWidgetItem(entry['account_name']))

                debit = float(entry['total_debit'] or 0)
                credit = float(entry['total_credit'] or 0)

                debit_item = QTableWidgetItem(f"{debit:,.2f} TL")
                debit_item.setForeground(QColor(231, 76, 60))
                table.setItem(row, 2, debit_item)

                credit_item = QTableWidgetItem(f"{credit:,.2f} TL")
                credit_item.setForeground(QColor(46, 204, 113))
                table.setItem(row, 3, credit_item)

                total_debit += debit
                total_credit += credit

            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem("TOPLAM"))
            table.setItem(row, 1, QTableWidgetItem(""))

            total_debit_item = QTableWidgetItem(f"{total_debit:,.2f} TL")
            total_debit_item.setForeground(QColor(231, 76, 60))
            total_debit_item.setFont(QFont("Arial", 10, QFont.Bold))
            table.setItem(row, 2, total_debit_item)

            total_credit_item = QTableWidgetItem(f"{total_credit:,.2f} TL")
            total_credit_item.setForeground(QColor(46, 204, 113))
            total_credit_item.setFont(QFont("Arial", 10, QFont.Bold))
            table.setItem(row, 3, total_credit_item)

            layout.addWidget(table)

            balance = total_debit - total_credit
            balance_label = QLabel(f"📌 Fark: {balance:,.2f} TL")
            balance_label.setAlignment(Qt.AlignRight)
            if abs(balance) < 0.01:
                balance_label.setStyleSheet("color: #10b981; font-weight: bold; font-size: 14pt;")
            else:
                balance_label.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 14pt;")
            layout.addWidget(balance_label)

            close_btn = QPushButton("Kapat")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn, alignment=Qt.AlignCenter)

            dialog.setLayout(layout)
            dialog.exec_()

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Deneme bilançosu hatası: {str(e)}")

    def on_activated(self):
        self.load_entries()

    def can_close(self):
        if self.form_group.isVisible():
            reply = QMessageBox.question(
                self, "Çıkış",
                "Kaydedilmemiş değişiklikler var. Çıkmak istiyor musunuz?",
                QMessageBox.Yes | QMessageBox.No
            )
            return reply == QMessageBox.Yes
        return True