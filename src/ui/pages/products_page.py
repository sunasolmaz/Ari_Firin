# src/ui/pages/products_page.py
"""
Şube Stok & Sevkiyat Yönetimi
- Şube Canlı Ürün Stokları ve Kalan Miktarlar
- İmalathaneden Gelen Günlük/Haftalık Sevkiyatlar
- Merkez Depodan Gelen Malzeme & Ambalaj Sevkiyatları
- Hızlı Stok Düzenleme / Sayım ve Ürün Yönetimi
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QMessageBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QTextEdit, QScrollArea, QGraphicsDropShadowEffect,
    QHeaderView, QTabWidget, QDateEdit, QSizePolicy
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont
from datetime import datetime, timedelta
from typing import Optional

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ...services.production_service import production_service
from ...services.warehouse_service import warehouse_service
from ..styles import AppStyles


class QuickStockAdjustDialog(QDialog):
    """Şube için Hızlı Stok Düzeltme / Sayım Penceresi"""

    def __init__(self, product_id: int, product_name: str, current_stock: float, unit: str = "Adet", parent=None):
        super().__init__(parent)
        self.product_id = product_id
        self.setWindowTitle(f"🔢 Hızlı Stok Düzenleme — {product_name}")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
            QDoubleSpinBox, QLineEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11pt;
                font-weight: bold;
            }}
            QDoubleSpinBox:focus, QLineEdit:focus {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        self.init_ui(product_name, current_stock, unit)

    def init_ui(self, product_name: str, current_stock: float, unit: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel(f"📦 {product_name}")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        layout.addWidget(title)

        curr_info = QLabel(f"Mevcut Kayıtlı Stok: <b>{current_stock:g} {unit}</b>")
        curr_info.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        layout.addWidget(curr_info)

        layout.addWidget(QLabel("Yeni Güncel Stok Miktarı:"))
        self.stock_spin = QDoubleSpinBox()
        self.stock_spin.setRange(0, 999999999.999)
        self.stock_spin.setDecimals(2)
        self.stock_spin.setValue(float(current_stock))
        self.stock_spin.setSuffix(f" {unit}")
        layout.addWidget(self.stock_spin)

        layout.addWidget(QLabel("Düzeltme / Sayım Nedeni:"))

        # Hızlı Hazır Sebepler (Adım 4)
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(6)
        presets = [
            ("🥖 Akşam Sayımı", "Gün Sonu / Akşam Sayımı"),
            ("⚠️ Bayat / Fire", "Bayat / Zayiat / Fire Ayrıldı"),
            ("📦 İmalat Eksiği", "İmalathane Sevkiyat Eksiği"),
            ("🔄 Hatalı Giriş", "Kasa Satış Düzeltmesi"),
        ]
        for btn_text, val_text in presets:
            p_btn = QPushButton(btn_text)
            p_btn.setCursor(Qt.PointingHandCursor)
            p_btn.setFixedHeight(28)
            p_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.BG_DARK};
                    color: {AppStyles.TEXT_SECONDARY};
                    border: 1px solid {AppStyles.BORDER};
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 8.5pt;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    border-color: {AppStyles.PRIMARY};
                    color: {AppStyles.PRIMARY};
                    background-color: {AppStyles.SIDEBAR_HOVER};
                }}
            """)
            p_btn.clicked.connect(lambda ch, v=val_text: self.reason_input.setText(v))
            preset_layout.addWidget(p_btn)
        layout.addLayout(preset_layout)

        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("Yukarıdan hazır sebep seçebilir veya serbest yazabilirsiniz...")
        layout.addWidget(self.reason_input)

        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Save).setText("💾 Stoğu Güncelle")
        btn_box.button(QDialogButtonBox.Cancel).setText("❌ İptal")
        btn_box.accepted.connect(self.save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def save(self):
        new_val = self.stock_spin.value()
        try:
            db.execute_query("""
                UPDATE Products 
                SET stock_quantity = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (new_val, self.product_id))
            logger.info(f"🔢 Şube stoğu güncellendi: Ürün ID={self.product_id}, Yeni Stok={new_val}")
            self.accept()
        except Exception as e:
            logger.error(f"Hızlı stok düzeltme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Stok güncellenemedi:\n{e}")


class ProductsPage(QWidget):
    """Şube Stok & Sevkiyat Yönetim Sayfası"""

    def __init__(self, user: User, branch_id: int, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window

        self.init_ui()
        self.load_all_data()

    def init_ui(self):
        self.setObjectName("ProductsPage")
        self.setStyleSheet(f"#ProductsPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # ==================== ÜST BAŞLIK BARI ====================
        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(2)

        title = QLabel("📦 Şube Stok & Sevkiyat Takibi")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)

        subtitle = QLabel("Şubedeki canlı ürün stokları, kalan miktarlar, imalat ve depodan gelen sevkiyatlar")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        top_bar.addLayout(left)
        top_bar.addStretch()

        refresh_all_btn = QPushButton("🔄 Tümünü Yenile")
        refresh_all_btn.setCursor(Qt.PointingHandCursor)
        refresh_all_btn.setFixedHeight(34)
        refresh_all_btn.clicked.connect(self.load_all_data)
        refresh_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.BG_LIGHT};
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        top_bar.addWidget(refresh_all_btn)

        new_btn = QPushButton("➕  Yeni Ürün Ekle")
        new_btn.clicked.connect(self.new_product)
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.setFixedHeight(34)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 9.5pt;
                padding: 4px 16px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
            }}
        """)
        top_bar.addWidget(new_btn)

        layout.addLayout(top_bar)

        # ==================== SEKMELER (TABS) ====================
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {AppStyles.BORDER};
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: transparent;
                color: {AppStyles.TEXT_SECONDARY};
                padding: 10px 20px;
                margin-right: 4px;
                border: none;
                border-bottom: 2px solid transparent;
                font-weight: 600;
                font-size: 10pt;
            }}
            QTabBar::tab:selected {{
                color: {AppStyles.PRIMARY};
                border-bottom: 2px solid {AppStyles.PRIMARY};
            }}
            QTabBar::tab:hover:!selected {{
                color: {AppStyles.TEXT_PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """)

        # Sekme 1: Şube Canlı Stokları
        self.tab_stock = QWidget()
        self._build_stock_tab()
        self.tabs.addTab(self.tab_stock, "📦 Şube Mevcut Stokları (Canlı Kalanlar)")

        # Sekme 2: İmalathaneden Gelen Sevkiyatlar
        self.tab_production_shipments = QWidget()
        self._build_production_shipments_tab()
        self.tabs.addTab(self.tab_production_shipments, "🚚 İmalathaneden Gelen Sevkiyatlar")

        # Sekme 3: Merkez Depodan Gelen Malzemeler
        self.tab_warehouse_dispatches = QWidget()
        self._build_warehouse_dispatches_tab()
        self.tabs.addTab(self.tab_warehouse_dispatches, "🏬 Merkez Depodan Gelenler (Ambalaj & Malzeme)")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    # ==================== SEKME 1: ŞUBE CANLI STOKLARI ====================

    def _build_stock_tab(self):
        layout = QVBoxLayout(self.tab_stock)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)

        # KPI Özet Kartları (4 Adet - Tıklanabilir Filtreler - Adım 3)
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(10)

        self.kpi_total_products = self._create_mini_card(
            "🏷️", "Toplam Çeşit", "0 Ürün", AppStyles.CYAN, self._reset_filters_and_reload
        )
        self.kpi_total_stock = self._create_mini_card(
            "📦", "Toplam Kalan Stok", "0 Adet", AppStyles.GREEN, self._filter_sufficient_and_reload
        )
        self.kpi_incoming_today = self._create_mini_card(
            "🚚", "Bugün İmalattan Gelen", "0 Adet", AppStyles.PURPLE, self._view_incoming_shipments
        )
        self.kpi_critical_stock = self._create_mini_card(
            "⚠️", "Kritik / Biten Ürün", "0 Ürün", AppStyles.RED, self._filter_critical_and_reload
        )

        kpi_layout.addWidget(self.kpi_total_products)
        kpi_layout.addWidget(self.kpi_total_stock)
        kpi_layout.addWidget(self.kpi_incoming_today)
        kpi_layout.addWidget(self.kpi_critical_stock)
        layout.addLayout(kpi_layout)

        # Filtreleme Barı
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Ürün adı veya kodu ile ara...")
        self.search_input.setMinimumHeight(38)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 10pt;
            }}
            QLineEdit:focus {{ border-color: {AppStyles.PRIMARY}; }}
        """)
        self.search_input.textChanged.connect(self.load_products)
        filter_bar.addWidget(self.search_input, 3)

        self.category_filter = QComboBox()
        self.category_filter.addItems(["Tüm Kategoriler", "Ekmek", "Simit & Poğaça", "Unlu Mamül", "Tatlı", "Pasta", "İçecek", "Diğer"])
        self.category_filter.setMinimumHeight(38)
        self.category_filter.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
        """)
        self.category_filter.currentTextChanged.connect(self.load_products)
        filter_bar.addWidget(self.category_filter, 1)

        self.health_filter = QComboBox()
        self.health_filter.addItems(["Tüm Stok Durumları", "🟢 Yeterli Stok", "🟡 Kritik Stok", "🔴 Tükendi (0 Stok)"])
        self.health_filter.setMinimumHeight(38)
        self.health_filter.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
        """)
        self.health_filter.currentTextChanged.connect(self.load_products)
        filter_bar.addWidget(self.health_filter, 1)

        layout.addLayout(filter_bar)

        # Tablo (10 Kolon: Bugün Gelen ve Bugün Satılan eklendi - Adım 2)
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            'Kod', 'Ürün Adı', 'Kategori', 'Birim', 'Satış Fiyatı',
            'Bugün Gelen 🚚', 'Bugün Satılan 🧾', 'Kalan Stok 📦', 'Kritik Eşik', 'Durum'
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setVisible(True)
        self.table.horizontalHeader().setFixedHeight(36)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemDoubleClicked.connect(self.edit_product)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                gridline-color: {AppStyles.BORDER};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{ padding: 8px 10px; border: none; font-size: 10pt; }}
            QTableWidget::item:selected {{ background-color: {AppStyles.PRIMARY}30; }}
            QHeaderView {{ background-color: {AppStyles.BG_DARKEST}; border: none; }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARKEST};
                color: #FFFFFF;
                padding: 0 10px;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                font-weight: bold;
                font-size: 9.5pt;
                height: 36px;
            }}
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        # Boş Durum Kutusu (Adım 5)
        self.stock_empty_box = self._create_empty_state(
            "📦",
            "Arama Kriterlerine Uygun Ürün Bulunamadı",
            "Filtreleri sıfırlayarak veya arama terimini değiştirerek tekrar deneyebilirsiniz."
        )
        layout.addWidget(self.stock_empty_box)

        # Alt Butonlar
        bottom_bar = QHBoxLayout()
        self.total_label = QLabel("Toplam: 0 ürün listelendi")
        self.total_label.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 10pt;")
        bottom_bar.addWidget(self.total_label)
        bottom_bar.addStretch()

        adjust_btn = QPushButton("🔢 Hızlı Stok Düzelt / Sayım")
        adjust_btn.clicked.connect(self.quick_adjust_stock)
        adjust_btn.setCursor(Qt.PointingHandCursor)
        adjust_btn.setFixedHeight(34)
        adjust_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.CYAN};
                border: 1px solid {AppStyles.CYAN};
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.CYAN};
                color: white;
            }}
        """)
        bottom_bar.addWidget(adjust_btn)

        edit_btn = QPushButton("✏️ Ürün Düzenle")
        edit_btn.clicked.connect(self.edit_product)
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.setFixedHeight(34)
        edit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.ORANGE};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 16px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{ background-color: #d97706; }}
        """)
        bottom_bar.addWidget(edit_btn)

        delete_btn = QPushButton("🗑️ Sil")
        delete_btn.clicked.connect(self.delete_product)
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setFixedHeight(34)
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.RED};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 16px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{ background-color: #dc2626; }}
        """)
        bottom_bar.addWidget(delete_btn)

        layout.addLayout(bottom_bar)

    # ==================== SEKME 2: İMALATHANEDEN GELEN SEVKİYATLAR ====================

    def _build_production_shipments_tab(self):
        layout = QVBoxLayout(self.tab_production_shipments)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)

        # İmalat KPI Kartları
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(10)

        self.kpi_prod_ship_count = self._create_mini_card("🚚", "Bugün Gelen Sefer", "0 Sevk", AppStyles.PRIMARY)
        self.kpi_prod_total_qty = self._create_mini_card("🍞", "Bugün Gelen Toplam Ürün", "0 Adet", AppStyles.GREEN)
        self.kpi_prod_total_amt = self._create_mini_card("💰", "Bugün Gelen Tutar", "0.00 ₺", AppStyles.PURPLE)

        kpi_layout.addWidget(self.kpi_prod_ship_count)
        kpi_layout.addWidget(self.kpi_prod_total_qty)
        kpi_layout.addWidget(self.kpi_prod_total_amt)
        layout.addLayout(kpi_layout)

        # Tarih Filtresi
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        filter_bar.addWidget(QLabel("📅 Tarih Aralığı:"))
        self.prod_period_combo = QComboBox()
        self.prod_period_combo.addItems(["Bugün", "Son 7 Gün", "Bu Ay", "Tüm Zamanlar"])
        self.prod_period_combo.setFixedHeight(36)
        self.prod_period_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
        """)
        self.prod_period_combo.currentTextChanged.connect(self.load_production_shipments)
        filter_bar.addWidget(self.prod_period_combo)
        filter_bar.addStretch()

        refresh_prod_btn = QPushButton("🔄 Sevkiyatları Yenile")
        refresh_prod_btn.setCursor(Qt.PointingHandCursor)
        refresh_prod_btn.setFixedHeight(34)
        refresh_prod_btn.clicked.connect(self.load_production_shipments)
        refresh_prod_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
        """)
        filter_bar.addWidget(refresh_prod_btn)
        layout.addLayout(filter_bar)

        # İmalat Sevkiyat Tablosu
        self.prod_table = QTableWidget()
        self.prod_table.setColumnCount(8)
        self.prod_table.setHorizontalHeaderLabels([
            'Sevk No', 'Tarih', 'Sevk Edilen Ürün', 'Miktar', 'Birim Fiyat', 'Toplam Tutar', 'Durum', 'Sürücü / Sevk Notu'
        ])
        self.prod_table.setAlternatingRowColors(True)
        self.prod_table.verticalHeader().setVisible(False)
        self.prod_table.verticalHeader().setDefaultSectionSize(44)
        self.prod_table.horizontalHeader().setVisible(True)
        self.prod_table.horizontalHeader().setFixedHeight(36)
        self.prod_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.prod_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                gridline-color: {AppStyles.BORDER};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{ padding: 8px 10px; border: none; font-size: 10pt; }}
            QTableWidget::item:selected {{ background-color: {AppStyles.PRIMARY}30; }}
            QHeaderView {{ background-color: {AppStyles.BG_DARKEST}; border: none; }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARKEST};
                color: #FFFFFF;
                padding: 0 10px;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                font-weight: bold;
                font-size: 9.5pt;
                height: 36px;
            }}
        """)
        self.prod_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.prod_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.prod_table)

        # Boş Durum Kutusu (Adım 5)
        self.prod_empty_box = self._create_empty_state(
            "🚚",
            "Bu Dönemde İmalathaneden Gelen Sevkiyat Bulunmuyor",
            "Seçtiğiniz tarih aralığında bu şubeye henüz imalat sevkiyatı kaydedilmemiş."
        )
        layout.addWidget(self.prod_empty_box)

    # ==================== SEKME 3: MERKEZ DEPODAN GELENLER ====================

    def _build_warehouse_dispatches_tab(self):
        layout = QVBoxLayout(self.tab_warehouse_dispatches)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)

        # Depo KPI Kartları
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(10)

        self.kpi_wh_total_items = self._create_mini_card("🏬", "Depodan Gelen Toplam Malzeme", "0 Kalem", AppStyles.CYAN)
        self.kpi_wh_last_date = self._create_mini_card("📅", "Son Geliş Tarihi", "-", AppStyles.ORANGE)

        kpi_layout.addWidget(self.kpi_wh_total_items)
        kpi_layout.addWidget(self.kpi_wh_last_date)
        layout.addLayout(kpi_layout)

        # Tarih Filtresi
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        filter_bar.addWidget(QLabel("📅 Tarih Aralığı:"))
        self.wh_period_combo = QComboBox()
        self.wh_period_combo.addItems(["Tüm Zamanlar", "Bugün", "Son 7 Gün", "Bu Ay"])
        self.wh_period_combo.setFixedHeight(36)
        self.wh_period_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
        """)
        self.wh_period_combo.currentTextChanged.connect(self.load_warehouse_dispatches)
        filter_bar.addWidget(self.wh_period_combo)
        filter_bar.addStretch()

        refresh_wh_btn = QPushButton("🔄 Depo Kayıtlarını Yenile")
        refresh_wh_btn.setCursor(Qt.PointingHandCursor)
        refresh_wh_btn.setFixedHeight(34)
        refresh_wh_btn.clicked.connect(self.load_warehouse_dispatches)
        refresh_wh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
        """)
        filter_bar.addWidget(refresh_wh_btn)
        layout.addLayout(filter_bar)

        # Depo Sevkiyat Tablosu
        self.wh_table = QTableWidget()
        self.wh_table.setColumnCount(6)
        self.wh_table.setHorizontalHeaderLabels([
            'İrsaliye / Belge No', 'Tarih', 'Malzeme / Ürün Adı', 'Kategori', 'Sevk Miktarı', 'Açıklama / Sevk Notu'
        ])
        self.wh_table.setAlternatingRowColors(True)
        self.wh_table.verticalHeader().setVisible(False)
        self.wh_table.verticalHeader().setDefaultSectionSize(44)
        self.wh_table.horizontalHeader().setVisible(True)
        self.wh_table.horizontalHeader().setFixedHeight(36)
        self.wh_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.wh_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                gridline-color: {AppStyles.BORDER};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{ padding: 8px 10px; border: none; font-size: 10pt; }}
            QTableWidget::item:selected {{ background-color: {AppStyles.PRIMARY}30; }}
            QHeaderView {{ background-color: {AppStyles.BG_DARKEST}; border: none; }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARKEST};
                color: #FFFFFF;
                padding: 0 10px;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                font-weight: bold;
                font-size: 9.5pt;
                height: 36px;
            }}
        """)
        self.wh_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.wh_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.wh_table)

        # Boş Durum Kutusu (Adım 5)
        self.wh_empty_box = self._create_empty_state(
            "🏬",
            "Bu Dönemde Merkez Depodan Gelen Malzeme Bulunmuyor",
            "Merkez depodan (ambalaj, sarf malzeme vb.) bu şubeye sevk kaydı bulunmamaktadır."
        )
        layout.addWidget(self.wh_empty_box)

    # ==================== VERİ YÜKLEME ====================

    def load_all_data(self):
        """Tüm sekmelerdeki verileri tazeler"""
        self.load_products()
        self.load_production_shipments()
        self.load_warehouse_dispatches()

    def _reset_filters_and_reload(self):
        """Tüm filtreleri sıfırlar ve listeler (Adım 3)"""
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)

        self.category_filter.blockSignals(True)
        self.category_filter.setCurrentIndex(0)
        self.category_filter.blockSignals(False)

        self.health_filter.blockSignals(True)
        self.health_filter.setCurrentIndex(0)
        self.health_filter.blockSignals(False)

        self.load_products()

    def _filter_sufficient_and_reload(self):
        """Sadece yeterli stokları filtreler (Adım 3)"""
        self.health_filter.blockSignals(True)
        self.health_filter.setCurrentText("🟢 Yeterli Stok")
        self.health_filter.blockSignals(False)
        self.load_products()

    def _view_incoming_shipments(self):
        """İmalattan gelen sevkiyatlar sekmesine geçer (Adım 3)"""
        self.tabs.setCurrentIndex(1)

    def _filter_critical_and_reload(self):
        """Kritik stokları filtreler (Adım 3)"""
        self.health_filter.blockSignals(True)
        self.health_filter.setCurrentText("🟡 Kritik Stok")
        self.health_filter.blockSignals(False)
        self.load_products()

    def _create_empty_state(self, icon: str, title: str, subtitle: str) -> QFrame:
        """Modern, bilgilendirici boş durum kartı (Adım 5)"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px dashed {AppStyles.BORDER};
                border-radius: 10px;
                padding: 40px 20px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        lay = QVBoxLayout(frame)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(6)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 32pt;")
        lay.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        lay.addWidget(title_lbl)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setStyleSheet(f"font-size: 9.5pt; color: {AppStyles.TEXT_MUTED};")
        lay.addWidget(sub_lbl)

        frame.hide()
        return frame

    def _create_mini_card(self, icon: str, title: str, val: str, color: str, click_callback=None) -> QFrame:
        """Ferah, okunaklı ve tıklanabilir gösterge kartı"""
        card = QFrame()
        card.setFixedHeight(82)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if click_callback:
            card.setCursor(Qt.PointingHandCursor)
            card.mousePressEvent = lambda ev: click_callback() if ev.button() == Qt.LeftButton else None

        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-left: 4px solid {color};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-color: {color};
                background-color: {AppStyles.BG_LIGHT};
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        lay = QVBoxLayout(card)
        lay.setSpacing(4)
        lay.setContentsMargins(14, 10, 14, 10)

        # Üst Satır: İkon + Başlık (+ Varsa Tıklama İpucu)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 11pt;")
        top_row.addWidget(icon_lbl)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 9.5pt; color: {AppStyles.TEXT_SECONDARY}; font-weight: 600;")
        top_row.addWidget(t_lbl)

        top_row.addStretch()

        if click_callback:
            hint_lbl = QLabel("Filtrele 🔍")
            hint_lbl.setStyleSheet(f"""
                font-size: 8.5pt;
                color: {color};
                font-weight: bold;
                background-color: {color}18;
                border-radius: 4px;
                padding: 2px 6px;
            """)
            top_row.addWidget(hint_lbl)

        lay.addLayout(top_row)

        # Alt Satır: Sayısal Değer
        v_lbl = QLabel(val)
        v_lbl.setObjectName("cardVal")
        v_lbl.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {color};")
        lay.addWidget(v_lbl)

        return card

    def load_products(self):
        """Sekme 1: Şube ürünlerini ve canlı stoklarını yükle"""
        try:
            search = self.search_input.text().strip()
            cat = self.category_filter.currentText() if hasattr(self, 'category_filter') else "Tüm Kategoriler"
            health = self.health_filter.currentText() if hasattr(self, 'health_filter') else "Tüm Stok Durumları"

            query = "SELECT * FROM Products WHERE branch_id = %s AND is_active = TRUE"
            params = [self.branch_id]

            if search:
                query += " AND (name ILIKE %s OR product_code ILIKE %s OR barcode ILIKE %s)"
                params.extend([f"%{search}%"] * 3)

            if cat and not cat.startswith("Tüm"):
                query += " AND category ILIKE %s"
                params.append(f"%{cat}%")

            if "Kritik" in health:
                query += " AND stock_quantity > 0 AND stock_quantity <= critical_stock"
            elif "Tükendi" in health:
                query += " AND stock_quantity <= 0"
            elif "Yeterli" in health:
                query += " AND stock_quantity > critical_stock"

            query += " ORDER BY stock_quantity ASC, name ASC"
            products = db.fetch_all(query, tuple(params))

            self.table.setRowCount(0)
            total_stock_qty = 0.0
            critical_prod_count = 0

            # Şubenin genel ürün sayılarını almak için ek sorgu
            all_prods = db.fetch_all("SELECT stock_quantity, critical_stock FROM Products WHERE branch_id = %s AND is_active = TRUE", (self.branch_id,))
            for ap in (all_prods or []):
                sq = float(ap.get('stock_quantity') or 0)
                cq = float(ap.get('critical_stock') or 1)
                total_stock_qty += sq
                if sq <= cq:
                    critical_prod_count += 1

            # 1. Bugün İmalathaneden Gelenler Haritası (Adım 2)
            today_incoming_rows = db.fetch_all("""
                SELECT LOWER(TRIM(product_name)) as p_name, COALESCE(SUM(quantity), 0) as total_qty
                FROM BranchShipments
                WHERE target_branch_id = %s AND shipment_date = CURRENT_DATE
                GROUP BY LOWER(TRIM(product_name))
            """, (self.branch_id,))
            incoming_map = {row['p_name']: float(row['total_qty']) for row in (today_incoming_rows or []) if row.get('p_name')}

            # 2. Bugün Kasadan / Faturadan Satılanlar Haritası (Adım 2)
            today_sold_rows = db.fetch_all("""
                SELECT ii.product_id, LOWER(TRIM(ii.product_name)) as p_name, COALESCE(SUM(ii.quantity), 0) as total_qty
                FROM InvoiceItems ii
                JOIN Invoices inv ON ii.invoice_id = inv.id
                WHERE inv.branch_id = %s 
                  AND inv.invoice_date = CURRENT_DATE 
                  AND inv.invoice_type = 'Sales' 
                  AND inv.status != 'Cancelled'
                GROUP BY ii.product_id, LOWER(TRIM(ii.product_name))
            """, (self.branch_id,))
            sold_map_by_id = {}
            sold_map_by_name = {}
            for row in (today_sold_rows or []):
                qty = float(row['total_qty'])
                if row.get('product_id'):
                    sold_map_by_id[row['product_id']] = sold_map_by_id.get(row['product_id'], 0.0) + qty
                if row.get('p_name'):
                    sold_map_by_name[row['p_name']] = sold_map_by_name.get(row['p_name'], 0.0) + qty

            for i, p in enumerate(products):
                self.table.insertRow(i)
                p_id = p.get('id')
                p_name_key = (p.get('name') or '').lower().strip()
                unit_str = p.get('unit') or 'Adet'
                stock = float(p.get('stock_quantity') or 0)
                critical = float(p.get('critical_stock') or 0)
                inc_qty = incoming_map.get(p_name_key, 0.0)
                sold_qty = sold_map_by_id.get(p_id, sold_map_by_name.get(p_name_key, 0.0))

                # Col 0: Kod
                self.table.setItem(i, 0, QTableWidgetItem(str(p.get('product_code') or '')))
                # Col 1: Ürün Adı
                self.table.setItem(i, 1, QTableWidgetItem(str(p.get('name') or '')))
                # Col 2: Kategori
                self.table.setItem(i, 2, QTableWidgetItem(str(p.get('category') or '')))
                # Col 3: Birim
                self.table.setItem(i, 3, QTableWidgetItem(unit_str))
                # Col 4: Satış Fiyatı
                price_item = QTableWidgetItem(f"{float(p.get('sale_price') or 0):,.2f} ₺")
                price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 4, price_item)

                # Col 5: Bugün Gelen 🚚 (Adım 2)
                inc_str = f"+{inc_qty:g} {unit_str}" if inc_qty > 0 else "-"
                inc_item = QTableWidgetItem(inc_str)
                inc_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if inc_qty > 0:
                    inc_item.setForeground(QColor(AppStyles.CYAN))
                    inc_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                else:
                    inc_item.setForeground(QColor(AppStyles.TEXT_MUTED))
                self.table.setItem(i, 5, inc_item)

                # Col 6: Bugün Satılan 🧾 (Adım 2)
                sold_str = f"-{sold_qty:g} {unit_str}" if sold_qty > 0 else "-"
                sold_item = QTableWidgetItem(sold_str)
                sold_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if sold_qty > 0:
                    sold_item.setForeground(QColor(AppStyles.PURPLE))
                    sold_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                else:
                    sold_item.setForeground(QColor(AppStyles.TEXT_MUTED))
                self.table.setItem(i, 6, sold_item)

                # Col 7: Kalan Canlı Stok 📦 (Adım 2)
                stock_item = QTableWidgetItem(f"{stock:g} {unit_str}")
                stock_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                stock_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                if stock <= 0:
                    stock_item.setForeground(QColor(AppStyles.RED))
                elif stock <= critical:
                    stock_item.setForeground(QColor(AppStyles.ORANGE))
                else:
                    stock_item.setForeground(QColor(AppStyles.GREEN))
                self.table.setItem(i, 7, stock_item)

                # Col 8: Kritik Eşik
                crit_item = QTableWidgetItem(f"{critical:g} {unit_str}")
                crit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 8, crit_item)

                # Col 9: Durum Rozeti
                if stock <= 0:
                    status_text = "❌ Tükendi"
                    status_color = AppStyles.RED
                elif stock <= critical:
                    status_text = "⚠️ Kritik"
                    status_color = AppStyles.ORANGE
                else:
                    status_text = "🟢 Yeterli"
                    status_color = AppStyles.GREEN

                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignCenter)
                status_item.setForeground(QColor(status_color))
                status_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(i, 9, status_item)

                # Satır Arka Planı Renk Vurgusu (Adım 6)
                if stock <= 0:
                    row_bg = QColor(239, 68, 68, 25)  # soft kırmızı vurgu
                elif stock <= critical:
                    row_bg = QColor(245, 158, 11, 20)  # soft turuncu/amber vurgu
                else:
                    row_bg = None

                if row_bg:
                    for col_idx in range(10):
                        it = self.table.item(i, col_idx)
                        if it:
                            it.setBackground(row_bg)

                self.table.item(i, 0).setData(Qt.UserRole, p.get('id'))
                self.table.item(i, 0).setData(Qt.UserRole + 1, p)

            # Boş Durum Kontrolü (Adım 5)
            if len(products) == 0:
                self.table.hide()
                self.stock_empty_box.show()
            else:
                self.table.show()
                self.stock_empty_box.hide()

            self.total_label.setText(f"Listelenen: {len(products)} ürün (Toplam Kayıtlı: {len(all_prods or [])})")

            # KPI Kartlarını güncelle
            c1 = self.kpi_total_products.findChild(QLabel, "cardVal")
            if c1: c1.setText(f"{len(all_prods or []):,} Çeşit")

            c2 = self.kpi_total_stock.findChild(QLabel, "cardVal")
            if c2: c2.setText(f"{total_stock_qty:,.0f} Adet")

            c4 = self.kpi_critical_stock.findChild(QLabel, "cardVal")
            if c4: c4.setText(f"{critical_prod_count:,} Ürün")

            # Bugün imalattan gelen miktar
            today_str = datetime.now().date().strftime('%Y-%m-%d')
            today_incoming = db.fetch_one("""
                SELECT COALESCE(SUM(quantity), 0) as total_qty
                FROM BranchShipments
                WHERE target_branch_id = %s AND shipment_date = %s
            """, (self.branch_id, today_str))
            today_qty = float(today_incoming.get('total_qty', 0)) if today_incoming else 0.0
            c3 = self.kpi_incoming_today.findChild(QLabel, "cardVal")
            if c3: c3.setText(f"{today_qty:,.0f} Adet")

        except Exception as e:
            logger.error(f"Şube ürünleri yükleme hatası: {e}")

    def load_production_shipments(self):
        """Sekme 2: İmalathaneden gelen sevkiyatları listeler"""
        try:
            period = self.prod_period_combo.currentText() if hasattr(self, 'prod_period_combo') else "Bugün"
            today = datetime.now().date()

            start_date = None
            end_date = today.strftime('%Y-%m-%d')

            if period == "Bugün":
                start_date = end_date
            elif period == "Son 7 Gün":
                start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            elif period == "Bu Ay":
                start_date = today.replace(day=1).strftime('%Y-%m-%d')
            else:
                end_date = None

            shipments = production_service.get_shipments(
                target_branch_id=self.branch_id,
                start_date=start_date,
                end_date=end_date
            )

            self.prod_table.setRowCount(0)
            tot_qty = 0.0
            tot_amt = 0.0

            for i, s in enumerate(shipments):
                self.prod_table.insertRow(i)
                self.prod_table.setItem(i, 0, QTableWidgetItem(str(s.get('shipment_no') or '-')))
                self.prod_table.setItem(i, 1, QTableWidgetItem(str(s.get('shipment_date') or '')))
                self.prod_table.setItem(i, 2, QTableWidgetItem(str(s.get('product_name') or '')))

                qty = float(s.get('quantity') or 0)
                tot_qty += qty
                unit = s.get('unit') or 'Adet'
                qty_item = QTableWidgetItem(f"{qty:g} {unit}")
                qty_item.setForeground(QColor(AppStyles.GREEN))
                self.prod_table.setItem(i, 3, qty_item)

                price = float(s.get('unit_price') or 0)
                self.prod_table.setItem(i, 4, QTableWidgetItem(f"{price:,.2f} ₺"))

                amt = float(s.get('total_amount') or 0)
                tot_amt += amt
                self.prod_table.setItem(i, 5, QTableWidgetItem(f"{amt:,.2f} ₺"))

                status_item = QTableWidgetItem("✅ Teslim Edildi")
                status_item.setForeground(QColor(AppStyles.GREEN))
                self.prod_table.setItem(i, 6, status_item)

                notes = str(s.get('driver_notes') or '')
                self.prod_table.setItem(i, 7, QTableWidgetItem(notes))

            # İmalat KPI kartları
            c1 = self.kpi_prod_ship_count.findChild(QLabel, "cardVal")
            if c1: c1.setText(f"{len(shipments)} Sefer")

            c2 = self.kpi_prod_total_qty.findChild(QLabel, "cardVal")
            if c2: c2.setText(f"{tot_qty:,.0f} Adet")

            c3 = self.kpi_prod_total_amt.findChild(QLabel, "cardVal")
            if c3: c3.setText(f"{tot_amt:,.2f} ₺")

            # Boş Durum Kontrolü (Adım 5)
            if len(shipments) == 0:
                self.prod_table.hide()
                self.prod_empty_box.show()
            else:
                self.prod_table.show()
                self.prod_empty_box.hide()

        except Exception as e:
            logger.error(f"İmalat sevkiyatlarını yükleme hatası: {e}")

    def load_warehouse_dispatches(self):
        """Sekme 3: Merkez depodan gelen malzeme & ambalaj kayıtlarını listeler"""
        try:
            period = self.wh_period_combo.currentText() if hasattr(self, 'wh_period_combo') else "Tüm Zamanlar"
            today = datetime.now().date()

            start_date = None
            end_date = today.strftime('%Y-%m-%d')

            if period == "Bugün":
                start_date = end_date
            elif period == "Son 7 Gün":
                start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            elif period == "Bu Ay":
                start_date = today.replace(day=1).strftime('%Y-%m-%d')
            else:
                end_date = None

            dispatches = warehouse_service.get_branch_dispatches(
                branch_id=self.branch_id,
                start_date=start_date,
                end_date=end_date
            )

            self.wh_table.setRowCount(0)
            last_date_str = "-"

            for i, d in enumerate(dispatches):
                self.wh_table.insertRow(i)
                self.wh_table.setItem(i, 0, QTableWidgetItem(str(d.get('document_no') or 'SEVKIYAT')))
                
                m_date = str(d.get('movement_date') or '')
                if i == 0 and m_date:
                    last_date_str = m_date
                self.wh_table.setItem(i, 1, QTableWidgetItem(m_date))

                self.wh_table.setItem(i, 2, QTableWidgetItem(str(d.get('product_name') or '')))
                self.wh_table.setItem(i, 3, QTableWidgetItem(str(d.get('product_category') or '-')))

                qty = float(d.get('quantity') or 0)
                unit = d.get('unit') or 'Adet'
                qty_item = QTableWidgetItem(f"{qty:g} {unit}")
                qty_item.setForeground(QColor(AppStyles.CYAN))
                self.wh_table.setItem(i, 4, qty_item)

                desc = str(d.get('description') or '')
                self.wh_table.setItem(i, 5, QTableWidgetItem(desc))

            # Depo KPI kartları
            c1 = self.kpi_wh_total_items.findChild(QLabel, "cardVal")
            if c1: c1.setText(f"{len(dispatches)} Kalem")

            c2 = self.kpi_wh_last_date.findChild(QLabel, "cardVal")
            if c2: c2.setText(last_date_str)

            # Boş Durum Kontrolü (Adım 5)
            if len(dispatches) == 0:
                self.wh_table.hide()
                self.wh_empty_box.show()
            else:
                self.wh_table.show()
                self.wh_empty_box.hide()

        except Exception as e:
            logger.error(f"Depo sevkiyatlarını yükleme hatası: {e}")

    # ==================== ÜRÜN İŞLEMLERİ ====================

    def quick_adjust_stock(self):
        """Seçili ürünün stoğunu hızlıca sayım ile düzeltir"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen stoğunu düzenlemek istediğiniz ürünü tablodan seçin!")
            return

        prod_id = self.table.item(row, 0).data(Qt.UserRole)
        p_data = self.table.item(row, 0).data(Qt.UserRole + 1)
        name = p_data.get('name', 'Ürün')
        stock = float(p_data.get('stock_quantity', 0))
        unit = p_data.get('unit', 'Adet')

        dlg = QuickStockAdjustDialog(prod_id, name, stock, unit, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_products()

    def new_product(self):
        dialog = ProductDialog(self.branch_id, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_products()

    def edit_product(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir ürün seçin!")
            return

        product_id = self.table.item(row, 0).data(Qt.UserRole)
        dialog = ProductDialog(self.branch_id, self, product_id=product_id)
        if dialog.exec_() == QDialog.Accepted:
            self.load_products()

    def delete_product(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir ürün seçin!")
            return

        product_id = self.table.item(row, 0).data(Qt.UserRole)

        reply = QMessageBox.question(
            self, "Sil", "Bu ürünü şube listenizden silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                db.execute_query(
                    "UPDATE Products SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (product_id,)
                )
                QMessageBox.information(self, "Başarılı", "Ürün başarıyla silindi!")
                self.load_products()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Silme hatası:\n{str(e)}")


class ProductDialog(QDialog):
    """Ürün ekleme/düzenleme dialog'u"""

    def __init__(self, branch_id, parent=None, product_id=None):
        super().__init__(parent)
        self.branch_id = branch_id
        self.product_id = product_id

        self.setWindowTitle("Yeni Ürün" if not product_id else "Ürün Düzenle")
        self.setMinimumSize(500, 600)
        self.setStyleSheet(AppStyles.get_main_style())

        self.init_ui()

        if product_id:
            self.load_product()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("🛍️ " + ("Yeni Ürün" if not self.product_id else "Ürün Düzenle"))
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        layout.addWidget(title)

        form = QGridLayout()
        form.setSpacing(10)

        row = 0
        form.addWidget(QLabel("Ürün Adı *"), row, 0)
        self.name_input = QLineEdit()
        form.addWidget(self.name_input, row, 1)

        row += 1
        form.addWidget(QLabel("Ürün Kodu"), row, 0)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Boş bırakılırsa otomatik üretilir")
        form.addWidget(self.code_input, row, 1)

        row += 1
        form.addWidget(QLabel("Barkod"), row, 0)
        self.barcode_input = QLineEdit()
        form.addWidget(self.barcode_input, row, 1)

        row += 1
        form.addWidget(QLabel("Kategori"), row, 0)
        self.category_input = QComboBox()
        self.category_input.addItems([
            "Ekmek", "Simit & Poğaça", "Unlu Mamül", "Tatlı", "Pasta", "İçecek", "Diğer"
        ])
        self.category_input.setEditable(True)
        form.addWidget(self.category_input, row, 1)

        row += 1
        form.addWidget(QLabel("Birim"), row, 0)
        self.unit_input = QLineEdit()
        self.unit_input.setText("Adet")
        form.addWidget(self.unit_input, row, 1)

        row += 1
        form.addWidget(QLabel("Alış Fiyatı"), row, 0)
        self.purchase_input = QDoubleSpinBox()
        self.purchase_input.setRange(0, 999999999999.99)
        self.purchase_input.setPrefix("₺ ")
        self.purchase_input.setDecimals(2)
        form.addWidget(self.purchase_input, row, 1)

        row += 1
        form.addWidget(QLabel("Satış Fiyatı"), row, 0)
        self.sale_input = QDoubleSpinBox()
        self.sale_input.setRange(0, 999999999999.99)
        self.sale_input.setPrefix("₺ ")
        self.sale_input.setDecimals(2)
        form.addWidget(self.sale_input, row, 1)

        row += 1
        form.addWidget(QLabel("Stok Miktarı"), row, 0)
        self.stock_input = QDoubleSpinBox()
        self.stock_input.setRange(0, 999999999.999)
        self.stock_input.setDecimals(2)
        form.addWidget(self.stock_input, row, 1)

        row += 1
        form.addWidget(QLabel("Kritik Stok"), row, 0)
        self.critical_input = QDoubleSpinBox()
        self.critical_input.setRange(1, 999999999.999)
        self.critical_input.setValue(5)
        self.critical_input.setDecimals(2)
        form.addWidget(self.critical_input, row, 1)

        row += 1
        form.addWidget(QLabel("KDV %"), row, 0)
        self.vat_input = QDoubleSpinBox()
        self.vat_input.setRange(0, 100)
        self.vat_input.setValue(1)
        form.addWidget(self.vat_input, row, 1)

        row += 1
        form.addWidget(QLabel("Notlar"), row, 0)
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        form.addWidget(self.notes_input, row, 1)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Save).setText("💾 Kaydet")
        btn_box.button(QDialogButtonBox.Cancel).setText("❌ İptal")
        btn_box.accepted.connect(self.save_product)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.setLayout(layout)

    def load_product(self):
        try:
            p = db.fetch_one("SELECT * FROM Products WHERE id = %s", (self.product_id,))
            if p:
                self.name_input.setText(p.get('name') or '')
                self.code_input.setText(p.get('product_code') or '')
                self.barcode_input.setText(p.get('barcode') or '')
                cat_val = p.get('category') or 'Ekmek'
                idx = self.category_input.findText(cat_val)
                if idx >= 0:
                    self.category_input.setCurrentIndex(idx)
                else:
                    self.category_input.setEditText(cat_val)
                self.unit_input.setText(p.get('unit') or 'Adet')
                self.purchase_input.setValue(float(p.get('purchase_price') or 0))
                self.sale_input.setValue(float(p.get('sale_price') or 0))
                self.stock_input.setValue(float(p.get('stock_quantity') or 0))
                self.critical_input.setValue(max(1.0, float(p.get('critical_stock') or 1)))
                self.vat_input.setValue(float(p.get('vat_rate') or 1))
                self.notes_input.setText(p.get('notes') or '')
        except Exception as e:
            logger.error(f"Ürün yükleme hatası: {e}")

    def _generate_product_code(self) -> str:
        """Otomatik ürün kodu üret: PRD-XXXX"""
        try:
            result = db.fetch_one("SELECT COALESCE(MAX(id), 0) + 1 as next_id FROM Products")
            next_id = result['next_id'] if result else 1
            for _ in range(10):
                code = f"PRD-{next_id:04d}"
                existing = db.fetch_one("SELECT id FROM Products WHERE product_code = %s LIMIT 1", (code,))
                if not existing:
                    return code
                next_id += 1
            return f"PRD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        except Exception as e:
            logger.error(f"Ürün kodu üretme hatası: {e}")
            return f"PRD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def save_product(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Uyarı", "Ürün adı zorunludur!")
            return

        code = self.code_input.text().strip() or self._generate_product_code()
        barcode = self.barcode_input.text().strip() or None
        category = self.category_input.currentText().strip() or "Ekmek"
        unit = self.unit_input.text().strip() or "Adet"
        purchase = self.purchase_input.value()
        sale = self.sale_input.value()
        stock = self.stock_input.value()
        critical = self.critical_input.value()
        vat = self.vat_input.value()
        notes = self.notes_input.toPlainText().strip() or None

        try:
            if not self.product_id:
                db.execute_query("""
                    INSERT INTO Products (
                        branch_id, product_code, barcode, name, category, unit,
                        purchase_price, sale_price, stock_quantity, critical_stock,
                        vat_rate, notes, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                """, (
                    self.branch_id, code, barcode, name, category, unit,
                    purchase, sale, stock, critical, vat, notes
                ))
                QMessageBox.information(self, "Başarılı", "Yeni ürün başarıyla eklendi!")
            else:
                db.execute_query("""
                    UPDATE Products SET
                        product_code = %s, barcode = %s, name = %s, category = %s, unit = %s,
                        purchase_price = %s, sale_price = %s, stock_quantity = %s,
                        critical_stock = %s, vat_rate = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    code, barcode, name, category, unit,
                    purchase, sale, stock, critical, vat, notes, self.product_id
                ))
                QMessageBox.information(self, "Başarılı", "Ürün güncellendi!")

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kayıt hatası:\n{str(e)}")