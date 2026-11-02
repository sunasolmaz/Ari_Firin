# src/ui/pages/stock_count_page.py
"""
Ay Sonu ve Günlük Stok Sayım & Fire Takibi Sayfası
Şubeler için Excel'deki "ARI FIRIN - AY SONU STOK VE SAYIM FORMU"nun birebir dijital karşılığı.
- Sekme 1: Stok Durumu ve Takibi (Günlük / Haftalık / Aylık / Tüm Dönemler Özet Listesi & Detay Penceresi)
- Sekme 2: Fire ve Zayiat Analizi (Günlük / Haftalık / Aylık Zarar, Ciro Oranı, En Çok Fire Verenler)
- DailyClosingStockCountDialog: "🌙 Gün Sonu Sayımı" - Kalan Stok ve Fire tek ekranda, tek tıkla otomatik dağıtım
- StockCountDetailDialog: Belirtilen dönemin tam 15 sütunlu sayım tablosu ve hareket logları
"""

import os
import calendar
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QMessageBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QTextEdit, QScrollArea, QGraphicsDropShadowEffect,
    QHeaderView, QTabWidget, QDateEdit, QSizePolicy, QFileDialog,
    QAbstractItemView, QCheckBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ...services.stock_count_service import (
    stock_count_service,
    DEFAULT_STOCK_COUNT_TEMPLATE
)
from ..styles import AppStyles


# ==================== YARDIMCI SAYISAL FONKSİYONLAR ====================

def parse_num(val) -> float:
    """Metin veya sayıdan float değere güvenli dönüştürücü (Türkçe virgül/nokta desteği)"""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace('₺', '').replace('TL', '').replace(' ', '')
    if not s:
        return 0.0
    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def format_num(val: float) -> str:
    """Sayıyı 1.250,50 formatında gösterir"""
    if val is None:
        val = 0.0
    return f"{float(val):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def format_currency(val: float) -> str:
    """Para birimi formatı: 1.250,50 ₺"""
    return f"{format_num(val)} ₺"


# ==================== DİALOGLAR ====================

class NewStockCountSessionDialog(QDialog):
    """Yeni Sayım Dönemi Başlatma Penceresi"""

    def __init__(self, parent=None, default_period: str = ""):
        super().__init__(parent)
        self.setWindowTitle("➕ Yeni Sayım Dönemi Başlat")
        self.setMinimumWidth(440)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
            QLineEdit, QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 10.5pt;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {AppStyles.PRIMARY};
            }}
            QCheckBox {{
                color: {AppStyles.TEXT_PRIMARY};
                font-size: 9.5pt;
                spacing: 8px;
            }}
        """)
        self.init_ui(default_period)

    def init_ui(self, default_period: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("🗓️ Yeni Stok Sayım Dönemi")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        layout.addWidget(title)

        desc = QLabel(
            "Yeni bir dönem boş bir sayım tablosu olarak açılır.\n"
            "Dilediğiniz ürünleri '➕ Yeni Satır / Ürün Ekle' butonuyla kendi ürünlerinizi teker teker ekleyerek oluşturabilirsiniz."
        )
        desc.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9pt;")
        layout.addWidget(desc)

        layout.addWidget(QLabel("Dönem Adı / Tarih (Örn: 01.11.2026 veya Kasım 2026):"))
        self.period_edit = QLineEdit()
        self.period_edit.setPlaceholderText("Örn: Kasım 2026")
        if default_period:
            self.period_edit.setText(default_period)
        else:
            now = datetime.now()
            aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                     "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
            self.period_edit.setText(f"{aylar[now.month - 1]} {now.year}")
        layout.addWidget(self.period_edit)

        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("🚀 Dönemi Başlat")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.PRIMARY};
                color: {AppStyles.TEXT_ON_PRIMARY};
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.PRIMARY_HOVER};
            }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def get_data(self) -> Dict:
        return {
            "period_name": self.period_edit.text().strip(),
            "copy_from_previous": False,
            "load_template_items": False
        }


class AddStockCountItemDialog(QDialog):
    """Tabloya Yeni Satır / Ürün Ekleme Penceresi (Canlı Fire Tutarı ve Net Tutar Hesaplamalı)"""

    def __init__(self, parent=None, categories: Optional[List[str]] = None):
        super().__init__(parent)
        self.setWindowTitle("➕ Yeni Ürün / Satır Ekle")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
            QLineEdit, QComboBox, QDoubleSpinBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 10pt;
            }}
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        self.init_ui(categories or ["Tezgah Ürünleri", "Meşrubatlar", "Pasta Süsleri", "Diğer"])

    def init_ui(self, categories: List[str]):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(22, 22, 22, 22)

        title = QLabel("📦 Yeni Sayım Kalemi Ekle")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        layout.addWidget(title)

        form_grid = QGridLayout()
        form_grid.setSpacing(10)

        # 0. Kategori
        form_grid.addWidget(QLabel("Kategori:"), 0, 0)
        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        for c in categories:
            self.cat_combo.addItem(c)
        form_grid.addWidget(self.cat_combo, 0, 1)

        # 1. Ürün Adı
        form_grid.addWidget(QLabel("Ürün Adı:"), 1, 0)
        self.pname_edit = QLineEdit()
        self.pname_edit.setPlaceholderText("Örn: Yaş Pasta No:1")
        form_grid.addWidget(self.pname_edit, 1, 1)

        # 2. Birim
        form_grid.addWidget(QLabel("Birim:"), 2, 0)
        self.unit_combo = QComboBox()
        self.unit_combo.setEditable(True)
        self.unit_combo.addItems(["Adet", "Kg", "Kutu", "Paket", "Porsiyon", "Lt"])
        form_grid.addWidget(self.unit_combo, 2, 1)

        # 3. Ay Başı Stok
        form_grid.addWidget(QLabel("Ay Başı / Sabah Stok:"), 3, 0)
        self.open_spin = QDoubleSpinBox()
        self.open_spin.setRange(0, 9999999.99)
        self.open_spin.setDecimals(2)
        form_grid.addWidget(self.open_spin, 3, 1)

        # 4. Gelen (Giren)
        form_grid.addWidget(QLabel("Gelen (Giren):"), 4, 0)
        self.in_spin = QDoubleSpinBox()
        self.in_spin.setRange(0, 9999999.99)
        self.in_spin.setDecimals(2)
        form_grid.addWidget(self.in_spin, 4, 1)

        # 5. Fiziksel Sayım (Kalan)
        form_grid.addWidget(QLabel("Fiziksel Sayım (Kalan):"), 5, 0)
        self.phys_spin = QDoubleSpinBox()
        self.phys_spin.setRange(0, 9999999.99)
        self.phys_spin.setDecimals(2)
        form_grid.addWidget(self.phys_spin, 5, 1)

        # 6. Fire ve Zayiat
        form_grid.addWidget(QLabel("🔥 Fire ve Zayiat:"), 6, 0)
        self.waste_spin = QDoubleSpinBox()
        self.waste_spin.setRange(0, 9999999.99)
        self.waste_spin.setDecimals(2)
        form_grid.addWidget(self.waste_spin, 6, 1)

        # 7. Birim Maliyet (TL)
        form_grid.addWidget(QLabel("Birim Maliyet (TL):"), 7, 0)
        self.cost_spin = QDoubleSpinBox()
        self.cost_spin.setRange(0, 9999999.99)
        self.cost_spin.setDecimals(2)
        self.cost_spin.setPrefix("₺ ")
        form_grid.addWidget(self.cost_spin, 7, 1)

        # Ayırıcı
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {AppStyles.BORDER};")
        form_grid.addWidget(sep, 8, 0, 1, 2)

        # 8. Fire Tutarı (Otomatik Hesaplanır)
        lbl_waste_val = QLabel("🔥 Fire / Zayiat Tutarı:")
        lbl_waste_val.setStyleSheet(f"color: {AppStyles.DANGER}; font-weight: bold; font-size: 10pt;")
        form_grid.addWidget(lbl_waste_val, 9, 0)

        self.waste_val_edit = QLineEdit("0,00 ₺")
        self.waste_val_edit.setReadOnly(True)
        self.waste_val_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2a1515;
                color: #f87171;
                border: 1px solid {AppStyles.DANGER};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 10.5pt;
                font-weight: bold;
            }}
        """)
        form_grid.addWidget(self.waste_val_edit, 9, 1)

        # 9. Net Toplam Tutar (Fire Varsa Otomatik Düşülür)
        lbl_total_val = QLabel("💰 Net Toplam Tutar:")
        lbl_total_val.setStyleSheet("color: #10b981; font-weight: bold; font-size: 10.5pt;")
        form_grid.addWidget(lbl_total_val, 10, 0)

        self.total_val_edit = QLineEdit("0,00 ₺")
        self.total_val_edit.setReadOnly(True)
        self.total_val_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0f291e;
                color: #34d399;
                border: 1px solid #10b981;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 11pt;
                font-weight: bold;
            }}
        """)
        form_grid.addWidget(self.total_val_edit, 10, 1)

        layout.addLayout(form_grid)

        # Canlı Hesaplama Bilgi Kutusu
        self.calc_info_card = QFrame()
        self.calc_info_card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px dashed {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
            }}
        """)
        cic_layout = QVBoxLayout(self.calc_info_card)
        cic_layout.setContentsMargins(8, 6, 8, 6)
        cic_layout.setSpacing(2)

        self.calc_info_lbl = QLabel("💡 Toplam Tutar = (Toplam Stok × Birim Maliyet) - Fire Tutarı")
        self.calc_info_lbl.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 8.5pt;")
        self.calc_info_lbl.setWordWrap(True)
        cic_layout.addWidget(self.calc_info_lbl)
        layout.addWidget(self.calc_info_card)

        # Spinbox bağlantıları (anında canlı hesaplama)
        self.open_spin.valueChanged.connect(self.recalculate)
        self.in_spin.valueChanged.connect(self.recalculate)
        self.phys_spin.valueChanged.connect(self.recalculate)
        self.waste_spin.valueChanged.connect(self.recalculate)
        self.cost_spin.valueChanged.connect(self.recalculate)

        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 7px 16px;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("➕ Kalemi Ekle")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.PRIMARY};
                color: {AppStyles.TEXT_ON_PRIMARY};
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.PRIMARY_HOVER};
            }}
        """)
        save_btn.clicked.connect(self.on_submit)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

        # İlk hesaplama
        self.recalculate()

    def recalculate(self):
        """Canlı Fire Tutarı ve Net Toplam Tutar hesaplar"""
        open_qty = self.open_spin.value()
        in_qty = self.in_spin.value()
        phys_qty = self.phys_spin.value()
        waste_qty = self.waste_spin.value()
        cost = self.cost_spin.value()

        # Fire Tutarı = Fire Miktarı × Birim Maliyet
        waste_val = waste_qty * cost

        # Toplam Miktar (Ay Başı + Gelen varsa o, yoksa Fiziksel Sayım)
        tot_avail = open_qty + in_qty
        if tot_avail > 0:
            gross_qty = tot_avail
            qty_label = "Mevcut"
        elif phys_qty > 0:
            gross_qty = phys_qty
            qty_label = "Sayım"
        else:
            gross_qty = 0.0
            qty_label = "Mevcut"

        gross_val = gross_qty * cost
        # Fire varsa tutarı hesaplanan tutardan düşsün
        net_total = max(0.0, gross_val - waste_val)

        self.waste_val_edit.setText(format_currency(waste_val))
        self.total_val_edit.setText(format_currency(net_total))

        if gross_qty > 0 and waste_qty > 0:
            self.calc_info_lbl.setText(
                f"💡 Hesaplanan: {format_num(gross_qty)} {qty_label} × {format_currency(cost)} = {format_currency(gross_val)}  "
                f"|  Fire Düşüldü: -{format_currency(waste_val)}  ➜  Net: {format_currency(net_total)}"
            )
        elif gross_qty > 0:
            self.calc_info_lbl.setText(
                f"💡 Toplam: {format_num(gross_qty)} {qty_label} × {format_currency(cost)} = {format_currency(net_total)} (Fire yok)"
            )
        elif waste_qty > 0:
            self.calc_info_lbl.setText(
                f"⚠️ Fire Tutarı: {format_num(waste_qty)} × {format_currency(cost)} = {format_currency(waste_val)}"
            )
        else:
            self.calc_info_lbl.setText("💡 Toplam Tutar = (Toplam Stok × Birim Maliyet) - Fire Tutarı")

    def on_submit(self):
        pname = self.pname_edit.text().strip()
        if not pname:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir ürün adı yazınız.")
            return
        self.accept()

    def get_data(self) -> Dict:
        open_qty = self.open_spin.value()
        in_qty = self.in_spin.value()
        phys_qty = self.phys_spin.value()
        waste_qty = self.waste_spin.value()
        cost = self.cost_spin.value()

        waste_val = waste_qty * cost
        tot_avail = open_qty + in_qty
        gross_qty = tot_avail if tot_avail > 0 else phys_qty
        net_total = max(0.0, (gross_qty * cost) - waste_val)

        return {
            "category": self.cat_combo.currentText().strip() or "Diğer",
            "product_name": self.pname_edit.text().strip(),
            "unit": self.unit_combo.currentText().strip() or "Adet",
            "opening_stock": open_qty,
            "incoming_stock": in_qty,
            "physical_count": phys_qty,
            "waste_qty": waste_qty,
            "waste_value": waste_val,
            "total_value": net_total,
            "unit_cost": cost
        }


class AddStockMovementDialog(QDialog):
    """Gelen - Çıkan - Zayi Hareketi Ekleme Penceresi"""

    def __init__(self, parent=None, items: Optional[List[Dict]] = None):
        super().__init__(parent)
        self.setWindowTitle("➕ Yeni Stok Hareketi Ekle")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
            QLineEdit, QComboBox, QDoubleSpinBox, QDateEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 10pt;
            }}
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        self.items = items or []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("🚚 Gelen - Giden - Zayiat Girişi")
        title.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        layout.addWidget(title)

        form_grid = QGridLayout()
        form_grid.setSpacing(10)

        form_grid.addWidget(QLabel("Tarih:"), 0, 0)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        form_grid.addWidget(self.date_edit, 0, 1)

        form_grid.addWidget(QLabel("İşlem Türü:"), 1, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Gelen", "Çıkan", "Zayi"])
        form_grid.addWidget(self.type_combo, 1, 1)

        form_grid.addWidget(QLabel("Ürün:"), 2, 0)
        self.prod_combo = QComboBox()
        self.prod_combo.setEditable(True)
        self.prod_combo.addItem("— Listeden Seçiniz veya Yazınız —")
        for itm in self.items:
            cat = itm.get('category', '')
            pname = itm.get('product_name', '')
            self.prod_combo.addItem(f"{pname} ({cat})", userData=itm)
        self.prod_combo.currentIndexChanged.connect(self.on_prod_selected)
        form_grid.addWidget(self.prod_combo, 2, 1)

        form_grid.addWidget(QLabel("Kategori:"), 3, 0)
        self.cat_edit = QLineEdit()
        form_grid.addWidget(self.cat_edit, 3, 1)

        form_grid.addWidget(QLabel("Miktar:"), 4, 0)
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0.01, 9999999.99)
        self.qty_spin.setDecimals(2)
        self.qty_spin.setValue(1.0)
        form_grid.addWidget(self.qty_spin, 4, 1)

        form_grid.addWidget(QLabel("Birim:"), 5, 0)
        self.unit_edit = QLineEdit("Adet")
        form_grid.addWidget(self.unit_edit, 5, 1)

        form_grid.addWidget(QLabel("Açıklama / Tedarikçi:"), 6, 0)
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Örn: İmalathane Sevkiyatı / Fatura No / Zayi Nedeni")
        form_grid.addWidget(self.desc_edit, 6, 1)

        layout.addLayout(form_grid)

        info = QLabel("💡 Not: 'Gelen' hareketi eklendiğinde, sayım tablosundaki 'Gelen (Giren)' miktarı otomatik artırılır.")
        info.setStyleSheet(f"color: {AppStyles.INFO}; font-size: 8.5pt;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 7px 16px;
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Hareketi Kaydet")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.PRIMARY};
                color: {AppStyles.TEXT_ON_PRIMARY};
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-weight: bold;
            }}
        """)
        save_btn.clicked.connect(self.on_submit)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)

    def on_prod_selected(self, index: int):
        data = self.prod_combo.currentData()
        if isinstance(data, dict):
            self.cat_edit.setText(data.get('category', ''))
            self.unit_edit.setText(data.get('unit', 'Adet'))

    def on_submit(self):
        pname = self.prod_combo.currentText().strip()
        data = self.prod_combo.currentData()
        if isinstance(data, dict):
            pname = data.get('product_name', '')
        elif " (" in pname:
            pname = pname.split(" (")[0].strip()

        if not pname or pname.startswith("—"):
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir ürün seçiniz veya yazınız.")
            return

        if self.qty_spin.value() <= 0:
            QMessageBox.warning(self, "Eksik Bilgi", "Miktar 0'dan büyük olmalıdır.")
            return

        self.accept()

    def get_data(self) -> Dict:
        pname = self.prod_combo.currentText().strip()
        data = self.prod_combo.currentData()
        if isinstance(data, dict):
            pname = data.get('product_name', '')
        elif " (" in pname:
            pname = pname.split(" (")[0].strip()

        return {
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "movement_type": self.type_combo.currentText().strip(),
            "product_name": pname,
            "category": self.cat_edit.text().strip(),
            "quantity": self.qty_spin.value(),
            "unit": self.unit_edit.text().strip() or "Adet",
            "description": self.desc_edit.text().strip()
        }


