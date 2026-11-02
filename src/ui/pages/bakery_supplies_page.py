# src/ui/pages/bakery_supplies_page.py
"""
İmalathane Tedarik & Malzeme Kabul Takip Sayfası
Tedarikçilerden alınan Manav, Şarküteri, Hammadde, Un vb. ürünlerin takibi.
Tek satırda çoklu kalem girişi, açılır pencerede detay görüntüleme ve fatura aktarım desteği.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox, QMessageBox,
    QDialog, QDialogButtonBox, QDoubleSpinBox, QTextEdit, QHeaderView,
    QSizePolicy, QDateEdit, QCompleter
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont
from datetime import datetime

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles


# ══════════════════════════════════════════════════════════════
# 1. AÇILIR DETAY PENCERESİ (SupplyDetailDialog)
# ══════════════════════════════════════════════════════════════

class SupplyDetailDialog(QDialog):
    """Tedarik Kabul Detaylarını ve Kalemlerini Gösteren Açılır Pencere"""

    def __init__(self, supply_id: int, user: User = None, branch_id: int = None, parent=None):
        super().__init__(parent)
        self.supply_id = supply_id
        self.user = user
        self.branch_id = branch_id
        self.supply_data = None
        self.items_data = []

        self.setWindowTitle("📦 Tedarik & Malzeme Kabul Detayı")
        self.resize(1000, 620)
        self.setMinimumWidth(880)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; }}
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                gridline-color: #242430;
                font-size: 10pt;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
                font-weight: bold;
                font-size: 9.5pt;
                padding: 8px 6px;
                border: none;
                border-right: 1px solid {AppStyles.BG_MEDIUM};
            }}
            QTableWidget::item:selected {{
                background-color: rgba(217, 119, 6, 0.25);
            }}
        """)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 24, 20)

        # 1. Başlık & Tedarikçi Kartı
        header_card = QFrame()
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-left: 5px solid {AppStyles.PRIMARY};
                border-radius: 8px;
                padding: 12px 16px;
            }}
        """)
        h_lay = QHBoxLayout(header_card)
        h_lay.setContentsMargins(0, 0, 0, 0)

        v_info = QVBoxLayout()
        v_info.setSpacing(4)
        self.lbl_supplier = QLabel("🏢 Tedarikçi")
        self.lbl_supplier.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        v_info.addWidget(self.lbl_supplier)

        self.lbl_info = QLabel("📅 Tarih: -   |   📄 Fatura No: -   |   👤 Teslim Alan / Not: -")
        self.lbl_info.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        v_info.addWidget(self.lbl_info)
        h_lay.addLayout(v_info, 3)

        v_tot = QVBoxLayout()
        v_tot.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        t_sub = QLabel("Genel Toplam")
        t_sub.setStyleSheet("color: #94a3b8; font-size: 8.5pt;")
        self.lbl_total = QLabel("0.00 ₺")
        self.lbl_total.setStyleSheet("font-size: 16pt; font-weight: bold; color: #10b981;")
        v_tot.addWidget(t_sub)
        v_tot.addWidget(self.lbl_total)
        h_lay.addLayout(v_tot, 1)

        layout.addWidget(header_card)

        # 2. Kalemler Tablosu
        sec_title = QLabel("📋 Sevkiyatta Bulunan Ürün ve Malzeme Kalemleri:")
        sec_title.setStyleSheet("font-size: 10.5pt; font-weight: bold; color: #e2e8f0; margin-top: 4px;")
        layout.addWidget(sec_title)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "#", "Malzeme / Ürün Adı", "Kategori", "Miktar", "Birim", "Birim Fiyat", "Toplam Tutar"
        ])
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 45)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 145)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 110)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 90)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 125)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(6, 150)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # 3. Alt Butonlar ve Özet
        btn_box = QHBoxLayout()
        self.lbl_summary = QLabel("Toplam 0 Kalem")
        self.lbl_summary.setStyleSheet("font-size: 10pt; font-weight: 500; color: #cbd5e1;")
        btn_box.addWidget(self.lbl_summary)
        btn_box.addStretch()

        btn_edit = QPushButton("✏️ Bu Kaydı Düzenle")
        btn_edit.setStyleSheet(AppStyles.btn_primary())
        btn_edit.clicked.connect(self.edit_record)
        btn_box.addWidget(btn_edit)

        btn_del = QPushButton("🗑️ Bu Kaydı Sil")
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 9.5pt;
                border: none;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        btn_del.clicked.connect(self.delete_record)
        btn_box.addWidget(btn_del)

        btn_close = QPushButton("Kapat")
        btn_close.setStyleSheet(AppStyles.btn_secondary())
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)

    def load_data(self):
        try:
            self.supply_data = db.fetch_one("SELECT * FROM bakery_supplies WHERE id = %s", (self.supply_id,))
            if not self.supply_data:
                QMessageBox.warning(self, "Hata", "Tedarik kaydı bulunamadı.")
                self.reject()
                return

            sup_name = self.supply_data.get('supplier_name') or "Tedarikçi Belirtilmemiş"
            self.lbl_supplier.setText(f"🏢 {sup_name}")

            dt = self.supply_data.get('supply_date')
            dt_str = str(dt)[:10] if dt else "-"
            inv_no = self.supply_data.get('invoice_no') or "-"
            rec_by = self.supply_data.get('received_by') or self.supply_data.get('notes') or "-"
            self.lbl_info.setText(f"📅 Tarih: {dt_str}   |   📄 Fatura No: {inv_no}   |   👤 Not / Teslim: {rec_by}")

            tot = float(self.supply_data.get('total_price') or 0.0)
            self.lbl_total.setText(f"{tot:,.2f} ₺")

            items = db.fetch_all("""
                SELECT * FROM bakery_supply_items
                WHERE supply_id = %s
                ORDER BY id ASC
            """, (self.supply_id,))

            # Geriye dönük uyumluluk: alt tabloda henüz kayıt yoksa ana tablodaki veriyi tek kalem göster
            if not items and self.supply_data.get('item_name'):
                items = [{
                    'item_name': self.supply_data.get('item_name'),
                    'category': self.supply_data.get('category'),
                    'quantity': self.supply_data.get('quantity'),
                    'unit': self.supply_data.get('unit'),
                    'unit_price': self.supply_data.get('unit_price'),
                    'total_price': self.supply_data.get('total_price'),
                }]

            self.items_data = items or []
            self.populate_items()
        except Exception as e:
            logger.error(f"Error loading supply details: {e}")

    def populate_items(self):
        self.table.setRowCount(len(self.items_data))
        for row_idx, itm in enumerate(self.items_data):
            # 0. Sıra
            seq_item = QTableWidgetItem(str(row_idx + 1))
            seq_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, seq_item)

            # 1. Ürün Adı
            name_item = QTableWidgetItem(itm.get('item_name') or "-")
            name_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row_idx, 1, name_item)

            # 2. Kategori Pill
            cat_str = itm.get('category') or "Hammadde"
            cat_item = QTableWidgetItem(f"🏷️ {cat_str}")
            cat_item.setTextAlignment(Qt.AlignCenter)
            c_low = cat_str.lower()
            if "manav" in c_low:
                cat_item.setForeground(QColor("#34d399"))
            elif "şarküteri" in c_low:
                cat_item.setForeground(QColor("#fbbf24"))
            elif any(w in c_low for w in ["un", "maya", "hammadde"]):
                cat_item.setForeground(QColor("#818cf8"))
            else:
                cat_item.setForeground(QColor("#94a3b8"))
            self.table.setItem(row_idx, 2, cat_item)

            # 3. Miktar
            qty = float(itm.get('quantity') or 0.0)
            q_item = QTableWidgetItem(f"{qty:,.4f}")
            q_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row_idx, 3, q_item)

            # 4. Birim
            u_item = QTableWidgetItem(itm.get('unit') or "kg")
            u_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 4, u_item)

            # 5. Birim Fiyat
            price = float(itm.get('unit_price') or 0.0)
            p_item = QTableWidgetItem(f"{price:,.2f} ₺")
            p_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row_idx, 5, p_item)

            # 6. Toplam Tutar
            tot = float(itm.get('total_price') or (qty * price))
            t_item = QTableWidgetItem(f"{tot:,.2f} ₺")
            t_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            t_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            t_item.setForeground(QColor("#10b981"))
            self.table.setItem(row_idx, 6, t_item)

        self.lbl_summary.setText(f"Toplam {len(self.items_data)} Kalem Malzeme Teslim Alındı")

    def edit_record(self):
        dlg = SupplyEntryDialog(user=self.user, branch_id=self.branch_id, parent=self, item_id=self.supply_id)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()
            if self.parent() and hasattr(self.parent(), 'load_data'):
                self.parent().load_data()

    def delete_record(self):
        reply = QMessageBox.question(
            self, "Silme Onayı",
            "Bu tedarik kaydını ve altındaki tüm ürün kalemlerini silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                with db.transaction():
                    db.execute_query("DELETE FROM bakery_supply_items WHERE supply_id = %s", (self.supply_id,))
                    db.execute_query("DELETE FROM bakery_supplies WHERE id = %s", (self.supply_id,))
                if self.parent() and hasattr(self.parent(), 'load_data'):
                    self.parent().load_data()
                self.accept()
            except Exception as e:
                logger.error(f"Error deleting supply record: {e}")
                QMessageBox.critical(self, "Hata", f"Silinirken hata oluştu: {e}")


# ══════════════════════════════════════════════════════════════
# 2. ÇOKLU KALEM GİRİŞ / DÜZENLEME PENCERESİ (SupplyEntryDialog)
# ══════════════════════════════════════════════════════════════

class SupplyEntryDialog(QDialog):
    """Yeni Tedarik Malzemesi Girişi veya Düzenleme Penceresi (Sınırsız Çoklu Kalem Destekli)"""

    def __init__(self, user: User = None, branch_id: int = None, parent=None, item_id: int = None):
        super().__init__(parent)
        self.user = user
        self.branch_id = branch_id
        self.item_id = item_id

        self.setWindowTitle("➕ Yeni Tedarik Girişi" if not item_id else "✏️ Tedarik Kaydını Düzenle")
        self.resize(1260, 750)
        self.setMinimumWidth(1100)
        self.setMinimumHeight(620)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {AppStyles.TEXT_PRIMARY};
                font-size: 9.5pt;
                font-weight: 500;
            }}
            /* Üst form alanları */
            QLineEdit, QDateEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10pt;
            }}
            QLineEdit:focus, QDateEdit:focus {{
                border-color: {AppStyles.PRIMARY};
            }}

            /* Tablo Genel */
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                gridline-color: #242430;
                font-size: 10pt;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
                font-weight: bold;
                font-size: 9.5pt;
                padding: 8px 6px;
                border: none;
                border-right: 1px solid {AppStyles.BG_MEDIUM};
            }}

            /* Tablo Hücrelerindeki Girdiler (Kutucuklar) */
            QTableWidget QLineEdit {{
                background-color: #1e1e24;
                color: #ffffff;
                border: 1px solid #3a3a44;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 10pt;
            }}
            QTableWidget QLineEdit:focus {{
                border: 1px solid {AppStyles.PRIMARY};
                background-color: #242430;
            }}

            QTableWidget QComboBox {{
                background-color: #1e1e24;
                color: #ffffff;
                border: 1px solid #3a3a44;
                border-radius: 5px;
                padding: 3px 6px;
                font-size: 9.5pt;
                font-weight: 500;
            }}
            QTableWidget QComboBox:focus {{
                border: 1px solid {AppStyles.PRIMARY};
            }}
            QTableWidget QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border-left: 1px solid #3a3a44;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }}
            QTableWidget QComboBox QAbstractItemView {{
                background-color: #1e1e24;
                color: #ffffff;
                selection-background-color: {AppStyles.PRIMARY};
                selection-color: #ffffff;
                border: 1px solid #3a3a44;
                padding: 4px;
            }}

            QTableWidget QDoubleSpinBox {{
                background-color: #1e1e24;
                color: #ffffff;
                border: 1px solid #3a3a44;
                border-radius: 5px;
                padding: 3px 4px 3px 6px;
                font-size: 10pt;
                font-weight: 600;
            }}
            QTableWidget QDoubleSpinBox:focus {{
                border: 1px solid {AppStyles.PRIMARY};
                background-color: #242430;
            }}
            QTableWidget QDoubleSpinBox::up-button, QTableWidget QDoubleSpinBox::down-button {{
                width: 18px;
                background-color: #2a2a32;
                border: none;
            }}
            QTableWidget QDoubleSpinBox::up-button:hover, QTableWidget QDoubleSpinBox::down-button:hover {{
                background-color: #3a3a44;
            }}
        """)
        try:
            db.ensure_bakery_supply_tables()
        except Exception:
            pass
        self.init_ui()
        self.load_suppliers_autocomplete()
        if item_id:
            self.load_data()
        else:
            self.add_item_row()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 24, 20)

        # Başlık
        title = QLabel("📦 " + ("Yeni Tedarik Girişi (Çoklu Ürün)" if not self.item_id else "Tedarik Kaydını Düzenle"))
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        layout.addWidget(title)

        # Üst Form Alanı
        form_frame = QFrame()
        form_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 12px 14px;
            }}
        """)
        f_lay = QVBoxLayout(form_frame)
        f_lay.setSpacing(10)

        # Satır 1: Tedarikçi Firma (geniş), Fatura No (küçük), Tarih (küçük)
        row1 = QHBoxLayout()
        row1.setSpacing(14)

        v_sup = QVBoxLayout()
        v_sup.setSpacing(4)
        v_sup.addWidget(QLabel("Tedarikçi Firma / Kişi *"))
        self.supplier_input = QLineEdit()
        self.supplier_input.setPlaceholderText("Örn: Öz Hal Manavı, Aktaş Şarküteri, Torku...")
        v_sup.addWidget(self.supplier_input)
        row1.addLayout(v_sup, 4)

        v_inv = QVBoxLayout()
        v_inv.setSpacing(4)
        v_inv.addWidget(QLabel("Fatura / İrsaliye No"))
        self.invoice_input = QLineEdit()
        self.invoice_input.setPlaceholderText("Örn: GIB2026...")
        self.invoice_input.setFixedWidth(170)
        v_inv.addWidget(self.invoice_input)
        row1.addLayout(v_inv, 0)

        v_date = QVBoxLayout()
        v_date.setSpacing(4)
        v_date.addWidget(QLabel("Tedarik / İrsaliye Tarihi"))
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setFixedWidth(145)
        v_date.addWidget(self.date_input)
        row1.addLayout(v_date, 0)

        f_lay.addLayout(row1)

        # Satır 2: Teslim Alan / Not
        v_notes = QVBoxLayout()
        v_notes.setSpacing(4)
        v_notes.addWidget(QLabel("Teslim Alan Personel / Açıklama Notu"))
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Teslim alan personel veya sevkiyat açıklaması notu...")
        v_notes.addWidget(self.notes_input)
        f_lay.addLayout(v_notes)

        layout.addWidget(form_frame)

        # Kalemler Tablo Başlığı ve Butonu
        items_header = QHBoxLayout()
        items_lbl = QLabel("📋 Sevkiyat Kalemleri (Bu firmaya ait teslim alınan ürünler):")
        items_lbl.setStyleSheet("font-size: 10.5pt; font-weight: bold; color: #f1f5f9;")
        items_header.addWidget(items_lbl)
        items_header.addStretch()

        btn_add_row = QPushButton("➕ Kalem Ekle")
        btn_add_row.setStyleSheet(f"""
            QPushButton {{
                background-color: #10b981;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 7px 16px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        btn_add_row.clicked.connect(lambda: self.add_item_row())
        items_header.addWidget(btn_add_row)
        layout.addLayout(items_header)

        # Kalemler Tablosu
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(7)
        self.items_table.setHorizontalHeaderLabels([
            "Malzeme / Ürün Adı *", "Kategori", "Miktar *", "Birim", "Birim Fiyat (₺)", "Tutar (₺)", "Sil"
        ])
        self.items_table.verticalHeader().setDefaultSectionSize(50)
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.items_table.setColumnWidth(1, 145)
        self.items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.items_table.setColumnWidth(2, 110)
        self.items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.items_table.setColumnWidth(3, 95)
        self.items_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.items_table.setColumnWidth(4, 130)
        self.items_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.items_table.setColumnWidth(5, 135)
        self.items_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.items_table.setColumnWidth(6, 100)
        layout.addWidget(self.items_table)

        # Alt Toplam ve Butonlar
        bottom_bar = QHBoxLayout()
        self.lbl_count = QLabel("Toplam: 0 Kalem")
        self.lbl_count.setStyleSheet("color: #94a3b8; font-size: 10pt; font-weight: 500;")
        bottom_bar.addWidget(self.lbl_count)
        bottom_bar.addStretch()

        self.lbl_grand_total = QLabel("Genel Toplam: 0.00 ₺")
        self.lbl_grand_total.setStyleSheet("font-size: 13pt; font-weight: bold; color: #10b981; margin-right: 16px;")
        bottom_bar.addWidget(self.lbl_grand_total)

        btn_box = QDialogButtonBox()
        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.setStyleSheet(AppStyles.btn_primary())
        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setStyleSheet(AppStyles.btn_secondary())

        btn_box.addButton(self.btn_save, QDialogButtonBox.AcceptRole)
        btn_box.addButton(self.btn_cancel, QDialogButtonBox.RejectRole)
        btn_box.accepted.connect(self.save)
        btn_box.rejected.connect(self.reject)
        bottom_bar.addWidget(btn_box)

        layout.addLayout(bottom_bar)

    def load_suppliers_autocomplete(self):
        try:
            suppliers = set()
            rows_s = db.fetch_all("SELECT DISTINCT supplier_name FROM bakery_supplies WHERE supplier_name IS NOT NULL AND supplier_name != ''")
            for r in rows_s or []:
                suppliers.add(r['supplier_name'])
            rows_c = db.fetch_all("SELECT title FROM Customers WHERE is_supplier = TRUE ORDER BY title")
            for r in rows_c or []:
                if r.get('title'):
                    suppliers.add(r['title'])
            sup_list = sorted(list(suppliers))
            completer = QCompleter(sup_list, self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            self.supplier_input.setCompleter(completer)
        except Exception as e:
            logger.warning(f"Tedarikçi otomatik tamamlama yüklenemedi: {e}")

    def add_item_row(self, name="", category="Hammadde", qty=1.0, unit="kg", price=0.0):
        row_idx = self.items_table.rowCount()
        self.items_table.insertRow(row_idx)

        # 0. Malzeme Adı
        name_edit = QLineEdit(name)
        name_edit.setPlaceholderText("Örn: Kaşar Peyniri, Domates, Un...")
        name_edit.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e24;
                color: #ffffff;
                border: 1px solid #3a3a44;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 10pt;
                font-weight: 500;
                min-height: 32px;
                max-height: 34px;
            }
            QLineEdit:focus {
                border: 1px solid #10b981;
                background-color: #242430;
            }
        """)
        self.items_table.setCellWidget(row_idx, 0, name_edit)

        # 1. Kategori
        cat_combo = QComboBox()
        cat_combo.addItems(["Manav", "Şarküteri", "Hammadde", "Un & Maya", "Süt Ürünleri", "Ambalaj", "Diğer"])
        cat_combo.setEditable(True)
        cat_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e1e24;
                color: #ffffff;
                border: 1px solid #3a3a44;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 9.5pt;
                font-weight: 500;
                min-height: 32px;
                max-height: 34px;
            }
        """)
        if category in ["Manav", "Şarküteri", "Hammadde", "Un & Maya", "Süt Ürünleri", "Ambalaj", "Diğer"]:
            cat_combo.setCurrentText(category)
        else:
            cat_combo.setCurrentText(category or "Hammadde")
        self.items_table.setCellWidget(row_idx, 1, cat_combo)

        # 2. Miktar
        qty_spin = QDoubleSpinBox()
        qty_spin.setRange(0.001, 999999.0)
        qty_spin.setDecimals(4)
        qty_spin.setValue(float(qty or 1.0))
        qty_spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        qty_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #1e1e24;
                color: #ffffff;
                border: 1px solid #3a3a44;
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 10pt;
                font-weight: 600;
                min-height: 32px;
                max-height: 34px;
            }
        """)
        qty_spin.valueChanged.connect(self._recalc_all_totals)
        self.items_table.setCellWidget(row_idx, 2, qty_spin)

        # 3. Birim
        unit_combo = QComboBox()
        unit_combo.addItems(["kg", "Kasa", "Adet", "Çuval", "Teneke", "Koli", "Litre", "Paket"])
        unit_combo.setEditable(True)
        unit_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e1e24;
                color: #ffffff;
                border: 1px solid #3a3a44;
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 9.5pt;
                font-weight: 500;
                min-height: 32px;
                max-height: 34px;
            }
        """)
        unit_combo.setCurrentText(unit or "kg")
        self.items_table.setCellWidget(row_idx, 3, unit_combo)

        # 4. Birim Fiyat
        price_spin = QDoubleSpinBox()
        price_spin.setRange(0.0, 999999.0)
        price_spin.setDecimals(2)
        price_spin.setValue(float(price or 0.0))
        price_spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        price_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #1e1e24;
                color: #ffffff;
                border: 1px solid #3a3a44;
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 10pt;
                font-weight: 600;
                min-height: 32px;
                max-height: 34px;
            }
        """)
        price_spin.valueChanged.connect(self._recalc_all_totals)
        self.items_table.setCellWidget(row_idx, 4, price_spin)

        # 5. Satır Toplamı (Label)
        tot_val = (float(qty or 1.0)) * (float(price or 0.0))
        lbl_tot = QLabel(f"{tot_val:,.2f} ₺")
        lbl_tot.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_tot.setStyleSheet("font-size: 10pt; font-weight: bold; color: #10b981; padding-right: 8px;")
        self.items_table.setCellWidget(row_idx, 5, lbl_tot)

        # 6. Sil Butonu (Hücre ortalı kapsayıcı ile sağ kenardan ve kaydırma çubuğundan asla kesilmez)
        del_widget = QWidget()
        d_lay = QHBoxLayout(del_widget)
        d_lay.setContentsMargins(2, 2, 2, 2)
        d_lay.setAlignment(Qt.AlignCenter)

        btn_del = QPushButton("🗑️ Sil")
        btn_del.setToolTip("Bu Kalemi Kaldır")
        btn_del.setFixedSize(76, 32)
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                font-size: 9.5pt;
                font-weight: bold;
                border-radius: 6px;
                border: none;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        btn_del.clicked.connect(lambda ch, r=btn_del: self._remove_row_by_widget(r))
        d_lay.addWidget(btn_del)
        self.items_table.setCellWidget(row_idx, 6, del_widget)

        self._recalc_all_totals()

    def _remove_row_by_widget(self, btn_widget):
        for r in range(self.items_table.rowCount()):
            cell_w = self.items_table.cellWidget(r, 6)
            if cell_w == btn_widget or (cell_w and btn_widget in cell_w.findChildren(QPushButton)):
                self.items_table.removeRow(r)
                break
        self._recalc_all_totals()

    def _recalc_all_totals(self):
        grand_total = 0.0
        count = self.items_table.rowCount()
        for r in range(count):
            qty_widget = self.items_table.cellWidget(r, 2)
            price_widget = self.items_table.cellWidget(r, 4)
            tot_label = self.items_table.cellWidget(r, 5)
            q = qty_widget.value() if isinstance(qty_widget, QDoubleSpinBox) else 0.0
            p = price_widget.value() if isinstance(price_widget, QDoubleSpinBox) else 0.0
            line_tot = q * p
            grand_total += line_tot
            if isinstance(tot_label, QLabel):
                tot_label.setText(f"{line_tot:,.2f} ₺")

        self.lbl_count.setText(f"Toplam: {count} Kalem")
        self.lbl_grand_total.setText(f"Genel Toplam: {grand_total:,.2f} ₺")

    def load_data(self):
        try:
            row = db.fetch_one("SELECT * FROM bakery_supplies WHERE id = %s", (self.item_id,))
            if not row:
                return

            if row.get('supply_date'):
                d = row['supply_date']
                if isinstance(d, str):
                    d = datetime.strptime(d[:10], "%Y-%m-%d").date()
                self.date_input.setDate(QDate(d.year, d.month, d.day))

            self.invoice_input.setText(row.get('invoice_no') or "")
            self.supplier_input.setText(row.get('supplier_name') or "")
            self.notes_input.setText(row.get('notes') or row.get('received_by') or "")

            # Kalemleri yükle
            items = db.fetch_all("""
                SELECT * FROM bakery_supply_items
                WHERE supply_id = %s
                ORDER BY id ASC
            """, (self.item_id,))

            self.items_table.setRowCount(0)
            if items:
                for itm in items:
                    self.add_item_row(
                        name=itm.get('item_name') or "",
                        category=itm.get('category') or "Hammadde",
                        qty=float(itm.get('quantity') or 1.0),
                        unit=itm.get('unit') or "kg",
                        price=float(itm.get('unit_price') or 0.0)
                    )
            elif row.get('item_name'):
                # Geriye dönük tek satır fallback
                self.add_item_row(
                    name=row.get('item_name') or "",
                    category=row.get('category') or "Hammadde",
                    qty=float(row.get('quantity') or 1.0),
                    unit=row.get('unit') or "kg",
                    price=float(row.get('unit_price') or 0.0)
                )
            else:
                self.add_item_row()

            self._recalc_all_totals()
        except Exception as e:
            logger.error(f"Error loading supply item: {e}")

    def save(self):
        supplier = self.supplier_input.text().strip()
        if not supplier:
            QMessageBox.warning(self, "Uyarı", "Lütfen tedarikçi firma veya kişi adını girin.")
            self.supplier_input.setFocus()
            return

        row_count = self.items_table.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen en az bir ürün kalemi ekleyin.")
            return

        items = []
        categories = set()
        for r in range(row_count):
            name_widget = self.items_table.cellWidget(r, 0)
            cat_widget = self.items_table.cellWidget(r, 1)
            qty_widget = self.items_table.cellWidget(r, 2)
            unit_widget = self.items_table.cellWidget(r, 3)
            price_widget = self.items_table.cellWidget(r, 4)

            name = name_widget.text().strip() if isinstance(name_widget, QLineEdit) else ""
            if not name:
                QMessageBox.warning(self, "Uyarı", f"{r+1}. satırdaki malzeme / ürün adını girin.")
                if name_widget:
                    name_widget.setFocus()
                return

            cat = cat_widget.currentText().strip() if isinstance(cat_widget, QComboBox) else "Hammadde"
            qty = qty_widget.value() if isinstance(qty_widget, QDoubleSpinBox) else 1.0
            unit = unit_widget.currentText().strip() if isinstance(unit_widget, QComboBox) else "kg"
            price = price_widget.value() if isinstance(price_widget, QDoubleSpinBox) else 0.0
            line_tot = qty * price

            categories.add(cat)
            items.append({
                'item_name': name,
                'category': cat,
                'quantity': qty,
                'unit': unit,
                'unit_price': price,
                'total_price': line_tot
            })

        date_val = self.date_input.date().toPyDate()
        inv_no = self.invoice_input.text().strip()
        notes = self.notes_input.text().strip()
        grand_total = sum(i['total_price'] for i in items)
        summary_cat = ", ".join(sorted(list(categories))) if categories else "Hammadde"
        first_item_name = items[0]['item_name'] if len(items) == 1 else f"{items[0]['item_name']} (+{len(items)-1} ürün)"

        try:
            with db.transaction():
                if self.item_id:
                    # Güncelleme
                    db.execute_query("""
                        UPDATE bakery_supplies
                        SET supply_date = %s, invoice_no = %s, supplier_name = %s,
                            item_name = %s, category = %s, total_price = %s,
                            notes = %s, received_by = %s
                        WHERE id = %s
                    """, (date_val, inv_no, supplier, first_item_name, summary_cat, grand_total, notes, notes, self.item_id))

                    # Kalemleri yenile
                    db.execute_query("DELETE FROM bakery_supply_items WHERE supply_id = %s", (self.item_id,))
                    for itm in items:
                        db.execute_query("""
                            INSERT INTO bakery_supply_items
                                (supply_id, item_name, category, quantity, unit, unit_price, total_price)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (self.item_id, itm['item_name'], itm['category'], itm['quantity'], itm['unit'], itm['unit_price'], itm['total_price']))
                else:
                    # Yeni Kayıt
                    res = db.fetch_one("""
                        INSERT INTO bakery_supplies
                            (supply_date, invoice_no, supplier_name, item_name, category,
                             total_price, notes, received_by)
                        VALUES
                            (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (date_val, inv_no, supplier, first_item_name, summary_cat, grand_total, notes, notes))

                    supply_id = res['id'] if res and 'id' in res else None
                    if supply_id:
                        for itm in items:
                            db.execute_query("""
                                INSERT INTO bakery_supply_items
                                    (supply_id, item_name, category, quantity, unit, unit_price, total_price)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (supply_id, itm['item_name'], itm['category'], itm['quantity'], itm['unit'], itm['unit_price'], itm['total_price']))

                    # Günlük Ciro ve Kasaya Gider olarak tek satırda yansıt
                    try:
                        from ...services.turnover_service import turnover_service
                        b_id = self.branch_id
                        if not b_id and hasattr(self.parent(), 'branch_id'):
                            b_id = getattr(self.parent(), 'branch_id', None)
                        if not b_id:
                            b_id = 1
                        u_id = getattr(self.user, 'id', None)
                        turnover_service.add_entry(
                            branch_id=b_id,
                            entry_date=str(date_val),
                            entry_type='Expense',
                            category=f"Tedarik: {items[0]['category']}",
                            amount=float(grand_total),
                            payment_method="Fatura / Tedarik",
                            description=f"Tedarik: {supplier} ({len(items)} Kalem Malzeme)" + (f" - Fatura: {inv_no}" if inv_no else ""),
                            user_id=u_id
                        )
                    except Exception as ex:
                        logger.warning(f"Ciroya yansıtma uyarısı: {ex}")

            self.accept()
        except Exception as e:
            logger.error(f"Error saving supply item: {e}")
            QMessageBox.critical(self, "Hata", f"Kaydedilirken hata oluştu: {e}")


