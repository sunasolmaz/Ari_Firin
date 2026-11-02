# src/ui/pages/production_hub_page.py
"""
Fırın İmalathane & Üretim Dağıtım Merkezi Sayfası
- Günlük fırın üretimi (Ekmek, Simit, Poğaça, Unlu Mamül, Tatlı, Pasta)
- 3 Şubeye iç dağıtım ve sevkiyat (Armada, Çobançeşme, Rumeli)
- Dış müşterilere toptan satış (Marketler, Oteller, Restoranlar, Kafeler)
- Hammadde ve mamul stok takibi
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QDateEdit, QComboBox, QLineEdit,
    QDoubleSpinBox, QMessageBox, QHeaderView, QGraphicsDropShadowEffect,
    QScrollArea, QTabWidget, QDialog, QFormLayout, QTextEdit, QCompleter,
    QDialogButtonBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any

from ...models.user import User
from ...core.database import db
from ...core.logger import logger
from ...services.production_service import production_service
from ...services.payment_plan_service import payment_plan_service
from ..notifications_dialog import NotificationsDialog
from ..styles import AppStyles


# ==================== DİYALOGLAR ====================

class AddProductionDialog(QDialog):
    """Yeni Üretim Partisi Ekleme Penceresi"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🥖 Yeni Fırın Üretimi Kaydı")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; font-weight: 500; }}
            QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit, QDateEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 10pt;
            }}
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("🍞 Fırın İmalat / Üretim Girişi")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.PRIMARY}; margin-bottom: 8px;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        form.addRow("Üretim Tarihi:", self.date_edit)

        self.category_cb = QComboBox()
        self.category_cb.addItems(["Ekmek", "Simit & Poğaça", "Unlu Mamül", "Tatlı", "Pasta", "Diğer"])
        form.addRow("Kategori:", self.category_cb)

        self.product_name_input = QLineEdit()
        self.product_name_input.setPlaceholderText("Örn: Somun Ekmek, Çavdar Ekmeği, Kandil Simidi...")
        # Popüler fırın ürünleri tamamlayıcısı
        popular_items = [
            "Somun Ekmek (200 gr)", "Kepekli Ekmek", "Tam Buğday Ekmeği", "Çavdar Ekmeği",
            "Köy Ekmeği", "Trabzon Ekmeği", "Baget Ekmek", "Sokak Simidi", "Kandil Simidi",
            "Sade Poğaça", "Peynirli Poğaça", "Zeytinli Açma", "Kaşarlı Açma", "Boyoz",
            "Su Böreği (Tepsi)", "Kıymalı Kol Böreği", "Peynirli Kol Böreği", "Baklava (Tepsi)",
            "Kuru Pasta (Tuzlu)", "Kuru Pasta (Tatlı)", "Yaş Pasta (No:1)", "Yaş Pasta (No:2)"
        ]
        completer = QCompleter(popular_items)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.product_name_input.setCompleter(completer)
        form.addRow("Ürün Adı *:", self.product_name_input)

        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0.1, 999999999.999)
        self.qty_spin.setValue(100.0)
        self.qty_spin.setDecimals(2)
        form.addRow("Üretilen Miktar *:", self.qty_spin)

        self.unit_cb = QComboBox()
        self.unit_cb.addItems(["Adet", "Kg", "Tepsi", "Koli", "Porsiyon"])
        form.addRow("Birim:", self.unit_cb)

        self.cost_spin = QDoubleSpinBox()
        self.cost_spin.setRange(0.0, 999999999999.99)
        self.cost_spin.setDecimals(2)
        self.cost_spin.setSuffix(" ₺")
        form.addRow("Tahmini Birim Maliyet:", self.cost_spin)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0.0, 999999999999.99)
        self.price_spin.setDecimals(2)
        self.price_spin.setSuffix(" ₺")
        form.addRow("Satış / Sevk Fiyatı:", self.price_spin)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(65)
        self.notes_input.setPlaceholderText("Vardiya, usta veya un partisi notları...")
        form.addRow("Açıklama / Not:", self.notes_input)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 8px 18px;
            }}
            QPushButton:hover {{ background-color: {AppStyles.BG_LIGHT}; }}
        """)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Üretimi Kaydet")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.save)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.SUCCESS});
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                padding: 8px 22px;
            }}
        """)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)

    def save(self):
        p_name = self.product_name_input.text().strip()
        if not p_name:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen ürün adını yazınız!")
            return

        data = {
            'production_date': self.date_edit.date().toString('yyyy-MM-dd'),
            'category': self.category_cb.currentText(),
            'product_name': p_name,
            'quantity': self.qty_spin.value(),
            'unit': self.unit_cb.currentText(),
            'unit_cost': self.cost_spin.value(),
            'sale_price': self.price_spin.value(),
            'notes': self.notes_input.toPlainText().strip()
        }

        ok, msg, _ = production_service.add_production(data)
        if ok:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)


# ==================== 2. ŞUBEYE SEVKİYAT DİYALOGLARI (ÇOKLU KALEM) ====================