# ==================== 🌙 GÜN SONU BİRLEŞİK SAYIM DİALOGU ====================

class DailyClosingStockCountDialog(QDialog):
    """
    Fırın ve Pastaneler için Gün Sonu Birleşik Stok ve Fire Sayım Ekranı.
    - Tek bir tabloda tüm ürünlerin Kalan Stoğu ve Günün Firesi aynı anda girilir.
    - Kaydet butonuna basıldığında hem Stok modülüne hem Fire analizine hem de Günlük Ciroya otomatik işlenir.
    """

    COL_CAT = 0
    COL_PNAME = 1
    COL_UNIT = 2
    COL_OPENING = 3
    COL_INCOMING = 4
    COL_TOTAL_AVAIL = 5
    COL_PHYSICAL = 6    # ✨ DÜZENLENEBİLİR (Akşam Kalan Sayım)
    COL_WASTE_QTY = 7   # ✨ DÜZENLENEBİLİR (Günün Firesi)
    COL_UNIT_COST = 8   # Düzenlenebilir (Maliyet)
    COL_WASTE_VAL = 9   # Hesaplanan (Fire Tutarı)
    COL_SOLD_OUT = 10   # Hesaplanan (Satılan Miktar)
    COL_REM_VAL = 11    # Hesaplanan (Kalan Değer)
    COL_SOLD_VAL = 12   # Hesaplanan (Satılan Mal Değeri)
    COL_ACTIONS = 13    # Silme / İşlem Butonu

    HEADERS = [
        "Kategori",
        "Ürün Adı",
        "Birim",
        "Sabah / Devir",
        "Gelen (Giren)",
        "Toplam Mevcut",
        "Akşam Kalan (Sayım)",
        "Günün Firesi",
        "Birim Maliyet (TL)",
        "Fire Tutarı (TL)",
        "Satılan / Çıkan",
        "Kalan Stok Değeri",
        "Satılan Mal Değeri",
        "İşlem"
    ]

    def __init__(self, branch_id: int, user: User, default_date: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.branch_id = branch_id
        self.user = user
        self.session_data: Optional[Dict] = None
        self._items_cache: List[Dict] = []
        self._is_calculating = False
        self._has_unsaved_changes = False

        self.setWindowTitle("🌙 Gün Sonu Stok ve Fire Sayımı — Arı Fırın")
        self.resize(1240, 780)
        self.setMinimumWidth(1050)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; }}
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                alternate-background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                gridline-color: {AppStyles.BORDER};
                font-size: 9.5pt;
            }}
            QHeaderView::section {{
                background-color: #1e293b;
                color: #e2e8f0;
                padding: 8px 6px;
                border: 1px solid {AppStyles.BORDER};
                font-weight: bold;
                font-size: 9pt;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
            }}
            QTableWidget::item:selected {{
                background-color: rgba(217, 119, 6, 0.25);
            }}
        """)

        self.init_ui(default_date)
        self.load_daily_session()

    def init_ui(self, default_date: Optional[str]):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 1. ÜST BAŞLIK VE TARİH KONTROL KARTI
        top_card = QFrame()
        top_card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-left: 5px solid {AppStyles.PRIMARY};
                border-radius: 8px;
                padding: 10px 16px;
            }}
        """)
        tc_layout = QHBoxLayout(top_card)
        tc_layout.setContentsMargins(10, 6, 10, 6)
        tc_layout.setSpacing(14)

        # Başlık
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("🌙 Gün Sonu Stok & Fire Sayımı")
        lbl_title.setStyleSheet(f"font-size: 13.5pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        lbl_sub = QLabel("Akşam kalan tezgah stoğunu ve günün zayiatını aynı satırda kolayca giriniz.")
        lbl_sub.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_SECONDARY};")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        tc_layout.addLayout(title_box)

        tc_layout.addStretch()

        # Tarih Seçici
        lbl_dt = QLabel("Sayım Tarihi:")
        lbl_dt.setStyleSheet(f"font-weight: bold; color: {AppStyles.TEXT_SECONDARY}; font-size: 9.5pt;")
        tc_layout.addWidget(lbl_dt)

        prev_d = QPushButton("◀")
        prev_d.setFixedSize(28, 28)
        prev_d.setCursor(Qt.PointingHandCursor)
        prev_d.setStyleSheet(f"background-color: {AppStyles.BG_MEDIUM}; border: 1px solid {AppStyles.BORDER}; border-radius: 4px; color: {AppStyles.TEXT_PRIMARY};")
        prev_d.clicked.connect(self.prev_date)
        tc_layout.addWidget(prev_d)

        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)
        if default_date:
            try:
                y, m, d = [int(x) for x in default_date.split('-')]
                self.date_picker.setDate(QDate(y, m, d))
            except Exception:
                self.date_picker.setDate(QDate.currentDate())
        else:
            self.date_picker.setDate(QDate.currentDate())
        self.date_picker.setDisplayFormat("dd MMMM yyyy dddd")
        self.date_picker.setFixedHeight(30)
        self.date_picker.setMinimumWidth(210)
        self.date_picker.setStyleSheet(f"""
            QDateEdit {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: bold;
            }}
        """)
        self.date_picker.dateChanged.connect(self.load_daily_session)
        tc_layout.addWidget(self.date_picker)

        next_d = QPushButton("▶")
        next_d.setFixedSize(28, 28)
        next_d.setCursor(Qt.PointingHandCursor)
        next_d.setStyleSheet(f"background-color: {AppStyles.BG_MEDIUM}; border: 1px solid {AppStyles.BORDER}; border-radius: 4px; color: {AppStyles.TEXT_PRIMARY};")
        next_d.clicked.connect(self.next_date)
        tc_layout.addWidget(next_d)

        btn_today = QPushButton("Bugün")
        btn_today.setFixedHeight(28)
        btn_today.setCursor(Qt.PointingHandCursor)
        btn_today.setStyleSheet(f"background-color: {AppStyles.BG_MEDIUM}; border: 1px solid {AppStyles.BORDER}; border-radius: 4px; color: {AppStyles.TEXT_PRIMARY}; padding: 0 10px;")
        btn_today.clicked.connect(lambda: self.date_picker.setDate(QDate.currentDate()))
        tc_layout.addWidget(btn_today)

        # Kapat Butonu
        btn_close = QPushButton("✖️ Kapat")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedHeight(30)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                color: {AppStyles.TEXT_PRIMARY};
            }}
        """)
        btn_close.clicked.connect(self.reject)
        tc_layout.addWidget(btn_close)

        layout.addWidget(top_card)

        # 2. CANLI KPI KARTLARI ŞERİDİ
        kpi_strip = self.create_kpi_strip()
        layout.addWidget(kpi_strip)

        # 3. FİLTRE VE ARAMA BARI
        search_bar = QHBoxLayout()
        search_bar.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Ürün adı veya kategori ara...")
        self.search_edit.setFixedHeight(30)
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 9.5pt;
            }}
        """)
        self.search_edit.textChanged.connect(self.filter_table)
        search_bar.addWidget(self.search_edit, 2)

        self.cat_filter_combo = QComboBox()
        self.cat_filter_combo.setFixedHeight(30)
        self.cat_filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 9.5pt;
            }}
        """)
        self.cat_filter_combo.addItems(["Tüm Kategoriler", "Tezgah Ürünleri", "Meşrubatlar", "Pasta Süsleri"])
        self.cat_filter_combo.currentIndexChanged.connect(self.filter_table)
        search_bar.addWidget(self.cat_filter_combo, 1)

        self.btn_add_closing_item = QPushButton("➕ Yeni Ürün Ekle")
        self.btn_add_closing_item.setCursor(Qt.PointingHandCursor)
        self.btn_add_closing_item.setFixedHeight(30)
        self.btn_add_closing_item.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.PRIMARY};
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: 500;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.PRIMARY};
                color: {AppStyles.TEXT_ON_PRIMARY};
            }}
        """)
        self.btn_add_closing_item.clicked.connect(self.on_add_closing_item)
        search_bar.addWidget(self.btn_add_closing_item)

        search_bar.addStretch()

        self.closing_tip_lbl = QLabel("💡 'Akşam Kalan' ve 'Günün Firesi' değerlerini giriniz.")
        self.closing_tip_lbl.setStyleSheet(f"color: {AppStyles.INFO}; font-size: 8.5pt;")
        search_bar.addWidget(self.closing_tip_lbl)

        layout.addLayout(search_bar)

        # 4. BİRLEŞİK GÜN SONU TABLOSU
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_CAT, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_PNAME, QHeaderView.Stretch)
        hdr.setSectionResizeMode(self.COL_UNIT, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_OPENING, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_INCOMING, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_TOTAL_AVAIL, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_PHYSICAL, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_WASTE_QTY, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_UNIT_COST, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_WASTE_VAL, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_SOLD_OUT, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_REM_VAL, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_SOLD_VAL, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_ACTIONS, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_ACTIONS, 46)

        self.table.itemChanged.connect(self.on_table_item_changed)
        layout.addWidget(self.table, 1)

        # 5. ALT BİLGİ VE BÜYÜK KAYDET BUTONU
        bottom_bar = QFrame()
        bottom_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 10px 16px;
            }}
        """)
        bb_layout = QHBoxLayout(bottom_bar)
        bb_layout.setContentsMargins(10, 6, 10, 6)
        bb_layout.setSpacing(16)

        self.cb_sync_turnover = QCheckBox("🔥 Girilen Fire Zararını 'Günlük Ciro' ekranına gider olarak otomatik yaz")
        self.cb_sync_turnover.setChecked(True)
        self.cb_sync_turnover.setStyleSheet(f"color: {AppStyles.TEXT_PRIMARY}; font-size: 9.5pt; font-weight: 500;")
        bb_layout.addWidget(self.cb_sync_turnover)

        bb_layout.addStretch()

        self.btn_save_closing = QPushButton("💾 Gün Sonu Sayımını Tamamla & Kaydet")
        self.btn_save_closing.setCursor(Qt.PointingHandCursor)
        self.btn_save_closing.setFixedHeight(38)
        self.btn_save_closing.setStyleSheet(f"""
            QPushButton {{
                background-color: #059669;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 24px;
                font-weight: bold;
                font-size: 10.5pt;
            }}
            QPushButton:hover {{
                background-color: #047857;
            }}
        """)
        self.btn_save_closing.clicked.connect(self.on_save_clicked)
        bb_layout.addWidget(self.btn_save_closing)

        layout.addWidget(bottom_bar)

    def create_kpi_strip(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 8px 12px;
            }}
        """)
        l = QHBoxLayout(frame)
        l.setContentsMargins(8, 4, 8, 4)
        l.setSpacing(14)

        self.kpi_tot_items = self.create_mini_kpi("Toplam Kalem", "0 Ürün", AppStyles.TEXT_SECONDARY)
        self.kpi_tot_avail = self.create_mini_kpi("Mevcut Stok", "0,00", AppStyles.CYAN)
        self.kpi_tot_phys = self.create_mini_kpi("Akşam Kalan", "0,00", "#10b981")
        self.kpi_tot_waste = self.create_mini_kpi("🔥 Günün Fire Zararı", "0,00 ₺", AppStyles.DANGER, is_bold=True)
        self.kpi_tot_sold = self.create_mini_kpi("Satılan / Çıkan", "0,00", AppStyles.WARNING)
        self.kpi_tot_rem_val = self.create_mini_kpi("💰 Kalan Stok Değeri", "0,00 ₺", AppStyles.PRIMARY, is_bold=True)
        self.kpi_tot_sold_val = self.create_mini_kpi("🏷️ Satılan Mal Değeri", "0,00 ₺", "#38bdf8", is_bold=True)

        l.addWidget(self.kpi_tot_items)
        l.addWidget(self.kpi_tot_avail)
        l.addWidget(self.kpi_tot_phys)
        l.addWidget(self.kpi_tot_waste)
        l.addWidget(self.kpi_tot_sold)
        l.addStretch()
        l.addWidget(self.kpi_tot_rem_val)
        l.addWidget(self.kpi_tot_sold_val)

        return frame

    def create_mini_kpi(self, title: str, val: str, color: str, is_bold: bool = False) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(1)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 8pt; font-weight: 500;")
        l.addWidget(lbl_t)

        f_size = "12pt" if is_bold else "10.5pt"
        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(f"color: {color}; font-size: {f_size}; font-weight: bold;")
        l.addWidget(lbl_v)

        w.value_label = lbl_v
        return w

    def prev_date(self):
        cur = self.date_picker.date().toPyDate()
        new_d = cur - timedelta(days=1)
        self.date_picker.setDate(QDate(new_d.year, new_d.month, new_d.day))

    def next_date(self):
        cur = self.date_picker.date().toPyDate()
        new_d = cur + timedelta(days=1)
        self.date_picker.setDate(QDate(new_d.year, new_d.month, new_d.day))

    def load_daily_session(self):
        """Seçili tarihe ait gün sonu oturumunu ve kalemlerini yükle"""
        date_str = self.date_picker.date().toString("yyyy-MM-dd")
        u_id = getattr(self.user, 'id', None)

        ok, msg, sess, items = stock_count_service.get_or_create_daily_session(
            branch_id=self.branch_id,
            date_str=date_str,
            user_id=u_id
        )

        if not ok or not sess:
            QMessageBox.warning(self, "Hata", msg or "Gün sonu oturumu açılamadı.")
            return

        self.session_data = sess
        self._items_cache = items

        self._is_calculating = True
        self.table.blockSignals(True)
        self.table.setRowCount(len(items))

        for row, itm in enumerate(items):
            self.populate_table_row(row, itm)

        self.table.blockSignals(False)
        self._is_calculating = False
        self.recalculate_totals()
        self.filter_table()

    def populate_table_row(self, row: int, itm: Dict):
        item_id = itm.get('id')

        # 0. Kategori
        c_item = QTableWidgetItem(itm.get('category', ''))
        c_item.setFlags(c_item.flags() & ~Qt.ItemIsEditable)
        c_item.setData(Qt.UserRole, item_id)
        self.table.setItem(row, self.COL_CAT, c_item)

        # 1. Ürün Adı
        p_item = QTableWidgetItem(itm.get('product_name', ''))
        p_item.setFlags(p_item.flags() & ~Qt.ItemIsEditable)
        p_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, self.COL_PNAME, p_item)

        # 2. Birim
        u_item = QTableWidgetItem(itm.get('unit', 'Adet'))
        u_item.setTextAlignment(Qt.AlignCenter)
        u_item.setFlags(u_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, self.COL_UNIT, u_item)

        opening = float(itm.get('opening_stock') or 0.0)
        incoming = float(itm.get('incoming_stock') or 0.0)
        physical = float(itm.get('physical_count') or 0.0)
        waste = float(itm.get('waste_qty') or 0.0)
        cost = float(itm.get('unit_cost') or 0.0)

        total_avail = opening + incoming
        sold_out = max(0.0, total_avail - physical - waste)
        waste_val = waste * cost
        rem_val = physical * cost
        sold_val = sold_out * cost

        # 3. Sabah / Devir
        op_item = QTableWidgetItem(format_num(opening))
        op_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        op_item.setFlags(op_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, self.COL_OPENING, op_item)

        # 4. Gelen (Giren) (Düzenlenebilir)
        in_item = QTableWidgetItem(format_num(incoming))
        in_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, self.COL_INCOMING, in_item)

        # 5. Toplam Mevcut
        av_item = QTableWidgetItem(format_num(total_avail))
        av_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        av_item.setFlags(av_item.flags() & ~Qt.ItemIsEditable)
        av_item.setBackground(QColor("#1e293b"))
        av_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, self.COL_TOTAL_AVAIL, av_item)

        # 6. Akşam Kalan Sayım (✨ DÜZENLENEBİLİR - Yeşil vurgulu)
        ph_item = QTableWidgetItem(format_num(physical))
        ph_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ph_item.setBackground(QColor("#133827"))
        ph_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        ph_item.setForeground(QColor("#34d399"))
        self.table.setItem(row, self.COL_PHYSICAL, ph_item)

        # 7. Günün Firesi (✨ DÜZENLENEBİLİR - Kırmızımsı vurgulu)
        w_item = QTableWidgetItem(format_num(waste))
        w_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        w_item.setBackground(QColor("#3b1818"))
        w_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        w_item.setForeground(QColor("#f87171"))
        self.table.setItem(row, self.COL_WASTE_QTY, w_item)

        # 8. Birim Maliyet (Düzenlenebilir)
        c_item = QTableWidgetItem(format_num(cost))
        c_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, self.COL_UNIT_COST, c_item)

        # 9. Fire Tutarı (Hesaplanan)
        wv_item = QTableWidgetItem(format_currency(waste_val))
        wv_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        wv_item.setFlags(wv_item.flags() & ~Qt.ItemIsEditable)
        wv_item.setForeground(QColor(AppStyles.DANGER))
        wv_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, self.COL_WASTE_VAL, wv_item)

        # 10. Satılan / Çıkan
        so_item = QTableWidgetItem(format_num(sold_out))
        so_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        so_item.setFlags(so_item.flags() & ~Qt.ItemIsEditable)
        so_item.setBackground(QColor("#1e293b"))
        so_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, self.COL_SOLD_OUT, so_item)

        # 11. Kalan Stok Değeri
        rv_item = QTableWidgetItem(format_currency(rem_val))
        rv_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        rv_item.setFlags(rv_item.flags() & ~Qt.ItemIsEditable)
        rv_item.setForeground(QColor(AppStyles.PRIMARY))
        rv_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, self.COL_REM_VAL, rv_item)

        # 12. Satılan Mal Değeri
        sv_item = QTableWidgetItem(format_currency(sold_val))
        sv_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sv_item.setFlags(sv_item.flags() & ~Qt.ItemIsEditable)
        sv_item.setForeground(QColor("#38bdf8"))
        sv_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, self.COL_SOLD_VAL, sv_item)

        # 13. İşlem Butonu (Sil)
        del_btn = QPushButton("🗑️")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setFixedSize(28, 26)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {AppStyles.DANGER};
                border: none;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: #ef444422;
                border-radius: 4px;
            }}
        """)
        del_btn.clicked.connect(lambda _, r=row, iid=item_id: self.delete_closing_row(r, iid))
        self.table.setCellWidget(row, self.COL_ACTIONS, del_btn)

    def on_table_item_changed(self, item: QTableWidgetItem):
        """Canlı hücre düzenlemesinde otomatik hesaplamaları anında uygula"""
        if self._is_calculating:
            return

        col = item.column()
        row = item.row()

        if col not in (self.COL_INCOMING, self.COL_PHYSICAL, self.COL_WASTE_QTY, self.COL_UNIT_COST):
            return

        try:
            self._is_calculating = True
            self._has_unsaved_changes = True

            opening = parse_num(self.table.item(row, self.COL_OPENING).text() if self.table.item(row, self.COL_OPENING) else 0)
            incoming = parse_num(self.table.item(row, self.COL_INCOMING).text() if self.table.item(row, self.COL_INCOMING) else 0)
            physical = parse_num(self.table.item(row, self.COL_PHYSICAL).text() if self.table.item(row, self.COL_PHYSICAL) else 0)
            waste = parse_num(self.table.item(row, self.COL_WASTE_QTY).text() if self.table.item(row, self.COL_WASTE_QTY) else 0)
            cost = parse_num(self.table.item(row, self.COL_UNIT_COST).text() if self.table.item(row, self.COL_UNIT_COST) else 0)

            total_avail = opening + incoming
            sold_out = max(0.0, total_avail - physical - waste)
            waste_val = waste * cost
            rem_val = physical * cost
            sold_val = sold_out * cost

            self.table.item(row, self.COL_TOTAL_AVAIL).setText(format_num(total_avail))
            self.table.item(row, self.COL_WASTE_VAL).setText(format_currency(waste_val))
            self.table.item(row, self.COL_SOLD_OUT).setText(format_num(sold_out))
            self.table.item(row, self.COL_REM_VAL).setText(format_currency(rem_val))
            self.table.item(row, self.COL_SOLD_VAL).setText(format_currency(sold_val))

            if col == self.COL_INCOMING:
                self.table.item(row, self.COL_INCOMING).setText(format_num(incoming))
            elif col == self.COL_PHYSICAL:
                self.table.item(row, self.COL_PHYSICAL).setText(format_num(physical))
            elif col == self.COL_WASTE_QTY:
                self.table.item(row, self.COL_WASTE_QTY).setText(format_num(waste))
            elif col == self.COL_UNIT_COST:
                self.table.item(row, self.COL_UNIT_COST).setText(format_num(cost))

            self._is_calculating = False
            self.recalculate_totals()
        except Exception as e:
            logger.error(f"DailyClosingDialog on_table_item_changed hatası: {e}")
            self._is_calculating = False

    def recalculate_totals(self):
        """Alt toplamları tablodan canlı hesaplar"""
        tot_avail = 0.0
        tot_phys = 0.0
        tot_waste_qty = 0.0
        tot_waste_val = 0.0
        tot_sold = 0.0
        tot_rem_val = 0.0
        tot_sold_val = 0.0
        tot_items = self.table.rowCount()

        for r in range(tot_items):
            avail = parse_num(self.table.item(r, self.COL_TOTAL_AVAIL).text() if self.table.item(r, self.COL_TOTAL_AVAIL) else 0)
            phys = parse_num(self.table.item(r, self.COL_PHYSICAL).text() if self.table.item(r, self.COL_PHYSICAL) else 0)
            waste_q = parse_num(self.table.item(r, self.COL_WASTE_QTY).text() if self.table.item(r, self.COL_WASTE_QTY) else 0)
            waste_v = parse_num(self.table.item(r, self.COL_WASTE_VAL).text() if self.table.item(r, self.COL_WASTE_VAL) else 0)
            sold = parse_num(self.table.item(r, self.COL_SOLD_OUT).text() if self.table.item(r, self.COL_SOLD_OUT) else 0)
            rem = parse_num(self.table.item(r, self.COL_REM_VAL).text() if self.table.item(r, self.COL_REM_VAL) else 0)
            sold_v = parse_num(self.table.item(r, self.COL_SOLD_VAL).text() if self.table.item(r, self.COL_SOLD_VAL) else 0)

            tot_avail += avail
            tot_phys += phys
            tot_waste_qty += waste_q
            tot_waste_val += waste_v
            tot_sold += sold
            tot_rem_val += rem
            tot_sold_val += sold_v

        self.kpi_tot_items.value_label.setText(f"{tot_items} Kalem")
        self.kpi_tot_avail.value_label.setText(f"{tot_avail:,.1f}")
        self.kpi_tot_phys.value_label.setText(f"{tot_phys:,.1f}")
        self.kpi_tot_sold.value_label.setText(f"{tot_sold:,.1f}")

        if tot_waste_val > 0 or tot_waste_qty > 0:
            self.kpi_tot_waste.value_label.setText(f"{format_currency(tot_waste_val)} ({tot_waste_qty:,.1f})")
            self.kpi_tot_waste.value_label.setStyleSheet(f"color: {AppStyles.DANGER}; font-size: 12pt; font-weight: bold;")
        else:
            self.kpi_tot_waste.value_label.setText("0,00 ₺ (Fire Yok)")
            self.kpi_tot_waste.value_label.setStyleSheet(f"color: {AppStyles.SUCCESS}; font-size: 12pt; font-weight: bold;")

        self.kpi_tot_rem_val.value_label.setText(format_currency(tot_rem_val))
        self.kpi_tot_sold_val.value_label.setText(format_currency(tot_sold_val))

    def filter_table(self):
        q = self.search_edit.text().strip().lower()
        cat_filter = self.cat_filter_combo.currentText()

        for r in range(self.table.rowCount()):
            cat_item = self.table.item(r, self.COL_CAT)
            pname_item = self.table.item(r, self.COL_PNAME)

            cat_str = cat_item.text().lower() if cat_item else ""
            pname_str = pname_item.text().lower() if pname_item else ""

            match_query = (not q) or (q in cat_str) or (q in pname_str)
            match_cat = (cat_filter == "Tüm Kategoriler") or (cat_filter.lower() in cat_str)

            self.table.setRowHidden(r, not (match_query and match_cat))

    def on_save_clicked(self):
        """Gün sonu sayımını veritabanına kaydeder ve dağıtır"""
        if not self.session_data:
            QMessageBox.warning(self, "Hata", "Sayım dönemi bulunamadı.")
            return

        date_str = self.date_picker.date().toString("yyyy-MM-dd")
        sess_id = self.session_data.get('id')
        sync_turnover = self.cb_sync_turnover.isChecked()

        items_list = []
        for r in range(self.table.rowCount()):
            c_item = self.table.item(r, self.COL_CAT)
            item_id = c_item.data(Qt.UserRole) if c_item else None
            cat = c_item.text().strip() if c_item else ""
            pname = self.table.item(r, self.COL_PNAME).text().strip() if self.table.item(r, self.COL_PNAME) else ""
            unit = self.table.item(r, self.COL_UNIT).text().strip() if self.table.item(r, self.COL_UNIT) else "Adet"

            opening = parse_num(self.table.item(r, self.COL_OPENING).text() if self.table.item(r, self.COL_OPENING) else 0)
            incoming = parse_num(self.table.item(r, self.COL_INCOMING).text() if self.table.item(r, self.COL_INCOMING) else 0)
            physical = parse_num(self.table.item(r, self.COL_PHYSICAL).text() if self.table.item(r, self.COL_PHYSICAL) else 0)
            waste = parse_num(self.table.item(r, self.COL_WASTE_QTY).text() if self.table.item(r, self.COL_WASTE_QTY) else 0)
            cost = parse_num(self.table.item(r, self.COL_UNIT_COST).text() if self.table.item(r, self.COL_UNIT_COST) else 0)

            items_list.append({
                "id": item_id,
                "category": cat,
                "product_name": pname,
                "unit": unit,
                "opening_stock": opening,
                "incoming_stock": incoming,
                "physical_count": physical,
                "transfer_out_qty": 0.0,
                "waste_qty": waste,
                "unit_cost": cost,
                "display_order": r + 1
            })

        ok, msg = stock_count_service.save_daily_closing(
            branch_id=self.branch_id,
            session_id=sess_id,
            date_str=date_str,
            items_data=items_list,
            sync_to_turnover=sync_turnover
        )

        if ok:
            QMessageBox.information(self, "Gün Sonu Kaydedildi", msg)
            self._has_unsaved_changes = False
            self.accept()
        else:
            QMessageBox.warning(self, "Kayıt Hatası", msg)

    def on_add_closing_item(self):
        """Gün sonu tablosuna tek tek yeni ürün ekleme"""
        if not self.session_data or not self.session_data.get('id'):
            QMessageBox.warning(self, "Hata", "Sayım oturumu bulunamadı.")
            return

        existing_cats = set()
        for r in range(self.table.rowCount()):
            c_item = self.table.item(r, self.COL_CAT)
            if c_item and c_item.text().strip():
                existing_cats.add(c_item.text().strip())
        cats = sorted(list(existing_cats or ["Tezgah Ürünleri", "Meşrubatlar", "Pasta Süsleri"]))

        dlg = AddStockCountItemDialog(self, categories=cats)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            sess_id = self.session_data['id']
            ok, msg, new_id = stock_count_service.add_item(sess_id, data)
            if ok:
                self.load_daily_session()
            else:
                QMessageBox.warning(self, "Hata", msg)

    def delete_closing_row(self, row: int, item_id: Optional[int]):
        """Bir ürünü gün sonu tablosundan ve oturumundan siler"""
        pname = self.table.item(row, self.COL_PNAME).text() if self.table.item(row, self.COL_PNAME) else "Ürün"
        reply = QMessageBox.question(
            self,
            "Ürünü Kaldır",
            f"'{pname}' ürününü gün sonu listesinden kaldırmak istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if item_id:
                ok, msg = stock_count_service.delete_item(item_id)
                if not ok:
                    QMessageBox.warning(self, "Hata", msg)
                    return
            self.table.removeRow(row)
            self.recalculate_totals()


# ==================== DETAY PENCERESİ (POPUP) ====================

class StockCountDetailDialog(QDialog):
    """
    Belirtilen günün/dönemin detaylı stok sayım formunu gösteren pencere.
    - 15 Sütunlu Sayım Tablosu (Excel formatında otomatik hesaplamalar)
    - Canlı Hücre Düzenleme (Ay Başı, Gelen, Fiziksel Sayım, Transfer, Fire, Maliyet)
    - Fire & Zayiat Özeti ve Zarar Hesabı
    - Gelen-Giden Hareket Logları
    - Excel'den Yükleme ve Excel'e Aktarma
    """

    COL_CATEGORY = 0
    COL_PRODUCT = 1
    COL_UNIT = 2
    COL_OPENING = 3       # Düzenlenebilir
    COL_INCOMING = 4      # Düzenlenebilir
    COL_TOTAL_AVAIL = 5   # Hesaplanan (Ay Başı + Gelen)
    COL_PHYSICAL = 6      # Düzenlenebilir (Fiziksel Sayım)
    COL_TRANSFER_OUT = 7  # Düzenlenebilir (Şubeye Transfer)
    COL_WASTE_QTY = 8     # Düzenlenebilir (Fire / Zayiat)
    COL_SOLD_OUT = 9      # Hesaplanan (Toplam Mevcut - Fiziksel - Transfer - Fire)
    COL_UNIT_COST = 10    # Düzenlenebilir (Birim Maliyet TL)
    COL_WASTE_VALUE = 11  # Hesaplanan (Fire * Maliyet)
    COL_REM_VALUE = 12    # Hesaplanan (Fiziksel * Maliyet)
    COL_SOLD_VALUE = 13   # Hesaplanan (Satılan * Maliyet)
    COL_ACTIONS = 14      # Sil butonu

    HEADERS = [
        "Kategori",
        "Ürün Adı",
        "Birim",
        "Ay Başı Stok",
        "Gelen (Giren)",
        "Toplam Mevcut",
        "Fiziksel Sayım (Kalan)",
        "Şubeye Transfer",
        "Fire / Zayiat",
        "Satılan / Çıkan",
        "Birim Maliyet (TL)",
        "Fire Tutarı",
        "Kalan Stok Değeri (TL)",
        "Satılan Mal Değeri (TL)",
        "İşlemler"
    ]

    def __init__(self, session_id: int, user: User, branch_id: int, parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self.user = user
        self.branch_id = branch_id
        self.session_data: Optional[Dict] = None
        self._is_calculating = False
        self._items_cache: List[Dict] = []
        self._has_unsaved_changes = False

        self.setWindowTitle("🔍 Stok Sayım ve Durum Detayı")
        self.resize(1180, 760)
        self.setMinimumWidth(1000)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; }}
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                alternate-background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                gridline-color: {AppStyles.BORDER};
                font-size: 9.5pt;
            }}
            QHeaderView::section {{
                background-color: #1e293b;
                color: #e2e8f0;
                padding: 8px 6px;
                border: 1px solid {AppStyles.BORDER};
                font-weight: bold;
                font-size: 9pt;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
            }}
            QTableWidget::item:selected {{
                background-color: rgba(217, 119, 6, 0.25);
            }}
        """)

        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 1. ÜST KART: Dönem Başlığı, Bilgiler, Durum Rozeti ve Butonlar
        header_card = self.create_header_card()
        layout.addWidget(header_card)

        # 2. ALT TOPLAMLAR (Canlı KPI Kartları)
        totals_panel = self.create_totals_panel()
        layout.addWidget(totals_panel)

        # 3. İÇ SEKME YAPISI: Stok Tablosu & Hareket Logları
        self.inner_tabs = QTabWidget()
        self.inner_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {AppStyles.BORDER};
                background: {AppStyles.BG_DARK};
                border-radius: 6px;
            }}
            QTabBar::tab {{
                background: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_SECONDARY};
                padding: 8px 20px;
                font-size: 9.5pt;
                font-weight: bold;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                background: {AppStyles.BG_DARK};
                color: {AppStyles.PRIMARY};
                border-bottom: 2px solid {AppStyles.PRIMARY};
            }}
        """)

        # Sekme 1: Detaylı Sayım Tablosu
        self.tab_count = QWidget()
        self.setup_count_tab(self.tab_count)
        self.inner_tabs.addTab(self.tab_count, "📊 Ürün Bazında Stok ve Sayım Tablosu")

        # Sekme 2: Hareket Logları
        self.tab_logs = QWidget()
        self.setup_logs_tab(self.tab_logs)
        self.inner_tabs.addTab(self.tab_logs, "📋 Gelen - Giden Hareket Logu")

        layout.addWidget(self.inner_tabs, 1)

    def create_header_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-left: 5px solid {AppStyles.PRIMARY};
                border-radius: 8px;
                padding: 10px 16px;
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(14)

        # Sol Bilgiler
        left_box = QVBoxLayout()
        left_box.setSpacing(3)
        self.lbl_title = QLabel("📦 Sayım Detayı")
        self.lbl_title.setStyleSheet(f"font-size: 13.5pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        self.lbl_info = QLabel("Yükleniyor...")
        self.lbl_info.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_SECONDARY};")
        left_box.addWidget(self.lbl_title)
        left_box.addWidget(self.lbl_info)
        layout.addLayout(left_box)

        layout.addStretch()

        # Sağ Durum Rozeti ve Butonlar
        right_box = QHBoxLayout()
        right_box.setSpacing(8)

        self.status_badge = QLabel("—")
        self.status_badge.setFixedHeight(30)
        self.status_badge.setStyleSheet(f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_MUTED};
            border-radius: 15px;
            padding: 4px 14px;
            font-size: 8.5pt;
            font-weight: bold;
        """)
        right_box.addWidget(self.status_badge)

        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setFixedHeight(32)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.CYAN};
                color: #064e3b;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: #6ee7b7;
            }}
        """)
        self.btn_save.clicked.connect(self.save_current_items)
        right_box.addWidget(self.btn_save)

        self.btn_approve = QPushButton("✅ Sayımı Onayla")
        self.btn_approve.setCursor(Qt.PointingHandCursor)
        self.btn_approve.setFixedHeight(32)
        self.btn_approve.setStyleSheet(f"""
            QPushButton {{
                background-color: #059669;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: #047857;
            }}
        """)
        self.btn_approve.clicked.connect(self.on_approve_session_click)
        right_box.addWidget(self.btn_approve)

        btn_import = QPushButton("📥 Excel'den Yükle")
        btn_import.setCursor(Qt.PointingHandCursor)
        btn_import.setFixedHeight(32)
        btn_import.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        btn_import.clicked.connect(self.on_import_excel_click)
        right_box.addWidget(btn_import)

        btn_export = QPushButton("📤 Excel'e Aktar")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.setFixedHeight(32)
        btn_export.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        btn_export.clicked.connect(self.on_export_excel_click)
        right_box.addWidget(btn_export)

        btn_close = QPushButton("✖️ Kapat")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedHeight(32)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                color: {AppStyles.TEXT_PRIMARY};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        right_box.addWidget(btn_close)

        layout.addLayout(right_box)
        return card

    def create_totals_panel(self) -> QWidget:
        """Alt Toplamlar ve Değer Özet Kartları"""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 8px 14px;
            }}
        """)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(16)

        # 1. Toplam Kalem
        self.lbl_tot_items = self.create_kpi_widget("Toplam Kalem", "0 Ürün", AppStyles.TEXT_SECONDARY)
        layout.addWidget(self.lbl_tot_items)

        # 2. Toplam Mevcut
        self.lbl_tot_avail = self.create_kpi_widget("Toplam Mevcut", "0,00", AppStyles.CYAN)
        layout.addWidget(self.lbl_tot_avail)

        # 3. Toplam Satılan / Çıkan
        self.lbl_tot_sold = self.create_kpi_widget("Satılan / Çıkan", "0,00", AppStyles.WARNING)
        layout.addWidget(self.lbl_tot_sold)

        # 4. Fire / Zayiat Durumu
        self.lbl_tot_waste_val = self.create_kpi_widget("🔥 Fire / Zayiat Zararı", "0,00 ₺", AppStyles.DANGER, is_large=True)
        layout.addWidget(self.lbl_tot_waste_val)

        layout.addStretch()

        # 5. Kalan Stok Değeri (TL)
        self.lbl_tot_rem_val = self.create_kpi_widget("💰 Kalan Stok Değeri", "0,00 ₺", AppStyles.PRIMARY, is_large=True)
        layout.addWidget(self.lbl_tot_rem_val)

        # 6. Satılan Mal Değeri (TL)
        self.lbl_tot_sold_val = self.create_kpi_widget("🏷️ Satılan Mal Değeri", "0,00 ₺", "#38bdf8", is_large=True)
        layout.addWidget(self.lbl_tot_sold_val)

        return panel

    def create_kpi_widget(self, title: str, val: str, color: str, is_large: bool = False) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 8.5pt; font-weight: 500;")
        l.addWidget(lbl_t)

        f_size = "13pt" if is_large else "11pt"
        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(f"color: {color}; font-size: {f_size}; font-weight: bold;")
        l.addWidget(lbl_v)

        w.value_label = lbl_v
        return w

    def setup_count_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Filtre ve Ekleme Çubuğu
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        # Arama kutusu
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Ürün veya kategori ara...")
        self.search_edit.setFixedHeight(32)
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 9.5pt;
            }}
            QLineEdit:focus {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        self.search_edit.textChanged.connect(self.filter_table)
        filter_bar.addWidget(self.search_edit, 2)

        # Kategori filtresi
        self.cat_filter_combo = QComboBox()
        self.cat_filter_combo.setFixedHeight(32)
        self.cat_filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 9.5pt;
            }}
        """)
        self.cat_filter_combo.addItems(["Tüm Kategoriler", "Tezgah Ürünleri", "Meşrubatlar", "Pasta Süsleri"])
        self.cat_filter_combo.currentIndexChanged.connect(self.filter_table)
        filter_bar.addWidget(self.cat_filter_combo, 1)

        filter_bar.addStretch()

        # Yeni Satır Ekle Butonu
        self.btn_add_item = QPushButton("➕ Yeni Satır / Ürün Ekle")
        self.btn_add_item.setCursor(Qt.PointingHandCursor)
        self.btn_add_item.setFixedHeight(32)
        self.btn_add_item.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.PRIMARY};
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: 500;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.PRIMARY};
                color: {AppStyles.TEXT_ON_PRIMARY};
            }}
        """)
        self.btn_add_item.clicked.connect(self.on_add_item_click)
        filter_bar.addWidget(self.btn_add_item)

        layout.addLayout(filter_bar)

        # Ana Sayım Tablosu (15 Sütun)
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_CATEGORY, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_PRODUCT, QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_UNIT, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_OPENING, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_INCOMING, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_TOTAL_AVAIL, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_PHYSICAL, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_TRANSFER_OUT, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_WASTE_QTY, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_SOLD_OUT, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_UNIT_COST, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_WASTE_VALUE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_REM_VALUE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_SOLD_VALUE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self.COL_ACTIONS, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_ACTIONS, 46)

        self.table.itemChanged.connect(self.on_table_item_changed)
        layout.addWidget(self.table, 1)

    def setup_logs_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Üst Araç Çubuğu
        tool_bar = QHBoxLayout()
        tool_bar.setSpacing(10)

        self.btn_add_mov = QPushButton("➕ Yeni Hareket Ekle")
        self.btn_add_mov.setCursor(Qt.PointingHandCursor)
        self.btn_add_mov.setFixedHeight(32)
        self.btn_add_mov.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.PRIMARY};
                color: {AppStyles.TEXT_ON_PRIMARY};
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.PRIMARY_HOVER};
            }}
        """)
        self.btn_add_mov.clicked.connect(self.on_add_movement_click)
        tool_bar.addWidget(self.btn_add_mov)

        # Hareket Türü Filtresi
        self.mov_filter_combo = QComboBox()
        self.mov_filter_combo.setFixedHeight(32)
        self.mov_filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 9.5pt;
            }}
        """)
        self.mov_filter_combo.addItems(["Tüm Hareketler", "Gelen", "Çıkan", "Zayi"])
        self.mov_filter_combo.currentIndexChanged.connect(self.load_movements)
        tool_bar.addWidget(self.mov_filter_combo)

        tool_bar.addStretch()

        # Özet İstatistikler
        self.lbl_mov_summary = QLabel("Gelen: 0 | Çıkan: 0 | Zayi: 0")
        self.lbl_mov_summary.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-weight: bold; font-size: 9pt;")
        tool_bar.addWidget(self.lbl_mov_summary)

        btn_refresh_mov = QPushButton("🔄 Yenile")
        btn_refresh_mov.setCursor(Qt.PointingHandCursor)
        btn_refresh_mov.setFixedHeight(32)
        btn_refresh_mov.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.BG_LIGHT};
            }}
        """)
        btn_refresh_mov.clicked.connect(self.load_movements)
        tool_bar.addWidget(btn_refresh_mov)

        layout.addLayout(tool_bar)

        # Hareket Tablosu
        self.mov_table = QTableWidget()
        mov_headers = ["Tarih", "Kategori", "Ürün Adı", "İşlem Türü", "Miktar", "Birim", "Açıklama / Tedarikçi", "Sil"]
        self.mov_table.setColumnCount(len(mov_headers))
        self.mov_table.setHorizontalHeaderLabels(mov_headers)
        self.mov_table.setAlternatingRowColors(True)
        self.mov_table.verticalHeader().setVisible(False)
        self.mov_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        m_header = self.mov_table.horizontalHeader()
        m_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        m_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        m_header.setSectionResizeMode(2, QHeaderView.Stretch)
        m_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        m_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        m_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        m_header.setSectionResizeMode(6, QHeaderView.Stretch)
        m_header.setSectionResizeMode(7, QHeaderView.Fixed)
        self.mov_table.setColumnWidth(7, 46)

        layout.addWidget(self.mov_table, 1)

    # ==================== VERİ YÜKLEME VE YÖNETİM ====================

    def load_data(self):
        """Dönem verilerini ve kalemlerini yükler"""
        self.session_data = stock_count_service.get_session(self.session_id)
        if not self.session_data:
            QMessageBox.warning(self, "Hata", "Sayım dönemi bulunamadı.")
            self.reject()
            return

        p_name = self.session_data.get('period_name', '')
        b_name = self.session_data.get('branch_name', '')
        c_by = self.session_data.get('created_by_name', '')
        c_at = str(self.session_data.get('created_at', ''))[:10]

        self.lbl_title.setText(f"📦 {p_name} — Stok Sayım Detayı")
        self.lbl_info.setText(f"🗓️ Tarih: {c_at}  |  🏢 Şube: {b_name or 'Merkez'}  |  👤 Oluşturan: {c_by or '—'}")

        self.update_status_ui()
        self.load_session_items()
        self.load_movements()

    def update_status_ui(self):
        if not self.session_data:
            return

        status = self.session_data.get('status', 'Draft')
        if status == 'Approved':
            self.status_badge.setText("🟢 ONAYLANDI (KİLİTLİ)")
            self.status_badge.setStyleSheet("""
                background-color: #064e3b;
                color: #34d399;
                border-radius: 14px;
                padding: 4px 12px;
                font-size: 8.5pt;
                font-weight: bold;
            """)
            self.btn_approve.setText("🔓 Düzenlemeye Aç")
            self.btn_approve.setEnabled(True)
            self.btn_save.setEnabled(False)
            if hasattr(self, 'btn_add_item'):
                self.btn_add_item.setEnabled(False)
            if hasattr(self, 'btn_add_mov'):
                self.btn_add_mov.setEnabled(False)
        else:
            self.status_badge.setText("🟡 TASLAK (DÜZENLENEBİLİR)")
            self.status_badge.setStyleSheet("""
                background-color: #78350f;
                color: #fbbf24;
                border-radius: 14px;
                padding: 4px 12px;
                font-size: 8.5pt;
                font-weight: bold;
            """)
            self.btn_approve.setText("✅ Sayımı Onayla")
            self.btn_approve.setEnabled(True)
            self.btn_save.setEnabled(True)
            if hasattr(self, 'btn_add_item'):
                self.btn_add_item.setEnabled(True)
            if hasattr(self, 'btn_add_mov'):
                self.btn_add_mov.setEnabled(True)

    def load_session_items(self):
        """Oturuma ait kalemleri veritabanından çek ve tabloya doldur"""
        try:
            self._is_calculating = True
            self.table.blockSignals(True)
            self.table.setRowCount(0)

            items = stock_count_service.get_session_items(self.session_id)
            self._items_cache = items
            is_readonly = (self.session_data or {}).get('status') == 'Approved'

            self.table.setRowCount(len(items))

            for row_idx, itm in enumerate(items):
                self.populate_table_row(row_idx, itm, is_readonly)

            self.table.blockSignals(False)
            self._is_calculating = False
            self.recalculate_totals()
            self.filter_table()
        except Exception as e:
            logger.error(f"load_session_items hatası: {e}")
            self.table.blockSignals(False)
            self._is_calculating = False

    def populate_table_row(self, row: int, itm: Dict, is_readonly: bool = False):
        """Tek bir satırı oluşturur ve hesaplanmış sütunları doldurur"""
        item_id = itm.get('id')

        # 0. Kategori
        cat_item = QTableWidgetItem(itm.get('category', ''))
        cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsEditable)
        cat_item.setData(Qt.UserRole, item_id)
        self.table.setItem(row, self.COL_CATEGORY, cat_item)

        # 1. Ürün Adı
        pname_item = QTableWidgetItem(itm.get('product_name', ''))
        pname_item.setFlags(pname_item.flags() & ~Qt.ItemIsEditable)
        pname_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, self.COL_PRODUCT, pname_item)

        # 2. Birim
        unit_item = QTableWidgetItem(itm.get('unit', 'Adet'))
        unit_item.setTextAlignment(Qt.AlignCenter)
        unit_item.setFlags(unit_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, self.COL_UNIT, unit_item)

        opening = float(itm.get('opening_stock') or 0.0)
        incoming = float(itm.get('incoming_stock') or 0.0)
        physical = float(itm.get('physical_count') or 0.0)
        transfer_out = float(itm.get('transfer_out_qty') or 0.0)
        waste = float(itm.get('waste_qty') or 0.0)
        cost = float(itm.get('unit_cost') or 0.0)

        total_avail = opening + incoming
        sold_out = max(0.0, total_avail - physical - transfer_out - waste)
        waste_val = waste * cost
        rem_val = physical * cost
        sold_val = sold_out * cost

        # 3. Ay Başı Stok
        open_item = QTableWidgetItem(format_num(opening))
        open_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if is_readonly:
            open_item.setFlags(open_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, self.COL_OPENING, open_item)

        # 4. Gelen (Giren)
        in_item = QTableWidgetItem(format_num(incoming))
        in_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if is_readonly:
            in_item.setFlags(in_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, self.COL_INCOMING, in_item)

        # 5. Toplam Mevcut (Ay Başı + Gelen)
        avail_item = QTableWidgetItem(format_num(total_avail))
        avail_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        avail_item.setFlags(avail_item.flags() & ~Qt.ItemIsEditable)
        avail_item.setBackground(QColor("#1e293b"))
        avail_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, self.COL_TOTAL_AVAIL, avail_item)

        # 6. Fiziksel Sayım (Kalan)
        phys_item = QTableWidgetItem(format_num(physical))
        phys_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if is_readonly:
            phys_item.setFlags(phys_item.flags() & ~Qt.ItemIsEditable)
        else:
            phys_item.setBackground(QColor("#1e2924"))
        self.table.setItem(row, self.COL_PHYSICAL, phys_item)

        # 7. Şubeye Transfer
        trans_item = QTableWidgetItem(format_num(transfer_out))
        trans_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if is_readonly:
            trans_item.setFlags(trans_item.flags() & ~Qt.ItemIsEditable)
        else:
            trans_item.setBackground(QColor("#1e1b4b"))
        self.table.setItem(row, self.COL_TRANSFER_OUT, trans_item)

        # 8. Fire / Zayiat
        waste_item = QTableWidgetItem(format_num(waste))
        waste_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if is_readonly:
            waste_item.setFlags(waste_item.flags() & ~Qt.ItemIsEditable)
        else:
            waste_item.setBackground(QColor("#3b1818"))
        self.table.setItem(row, self.COL_WASTE_QTY, waste_item)

        # 9. Satılan / Çıkan
        sold_item = QTableWidgetItem(format_num(sold_out))
        sold_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sold_item.setFlags(sold_item.flags() & ~Qt.ItemIsEditable)
        sold_item.setBackground(QColor("#1e293b"))
        sold_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, self.COL_SOLD_OUT, sold_item)

        # 10. Birim Maliyet (TL)
        cost_item = QTableWidgetItem(format_num(cost))
        cost_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if is_readonly:
            cost_item.setFlags(cost_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, self.COL_UNIT_COST, cost_item)

        # 11. Fire Tutarı (TL)
        waste_val_item = QTableWidgetItem(format_currency(waste_val))
        waste_val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        waste_val_item.setFlags(waste_val_item.flags() & ~Qt.ItemIsEditable)
        waste_val_item.setForeground(QColor(AppStyles.DANGER))
        waste_val_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, self.COL_WASTE_VALUE, waste_val_item)

        # 12. Kalan Stok Değeri (TL)
        rem_item = QTableWidgetItem(format_currency(rem_val))
        rem_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        rem_item.setFlags(rem_item.flags() & ~Qt.ItemIsEditable)
        rem_item.setForeground(QColor(AppStyles.PRIMARY))
        rem_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, self.COL_REM_VALUE, rem_item)

        # 13. Satılan Mal Değeri (TL)
        sold_val_item = QTableWidgetItem(format_currency(sold_val))
        sold_val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sold_val_item.setFlags(sold_val_item.flags() & ~Qt.ItemIsEditable)
        sold_val_item.setForeground(QColor("#38bdf8"))
        sold_val_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, self.COL_SOLD_VALUE, sold_val_item)

        # 14. İşlem Butonu (Sil)
        if not is_readonly:
            del_btn = QPushButton("🗑️")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setFixedSize(28, 26)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {AppStyles.DANGER};
                    border: none;
                    font-size: 10pt;
                }}
                QPushButton:hover {{
                    background-color: #ef444422;
                    border-radius: 4px;
                }}
            """)
            del_btn.clicked.connect(lambda _, r=row, iid=item_id: self.delete_row_item(r, iid))
            self.table.setCellWidget(row, self.COL_ACTIONS, del_btn)
        else:
            self.table.setCellWidget(row, self.COL_ACTIONS, QWidget())

    def on_table_item_changed(self, item: QTableWidgetItem):
        """Hücre içeriği değiştiğinde otomatik formül hesaplamalarını anında uygula"""
        if self._is_calculating:
            return

        col = item.column()
        row = item.row()

        if col not in (self.COL_OPENING, self.COL_INCOMING, self.COL_PHYSICAL, self.COL_TRANSFER_OUT, self.COL_WASTE_QTY, self.COL_UNIT_COST):
            return

        try:
            self._is_calculating = True
            self._has_unsaved_changes = True

            opening = parse_num(self.table.item(row, self.COL_OPENING).text() if self.table.item(row, self.COL_OPENING) else 0)
            incoming = parse_num(self.table.item(row, self.COL_INCOMING).text() if self.table.item(row, self.COL_INCOMING) else 0)
            physical = parse_num(self.table.item(row, self.COL_PHYSICAL).text() if self.table.item(row, self.COL_PHYSICAL) else 0)
            transfer_out = parse_num(self.table.item(row, self.COL_TRANSFER_OUT).text() if self.table.item(row, self.COL_TRANSFER_OUT) else 0)
            waste = parse_num(self.table.item(row, self.COL_WASTE_QTY).text() if self.table.item(row, self.COL_WASTE_QTY) else 0)
            cost = parse_num(self.table.item(row, self.COL_UNIT_COST).text() if self.table.item(row, self.COL_UNIT_COST) else 0)

            total_avail = opening + incoming
            sold_out = max(0.0, total_avail - physical - transfer_out - waste)
            waste_val = waste * cost
            rem_val = physical * cost
            sold_val = sold_out * cost

            self.table.item(row, self.COL_TOTAL_AVAIL).setText(format_num(total_avail))
            self.table.item(row, self.COL_SOLD_OUT).setText(format_num(sold_out))
            self.table.item(row, self.COL_WASTE_VALUE).setText(format_currency(waste_val))
            self.table.item(row, self.COL_REM_VALUE).setText(format_currency(rem_val))
            self.table.item(row, self.COL_SOLD_VALUE).setText(format_currency(sold_val))

            if col == self.COL_OPENING:
                self.table.item(row, self.COL_OPENING).setText(format_num(opening))
            elif col == self.COL_INCOMING:
                self.table.item(row, self.COL_INCOMING).setText(format_num(incoming))
            elif col == self.COL_PHYSICAL:
                self.table.item(row, self.COL_PHYSICAL).setText(format_num(physical))
            elif col == self.COL_TRANSFER_OUT:
                self.table.item(row, self.COL_TRANSFER_OUT).setText(format_num(transfer_out))
            elif col == self.COL_WASTE_QTY:
                self.table.item(row, self.COL_WASTE_QTY).setText(format_num(waste))
            elif col == self.COL_UNIT_COST:
                self.table.item(row, self.COL_UNIT_COST).setText(format_num(cost))

            self._is_calculating = False
            self.recalculate_totals()
        except Exception as e:
            logger.error(f"on_table_item_changed hesaplama hatası: {e}")
            self._is_calculating = False

    def recalculate_totals(self):
        """Alt toplamları tablodaki canlı verilerden hesaplar"""
        tot_avail = 0.0
        tot_sold = 0.0
        tot_waste_qty = 0.0
        tot_waste_val = 0.0
        tot_rem_val = 0.0
        tot_sold_val = 0.0
        tot_items = self.table.rowCount()

        for r in range(tot_items):
            avail = parse_num(self.table.item(r, self.COL_TOTAL_AVAIL).text() if self.table.item(r, self.COL_TOTAL_AVAIL) else 0)
            sold = parse_num(self.table.item(r, self.COL_SOLD_OUT).text() if self.table.item(r, self.COL_SOLD_OUT) else 0)
            waste_q = parse_num(self.table.item(r, self.COL_WASTE_QTY).text() if self.table.item(r, self.COL_WASTE_QTY) else 0)
            waste_v = parse_num(self.table.item(r, self.COL_WASTE_VALUE).text() if self.table.item(r, self.COL_WASTE_VALUE) else 0)
            rem = parse_num(self.table.item(r, self.COL_REM_VALUE).text() if self.table.item(r, self.COL_REM_VALUE) else 0)
            sold_v = parse_num(self.table.item(r, self.COL_SOLD_VALUE).text() if self.table.item(r, self.COL_SOLD_VALUE) else 0)

            tot_avail += avail
            tot_sold += sold
            tot_waste_qty += waste_q
            tot_waste_val += waste_v
            tot_rem_val += rem
            tot_sold_val += sold_v

        self.lbl_tot_items.value_label.setText(f"{tot_items} Kalem")
        self.lbl_tot_avail.value_label.setText(format_num(tot_avail))
        self.lbl_tot_sold.value_label.setText(format_num(tot_sold))

        if tot_waste_val > 0 or tot_waste_qty > 0:
            self.lbl_tot_waste_val.value_label.setText(f"{format_currency(tot_waste_val)} ({tot_waste_qty:,.1f})")
            self.lbl_tot_waste_val.value_label.setStyleSheet(f"color: {AppStyles.DANGER}; font-size: 13pt; font-weight: bold;")
        else:
            self.lbl_tot_waste_val.value_label.setText("0,00 ₺ (Fire Yok)")
            self.lbl_tot_waste_val.value_label.setStyleSheet(f"color: {AppStyles.SUCCESS}; font-size: 13pt; font-weight: bold;")

        self.lbl_tot_rem_val.value_label.setText(format_currency(tot_rem_val))
        self.lbl_tot_sold_val.value_label.setText(format_currency(tot_sold_val))

    def filter_table(self):
        """Arama ve kategori filtresini uygula"""
        q = self.search_edit.text().strip().lower()
        cat_filter = self.cat_filter_combo.currentText()

        for r in range(self.table.rowCount()):
            cat_item = self.table.item(r, self.COL_CATEGORY)
            pname_item = self.table.item(r, self.COL_PRODUCT)

            cat_str = cat_item.text().lower() if cat_item else ""
            pname_str = pname_item.text().lower() if pname_item else ""

            match_query = (not q) or (q in cat_str) or (q in pname_str)
            match_cat = (cat_filter == "Tüm Kategoriler") or (cat_filter.lower() in cat_str)

            self.table.setRowHidden(r, not (match_query and match_cat))

    def save_current_items(self, silent: bool = False):
        """Tablodaki tüm satırları veritabanına kaydeder"""
        if (self.session_data or {}).get('status') == 'Approved':
            if not silent:
                QMessageBox.warning(self, "Kilitli", "Onaylanmış dönemlerde değişiklik yapılamaz.")
            return

        try:
            items_list = []
            for r in range(self.table.rowCount()):
                cat_item = self.table.item(r, self.COL_CATEGORY)
                item_id = cat_item.data(Qt.UserRole) if cat_item else None
                cat = cat_item.text().strip() if cat_item else ""
                pname = self.table.item(r, self.COL_PRODUCT).text().strip() if self.table.item(r, self.COL_PRODUCT) else ""
                unit = self.table.item(r, self.COL_UNIT).text().strip() if self.table.item(r, self.COL_UNIT) else "Adet"

                opening = parse_num(self.table.item(r, self.COL_OPENING).text() if self.table.item(r, self.COL_OPENING) else 0)
                incoming = parse_num(self.table.item(r, self.COL_INCOMING).text() if self.table.item(r, self.COL_INCOMING) else 0)
                physical = parse_num(self.table.item(r, self.COL_PHYSICAL).text() if self.table.item(r, self.COL_PHYSICAL) else 0)
                transfer_out = parse_num(self.table.item(r, self.COL_TRANSFER_OUT).text() if self.table.item(r, self.COL_TRANSFER_OUT) else 0)
                waste = parse_num(self.table.item(r, self.COL_WASTE_QTY).text() if self.table.item(r, self.COL_WASTE_QTY) else 0)
                cost = parse_num(self.table.item(r, self.COL_UNIT_COST).text() if self.table.item(r, self.COL_UNIT_COST) else 0)

                items_list.append({
                    "id": item_id,
                    "category": cat,
                    "product_name": pname,
                    "unit": unit,
                    "opening_stock": opening,
                    "incoming_stock": incoming,
                    "physical_count": physical,
                    "transfer_out_qty": transfer_out,
                    "waste_qty": waste,
                    "unit_cost": cost,
                    "display_order": r + 1
                })

            ok, msg = stock_count_service.save_items(self.session_id, items_list)
            self._has_unsaved_changes = False

            if ok:
                if not silent:
                    QMessageBox.information(self, "Kaydedildi", msg)
            else:
                if not silent:
                    QMessageBox.warning(self, "Hata", msg)
        except Exception as e:
            logger.error(f"save_current_items hatası: {e}")
            if not silent:
                QMessageBox.critical(self, "Kayıt Hatası", str(e))

    def on_add_item_click(self):
        """Manuel satır / ürün ekleme"""
        if (self.session_data or {}).get('status') == 'Approved':
            QMessageBox.warning(self, "Kilitli", "Onaylanmış dönemlere ürün eklenemez.")
            return

        existing_cats = set()
        for r in range(self.table.rowCount()):
            c_item = self.table.item(r, self.COL_CATEGORY)
            if c_item and c_item.text().strip():
                existing_cats.add(c_item.text().strip())
        cats = sorted(list(existing_cats or ["Tezgah Ürünleri", "Meşrubatlar", "Pasta Süsleri"]))

        dlg = AddStockCountItemDialog(self, categories=cats)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            ok, msg, new_id = stock_count_service.add_item(self.session_id, data)
            if ok:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_session_items()
            else:
                QMessageBox.warning(self, "Hata", msg)

    def delete_row_item(self, row: int, item_id: Optional[int]):
        """Bir kalemi tablodan ve veritabanından sil"""
        pname = self.table.item(row, self.COL_PRODUCT).text() if self.table.item(row, self.COL_PRODUCT) else "Ürün"
        reply = QMessageBox.question(
            self,
            "Kalemi Sil",
            f"'{pname}' ürününü sayım tablosundan silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if item_id:
                ok, msg = stock_count_service.delete_item(item_id)
                if not ok:
                    QMessageBox.warning(self, "Hata", msg)
                    return
            self.table.removeRow(row)
            self.recalculate_totals()

    def on_approve_session_click(self):
        """Dönemi onayla veya tekrar aç"""
        status = (self.session_data or {}).get('status', 'Draft')
        if status == 'Approved':
            reply = QMessageBox.question(
                self,
                "Düzenlemeye Aç",
                "Bu sayım dönemini tekrar taslağa alıp düzenlemek istiyor musunuz?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                ok, msg = stock_count_service.reopen_session(self.session_id)
                if ok:
                    self.session_data['status'] = 'Draft'
                    self.update_status_ui()
                    self.load_session_items()
                else:
                    QMessageBox.warning(self, "Hata", msg)
        else:
            reply = QMessageBox.question(
                self,
                "Sayımı Onayla",
                "Bu sayım dönemini onaylamak istiyor musunuz?\n"
                "Onaylanan sayım kilitlenir ve resmi dönem sonu raporlarına yansıtılır.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.save_current_items(silent=True)
                ok, msg = stock_count_service.approve_session(self.session_id)
                if ok:
                    QMessageBox.information(self, "Onaylandı", msg)
                    self.session_data['status'] = 'Approved'
                    self.update_status_ui()
                    self.load_session_items()
                else:
                    QMessageBox.warning(self, "Hata", msg)

    def on_export_excel_click(self):
        """Mevcut dönemi Excel formatında dışa aktar"""
        if self._has_unsaved_changes:
            self.save_current_items(silent=True)

        p_name = (self.session_data or {}).get('period_name', 'Sayim').replace(' ', '_')
        default_filename = f"Ari_Firin_Stok_Sayim_{p_name}.xlsx"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Excel Olarak Dışa Aktar",
            default_filename,
            "Excel Dosyası (*.xlsx)"
        )
        if not file_path:
            return

        ok, msg = stock_count_service.export_to_excel(self.session_id, file_path)
        if ok:
            QMessageBox.information(self, "Dışa Aktarma Başarılı", msg)
        else:
            QMessageBox.warning(self, "Dışa Aktarma Hatası", msg)

    def on_import_excel_click(self):
        """Excel dosyasından toplu sayım verisi yükle"""
        if (self.session_data or {}).get('status') == 'Approved':
            QMessageBox.warning(self, "Kilitli", "Onaylanmış dönemlere Excel'den veri yüklenemez.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Excel Dosyasından Sayım Yükle",
            "",
            "Excel Dosyası (*.xlsx *.xls)"
        )
        if not file_path:
            return

        ok, msg, count = stock_count_service.import_from_excel(self.session_id, file_path)
        if ok:
            QMessageBox.information(self, "Yükleme Başarılı", msg)
            self.load_session_items()
        else:
            QMessageBox.warning(self, "Yükleme Hatası", msg)

    def load_movements(self):
        """Döneme ait hareketleri yükle"""
        try:
            self.mov_table.setRowCount(0)
            movements = stock_count_service.get_movements(self.session_id)
            selected_type = self.mov_filter_combo.currentText()

            count_in = sum(1 for m in movements if m.get('movement_type') == 'Gelen')
            count_out = sum(1 for m in movements if m.get('movement_type') == 'Çıkan')
            count_waste = sum(1 for m in movements if m.get('movement_type') in ('Zayi', 'Fire'))
            self.lbl_mov_summary.setText(f"🟢 Gelen: {count_in} | 🔴 Çıkan: {count_out} | 🟠 Zayi: {count_waste}")

            filtered = [
                m for m in movements
                if selected_type == "Tüm Hareketler" or m.get('movement_type') == selected_type
            ]

            self.mov_table.setRowCount(len(filtered))
            is_readonly = (self.session_data or {}).get('status') == 'Approved'

            for r, m in enumerate(filtered):
                m_id = m.get('id')

                t_item = QTableWidgetItem(str(m.get('date', '')))
                t_item.setTextAlignment(Qt.AlignCenter)
                self.mov_table.setItem(r, 0, t_item)

                self.mov_table.setItem(r, 1, QTableWidgetItem(m.get('category', '')))

                p_item = QTableWidgetItem(m.get('product_name', ''))
                p_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.mov_table.setItem(r, 2, p_item)

                mtype = m.get('movement_type', 'Gelen')
                type_item = QTableWidgetItem(mtype)
                type_item.setTextAlignment(Qt.AlignCenter)
                if mtype == 'Gelen':
                    type_item.setForeground(QColor(AppStyles.SUCCESS))
                elif mtype == 'Çıkan':
                    type_item.setForeground(QColor(AppStyles.DANGER))
                else:
                    type_item.setForeground(QColor(AppStyles.WARNING))
                type_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.mov_table.setItem(r, 3, type_item)

                q_item = QTableWidgetItem(format_num(m.get('quantity', 0.0)))
                q_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                q_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.mov_table.setItem(r, 4, q_item)

                u_item = QTableWidgetItem(m.get('unit', 'Adet'))
                u_item.setTextAlignment(Qt.AlignCenter)
                self.mov_table.setItem(r, 5, u_item)

                self.mov_table.setItem(r, 6, QTableWidgetItem(m.get('description', '')))

                if not is_readonly:
                    del_btn = QPushButton("🗑️")
                    del_btn.setCursor(Qt.PointingHandCursor)
                    del_btn.setFixedSize(28, 26)
                    del_btn.setStyleSheet(f"""
                        QPushButton {{
                            background: transparent;
                            color: {AppStyles.DANGER};
                            border: none;
                            font-size: 10pt;
                        }}
                        QPushButton:hover {{
                            background-color: #ef444422;
                            border-radius: 4px;
                        }}
                    """)
                    del_btn.clicked.connect(lambda _, mid=m_id: self.delete_movement_click(mid))
                    self.mov_table.setCellWidget(r, 7, del_btn)
                else:
                    self.mov_table.setCellWidget(r, 7, QWidget())
        except Exception as e:
            logger.error(f"load_movements hatası: {e}")

    def on_add_movement_click(self):
        """Yeni hareket ekleme dialogu"""
        if (self.session_data or {}).get('status') == 'Approved':
            QMessageBox.warning(self, "Kilitli", "Onaylanmış dönemlere hareket eklenemez.")
            return

        items = stock_count_service.get_session_items(self.session_id)
        dlg = AddStockMovementDialog(self, items=items)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            ok, msg, new_id = stock_count_service.add_movement(self.session_id, data)
            if ok:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_movements()
                self.load_session_items()
            else:
                QMessageBox.warning(self, "Hata", msg)

    def delete_movement_click(self, movement_id: int):
        reply = QMessageBox.question(
            self,
            "Hareketi Sil",
            "Bu hareket kaydını silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = stock_count_service.delete_movement(movement_id)
            if ok:
                self.load_movements()
                self.load_session_items()
            else:
                QMessageBox.warning(self, "Hata", msg)


# ==================== ANA SAYFA SINIFI ====================

class StockCountPage(QWidget):
    """
    Ay Sonu ve Günlük Stok Sayım & Fire Takibi Sayfası
    - Sekme 1: Stok Durumu ve Takibi (Günlük / Haftalık / Aylık / Tüm Dönemler Listesi & Detay Butonu)
    - Sekme 2: Fire ve Zayiat Analizi (Günlük / Haftalık / Aylık Metrikler, Top 5)
    """

    def __init__(self, user: User, branch_id: int, parent=None):
        super().__init__(parent)
        self.user = user
        self.branch_id = branch_id
        self._stock_mode = "daily"
        self._waste_mode = "daily"

        self.init_ui()
        self.set_stock_mode("daily")
        self.set_waste_mode("daily")

    # ==================== ARAYÜZ OLUŞTURMA ====================

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # 1. ÜST BAŞLIK BARI
        top_bar = self.create_top_bar()
        main_layout.addWidget(top_bar)

        # 2. ANA SEKME YAPISI (Genişletilmiş ve Ferah Sekmeler)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {AppStyles.BORDER};
                background: {AppStyles.BG_DARK};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_SECONDARY};
                padding: 12px 28px;
                min-width: 260px;
                font-size: 11pt;
                font-weight: bold;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 6px;
            }}
            QTabBar::tab:selected {{
                background: {AppStyles.BG_DARK};
                color: {AppStyles.PRIMARY};
                border-bottom: 3px solid {AppStyles.PRIMARY};
            }}
            QTabBar::tab:hover:!selected {{
                background: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
            }}
        """)

        # 1. SEKME: Stok Durumu ve Takibi (Günlük / Haftalık / Aylık / Tüm Dönemler)
        self.tab_stock = QWidget()
        self.setup_stock_tab(self.tab_stock)
        self.tabs.addTab(self.tab_stock, "📦 Stok Durumu ve Takibi")

        # 2. SEKME: Fire ve Zayiat Analizi (Günlük / Haftalık / Aylık)
        self.tab_waste = QWidget()
        self.setup_waste_tab(self.tab_waste)
        self.tabs.addTab(self.tab_waste, "🔥 Fire ve Zayiat Analizi")

        self.tabs.currentChanged.connect(self.on_main_tab_changed)
        main_layout.addWidget(self.tabs, 1)

    def create_top_bar(self) -> QWidget:
        """Üst başlık çubuğu"""
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 8px 14px;
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)

        # Başlık ve İkon
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("📦 Stok ve Sayım Yönetimi")
        lbl_title.setStyleSheet(f"font-size: 13.5pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        lbl_sub = QLabel("Arı Fırın Standart Formu — Günlük / Haftalık / Aylık / Yıllık Stok & Fire İzleme")
        lbl_sub.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_SECONDARY};")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        layout.addLayout(title_box)

        layout.addStretch()

        # 🌙 Gün Sonu Sayımı Yap Butonu (Vurgulu ve Önemli)
        btn_daily_closing = QPushButton("🌙 Gün Sonu Sayımı Yap")
        btn_daily_closing.setCursor(Qt.PointingHandCursor)
        btn_daily_closing.setFixedHeight(34)
        btn_daily_closing.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        btn_daily_closing.setToolTip("Akşam vitrin stoğunu ve günün firelerini aynı satırda kolayca sayıp kaydedin.")
        btn_daily_closing.clicked.connect(self.on_open_daily_closing)
        layout.addWidget(btn_daily_closing)

        # Yeni Sayım Dönemi Başlat Butonu
        btn_new = QPushButton("➕ Yeni Dönem Başlat")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.setFixedHeight(34)
        btn_new.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.PRIMARY};
                color: {AppStyles.TEXT_ON_PRIMARY};
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.PRIMARY_HOVER};
            }}
        """)
        btn_new.clicked.connect(self.on_new_session_click)
        layout.addWidget(btn_new)

        return bar

    # ==================== SEKME 1: STOK DURUMU VE TAKİBİ ====================

    def setup_stock_tab(self, parent: QWidget):
        """1. Sekme: Günlük, Haftalık, Aylık ve Tüm Dönemler Stok Listesi"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 1. Filtre Çubuğu (Günlük / Haftalık / Aylık / Tüm Dönemler)
        filter_bar = self.create_stock_filter_bar()
        layout.addWidget(filter_bar)

        # 2. KPI Kartları Satırı
        kpi_row = self.create_stock_kpi_row()
        layout.addWidget(kpi_row)

        # 3. Sayım Dönemleri Özet Tablosu
        self.stock_table = QTableWidget()
        stock_headers = [
            "Tarih / Dönem",
            "Durum",
            "Kalem Sayısı",
            "Toplam Mevcut",
            "Satılan / Çıkan",
            "Kalan Stok Değeri (TL)",
            "Satılan Değer (TL)",
            "🔥 Fire / Zayiat",
            "İşlemler"
        ]
        self.stock_table.setColumnCount(len(stock_headers))
        self.stock_table.setHorizontalHeaderLabels(stock_headers)
        self.stock_table.setAlternatingRowColors(True)
        self.stock_table.verticalHeader().setVisible(False)
        self.stock_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.stock_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                alternate-background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                gridline-color: {AppStyles.BORDER};
                font-size: 9.5pt;
            }}
            QHeaderView::section {{
                background-color: #1e293b;
                color: #e2e8f0;
                padding: 10px 8px;
                border: 1px solid {AppStyles.BORDER};
                font-weight: bold;
                font-size: 9pt;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
        """)

        s_hdr = self.stock_table.horizontalHeader()
        s_hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        s_hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        s_hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        s_hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        s_hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        s_hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        s_hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        s_hdr.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        s_hdr.setSectionResizeMode(8, QHeaderView.Fixed)
        self.stock_table.setColumnWidth(8, 120)

        self.stock_table.cellDoubleClicked.connect(lambda row, col: self.on_stock_row_double_click(row))
        layout.addWidget(self.stock_table, 1)

    def create_stock_filter_bar(self) -> QFrame:
        """Stok durumu için Günlük/Haftalık/Aylık/Tüm Dönemler seçim çubuğu"""
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
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

        self.btn_stock_daily = QPushButton("📅 Günlük")
        self.btn_stock_weekly = QPushButton("📆 Haftalık")
        self.btn_stock_monthly = QPushButton("🗓️ Aylık")
        self.btn_stock_yearly = QPushButton("📊 Yıllık")
        self.btn_stock_all = QPushButton("📋 Tüm Dönemler")

        for btn in (self.btn_stock_daily, self.btn_stock_weekly, self.btn_stock_monthly, self.btn_stock_yearly, self.btn_stock_all):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)

        self.btn_stock_daily.clicked.connect(lambda: self.set_stock_mode("daily"))
        self.btn_stock_weekly.clicked.connect(lambda: self.set_stock_mode("weekly"))
        self.btn_stock_monthly.clicked.connect(lambda: self.set_stock_mode("monthly"))
        self.btn_stock_yearly.clicked.connect(lambda: self.set_stock_mode("yearly"))
        self.btn_stock_all.clicked.connect(lambda: self.set_stock_mode("all"))

        l.addWidget(self.btn_stock_daily)
        l.addWidget(self.btn_stock_weekly)
        l.addWidget(self.btn_stock_monthly)
        l.addWidget(self.btn_stock_yearly)
        l.addWidget(self.btn_stock_all)

        # Ayırıcı
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setFixedHeight(24)
        sep.setStyleSheet(f"background-color: {AppStyles.BORDER};")
        l.addWidget(sep)

        # Tarih Seçici ve Oklar
        prev_btn = QPushButton("◀")
        prev_btn.setFixedSize(30, 30)
        prev_btn.setCursor(Qt.PointingHandCursor)
        prev_btn.setStyleSheet(f"background-color: {AppStyles.BG_DARK}; border: 1px solid {AppStyles.BORDER}; border-radius: 4px; color: {AppStyles.TEXT_PRIMARY};")
        prev_btn.clicked.connect(self.stock_prev_period)
        l.addWidget(prev_btn)

        self.stock_date_edit = QDateEdit()
        self.stock_date_edit.setCalendarPopup(True)
        self.stock_date_edit.setDate(QDate.currentDate())
        self.stock_date_edit.setDisplayFormat("dd MMMM yyyy dddd")
        self.stock_date_edit.setFixedHeight(30)
        self.stock_date_edit.setMinimumWidth(150)
        self.stock_date_edit.setMaximumWidth(190)
        self.stock_date_edit.setStyleSheet(f"""
            QDateEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: bold;
            }}
        """)
        self.stock_date_edit.dateChanged.connect(self.load_stock_overview)
        l.addWidget(self.stock_date_edit)

        today_btn = QPushButton("Bugün")
        today_btn.setFixedHeight(30)
        today_btn.setCursor(Qt.PointingHandCursor)
        today_btn.setStyleSheet(f"background-color: {AppStyles.BG_DARK}; border: 1px solid {AppStyles.BORDER}; border-radius: 4px; color: {AppStyles.TEXT_PRIMARY}; padding: 0 10px;")
        today_btn.clicked.connect(lambda: self.stock_date_edit.setDate(QDate.currentDate()))
        l.addWidget(today_btn)

        next_btn = QPushButton("▶")
        next_btn.setFixedSize(30, 30)
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.setStyleSheet(f"background-color: {AppStyles.BG_DARK}; border: 1px solid {AppStyles.BORDER}; border-radius: 4px; color: {AppStyles.TEXT_PRIMARY};")
        next_btn.clicked.connect(self.stock_next_period)
        l.addWidget(next_btn)

        l.addStretch()

        self.lbl_stock_range_title = QLabel("")
        self.lbl_stock_range_title.setStyleSheet(f"color: {AppStyles.PRIMARY}; font-weight: bold; font-size: 10pt;")
        l.addWidget(self.lbl_stock_range_title)



        return bar

    def create_stock_kpi_row(self) -> QWidget:
        """Stok özeti KPI kartları"""
        row = QWidget()
        l = QHBoxLayout(row)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(12)

        self.kpi_stock_rem_val = self.create_card_widget("💰 Toplam Kalan Stok Değeri", "0,00 ₺", AppStyles.PRIMARY)
        self.kpi_stock_sold_val = self.create_card_widget("🏷️ Toplam Satılan Değer", "0,00 ₺", "#38bdf8")
        self.kpi_stock_waste_val = self.create_card_widget("🔥 Dönem Fire Zararı", "0,00 ₺", AppStyles.DANGER)
        self.kpi_stock_avail_qty = self.create_card_widget("📦 Toplam Mevcut Stok", "0,00", AppStyles.CYAN)
        self.kpi_stock_count = self.create_card_widget("📋 Sayım / Dönem Sayısı", "0", AppStyles.TEXT_PRIMARY)

        l.addWidget(self.kpi_stock_rem_val)
        l.addWidget(self.kpi_stock_sold_val)
        l.addWidget(self.kpi_stock_waste_val)
        l.addWidget(self.kpi_stock_avail_qty)
        l.addWidget(self.kpi_stock_count)

        return row

    def create_card_widget(self, title: str, val: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 10px 14px;
            }}
        """)
        l = QVBoxLayout(card)
        l.setContentsMargins(6, 4, 6, 4)
        l.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 8.5pt; font-weight: 500;")
        l.addWidget(lbl_t)

        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(f"color: {color}; font-size: 13.5pt; font-weight: bold;")
        l.addWidget(lbl_v)

        card.value_label = lbl_v
        return card

    def set_stock_mode(self, mode: str):
        """Stok görünüm modunu (günlük/haftalık/aylık/yıllık/tüm) değiştirir"""
        self._stock_mode = mode
        active_style = f"background-color: {AppStyles.PRIMARY}; color: {AppStyles.TEXT_ON_PRIMARY}; font-weight: bold; border-radius: 6px; padding: 4px 10px; font-size: 9pt;"
        passive_style = f"background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_SECONDARY}; border: 1px solid {AppStyles.BORDER}; border-radius: 6px; padding: 4px 10px; font-size: 9pt;"

        self.btn_stock_daily.setStyleSheet(active_style if mode == "daily" else passive_style)
        self.btn_stock_weekly.setStyleSheet(active_style if mode == "weekly" else passive_style)
        self.btn_stock_monthly.setStyleSheet(active_style if mode == "monthly" else passive_style)
        self.btn_stock_yearly.setStyleSheet(active_style if mode == "yearly" else passive_style)
        self.btn_stock_all.setStyleSheet(active_style if mode == "all" else passive_style)

        if mode == "yearly":
            self.stock_date_edit.setDisplayFormat("yyyy")
            self.stock_date_edit.setEnabled(True)
        elif mode == "monthly":
            self.stock_date_edit.setDisplayFormat("MMMM yyyy")
            self.stock_date_edit.setEnabled(True)
        elif mode == "weekly":
            self.stock_date_edit.setDisplayFormat("dd MMMM yyyy")
            self.stock_date_edit.setEnabled(True)
        elif mode == "all":
            self.stock_date_edit.setEnabled(False)
        else:
            self.stock_date_edit.setDisplayFormat("dd MMMM yyyy dddd")
            self.stock_date_edit.setEnabled(True)

        self.load_stock_overview()

    def stock_prev_period(self):
        cur_dt = self.stock_date_edit.date().toPyDate()
        if self._stock_mode == "daily":
            new_dt = cur_dt - timedelta(days=1)
        elif self._stock_mode == "weekly":
            new_dt = cur_dt - timedelta(days=7)
        elif self._stock_mode == "monthly":
            m = cur_dt.month - 1
            y = cur_dt.year
            if m < 1:
                m = 12
                y -= 1
            new_dt = cur_dt.replace(year=y, month=m, day=1)
        elif self._stock_mode == "yearly":
            try:
                new_dt = cur_dt.replace(year=cur_dt.year - 1)
            except ValueError:
                new_dt = cur_dt.replace(year=cur_dt.year - 1, day=28)
        else:
            return
        self.stock_date_edit.setDate(QDate(new_dt.year, new_dt.month, new_dt.day))

    def stock_next_period(self):
        cur_dt = self.stock_date_edit.date().toPyDate()
        if self._stock_mode == "daily":
            new_dt = cur_dt + timedelta(days=1)
        elif self._stock_mode == "weekly":
            new_dt = cur_dt + timedelta(days=7)
        elif self._stock_mode == "monthly":
            m = cur_dt.month + 1
            y = cur_dt.year
            if m > 12:
                m = 1
                y += 1
            new_dt = cur_dt.replace(year=y, month=m, day=1)
        elif self._stock_mode == "yearly":
            try:
                new_dt = cur_dt.replace(year=cur_dt.year + 1)
            except ValueError:
                new_dt = cur_dt.replace(year=cur_dt.year + 1, day=28)
        else:
            return
        self.stock_date_edit.setDate(QDate(new_dt.year, new_dt.month, new_dt.day))

    def load_stock_overview(self):
        """Seçili zaman dilimine göre stok sayım özetlerini ve KPI kartlarını yükler"""
        if not hasattr(self, 'stock_table'):
            return

        target_date_str = self.stock_date_edit.date().toString("yyyy-MM-dd")
        data = stock_count_service.get_stock_overview(
            branch_id=self.branch_id,
            mode=self._stock_mode,
            target_date_str=target_date_str
        )

        self.lbl_stock_range_title.setText(data.get('title', ''))

        self.kpi_stock_rem_val.value_label.setText(format_currency(data.get('total_remaining_value', 0.0)))
        self.kpi_stock_sold_val.value_label.setText(format_currency(data.get('total_sold_value', 0.0)))
        self.kpi_stock_waste_val.value_label.setText(format_currency(data.get('total_waste_value', 0.0)))
        self.kpi_stock_avail_qty.value_label.setText(f"{data.get('total_available_qty', 0.0):,.1f}")
        self.kpi_stock_count.value_label.setText(f"{data.get('session_count', 0)} Sayım")

        sessions = data.get('sessions', [])
        self.stock_table.setRowCount(len(sessions))

        for r, s in enumerate(sessions):
            s_id = s.get('id')
            p_name = s.get('period_name', '')
            c_at = str(s.get('created_at', ''))[:10]
            status = s.get('status', 'Draft')
            item_count = s.get('item_count', 0)
            avail_q = s.get('total_available_qty', 0.0)
            sold_q = s.get('total_sold_qty', 0.0)
            rem_val = s.get('total_remaining_value', 0.0)
            sold_val = s.get('total_sold_value', 0.0)
            waste_q = s.get('total_waste_qty', 0.0)
            waste_val = s.get('total_waste_value', 0.0)

            # 0. Tarih / Dönem
            it_period = QTableWidgetItem(f"{c_at}  —  {p_name}")
            it_period.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it_period.setData(Qt.UserRole, s_id)
            self.stock_table.setItem(r, 0, it_period)

            # 1. Durum
            status_text = "🟢 Onaylandı" if status == 'Approved' else "🟡 Taslak"
            it_status = QTableWidgetItem(status_text)
            it_status.setTextAlignment(Qt.AlignCenter)
            it_status.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.stock_table.setItem(r, 1, it_status)

            # 2. Kalem Sayısı
            it_cnt = QTableWidgetItem(f"{item_count} Kalem")
            it_cnt.setTextAlignment(Qt.AlignCenter)
            self.stock_table.setItem(r, 2, it_cnt)

            # 3. Toplam Mevcut
            it_avail = QTableWidgetItem(f"{avail_q:,.1f}")
            it_avail.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.stock_table.setItem(r, 3, it_avail)

            # 4. Satılan / Çıkan
            it_sold = QTableWidgetItem(f"{sold_q:,.1f}")
            it_sold.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.stock_table.setItem(r, 4, it_sold)

            # 5. Kalan Stok Değeri
            it_rem = QTableWidgetItem(format_currency(rem_val))
            it_rem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_rem.setForeground(QColor(AppStyles.PRIMARY))
            it_rem.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.stock_table.setItem(r, 5, it_rem)

            # 6. Satılan Değer
            it_sval = QTableWidgetItem(format_currency(sold_val))
            it_sval.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_sval.setForeground(QColor("#38bdf8"))
            it_sval.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.stock_table.setItem(r, 6, it_sval)

            # 7. Fire / Zayiat (kısaca ve anlaşılır)
            if waste_val > 0 or waste_q > 0:
                it_waste = QTableWidgetItem(f"🔥 {waste_q:,.1f} Adet ({format_currency(waste_val)})")
                it_waste.setForeground(QColor(AppStyles.DANGER))
                it_waste.setFont(QFont("Segoe UI", 9, QFont.Bold))
            else:
                it_waste = QTableWidgetItem("✅ Fire Yok (0 ₺)")
                it_waste.setForeground(QColor(AppStyles.SUCCESS))
            it_waste.setTextAlignment(Qt.AlignCenter)
            self.stock_table.setItem(r, 7, it_waste)

            # 8. İşlemler (Detay Butonu)
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(6)

            btn_detail = QPushButton("🔍 Detay")
            btn_detail.setCursor(Qt.PointingHandCursor)
            btn_detail.setFixedHeight(26)
            btn_detail.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.PRIMARY};
                    color: {AppStyles.TEXT_ON_PRIMARY};
                    border: none;
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-weight: bold;
                    font-size: 8.5pt;
                }}
                QPushButton:hover {{
                    background-color: {AppStyles.PRIMARY_HOVER};
                }}
            """)
            btn_detail.clicked.connect(lambda _, sid=s_id: self.open_session_detail(sid))
            action_layout.addWidget(btn_detail)

            btn_del = QPushButton("🗑️")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setFixedSize(26, 26)
            btn_del.setStyleSheet(f"background: transparent; color: {AppStyles.DANGER}; border: none;")
            btn_del.setToolTip("Sayım Dönemini Sil")
            btn_del.clicked.connect(lambda _, sid=s_id, pn=p_name: self.delete_session_row(sid, pn))
            action_layout.addWidget(btn_del)

            self.stock_table.setCellWidget(r, 8, action_widget)

    def on_stock_row_double_click(self, row: int):
        it = self.stock_table.item(row, 0)
        if it:
            s_id = it.data(Qt.UserRole)
            if s_id:
                self.open_session_detail(s_id)

    def open_session_detail(self, session_id: int):
        """Detay penceresini açar"""
        dlg = StockCountDetailDialog(session_id, self.user, self.branch_id, self)
        dlg.exec_()
        self.load_stock_overview()
        self.load_waste_analytics()

    def on_open_daily_closing(self):
        """Gün sonu birleşik sayım penceresini açar"""
        cur_date_str = self.stock_date_edit.date().toString("yyyy-MM-dd")
        dlg = DailyClosingStockCountDialog(branch_id=self.branch_id, user=self.user, default_date=cur_date_str, parent=self)
        dlg.exec_()
        self.load_stock_overview()
        self.load_waste_analytics()

    def on_new_session_click(self):
        """Yeni sayım dönemi başlatma dialogu"""
        dlg = NewStockCountSessionDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            p_name = data.get("period_name")
            copy_prev = data.get("copy_from_previous", False)
            load_tpl = data.get("load_template_items", False)
            u_id = getattr(self.user, 'id', None)

            success, msg, created = stock_count_service.create_session(
                branch_id=self.branch_id,
                period_name=p_name,
                user_id=u_id,
                copy_from_previous=copy_prev,
                load_template_items=load_tpl
            )
            if success and created:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_stock_overview()
                self.open_session_detail(created.get('id'))
            else:
                QMessageBox.warning(self, "Hata", msg)

    def delete_session_row(self, session_id: int, period_name: str):
        reply = QMessageBox.question(
            self,
            "Dönemi Sil",
            f"'{period_name}' sayım dönemini ve tüm kayıtlarını silmek istediğinize emin misiniz?\n"
            "Bu işlem geri alınamaz!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = stock_count_service.delete_session(session_id)
            if ok:
                QMessageBox.information(self, "Silindi", msg)
                self.load_stock_overview()
                self.load_waste_analytics()
            else:
                QMessageBox.warning(self, "Hata", msg)

    # ==================== SEKME 2: FİRE VE ZAYİAT ANALİZİ ====================

    def setup_waste_tab(self, parent: QWidget):
        """2. Sekme: Fire ve Zayiat Analizi (Günlük / Haftalık / Aylık)"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 1. Filtre ve Zaman Dilimi Çubuğu
        filter_bar = self.create_waste_filter_bar()
        layout.addWidget(filter_bar)

        # 2. KPI Kartları Satırı
        kpi_row = self.create_waste_kpi_row()
        layout.addWidget(kpi_row)

        # 3. Alt Bölüm (Zayiat Tablosu + Sağ Panel: En Çok Fire Verenler)
        body_layout = QHBoxLayout()
        body_layout.setSpacing(14)

        # Sol: Zayiat Tablosu
        self.waste_table = QTableWidget()
        waste_headers = [
            "Tarih", "Kategori", "Ürün Adı", "Miktar", "Birim",
            "Birim Maliyet (TL)", "Fire Tutarı (TL)", "Zayiat Nedeni / Açıklama", "Sil"
        ]
        self.waste_table.setColumnCount(len(waste_headers))
        self.waste_table.setHorizontalHeaderLabels(waste_headers)
        self.waste_table.setAlternatingRowColors(True)
        self.waste_table.verticalHeader().setVisible(False)
        self.waste_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.waste_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                alternate-background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                gridline-color: {AppStyles.BORDER};
                font-size: 9.5pt;
            }}
            QHeaderView::section {{
                background-color: #1e293b;
                color: #e2e8f0;
                padding: 8px 6px;
                border: 1px solid {AppStyles.BORDER};
                font-weight: bold;
                font-size: 9pt;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
            }}
        """)
        w_hdr = self.waste_table.horizontalHeader()
        w_hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        w_hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        w_hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        w_hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        w_hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        w_hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        w_hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        w_hdr.setSectionResizeMode(7, QHeaderView.Stretch)
        w_hdr.setSectionResizeMode(8, QHeaderView.Fixed)
        self.waste_table.setColumnWidth(8, 46)

        body_layout.addWidget(self.waste_table, 7)

        # Sağ: En Çok Fire Veren Ürünler (Top 5) & Kategori Dağılım Paneli
        self.waste_summary_panel = self.create_waste_top_panel()
        body_layout.addWidget(self.waste_summary_panel, 3)

        layout.addLayout(body_layout, 1)

    def create_waste_filter_bar(self) -> QFrame:
        """Fire analizi için Günlük/Haftalık/Aylık ve Tarih seçim çubuğu"""
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 6px 12px;
            }}
        """)
        l = QHBoxLayout(bar)
        l.setContentsMargins(10, 6, 10, 6)
        l.setSpacing(8)

        lbl_mode = QLabel("Dönem Görünümü:")
        lbl_mode.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-weight: bold; font-size: 9.5pt;")
        l.addWidget(lbl_mode)

        self.btn_waste_daily = QPushButton("📅 Günlük")
        self.btn_waste_weekly = QPushButton("📆 Haftalık")
        self.btn_waste_monthly = QPushButton("🗓️ Aylık")
        self.btn_waste_yearly = QPushButton("📊 Yıllık")

        for btn in (self.btn_waste_daily, self.btn_waste_weekly, self.btn_waste_monthly, self.btn_waste_yearly):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)

        self.btn_waste_daily.clicked.connect(lambda: self.set_waste_mode("daily"))
        self.btn_waste_weekly.clicked.connect(lambda: self.set_waste_mode("weekly"))
        self.btn_waste_monthly.clicked.connect(lambda: self.set_waste_mode("monthly"))
        self.btn_waste_yearly.clicked.connect(lambda: self.set_waste_mode("yearly"))

        l.addWidget(self.btn_waste_daily)
        l.addWidget(self.btn_waste_weekly)
        l.addWidget(self.btn_waste_monthly)
        l.addWidget(self.btn_waste_yearly)

        # Ayırıcı
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setFixedHeight(24)
        sep.setStyleSheet(f"background-color: {AppStyles.BORDER};")
        l.addWidget(sep)

        # Tarih Seçici ve Oklar
        prev_btn = QPushButton("◀")
        prev_btn.setFixedSize(30, 30)
        prev_btn.setCursor(Qt.PointingHandCursor)
        prev_btn.setStyleSheet(f"background-color: {AppStyles.BG_DARK}; border: 1px solid {AppStyles.BORDER}; border-radius: 4px; color: {AppStyles.TEXT_PRIMARY};")
        prev_btn.clicked.connect(self.waste_prev_period)
        l.addWidget(prev_btn)

        self.waste_date_edit = QDateEdit()
        self.waste_date_edit.setCalendarPopup(True)
        self.waste_date_edit.setDate(QDate.currentDate())
        self.waste_date_edit.setDisplayFormat("dd MMMM yyyy dddd")
        self.waste_date_edit.setFixedHeight(30)
        self.waste_date_edit.setMinimumWidth(150)
        self.waste_date_edit.setMaximumWidth(190)
        self.waste_date_edit.setStyleSheet(f"""
            QDateEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: bold;
            }}
        """)
        self.waste_date_edit.dateChanged.connect(self.load_waste_analytics)
        l.addWidget(self.waste_date_edit)

        today_btn = QPushButton("Bugün")
        today_btn.setFixedHeight(30)
        today_btn.setCursor(Qt.PointingHandCursor)
        today_btn.setStyleSheet(f"background-color: {AppStyles.BG_DARK}; border: 1px solid {AppStyles.BORDER}; border-radius: 4px; color: {AppStyles.TEXT_PRIMARY}; padding: 0 10px;")
        today_btn.clicked.connect(lambda: self.waste_date_edit.setDate(QDate.currentDate()))
        l.addWidget(today_btn)

        next_btn = QPushButton("▶")
        next_btn.setFixedSize(30, 30)
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.setStyleSheet(f"background-color: {AppStyles.BG_DARK}; border: 1px solid {AppStyles.BORDER}; border-radius: 4px; color: {AppStyles.TEXT_PRIMARY};")
        next_btn.clicked.connect(self.waste_next_period)
        l.addWidget(next_btn)

        l.addStretch()

        self.lbl_waste_range_title = QLabel("")
        self.lbl_waste_range_title.setStyleSheet(f"color: {AppStyles.PRIMARY}; font-weight: bold; font-size: 10pt;")
        l.addWidget(self.lbl_waste_range_title)

        btn_export_waste = QPushButton("📊 Excel'e Aktar")
        btn_export_waste.setCursor(Qt.PointingHandCursor)
        btn_export_waste.setFixedHeight(30)
        btn_export_waste.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 4px;
                padding: 0 12px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        btn_export_waste.clicked.connect(self.export_waste_to_excel)
        l.addWidget(btn_export_waste)

        return bar

    def create_waste_kpi_row(self) -> QWidget:
        """Fire analizi KPI kartları satırı"""
        row = QWidget()
        l = QHBoxLayout(row)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(12)

        self.kpi_waste_val = self.create_card_widget("🔥 Toplam Fire / Zayiat Tutarı", "0,00 ₺", AppStyles.DANGER)
        self.kpi_waste_qty = self.create_card_widget("📦 Toplam Zayiat Miktarı", "0,00", AppStyles.WARNING)
        self.kpi_waste_ratio = self.create_card_widget("📉 Ciroya Fire Oranı", "% 0.00", AppStyles.CYAN)
        self.kpi_waste_top = self.create_card_widget("⚠️ En Çok Fire Veren Ürün", "—", AppStyles.TEXT_PRIMARY)

        l.addWidget(self.kpi_waste_val)
        l.addWidget(self.kpi_waste_qty)
        l.addWidget(self.kpi_waste_ratio)
        l.addWidget(self.kpi_waste_top)

        return row

    def create_waste_top_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        l = QVBoxLayout(panel)
        l.setContentsMargins(10, 10, 10, 10)
        l.setSpacing(10)

        title = QLabel("🏆 En Çok Ziyan Olan Ürünler")
        title.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        l.addWidget(title)

        sub = QLabel("Üretim planlamasını optimize etmek için:")
        sub.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_SECONDARY};")
        l.addWidget(sub)

        self.waste_top_list_widget = QWidget()
        self.waste_top_list_layout = QVBoxLayout(self.waste_top_list_widget)
        self.waste_top_list_layout.setContentsMargins(0, 0, 0, 0)
        self.waste_top_list_layout.setSpacing(6)
        l.addWidget(self.waste_top_list_widget)

        l.addStretch()

        cat_title = QLabel("📂 Kategori Bazında Zayiat")
        cat_title.setStyleSheet(f"font-size: 10.5pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        l.addWidget(cat_title)

        self.waste_cat_list_widget = QWidget()
        self.waste_cat_list_layout = QVBoxLayout(self.waste_cat_list_widget)
        self.waste_cat_list_layout.setContentsMargins(0, 0, 0, 0)
        self.waste_cat_list_layout.setSpacing(4)
        l.addWidget(self.waste_cat_list_widget)

        return panel

    def set_waste_mode(self, mode: str):
        """Zayiat görünüm modunu (günlük/haftalık/aylık/yıllık) değiştirir"""
        self._waste_mode = mode
        active_style = f"background-color: {AppStyles.PRIMARY}; color: {AppStyles.TEXT_ON_PRIMARY}; font-weight: bold; border-radius: 6px; padding: 4px 10px; font-size: 9pt;"
        passive_style = f"background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_SECONDARY}; border: 1px solid {AppStyles.BORDER}; border-radius: 6px; padding: 4px 10px; font-size: 9pt;"

        self.btn_waste_daily.setStyleSheet(active_style if mode == "daily" else passive_style)
        self.btn_waste_weekly.setStyleSheet(active_style if mode == "weekly" else passive_style)
        self.btn_waste_monthly.setStyleSheet(active_style if mode == "monthly" else passive_style)
        self.btn_waste_yearly.setStyleSheet(active_style if mode == "yearly" else passive_style)

        if mode == "yearly":
            self.waste_date_edit.setDisplayFormat("yyyy")
        elif mode == "monthly":
            self.waste_date_edit.setDisplayFormat("MMMM yyyy")
        elif mode == "weekly":
            self.waste_date_edit.setDisplayFormat("dd MMMM yyyy")
        else:
            self.waste_date_edit.setDisplayFormat("dd MMMM yyyy dddd")

        self.load_waste_analytics()

    def waste_prev_period(self):
        cur_dt = self.waste_date_edit.date().toPyDate()
        if self._waste_mode == "daily":
            new_dt = cur_dt - timedelta(days=1)
        elif self._waste_mode == "weekly":
            new_dt = cur_dt - timedelta(days=7)
        elif self._waste_mode == "monthly":
            m = cur_dt.month - 1
            y = cur_dt.year
            if m < 1:
                m = 12
                y -= 1
            new_dt = cur_dt.replace(year=y, month=m, day=1)
        elif self._waste_mode == "yearly":
            try:
                new_dt = cur_dt.replace(year=cur_dt.year - 1)
            except ValueError:
                new_dt = cur_dt.replace(year=cur_dt.year - 1, day=28)
        else:
            return
        self.waste_date_edit.setDate(QDate(new_dt.year, new_dt.month, new_dt.day))

    def waste_next_period(self):
        cur_dt = self.waste_date_edit.date().toPyDate()
        if self._waste_mode == "daily":
            new_dt = cur_dt + timedelta(days=1)
        elif self._waste_mode == "weekly":
            new_dt = cur_dt + timedelta(days=7)
        elif self._waste_mode == "monthly":
            m = cur_dt.month + 1
            y = cur_dt.year
            if m > 12:
                m = 1
                y += 1
            new_dt = cur_dt.replace(year=y, month=m, day=1)
        elif self._waste_mode == "yearly":
            try:
                new_dt = cur_dt.replace(year=cur_dt.year + 1)
            except ValueError:
                new_dt = cur_dt.replace(year=cur_dt.year + 1, day=28)
        else:
            return
        self.waste_date_edit.setDate(QDate(new_dt.year, new_dt.month, new_dt.day))

    def load_waste_analytics(self):
        """Seçili zaman dilimine göre zayiat verilerini yükle ve ekrana bas"""
        if not hasattr(self, 'waste_table'):
            return

        target_date_str = self.waste_date_edit.date().toString("yyyy-MM-dd")
        data = stock_count_service.get_waste_analytics(
            branch_id=self.branch_id,
            mode=self._waste_mode,
            target_date_str=target_date_str
        )

        self.lbl_waste_range_title.setText(data.get('title', ''))

        tot_val = data.get('total_waste_value', 0.0)
        tot_qty = data.get('total_waste_qty', 0.0)
        ratio = data.get('waste_ratio', 0.0)
        top_prods = data.get('top_products', [])

        self.kpi_waste_val.value_label.setText(format_currency(tot_val))
        self.kpi_waste_qty.value_label.setText(f"{tot_qty:,.2f}")
        self.kpi_waste_ratio.value_label.setText(f"% {ratio:.2f}")

        if top_prods:
            first_p = top_prods[0]
            self.kpi_waste_top.value_label.setText(f"{first_p['product_name']} ({format_currency(first_p['val'])})")
        else:
            self.kpi_waste_top.value_label.setText("— (Zayiat Yok)")

        records = data.get('records', [])
        self.waste_table.setRowCount(len(records))

        for r, rec in enumerate(records):
            r_id = rec.get('id')
            d_str = str(rec.get('date', ''))
            cat = str(rec.get('category', ''))
            pname = str(rec.get('product_name', ''))
            qty = float(rec.get('quantity') or 0.0)
            unit = str(rec.get('unit', 'Adet'))
            cost = float(rec.get('unit_cost') or 0.0)
            val = float(rec.get('waste_value') or 0.0)
            reason = str(rec.get('reason', ''))

            it_date = QTableWidgetItem(d_str)
            it_date.setTextAlignment(Qt.AlignCenter)
            self.waste_table.setItem(r, 0, it_date)

            self.waste_table.setItem(r, 1, QTableWidgetItem(cat))

            it_name = QTableWidgetItem(pname)
            it_name.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.waste_table.setItem(r, 2, it_name)

            it_qty = QTableWidgetItem(format_num(qty))
            it_qty.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.waste_table.setItem(r, 3, it_qty)

            it_unit = QTableWidgetItem(unit)
            it_unit.setTextAlignment(Qt.AlignCenter)
            self.waste_table.setItem(r, 4, it_unit)

            it_cost = QTableWidgetItem(format_num(cost))
            it_cost.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.waste_table.setItem(r, 5, it_cost)

            it_val = QTableWidgetItem(format_currency(val))
            it_val.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_val.setForeground(QColor(AppStyles.DANGER))
            it_val.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.waste_table.setItem(r, 6, it_val)

            self.waste_table.setItem(r, 7, QTableWidgetItem(reason))

            del_btn = QPushButton("🗑️")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setFixedSize(28, 26)
            del_btn.setStyleSheet(f"background: transparent; color: {AppStyles.DANGER}; border: none;")
            del_btn.clicked.connect(lambda _, mid=r_id: self.delete_waste_row(mid))
            self.waste_table.setCellWidget(r, 8, del_btn)

        # Sağ Top 5 Listesi
        while self.waste_top_list_layout.count():
            item = self.waste_top_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not top_prods:
            lbl_none = QLabel("Seçili dönemde kayıtlı fire bulunmuyor.")
            lbl_none.setStyleSheet(f"color: {AppStyles.TEXT_MUTED}; font-size: 8.5pt; font-style: italic;")
            self.waste_top_list_layout.addWidget(lbl_none)
        else:
            for rank, tp in enumerate(top_prods, 1):
                card = QFrame()
                card.setStyleSheet(f"background-color: {AppStyles.BG_DARK}; border: 1px solid {AppStyles.BORDER}; border-radius: 6px; padding: 6px;")
                c_l = QHBoxLayout(card)
                c_l.setContentsMargins(6, 4, 6, 4)
                lbl_rank = QLabel(f"#{rank}")
                lbl_rank.setStyleSheet(f"color: {AppStyles.PRIMARY}; font-weight: bold; font-size: 9pt;")
                c_l.addWidget(lbl_rank)

                lbl_pn = QLabel(f"{tp['product_name']}\n{tp['qty']:,.1f} {tp['unit']}")
                lbl_pn.setStyleSheet(f"color: {AppStyles.TEXT_PRIMARY}; font-size: 8.5pt;")
                c_l.addWidget(lbl_pn, 1)

                lbl_tl = QLabel(format_currency(tp['val']))
                lbl_tl.setStyleSheet(f"color: {AppStyles.DANGER}; font-weight: bold; font-size: 9pt;")
                c_l.addWidget(lbl_tl)
                self.waste_top_list_layout.addWidget(card)

        # Kategori Dağılım Listesi
        while self.waste_cat_list_layout.count():
            item = self.waste_cat_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cat_breakdown = data.get('category_breakdown', [])
        for cb in cat_breakdown:
            row_w = QWidget()
            rw_l = QHBoxLayout(row_w)
            rw_l.setContentsMargins(0, 2, 0, 2)
            c_name = QLabel(f"• {cb['category']}")
            c_name.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 8.5pt;")
            rw_l.addWidget(c_name, 1)

            c_val = QLabel(format_currency(cb['val']))
            c_val.setStyleSheet(f"color: {AppStyles.TEXT_PRIMARY}; font-weight: bold; font-size: 8.5pt;")
            rw_l.addWidget(c_val)
            self.waste_cat_list_layout.addWidget(row_w)

    def delete_waste_row(self, movement_id: int):
        """Zayiat hareket kaydını siler"""
        reply = QMessageBox.question(
            self,
            "Fire Kaydını Sil",
            "Bu zayiat hareket kaydını silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = stock_count_service.delete_movement(movement_id)
            if ok:
                self.load_waste_analytics()
                self.load_stock_overview()
            else:
                QMessageBox.warning(self, "Hata", msg)

    def export_waste_to_excel(self):
        """Mevcut zayiat raporunu Excel dosyası olarak kaydeder"""
        target_date_str = self.waste_date_edit.date().toString("yyyy-MM-dd")
        data = stock_count_service.get_waste_analytics(
            branch_id=self.branch_id,
            mode=self._waste_mode,
            target_date_str=target_date_str
        )
        records = data.get('records', [])
        if not records:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak zayiat kaydı bulunamadı.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Zayiat Raporunu Kaydet", f"Zayiat_Raporu_{self._waste_mode}_{target_date_str}.xlsx", "Excel Dosyası (*.xlsx)"
        )
        if not file_path:
            return

        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Zayiat Raporu"

            headers = ["Tarih", "Kategori", "Ürün Adı", "Miktar", "Birim", "Birim Maliyet (TL)", "Fire Tutarı (TL)", "Zayiat Nedeni"]
            ws.append(headers)
            for r in records:
                ws.append([
                    str(r.get('date', '')),
                    str(r.get('category', '')),
                    str(r.get('product_name', '')),
                    float(r.get('quantity') or 0.0),
                    str(r.get('unit', '')),
                    float(r.get('unit_cost') or 0.0),
                    float(r.get('waste_value') or 0.0),
                    str(r.get('reason', ''))
                ])
            wb.save(file_path)
            QMessageBox.information(self, "Başarılı", f"Zayiat raporu başarıyla kaydedildi:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel kaydedilirken hata oluştu:\n{e}")

    def on_main_tab_changed(self, index: int):
        """Sekmeler arası geçişte ilgili sekmenin verilerini tazele"""
        if index == 0:
            self.load_stock_overview()
        elif index == 1:
            self.load_waste_analytics()
