# src/ui/central_pages/warehouse_page.py
"""
Merkez Depo & Sevkiyat Yönetimi Sayfası
Genel Merkez (Ana Giriş) için depo ürün & stok durumu,
stok giriş/çıkış (azaltma/artırma) ve şubelere dağıtım/sevkiyat takibi
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QDoubleSpinBox, QMessageBox, QFileDialog, QHeaderView,
    QGraphicsDropShadowEffect, QScrollArea, QTabWidget, QDialog,
    QDateEdit, QTextEdit, QDialogButtonBox, QCheckBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont
from datetime import datetime
import pandas as pd

from ...models.user import User
from ...models.branch import Branch
from ...core.database import db
from ...core.logger import logger
from ...services.warehouse_service import warehouse_service
from ..styles import AppStyles


# ==================== DİALOG PENCERELERİ ====================

class AddWarehouseProductDialog(QDialog):
    """Yeni Depo Ürünü / Hammaddesi Ekleme"""

    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("➕ Yeni Depo Ürünü / Hammaddesi Ekle")
        self.setMinimumWidth(500)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("➕ Yeni Depo Ürünü Ekle")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        layout.addWidget(title)

        form = QGridLayout()
        form.setSpacing(10)

        # Ürün Kodu
        form.addWidget(QLabel("Ürün Kodu (İsteğe Bağlı):"), 0, 0)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Boş bırakılırsa otomatik üretilir (DEP-XXXX)")
        self.code_input.setStyleSheet(self._input_style())
        form.addWidget(self.code_input, 0, 1)

        # Ürün Adı
        form.addWidget(QLabel("Ürün Adı *:"), 1, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: Un (Tip 550), Maya, Susam...")
        self.name_input.setStyleSheet(self._input_style())
        form.addWidget(self.name_input, 1, 1)

        # Kategori
        form.addWidget(QLabel("Kategori:"), 2, 0)
        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        self.cat_combo.addItems(["Hammadde", "Ambalaj", "Katkı Maddesi", "Mamül", "Yarı Mamül", "Temizlik / Sarf"])
        self.cat_combo.setStyleSheet(self._input_style())
        form.addWidget(self.cat_combo, 2, 1)

        # Birim
        form.addWidget(QLabel("Birim:"), 3, 0)
        self.unit_combo = QComboBox()
        self.unit_combo.setEditable(True)
        self.unit_combo.addItems(["Çuval (50 Kg)", "Çuval (25 Kg)", "Koli", "Adet", "Kg", "Teneke (18 Lt)", "Paket", "Litre"])
        self.unit_combo.setStyleSheet(self._input_style())
        form.addWidget(self.unit_combo, 3, 1)

        # Başlangıç Stoğu
        form.addWidget(QLabel("Başlangıç Stoğu:"), 4, 0)
        self.stock_spin = QDoubleSpinBox()
        self.stock_spin.setRange(0, 1000000)
        self.stock_spin.setValue(0)
        self.stock_spin.setStyleSheet(self._input_style())
        form.addWidget(self.stock_spin, 4, 1)

        # Kritik Stok Eşiği
        form.addWidget(QLabel("Kritik Stok Uyarı Eşiği:"), 5, 0)
        self.crit_spin = QDoubleSpinBox()
        self.crit_spin.setRange(0, 100000)
        self.crit_spin.setValue(10)
        self.crit_spin.setStyleSheet(self._input_style())
        form.addWidget(self.crit_spin, 5, 1)

        # Alış Fiyatı
        form.addWidget(QLabel("Birim Alış Fiyatı (₺):"), 6, 0)
        self.purchase_spin = QDoubleSpinBox()
        self.purchase_spin.setRange(0, 1000000)
        self.purchase_spin.setDecimals(2)
        self.purchase_spin.setStyleSheet(self._input_style())
        form.addWidget(self.purchase_spin, 6, 1)

        # Açıklama / Not
        form.addWidget(QLabel("Notlar:"), 7, 0)
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("İsteğe bağlı ürün notu...")
        self.notes_input.setStyleSheet(self._input_style())
        form.addWidget(self.notes_input, 7, 1)

        layout.addLayout(form)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"background-color: transparent; color: {AppStyles.TEXT_SECONDARY}; border: 1px solid {AppStyles.BORDER}; border-radius: 8px; padding: 8px 16px;")
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Kaydet")
        save_btn.clicked.connect(self.save)
        save_btn.setStyleSheet(f"background-color: {AppStyles.PRIMARY}; color: white; border: none; border-radius: 8px; padding: 8px 22px; font-weight: bold;")
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        self.setLayout(layout)

    def save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Uyarı", "Ürün adı boş bırakılamaz!")
            return

        data = {
            'product_code': self.code_input.text().strip(),
            'name': name,
            'category': self.cat_combo.currentText().strip(),
            'unit': self.unit_combo.currentText().strip(),
            'stock_quantity': self.stock_spin.value(),
            'critical_stock': self.crit_spin.value(),
            'purchase_price': self.purchase_spin.value(),
            'sale_price': 0,
            'notes': self.notes_input.text().strip()
        }

        user_id = getattr(self.user, 'id', None)
        success, msg, _ = warehouse_service.add_product(data, user_id)
        if success:
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _input_style(self):
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 10pt;
        """


