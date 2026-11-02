# src/ui/customer_view.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QGroupBox,
    QTextEdit, QDoubleSpinBox, QCheckBox, QMessageBox, QFileDialog, QToolBar, QAction, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from .styles import AppStyles
from ..services.customer_service import CustomerService
from ..services.excel_service import ExcelService
from ..models.customer import Customer
from ..models.user import User

class CustomerView(QWidget):
    """Cari hesap görünümü"""
    
    def __init__(self, user: User, branch_id: int):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.customer_service = CustomerService()
        self.current_page = 1
        self.page_size = 50
        self.total_pages = 0
        self.selected_customer = None
        self.is_edit_mode = False
        
        self.init_ui()
        self.load_customers()
    
    def init_ui(self):
        """Arayüzü oluştur"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Araç çubuğu
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)
        
        # Arama ve filtreleme
        search_layout = self.create_search_bar()
        layout.addLayout(search_layout)
        
        # Tablo
        self.table = self.create_table()
        layout.addWidget(self.table)
        
        # Sayfalama
        pagination = self.create_pagination()
        layout.addLayout(pagination)
        
        # Form (Yeni ekleme/düzenleme)
        self.form_group = self.create_form()
        layout.addWidget(self.form_group)
        
        self.setLayout(layout)
    
    def create_toolbar(self):
        """Araç çubuğu oluştur"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        
        # Yeni ekle
        add_action = QAction("➕ Yeni Ekle", self)
        add_action.triggered.connect(self.new_customer)
        toolbar.addAction(add_action)
        
        # Düzenle
        edit_action = QAction("✏️ Düzenle", self)
        edit_action.triggered.connect(self.edit_customer)
        toolbar.addAction(edit_action)
        
        # Sil
        delete_action = QAction("🗑️ Sil", self)
        delete_action.triggered.connect(self.delete_customer)
        toolbar.addAction(delete_action)
        
        toolbar.addSeparator()
        
        # Yenile
        refresh_action = QAction("🔄 Yenile", self)
        refresh_action.triggered.connect(self.load_customers)
        toolbar.addAction(refresh_action)
        
        # Excel'e aktar
        export_action = QAction("📤 Excel'e Aktar", self)
        export_action.triggered.connect(self.export_to_excel)
        toolbar.addAction(export_action)
        
        toolbar.addSeparator()
        
        # Şablon oluştur
        template_action = QAction("📄 Şablon Oluştur", self)
        template_action.triggered.connect(self.create_template)
        toolbar.addAction(template_action)
        
        return toolbar
    
    def create_search_bar(self):
        """Arama çubuğu oluştur"""
        layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Ara (Ünvan, Vergi No, Telefon)...")
        self.search_input.returnPressed.connect(self.search_customers)
        layout.addWidget(self.search_input)
        
        search_btn = QPushButton("Ara")
        search_btn.clicked.connect(self.search_customers)
        layout.addWidget(search_btn)
        
        clear_btn = QPushButton("Temizle")
        clear_btn.clicked.connect(self.clear_search)
        layout.addWidget(clear_btn)
        
        layout.addStretch()
        
        # Filtreler
        filter_label = QLabel("Tür:")
        layout.addWidget(filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Tümü", "Müşteri", "Tedarikçi"])
        self.filter_combo.currentTextChanged.connect(self.load_customers)
        layout.addWidget(self.filter_combo)
        
        return layout
    
    def create_table(self):
        """Tablo oluştur"""
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            'Kod', 'Ünvan', 'Vergi No', 'Telefon', 'Email', 'Bakiye', 'Tür', 'Durum'
        ])
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(44)
        table.verticalHeader().setVisible(False)
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                border: none;
                gridline-color: {AppStyles.BORDER};
                color: {AppStyles.TEXT_PRIMARY};
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
                padding: 6px 10px;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                border-right: 1px solid #282838;
                font-weight: bold;
                font-size: 9.5pt;
                min-height: 38px;
            }}
            QHeaderView::section:hover {{
                background-color: #282838;
                color: #FFFFFF !important;
            }}
        """)
        
        # Sütun genişlikleri & Başlık Font/Görünüm
        h_h = table.horizontalHeader()
        h_h.setVisible(True)
        h_h.setFont(QFont("Segoe UI", 9, QFont.Bold))
        h_h.setDefaultAlignment(Qt.AlignCenter)
        h_h.setFixedHeight(38)
        h_h.setSectionResizeMode(QHeaderView.Stretch)
        
        # Seçim
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        
        # Tıklama
        table.itemClicked.connect(self.on_row_clicked)
        
        # Çift tıklama ile düzenle
        table.itemDoubleClicked.connect(self.edit_customer)
        
        return table
    
    def create_pagination(self):
        """Sayfalama oluştur"""
        layout = QHBoxLayout()
        layout.addStretch()
        
        self.prev_btn = QPushButton("◀ Önceki")
        self.prev_btn.clicked.connect(self.prev_page)
        layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel("Sayfa 1 / 1")
        layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("Sonraki ▶")
        self.next_btn.clicked.connect(self.next_page)
        layout.addWidget(self.next_btn)
        
        self.total_label = QLabel("Toplam: 0 kayıt")
        layout.addWidget(self.total_label)
        
        return layout
    
    def create_form(self):
        """Form oluştur"""
        group = QGroupBox("Cari Hesap Bilgileri")
        group.setVisible(False)
        layout = QGridLayout()
        layout.setSpacing(10)
        
        row = 0
        # Ünvan
        layout.addWidget(QLabel("Ünvan:*"), row, 0)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Firma veya kişi adı")
        layout.addWidget(self.title_input, row, 1)
        
        # Vergi No
        layout.addWidget(QLabel("Vergi No:"), row, 2)
        self.tax_no_input = QLineEdit()
        self.tax_no_input.setPlaceholderText("Vergi numarası")
        layout.addWidget(self.tax_no_input, row, 3)
        
        row += 1
        # Vergi Dairesi
        layout.addWidget(QLabel("Vergi Dairesi:"), row, 0)
        self.tax_office_input = QLineEdit()
        layout.addWidget(self.tax_office_input, row, 1)
        
        # Telefon
        layout.addWidget(QLabel("Telefon:"), row, 2)
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Telefon numarası")
        layout.addWidget(self.phone_input, row, 3)
        
        row += 1
        # Email
        layout.addWidget(QLabel("Email:"), row, 0)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email adresi")
        layout.addWidget(self.email_input, row, 1)
        
        # Adres
        layout.addWidget(QLabel("Adres:"), row, 2)
        self.address_input = QTextEdit()
        self.address_input.setMaximumHeight(60)
        layout.addWidget(self.address_input, row, 3)
        
        row += 1
        # Bakiye (sadece görüntüleme)
        layout.addWidget(QLabel("Bakiye:"), row, 0)
        self.balance_label = QLabel("0.00 TL")
        self.balance_label.setStyleSheet("font-weight: bold; color: #10b981;")
        layout.addWidget(self.balance_label, row, 1)
        
        # Kredi Limiti
        layout.addWidget(QLabel("Kredi Limiti:"), row, 2)
        self.credit_limit_input = QDoubleSpinBox()
        self.credit_limit_input.setRange(0, 999999999)
        self.credit_limit_input.setPrefix("₺ ")
        layout.addWidget(self.credit_limit_input, row, 3)
        
        row += 1
        # Tür
        layout.addWidget(QLabel("Tür:"), row, 0)
        self.is_supplier_check = QCheckBox("Tedarikçi")
        layout.addWidget(self.is_supplier_check, row, 1)
        
        # Notlar
        layout.addWidget(QLabel("Notlar:"), row, 2)
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(60)
        layout.addWidget(self.notes_input, row, 3)
        
        row += 1
        # Butonlar
        btn_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 Kaydet")
        self.save_btn.clicked.connect(self.save_customer)
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
    
    def load_customers(self):
        """Cari hesapları yükle"""
        try:
            # Filtre
            filter_type = self.filter_combo.currentText()
            
            customers, total = self.customer_service.get_customers(
                self.branch_id, self.current_page, self.page_size
            )
            
            # Filtre uygula
            if filter_type != "Tümü":
                is_supplier = filter_type == "Tedarikçi"
                customers = [c for c in customers if c.is_supplier == is_supplier]
                total = len(customers)
            
            self.table.setRowCount(0)
            
            for row, customer in enumerate(customers):
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(customer.customer_code or ''))
                self.table.setItem(row, 1, QTableWidgetItem(customer.title or ''))
                self.table.setItem(row, 2, QTableWidgetItem(customer.tax_no or ''))
                self.table.setItem(row, 3, QTableWidgetItem(customer.phone or ''))
                self.table.setItem(row, 4, QTableWidgetItem(customer.email or ''))
                
                # Bakiye
                balance_item = QTableWidgetItem(f"{customer.balance:,.2f} TL")
                if not customer.is_supplier:
                    b_color = QColor(46, 204, 113) if customer.balance > 0.001 else (QColor(231, 76, 60) if customer.balance < -0.001 else QColor(160, 160, 160))
                else:
                    b_color = QColor(231, 76, 60) if customer.balance > 0.001 else (QColor(46, 204, 113) if customer.balance < -0.001 else QColor(160, 160, 160))
                balance_item.setForeground(b_color)
                self.table.setItem(row, 5, balance_item)
                
                self.table.setItem(row, 6, QTableWidgetItem(
                    "Tedarikçi" if customer.is_supplier else "Müşteri"
                ))
                self.table.setItem(row, 7, QTableWidgetItem(
                    "Aktif" if customer.is_active else "Pasif"
                ))
            
            # Sayfalama
            self.total_pages = max(1, (total + self.page_size - 1) // self.page_size)
            self.page_label.setText(f"Sayfa {self.current_page} / {self.total_pages}")
            self.total_label.setText(f"Toplam: {total} kayıt")
            
            self.prev_btn.setEnabled(self.current_page > 1)
            self.next_btn.setEnabled(self.current_page < self.total_pages)
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Veriler yüklenirken hata: {str(e)}")
    
    def search_customers(self):
        """Cari hesap ara"""
        search_term = self.search_input.text().strip()
        if not search_term:
            self.load_customers()
            return
        
        try:
            customers, total = self.customer_service.search_customers(
                self.branch_id, search_term
            )
            
            self.table.setRowCount(0)
            for row, customer in enumerate(customers):
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(customer.customer_code or ''))
                self.table.setItem(row, 1, QTableWidgetItem(customer.title or ''))
                self.table.setItem(row, 2, QTableWidgetItem(customer.tax_no or ''))
                self.table.setItem(row, 3, QTableWidgetItem(customer.phone or ''))
                self.table.setItem(row, 4, QTableWidgetItem(customer.email or ''))
                bal_item = QTableWidgetItem(f"{customer.balance:,.2f} TL")
                if not customer.is_supplier:
                    b_color = QColor(46, 204, 113) if customer.balance > 0.001 else (QColor(231, 76, 60) if customer.balance < -0.001 else QColor(160, 160, 160))
                else:
                    b_color = QColor(231, 76, 60) if customer.balance > 0.001 else (QColor(46, 204, 113) if customer.balance < -0.001 else QColor(160, 160, 160))
                bal_item.setForeground(b_color)
                self.table.setItem(row, 5, bal_item)
                self.table.setItem(row, 6, QTableWidgetItem(
                    "Tedarikçi" if customer.is_supplier else "Müşteri"
                ))
                self.table.setItem(row, 7, QTableWidgetItem(
                    "Aktif" if customer.is_active else "Pasif"
                ))
            
            self.total_label.setText(f"Bulunan: {total} kayıt")
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Arama hatası: {str(e)}")
    
    def clear_search(self):
        """Aramayı temizle"""
        self.search_input.clear()
        self.current_page = 1
        self.load_customers()
    
    def next_page(self):
        """Sonraki sayfa"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_customers()
    
    def prev_page(self):
        """Önceki sayfa"""
        if self.current_page > 1:
            self.current_page -= 1
            self.load_customers()
    
    def on_row_clicked(self, item):
        """Satır seçildiğinde"""
        row = item.row()
        customer_id = self.table.item(row, 0).text()
        
        try:
            # Customer ID'yi bul
            customers, _ = self.customer_service.get_customers(self.branch_id, 1, 9999)
            for c in customers:
                if c.customer_code == customer_id:
                    self.selected_customer = c
                    self.show_customer_details(c)
                    break
                    
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Detay yükleme hatası: {str(e)}")
    
    def show_customer_details(self, customer: Customer):
        """Cari hesap detaylarını göster"""
        self.title_input.setText(customer.title or '')
        self.tax_no_input.setText(customer.tax_no or '')
        self.tax_office_input.setText(customer.tax_office or '')
        self.phone_input.setText(customer.phone or '')
        self.email_input.setText(customer.email or '')
        self.address_input.setText(customer.address or '')
        self.balance_label.setText(f"{customer.balance:,.2f} TL")
        self.credit_limit_input.setValue(customer.credit_limit or 0)
        self.is_supplier_check.setChecked(customer.is_supplier or False)
        self.notes_input.setText(customer.notes or '')
        
        # Renk
        if customer.balance > 0:
            self.balance_label.setStyleSheet("font-weight: bold; color: #10b981;")
        elif customer.balance < 0:
            self.balance_label.setStyleSheet("font-weight: bold; color: #ef4444;")
        else:
            self.balance_label.setStyleSheet("font-weight: bold; color: #10b981;")
    
    def new_customer(self):
        """Yeni cari hesap ekle"""
        self.is_edit_mode = False
        self.selected_customer = None
        self.clear_form()
        self.form_group.setVisible(True)
        self.title_input.setFocus()
        self.save_btn.setText("➕ Yeni Ekle")
    
    def edit_customer(self):
        """Cari hesap düzenle"""
        if not self.selected_customer:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir cari hesap seçin!")
            return
        
        self.is_edit_mode = True
        self.form_group.setVisible(True)
        self.save_btn.setText("💾 Güncelle")
        self.title_input.setFocus()
    
    def delete_customer(self):
        """Cari hesap sil"""
        if not self.selected_customer:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir cari hesap seçin!")
            return
        
        reply = QMessageBox.question(
            self, "Silme Onayı",
            f"{self.selected_customer.title} silinecek. Devam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, message = self.customer_service.delete_customer(self.selected_customer.id)
            if success:
                QMessageBox.information(self, "Başarılı", message)
                self.load_customers()
                self.cancel_form()
            else:
                QMessageBox.warning(self, "Hata", message)
    
    def save_customer(self):
        """Cari hesap kaydet"""
        # Validasyon
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Uyarı", "Ünvan alanı zorunludur!")
            self.title_input.setFocus()
            return
        
        data = {
            'branch_id': self.branch_id,
            'title': title,
            'tax_no': self.tax_no_input.text().strip(),
            'tax_office': self.tax_office_input.text().strip(),
            'phone': self.phone_input.text().strip(),
            'email': self.email_input.text().strip(),
            'address': self.address_input.toPlainText().strip(),
            'credit_limit': self.credit_limit_input.value(),
            'is_supplier': self.is_supplier_check.isChecked(),
            'notes': self.notes_input.toPlainText().strip()
        }
        
        try:
            if self.is_edit_mode and self.selected_customer:
                # Güncelle
                success, message = self.customer_service.update_customer(
                    self.selected_customer.id, data
                )
            else:
                # Yeni ekle
                success, message, customer = self.customer_service.create_customer(data)
            
            if success:
                QMessageBox.information(self, "Başarılı", message)
                self.load_customers()
                self.cancel_form()
            else:
                QMessageBox.warning(self, "Hata", message)
                
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kayıt hatası: {str(e)}")
    
    def cancel_form(self):
        """Formu iptal et"""
        self.form_group.setVisible(False)
        self.clear_form()
        self.selected_customer = None
        self.is_edit_mode = False
    
    def clear_form(self):
        """Formu temizle"""
        self.title_input.clear()
        self.tax_no_input.clear()
        self.tax_office_input.clear()
        self.phone_input.clear()
        self.email_input.clear()
        self.address_input.clear()
        self.balance_label.setText("0.00 TL")
        self.credit_limit_input.setValue(0)
        self.is_supplier_check.setChecked(False)
        self.notes_input.clear()
    
    def export_to_excel(self):
        """Excel'e aktar"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel Dosyasını Kaydet", "cari_hesaplar.xlsx", "Excel Files (*.xlsx)"
        )
        
        if file_path:
            success = self.customer_service.export_customers(self.branch_id, file_path)
            if success:
                QMessageBox.information(self, "Başarılı", f"Veriler aktarıldı:\n{file_path}")
            else:
                QMessageBox.warning(self, "Hata", "Aktarım başarısız!")
    
    def create_template(self):
        """Excel şablonu oluştur"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Şablonu Kaydet", "cari_sablon.xlsx", "Excel Files (*.xlsx)"
        )
        
        if file_path:
            excel_service = ExcelService()
            success = excel_service.export_template('customers', file_path)
            if success:
                QMessageBox.information(self, "Başarılı", f"Şablon oluşturuldu:\n{file_path}")
            else:
                QMessageBox.warning(self, "Hata", "Şablon oluşturulamadı!")
    
    def on_activated(self):
        """Tab aktif olduğunda"""
        self.load_customers()
    
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