class ShipmentDetailDialog(QDialog):
    """Şubeye Sevkiyat Detaylarını ve Kalemlerini Gösteren Açılır Pencere"""

    def __init__(self, shipment_id: int, user: User = None, branch_id: int = None, parent=None):
        super().__init__(parent)
        self.shipment_id = shipment_id
        self.user = user
        self.branch_id = branch_id
        self.shipment_data = None
        self.items_data = []

        self.setWindowTitle("🚚 Şubeye Sevkiyat Detayı")
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
                background-color: rgba(6, 182, 212, 0.25);
            }}
        """)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 24, 20)

        # 1. Başlık & Şube Kartı
        header_card = QFrame()
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-left: 5px solid {AppStyles.CYAN};
                border-radius: 8px;
                padding: 12px 16px;
            }}
        """)
        h_lay = QHBoxLayout(header_card)
        h_lay.setContentsMargins(0, 0, 0, 0)

        v_info = QVBoxLayout()
        v_info.setSpacing(4)
        self.lbl_branch = QLabel("🏢 Hedef Şube")
        self.lbl_branch.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {AppStyles.CYAN};")
        v_info.addWidget(self.lbl_branch)

        self.lbl_info = QLabel("📅 Tarih: -   |   📄 Sevk No: -   |   🚚 Şoför / Not: -")
        self.lbl_info.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        v_info.addWidget(self.lbl_info)
        h_lay.addLayout(v_info, 3)

        v_tot = QVBoxLayout()
        v_tot.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        t_sub = QLabel("Genel Toplam Sevk Tutarı")
        t_sub.setStyleSheet("color: #94a3b8; font-size: 8.5pt;")
        self.lbl_total = QLabel("0.00 ₺")
        self.lbl_total.setStyleSheet("font-size: 16pt; font-weight: bold; color: #10b981;")
        v_tot.addWidget(t_sub)
        v_tot.addWidget(self.lbl_total)
        h_lay.addLayout(v_tot, 1)

        layout.addWidget(header_card)

        # 2. Kalemler Tablosu
        sec_title = QLabel("📋 Sevkiyatta Bulunan Ürün Kalemleri:")
        sec_title.setStyleSheet("font-size: 10.5pt; font-weight: bold; color: #e2e8f0; margin-top: 4px;")
        layout.addWidget(sec_title)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "#", "Ürün Adı", "Kategori", "Miktar", "Birim", "Transfer Fiyatı (₺)", "Toplam Tutar"
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
        self.table.setColumnWidth(5, 140)
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

        btn_edit = QPushButton("✏️ Bu Sevkiyatı Düzenle")
        btn_edit.setStyleSheet(AppStyles.btn_primary())
        btn_edit.clicked.connect(self.edit_record)
        btn_box.addWidget(btn_edit)

        btn_del = QPushButton("🗑️ Bu Sevkiyatı Sil")
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
        shipment, items = production_service.get_shipment_details(self.shipment_id)
        if not shipment:
            QMessageBox.warning(self, "Hata", "Sevkiyat kaydı bulunamadı!")
            self.reject()
            return

        self.shipment_data = shipment
        self.items_data = items

        b_name = shipment.get('target_branch_name') or 'Şube'
        self.lbl_branch.setText(f"🏢 Hedef Şube: {b_name}")

        dt_str = shipment['shipment_date'].strftime('%d.%m.%Y') if hasattr(shipment['shipment_date'], 'strftime') else str(shipment['shipment_date'])
        s_no = shipment.get('shipment_no') or f"SVK-{shipment['id']}"
        notes = shipment.get('driver_notes') or '-'
        self.lbl_info.setText(f"📅 Tarih: {dt_str}   |   📄 Sevk No: {s_no}   |   🚚 Şoför / Not: {notes}")

        total_val = float(shipment.get('total_amount') or 0.0)
        self.lbl_total.setText(f"{total_val:,.2f} ₺")

        self.table.setRowCount(len(items))
        total_qty = 0.0
        for r_idx, itm in enumerate(items):
            # 0. Sırano
            no_item = QTableWidgetItem(str(r_idx + 1))
            no_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r_idx, 0, no_item)

            # 1. Ürün Adı
            p_name = itm.get('product_name') or '-'
            p_item = QTableWidgetItem(p_name)
            p_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(r_idx, 1, p_item)

            # 2. Kategori
            c_item = QTableWidgetItem(itm.get('category') or 'Unlu Mamül')
            c_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r_idx, 2, c_item)

            # 3. Miktar
            qty = float(itm.get('quantity') or 0.0)
            total_qty += qty
            q_item = QTableWidgetItem(f"{qty:,.2f}")
            q_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r_idx, 3, q_item)

            # 4. Birim
            u_item = QTableWidgetItem(itm.get('unit') or 'Adet')
            u_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r_idx, 4, u_item)

            # 5. Birim Fiyat
            p_val = float(itm.get('unit_price') or 0.0)
            pr_item = QTableWidgetItem(f"{p_val:,.2f} ₺")
            pr_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r_idx, 5, pr_item)

            # 6. Toplam Tutar
            tot_line = float(itm.get('total_amount') or (qty * p_val))
            tot_item = QTableWidgetItem(f"{tot_line:,.2f} ₺")
            tot_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            tot_item.setForeground(QColor("#10b981"))
            tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r_idx, 6, tot_item)

        self.lbl_summary.setText(f"Toplam {len(items)} Kalem   |   Toplam Miktar: {total_qty:,.1f}")

    def edit_record(self):
        dlg = ShipmentEntryDialog(parent=self.parent(), shipment_id=self.shipment_id, user=self.user, branch_id=self.branch_id)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()
            if self.parent() and hasattr(self.parent(), 'load_all_data'):
                self.parent().load_all_data()

    def delete_record(self):
        reply = QMessageBox.question(
            self, "Onay",
            "Bu sevkiyatı ve içerisindeki tüm ürün kalemlerini silmek istediğinize emin misiniz?\n"
            "İmalathane ve hedef şube stokları otomatik olarak geri yüklenecektir.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = production_service.delete_shipment(self.shipment_id)
            if ok:
                QMessageBox.information(self, "Başarılı", msg)
                if self.parent() and hasattr(self.parent(), 'load_all_data'):
                    self.parent().load_all_data()
                self.accept()
            else:
                QMessageBox.critical(self, "Hata", msg)


class ShipmentEntryDialog(QDialog):
    """3 Şubeye Sevkiyat Girişi veya Düzenleme Penceresi (Sınırsız Çoklu Kalem Destekli)"""

    def __init__(self, parent=None, shipment_id: int = None, user: User = None, branch_id: int = None):
        super().__init__(parent)
        self.shipment_id = shipment_id
        self.user = user
        self.branch_id = branch_id

        self.setWindowTitle("🚚 Yeni Şube Sevkiyatı (Çoklu Ürün)" if not shipment_id else "✏️ Sevkiyat Kaydını Düzenle")
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
            QLineEdit, QDateEdit, QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10pt;
            }}
            QLineEdit:focus, QDateEdit:focus, QComboBox:focus {{
                border-color: {AppStyles.CYAN};
            }}

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

            QTableWidget QLineEdit {{
                background-color: #1e1e24;
                color: #ffffff;
                border: 1px solid #3a3a44;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 10pt;
            }}
            QTableWidget QLineEdit:focus {{
                border: 1px solid {AppStyles.CYAN};
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
                border: 1px solid {AppStyles.CYAN};
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
                border: 1px solid {AppStyles.CYAN};
                background-color: #242430;
            }}
        """)
        self.popular_items = self._get_production_items()
        self.init_ui()
        if self.shipment_id:
            self.load_data()
        else:
            self.add_item_row()

    def _get_production_items(self) -> List[str]:
        items = [
            "Somun Ekmek (200 gr)", "Kepekli Ekmek", "Tam Buğday Ekmeği", "Çavdar Ekmeği",
            "Köy Ekmeği", "Trabzon Ekmeği", "Baget Ekmek", "Sokak Simidi", "Kandil Simidi",
            "Sade Poğaça", "Peynirli Poğaça", "Zeytinli Açma", "Kaşarlı Açma", "Boyoz",
            "Su Böreği (Tepsi)", "Kıymalı Kol Böreği", "Peynirli Kol Böreği", "Baklava (Tepsi)",
            "Kuru Pasta (Tuzlu)", "Kuru Pasta (Tatlı)", "Yaş Pasta (No:1)", "Yaş Pasta (No:2)"
        ]
        try:
            prods = production_service.get_productions()[:30]
            for p in prods:
                p_name = p.get('product_name')
                if p_name and p_name not in items:
                    items.insert(0, p_name)
        except Exception:
            pass
        return items

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 24, 20)

        # Başlık
        title = QLabel("🚚 " + ("Yeni Şube Sevkiyatı (Çoklu Ürün)" if not self.shipment_id else "Sevkiyat Kaydını Düzenle"))
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.CYAN};")
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

        # Satır 1: Hedef Şube, Sevk No, Sevkiyat Tarihi
        row1 = QHBoxLayout()
        row1.setSpacing(14)

        v_br = QVBoxLayout()
        v_br.setSpacing(4)
        v_br.addWidget(QLabel("Hedef Şube *"))
        self.branch_cb = QComboBox()
        branches = production_service.get_retail_branches()
        for b in branches:
            self.branch_cb.addItem(f"🏢 {b['name']} ({b.get('city') or 'Merkez'})", b['id'])
        v_br.addWidget(self.branch_cb)
        row1.addLayout(v_br, 4)

        v_no = QVBoxLayout()
        v_no.setSpacing(4)
        v_no.addWidget(QLabel("Sevk / İrsaliye No"))
        self.ship_no_input = QLineEdit()
        self.ship_no_input.setText(f"SVK-{datetime.now().strftime('%y%m%d')}-{int(datetime.now().timestamp()) % 10000:04d}")
        self.ship_no_input.setFixedWidth(180)
        v_no.addWidget(self.ship_no_input)
        row1.addLayout(v_no, 0)

        v_date = QVBoxLayout()
        v_date.setSpacing(4)
        v_date.addWidget(QLabel("Sevkiyat Tarihi"))
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setFixedWidth(145)
        v_date.addWidget(self.date_input)
        row1.addLayout(v_date, 0)

        f_lay.addLayout(row1)

        # Satır 2: Şoför / Araç / Not
        v_notes = QVBoxLayout()
        v_notes.setSpacing(4)
        v_notes.addWidget(QLabel("Şoför, Araç Plakası veya Sevkiyat Notu"))
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Teslimatı yapan şoför, plaka veya sipariş notu...")
        v_notes.addWidget(self.notes_input)
        f_lay.addLayout(v_notes)

        layout.addWidget(form_frame)

        # Kalemler Tablo Başlığı ve Butonu
        items_header = QHBoxLayout()
        items_lbl = QLabel("📋 Sevkiyat Kalemleri (Sevk edilen tüm fırın ürünleri):")
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
            "Ürün Adı *", "Kategori", "Miktar *", "Birim", "Transfer Birim Fiyatı (₺)", "Tutar (₺)", "Sil"
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
        self.items_table.setColumnWidth(4, 150)
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
        self.btn_save = QPushButton("💾 Sevkiyatı Kaydet")
        self.btn_save.setStyleSheet(AppStyles.btn_primary())
        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setStyleSheet(AppStyles.btn_secondary())

        btn_box.addButton(self.btn_save, QDialogButtonBox.AcceptRole)
        btn_box.addButton(self.btn_cancel, QDialogButtonBox.RejectRole)
        btn_box.accepted.connect(self.save)
        btn_box.rejected.connect(self.reject)
        bottom_bar.addWidget(btn_box)

        layout.addLayout(bottom_bar)

    def add_item_row(self, name="", category="Unlu Mamül", qty=50.0, unit="Adet", price=10.0):
        row_idx = self.items_table.rowCount()
        self.items_table.insertRow(row_idx)

        # 0. Ürün Adı
        name_edit = QLineEdit(name)
        name_edit.setPlaceholderText("Örn: Somun Ekmek (200 gr), Sokak Simidi...")
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
                border: 1px solid #06b6d4;
                background-color: #242430;
            }
        """)
        completer = QCompleter(self.popular_items, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        name_edit.setCompleter(completer)
        self.items_table.setCellWidget(row_idx, 0, name_edit)

        # 1. Kategori
        cat_combo = QComboBox()
        cat_combo.addItems(["Ekmek", "Simit & Poğaça", "Unlu Mamül", "Tatlı", "Pasta", "Diğer"])
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
        cat_combo.setCurrentText(category or "Unlu Mamül")
        self.items_table.setCellWidget(row_idx, 1, cat_combo)

        # 2. Miktar
        qty_spin = QDoubleSpinBox()
        qty_spin.setRange(0.01, 999999.0)
        qty_spin.setDecimals(2)
        qty_spin.setValue(float(qty or 50.0))
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
        unit_combo.addItems(["Adet", "Kg", "Tepsi", "Koli", "Porsiyon", "Paket"])
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
        unit_combo.setCurrentText(unit or "Adet")
        self.items_table.setCellWidget(row_idx, 3, unit_combo)

        # 4. Transfer Birim Fiyat
        price_spin = QDoubleSpinBox()
        price_spin.setRange(0.0, 999999.0)
        price_spin.setDecimals(2)
        price_spin.setValue(float(price or 10.0))
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
        tot_val = (float(qty or 50.0)) * (float(price or 10.0))
        lbl_tot = QLabel(f"{tot_val:,.2f} ₺")
        lbl_tot.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_tot.setStyleSheet("font-size: 10pt; font-weight: bold; color: #10b981; padding-right: 8px;")
        self.items_table.setCellWidget(row_idx, 5, lbl_tot)

        # 6. Sil Butonu (Hücre ortalı kapsayıcı ile sağ kenardan asla kesilmez)
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
            shipment, items = production_service.get_shipment_details(self.shipment_id)
            if not shipment:
                return

            # Şube seçimi
            target_id = shipment.get('target_branch_id')
            for i in range(self.branch_cb.count()):
                if self.branch_cb.itemData(i) == target_id:
                    self.branch_cb.setCurrentIndex(i)
                    break

            if shipment.get('shipment_date'):
                d = shipment['shipment_date']
                if isinstance(d, str):
                    d = datetime.strptime(d[:10], "%Y-%m-%d").date()
                self.date_input.setDate(QDate(d.year, d.month, d.day))

            self.ship_no_input.setText(shipment.get('shipment_no') or "")
            self.notes_input.setText(shipment.get('driver_notes') or "")

            self.items_table.setRowCount(0)
            if items:
                for itm in items:
                    self.add_item_row(
                        name=itm.get('product_name') or "",
                        category=itm.get('category') or "Unlu Mamül",
                        qty=float(itm.get('quantity') or 1.0),
                        unit=itm.get('unit') or "Adet",
                        price=float(itm.get('unit_price') or 0.0)
                    )
            else:
                self.add_item_row()

            self._recalc_all_totals()
        except Exception as e:
            logger.error(f"Sevkiyat düzenleme verisi yüklenirken hata: {e}")

    def save(self):
        target_branch_id = self.branch_cb.currentData()
        if not target_branch_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir hedef şube seçin.")
            return

        row_count = self.items_table.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen en az bir sevk kalemi ekleyin.")
            return

        items = []
        for r in range(row_count):
            name_widget = self.items_table.cellWidget(r, 0)
            cat_widget = self.items_table.cellWidget(r, 1)
            qty_widget = self.items_table.cellWidget(r, 2)
            unit_widget = self.items_table.cellWidget(r, 3)
            price_widget = self.items_table.cellWidget(r, 4)

            name = name_widget.text().strip() if isinstance(name_widget, QLineEdit) else ""
            if not name:
                QMessageBox.warning(self, "Uyarı", f"{r+1}. satırdaki ürün adını girin.")
                if name_widget:
                    name_widget.setFocus()
                return

            cat = cat_widget.currentText().strip() if isinstance(cat_widget, QComboBox) else "Unlu Mamül"
            qty = qty_widget.value() if isinstance(qty_widget, QDoubleSpinBox) else 1.0
            unit = unit_widget.currentText().strip() if isinstance(unit_widget, QComboBox) else "Adet"
            price = price_widget.value() if isinstance(price_widget, QDoubleSpinBox) else 0.0
            line_tot = qty * price

            items.append({
                'product_name': name,
                'category': cat,
                'quantity': qty,
                'unit': unit,
                'unit_price': price,
                'total_amount': line_tot
            })

        data = {
            'target_branch_id': target_branch_id,
            'shipment_date': self.date_input.date().toString('yyyy-MM-dd'),
            'shipment_no': self.ship_no_input.text().strip(),
            'driver_notes': self.notes_input.text().strip()
        }

        user_id = self.user.id if self.user else None
        if self.shipment_id:
            ok, msg = production_service.update_multi_shipment(self.shipment_id, data, items, user_id)
        else:
            ok, msg, _ = production_service.add_multi_shipment(data, items, user_id)

        if ok:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)


# Geriye dönük uyumluluk takma adı
AddShipmentDialog = ShipmentEntryDialog


# ==================== 3. DIŞ MÜŞTERİ SATIŞ DİYALOGLARI (ÇOKLU KALEM) ====================

