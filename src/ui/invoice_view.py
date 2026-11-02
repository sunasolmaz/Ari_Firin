# src/ui/invoice_view.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QGroupBox,
    QTextEdit, QDoubleSpinBox, QDateEdit, QMessageBox, QFileDialog, QToolBar, QAction, QHeaderView
)
from PyQt5.QtCore import QDate
from PyQt5.QtGui import QColor
from ..services.invoice_service import InvoiceService
from ..services.customer_service import CustomerService
from ..models.user import User

class InvoiceView(QWidget):
    """Fatura görünümü"""
    
    def __init__(self, user: User, branch_id: int):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.invoice_service = InvoiceService()
        self.customer_service = CustomerService()
        self.current_page = 1
        self.selected_invoice = None
        self.is_edit_mode = False
        self.items = []
        
        self.init_ui()
        self.load_invoices()
    
    def init_ui(self):
        """Arayüzü oluştur"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Araç çubuğu
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)
        
        # Filtreler
        filter_layout = self.create_filters()
        layout.addLayout(filter_layout)
        
        # Tablo
        self.table = self.create_table()
        layout.addWidget(self.table)
        
        # Form
        self.form_group = self.create_form()
        layout.addWidget(self.form_group)
        
        self.setLayout(layout)
    
    def create_toolbar(self):
        """Araç çubuğu"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        
        add_action = QAction("➕ Yeni Fatura", self)
        add_action.triggered.connect(self.new_invoice)
        toolbar.addAction(add_action)
        
        edit_action = QAction("✏️ Düzenle", self)
        edit_action.triggered.connect(self.edit_invoice)
        toolbar.addAction(edit_action)
        
        approve_action = QAction("✅ Onayla", self)
        approve_action.triggered.connect(self.approve_invoice)
        toolbar.addAction(approve_action)
        
        delete_action = QAction("🗑️ Sil", self)
        delete_action.triggered.connect(self.delete_invoice)
        toolbar.addAction(delete_action)
        
        toolbar.addSeparator()
        
        refresh_action = QAction("🔄 Yenile", self)
        refresh_action.triggered.connect(self.load_invoices)
        toolbar.addAction(refresh_action)
        
        return toolbar
    
    def create_filters(self):
        """Filtreler"""
        layout = QHBoxLayout()
        
        # Tarih aralığı
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
        
        # Tip filtresi
        layout.addWidget(QLabel("Tip:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Tümü", "Satış", "Alış", "İade"])
        layout.addWidget(self.type_combo)
        
        # Durum filtresi
        layout.addWidget(QLabel("Durum:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Tümü", "Taslak", "Onaylandı"])
        layout.addWidget(self.status_combo)
        
        # Filtrele butonu
        filter_btn = QPushButton("🔍 Filtrele")
        filter_btn.clicked.connect(self.load_invoices)
        layout.addWidget(filter_btn)
        
        layout.addStretch()
        
        return layout
    
    def create_table(self):
        """Tablo oluştur"""
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
            'Fatura No', 'Tarih', 'Tip', 'Müşteri', 'Toplam', 'KDV', 'Genel Toplam', 'Durum', 'Ödeme'
        ])
        
        # Sütun genişlikleri & Otomatik Esneme
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setDefaultSectionSize(44)
        table.verticalHeader().setVisible(False)
        
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.itemClicked.connect(self.on_row_clicked)
        
        return table
    
    def create_form(self):
        """Form oluştur"""
        group = QGroupBox("Fatura Bilgileri")
        group.setVisible(False)
        main_layout = QVBoxLayout()
        
        # Fatura başlık bilgileri
        header_layout = QGridLayout()
        header_layout.setSpacing(10)
        
        row = 0
        # Fatura No
        header_layout.addWidget(QLabel("Fatura No:"), row, 0)
        self.invoice_no_input = QLineEdit()
        self.invoice_no_input.setEnabled(False)
        header_layout.addWidget(self.invoice_no_input, row, 1)
        
        # Tarih
        header_layout.addWidget(QLabel("Tarih:*"), row, 2)
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        header_layout.addWidget(self.date_input, row, 3)
        
        row += 1
        # Tip
        header_layout.addWidget(QLabel("Tip:*"), row, 0)
        self.type_input = QComboBox()
        self.type_input.addItems(["Satış", "Alış", "İade"])
        header_layout.addWidget(self.type_input, row, 1)
        
        # Müşteri
        header_layout.addWidget(QLabel("Müşteri:*"), row, 2)
        self.customer_combo = QComboBox()
        self.customer_combo.setEditable(True)
        self.load_customers()
        header_layout.addWidget(self.customer_combo, row, 3)
        
        # Fatura kalemleri
        items_label = QLabel("📄 Fatura Kalemleri")
        items_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        main_layout.addWidget(items_label)
        
        # Kalem tablosu
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(8)
        self.items_table.setHorizontalHeaderLabels([
            'Ürün', 'Miktar', 'Birim', 'Birim Fiyat', 'İskonto %', 'KDV %', 'Toplam', 'İşlem'
        ])
        self.items_table.setColumnWidth(0, 180)
        self.items_table.setColumnWidth(1, 80)
        self.items_table.setColumnWidth(2, 70)
        self.items_table.setColumnWidth(3, 110)
        self.items_table.setColumnWidth(4, 75)
        self.items_table.setColumnWidth(5, 75)
        self.items_table.setColumnWidth(6, 120)
        self.items_table.setColumnWidth(7, 75)
        self.items_table.verticalHeader().setDefaultSectionSize(44)
        self.items_table.verticalHeader().setVisible(False)
        main_layout.addWidget(self.items_table)
        
        # Kalem ekleme
        item_layout = QHBoxLayout()
        item_layout.setSpacing(8)
        
        spin_style = f"""
            QDoubleSpinBox, QLineEdit, QComboBox, QDateEdit {{
                background-color: #1e1e24;
                color: #f9fafb;
                border: 1px solid #2a2a32;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10pt;
                font-weight: 500;
            }}
            QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
                border: 2px solid #10b981;
                background-color: #242430;
                color: #f9fafb;
            }}
        """
        
        self.product_input = QLineEdit()
        self.product_input.setPlaceholderText("Ürün adı")
        self.product_input.setStyleSheet(spin_style)
        item_layout.addWidget(self.product_input)
        
        self.qty_input = QDoubleSpinBox()
        self.qty_input.setRange(0.001, 999999999.999)
        self.qty_input.setValue(1)
        self.qty_input.setPrefix("x ")
        self.qty_input.setStyleSheet(spin_style)
        item_layout.addWidget(self.qty_input)
        
        self.unit_input = QLineEdit()
        self.unit_input.setPlaceholderText("Birim")
        self.unit_input.setText("Adet")
        self.unit_input.setMaximumWidth(80)
        self.unit_input.setStyleSheet(spin_style)
        item_layout.addWidget(self.unit_input)
        
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 999999999999.99)
        self.price_input.setPrefix("₺ ")
        self.price_input.setStyleSheet(spin_style)
        item_layout.addWidget(self.price_input)
        
        self.discount_input = QDoubleSpinBox()
        self.discount_input.setRange(0, 100)
        self.discount_input.setSuffix(" %")
        self.discount_input.setStyleSheet(spin_style)
        item_layout.addWidget(self.discount_input)
        
        self.vat_input = QDoubleSpinBox()
        self.vat_input.setRange(0, 100)
        self.vat_input.setValue(18)
        self.vat_input.setSuffix(" %")
        self.vat_input.setStyleSheet(spin_style)
        item_layout.addWidget(self.vat_input)
        
        add_item_btn = QPushButton("➕ Ekle")
        add_item_btn.clicked.connect(self.add_item)
        item_layout.addWidget(add_item_btn)
        
        main_layout.addLayout(item_layout)
        
        # Toplamlar
        total_layout = QHBoxLayout()
        total_layout.addStretch()
        
        self.subtotal_label = QLabel("Ara Toplam: 0.00 TL")
        self.subtotal_label.setStyleSheet("font-weight: bold;")
        total_layout.addWidget(self.subtotal_label)
        
        self.vat_total_label = QLabel("KDV Toplam: 0.00 TL")
        self.vat_total_label.setStyleSheet("font-weight: bold;")
        total_layout.addWidget(self.vat_total_label)
        
        self.grand_total_label = QLabel("Genel Toplam: 0.00 TL")
        self.grand_total_label.setStyleSheet("font-weight: bold; font-size: 14pt; color: #10b981;")
        total_layout.addWidget(self.grand_total_label)
        
        main_layout.addLayout(total_layout)
        
        # Notlar
        notes_layout = QHBoxLayout()
        notes_layout.addWidget(QLabel("Notlar:"))
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(60)
        notes_layout.addWidget(self.notes_input)
        main_layout.addLayout(notes_layout)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 Kaydet")
        self.save_btn.clicked.connect(self.save_invoice)
        self.save_btn.setStyleSheet("background-color: #10b981;")
        btn_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("❌ İptal")
        self.cancel_btn.clicked.connect(self.cancel_form)
        self.cancel_btn.setStyleSheet("background-color: #ef4444;")
        btn_layout.addWidget(self.cancel_btn)
        
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)
        
        group.setLayout(main_layout)
        return group
    
    def load_customers(self):
        """Müşteri listesini yükle"""
        try:
            customers, _ = self.customer_service.get_customers(self.branch_id, 1, 9999)
            self.customer_combo.clear()
            for customer in customers:
                self.customer_combo.addItem(
                    f"{customer.customer_code} - {customer.title} ({customer.tax_no or ''})",
                    customer.id
                )
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Müşteri listesi yüklenemedi: {str(e)}")
    
    def load_invoices(self):
        """Faturaları yükle"""
        try:
            start_date = self.start_date.date().toString("yyyy-MM-dd")
            end_date = self.end_date.date().toString("yyyy-MM-dd")
            
            invoices, total = self.invoice_service.get_invoices(self.branch_id, self.current_page)
            
            # Filtreleri uygula
            type_filter = self.type_combo.currentText()
            status_filter = self.status_combo.currentText()
            
            self.table.setRowCount(0)
            
            for row, invoice in enumerate(invoices):
                # Filtre kontrol
                if invoice.invoice_date and not (start_date <= str(invoice.invoice_date) <= end_date):
                    continue
                if type_filter != "Tümü" and invoice.invoice_type != type_filter:
                    continue
                if status_filter != "Tümü" and invoice.status != status_filter:
                    continue
                
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(invoice.invoice_no or ''))
                self.table.setItem(row, 1, QTableWidgetItem(str(invoice.invoice_date or '')))
                self.table.setItem(row, 2, QTableWidgetItem(invoice.invoice_type or ''))
                
                # Müşteri adı
                customer_name = ""
                if invoice.customer_id:
                    customer = self.customer_service.get_customer(invoice.customer_id)
                    if customer:
                        customer_name = customer.title
                self.table.setItem(row, 3, QTableWidgetItem(customer_name))
                
                self.table.setItem(row, 4, QTableWidgetItem(f"{invoice.total:,.2f} TL"))
                self.table.setItem(row, 5, QTableWidgetItem(f"{invoice.vat_total:,.2f} TL"))
                self.table.setItem(row, 6, QTableWidgetItem(f"{invoice.grand_total:,.2f} TL"))
                
                # Durum
                status_item = QTableWidgetItem(invoice.status or '')
                if invoice.status == 'Approved':
                    status_item.setForeground(QColor(46, 204, 113))
                elif invoice.status == 'Draft':
                    status_item.setForeground(QColor(243, 156, 18))
                self.table.setItem(row, 7, status_item)
                
                # Ödeme durumu
                payment_item = QTableWidgetItem(invoice.payment_status or '')
                if invoice.payment_status == 'Paid':
                    payment_item.setForeground(QColor(46, 204, 113))
                elif invoice.payment_status == 'Partial':
                    payment_item.setForeground(QColor(243, 156, 18))
                else:
                    payment_item.setForeground(QColor(231, 76, 60))
                self.table.setItem(row, 8, payment_item)
            
            self.total_label = QLabel(f"Toplam: {len(invoices)} kayıt")
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Veriler yüklenirken hata: {str(e)}")
    
    def on_row_clicked(self, item):
        """Satır seçildiğinde"""
        row = item.row()
        invoice_no = self.table.item(row, 0).text()
        
        try:
            invoice = self.invoice_service.get_invoice_by_no(invoice_no)
            if invoice:
                self.selected_invoice = invoice
                self.show_invoice_details(invoice)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Detay yükleme hatası: {str(e)}")
    
    def show_invoice_details(self, invoice):
        """Fatura detaylarını göster"""
        self.invoice_no_input.setText(invoice.invoice_no or '')
        self.date_input.setDate(QDate.fromString(str(invoice.invoice_date), "yyyy-MM-dd"))
        self.type_input.setCurrentText(invoice.invoice_type or '')
        self.notes_input.setText(invoice.notes or '')
        
        # Müşteri seç
        if invoice.customer_id:
            index = self.customer_combo.findData(invoice.customer_id)
            if index >= 0:
                self.customer_combo.setCurrentIndex(index)
        
        # Kalemleri yükle
        self.items = invoice.items if hasattr(invoice, 'items') else []
        self.update_items_table()
        self.update_totals()
    
    def add_item(self):
        """Fatura kalemi ekle"""
        product_name = self.product_input.text().strip()
        if not product_name:
            QMessageBox.warning(self, "Uyarı", "Ürün adı giriniz!")
            return
        
        qty = self.qty_input.value()
        price = self.price_input.value()
        discount = self.discount_input.value()
        vat = self.vat_input.value()
        
        # Hesaplamalar
        subtotal = qty * price
        discount_amount = subtotal * (discount / 100)
        subtotal_after_discount = subtotal - discount_amount
        vat_amount = subtotal_after_discount * (vat / 100)
        total = subtotal_after_discount + vat_amount
        
        item = {
            'product_name': product_name,
            'quantity': qty,
            'unit': self.unit_input.text() or 'Adet',
            'unit_price': price,
            'discount_rate': discount,
            'discount_amount': discount_amount,
            'vat_rate': vat,
            'vat_amount': vat_amount,
            'line_total': total
        }
        
        self.items.append(item)
        self.update_items_table()
        self.update_totals()
        
        # Temizle
        self.product_input.clear()
        self.qty_input.setValue(1)
        self.price_input.setValue(0)
        self.discount_input.setValue(0)
        self.product_input.setFocus()
    
    def remove_item(self, row):
        """Fatura kalemi sil"""
        reply = QMessageBox.question(
            self, "Silme Onayı",
            "Bu kalemi silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.items.pop(row)
            self.update_items_table()
            self.update_totals()
    
    def update_items_table(self):
        """Kalem tablosunu güncelle"""
        self.items_table.setRowCount(0)
        
        for row, item in enumerate(self.items):
            self.items_table.insertRow(row)
            self.items_table.setItem(row, 0, QTableWidgetItem(item['product_name']))
            self.items_table.setItem(row, 1, QTableWidgetItem(str(item['quantity'])))
            self.items_table.setItem(row, 2, QTableWidgetItem(item['unit']))
            self.items_table.setItem(row, 3, QTableWidgetItem(f"{item['unit_price']:,.2f} TL"))
            self.items_table.setItem(row, 4, QTableWidgetItem(f"{item['discount_rate']}%"))
            self.items_table.setItem(row, 5, QTableWidgetItem(f"{item['vat_rate']}%"))
            self.items_table.setItem(row, 6, QTableWidgetItem(f"{item['line_total']:,.2f} TL"))
            
            # Sil butonu
            del_widget = QWidget()
            del_widget.setStyleSheet("background: transparent;")
            del_lay = QHBoxLayout(del_widget)
            del_lay.setContentsMargins(2, 2, 2, 2)
            del_lay.setAlignment(Qt.AlignCenter)

            delete_btn = QPushButton("🗑️ Sil")
            delete_btn.setToolTip("Kalemi Sil")
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.setFixedSize(65, 30)
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 4px 6px;
                    font-size: 8.5pt;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                }
            """)
            delete_btn.clicked.connect(lambda checked, r=row: self.remove_item(r))
            del_lay.addWidget(delete_btn)
            self.items_table.setCellWidget(row, 7, del_widget)
    
    def update_totals(self):
        """Toplamları güncelle"""
        subtotal = sum(item.get('line_total', 0) - item.get('vat_amount', 0) for item in self.items)
        vat_total = sum(item.get('vat_amount', 0) for item in self.items)
        grand_total = subtotal + vat_total
        
        self.subtotal_label.setText(f"Ara Toplam: {subtotal:,.2f} TL")
        self.vat_total_label.setText(f"KDV Toplam: {vat_total:,.2f} TL")
        self.grand_total_label.setText(f"Genel Toplam: {grand_total:,.2f} TL")
    
    def new_invoice(self):
        """Yeni fatura oluştur"""
        self.is_edit_mode = False
        self.selected_invoice = None
        self.items = []
        self.clear_form()
        self.form_group.setVisible(True)
        self.save_btn.setText("➕ Yeni Fatura")
        self.date_input.setFocus()
    
    def edit_invoice(self):
        """Fatura düzenle"""
        if not self.selected_invoice:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir fatura seçin!")
            return
        
        if self.selected_invoice.status == 'Approved':
            QMessageBox.warning(self, "Uyarı", "Onaylanmış faturalar düzenlenemez!")
            return
        
        self.is_edit_mode = True
        self.form_group.setVisible(True)
        self.save_btn.setText("💾 Güncelle")
    
    def approve_invoice(self):
        """Faturayı onayla"""
        if not self.selected_invoice:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir fatura seçin!")
            return
        
        if self.selected_invoice.status == 'Approved':
            QMessageBox.warning(self, "Uyarı", "Fatura zaten onaylanmış!")
            return
        
        reply = QMessageBox.question(
            self, "Onaylama",
            f"{self.selected_invoice.invoice_no} faturasını onaylamak istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, message = self.invoice_service.approve_invoice(self.selected_invoice.id)
            if success:
                QMessageBox.information(self, "Başarılı", message)
                self.load_invoices()
                self.cancel_form()
            else:
                QMessageBox.warning(self, "Hata", message)
    
    def delete_invoice(self):
        """Fatura sil"""
        if not self.selected_invoice:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir fatura seçin!")
            return
        
        warn_msg = f"<b>{self.selected_invoice.invoice_no}</b> faturasını silmek istediğinize emin misiniz?"
        if self.selected_invoice.status == 'Approved':
            warn_msg += "<br><br><span style='color: orange;'>⚠️ <b>Dikkat:</b> Bu fatura <b>ONAYLANMIŞ</b> bir faturadır.<br>Silinmesi durumunda cari hesap bakiyesi otomatik olarak düzeltilecektir.</span>"
        else:
            warn_msg += "<br><br>Bu taslak faturayı kalıcı olarak silmek istiyor musunuz?"
            
        reply = QMessageBox.question(
            self, "Fatura Silme Onayı",
            warn_msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, message = self.invoice_service.delete_invoice(self.selected_invoice.id)
            if success:
                QMessageBox.information(self, "Başarılı", message)
                self.load_invoices()
                self.cancel_form()
            else:
                QMessageBox.warning(self, "Hata", message)
    
    def save_invoice(self):
        """Faturayı kaydet"""
        # Validasyon
        if not self.customer_combo.currentData():
            QMessageBox.warning(self, "Uyarı", "Lütfen bir müşteri seçin!")
            return
        
        if not self.items:
            QMessageBox.warning(self, "Uyarı", "En az bir fatura kalemi girin!")
            return
        
        data = {
            'branch_id': self.branch_id,
            'invoice_date': self.date_input.date().toString("yyyy-MM-dd"),
            'invoice_type': self.type_input.currentText(),
            'customer_id': self.customer_combo.currentData(),
            'notes': self.notes_input.toPlainText().strip(),
            'auto_journal': True
        }
        
        try:
            if self.is_edit_mode and self.selected_invoice:
                # Fatura güncelle
                success, message = self.invoice_service.update_invoice(
                    self.selected_invoice.id, data
                )
            else:
                # Yeni fatura oluştur
                success, message, invoice = self.invoice_service.create_invoice(
                    data, self.items, self.user.id
                )
            
            if success:
                QMessageBox.information(self, "Başarılı", message)
                self.load_invoices()
                self.cancel_form()
            else:
                QMessageBox.warning(self, "Hata", message)
                
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kayıt hatası: {str(e)}")
    
    def cancel_form(self):
        """Formu iptal et"""
        self.form_group.setVisible(False)
        self.clear_form()
        self.selected_invoice = None
        self.is_edit_mode = False
    
    def clear_form(self):
        """Formu temizle"""
        self.invoice_no_input.clear()
        self.date_input.setDate(QDate.currentDate())
        self.type_input.setCurrentIndex(0)
        self.customer_combo.setCurrentIndex(0)
        self.items = []
        self.update_items_table()
        self.update_totals()
        self.notes_input.clear()
    
    def on_activated(self):
        """Tab aktif olduğunda"""
        self.load_invoices()
    
    def can_close(self):
        """Kapatılabilir mi"""
        if self.form_group.isVisible():
            reply = QMessageBox.question(
                self, "Çıkış",
                "Kaydedilmemiş değişiklikler var. Çıkmak istiyor musunuz?",
                QMessageBox.Yes | QMessageBox.No
            )
            return reply == QMessageBox.Yes
        return True