# ══════════════════════════════════════════════════════════════
# 3. FATURADAN İÇE AKTARMA PENCERESİ (InvoiceImportDialog)
# ══════════════════════════════════════════════════════════════

class InvoiceImportDialog(QDialog):
    """Alış faturalarından imalathane tedarik listesine ürün aktarma penceresi (Tek Sevkiyat Olarak)"""

    def __init__(self, user: User = None, branch_id: int = None, parent=None):
        super().__init__(parent)
        self.user = user
        self.branch_id = branch_id
        self.setWindowTitle("🧾 Faturadan Tedarik Ürünü İçe Aktar")
        self.resize(980, 620)
        self.setMinimumWidth(880)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                gridline-color: {AppStyles.BORDER};
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
                font-weight: bold;
                padding: 6px;
                border: none;
            }}
        """)
        self.selected_invoice_id = None
        self.init_ui()
        self.load_invoices()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("🧾 Alış Faturaları ve Malzeme Kabul")
        header.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        layout.addWidget(header)

        sub_info = QLabel("Aşağıdan faturanızı seçin. Fatura içeriğindeki malzemeler tek bir tedarik kabul kaydı olarak içeri aktarılacaktır.")
        sub_info.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        layout.addWidget(sub_info)

        # Fatura Tablosu
        self.inv_table = QTableWidget()
        self.inv_table.setColumnCount(5)
        self.inv_table.setHorizontalHeaderLabels(["ID", "Fatura No", "Tarih", "Tedarikçi", "Toplam Tutar"])
        self.inv_table.verticalHeader().setDefaultSectionSize(34)
        self.inv_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.inv_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.inv_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.inv_table.itemSelectionChanged.connect(self.on_invoice_selected)
        layout.addWidget(self.inv_table, 2)

        # Kalem Tablosu
        layout.addWidget(QLabel("Seçili Faturanın Kalemleri:"))
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(6)
        self.items_table.setHorizontalHeaderLabels(["Kalem Adı", "Kategori Ata", "Miktar", "Birim", "Birim Fiyat", "Toplam"])
        self.items_table.verticalHeader().setDefaultSectionSize(38)
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.items_table.setColumnWidth(1, 145)
        self.items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.items_table.setColumnWidth(2, 105)
        self.items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.items_table.setColumnWidth(3, 85)
        self.items_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.items_table.setColumnWidth(4, 120)
        self.items_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.items_table.setColumnWidth(5, 125)
        layout.addWidget(self.items_table, 2)

        # Butonlar
        btn_box = QHBoxLayout()
        self.btn_import = QPushButton("⬇️ Faturadaki Kalemleri Listeye ve Ciroya Aktar")
        self.btn_import.setStyleSheet(AppStyles.btn_success())
        self.btn_import.clicked.connect(self.do_import)
        self.btn_import.setEnabled(False)

        btn_close = QPushButton("Kapat")
        btn_close.setStyleSheet(AppStyles.btn_secondary())
        btn_close.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(btn_close)
        btn_box.addWidget(self.btn_import)
        layout.addLayout(btn_box)

    def load_invoices(self):
        self.inv_table.setRowCount(0)
        try:
            sql = """
                SELECT i.id, i.invoice_no, i.invoice_date, i.grand_total, i.invoice_type,
                       COALESCE(c.title, 'Tedarikçi') as customer_name
                FROM invoices i
                LEFT JOIN customers c ON i.customer_id = c.id
            """
            params = []
            if self.branch_id:
                sql += " WHERE i.branch_id = %s"
                params.append(self.branch_id)
            sql += " ORDER BY i.invoice_date DESC, i.id DESC LIMIT 80"
            rows = db.fetch_all(sql, tuple(params) if params else ())

            self.inv_table.setRowCount(len(rows))
            for idx, r in enumerate(rows):
                self.inv_table.setItem(idx, 0, QTableWidgetItem(str(r['id'])))
                self.inv_table.setItem(idx, 1, QTableWidgetItem(r.get('invoice_no') or "-"))
                dt_str = str(r.get('invoice_date') or "")[:10]
                self.inv_table.setItem(idx, 2, QTableWidgetItem(dt_str))
                self.inv_table.setItem(idx, 3, QTableWidgetItem(r.get('customer_name') or "Tedarikçi"))
                tot = float(r.get('grand_total') or 0.0)
                self.inv_table.setItem(idx, 4, QTableWidgetItem(f"{tot:,.2f} ₺"))
        except Exception as e:
            logger.error(f"Error loading invoices: {e}")

    def on_invoice_selected(self):
        sel_items = self.inv_table.selectedItems()
        if not sel_items:
            self.btn_import.setEnabled(False)
            return
        row = self.inv_table.currentRow()
        inv_id_item = self.inv_table.item(row, 0)
        if not inv_id_item:
            return
        inv_id = int(inv_id_item.text())
        self.selected_invoice_id = inv_id
        self.btn_import.setEnabled(True)
        self.load_invoice_items(inv_id)

    def load_invoice_items(self, invoice_id: int):
        self.items_table.setRowCount(0)
        try:
            rows = db.fetch_all("""
                SELECT ii.id, ii.product_name, ii.quantity, ii.unit_price, ii.line_total,
                       p.name as prod_name, p.category as prod_cat, p.unit as prod_unit
                FROM invoiceitems ii
                LEFT JOIN products p ON ii.product_id = p.id
                WHERE ii.invoice_id = %s
            """, (invoice_id,))

            self.items_table.setRowCount(len(rows))
            for idx, r in enumerate(rows):
                p_name = r.get('product_name') or r.get('prod_name') or "Ürün"
                self.items_table.setItem(idx, 0, QTableWidgetItem(p_name))

                # Kategori combo
                cat_combo = QComboBox()
                cat_combo.addItems(["Manav", "Şarküteri", "Hammadde", "Un & Maya", "Süt Ürünleri", "Ambalaj", "Diğer"])
                name_l = p_name.lower()
                if any(w in name_l for w in ["peynir", "kaşar", "zeytin", "sucuk", "sosis", "salam", "şarküteri", "kasap", "et"]):
                    cat_combo.setCurrentText("Şarküteri")
                elif any(w in name_l for w in ["domates", "biber", "patates", "soğan", "maydonoz", "marul", "yeşillik", "ıspanak", "havuç", "meyve", "sebze"]):
                    cat_combo.setCurrentText("Manav")
                elif any(w in name_l for w in ["un", "maya", "tuz", "şeker", "yağ", "susam", "çörekotu", "çay", "kahve"]):
                    cat_combo.setCurrentText("Hammadde")
                self.items_table.setCellWidget(idx, 1, cat_combo)

                qty = float(r.get('quantity') or 1.0)
                q_item = QTableWidgetItem(f"{qty:,.2f}")
                q_item.setData(Qt.UserRole, qty)
                self.items_table.setItem(idx, 2, q_item)

                unit = r.get('prod_unit') or "kg"
                self.items_table.setItem(idx, 3, QTableWidgetItem(unit))

                price = float(r.get('unit_price') or 0.0)
                p_item = QTableWidgetItem(f"{price:,.2f} ₺")
                p_item.setData(Qt.UserRole, price)
                self.items_table.setItem(idx, 4, p_item)

                tot = float(r.get('line_total') or (qty * price))
                t_item = QTableWidgetItem(f"{tot:,.2f} ₺")
                t_item.setData(Qt.UserRole, tot)
                self.items_table.setItem(idx, 5, t_item)
        except Exception as e:
            logger.error(f"Error loading invoice items: {e}")

    def do_import(self):
        if not self.selected_invoice_id:
            return

        row_count = self.items_table.rowCount()
        if row_count == 0:
            QMessageBox.information(self, "Bilgi", "Bu faturada aktarılacak kalem bulunamadı.")
            return

        row = self.inv_table.currentRow()
        inv_no = self.inv_table.item(row, 1).text()
        inv_date_str = self.inv_table.item(row, 2).text()
        supplier = self.inv_table.item(row, 3).text()

        try:
            supply_date = datetime.strptime(inv_date_str, "%Y-%m-%d").date() if inv_date_str != "-" else datetime.now().date()
        except Exception:
            supply_date = datetime.now().date()

        items = []
        categories = set()
        total_imported_amount = 0.0

        for r in range(row_count):
            item_name = self.items_table.item(r, 0).text()
            cat_widget = self.items_table.cellWidget(r, 1)
            cat = cat_widget.currentText() if isinstance(cat_widget, QComboBox) else "Diğer"
            categories.add(cat)

            qty_raw = self.items_table.item(r, 2).data(Qt.UserRole)
            qty = float(qty_raw if qty_raw is not None else 1.0)

            unit = self.items_table.item(r, 3).text()

            price_raw = self.items_table.item(r, 4).data(Qt.UserRole)
            u_price = float(price_raw if price_raw is not None else 0.0)

            tot_raw = self.items_table.item(r, 5).data(Qt.UserRole)
            tot_price = float(tot_raw if tot_raw is not None else (qty * u_price))
            total_imported_amount += tot_price

            items.append({
                'item_name': item_name,
                'category': cat,
                'quantity': qty,
                'unit': unit,
                'unit_price': u_price,
                'total_price': tot_price
            })

        summary_cat = ", ".join(sorted(list(categories))) if categories else "Hammadde"
        first_item_name = items[0]['item_name'] if len(items) == 1 else f"{items[0]['item_name']} (+{len(items)-1} ürün)"

        try:
            from ...services.turnover_service import turnover_service
            b_id = self.branch_id
            if not b_id and hasattr(self.parent(), 'branch_id'):
                b_id = getattr(self.parent(), 'branch_id', None)
            if not b_id:
                b_id = 1
            u_id = getattr(self.user, 'id', None)

            with db.transaction():
                # 1. Ana Tedarik Kaydı (Tek Satır Olarak)
                res = db.fetch_one("""
                    INSERT INTO bakery_supplies
                        (invoice_id, invoice_no, supply_date, supplier_name, item_name,
                         category, total_price, notes)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (self.selected_invoice_id, inv_no, supply_date, supplier, first_item_name, summary_cat, total_imported_amount, f"Fatura #{inv_no} aktarımı"))

                supply_id = res['id'] if res and 'id' in res else None
                if supply_id:
                    for itm in items:
                        db.execute_query("""
                            INSERT INTO bakery_supply_items
                                (supply_id, item_name, category, quantity, unit, unit_price, total_price)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (supply_id, itm['item_name'], itm['category'], itm['quantity'], itm['unit'], itm['unit_price'], itm['total_price']))

                # 2. Günlük Ciro ve Kasaya Gider olarak tek kalemde yansıt
                try:
                    turnover_service.add_entry(
                        branch_id=b_id,
                        entry_date=str(supply_date),
                        entry_type='Expense',
                        category=f"Tedarik: {items[0]['category'] if items else 'Fatura'}",
                        amount=float(total_imported_amount),
                        payment_method="Fatura / Tedarik",
                        description=f"Faturadan Tedarik: {supplier} ({len(items)} Kalem) - Fatura #{inv_no}",
                        user_id=u_id
                    )
                except Exception as ex:
                    logger.warning(f"Ciroya yansıtma uyarısı: {ex}")

            QMessageBox.information(
                self, 
                "Başarılı", 
                f"{len(items)} kalem malzeme tek bir tedarik kabul kaydı olarak eklendi!\n"
                f"Toplam {total_imported_amount:,.2f} ₺ tutar Günlük Ciro ve Kasaya Gider olarak işlendi."
            )
            self.accept()
        except Exception as e:
            logger.error(f"Error importing invoice items: {e}")
            QMessageBox.critical(self, "Hata", f"Aktarım sırasında hata oluştu: {e}")


# ══════════════════════════════════════════════════════════════
# 4. ANA TEDARİK YÖNETİM SAYFASI (BakerySuppliesPage)
# ══════════════════════════════════════════════════════════════

class BakerySuppliesPage(QWidget):
    """
    İmalathane Tedarik & Malzeme Kabul Yönetim Sayfası
    Tedarikçi firma bazlı tek satır görünüm, açılır pencerede sınırsız kalem detayı.
    """

    def __init__(self, user: User, branch_id: int = None, parent=None):
        super().__init__(parent)
        self.user = user
        self.branch_id = branch_id
        self.all_items = []
        self.current_filtered_items = []

        try:
            db.ensure_bakery_supply_tables()
        except Exception as e:
            logger.warning(f"ensure_bakery_supply_tables warning: {e}")

        self.init_ui()
        self.load_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # 1. Başlık & Aksiyon Butonları
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("🥬 İmalathane Tedarik & Malzeme Takip Alanı")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        subtitle = QLabel("Tedarikçilerden alınan manav, şarküteri, hammadde ve un tedariklerinin konsolide kabulü ve detayları")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 10pt;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        btn_import_inv = QPushButton("🧾 Faturadan İçe Aktar")
        btn_import_inv.setStyleSheet(f"""
            QPushButton {{
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: #2563eb;
            }}
        """)
        btn_import_inv.clicked.connect(self.open_import_dialog)
        header_layout.addWidget(btn_import_inv)

        btn_add = QPushButton("➕ Yeni Tedarik Girişi")
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: #10b981;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        btn_add.clicked.connect(self.open_add_dialog)
        header_layout.addWidget(btn_add)

        main_layout.addLayout(header_layout)

        # 2. KPI Kartları
        self.kpi_layout = QHBoxLayout()
        self.kpi_layout.setSpacing(14)

        self.kpi_manav = self._create_kpi_card("🥬 Manav Tedariği", "0.00 ₺", "0 Kalem Kabul", "#10b981")
        self.kpi_sarkuteri = self._create_kpi_card("🧀 Şarküteri Tedariği", "0.00 ₺", "0 Kalem Kabul", "#f59e0b")
        self.kpi_hammadde = self._create_kpi_card("🌾 Hammadde & Un", "0.00 ₺", "0 Kalem Kabul", "#6366f1")
        self.kpi_total = self._create_kpi_card("💰 Toplam Tedarik Harcaması", "0.00 ₺", "Tüm Sevkiyatlar", "#ec4899")

        self.kpi_layout.addWidget(self.kpi_manav)
        self.kpi_layout.addWidget(self.kpi_sarkuteri)
        self.kpi_layout.addWidget(self.kpi_hammadde)
        self.kpi_layout.addWidget(self.kpi_total)
        main_layout.addLayout(self.kpi_layout)

        # 3. Filtreleme ve Arama Çubuğu
        filter_frame = QFrame()
        filter_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 6px 12px;
            }}
        """)
        ff_lay = QHBoxLayout(filter_frame)
        ff_lay.setSpacing(12)

        ff_lay.addWidget(QLabel("🔍 Arama:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tedarikçi firma, ürün adı, fatura no veya açıklama ara...")
        self.search_input.textChanged.connect(self.filter_data)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10pt;
            }}
        """)
        ff_lay.addWidget(self.search_input, 2)

        ff_lay.addWidget(QLabel("Kategori:"))
        self.filter_cat = QComboBox()
        self.filter_cat.addItems(["Tümü", "Manav", "Şarküteri", "Hammadde", "Un & Maya", "Süt Ürünleri", "Ambalaj", "Diğer"])
        self.filter_cat.currentTextChanged.connect(self.filter_data)
        self.filter_cat.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
            }}
        """)
        ff_lay.addWidget(self.filter_cat, 1)

        ff_lay.addWidget(QLabel("Dönem:"))
        self.filter_period = QComboBox()
        self.filter_period.addItems(["Tümü", "Bu Ay", "Son 7 Gün", "Bugün"])
        self.filter_period.currentTextChanged.connect(self.load_data)
        self.filter_period.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
            }}
        """)
        ff_lay.addWidget(self.filter_period, 1)

        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.setStyleSheet(AppStyles.btn_secondary())
        btn_refresh.clicked.connect(self.load_data)
        ff_lay.addWidget(btn_refresh)

        main_layout.addWidget(filter_frame)

        # 4. Konsolide Tablo (Sadeleştirilmiş Sütunlar)
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Tarih", "Fatura No", "Tedarikçi Firma / Kişi", "Kategori", "Kalem Sayısı", "Toplam Tutar", "Teslim Alan / Açıklama", "İşlemler"
        ])
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed)
        self.table.setColumnWidth(8, 185)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                gridline-color: {AppStyles.BORDER};
                font-size: 10pt;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
                font-weight: bold;
                font-size: 9.5pt;
                padding: 8px;
                border: none;
            }}
            QTableWidget::item:selected {{
                background-color: rgba(217, 119, 6, 0.25);
            }}
        """)
        # Satıra tıklandığında veya çift tıklandığında açılır pencere ile detayları göster
        self.table.cellDoubleClicked.connect(self.on_table_cell_clicked)
        self.table.cellClicked.connect(self.on_table_cell_clicked)
        main_layout.addWidget(self.table)

    def _create_kpi_card(self, title: str, val: str, sub: str, accent_color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-left: 4px solid {accent_color};
                border-radius: 8px;
                padding: 12px 14px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #94a3b8; font-size: 9.5pt; font-weight: 500;")
        layout.addWidget(t_lbl)

        v_lbl = QLabel(val)
        v_lbl.setObjectName("val_label")
        v_lbl.setStyleSheet(f"color: {accent_color}; font-size: 15pt; font-weight: bold;")
        layout.addWidget(v_lbl)

        s_lbl = QLabel(sub)
        s_lbl.setObjectName("sub_label")
        s_lbl.setStyleSheet("color: #64748b; font-size: 8.5pt;")
        layout.addWidget(s_lbl)

        return card

    def _update_kpi(self, card: QFrame, val: str, sub: str):
        v = card.findChild(QLabel, "val_label")
        if v:
            v.setText(val)
        s = card.findChild(QLabel, "sub_label")
        if s:
            s.setText(sub)

    def load_data(self):
        period = self.filter_period.currentText()
        date_filter_s = ""
        date_filter_where = ""
        if period == "Bugün":
            date_filter_s = "WHERE s.supply_date = CURRENT_DATE"
            date_filter_where = "WHERE supply_date = CURRENT_DATE"
        elif period == "Son 7 Gün":
            date_filter_s = "WHERE s.supply_date >= CURRENT_DATE - INTERVAL '7 days'"
            date_filter_where = "WHERE supply_date >= CURRENT_DATE - INTERVAL '7 days'"
        elif period == "Bu Ay":
            date_filter_s = "WHERE date_trunc('month', s.supply_date) = date_trunc('month', CURRENT_DATE)"
            date_filter_where = "WHERE date_trunc('month', supply_date) = date_trunc('month', CURRENT_DATE)"

        try:
            # 1. Ana konsolide tedarik listesini kalem sayısı ve ürün isimleriyle birlikte çek
            query = f"""
                SELECT s.id, s.supply_date, s.invoice_no, s.supplier_name, s.category,
                       s.total_price, s.received_by, s.notes,
                       COALESCE(NULLIF(COUNT(i.id), 0), 1) as item_count,
                       STRING_AGG(COALESCE(i.item_name, ''), ', ') as items_text
                FROM bakery_supplies s
                LEFT JOIN bakery_supply_items i ON s.id = i.supply_id
                {date_filter_s}
                GROUP BY s.id, s.supply_date, s.invoice_no, s.supplier_name, s.category,
                         s.total_price, s.received_by, s.notes
                ORDER BY s.supply_date DESC, s.id DESC
            """
            rows = db.fetch_all(query)
            self.all_items = rows or []

            # 2. KPI Hesaplama (Detay tablosundan kategori bazında hassas toplama)
            cat_query = f"""
                SELECT i.category,
                       SUM(i.total_price) as total_amt,
                       COUNT(i.id) as item_cnt,
                       SUM(i.quantity) as total_qty
                FROM bakery_supply_items i
                JOIN bakery_supplies s ON i.supply_id = s.id
                {date_filter_s}
                GROUP BY i.category
            """
            cat_stats = db.fetch_all(cat_query) or []

            tot_manav = sum(float(c['total_amt'] or 0) for c in cat_stats if "manav" in (c.get('category') or "").lower())
            cnt_manav = sum(int(c['item_cnt'] or 0) for c in cat_stats if "manav" in (c.get('category') or "").lower())

            tot_sark = sum(float(c['total_amt'] or 0) for c in cat_stats if "şarküteri" in (c.get('category') or "").lower())
            cnt_sark = sum(int(c['item_cnt'] or 0) for c in cat_stats if "şarküteri" in (c.get('category') or "").lower())

            tot_hamm = sum(float(c['total_amt'] or 0) for c in cat_stats if any(k in (c.get('category') or "").lower() for k in ["hammadde", "un", "maya", "süt"]))
            cnt_hamm = sum(int(c['item_cnt'] or 0) for c in cat_stats if any(k in (c.get('category') or "").lower() for k in ["hammadde", "un", "maya", "süt"]))

            tot_all = sum(float(i['total_price'] or 0) for i in self.all_items)

            self._update_kpi(self.kpi_manav, f"{tot_manav:,.2f} ₺", f"{cnt_manav} Kalem Ürün")
            self._update_kpi(self.kpi_sarkuteri, f"{tot_sark:,.2f} ₺", f"{cnt_sark} Kalem Ürün")
            self._update_kpi(self.kpi_hammadde, f"{tot_hamm:,.2f} ₺", f"{cnt_hamm} Kalem Ürün")
            self._update_kpi(self.kpi_total, f"{tot_all:,.2f} ₺", f"Toplam {len(self.all_items)} Tedarik Sevkiyatı")

            self.filter_data()
        except Exception as e:
            logger.error(f"Error loading bakery supplies: {e}")

    def filter_data(self):
        query = self.search_input.text().lower().strip()
        cat = self.filter_cat.currentText()

        filtered = []
        for item in self.all_items:
            if cat != "Tümü" and cat.lower() not in (item.get('category') or "").lower():
                continue
            if query:
                haystack = f"{item.get('supplier_name','')} {item.get('invoice_no','')} {item.get('notes','')} {item.get('received_by','')} {item.get('items_text','')}".lower()
                if query not in haystack:
                    continue
            filtered.append(item)

        self.current_filtered_items = filtered
        self._populate_table(filtered)

    def _populate_table(self, items):
        self.table.setRowCount(len(items))
        for row_idx, item in enumerate(items):
            # 0. ID
            id_item = QTableWidgetItem(str(item['id']))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, id_item)

            # 1. Tarih
            dt_str = str(item.get('supply_date') or "")[:10]
            d_item = QTableWidgetItem(dt_str)
            d_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 1, d_item)

            # 2. Fatura No
            inv_str = item.get('invoice_no') or "-"
            inv_item = QTableWidgetItem(inv_str)
            inv_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, inv_item)

            # 3. Tedarikçi Firma / Kişi
            sup_item = QTableWidgetItem(item.get('supplier_name') or "-")
            sup_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row_idx, 3, sup_item)

            # 4. Kategori Pill
            cat_str = item.get('category') or "Hammadde"
            cat_item = QTableWidgetItem(f"🏷️ {cat_str}")
            cat_item.setTextAlignment(Qt.AlignCenter)
            cat_lower = cat_str.lower()
            if "manav" in cat_lower:
                cat_item.setForeground(QColor("#34d399"))
            elif "şarküteri" in cat_lower:
                cat_item.setForeground(QColor("#fbbf24"))
            elif any(w in cat_lower for w in ["hammadde", "un", "maya"]):
                cat_item.setForeground(QColor("#818cf8"))
            else:
                cat_item.setForeground(QColor("#94a3b8"))
            self.table.setItem(row_idx, 4, cat_item)

            # 5. Kalem Sayısı Rozeti
            item_cnt = int(item.get('item_count') or 1)
            cnt_item = QTableWidgetItem(f"📦 {item_cnt} Kalem")
            cnt_item.setTextAlignment(Qt.AlignCenter)
            cnt_item.setForeground(QColor("#38bdf8"))
            cnt_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row_idx, 5, cnt_item)

            # 6. Toplam Tutar
            tot_price = float(item.get('total_price') or 0.0)
            tp_item = QTableWidgetItem(f"{tot_price:,.2f} ₺")
            tp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tp_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            tp_item.setForeground(QColor("#10b981"))
            self.table.setItem(row_idx, 6, tp_item)

            # 7. Teslim Alan / Açıklama
            desc = item.get('received_by') or item.get('notes') or "-"
            self.table.setItem(row_idx, 7, QTableWidgetItem(desc))

            # 8. İşlem Butonları (Detay 👁️, Sil 🗑️)
            action_widget = QWidget()
            a_lay = QHBoxLayout(action_widget)
            a_lay.setContentsMargins(2, 2, 2, 2)
            a_lay.setSpacing(8)
            a_lay.setAlignment(Qt.AlignCenter)

            btn_view = QPushButton("👁️ Detay")
            btn_view.setToolTip("Sevkiyat Detaylarını ve Kalemlerini Görüntüle / Düzenle")
            btn_view.setFixedSize(76, 32)
            btn_view.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    border-radius: 6px;
                    font-size: 9pt;
                    font-weight: 600;
                    padding: 2px 6px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #0369a1;
                }
            """)
            btn_view.clicked.connect(lambda ch, i_id=item['id']: self.open_detail_dialog(i_id))

            btn_del = QPushButton("🗑️ Sil")
            btn_del.setToolTip("Sevkiyatı ve Tüm Kalemleri Sil")
            btn_del.setFixedSize(68, 32)
            btn_del.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    color: white;
                    border-radius: 6px;
                    font-size: 9pt;
                    font-weight: bold;
                    border: none;
                    padding: 2px 6px;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                }
            """)
            btn_del.clicked.connect(lambda ch, i_id=item['id']: self.delete_item(i_id))

            a_lay.addWidget(btn_view)
            a_lay.addWidget(btn_del)
            self.table.setCellWidget(row_idx, 8, action_widget)

    def on_table_cell_clicked(self, row: int, col: int):
        """Tablo hücresine tıklandığında açılır pencerede detayları gösterir"""
        if row < 0 or row >= len(self.current_filtered_items):
            return
        if col == 8:
            return  # Butonların kendi tıklama işleyicisi var
        item = self.current_filtered_items[row]
        self.open_detail_dialog(item['id'])

    def open_detail_dialog(self, item_id: int):
        dlg = SupplyDetailDialog(supply_id=item_id, user=self.user, branch_id=self.branch_id, parent=self)
        dlg.exec_()

    def open_add_dialog(self):
        dlg = SupplyEntryDialog(user=self.user, branch_id=self.branch_id, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_edit_dialog(self, item_id: int):
        dlg = SupplyEntryDialog(user=self.user, branch_id=self.branch_id, parent=self, item_id=item_id)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_import_dialog(self):
        dlg = InvoiceImportDialog(user=self.user, branch_id=self.branch_id, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def delete_item(self, item_id: int):
        reply = QMessageBox.question(
            self, "Silme Onayı",
            "Bu tedarik kaydını ve altındaki tüm ürün kalemlerini silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                with db.transaction():
                    db.execute_query("DELETE FROM bakery_supply_items WHERE supply_id = %s", (item_id,))
                    db.execute_query("DELETE FROM bakery_supplies WHERE id = %s", (item_id,))
                self.load_data()
            except Exception as e:
                logger.error(f"Error deleting supply item: {e}")
                QMessageBox.critical(self, "Hata", f"Silinirken hata oluştu: {e}")