class ExternalSaleDetailDialog(QDialog):
    """Dış Müşteri Toptan Satış Detaylarını ve Kalemlerini Gösteren Açılır Pencere"""

    def __init__(self, sale_id: int, user: User = None, branch_id: int = None, parent=None):
        super().__init__(parent)
        self.sale_id = sale_id
        self.user = user
        self.branch_id = branch_id
        self.sale_data = None
        self.items_data = []

        self.setWindowTitle("🛒 Dış Müşteri Toptan Satış Detayı")
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
                background-color: rgba(16, 185, 129, 0.25);
            }}
        """)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 24, 20)

        # 1. Başlık & Müşteri Kartı
        header_card = QFrame()
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-left: 5px solid {AppStyles.SUCCESS};
                border-radius: 8px;
                padding: 12px 16px;
            }}
        """)
        h_lay = QHBoxLayout(header_card)
        h_lay.setContentsMargins(0, 0, 0, 0)

        v_info = QVBoxLayout()
        v_info.setSpacing(4)
        self.lbl_customer = QLabel("🤝 Müşteri / Firma Adı")
        self.lbl_customer.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {AppStyles.SUCCESS};")
        v_info.addWidget(self.lbl_customer)

        self.lbl_info = QLabel("📅 Tarih: -   |   📄 Satış No: -   |   💳 Tahsilat: -   |   📝 Not: -")
        self.lbl_info.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        v_info.addWidget(self.lbl_info)
        h_lay.addLayout(v_info, 3)

        v_tot = QVBoxLayout()
        v_tot.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        t_sub = QLabel("Genel Toplam Satış Tutarı")
        t_sub.setStyleSheet("color: #94a3b8; font-size: 8.5pt;")
        self.lbl_total = QLabel("0.00 ₺")
        self.lbl_total.setStyleSheet("font-size: 16pt; font-weight: bold; color: #10b981;")
        v_tot.addWidget(t_sub)
        v_tot.addWidget(self.lbl_total)
        h_lay.addLayout(v_tot, 1)

        layout.addWidget(header_card)

        # 2. Kalemler Tablosu
        sec_title = QLabel("📋 Satışta Bulunan Ürün Kalemleri:")
        sec_title.setStyleSheet("font-size: 10.5pt; font-weight: bold; color: #e2e8f0; margin-top: 4px;")
        layout.addWidget(sec_title)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "#", "Ürün Adı", "Kategori", "Miktar", "Birim", "Satış Fiyatı (₺)", "Toplam Tutar"
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
        self.table.setColumnWidth(5, 140)
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

        btn_edit = QPushButton("✏️ Bu Satışı Düzenle")
        btn_edit.setStyleSheet(AppStyles.btn_primary())
        btn_edit.clicked.connect(self.edit_record)
        btn_box.addWidget(btn_edit)

        btn_del = QPushButton("🗑️ Bu Satışı Sil")
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
        sale, items = production_service.get_external_sale_details(self.sale_id)
        if not sale:
            QMessageBox.warning(self, "Hata", "Satış kaydı bulunamadı!")
            self.reject()
            return

        self.sale_data = sale
        self.items_data = items

        c_name = sale.get('customer_name') or 'Müşteri'
        self.lbl_customer.setText(f"🤝 Müşteri / Firma: {c_name}")

        dt_str = sale['sale_date'].strftime('%d.%m.%Y') if hasattr(sale['sale_date'], 'strftime') else str(sale['sale_date'])
        s_no = sale.get('sale_no') or f"SAT-{sale['id']}"
        pay = sale.get('payment_method') or 'Nakit'
        notes = sale.get('notes') or '-'
        self.lbl_info.setText(f"📅 Tarih: {dt_str}   |   📄 Satış No: {s_no}   |   💳 Ödeme: {pay}   |   📝 Not: {notes}")

        total_val = float(sale.get('total_amount') or 0.0)
        self.lbl_total.setText(f"{total_val:,.2f} ₺")

        self.table.setRowCount(len(items))
        total_qty = 0.0
        for r_idx, itm in enumerate(items):
            # 0. Sırano
            no_item = QTableWidgetItem(str(r_idx + 1))
            no_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r_idx, 0, no_item)

            # 1. Ürün Adı
            p_name = itm.get('product_name') or '-'
            p_item = QTableWidgetItem(p_name)
            p_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(r_idx, 1, p_item)

            # 2. Kategori
            c_item = QTableWidgetItem(itm.get('category') or 'Unlu Mamül')
            c_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r_idx, 2, c_item)

            # 3. Miktar
            qty = float(itm.get('quantity') or 0.0)
            total_qty += qty
            q_item = QTableWidgetItem(f"{qty:,.2f}")
            q_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r_idx, 3, q_item)

            # 4. Birim
            u_item = QTableWidgetItem(itm.get('unit') or 'Adet')
            u_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r_idx, 4, u_item)

            # 5. Birim Fiyat
            p_val = float(itm.get('unit_price') or 0.0)
            pr_item = QTableWidgetItem(f"{p_val:,.2f} ₺")
            pr_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r_idx, 5, pr_item)

            # 6. Toplam Tutar
            tot_line = float(itm.get('total_amount') or (qty * p_val))
            tot_item = QTableWidgetItem(f"{tot_line:,.2f} ₺")
            tot_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            tot_item.setForeground(QColor("#10b981"))
            tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r_idx, 6, tot_item)

        self.lbl_summary.setText(f"Toplam {len(items)} Kalem   |   Toplam Miktar: {total_qty:,.1f}")

    def edit_record(self):
        dlg = ExternalSaleEntryDialog(parent=self.parent(), sale_id=self.sale_id, user=self.user, branch_id=self.branch_id)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()
            if self.parent() and hasattr(self.parent(), 'load_all_data'):
                self.parent().load_all_data()

    def delete_record(self):
        reply = QMessageBox.question(
            self, "Onay",
            "Bu toptan satışı ve içerisindeki tüm ürün kalemlerini silmek istediğinize emin misiniz?\n"
            "İmalathane mamul stoğu ve kasa/banka gelir kayıtları otomatik olarak geri alınacaktır.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = production_service.delete_external_sale(self.sale_id)
            if ok:
                QMessageBox.information(self, "Başarılı", msg)
                if self.parent() and hasattr(self.parent(), 'load_all_data'):
                    self.parent().load_all_data()
                self.accept()
            else:
                QMessageBox.critical(self, "Hata", msg)


class ExternalSaleEntryDialog(QDialog):
    """Dış Müşterilere Toptan Satış Girişi veya Düzenleme Penceresi (Sınırsız Çoklu Kalem Destekli)"""

    def __init__(self, parent=None, sale_id: int = None, user: User = None, branch_id: int = None):
        super().__init__(parent)
        self.sale_id = sale_id
        self.user = user
        self.branch_id = branch_id

        self.setWindowTitle("🛒 Yeni Dış Müşteri Satışı (Çoklu Ürün)" if not sale_id else "✏️ Satış Kaydını Düzenle")
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
            QLineEdit, QDateEdit, QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10pt;
            }}
            QLineEdit:focus, QDateEdit:focus, QComboBox:focus {{
                border-color: {AppStyles.SUCCESS};
            }}

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

            QTableWidget QLineEdit {{
                background-color: #1e1e24;
                color: #ffffff;
                border: 1px solid #3a3a44;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 10pt;
            }}
            QTableWidget QLineEdit:focus {{
                border: 1px solid {AppStyles.SUCCESS};
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
                border: 1px solid {AppStyles.SUCCESS};
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
                border: 1px solid {AppStyles.SUCCESS};
                background-color: #242430;
            }}
        """)
        self.popular_items = self._get_production_items()
        self.init_ui()
        self.load_customers_autocomplete()
        if self.sale_id:
            self.load_data()
        else:
            self.add_item_row()

    def _get_production_items(self) -> List[str]:
        items = [
            "Somun Ekmek (200 gr)", "Kepekli Ekmek", "Tam Buğday Ekmeği", "Çavdar Ekmeği",
            "Köy Ekmeği", "Trabzon Ekmeği", "Baget Ekmek", "Sokak Simidi", "Kandil Simidi",
            "Sade Poğaça", "Peynirli Poğaça", "Zeytinli Açma", "Kaşarlı Açma", "Boyoz",
            "Su Böreği (Tepsi)", "Kıymalı Kol Böreği", "Peynirli Kol Böreği", "Baklava (Tepsi)",
            "Kuru Pasta (Tuzlu)", "Kuru Pasta (Tatlı)", "Yaş Pasta (No:1)", "Yaş Pasta (No:2)"
        ]
        try:
            prods = production_service.get_productions()[:30]
            for p in prods:
                p_name = p.get('product_name')
                if p_name and p_name not in items:
                    items.insert(0, p_name)
        except Exception:
            pass
        return items

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 24, 20)

        # Başlık
        title = QLabel("🛒 " + ("Yeni Dış Müşteri Satışı (Çoklu Ürün)" if not self.sale_id else "Satış Kaydını Düzenle"))
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.SUCCESS};")
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

        # Satır 1: Müşteri / Firma Adı, Satış No, Satış Tarihi, Tahsilat Şekli
        row1 = QHBoxLayout()
        row1.setSpacing(14)

        v_cust = QVBoxLayout()
        v_cust.setSpacing(4)
        v_cust.addWidget(QLabel("Müşteri / Firma Adı *"))
        self.customer_input = QLineEdit()
        self.customer_input.setPlaceholderText("Örn: Çorlu Grand Otel, Bereket Market, Güneş Kafe...")
        v_cust.addWidget(self.customer_input)
        row1.addLayout(v_cust, 4)

        v_no = QVBoxLayout()
        v_no.setSpacing(4)
        v_no.addWidget(QLabel("Satış No"))
        self.sale_no_input = QLineEdit()
        self.sale_no_input.setText(f"SAT-{datetime.now().strftime('%y%m%d')}-{int(datetime.now().timestamp()) % 10000:04d}")
        self.sale_no_input.setFixedWidth(170)
        v_no.addWidget(self.sale_no_input)
        row1.addLayout(v_no, 0)

        v_date = QVBoxLayout()
        v_date.setSpacing(4)
        v_date.addWidget(QLabel("Satış Tarihi"))
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setFixedWidth(145)
        v_date.addWidget(self.date_input)
        row1.addLayout(v_date, 0)

        v_pay = QVBoxLayout()
        v_pay.setSpacing(4)
        v_pay.addWidget(QLabel("Tahsilat Şekli"))
        self.payment_method_cb = QComboBox()
        self.payment_method_cb.addItems(["Nakit", "Kredi Kartı", "Havale / EFT", "Açık Hesap (Cari)"])
        self.payment_method_cb.setFixedWidth(165)
        v_pay.addWidget(self.payment_method_cb)
        row1.addLayout(v_pay, 0)

        f_lay.addLayout(row1)

        # Satır 2: Açıklama / İrsaliye
        v_notes = QVBoxLayout()
        v_notes.setSpacing(4)
        v_notes.addWidget(QLabel("İrsaliye / Fatura No veya Sipariş Notu"))
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("İrsaliye no, fatura, sipariş no veya teslimat detayları...")
        v_notes.addWidget(self.notes_input)
        f_lay.addLayout(v_notes)

        layout.addWidget(form_frame)

        # Kalemler Tablo Başlığı ve Butonu
        items_header = QHBoxLayout()
        items_lbl = QLabel("📋 Satış Kalemleri (Dış müşteriye satılan tüm ürünler):")
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
            "Ürün Adı *", "Kategori", "Miktar *", "Birim", "Birim Satış Fiyatı (₺)", "Tutar (₺)", "Sil"
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
        self.items_table.setColumnWidth(4, 150)
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
        self.btn_save = QPushButton("💾 Satışı Onayla & Kaydet")
        self.btn_save.setStyleSheet(AppStyles.btn_primary())
        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setStyleSheet(AppStyles.btn_secondary())

        btn_box.addButton(self.btn_save, QDialogButtonBox.AcceptRole)
        btn_box.addButton(self.btn_cancel, QDialogButtonBox.RejectRole)
        btn_box.accepted.connect(self.save)
        btn_box.rejected.connect(self.reject)
        bottom_bar.addWidget(btn_box)

        layout.addLayout(bottom_bar)

    def load_customers_autocomplete(self):
        try:
            cust_set = set()
            sql = "SELECT title FROM Customers WHERE (branch_id = %s OR branch_id IS NULL) AND is_active = TRUE ORDER BY title ASC"
            rows_c = db.fetch_all(sql, (self.branch_id,))
            for r in rows_c or []:
                if r.get('title'):
                    cust_set.add(r['title'])
            rows_e = db.fetch_all("SELECT DISTINCT customer_name FROM ExternalSales WHERE customer_name IS NOT NULL AND customer_name != ''")
            for r in rows_e or []:
                cust_set.add(r['customer_name'])
            completer = QCompleter(sorted(list(cust_set)), self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            self.customer_input.setCompleter(completer)
        except Exception as e:
            logger.warning(f"Müşteri otomatik tamamlama yüklenemedi: {e}")

    def add_item_row(self, name="", category="Unlu Mamül", qty=100.0, unit="Adet", price=12.5):
        row_idx = self.items_table.rowCount()
        self.items_table.insertRow(row_idx)

        # 0. Ürün Adı
        name_edit = QLineEdit(name)
        name_edit.setPlaceholderText("Örn: Somun Ekmek (200 gr), Sokak Simidi...")
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
        completer = QCompleter(self.popular_items, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        name_edit.setCompleter(completer)
        self.items_table.setCellWidget(row_idx, 0, name_edit)

        # 1. Kategori
        cat_combo = QComboBox()
        cat_combo.addItems(["Ekmek", "Simit & Poğaça", "Unlu Mamül", "Tatlı", "Pasta", "Diğer"])
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
        cat_combo.setCurrentText(category or "Unlu Mamül")
        self.items_table.setCellWidget(row_idx, 1, cat_combo)

        # 2. Miktar
        qty_spin = QDoubleSpinBox()
        qty_spin.setRange(0.01, 999999.0)
        qty_spin.setDecimals(2)
        qty_spin.setValue(float(qty or 100.0))
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
        unit_combo.addItems(["Adet", "Kg", "Tepsi", "Koli", "Porsiyon", "Paket"])
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
        unit_combo.setCurrentText(unit or "Adet")
        self.items_table.setCellWidget(row_idx, 3, unit_combo)

        # 4. Birim Satış Fiyatı
        price_spin = QDoubleSpinBox()
        price_spin.setRange(0.0, 999999.0)
        price_spin.setDecimals(2)
        price_spin.setValue(float(price or 12.5))
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
        tot_val = (float(qty or 100.0)) * (float(price or 12.5))
        lbl_tot = QLabel(f"{tot_val:,.2f} ₺")
        lbl_tot.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_tot.setStyleSheet("font-size: 10pt; font-weight: bold; color: #10b981; padding-right: 8px;")
        self.items_table.setCellWidget(row_idx, 5, lbl_tot)

        # 6. Sil Butonu (Hücre ortalı kapsayıcı ile sağ kenardan asla kesilmez)
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
            sale, items = production_service.get_external_sale_details(self.sale_id)
            if not sale:
                return

            self.customer_input.setText(sale.get('customer_name') or "")

            if sale.get('sale_date'):
                d = sale['sale_date']
                if isinstance(d, str):
                    d = datetime.strptime(d[:10], "%Y-%m-%d").date()
                self.date_input.setDate(QDate(d.year, d.month, d.day))

            self.sale_no_input.setText(sale.get('sale_no') or "")
            self.payment_method_cb.setCurrentText(sale.get('payment_method') or "Nakit")
            self.notes_input.setText(sale.get('notes') or "")

            self.items_table.setRowCount(0)
            if items:
                for itm in items:
                    self.add_item_row(
                        name=itm.get('product_name') or "",
                        category=itm.get('category') or "Unlu Mamül",
                        qty=float(itm.get('quantity') or 1.0),
                        unit=itm.get('unit') or "Adet",
                        price=float(itm.get('unit_price') or 0.0)
                    )
            else:
                self.add_item_row()

            self._recalc_all_totals()
        except Exception as e:
            logger.error(f"Satış düzenleme verisi yüklenirken hata: {e}")

    def save(self):
        c_name = self.customer_input.text().strip()
        if not c_name:
            QMessageBox.warning(self, "Uyarı", "Lütfen müşteri / firma adını girin.")
            self.customer_input.setFocus()
            return

        row_count = self.items_table.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen en az bir satış kalemi ekleyin.")
            return

        items = []
        for r in range(row_count):
            name_widget = self.items_table.cellWidget(r, 0)
            cat_widget = self.items_table.cellWidget(r, 1)
            qty_widget = self.items_table.cellWidget(r, 2)
            unit_widget = self.items_table.cellWidget(r, 3)
            price_widget = self.items_table.cellWidget(r, 4)

            name = name_widget.text().strip() if isinstance(name_widget, QLineEdit) else ""
            if not name:
                QMessageBox.warning(self, "Uyarı", f"{r+1}. satırdaki ürün adını girin.")
                if name_widget:
                    name_widget.setFocus()
                return

            cat = cat_widget.currentText().strip() if isinstance(cat_widget, QComboBox) else "Unlu Mamül"
            qty = qty_widget.value() if isinstance(qty_widget, QDoubleSpinBox) else 1.0
            unit = unit_widget.currentText().strip() if isinstance(unit_widget, QComboBox) else "Adet"
            price = price_widget.value() if isinstance(price_widget, QDoubleSpinBox) else 0.0
            line_tot = qty * price

            items.append({
                'product_name': name,
                'category': cat,
                'quantity': qty,
                'unit': unit,
                'unit_price': price,
                'total_amount': line_tot
            })

        data = {
            'customer_name': c_name,
            'sale_date': self.date_input.date().toString('yyyy-MM-dd'),
            'sale_no': self.sale_no_input.text().strip(),
            'payment_method': self.payment_method_cb.currentText(),
            'notes': self.notes_input.text().strip()
        }

        user_id = self.user.id if self.user else None
        if self.sale_id:
            ok, msg = production_service.update_multi_external_sale(self.sale_id, data, items, user_id)
        else:
            ok, msg, _ = production_service.add_multi_external_sale(data, items, user_id)

        if ok:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)


# Geriye dönük uyumluluk takma adı
AddExternalSaleDialog = ExternalSaleEntryDialog


# ==================== ANA İMALATHANE SAYFASI ====================

class ProductionHubPage(QWidget):
    """
    Fırın İmalathane & Üretim Dağıtım Merkezi
    3 Perakende Şube (Armada, Çobançeşme, Rumeli) ve Dış Satış Yönetimi
    """

    def __init__(self, user: User, branch_id: int = None, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window
        self._shipment_mode = "daily"
        try:
            production_service.ensure_tables()
        except Exception as e:
            logger.warning(f"ProductionHubPage ensure_tables uyarısı: {e}")
        self.notifications = []
        try:
            self.notifications = self.fetch_notifications()
        except Exception:
            pass

        self.init_ui()
        self.load_all_data()

    def init_ui(self):
        self.setObjectName("ProductionHubPage")
        self.setStyleSheet(f"#ProductionHubPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 1. ÜST BAŞLIK VE HIZLI EYLEMLER
        header = self.create_header()
        layout.addWidget(header)

        # 2. KPI ÖZET KARTLARI
        kpi_cards = self.create_kpi_cards()
        layout.addWidget(kpi_cards)

        # 3. SEKMELER
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

        # Sekme 1: Fırın Üretimi & Mamul Stoğu
        self.production_tab = self.create_production_tab()
        self.tabs.addTab(self.production_tab, "🥖 Günlük Fırın Üretimi & Stok")

        # Sekme 2: 3 Şubeye Dağıtım / Sevkiyat
        self.shipments_tab = self.create_shipments_tab()
        self.tabs.addTab(self.shipments_tab, "🚚 3 Şubeye Sevkiyat (İç Dağıtım)")

        # Sekme 3: Dış Müşterilere Toptan Satış
        self.sales_tab = self.create_sales_tab()
        self.tabs.addTab(self.sales_tab, "🛒 Dış Müşterilere Satış (Toptan)")

        # Sekme 4: Fırın Günlük Hammadde Stoğu
        self.raw_tab = self.create_raw_materials_tab()
        self.tabs.addTab(self.raw_tab, "🌾 Günlük İmalat Hammadde & Sarfiyatı")

        layout.addWidget(self.tabs)

    def create_header(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Başlık & Rozet
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel("🏭 Fırın İmalathane & Üretim Dağıtım Merkezi")
        title.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        title_box.addWidget(title)

        subtitle = QLabel("3 Perakende Şube (Armada, Çobançeşme, Rumeli) ve Dış Toptan Müşteri Entegre Paneli")
        subtitle.setStyleSheet(f"font-size: 9.5pt; color: {AppStyles.TEXT_SECONDARY};")
        title_box.addWidget(subtitle)

        layout.addLayout(title_box)
        layout.addStretch()

        # Tarih Seçici
        date_box = QHBoxLayout()
        date_box.setSpacing(6)
        date_lbl = QLabel("Tarih:")
        date_lbl.setStyleSheet(f"color: {AppStyles.TEXT_MUTED}; font-size: 9.5pt; font-weight: bold;")
        date_box.addWidget(date_lbl)

        self.filter_date = QDateEdit(QDate.currentDate())
        self.filter_date.setCalendarPopup(True)
        self.filter_date.setStyleSheet(f"""
            QDateEdit {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 6px 12px;
                font-weight: bold;
            }}
        """)
        self.filter_date.dateChanged.connect(self.load_all_data)
        date_box.addWidget(self.filter_date)
        layout.addLayout(date_box)

        # 🔔 BİLDİRİMLER BUTONU
        notif_cnt = len(self.notifications) if hasattr(self, 'notifications') else 0
        btn_txt = f"🔔  {notif_cnt} Bildirim" if notif_cnt > 0 else "🔔  Bildirimler"
        self.notif_btn = QPushButton(btn_txt)
        self.notif_btn.setCursor(Qt.PointingHandCursor)
        self.notif_btn.clicked.connect(self.open_notifications_dialog)
        self._update_notif_btn_style(notif_cnt)
        layout.addWidget(self.notif_btn)


        # Yenile Butonu
        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.load_all_data)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 9px 18px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                color: {AppStyles.TEXT_PRIMARY};
                border-color: {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """)
        layout.addWidget(refresh_btn)

        return header

    def _update_notif_btn_style(self, notif_cnt: int):
        """Bildirim buton metni ve renk stilini günceller"""
        if not hasattr(self, 'notif_btn') or self.notif_btn is None:
            return
        btn_txt = f"🔔  {notif_cnt} Bildirim" if notif_cnt > 0 else "🔔  Bildirimler"
        self.notif_btn.setText(btn_txt)
        if notif_cnt > 0:
            self.notif_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.RED}25;
                    color: {AppStyles.RED};
                    border: 1px solid {AppStyles.RED}80;
                    border-radius: 8px;
                    padding: 9px 18px;
                    font-weight: bold;
                    font-size: 9.5pt;
                }}
                QPushButton:hover {{
                    background-color: {AppStyles.RED};
                    color: white;
                }}
            """)
        else:
            self.notif_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.BG_MEDIUM};
                    color: {AppStyles.TEXT_SECONDARY};
                    border: 1px solid {AppStyles.BORDER};
                    border-radius: 8px;
                    padding: 9px 18px;
                    font-weight: 600;
                    font-size: 9.5pt;
                }}
                QPushButton:hover {{
                    border-color: {AppStyles.PRIMARY};
                    color: {AppStyles.PRIMARY};
                }}
            """)

    def fetch_notifications(self) -> list:
        """İmalathane şubesi için yaklaşan ödemeleri ve personel maaş/avans bildirimlerini toplar"""
        notifications = []
        target_branch = self.branch_id or 4
        try:
            # 1. Yaklaşan Personel Maaşları ve Ödeme Planları (7 Gün)
            try:
                upcoming = payment_plan_service.get_upcoming_payments(branch_id=target_branch, days=7)
                for p in (upcoming or [])[:5]:
                    p_title = p.get('title') or 'Ödeme'
                    p_payee = p.get('payee_name') or '-'
                    p_amount = float(p.get('amount') or 0)
                    days_left = p.get('days_left', 0)
                    p_type = p.get('plan_type')
                    is_salary = (p_type == 'personel')

                    def click_plan():
                        self.go_to_payment_plans()

                    notifications.append({
                        'icon': "👤" if is_salary else "⏰",
                        'title': f"Yaklaşan Personel Maaşı — {p_payee}" if is_salary else "Yaklaşan Ödeme Planı Taksiti",
                        'desc': f"<b>{p_title}</b> ({p_payee}) ödemesine <b>{days_left} gün</b> kaldı! Tutar: <b>{p_amount:,.2f} ₺</b>",
                        'color': AppStyles.PRIMARY if is_salary else AppStyles.ORANGE,
                        'on_click': click_plan
                    })
            except Exception as e:
                logger.error(f"İmalathane yaklaşan ödeme bildirim hatası: {e}")

            # 2. Gecikmiş Personel Maaşları ve Ödeme Planları
            try:
                overdue = payment_plan_service.get_overdue_payments(branch_id=target_branch)
                for p in (overdue or [])[:4]:
                    p_title = p.get('title') or 'Ödeme'
                    p_payee = p.get('payee_name') or '-'
                    p_amount = float(p.get('amount') or 0)
                    p_type = p.get('plan_type')
                    days_overdue = int(p.get('days_overdue', 0) or 0)
                    is_salary = (p_type == 'personel')

                    def click_overdue_plan():
                        self.go_to_payment_plans()

                    notifications.append({
                        'icon': "🚨" if is_salary else "🔴",
                        'title': f"GECİKMİŞ PERSONEL MAAŞI — {p_payee}" if is_salary else f"Gecikmiş Ödeme — {p_title}",
                        'desc': f"<b>{p_title}</b> ({p_payee}) ödemesi <b>{days_overdue} gün</b> gecikmiştir! Tutar: <b>{p_amount:,.2f} ₺</b>",
                        'color': AppStyles.RED,
                        'on_click': click_overdue_plan
                    })
            except Exception as e:
                logger.error(f"İmalathane gecikmiş ödeme bildirim hatası: {e}")

            # 3. Açık Personel Avansları
            try:
                open_advances = db.fetch_all("""
                    SELECT el.id, el.amount, el.remaining_amount, e.full_name AS employee_name
                    FROM EmployeeLedger el
                    JOIN Employees e ON e.id = el.employee_id
                    WHERE e.branch_id = %s AND el.entry_type = 'avans' 
                      AND el.remaining_amount > 0 AND (el.is_closed = 0 OR el.is_closed IS NULL)
                    ORDER BY el.entry_date DESC
                    LIMIT 3
                """, (target_branch,))
                for adv in (open_advances or []):
                    emp_name = adv.get('employee_name') or 'Personel'
                    rem = float(adv.get('remaining_amount') or 0)

                    def click_adv():
                        self.go_to_payment_plans()

                    notifications.append({
                        'icon': "💸",
                        'title': f"Açık Personel Avansı — {emp_name}",
                        'desc': f"<b>{emp_name}</b> üzerinde <b>{rem:,.2f} ₺</b> açık avans bakiyesi bulunmaktadır.",
                        'color': AppStyles.PURPLE,
                        'on_click': click_adv
                    })
            except Exception as e:
                logger.error(f"İmalathane açık avans bildirim hatası: {e}")

            # 4. Maaş Günü Yaklaşan Personeller (salary_day)
            try:
                today = datetime.now().date()
                employees = db.fetch_all("""
                    SELECT id, full_name, monthly_salary, salary_day
                    FROM Employees
                    WHERE branch_id = %s AND is_active = TRUE AND salary_day IS NOT NULL
                """, (target_branch,))
                for emp in (employees or []):
                    sal_day = int(emp.get('salary_day') or 1)
                    sal_amount = float(emp.get('monthly_salary') or 0)
                    emp_name = emp.get('full_name') or 'Personel'
                    try:
                        sal_date = today.replace(day=sal_day)
                    except Exception:
                        sal_date = today.replace(day=28)
                    days_diff = (sal_date - today).days
                    if 0 <= days_diff <= 3:
                        def click_sal_emp():
                            self.go_to_payment_plans()

                        notifications.append({
                            'icon': "📅",
                            'title': f"Maaş Günü Yaklaşıyor — {emp_name}",
                            'desc': f"<b>{emp_name}</b> için aylık maaş ödeme günü ({sal_day}. gün). Tutar: <b>{sal_amount:,.2f} ₺</b> ({days_diff} gün kaldı).",
                            'color': AppStyles.PRIMARY,
                            'on_click': click_sal_emp
                        })
            except Exception as e:
                logger.error(f"İmalathane maaş günü bildirim hatası: {e}")

            # 5. Kritik Hammadde Stoğu Uyarısı
            try:
                p_branch_id = production_service.get_production_branch_id()
                low_raw = db.fetch_all("""
                    SELECT name, stock_quantity, critical_stock, unit 
                    FROM Products 
                    WHERE (branch_id = %s OR LOWER(category) IN ('hammadde', 'fırın hammadde', 'un', 'maya'))
                      AND is_active = TRUE
                      AND (stock_quantity <= 0 OR stock_quantity <= critical_stock OR stock_quantity <= 10)
                    ORDER BY stock_quantity ASC
                    LIMIT 3
                """, (p_branch_id,))
                for rm in (low_raw or []):
                    m_name = rm.get('name') or 'Hammadde'
                    rem_stk = float(rm.get('stock_quantity') or 0)
                    m_unit = rm.get('unit') or 'Kg'

                    def click_raw():
                        if hasattr(self, 'tabs'):
                            self.tabs.setCurrentIndex(3)

                    notifications.append({
                        'icon': "🌾",
                        'title': f"Kritik Hammadde Stoğu — {m_name}",
                        'desc': f"<b>{m_name}</b> stoğu kritik seviyede: <b>{rem_stk:g} {m_unit}</b> kaldı!",
                        'color': AppStyles.WARNING,
                        'on_click': click_raw
                    })
            except Exception as e:
                logger.error(f"Hammadde bildirim hatası: {e}")

        except Exception as e:
            logger.error(f"İmalathane bildirim toplama hatası: {e}")

        return notifications

    def open_notifications_dialog(self):
        """Bildirimler & Hatırlatmalar modalını açar"""
        try:
            self.notifications = self.fetch_notifications()
            dlg = NotificationsDialog(self.notifications, self)
            dlg.exec_()
            self._update_notif_btn_style(len(self.notifications))
        except Exception as e:
            logger.error(f"Bildirim penceresi açılırken hata: {e}")

    def go_to_payment_plans(self):
        """Personel ve ödeme planları sayfasına yönlendir"""
        if self.main_window and hasattr(self.main_window, 'navigate_to'):
            self.main_window.navigate_to("payment_plans")

    def create_kpi_cards(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.kpi_labels = {}

        cards_data = [
            ("produced", "🥖", "Günün Toplam Üretimi", "0 Adet", AppStyles.PRIMARY),
            ("shipped", "🚚", "3 Şubeye Sevk Edilen", "0 Adet", AppStyles.CYAN),
            ("external", "🛒", "Dış Müşterilere Satış", "0 Adet", AppStyles.SUCCESS),
            ("remaining", "📦", "İmalathane Kalan Stok", "0 Adet", AppStyles.WARNING),
            ("value", "💰", "Toplam Üretim / Sevk Hacmi", "0.00 ₺", AppStyles.PURPLE),
        ]

        for key, icon, title, initial_val, color in cards_data:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {AppStyles.BG_MEDIUM};
                    border: 1px solid {AppStyles.BORDER};
                    border-radius: 10px;
                    padding: 10px 14px;
                }}
            """)
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(0, 0, 0, 0)
            c_layout.setSpacing(4)

            top_h = QHBoxLayout()
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet(f"color: {AppStyles.TEXT_MUTED}; font-size: 8.5pt; font-weight: 600;")
            lbl_icon = QLabel(icon)
            lbl_icon.setStyleSheet("font-size: 13pt;")
            top_h.addWidget(lbl_icon)
            top_h.addWidget(lbl_title)
            top_h.addStretch()
            c_layout.addLayout(top_h)

            val_lbl = QLabel(initial_val)
            val_lbl.setStyleSheet(f"color: {color}; font-size: 13.5pt; font-weight: bold;")
            c_layout.addWidget(val_lbl)

            self.kpi_labels[key] = val_lbl
            layout.addWidget(card)

        return container

    # ==================== SEKME 1: FIRIN ÜRETİMİ ====================

    def create_production_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        # Filtre ve Eylem Barı
        bar = QHBoxLayout()
        bar.setSpacing(10)

        cat_lbl = QLabel("Kategori:")
        cat_lbl.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-weight: bold;")
        bar.addWidget(cat_lbl)

        self.prod_cat_filter = QComboBox()
        self.prod_cat_filter.addItems(["Tümü", "Ekmek", "Simit & Poğaça", "Unlu Mamül", "Tatlı", "Pasta", "Diğer"])
        self.prod_cat_filter.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
            }}
        """)
        self.prod_cat_filter.currentTextChanged.connect(self.load_productions_table)
        bar.addWidget(self.prod_cat_filter)

        bar.addStretch()

        add_btn = QPushButton("➕ Yeni Üretim Partisi Ekle")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self.open_add_production)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.PRIMARY};
                color: white;
                border-radius: 6px;
                font-weight: bold;
                padding: 7px 16px;
            }}
        """)
        bar.addWidget(add_btn)

        layout.addLayout(bar)

        # Tablo
        self.prod_table = QTableWidget()
        self.prod_table.setColumnCount(10)
        self.prod_table.setHorizontalHeaderLabels([
            "ID", "Tarih", "Kategori", "Ürün Adı", "Üretilen",
            "Sevk Edilen", "Dış Satılan", "Kalan Stok", "Birim Fiyat", "İşlem"
        ])
        self.prod_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.prod_table.horizontalHeader().setSectionResizeMode(9, QHeaderView.Fixed)
        self.prod_table.setColumnWidth(9, 85)
        self.prod_table.verticalHeader().setDefaultSectionSize(46)
        self.prod_table.verticalHeader().setVisible(False)
        self.prod_table.setStyleSheet(self._table_style())
        layout.addWidget(self.prod_table)

        return widget

    # ==================== SEKME 2: 3 ŞUBEYE SEVKİYAT ====================

    def create_shipments_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        # 1. DÖNEM FİLTRE ÇUBUĞU (Günlük / Haftalık / Aylık / Yıllık)
        period_bar = self.create_shipments_period_bar()
        layout.addWidget(period_bar)

        # 2. Şube Özet Kartları (Armada, Çobançeşme, Rumeli)
        self.branch_cards_layout = QHBoxLayout()
        self.branch_cards_layout.setSpacing(12)
        self.branch_stat_widgets = {}

        branches = production_service.get_retail_branches()
        colors = [AppStyles.PRIMARY, AppStyles.CYAN, AppStyles.PURPLE, AppStyles.YELLOW]
        for idx, b in enumerate(branches):
            accent = colors[idx % len(colors)]
            b_card = QFrame()
            b_card.setStyleSheet(f"""
                QFrame {{
                    background-color: {AppStyles.BG_DARK};
                    border: 1px solid {AppStyles.BORDER};
                    border-top: 3px solid {accent};
                    border-radius: 8px;
                    padding: 10px 14px;
                }}
                QFrame:hover {{
                    border-color: {accent};
                }}
            """)
            bc_layout = QVBoxLayout(b_card)
            bc_layout.setContentsMargins(0, 0, 0, 0)
            bc_layout.setSpacing(4)

            b_title = b['name'] if "şube" in b['name'].lower() else f"{b['name']} Şubesi"
            b_name = QLabel(f"🏢 {b_title}")
            b_name.setStyleSheet(f"color: {accent}; font-size: 11pt; font-weight: bold;")
            bc_layout.addWidget(b_name)

            b_stat = QLabel("0 Adet | 0,00 ₺ Sevk")
            b_stat.setStyleSheet(f"color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; font-weight: 600;")
            bc_layout.addWidget(b_stat)

            self.branch_stat_widgets[b['name']] = b_stat
            self.branch_cards_layout.addWidget(b_card)

        layout.addLayout(self.branch_cards_layout)

        # 3. Şube Filtreleme ve Yeni Sevkiyat Aksiyonu
        bar = QHBoxLayout()
        bar.setSpacing(10)

        b_lbl = QLabel("Şube Filtrele:")
        b_lbl.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-weight: bold; font-size: 9.5pt;")
        bar.addWidget(b_lbl)

        self.ship_branch_filter = QComboBox()
        self.ship_branch_filter.addItem("Tüm Şubeler", None)
        for b in branches:
            self.ship_branch_filter.addItem(b['name'], b['id'])
        self.ship_branch_filter.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 500;
            }}
        """)
        self.ship_branch_filter.currentIndexChanged.connect(self.load_shipments_table)
        bar.addWidget(self.ship_branch_filter)

        bar.addStretch()

        add_ship_btn = QPushButton("🚚 Yeni Şube Sevkiyatı Yap")
        add_ship_btn.setCursor(Qt.PointingHandCursor)
        add_ship_btn.clicked.connect(self.open_add_shipment)
        add_ship_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.CYAN};
                color: black;
                border-radius: 6px;
                font-weight: bold;
                padding: 7px 16px;
            }}
            QPushButton:hover {{
                background-color: #38bdf8;
            }}
        """)
        bar.addWidget(add_ship_btn)

        layout.addLayout(bar)

        # 4. Sevkiyat Tablosu (Sadeleştirilmiş ve Konsolide)
        self.ship_table = QTableWidget()
        self.ship_table.setColumnCount(9)
        self.ship_table.setHorizontalHeaderLabels([
            "Sevk No", "Tarih", "Hedef Şube", "Kalem Sayısı",
            "Toplam Miktar", "Toplam Tutar", "Durum", "Şoför / Not", "İşlemler"
        ])
        self.ship_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ship_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ship_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.ship_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.ship_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.ship_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.ship_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.ship_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed)
        self.ship_table.setColumnWidth(8, 165)
        self.ship_table.verticalHeader().setDefaultSectionSize(48)
        self.ship_table.verticalHeader().setVisible(False)
        self.ship_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ship_table.setStyleSheet(self._table_style())
        self.ship_table.cellDoubleClicked.connect(self.on_shipment_cell_clicked)
        self.ship_table.cellClicked.connect(self.on_shipment_cell_clicked)
        layout.addWidget(self.ship_table)

        return widget

    # ==================== SEKME 3: DIŞ SATIŞLAR ====================

    def create_sales_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        # Üst Bar
        bar = QHBoxLayout()
        desc = QLabel("Otel, Restoran, Market ve Kafelere yapılan toptan fırın satışları")
        desc.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9.5pt;")
        bar.addWidget(desc)
        bar.addStretch()

        add_sale_btn = QPushButton("🛒 Dış Müşteriye Satış Kaydet")
        add_sale_btn.setCursor(Qt.PointingHandCursor)
        add_sale_btn.clicked.connect(self.open_add_external_sale)
        add_sale_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.SUCCESS};
                color: white;
                border-radius: 6px;
                font-weight: bold;
                padding: 7px 16px;
            }}
        """)
        bar.addWidget(add_sale_btn)

        layout.addLayout(bar)

        # Tablo (Sadeleştirilmiş ve Konsolide)
        self.sales_table = QTableWidget()
        self.sales_table.setColumnCount(9)
        self.sales_table.setHorizontalHeaderLabels([
            "Satış No", "Tarih", "Müşteri / Firma", "Kalem Sayısı",
            "Toplam Miktar", "Toplam Tutar", "Tahsilat Şekli", "Açıklama / Not", "İşlemler"
        ])
        self.sales_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sales_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.sales_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.sales_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.sales_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.sales_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.sales_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.sales_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed)
        self.sales_table.setColumnWidth(8, 165)
        self.sales_table.verticalHeader().setDefaultSectionSize(48)
        self.sales_table.verticalHeader().setVisible(False)
        self.sales_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sales_table.setStyleSheet(self._table_style())
        self.sales_table.cellDoubleClicked.connect(self.on_sales_cell_clicked)
        self.sales_table.cellClicked.connect(self.on_sales_cell_clicked)
        layout.addWidget(self.sales_table)

        return widget

    # ==================== SEKME 4: HAMMADDE DEPOSU ====================

    def create_raw_materials_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        bar = QHBoxLayout()
        info_lbl = QLabel("🥖 Fırın imalathanesinde günlük üretim ihtiyacına göre kullanılan un, maya, tuz vb. sarfiyat stoğu. (Toptan ve fazlalık hammadde/ambalaj Merkez Depo'da tutulur)")
        info_lbl.setStyleSheet(f"color: {AppStyles.CYAN}; font-size: 9.5pt; font-weight: 500;")
        bar.addWidget(info_lbl)
        bar.addStretch()
        layout.addLayout(bar)

        self.raw_table = QTableWidget()
        self.raw_table.setColumnCount(6)
        self.raw_table.setHorizontalHeaderLabels([
            "Hammadde Adı", "Kategori", "Mevcut Stok", "Birim", "Birim Alış Fiyatı", "Durum"
        ])
        self.raw_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.raw_table.verticalHeader().setDefaultSectionSize(44)
        self.raw_table.verticalHeader().setVisible(False)
        self.raw_table.setStyleSheet(self._table_style())
        layout.addWidget(self.raw_table)

        return widget

    # ==================== VERİ YÜKLEME ====================

    def load_all_data(self):
        """Tüm sekmelerdeki ve KPI alanlarındaki verileri yeniler"""
        target_date = self.filter_date.date().toString('yyyy-MM-dd')

        # 1. KPI İstatistikleri
        stats = production_service.get_hub_stats(target_date)
        if "produced" in self.kpi_labels:
            self.kpi_labels["produced"].setText(f"{stats.get('total_produced', 0):,.0f} Adet")
            self.kpi_labels["shipped"].setText(f"{stats.get('total_shipped', 0):,.0f} Adet")
            self.kpi_labels["external"].setText(f"{stats.get('total_external_sold', 0):,.0f} Adet")
            self.kpi_labels["remaining"].setText(f"{stats.get('total_remaining', 0):,.0f} Adet")
            self.kpi_labels["value"].setText(f"{stats.get('grand_production_value', 0):,.2f} ₺")

        # Şube Sevkiyat Dağılım Kartları
        breakdown = stats.get('branch_breakdown', {})
        for b_name, b_val in breakdown.items():
            if b_name in self.branch_stat_widgets:
                self.branch_stat_widgets[b_name].setText(f"{b_val.get('qty', 0):,.0f} Adet | {b_val.get('total', 0):,.2f} ₺")

        # 2. Üretim Tablosu
        self.load_productions_table()

        # 3. Sevkiyat Tablosu
        self.load_shipments_table()

        # 4. Dış Satışlar Tablosu
        self.load_sales_table()

        # 5. Hammadde Tablosu
        self.load_raw_materials_table()

        # 6. Bildirimleri Yenile
        self.notifications = self.fetch_notifications()
        self._update_notif_btn_style(len(self.notifications))

    def load_productions_table(self):
        target_date = self.filter_date.date().toString('yyyy-MM-dd')
        cat = self.prod_cat_filter.currentText()
        records = production_service.get_productions(target_date=target_date, category=cat)

        self.prod_table.setRowCount(len(records))
        for row, r in enumerate(records):
            # ID
            self.prod_table.setItem(row, 0, QTableWidgetItem(str(r['id'])))
            # Tarih
            dt_str = r['production_date'].strftime('%d.%m.%Y') if hasattr(r['production_date'], 'strftime') else str(r['production_date'])
            self.prod_table.setItem(row, 1, QTableWidgetItem(dt_str))
            # Kategori
            self.prod_table.setItem(row, 2, QTableWidgetItem(r.get('category') or '-'))
            # Ürün Adı
            self.prod_table.setItem(row, 3, QTableWidgetItem(r.get('product_name') or '-'))
            # Üretilen
            unit = r.get('unit') or 'Adet'
            self.prod_table.setItem(row, 4, QTableWidgetItem(f"{float(r.get('quantity') or 0):,.1f} {unit}"))
            # Sevk Edilen
            self.prod_table.setItem(row, 5, QTableWidgetItem(f"{float(r.get('shipped_quantity') or 0):,.1f} {unit}"))
            # Dış Satılan
            self.prod_table.setItem(row, 6, QTableWidgetItem(f"{float(r.get('external_sold_quantity') or 0):,.1f} {unit}"))
            # Kalan Stok
            rem_item = QTableWidgetItem(f"{float(r.get('remaining_quantity') or 0):,.1f} {unit}")
            rem_item.setForeground(QColor(AppStyles.SUCCESS if float(r.get('remaining_quantity') or 0) > 0 else AppStyles.TEXT_MUTED))
            self.prod_table.setItem(row, 7, rem_item)
            # Birim Fiyat
            self.prod_table.setItem(row, 8, QTableWidgetItem(f"{float(r.get('sale_price') or 0):,.2f} ₺"))

            # Sil Butonu
            del_widget = QWidget()
            del_widget.setStyleSheet("background: transparent;")
            del_layout = QHBoxLayout(del_widget)
            del_layout.setContentsMargins(2, 2, 2, 2)
            del_layout.setAlignment(Qt.AlignCenter)

            del_btn = QPushButton("🗑️ Sil")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setFixedSize(68, 30)
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 9pt;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                }
            """)
            del_btn.clicked.connect(lambda _, pid=r['id']: self.delete_production(pid))
            del_layout.addWidget(del_btn)
            self.prod_table.setCellWidget(row, 9, del_widget)

    def delete_production(self, prod_id: int):
        reply = QMessageBox.question(
            self, "Onay", "Bu üretim kaydını silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = production_service.delete_production(prod_id)
            if ok:
                self.load_all_data()
            else:
                QMessageBox.critical(self, "Hata", msg)

    def create_shipments_period_bar(self) -> QFrame:
        """Sevkiyatlar için Günlük/Haftalık/Aylık/Yıllık/Tüm Dönemler seçim çubuğu"""
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 6px 12px;
            }}
        """)
        l = QHBoxLayout(bar)
        l.setContentsMargins(10, 6, 10, 6)
        l.setSpacing(8)

        lbl_mode = QLabel("Görünüm:")
        lbl_mode.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-weight: bold; font-size: 9.5pt;")
        l.addWidget(lbl_mode)

        self.btn_ship_daily = QPushButton("📅 Günlük")
        self.btn_ship_weekly = QPushButton("📆 Haftalık")
        self.btn_ship_monthly = QPushButton("🗓️ Aylık")
        self.btn_ship_yearly = QPushButton("📊 Yıllık")
        self.btn_ship_all = QPushButton("📋 Tüm Dönemler")

        for btn in (self.btn_ship_daily, self.btn_ship_weekly, self.btn_ship_monthly, self.btn_ship_yearly, self.btn_ship_all):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(30)

        self.btn_ship_daily.clicked.connect(lambda: self.set_shipment_mode("daily"))
        self.btn_ship_weekly.clicked.connect(lambda: self.set_shipment_mode("weekly"))
        self.btn_ship_monthly.clicked.connect(lambda: self.set_shipment_mode("monthly"))
        self.btn_ship_yearly.clicked.connect(lambda: self.set_shipment_mode("yearly"))
        self.btn_ship_all.clicked.connect(lambda: self.set_shipment_mode("all"))

        l.addWidget(self.btn_ship_daily)
        l.addWidget(self.btn_ship_weekly)
        l.addWidget(self.btn_ship_monthly)
        l.addWidget(self.btn_ship_yearly)
        l.addWidget(self.btn_ship_all)

        # Ayırıcı
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setFixedHeight(22)
        sep.setStyleSheet(f"background-color: {AppStyles.BORDER};")
        l.addWidget(sep)

        # Tarih Seçici ve Oklar
        prev_btn = QPushButton("◀")
        prev_btn.setFixedSize(28, 28)
        prev_btn.setCursor(Qt.PointingHandCursor)
        prev_btn.setStyleSheet(f"background-color: {AppStyles.BG_MEDIUM}; border: 1px solid {AppStyles.BORDER}; border-radius: 4px; color: {AppStyles.TEXT_PRIMARY};")
        prev_btn.clicked.connect(self.ship_prev_period)
        l.addWidget(prev_btn)

        self.ship_date_edit = QDateEdit()
        self.ship_date_edit.setCalendarPopup(True)
        self.ship_date_edit.setDate(QDate.currentDate())
        self.ship_date_edit.setDisplayFormat("dd MMMM yyyy dddd")
        self.ship_date_edit.setFixedHeight(28)
        self.ship_date_edit.setMinimumWidth(200)
        self.ship_date_edit.setStyleSheet(f"""
            QDateEdit {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: bold;
            }}
        """)
        self.ship_date_edit.dateChanged.connect(lambda: self.load_shipments_data())
        l.addWidget(self.ship_date_edit)

        today_btn = QPushButton("Bugün")
        today_btn.setFixedHeight(28)
        today_btn.setCursor(Qt.PointingHandCursor)
        today_btn.setStyleSheet(f"background-color: {AppStyles.BG_MEDIUM}; border: 1px solid {AppStyles.BORDER}; border-radius: 4px; color: {AppStyles.TEXT_PRIMARY}; padding: 0 10px;")
        today_btn.clicked.connect(lambda: self.ship_date_edit.setDate(QDate.currentDate()))
        l.addWidget(today_btn)

        next_btn = QPushButton("▶")
        next_btn.setFixedSize(28, 28)
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.setStyleSheet(f"background-color: {AppStyles.BG_MEDIUM}; border: 1px solid {AppStyles.BORDER}; border-radius: 4px; color: {AppStyles.TEXT_PRIMARY};")
        next_btn.clicked.connect(self.ship_next_period)
        l.addWidget(next_btn)

        l.addStretch()

        self.lbl_ship_period_title = QLabel("")
        self.lbl_ship_period_title.setStyleSheet(f"color: {AppStyles.CYAN}; font-weight: bold; font-size: 10pt;")
        l.addWidget(self.lbl_ship_period_title)

        self.lbl_ship_grand_stat = QLabel("")
        self.lbl_ship_grand_stat.setStyleSheet(f"""
            background-color: {AppStyles.BG_MEDIUM};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 6px;
            padding: 4px 10px;
            font-weight: bold;
            color: {AppStyles.GREEN};
            font-size: 9.5pt;
        """)
        l.addWidget(self.lbl_ship_grand_stat)

        return bar

    def set_shipment_mode(self, mode: str):
        """Sevkiyat görünüm modunu (günlük/haftalık/aylık/yıllık/tüm) değiştirir"""
        self._shipment_mode = mode
        active_style = f"background-color: {AppStyles.PRIMARY}; color: {AppStyles.TEXT_ON_PRIMARY}; font-weight: bold; border-radius: 6px; padding: 4px 14px;"
        passive_style = f"background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_SECONDARY}; border: 1px solid {AppStyles.BORDER}; border-radius: 6px; padding: 4px 14px;"

        if hasattr(self, 'btn_ship_daily'):
            self.btn_ship_daily.setStyleSheet(active_style if mode == "daily" else passive_style)
            self.btn_ship_weekly.setStyleSheet(active_style if mode == "weekly" else passive_style)
            self.btn_ship_monthly.setStyleSheet(active_style if mode == "monthly" else passive_style)
            self.btn_ship_yearly.setStyleSheet(active_style if mode == "yearly" else passive_style)
            self.btn_ship_all.setStyleSheet(active_style if mode == "all" else passive_style)

        if hasattr(self, 'ship_date_edit'):
            if mode == "yearly":
                self.ship_date_edit.setDisplayFormat("yyyy")
                self.ship_date_edit.setEnabled(True)
            elif mode == "monthly":
                self.ship_date_edit.setDisplayFormat("MMMM yyyy")
                self.ship_date_edit.setEnabled(True)
            elif mode == "weekly":
                self.ship_date_edit.setDisplayFormat("dd MMMM yyyy")
                self.ship_date_edit.setEnabled(True)
            elif mode == "all":
                self.ship_date_edit.setEnabled(False)
            else:
                self.ship_date_edit.setDisplayFormat("dd MMMM yyyy dddd")
                self.ship_date_edit.setEnabled(True)

        self.load_shipments_data()

    def ship_prev_period(self):
        cur_dt = self.ship_date_edit.date().toPyDate()
        if self._shipment_mode == "daily":
            new_dt = cur_dt - timedelta(days=1)
        elif self._shipment_mode == "weekly":
            new_dt = cur_dt - timedelta(days=7)
        elif self._shipment_mode == "monthly":
            m = cur_dt.month - 1
            y = cur_dt.year
            if m < 1:
                m = 12
                y -= 1
            new_dt = cur_dt.replace(year=y, month=m, day=1)
        elif self._shipment_mode == "yearly":
            try:
                new_dt = cur_dt.replace(year=cur_dt.year - 1)
            except ValueError:
                new_dt = cur_dt.replace(year=cur_dt.year - 1, day=28)
        else:
            return
        self.ship_date_edit.setDate(QDate(new_dt.year, new_dt.month, new_dt.day))

    def ship_next_period(self):
        cur_dt = self.ship_date_edit.date().toPyDate()
        if self._shipment_mode == "daily":
            new_dt = cur_dt + timedelta(days=1)
        elif self._shipment_mode == "weekly":
            new_dt = cur_dt + timedelta(days=7)
        elif self._shipment_mode == "monthly":
            m = cur_dt.month + 1
            y = cur_dt.year
            if m > 12:
                m = 1
                y += 1
            new_dt = cur_dt.replace(year=y, month=m, day=1)
        elif self._shipment_mode == "yearly":
            try:
                new_dt = cur_dt.replace(year=cur_dt.year + 1)
            except ValueError:
                new_dt = cur_dt.replace(year=cur_dt.year + 1, day=28)
        else:
            return
        self.ship_date_edit.setDate(QDate(new_dt.year, new_dt.month, new_dt.day))

    def load_shipments_data(self):
        """Seçili zaman dilimine (günlük/haftalık/aylık/yıllık/tüm) ve şubeye göre sevkiyatları yükler"""
        if not hasattr(self, 'ship_table') or not hasattr(self, 'ship_date_edit'):
            return

        target_date_str = self.ship_date_edit.date().toString("yyyy-MM-dd")
        target_branch_id = self.ship_branch_filter.currentData() if hasattr(self, 'ship_branch_filter') else None

        summary = production_service.get_shipments_summary(
            mode=self._shipment_mode,
            target_date=target_date_str
        )

        if hasattr(self, 'lbl_ship_period_title'):
            self.lbl_ship_period_title.setText(summary.get('title', ''))

        g_qty = summary.get('grand_total_qty', 0.0)
        g_amt = summary.get('grand_total_amount', 0.0)
        g_cnt = summary.get('grand_shipment_count', 0)
        if hasattr(self, 'lbl_ship_grand_stat'):
            self.lbl_ship_grand_stat.setText(f"Toplam: {g_qty:,.0f} Adet | {g_amt:,.2f} ₺ ({g_cnt} Sefer)")

        branches_data = {b['branch_name']: b for b in summary.get('branches', [])}
        for b_name, b_stat_lbl in self.branch_stat_widgets.items():
            b_info = branches_data.get(b_name, {})
            b_qty = b_info.get('total_qty', 0.0)
            b_amt = b_info.get('total_amount', 0.0)
            b_scnt = b_info.get('shipment_count', 0)
            b_stat_lbl.setText(f"{b_qty:,.0f} Adet | {b_amt:,.2f} ₺ ({b_scnt} Sefer)")

        start_d = summary.get('start_date')
        end_d = summary.get('end_date')

        if self._shipment_mode == "all":
            records = production_service.get_shipments(target_branch_id=target_branch_id)
        elif self._shipment_mode == "daily":
            records = production_service.get_shipments(target_branch_id=target_branch_id, target_date=target_date_str)
        else:
            records = production_service.get_shipments(target_branch_id=target_branch_id, start_date=start_d, end_date=end_d)

        self.current_shipments = records or []
        self._populate_shipments_table(records)

    def load_shipments_table(self):
        """Geriye dönük uyumluluk: sevkiyat yüklemesini load_shipments_data metoduna yönlendirir"""
        self.load_shipments_data()

    def _populate_shipments_table(self, records: List[Dict]):
        self.ship_table.setRowCount(len(records))
        for row, r in enumerate(records):
            # 0. Sevk No
            no_item = QTableWidgetItem(r.get('shipment_no') or f"SVK-{r['id']}")
            no_item.setTextAlignment(Qt.AlignCenter)
            self.ship_table.setItem(row, 0, no_item)

            # 1. Tarih
            dt_str = r['shipment_date'].strftime('%d.%m.%Y') if hasattr(r['shipment_date'], 'strftime') else str(r['shipment_date'])
            d_item = QTableWidgetItem(dt_str)
            d_item.setTextAlignment(Qt.AlignCenter)
            self.ship_table.setItem(row, 1, d_item)

            # 2. Hedef Şube
            b_item = QTableWidgetItem(f"🏢 {r.get('target_branch_name') or 'Şube'}")
            b_item.setForeground(QColor(AppStyles.CYAN))
            b_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.ship_table.setItem(row, 2, b_item)

            # 3. Kalem Sayısı Rozeti
            item_cnt = int(r.get('item_count') or 1)
            cnt_item = QTableWidgetItem(f"📦 {item_cnt} Kalem")
            cnt_item.setTextAlignment(Qt.AlignCenter)
            cnt_item.setForeground(QColor("#38bdf8"))
            cnt_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.ship_table.setItem(row, 3, cnt_item)

            # 4. Toplam Miktar
            tot_qty = float(r.get('calc_quantity') or r.get('quantity') or 0.0)
            unit = r.get('unit') or 'Adet'
            q_item = QTableWidgetItem(f"{tot_qty:,.1f} {unit}")
            q_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.ship_table.setItem(row, 4, q_item)

            # 5. Toplam Tutar
            tot_val = float(r.get('calc_total') or r.get('total_amount') or 0.0)
            tot_item = QTableWidgetItem(f"{tot_val:,.2f} ₺")
            tot_item.setForeground(QColor("#10b981"))
            tot_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.ship_table.setItem(row, 5, tot_item)

            # 6. Durum
            st_item = QTableWidgetItem(r.get('status') or 'Teslim Edildi')
            st_item.setTextAlignment(Qt.AlignCenter)
            self.ship_table.setItem(row, 6, st_item)

            # 7. Şoför / Not
            self.ship_table.setItem(row, 7, QTableWidgetItem(r.get('driver_notes') or '-'))

            # 8. İşlem Butonları (Detay 👁️, Sil 🗑️)
            action_widget = QWidget()
            a_lay = QHBoxLayout(action_widget)
            a_lay.setContentsMargins(2, 2, 2, 2)
            a_lay.setSpacing(8)
            a_lay.setAlignment(Qt.AlignCenter)

            btn_view = QPushButton("👁️ Detay")
            btn_view.setToolTip("Sevkiyat Detaylarını ve Kalemlerini Görüntüle")
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
            btn_view.clicked.connect(lambda ch, sid=r['id']: self.open_shipment_detail(sid))

            btn_del = QPushButton("🗑️ Sil")
            btn_del.setToolTip("Sevkiyatı ve Tüm Kalemlerini Sil")
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
            btn_del.clicked.connect(lambda ch, sid=r['id']: self.delete_shipment(sid))

            a_lay.addWidget(btn_view)
            a_lay.addWidget(btn_del)
            self.ship_table.setCellWidget(row, 8, action_widget)

    def on_shipment_cell_clicked(self, row: int, col: int):
        """Sevkiyat tablosu hücresine tıklandığında açılır detay penceresini açar"""
        if row < 0 or row >= len(getattr(self, 'current_shipments', [])):
            return
        if col == 8:
            return
        rec = self.current_shipments[row]
        self.open_shipment_detail(rec['id'])

    def open_shipment_detail(self, shipment_id: int):
        dlg = ShipmentDetailDialog(shipment_id=shipment_id, user=self.user, branch_id=self.branch_id, parent=self)
        dlg.exec_()

    def delete_shipment(self, shipment_id: int):
        reply = QMessageBox.question(
            self, "Onay",
            "Bu sevkiyatı ve tüm ürün kalemlerini silmek istediğinize emin misiniz?\n"
            "İmalathane ve şube ürün stokları otomatik olarak geri yüklenecektir.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = production_service.delete_shipment(shipment_id)
            if ok:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_all_data()
            else:
                QMessageBox.critical(self, "Hata", msg)

    def load_sales_table(self):
        target_date = self.filter_date.date().toString('yyyy-MM-dd')
        records = production_service.get_external_sales(target_date=target_date)
        self.current_sales = records or []

        self.sales_table.setRowCount(len(records))
        for row, r in enumerate(records):
            # 0. Satış No
            no_item = QTableWidgetItem(r.get('sale_no') or f"SAT-{r['id']}")
            no_item.setTextAlignment(Qt.AlignCenter)
            self.sales_table.setItem(row, 0, no_item)

            # 1. Tarih
            dt_str = r['sale_date'].strftime('%d.%m.%Y') if hasattr(r['sale_date'], 'strftime') else str(r['sale_date'])
            d_item = QTableWidgetItem(dt_str)
            d_item.setTextAlignment(Qt.AlignCenter)
            self.sales_table.setItem(row, 1, d_item)

            # 2. Müşteri / Firma
            cust_item = QTableWidgetItem(f"🤝 {r.get('customer_name') or '-'}")
            cust_item.setForeground(QColor(AppStyles.SUCCESS))
            cust_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.sales_table.setItem(row, 2, cust_item)

            # 3. Kalem Sayısı Rozeti
            item_cnt = int(r.get('item_count') or 1)
            cnt_item = QTableWidgetItem(f"📦 {item_cnt} Kalem")
            cnt_item.setTextAlignment(Qt.AlignCenter)
            cnt_item.setForeground(QColor("#38bdf8"))
            cnt_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.sales_table.setItem(row, 3, cnt_item)

            # 4. Toplam Miktar
            tot_qty = float(r.get('calc_quantity') or r.get('quantity') or 0.0)
            unit = r.get('unit') or 'Adet'
            q_item = QTableWidgetItem(f"{tot_qty:,.1f} {unit}")
            q_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.sales_table.setItem(row, 4, q_item)

            # 5. Toplam Tutar
            tot_val = float(r.get('calc_total') or r.get('total_amount') or 0.0)
            tot_item = QTableWidgetItem(f"{tot_val:,.2f} ₺")
            tot_item.setForeground(QColor("#10b981"))
            tot_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.sales_table.setItem(row, 5, tot_item)

            # 6. Tahsilat Şekli
            pay_item = QTableWidgetItem(f"💳 {r.get('payment_method') or 'Nakit'}")
            pay_item.setTextAlignment(Qt.AlignCenter)
            self.sales_table.setItem(row, 6, pay_item)

            # 7. Açıklama / Not
            self.sales_table.setItem(row, 7, QTableWidgetItem(r.get('notes') or '-'))

            # 8. İşlem Butonları (Detay 👁️, Sil 🗑️)
            action_widget = QWidget()
            a_lay = QHBoxLayout(action_widget)
            a_lay.setContentsMargins(2, 2, 2, 2)
            a_lay.setSpacing(8)
            a_lay.setAlignment(Qt.AlignCenter)

            btn_view = QPushButton("👁️ Detay")
            btn_view.setToolTip("Satış Detaylarını ve Kalemlerini Görüntüle")
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
            btn_view.clicked.connect(lambda ch, sid=r['id']: self.open_sales_detail(sid))

            btn_del = QPushButton("🗑️ Sil")
            btn_del.setToolTip("Satış Kaydını ve Kalemlerini Sil")
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
            btn_del.clicked.connect(lambda ch, sid=r['id']: self.delete_external_sale(sid))

            a_lay.addWidget(btn_view)
            a_lay.addWidget(btn_del)
            self.sales_table.setCellWidget(row, 8, action_widget)

    def on_sales_cell_clicked(self, row: int, col: int):
        """Satış tablosu hücresine tıklandığında açılır detay penceresini açar"""
        if row < 0 or row >= len(getattr(self, 'current_sales', [])):
            return
        if col == 8:
            return
        rec = self.current_sales[row]
        self.open_sales_detail(rec['id'])

    def open_sales_detail(self, sale_id: int):
        dlg = ExternalSaleDetailDialog(sale_id=sale_id, user=self.user, branch_id=self.branch_id, parent=self)
        dlg.exec_()

    def delete_external_sale(self, sale_id: int):
        reply = QMessageBox.question(
            self, "Onay",
            "Bu dış satışı ve tüm ürün kalemlerini silmek istediğinize emin misiniz?\n"
            "İmalathane üretim stoğu ve kasa/banka gelir kayıtları otomatik olarak geri alınacaktır.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = production_service.delete_external_sale(sale_id)
            if ok:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_all_data()
            else:
                QMessageBox.critical(self, "Hata", msg)

    def load_raw_materials_table(self):
        """Hammadde deposundaki un, maya, susam gibi malzemeleri listeler"""
        try:
            # WarehouseProducts veya Products'tan hammadde kayıtlarını al
            p_branch_id = production_service.get_production_branch_id()
            rows = db.fetch_all("""
                SELECT name, category, stock_quantity, unit, purchase_price 
                FROM Products 
                WHERE branch_id = %s OR LOWER(category) IN ('hammadde', 'fırın hammadde', 'un', 'maya')
                ORDER BY name ASC
            """, (p_branch_id,))

            if not rows:
                self.raw_table.setRowCount(0)
                return

            self.raw_table.setRowCount(len(rows))
            for row, r in enumerate(rows):
                self.raw_table.setItem(row, 0, QTableWidgetItem(r.get('name') or '-'))
                self.raw_table.setItem(row, 1, QTableWidgetItem(r.get('category') or 'Hammadde'))
                qty = float(r.get('stock_quantity') or 0)
                self.raw_table.setItem(row, 2, QTableWidgetItem(f"{qty:,.1f}"))
                self.raw_table.setItem(row, 3, QTableWidgetItem(r.get('unit') or 'Kg'))
                self.raw_table.setItem(row, 4, QTableWidgetItem(f"{float(r.get('purchase_price') or 0):,.2f} ₺"))
                status_item = QTableWidgetItem("🟢 Yeterli" if qty > 50 else "🟡 Azaldı")
                status_item.setForeground(QColor(AppStyles.SUCCESS if qty > 50 else AppStyles.WARNING))
                self.raw_table.setItem(row, 5, status_item)
        except Exception as e:
            logger.error(f"load_raw_materials_table hatası: {e}")

    # ==================== EYLEM METOTLARI ====================

    def open_add_production(self):
        dlg = AddProductionDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_all_data()

    def open_add_shipment(self, shipment_id: int = None):
        dlg = ShipmentEntryDialog(parent=self, shipment_id=shipment_id, user=self.user, branch_id=self.branch_id)
        if dlg.exec_() == QDialog.Accepted:
            self.load_all_data()

    def open_add_external_sale(self, sale_id: int = None):
        dlg = ExternalSaleEntryDialog(parent=self, sale_id=sale_id, user=self.user, branch_id=self.branch_id)
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
            QHeaderView {{
                background-color: {AppStyles.BG_DARKEST};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARKEST};
                color: #FFFFFF;
                font-weight: bold;
                font-size: 9.5pt;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                padding: 8px 10px;
                height: 36px;
            }}
            QTableWidget::item {{
                padding: 7px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {AppStyles.SIDEBAR_ACTIVE};
                color: {AppStyles.PRIMARY};
            }}
        """