class EditWarehouseProductDialog(QDialog):
    """Mevcut Depo Ürününü Düzenleme"""

    def __init__(self, user: User, product: dict, parent=None):
        super().__init__(parent)
        self.user = user
        self.product = product
        self.setWindowTitle(f"✏️ Ürünü Düzenle: {product.get('name', '')}")
        self.setMinimumWidth(500)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("✏️ Depo Ürününü Düzenle")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.ORANGE};")
        layout.addWidget(title)

        form = QGridLayout()
        form.setSpacing(10)

        p = self.product

        # Ürün Kodu (salt okunur)
        form.addWidget(QLabel("Ürün Kodu:"), 0, 0)
        self.code_input = QLineEdit(p.get('product_code', ''))
        self.code_input.setReadOnly(True)
        self.code_input.setStyleSheet(self._input_style())
        form.addWidget(self.code_input, 0, 1)

        # Ürün Adı
        form.addWidget(QLabel("Ürün Adı *:"), 1, 0)
        self.name_input = QLineEdit(p.get('name', ''))
        self.name_input.setStyleSheet(self._input_style())
        form.addWidget(self.name_input, 1, 1)

        # Kategori
        form.addWidget(QLabel("Kategori:"), 2, 0)
        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        self.cat_combo.addItems(["Hammadde", "Ambalaj", "Katkı Maddesi", "Mamül", "Yarı Mamül", "Temizlik / Sarf"])
        self.cat_combo.setCurrentText(p.get('category', 'Hammadde') or 'Hammadde')
        self.cat_combo.setStyleSheet(self._input_style())
        form.addWidget(self.cat_combo, 2, 1)

        # Birim
        form.addWidget(QLabel("Birim:"), 3, 0)
        self.unit_combo = QComboBox()
        self.unit_combo.setEditable(True)
        self.unit_combo.addItems(["Çuval (50 Kg)", "Çuval (25 Kg)", "Koli", "Adet", "Kg", "Teneke (18 Lt)", "Paket", "Litre"])
        self.unit_combo.setCurrentText(p.get('unit', 'Adet') or 'Adet')
        self.unit_combo.setStyleSheet(self._input_style())
        form.addWidget(self.unit_combo, 3, 1)

        # Kritik Stok
        form.addWidget(QLabel("Kritik Stok Eşiği:"), 4, 0)
        self.crit_spin = QDoubleSpinBox()
        self.crit_spin.setRange(0, 100000)
        self.crit_spin.setValue(float(p.get('critical_stock', 10) or 10))
        self.crit_spin.setStyleSheet(self._input_style())
        form.addWidget(self.crit_spin, 4, 1)

        # Alış Fiyatı
        form.addWidget(QLabel("Birim Alış Fiyatı (₺):"), 5, 0)
        self.purchase_spin = QDoubleSpinBox()
        self.purchase_spin.setRange(0, 1000000)
        self.purchase_spin.setDecimals(2)
        self.purchase_spin.setValue(float(p.get('purchase_price', 0) or 0))
        self.purchase_spin.setStyleSheet(self._input_style())
        form.addWidget(self.purchase_spin, 5, 1)

        # Satış Fiyatı
        form.addWidget(QLabel("Birim Satış Fiyatı (₺):"), 6, 0)
        self.sale_spin = QDoubleSpinBox()
        self.sale_spin.setRange(0, 1000000)
        self.sale_spin.setDecimals(2)
        self.sale_spin.setValue(float(p.get('sale_price', 0) or 0))
        self.sale_spin.setStyleSheet(self._input_style())
        form.addWidget(self.sale_spin, 6, 1)

        # Notlar
        form.addWidget(QLabel("Notlar:"), 7, 0)
        self.notes_input = QLineEdit(p.get('notes', '') or '')
        self.notes_input.setStyleSheet(self._input_style())
        form.addWidget(self.notes_input, 7, 1)

        layout.addLayout(form)

        # Bilgi notu
        info = QLabel("ℹ️ Mevcut stok miktarını değiştirmek için üst bardaki 'Stok Girişi' veya 'Stok Çıkışı' işlemlerini kullanın.")
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {AppStyles.CYAN}; font-size: 9pt; padding: 8px; background-color: {AppStyles.BG_MEDIUM}; border-radius: 6px;")
        layout.addWidget(info)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"background-color: transparent; color: {AppStyles.TEXT_SECONDARY}; border: 1px solid {AppStyles.BORDER}; border-radius: 8px; padding: 8px 16px;")
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Kaydet")
        save_btn.clicked.connect(self.save)
        save_btn.setStyleSheet(f"background-color: {AppStyles.ORANGE}; color: white; border: none; border-radius: 8px; padding: 8px 22px; font-weight: bold;")
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        self.setLayout(layout)

    def save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Uyarı", "Ürün adı boş bırakılamaz!")
            return

        data = {
            'name': name,
            'category': self.cat_combo.currentText().strip(),
            'unit': self.unit_combo.currentText().strip(),
            'critical_stock': self.crit_spin.value(),
            'purchase_price': self.purchase_spin.value(),
            'sale_price': self.sale_spin.value(),
            'notes': self.notes_input.text().strip(),
        }

        success, msg = warehouse_service.update_product(self.product['id'], data)
        if success:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _input_style(self):
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 10pt;
        """


class StockInDialog(QDialog):
    """Depoya Malzeme Kabulü & Stok Girişi"""

    def __init__(self, user: User, preselected_id: int = None, parent=None):
        super().__init__(parent)
        self.user = user
        self.preselected_id = preselected_id
        self.setWindowTitle("📥 Depo Malzeme Kabulü & Stok Girişi")
        self.setMinimumWidth(540)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(25, 22, 25, 22)

        # Başlık ve açıklama
        h_box = QVBoxLayout()
        h_box.setSpacing(3)
        title = QLabel("📥 Depoya Malzeme Kabulü")
        title.setStyleSheet(f"font-size: 15pt; font-weight: bold; color: {AppStyles.GREEN};")
        sub_title = QLabel("Yeni gelen veya mevcut malzemelerin depo stok kabulünü gerçekleştirin.")
        sub_title.setStyleSheet("font-size: 8.5pt; color: #94a3b8;")
        h_box.addWidget(title)
        h_box.addWidget(sub_title)
        layout.addLayout(h_box)

        form = QGridLayout()
        form.setSpacing(10)
        form.setColumnStretch(1, 1)

        # 1. Ürün Adı / Seçimi
        form.addWidget(QLabel("Ürün Adı *:"), 0, 0)
        
        prod_container = QVBoxLayout()
        prod_container.setSpacing(4)

        self.prod_combo = QComboBox()
        self.prod_combo.setEditable(True)
        self.prod_combo.setInsertPolicy(QComboBox.NoInsert)
        self.prod_combo.setStyleSheet(self._input_style())
        if self.prod_combo.lineEdit():
            self.prod_combo.lineEdit().setPlaceholderText("Ürün seçin veya yeni ürün adı yazın...")

        self.products = warehouse_service.get_products()
        self.products_map = {p['id']: p for p in self.products}
        self.products_by_name = {p['name'].strip().lower(): p for p in self.products}

        self.prod_combo.addItem("🔍 Listeden Seçin veya Buraya Yeni Ürün Adı Yazın...", None)
        for p in self.products:
            self.prod_combo.addItem(f"{p['name']} ({p['product_code']}) - Stok: {p['stock_quantity']} {p['unit']}", p['id'])

        if self.preselected_id:
            idx = self.prod_combo.findData(self.preselected_id)
            if idx >= 0:
                self.prod_combo.setCurrentIndex(idx)

        prod_container.addWidget(self.prod_combo)

        # Dinamik Bilgi Etiketi
        self.lbl_prod_info = QLabel("💡 Listede olmayan yeni bir ürün ismi yazarsanız otomatik olarak depoya eklenecektir.")
        self.lbl_prod_info.setStyleSheet("color: #94a3b8; font-size: 8pt;")
        self.lbl_prod_info.setWordWrap(True)
        prod_container.addWidget(self.lbl_prod_info)

        form.addLayout(prod_container, 0, 1)

        # 2. Birim (Unit)
        form.addWidget(QLabel("Birim *:"), 1, 0)
        self.unit_combo = QComboBox()
        self.unit_combo.setEditable(True)
        self.unit_combo.addItems(["kg", "Adet", "Litre", "Çuval", "Paket", "Koli", "Teneke", "Gram", "Kasa", "Tepsi", "Bağ"])
        self.unit_combo.setCurrentText("kg")
        self.unit_combo.setStyleSheet(self._input_style())
        form.addWidget(self.unit_combo, 1, 1)

        # 3. Giriş Miktarı
        form.addWidget(QLabel("Kabul Miktarı *:"), 2, 0)
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0.01, 1000000.0)
        self.qty_spin.setDecimals(2)
        self.qty_spin.setValue(10.0)
        self.qty_spin.setStyleSheet(self._input_style())
        form.addWidget(self.qty_spin, 2, 1)

        # 4. Firma / Tedarikçi
        form.addWidget(QLabel("Firma / Tedarikçi:"), 3, 0)
        self.supplier_combo = QComboBox()
        self.supplier_combo.setEditable(True)
        self.supplier_combo.setStyleSheet(self._input_style())
        if self.supplier_combo.lineEdit():
            self.supplier_combo.lineEdit().setPlaceholderText("Malzemenin geldiği firmayı seçin veya yazın...")

        # Tedarikçileri veritabanından çek
        try:
            supp_rows = db.fetch_all("""
                SELECT id, title FROM Customers 
                WHERE is_supplier = TRUE AND is_active = TRUE 
                ORDER BY title ASC
            """)
            if not supp_rows:
                supp_rows = db.fetch_all("SELECT id, title FROM Customers WHERE is_active = TRUE ORDER BY title ASC")
            self.supplier_combo.addItem("", None)
            for s in supp_rows:
                if s.get('title'):
                    self.supplier_combo.addItem(s['title'], s['id'])
        except Exception as e:
            logger.error(f"Tedarikçi listesi yüklenemedi: {e}")
            self.supplier_combo.addItem("", None)

        form.addWidget(self.supplier_combo, 3, 1)

        # 5. İrsaliye / Fatura No
        form.addWidget(QLabel("İrsaliye / Fatura No:"), 4, 0)
        self.doc_input = QLineEdit()
        self.doc_input.setPlaceholderText("Örn: IRS-2026-0012 veya FAT-0045")
        self.doc_input.setStyleSheet(self._input_style())
        form.addWidget(self.doc_input, 4, 1)

        # 6. Açıklama / Not
        form.addWidget(QLabel("Açıklama / Not:"), 5, 0)
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Parti no, hammadde kabul notu vb...")
        self.desc_input.setStyleSheet(self._input_style())
        form.addWidget(self.desc_input, 5, 1)

        layout.addLayout(form)

        # Event connections
        self.prod_combo.currentIndexChanged.connect(self.on_product_selection_changed)
        if self.prod_combo.lineEdit():
            self.prod_combo.lineEdit().textChanged.connect(self.on_product_text_edited)

        if self.preselected_id:
            self.on_product_selection_changed(self.prod_combo.currentIndex())

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                color: white;
                border-color: #64748b;
            }}
        """)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("📥 Malzeme Kabulünü Onayla")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.save)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.GREEN};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 22px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        self.setLayout(layout)

    def on_product_selection_changed(self, idx: int):
        prod_id = self.prod_combo.currentData()
        if prod_id and prod_id in self.products_map:
            p = self.products_map[prod_id]
            unit = p.get('unit') or 'kg'
            idx_u = self.unit_combo.findText(unit, Qt.MatchFixedString)
            if idx_u >= 0:
                self.unit_combo.setCurrentIndex(idx_u)
            else:
                self.unit_combo.setCurrentText(unit)
            self.lbl_prod_info.setText(f"ℹ️ Mevcut Ürün: {p['name']} (Stok: {p['stock_quantity']} {unit}) ➔ Girilen miktar mevcut stoğa EKLENECEK.")
            self.lbl_prod_info.setStyleSheet("color: #38bdf8; font-size: 8.5pt; font-weight: bold;")
        else:
            self.on_product_text_edited(self.prod_combo.currentText())

    def on_product_text_edited(self, text: str):
        raw = text.strip()
        if not raw or raw.startswith("🔍 Listeden"):
            self.lbl_prod_info.setText("💡 Listede olmayan yeni bir ürün ismi yazarsanız otomatik olarak depoya eklenecektir.")
            self.lbl_prod_info.setStyleSheet("color: #94a3b8; font-size: 8pt;")
            return

        # İsim eşleşmesi var mı kontrol et
        low_txt = raw.lower()
        matched = None
        for name_low, p in self.products_by_name.items():
            if name_low == low_txt or raw.startswith(p['name']):
                matched = p
                break

        if matched:
            unit = matched.get('unit') or 'kg'
            idx_u = self.unit_combo.findText(unit, Qt.MatchFixedString)
            if idx_u >= 0:
                self.unit_combo.setCurrentIndex(idx_u)
            else:
                self.unit_combo.setCurrentText(unit)
            self.lbl_prod_info.setText(f"ℹ️ Mevcut Depo Ürünü: {matched['name']} (Stok: {matched['stock_quantity']} {unit}) ➔ Miktar stoğa EKLENECEK.")
            self.lbl_prod_info.setStyleSheet("color: #38bdf8; font-size: 8.5pt; font-weight: bold;")
        else:
            self.lbl_prod_info.setText(f"✨ Yeni Depo Ürünü: '{raw}' depoya ilk defa kaydedilecek ve stok girişi otomatik yapılacak.")
            self.lbl_prod_info.setStyleSheet("color: #10b981; font-size: 8.5pt; font-weight: bold;")

    def save(self):
        txt = self.prod_combo.currentText().strip()
        if not txt or txt.startswith("🔍 Listeden"):
            QMessageBox.warning(self, "Uyarı", "Lütfen bir ürün seçin veya yeni ürün adını yazın!")
            return

        # Ürünü ID veya ada göre eşle
        prod_id = self.prod_combo.currentData()
        prod_name = None
        if prod_id and prod_id in self.products_map:
            prod_name = self.products_map[prod_id]['name']
        else:
            # İsme göre kontrol
            low_txt = txt.lower()
            matched = None
            for name_low, p in self.products_by_name.items():
                if name_low == low_txt:
                    matched = p
                    break
            if matched:
                prod_id = matched['id']
                prod_name = matched['name']
            else:
                prod_id = None
                prod_name = txt

        qty = self.qty_spin.value()
        unit = self.unit_combo.currentText().strip() or "kg"
        supplier = self.supplier_combo.currentText().strip()
        doc_no = self.doc_input.text().strip()
        desc = self.desc_input.text().strip()
        user_id = getattr(self.user, 'id', None)

        success, msg, new_id = warehouse_service.add_stock_in(
            product_id=prod_id,
            quantity=qty,
            document_no=doc_no,
            description=desc,
            user_id=user_id,
            product_name=prod_name,
            unit=unit,
            supplier_name=supplier
        )
        if success:
            QMessageBox.information(self, "Malzeme Kabulü Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _input_style(self):
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 10pt;
        """


class StockOutDialog(QDialog):
    """Depodan Stok Çıkışı (Azaltma / Fire / Zayiat)"""

    def __init__(self, user: User, preselected_id: int = None, parent=None):
        super().__init__(parent)
        self.user = user
        self.preselected_id = preselected_id
        self.setWindowTitle("📤 Depodan Stok Çıkışı (Azaltma)")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("📤 Depodan Stok Çıkışı / Azaltma")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.RED};")
        layout.addWidget(title)

        form = QGridLayout()
        form.setSpacing(10)

        # Ürün Seçimi
        form.addWidget(QLabel("Ürün *:"), 0, 0)
        self.prod_combo = QComboBox()
        self.products = warehouse_service.get_products()
        for p in self.products:
            self.prod_combo.addItem(f"{p['name']} ({p['product_code']}) - Kalan: {p['stock_quantity']} {p['unit']}", p['id'])
        if self.preselected_id:
            idx = self.prod_combo.findData(self.preselected_id)
            if idx >= 0:
                self.prod_combo.setCurrentIndex(idx)
        self.prod_combo.setStyleSheet(self._input_style())
        form.addWidget(self.prod_combo, 0, 1)

        # Çıkış Miktarı
        form.addWidget(QLabel("Düşülecek Miktar *:"), 1, 0)
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0.01, 1000000)
        self.qty_spin.setValue(1)
        self.qty_spin.setStyleSheet(self._input_style())
        form.addWidget(self.qty_spin, 1, 1)

        # Çıkış Nedeni
        form.addWidget(QLabel("Çıkış Nedeni:"), 2, 0)
        self.reason_combo = QComboBox()
        self.reason_combo.addItems(["Fire / Zayiat", "Bozulma / SKT", "Üretim Sarfiyatı", "Tedarikçiye İade", "Düzeltme / Sayım Farkı"])
        self.reason_combo.setStyleSheet(self._input_style())
        form.addWidget(self.reason_combo, 2, 1)

        # Açıklama
        form.addWidget(QLabel("Açıklama / Detay:"), 3, 0)
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("İsteğe bağlı ek açıklama...")
        self.desc_input.setStyleSheet(self._input_style())
        form.addWidget(self.desc_input, 3, 1)

        layout.addLayout(form)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"background-color: transparent; color: {AppStyles.TEXT_SECONDARY}; border: 1px solid {AppStyles.BORDER}; border-radius: 8px; padding: 8px 16px;")
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("📤 Stoktan Düş")
        save_btn.clicked.connect(self.save)
        save_btn.setStyleSheet(f"background-color: {AppStyles.RED}; color: white; border: none; border-radius: 8px; padding: 8px 22px; font-weight: bold;")
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        self.setLayout(layout)

    def save(self):
        prod_id = self.prod_combo.currentData()
        if not prod_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir ürün seçin!")
            return

        qty = self.qty_spin.value()
        user_id = getattr(self.user, 'id', None)
        success, msg = warehouse_service.add_stock_out(
            product_id=prod_id,
            quantity=qty,
            reason=self.reason_combo.currentText(),
            description=self.desc_input.text().strip(),
            user_id=user_id
        )
        if success:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _input_style(self):
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 10pt;
        """


class DispatchDialog(QDialog):
    """Şubeye Ürün Sevkiyatı (Dağıtım)"""

    def __init__(self, user: User, preselected_id: int = None, parent=None):
        super().__init__(parent)
        self.user = user
        self.preselected_id = preselected_id
        self.setWindowTitle("🚚 Şubeye Ürün Sevk Et (Dağıtım)")
        self.setMinimumWidth(500)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("🚚 Şubeye Ürün Sevkiyatı (Dağıtım)")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.CYAN};")
        layout.addWidget(title)

        info_lbl = QLabel("✨ Depodan düşülen ürün, otomatik olarak hedef şubenin stoğuna eklenecektir.")
        info_lbl.setStyleSheet(f"color: {AppStyles.PRIMARY}; font-size: 9pt;")
        layout.addWidget(info_lbl)

        form = QGridLayout()
        form.setSpacing(10)

        # Hedef Şube
        form.addWidget(QLabel("Hedef Şube *:"), 0, 0)
        self.branch_combo = QComboBox()
        branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY name")
        for b in branches:
            self.branch_combo.addItem(f"🏢 {b['name']}", b['id'])
        self.branch_combo.setStyleSheet(self._input_style())
        form.addWidget(self.branch_combo, 0, 1)

        # Sevk Edilecek Ürün
        form.addWidget(QLabel("Depo Ürünü *:"), 1, 0)
        self.prod_combo = QComboBox()
        self.products = warehouse_service.get_products()
        for p in self.products:
            self.prod_combo.addItem(f"{p['name']} ({p['product_code']}) - Kalan: {p['stock_quantity']} {p['unit']}", p['id'])
        if self.preselected_id:
            idx = self.prod_combo.findData(self.preselected_id)
            if idx >= 0:
                self.prod_combo.setCurrentIndex(idx)
        self.prod_combo.setStyleSheet(self._input_style())
        form.addWidget(self.prod_combo, 1, 1)

        # Sevkiyat Miktarı
        form.addWidget(QLabel("Sevk Miktarı *:"), 2, 0)
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0.01, 1000000)
        self.qty_spin.setValue(5)
        self.qty_spin.setStyleSheet(self._input_style())
        form.addWidget(self.qty_spin, 2, 1)

        # Tarih
        form.addWidget(QLabel("Sevkiyat Tarihi:"), 3, 0)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setStyleSheet(self._input_style())
        form.addWidget(self.date_edit, 3, 1)

        # İrsaliye No
        form.addWidget(QLabel("İrsaliye / Fiş No:"), 4, 0)
        self.doc_input = QLineEdit()
        self.doc_input.setPlaceholderText("Örn: SEVK-2026-0045")
        self.doc_input.setStyleSheet(self._input_style())
        form.addWidget(self.doc_input, 4, 1)

        # Notlar / Şoför
        form.addWidget(QLabel("Açıklama / Not:"), 5, 0)
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Taşıyıcı, araç plakası veya özel talimat...")
        self.desc_input.setStyleSheet(self._input_style())
        form.addWidget(self.desc_input, 5, 1)

        layout.addLayout(form)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"background-color: transparent; color: {AppStyles.TEXT_SECONDARY}; border: 1px solid {AppStyles.BORDER}; border-radius: 8px; padding: 8px 16px;")
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("🚚 Sevkiyatı Başlat & Şubeye Gönder")
        save_btn.clicked.connect(self.save)
        save_btn.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN}); color: white; border: none; border-radius: 8px; padding: 8px 22px; font-weight: bold;")
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        self.setLayout(layout)

    def save(self):
        branch_id = self.branch_combo.currentData()
        prod_id = self.prod_combo.currentData()
        if not branch_id or not prod_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen şube ve ürün seçin!")
            return

        qty = self.qty_spin.value()
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        user_id = getattr(self.user, 'id', None)

        success, msg = warehouse_service.dispatch_to_branch(
            product_id=prod_id,
            target_branch_id=branch_id,
            quantity=qty,
            dispatch_date=date_str,
            document_no=self.doc_input.text().strip(),
            description=self.desc_input.text().strip(),
            user_id=user_id
        )

        if success:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _input_style(self):
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 10pt;
        """


class EditMovementDialog(QDialog):
    """Depo Hareketi (Sevkiyat, Malzeme Kabul veya Çıkış) Düzenleme Penceresi"""

    def __init__(self, user: User, movement: dict, parent=None):
        super().__init__(parent)
        self.user = user
        self.movement = movement
        self.movement_id = movement.get('id')
        self.m_type = movement.get('movement_type', 'DISPATCH')

        if self.m_type == 'DISPATCH':
            self.setWindowTitle("✏️ Sevkiyat Kaydını Düzenle")
        elif self.m_type == 'IN':
            self.setWindowTitle("✏️ Malzeme Kabul / Giriş Kaydını Düzenle")
        else:
            self.setWindowTitle("✏️ Depo Hareket Kaydını Düzenle")

        self.setMinimumWidth(520)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(25, 25, 25, 25)

        title_color = AppStyles.CYAN if self.m_type == 'DISPATCH' else (AppStyles.GREEN if self.m_type == 'IN' else AppStyles.RED)
        type_title = "🚚 Sevkiyat Kaydını Düzenle" if self.m_type == 'DISPATCH' else ("📥 Malzeme Kabul Kaydını Düzenle" if self.m_type == 'IN' else "📤 Stok Çıkışını Düzenle")

        title = QLabel(type_title)
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {title_color};")
        layout.addWidget(title)

        info_lbl = QLabel("ℹ️ Miktar veya hedef şube değişiklikleri ilgili tüm stoklara otomatik olarak yansıtılır.")
        info_lbl.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9pt;")
        layout.addWidget(info_lbl)

        form = QGridLayout()
        form.setSpacing(10)
        row = 0

        # Ürün Bilgisi (Salt Okunur)
        form.addWidget(QLabel("Ürün:"), row, 0)
        p_name = self.movement.get('product_name') or 'Ürün'
        p_code = self.movement.get('product_code') or ''
        prod_lbl = QLabel(f"<b>{p_name}</b>" + (f" ({p_code})" if p_code else ""))
        prod_lbl.setStyleSheet(f"color: {AppStyles.TEXT_PRIMARY}; font-size: 10.5pt; padding: 4px;")
        form.addWidget(prod_lbl, row, 1)
        row += 1

        # Hedef Şube (Sadece Sevkiyat ise)
        self.branch_combo = None
        if self.m_type == 'DISPATCH':
            form.addWidget(QLabel("Hedef Şube *:"), row, 0)
            self.branch_combo = QComboBox()
            branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY name")
            cur_b_id = self.movement.get('target_branch_id')
            selected_idx = 0
            for idx, b in enumerate(branches):
                self.branch_combo.addItem(f"🏢 {b['name']}", b['id'])
                if cur_b_id and b['id'] == cur_b_id:
                    selected_idx = idx
            self.branch_combo.setCurrentIndex(selected_idx)
            self.branch_combo.setStyleSheet(self._input_style())
            form.addWidget(self.branch_combo, row, 1)
            row += 1

        # Tedarikçi / Firma (Sadece Malzeme Kabul / Giriş ise)
        self.supplier_input = None
        if self.m_type == 'IN':
            form.addWidget(QLabel("Tedarikçi / Firma:"), row, 0)
            self.supplier_input = QLineEdit()
            self.supplier_input.setText(self.movement.get('supplier_name') or "")
            self.supplier_input.setPlaceholderText("Malzemenin geldiği firma adı")
            self.supplier_input.setStyleSheet(self._input_style())
            form.addWidget(self.supplier_input, row, 1)
            row += 1

        # Miktar
        form.addWidget(QLabel("Miktar *:"), row, 0)
        qty_box = QHBoxLayout()
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0.01, 1000000)
        self.qty_spin.setDecimals(2)
        self.qty_spin.setValue(float(self.movement.get('quantity') or 1.0))
        self.qty_spin.setStyleSheet(self._input_style())
        qty_box.addWidget(self.qty_spin, 2)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["Kg", "Adet", "Gram", "Litre", "Çuval", "Koli", "Paket", "Kutu", "Tepsi", "Bağ"])
        cur_unit = self.movement.get('unit') or "Adet"
        u_idx = self.unit_combo.findText(cur_unit, Qt.MatchFixedString)
        if u_idx >= 0:
            self.unit_combo.setCurrentIndex(u_idx)
        else:
            self.unit_combo.addItem(cur_unit)
            self.unit_combo.setCurrentText(cur_unit)
        self.unit_combo.setStyleSheet(self._input_style())
        qty_box.addWidget(self.unit_combo, 1)
        form.addLayout(qty_box, row, 1)
        row += 1

        # Tarih
        form.addWidget(QLabel("İşlem Tarihi *:"), row, 0)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        m_date_val = self.movement.get('movement_date')
        if m_date_val:
            try:
                if isinstance(m_date_val, str):
                    qd = QDate.fromString(m_date_val[:10], "yyyy-MM-dd")
                elif hasattr(m_date_val, 'year'):
                    qd = QDate(m_date_val.year, m_date_val.month, m_date_val.day)
                else:
                    qd = QDate.currentDate()
                self.date_edit.setDate(qd)
            except Exception:
                self.date_edit.setDate(QDate.currentDate())
        else:
            self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setStyleSheet(self._input_style())
        form.addWidget(self.date_edit, row, 1)
        row += 1

        # İrsaliye / Fiş No
        form.addWidget(QLabel("Belge / İrsaliye No:"), row, 0)
        self.doc_input = QLineEdit()
        self.doc_input.setText(self.movement.get('document_no') or "")
        self.doc_input.setPlaceholderText("İrsaliye no, fatura seri no vb.")
        self.doc_input.setStyleSheet(self._input_style())
        form.addWidget(self.doc_input, row, 1)
        row += 1

        # Açıklama
        form.addWidget(QLabel("Açıklama:"), row, 0)
        self.desc_input = QTextEdit()
        self.desc_input.setPlainText(self.movement.get('description') or "")
        self.desc_input.setMaximumHeight(70)
        self.desc_input.setStyleSheet(self._input_style())
        form.addWidget(self.desc_input, row, 1)

        layout.addLayout(form)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {AppStyles.BORDER}; }}
        """)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Değişiklikleri Kaydet")
        save_btn.clicked.connect(self.save_changes)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {title_color};
                color: {'#000000' if title_color == AppStyles.CYAN else 'white'};
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        self.setLayout(layout)

    def save_changes(self):
        new_qty = self.qty_spin.value()
        if new_qty <= 0:
            QMessageBox.warning(self, "Uyarı", "Miktar 0'dan büyük olmalıdır!")
            return

        data = {
            'quantity': new_qty,
            'unit': self.unit_combo.currentText().strip(),
            'movement_date': self.date_edit.date().toString("yyyy-MM-dd"),
            'document_no': self.doc_input.text().strip() or None,
            'description': self.desc_input.toPlainText().strip() or None,
        }

        if self.branch_combo:
            data['target_branch_id'] = self.branch_combo.currentData()

        if self.supplier_input:
            data['supplier_name'] = self.supplier_input.text().strip() or None

        success, msg = warehouse_service.update_stock_movement(self.movement_id, data, user_id=getattr(self.user, 'id', None))
        if success:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _input_style(self):
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 10pt;
        """


# ==================== ANA DEPO VE SEVKİYAT SAYFASI ====================

class WarehousePage(QWidget):
    """Merkez Depo & Sevkiyat Sayfası"""

    def __init__(self, user: User, central_window=None):
        super().__init__()
        self.user = user
        self.central_window = central_window

        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setObjectName("WarehousePage")
        self.setStyleSheet(f"#WarehousePage {{ background-color: {AppStyles.BG_DARK}; }}")

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        content = QWidget()
        content.setStyleSheet(f"background-color: {AppStyles.BG_DARK};")

        self.layout = QVBoxLayout()
        self.layout.setSpacing(18)
        self.layout.setContentsMargins(25, 20, 25, 20)

        # 1. Üst Bar (Başlık ve Hızlı İşlem Butonları)
        top_bar = self.create_top_bar()
        self.layout.addWidget(top_bar)

        # 2. İstatistik Kartları (KPI)
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(15)
        self.layout.addLayout(self.stats_layout)

        # 3. Sekmeli Alan (Tab 1: Depo Stokları, Tab 2: Şubelere Sevkiyat)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {AppStyles.BORDER};
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                padding: 15px;
            }}
            QTabBar::tab {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_SECONDARY};
                padding: 14px 36px;
                min-width: 400px; 
                font-weight: bold;
                font-size: 10.5pt;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 6px;
            }}
            QTabBar::tab:selected {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.PRIMARY};
                border-bottom: 2px solid {AppStyles.PRIMARY};
            }}
        """)

        # Tab 1
        tab1 = self.create_products_tab()
        self.tabs.addTab(tab1, "🏬 Depo Ürün & Stok Durumu")

        # Tab 2
        tab2 = self.create_dispatches_tab()
        self.tabs.addTab(tab2, "🚚 Şubelere Verilen Ürünler (Sevkiyat Takibi)")

        self.layout.addWidget(self.tabs)

        content.setLayout(self.layout)
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    # ==================== ÜST BAR ====================

    def create_top_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        left = QVBoxLayout()
        left.setSpacing(3)
        title = QLabel("🏬 Merkez Depo & Sevkiyat Yönetimi")
        title.setStyleSheet(f"font-size: 20pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)

        subtitle = QLabel("Toptan un, şeker, ambalaj ve fazla stok deposu • Şubelere ve imalathaneye toplu malzeme transferi")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        layout.addLayout(left)

        layout.addStretch()

        # Hızlı Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        # 1. Yeni Ürün
        add_prod_btn = QPushButton("➕ Yeni Ürün")
        add_prod_btn.setCursor(Qt.PointingHandCursor)
        add_prod_btn.clicked.connect(self.open_add_product)
        add_prod_btn.setStyleSheet(self._btn_style(AppStyles.PRIMARY))
        btn_layout.addWidget(add_prod_btn)

        # 2. Stok Girişi
        stock_in_btn = QPushButton("📥 Stok Girişi")
        stock_in_btn.setCursor(Qt.PointingHandCursor)
        stock_in_btn.clicked.connect(self.open_stock_in)
        stock_in_btn.setStyleSheet(self._btn_style(AppStyles.GREEN))
        btn_layout.addWidget(stock_in_btn)

        # 3. Stok Çıkışı
        stock_out_btn = QPushButton("📤 Stok Çıkışı")
        stock_out_btn.setCursor(Qt.PointingHandCursor)
        stock_out_btn.clicked.connect(self.open_stock_out)
        stock_out_btn.setStyleSheet(self._btn_style(AppStyles.RED))
        btn_layout.addWidget(stock_out_btn)

        # 4. Şubeye Sevk Et
        dispatch_btn = QPushButton("🚚 Şubeye Sevk Et")
        dispatch_btn.setCursor(Qt.PointingHandCursor)
        dispatch_btn.clicked.connect(self.open_dispatch)
        dispatch_btn.setStyleSheet(self._btn_style(AppStyles.CYAN, text_color="#000000"))
        btn_layout.addWidget(dispatch_btn)

        layout.addLayout(btn_layout)
        bar.setLayout(layout)
        return bar

    # ==================== KPI KARTLARI ====================

    def update_stats_cards(self):
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        stats = warehouse_service.get_warehouse_stats()
        tot_prods = stats.get('total_products', 0)
        tot_stock = stats.get('total_stock', 0.0)
        crit_count = stats.get('critical_count', 0)
        today_dispatch = stats.get('today_dispatch_qty', 0.0)

        cards = [
            ("📦", "Depo Ürün Çeşidi", str(tot_prods), AppStyles.PRIMARY, "Aktif hammadde & ürün"),
            ("📊", "Toplam Depo Stoğu", f"{tot_stock:,.0f} Kalem", AppStyles.GREEN, "Mevcut fiziksel stok"),
            ("⚠️", "Kritik Stok Uyarısı", f"{crit_count} Ürün", AppStyles.RED if crit_count > 0 else AppStyles.GREEN, "Eşik değerin altında"),
            ("🚚", "Bugün Şubelere Sevk", f"{today_dispatch:,.0f} Kalem", AppStyles.CYAN, "Günlük şube dağıtımı"),
        ]

        for icon, title, val, color, sub in cards:
            card = self.create_kpi_card(icon, title, val, color, sub)
            self.stats_layout.addWidget(card)

    def create_kpi_card(self, icon: str, title: str, val: str, color: str, sub: str) -> QFrame:
        card = QFrame()
        card.setMinimumHeight(105)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                border-left: 4px solid {color};
                border-top: 1px solid {AppStyles.BORDER};
                border-right: 1px solid {AppStyles.BORDER};
                border-bottom: 1px solid {AppStyles.BORDER};
                padding: 12px 16px;
            }}
            QFrame QLabel {{ background: transparent; border: none; }}
        """)
        lay = QVBoxLayout()
        lay.setSpacing(3)

        top = QHBoxLayout()
        top.addWidget(QLabel(f"{icon} {title}"))
        top.itemAt(0).widget().setStyleSheet(f"font-size: 9.5pt; font-weight: bold; color: {AppStyles.TEXT_SECONDARY};")
        top.addStretch()
        lay.addLayout(top)

        val_lbl = QLabel(val)
        val_lbl.setStyleSheet(f"font-size: 15pt; font-weight: bold; color: {color};")
        lay.addWidget(val_lbl)

        sub_lbl = QLabel(sub)
        sub_lbl.setStyleSheet(f"font-size: 8pt; color: {AppStyles.TEXT_MUTED};")
        lay.addWidget(sub_lbl)

        card.setLayout(lay)
        return card

    # ==================== TAB 1: DEPO ÜRÜNLERİ VE STOKLARI ====================

    def create_products_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(14)

        # Filtre Çubuğu
        f_row = QHBoxLayout()
        f_row.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Ürün adı veya kodu ara...")
        self.search_input.setMinimumHeight(38)
        self.search_input.textChanged.connect(self.load_products)
        self.search_input.setStyleSheet(self._input_style())
        f_row.addWidget(self.search_input, 3)

        self.cat_filter = QComboBox()
        self.cat_filter.addItem("Tümü (Kategoriler)", "Tümü")
        self.cat_filter.addItems(["Hammadde", "Ambalaj", "Katkı Maddesi", "Mamül", "Yarı Mamül"])
        self.cat_filter.setMinimumHeight(38)
        self.cat_filter.currentIndexChanged.connect(self.load_products)
        self.cat_filter.setStyleSheet(self._input_style())
        f_row.addWidget(self.cat_filter, 2)

        self.crit_filter_btn = QPushButton("⚠️ Yalnızca Kritik Stoklar")
        self.crit_filter_btn.setCheckable(True)
        self.crit_filter_btn.setCursor(Qt.PointingHandCursor)
        self.crit_filter_btn.setMinimumHeight(38)
        self.crit_filter_btn.toggled.connect(self.load_products)
        self.crit_filter_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 0 14px;
                font-weight: 600;
            }}
            QPushButton:checked {{
                background-color: {AppStyles.RED}25;
                color: {AppStyles.RED};
                border-color: {AppStyles.RED};
            }}
        """)
        f_row.addWidget(self.crit_filter_btn, 2)

        refresh_btn = QPushButton("🔄")
        refresh_btn.setToolTip("Yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setFixedSize(38, 38)
        refresh_btn.setStyleSheet(self._btn_style(AppStyles.BG_DARK))
        f_row.addWidget(refresh_btn)

        layout.addLayout(f_row)

        # Tablo
        self.prod_table = QTableWidget()
        self.prod_table.setColumnCount(9)
        self.prod_table.setHorizontalHeaderLabels([
            'Kod', 'Ürün Adı', 'Kategori', 'Birim', 'Alış Fiyatı',
            'Mevcut Stok', 'Kritik Eşik', 'Durum', 'İşlemler'
        ])
        self.prod_table.setAlternatingRowColors(True)
        self.prod_table.verticalHeader().setVisible(False)

        header = self.prod_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        # ✅ İşlemler sütunu — 2 buton rahat sığsın
        header.setSectionResizeMode(8, QHeaderView.Fixed)
        self.prod_table.setColumnWidth(8, 105)
        # ✅ Satır yüksekliği butonlar için yeterli olsun
        self.prod_table.verticalHeader().setDefaultSectionSize(48)

        self.prod_table.setStyleSheet(self._table_style())
        layout.addWidget(self.prod_table)

        w.setLayout(layout)
        return w

    # ==================== TAB 2: ŞUBELERE VERİLEN ÜRÜNLER ====================

    def create_dispatches_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(14)

        # Filtreler
        f_row = QHBoxLayout()
        f_row.setSpacing(10)

        f_row.addWidget(QLabel("Şube:"))
        self.dispatch_branch_combo = QComboBox()
        self.dispatch_branch_combo.addItem("Tüm Şubeler", None)
        branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY name")
        for b in branches:
            self.dispatch_branch_combo.addItem(f"🏢 {b['name']}", b['id'])
        self.dispatch_branch_combo.setMinimumHeight(38)
        self.dispatch_branch_combo.currentIndexChanged.connect(self.load_dispatches)
        self.dispatch_branch_combo.setStyleSheet(self._input_style())
        f_row.addWidget(self.dispatch_branch_combo, 2)

        f_row.addWidget(QLabel("Başlangıç:"))
        self.disp_start = QDateEdit()
        self.disp_start.setCalendarPopup(True)
        self.disp_start.setDate(QDate.currentDate().addDays(-30))
        self.disp_start.setDisplayFormat("dd.MM.yyyy")
        self.disp_start.setMinimumHeight(38)
        self.disp_start.dateChanged.connect(self.load_dispatches)
        self.disp_start.setStyleSheet(self._input_style())
        f_row.addWidget(self.disp_start, 2)

        f_row.addWidget(QLabel("Bitiş:"))
        self.disp_end = QDateEdit()
        self.disp_end.setCalendarPopup(True)
        self.disp_end.setDate(QDate.currentDate())
        self.disp_end.setDisplayFormat("dd.MM.yyyy")
        self.disp_end.setMinimumHeight(38)
        self.disp_end.dateChanged.connect(self.load_dispatches)
        self.disp_end.setStyleSheet(self._input_style())
        f_row.addWidget(self.disp_end, 2)

        export_disp_btn = QPushButton("📤 Excel'e Aktar")
        export_disp_btn.setCursor(Qt.PointingHandCursor)
        export_disp_btn.clicked.connect(self.export_dispatches_to_excel)
        export_disp_btn.setMinimumHeight(38)
        export_disp_btn.setStyleSheet(f"background-color: {AppStyles.GREEN}; color: white; border: none; border-radius: 8px; font-weight: bold; padding: 0 16px;")
        f_row.addWidget(export_disp_btn)

        layout.addLayout(f_row)

        # Tablo
        self.disp_table = QTableWidget()
        self.disp_table.setColumnCount(9)
        self.disp_table.setHorizontalHeaderLabels([
            'Tarih', 'Hedef Şube', 'Ürün Kodu', 'Ürün Adı', 'Sevk Edilen Miktar',
            'İrsaliye / Fiş No', 'Açıklama / Not', 'Sevk Eden', 'İşlemler'
        ])
        self.disp_table.setAlternatingRowColors(True)
        self.disp_table.verticalHeader().setVisible(False)
        self.disp_table.verticalHeader().setDefaultSectionSize(44)
        header = self.disp_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.Fixed)
        self.disp_table.setColumnWidth(8, 105)
        self.disp_table.setStyleSheet(self._table_style())
        layout.addWidget(self.disp_table)

        w.setLayout(layout)
        return w

    # ==================== VERİ YÜKLEME ====================

    def load_data(self):
        self.update_stats_cards()
        self.load_products()
        self.load_dispatches()

    def load_products(self):
        search = self.search_input.text().strip()
        cat = self.cat_filter.currentData() or self.cat_filter.currentText()
        low_only = self.crit_filter_btn.isChecked()

        products = warehouse_service.get_products(search=search, category=cat, low_stock_only=low_only)
        self.prod_table.setRowCount(len(products))

        for row_idx, p in enumerate(products):
            p_id = p['id']
            code = p.get('product_code', '-')
            name = p.get('name', '-')
            cat_name = p.get('category', '-')
            unit = p.get('unit', 'Adet')
            p_price = float(p.get('purchase_price', 0))
            stock = float(p.get('stock_quantity', 0))
            crit = float(p.get('critical_stock', 10))

            # 0. Kod
            self.prod_table.setItem(row_idx, 0, QTableWidgetItem(code))
            # 1. Ad
            item_name = QTableWidgetItem(name)
            item_name.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.prod_table.setItem(row_idx, 1, item_name)
            # 2. Kategori
            self.prod_table.setItem(row_idx, 2, QTableWidgetItem(cat_name))
            # 3. Birim
            self.prod_table.setItem(row_idx, 3, QTableWidgetItem(unit))
            # 4. Alış Fiyatı
            self.prod_table.setItem(row_idx, 4, QTableWidgetItem(f"{p_price:,.2f} ₺"))

            # 5. Mevcut Stok
            stock_item = QTableWidgetItem(f"{stock:,.1f} {unit}")
            stock_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            if stock <= 0:
                stock_item.setForeground(QColor(AppStyles.RED))
            elif stock <= crit:
                stock_item.setForeground(QColor(AppStyles.ORANGE))
            else:
                stock_item.setForeground(QColor(AppStyles.GREEN))
            self.prod_table.setItem(row_idx, 5, stock_item)

            # 6. Kritik Eşik
            self.prod_table.setItem(row_idx, 6, QTableWidgetItem(f"{crit:,.0f} {unit}"))

            # 7. Durum Rozeti
            if stock <= 0:
                status_text = "🔴 Tükendi"
                status_color = AppStyles.RED
            elif stock <= crit:
                status_text = "⚠️ Kritik Stok"
                status_color = AppStyles.ORANGE
            else:
                status_text = "🟢 Yeterli"
                status_color = AppStyles.GREEN

            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            status_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.prod_table.setItem(row_idx, 7, status_item)

            # 8. Hızlı İşlem Butonları (Düzenle, Sil) — YATAY
            action_widget = QWidget()
            action_widget.setStyleSheet("background: transparent;")

            # ✅ Layout'u doğrudan widget'a bağla (parent ile) — dikey konumlanmayı önler
            a_lay = QHBoxLayout(action_widget)
            a_lay.setContentsMargins(2, 2, 2, 2)
            a_lay.setSpacing(4)
            a_lay.setAlignment(Qt.AlignCenter)

            # Düzenle
            edit_btn = QPushButton("✏️")
            edit_btn.setToolTip("Ürünü Düzenle")
            edit_btn.setFixedSize(36, 30)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setStyleSheet(self._mini_btn_style(AppStyles.ORANGE))
            edit_btn.clicked.connect(lambda checked, pid=p_id: self.open_edit_product(pid))
            a_lay.addWidget(edit_btn)

            # Sil
            del_btn = QPushButton("🗑️")
            del_btn.setToolTip("Ürünü Sil")
            del_btn.setFixedSize(36, 30)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet(self._mini_btn_style(AppStyles.RED))
            del_btn.clicked.connect(lambda checked, pid=p_id: self.delete_product(pid))
            a_lay.addWidget(del_btn)

            self.prod_table.setCellWidget(row_idx, 8, action_widget)

    def load_dispatches(self):
        b_id = self.dispatch_branch_combo.currentData()
        start = self.disp_start.date().toString("yyyy-MM-dd")
        end = self.disp_end.date().toString("yyyy-MM-dd")

        dispatches = warehouse_service.get_branch_dispatches(branch_id=b_id, start_date=start, end_date=end)
        self.disp_table.setRowCount(len(dispatches))

        for row_idx, d in enumerate(dispatches):
            m_date = str(d.get('movement_date', ''))
            b_name = d.get('branch_name', '-')
            p_code = d.get('product_code', '-')
            p_name = d.get('product_name', '-')
            qty = float(d.get('quantity', 0))
            unit = d.get('unit', '')
            doc = d.get('document_no', '-')
            desc = d.get('description', '-')
            user = d.get('created_by_name', '-')

            self.disp_table.setItem(row_idx, 0, QTableWidgetItem(m_date))

            b_item = QTableWidgetItem(f"🏢 {b_name}")
            b_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.disp_table.setItem(row_idx, 1, b_item)

            self.disp_table.setItem(row_idx, 2, QTableWidgetItem(p_code))

            p_item = QTableWidgetItem(p_name)
            p_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.disp_table.setItem(row_idx, 3, p_item)

            qty_item = QTableWidgetItem(f"{qty:,.1f} {unit}")
            qty_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            qty_item.setForeground(QColor(AppStyles.CYAN))
            self.disp_table.setItem(row_idx, 4, qty_item)

            self.disp_table.setItem(row_idx, 5, QTableWidgetItem(doc))
            self.disp_table.setItem(row_idx, 6, QTableWidgetItem(desc))
            self.disp_table.setItem(row_idx, 7, QTableWidgetItem(user))

            # 8. Hızlı İşlem Butonları (Düzenle & Sil)
            action_widget = QWidget()
            action_widget.setStyleSheet("background: transparent;")
            a_lay = QHBoxLayout(action_widget)
            a_lay.setContentsMargins(2, 2, 2, 2)
            a_lay.setSpacing(4)
            a_lay.setAlignment(Qt.AlignCenter)

            edit_btn = QPushButton("✏️")
            edit_btn.setToolTip("Sevkiyatı Düzenle")
            edit_btn.setFixedSize(36, 30)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setStyleSheet(self._mini_btn_style(AppStyles.ORANGE))
            edit_btn.clicked.connect(lambda checked, m=d: self.edit_dispatch(m))
            a_lay.addWidget(edit_btn)

            del_btn = QPushButton("🗑️")
            del_btn.setToolTip("Sevkiyatı Sil & Stoğu İade Et")
            del_btn.setFixedSize(36, 30)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet(self._mini_btn_style(AppStyles.RED))
            del_btn.clicked.connect(lambda checked, m=d: self.delete_dispatch(m))
            a_lay.addWidget(del_btn)

            self.disp_table.setCellWidget(row_idx, 8, action_widget)

    def edit_dispatch(self, movement: dict):
        m_id = movement.get('id')
        full_mov = warehouse_service.get_stock_movement(m_id) or movement
        dlg = EditMovementDialog(self.user, full_mov, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def delete_dispatch(self, movement: dict):
        m_id = movement.get('id')
        prod_name = movement.get('product_name') or 'Ürün'
        qty = float(movement.get('quantity', 0))
        unit = movement.get('unit', '')
        branch_name = movement.get('branch_name', 'Şube')

        reply = QMessageBox.question(
            self,
            "Sevkiyatı Sil & Geri Al",
            f"<b>{prod_name}</b> ürününe ait bu sevkiyatı silmek istediğinize emin misiniz?<br><br>"
            f"<b>Miktar:</b> {qty:,.2f} {unit}<br>"
            f"<b>Hedef Şube:</b> {branch_name}<br><br>"
            f"⚠️ <i>İşlem onaylandığında sevk edilen miktar Merkez Depo stoğuna geri eklenecek "
            f"ve hedef şubenin stoğundan otomatik olarak düşülecektir.</i>",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = warehouse_service.delete_stock_movement(m_id, user_id=getattr(self.user, 'id', None))
            if success:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_data()
            else:
                QMessageBox.critical(self, "Hata", msg)

    # ==================== DİALOG AÇMA METODLARI ====================

    def open_add_product(self):
        dlg = AddWarehouseProductDialog(self.user, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_edit_product(self, product_id: int):
        """Mevcut ürünü düzenle"""
        product = warehouse_service.get_product(product_id)
        if not product:
            QMessageBox.warning(self, "Uyarı", "Ürün bulunamadı!")
            return

        dlg = EditWarehouseProductDialog(self.user, product, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_stock_in(self, preselected_id: int = None):
        dlg = StockInDialog(self.user, preselected_id, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_stock_out(self, preselected_id: int = None):
        dlg = StockOutDialog(self.user, preselected_id, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_dispatch(self, preselected_id: int = None):
        dlg = DispatchDialog(self.user, preselected_id, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def delete_product(self, product_id: int):
        reply = QMessageBox.question(
            self, "Silme Onayı", "Bu ürünü depodan silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = warehouse_service.delete_product(product_id)
            if success:
                self.load_data()
            else:
                QMessageBox.critical(self, "Hata", msg)

    def export_dispatches_to_excel(self):
        b_id = self.dispatch_branch_combo.currentData()
        start = self.disp_start.date().toString("yyyy-MM-dd")
        end = self.disp_end.date().toString("yyyy-MM-dd")
        dispatches = warehouse_service.get_branch_dispatches(b_id, start, end)

        if not dispatches:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak sevkiyat kaydı bulunamadı.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel Olarak Kaydet", f"Sube_Sevkiyatlari_{start}_{end}.xlsx", "Excel Dosyaları (*.xlsx)"
        )
        if not file_path:
            return

        try:
            data = []
            for d in dispatches:
                data.append({
                    "Tarih": str(d.get('movement_date')),
                    "Hedef Şube": d.get('branch_name'),
                    "Ürün Kodu": d.get('product_code'),
                    "Ürün Adı": d.get('product_name'),
                    "Sevk Edilen Miktar": float(d.get('quantity', 0)),
                    "Birim": d.get('unit'),
                    "İrsaliye / Fiş No": d.get('document_no'),
                    "Açıklama": d.get('description'),
                    "Sevk Eden": d.get('created_by_name')
                })
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False, engine='openpyxl')
            QMessageBox.information(self, "Başarılı", f"Sevkiyat raporu başarıyla kaydedildi:\n{file_path}")
        except Exception as e:
            logger.error(f"Excel aktarma hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Excel'e aktarılırken hata oluştu:\n{str(e)}")

    # ==================== STİLLER ====================

    def _btn_style(self, color: str, text_color: str = "white") -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: {text_color};
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """

    def _mini_btn_style(self, color: str, text_color: str = "white") -> str:
        return f"""
            QPushButton {{
                background-color: {color}25;
                color: {color};
                border: 1px solid {color}50;
                border-radius: 7px;
                font-size: 14pt;
                font-weight: normal;
                padding: 0px;
                text-align: center;
                min-width: 0px;
                min-height: 0px;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: {text_color};
            }}
        """

    def _input_style(self) -> str:
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 10pt;
        """

    def _table_style(self) -> str:
        return f"""
            QTableWidget {{
                background-color: transparent;
                border: none;
                gridline-color: {AppStyles.BORDER};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{
                padding: 10px;
                border: none;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARKEST};
                color: {AppStyles.TEXT_SECONDARY};
                padding: 10px;
                border: none;
                border-bottom: 1px solid {AppStyles.BORDER};
                font-weight: 600;
            }}
        """