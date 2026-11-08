# src/ui/pages/reports_page.py
"""
Gelişmiş Raporlar Sayfası
Şubenin tüm kazançları, faaliyet giderleri, fire zararları ve müşteri cari hesap listesi
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QDateEdit, QComboBox, QMessageBox, QFileDialog, QScrollArea,
    QGraphicsDropShadowEffect, QHeaderView, QTabWidget, QLineEdit,
    QSplitter
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ...services.report_service import ReportService
from ...services.excel_service import ExcelService
from ...services.turnover_service import turnover_service
from ...services.stock_count_service import stock_count_service
from ...services.customer_service import CustomerService
from ..styles import AppStyles


class ReportsPage(QWidget):
    """Gelişmiş raporlar ve detaylı finansal analiz sayfası"""

    def __init__(self, user: User, branch_id: int, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window
        self.report_service = ReportService()
        self.excel_service = ExcelService()
        self.customer_service = CustomerService()

        self._all_companies_data = []

        self.init_ui()
        self.load_active_tab_data()

    def init_ui(self):
        self.setObjectName("ReportsPage")
        self.setStyleSheet(f"#ReportsPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(25, 20, 25, 20)

        # 1. ÜST BAŞLIK VE TARİH FİLTRE ÇUBUĞU
        top_frame = QFrame()
        top_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
                padding: 10px 16px;
            }}
        """)
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel("📈 Gelişmiş Raporlar & Finansal Analiz")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; border: none;")
        left.addWidget(title)
        subtitle = QLabel("Şube kazançları, işletme giderleri, fire zararları ve detaylı müşteri cari hesapları")
        subtitle.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_SECONDARY}; border: none;")
        left.addWidget(subtitle)
        top_layout.addLayout(left)

        top_layout.addStretch()

        # Hızlı Tarih Butonları
        quick_btns = [
            ("Bu Ay", self._set_this_month),
            ("Geçen Ay", self._set_last_month),
            ("Bu Yıl", self._set_this_year),
            ("Son 30 Gün", self._set_last_30_days)
        ]
        for btn_text, slot in quick_btns:
            btn = QPushButton(btn_text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.BG_DARK};
                    color: {AppStyles.TEXT_SECONDARY};
                    border: 1px solid {AppStyles.BORDER};
                    border-radius: 5px;
                    padding: 0 10px;
                    font-size: 8.5pt;
                }}
                QPushButton:hover {{
                    background-color: {AppStyles.BG_LIGHT};
                    color: {AppStyles.TEXT_PRIMARY};
                    border-color: {AppStyles.PRIMARY};
                }}
            """)
            btn.clicked.connect(slot)
            top_layout.addWidget(btn)

        # Başlangıç Tarihi
        top_layout.addWidget(QLabel("📅 Başlangıç:"))
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd.MM.yyyy")
        self.start_date.setFixedHeight(34)
        self.start_date.setStyleSheet(self._input_style())
        self.start_date.dateChanged.connect(self.load_active_tab_data)
        top_layout.addWidget(self.start_date)

        # Bitiş Tarihi
        top_layout.addWidget(QLabel("📅 Bitiş:"))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("dd.MM.yyyy")
        self.end_date.setFixedHeight(34)
        self.end_date.setStyleSheet(self._input_style())
        self.end_date.dateChanged.connect(self.load_active_tab_data)
        top_layout.addWidget(self.end_date)

        # Yenile Butonu
        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setFixedHeight(34)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.PRIMARY};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.PRIMARY_DARK if hasattr(AppStyles, 'PRIMARY_DARK') else '#4f46e5'};
            }}
        """)
        refresh_btn.clicked.connect(self.load_active_tab_data)
        top_layout.addWidget(refresh_btn)

        # Excel'e Aktar Butonu
        export_btn = QPushButton("📥 Excel'e Aktar")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setFixedHeight(34)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.GREEN};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: bold;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        export_btn.clicked.connect(self.export_to_excel)
        top_layout.addWidget(export_btn)

        layout.addWidget(top_frame)

        # 2. ANA SEKMELİ YAPI (QTabWidget)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                background-color: {AppStyles.BG_MEDIUM};
            }}
            QTabBar::tab {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_SECONDARY};
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
                font-size: 9.5pt;
                border: 1px solid {AppStyles.BORDER};
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: {AppStyles.BG_MEDIUM};
                color: white;
                border-top: 3px solid {AppStyles.PRIMARY};
            }}
            QTabBar::tab:hover {{
                color: {AppStyles.TEXT_PRIMARY};
            }}
        """)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Sekme 1: Kazanç, Gider & Fire Analizi
        self.tab_finances = self.create_finances_tab()
        self.tabs.addTab(self.tab_finances, "📊 Kazanç & Gider Analizi (Kâr / Zarar)")

        # Sekme 2: Müşteri & Cari Bakiye Listesi
        self.tab_customers = self.create_customers_tab()
        self.tabs.addTab(self.tab_customers, "👥 Müşteri & Cari Hesap Listesi")

        # Sekme 3: Resmi & Standart Muhasebe Raporları
        self.tab_accounting = self.create_accounting_tab()
        self.tabs.addTab(self.tab_accounting, "📑 Standart Muhasebe Raporları")

        layout.addWidget(self.tabs, 1)
        self.setLayout(layout)

    # ==================== SEKME 1: KAZANÇ & GİDER & FİRE ANALİZİ ====================

    def create_finances_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(14, 14, 14, 14)

        # 4 Büyük Finansal KPI Kartı
        self.fin_kpi_container = QFrame()
        self.fin_kpi_container.setStyleSheet("background: transparent; border: none;")
        self.fin_kpi_layout = QHBoxLayout(self.fin_kpi_container)
        self.fin_kpi_layout.setContentsMargins(0, 0, 0, 0)
        self.fin_kpi_layout.setSpacing(12)
        layout.addWidget(self.fin_kpi_container)

        # İki Bölmeli Detay: Sol Kategori Özeti, Sağ Detaylı Hareketler
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {AppStyles.BORDER};
                width: 2px;
            }}
        """)

        # Sol: Kategori Bazlı Dağılım
        left_box = QFrame()
        left_box.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border-radius: 8px;
                border: 1px solid {AppStyles.BORDER};
                padding: 10px;
            }}
        """)
        l_lay = QVBoxLayout(left_box)
        l_lay.setContentsMargins(0, 0, 0, 0)
        l_lay.setSpacing(6)
        l_title = QLabel("📊 Kategori Bazlı Kazanç, Gider & Fire Dağılımı")
        l_title.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; border: none;")
        l_lay.addWidget(l_title)

        self.fin_cat_table = QTableWidget()
        self.fin_cat_table.setColumnCount(4)
        self.fin_cat_table.setHorizontalHeaderLabels(['Tür', 'Kategori', 'Tutar', 'Pay'])
        self.fin_cat_table.setAlternatingRowColors(True)
        self.fin_cat_table.verticalHeader().setVisible(False)
        self.fin_cat_table.verticalHeader().setDefaultSectionSize(36)
        self.fin_cat_table.setStyleSheet(self._table_style())
        self.fin_cat_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.fin_cat_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.fin_cat_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.fin_cat_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        l_lay.addWidget(self.fin_cat_table)
        splitter.addWidget(left_box)

        # Sağ: Detaylı Finansal Hareketler
        right_box = QFrame()
        right_box.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border-radius: 8px;
                border: 1px solid {AppStyles.BORDER};
                padding: 10px;
            }}
        """)
        r_lay = QVBoxLayout(right_box)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(6)
        r_title = QLabel("📝 Dönem İçi Detaylı Kasa & Gider Hareketleri")
        r_title.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; border: none;")
        r_lay.addWidget(r_title)

        self.fin_details_table = QTableWidget()
        self.fin_details_table.setColumnCount(6)
        self.fin_details_table.setHorizontalHeaderLabels(['Tarih', 'Tür', 'Kategori', 'Açıklama', 'Ödeme', 'Tutar'])
        self.fin_details_table.setAlternatingRowColors(True)
        self.fin_details_table.verticalHeader().setVisible(False)
        self.fin_details_table.verticalHeader().setDefaultSectionSize(36)
        self.fin_details_table.setStyleSheet(self._table_style())
        self.fin_details_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.fin_details_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.fin_details_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.fin_details_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.fin_details_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.fin_details_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        r_lay.addWidget(self.fin_details_table)
        splitter.addWidget(right_box)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        return widget

    def _create_large_kpi_card(self, icon: str, title: str, value: str, sub_text: str, color: str) -> QFrame:
        card = QFrame()
        card.setFixedHeight(106)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border-radius: 8px;
                border: 1px solid {AppStyles.BORDER};
                border-left: 4px solid {color};
                padding: 6px 12px;
            }}
            QFrame:hover {{
                border-color: {color};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)

        t_row = QHBoxLayout()
        t_row.setSpacing(6)
        i_lbl = QLabel(icon)
        i_lbl.setStyleSheet("font-size: 11pt;")
        t_row.addWidget(i_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 8.5pt; font-weight: bold; color: {AppStyles.TEXT_SECONDARY};")
        t_row.addWidget(title_lbl)
        t_row.addStretch()
        lay.addLayout(t_row)

        v_lbl = QLabel(value)
        v_lbl.setStyleSheet(f"font-size: 13.5pt; font-weight: bold; color: {color}; min-height: 24px;")
        lay.addWidget(v_lbl)

        s_lbl = QLabel(sub_text)
        s_lbl.setStyleSheet(f"font-size: 8pt; color: {AppStyles.TEXT_MUTED};")
        s_lbl.setWordWrap(True)
        lay.addWidget(s_lbl)

        return card

    # ==================== SEKME 2: MÜŞTERİ & CARİ HESAP LİSTESİ ====================

    def create_customers_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(14, 14, 14, 14)

        # Cari KPI Kartları
        self.cust_kpi_container = QFrame()
        self.cust_kpi_container.setStyleSheet("background: transparent; border: none;")
        self.cust_kpi_layout = QHBoxLayout(self.cust_kpi_container)
        self.cust_kpi_layout.setContentsMargins(0, 0, 0, 0)
        self.cust_kpi_layout.setSpacing(12)
        layout.addWidget(self.cust_kpi_container)

        # Arama ve Filtre Çubuğu
        f_bar = QHBoxLayout()
        f_bar.setSpacing(10)

        f_bar.addWidget(QLabel("🔍 Ara:"))
        self.cust_search_input = QLineEdit()
        self.cust_search_input.setPlaceholderText("Müşteri adı veya telefon ile ara...")
        self.cust_search_input.setFixedHeight(34)
        self.cust_search_input.setStyleSheet(self._input_style())
        self.cust_search_input.textChanged.connect(self.filter_customers_table)
        f_bar.addWidget(self.cust_search_input, 1)

        f_bar.addWidget(QLabel("⚖️ Durum:"))
        self.cust_filter_combo = QComboBox()
        self.cust_filter_combo.addItems([
            "Tüm Müşteriler",
            "Sadece Borçlu Olanlar (Alacaklarımız)",
            "Bakiyesi Sıfır Olanlar",
            "Alacaklı Olanlar (Tedarikçi/Avans)"
        ])
        self.cust_filter_combo.setFixedHeight(34)
        self.cust_filter_combo.setMinimumWidth(210)
        self.cust_filter_combo.setStyleSheet(self._input_style())
        self.cust_filter_combo.currentIndexChanged.connect(self.filter_customers_table)
        f_bar.addWidget(self.cust_filter_combo)

        layout.addLayout(f_bar)

        # Müşteriler Tablosu
        self.cust_table = QTableWidget()
        self.cust_table.setColumnCount(8)
        self.cust_table.setHorizontalHeaderLabels([
            'Müşteri Kodu', 'Müşteri / Cari Ünvanı', 'Telefon', 'Fatura Sayısı',
            'Toplam Fatura Hacmi', 'Tahsilat Tutarı', 'Kalan Bakiye', 'Cari Durum'
        ])
        self.cust_table.setAlternatingRowColors(True)
        self.cust_table.verticalHeader().setVisible(False)
        self.cust_table.verticalHeader().setDefaultSectionSize(38)
        self.cust_table.setStyleSheet(self._table_style())
        self.cust_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.cust_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.cust_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.cust_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.cust_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.cust_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.cust_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.cust_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        layout.addWidget(self.cust_table, 1)

        return widget

    # ==================== SEKME 3: STANDART MUHASEBE RAPORLARI ====================

    def create_accounting_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(14, 14, 14, 14)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("📊 Standart Rapor Tipi:"))
        self.report_type = QComboBox()
        self.report_type.addItems([
            "Bilanço", "Gelir Tablosu", "Deneme Bilançosu",
            "Fatura Özeti", "Cari Yaşlandırma", "Günlük Özet"
        ])
        self.report_type.setFixedHeight(34)
        self.report_type.setMinimumWidth(200)
        self.report_type.setStyleSheet(self._input_style())
        self.report_type.currentTextChanged.connect(self.load_accounting_report)
        bar.addWidget(self.report_type)

        calc_btn = QPushButton("Hesapla")
        calc_btn.setFixedHeight(34)
        calc_btn.setStyleSheet(f"background-color: {AppStyles.PRIMARY}; color: white; border: none; border-radius: 6px; padding: 0 16px; font-weight: bold;")
        calc_btn.clicked.connect(self.load_accounting_report)
        bar.addWidget(calc_btn)
        bar.addStretch()
        layout.addLayout(bar)

        self.accounting_frame = QFrame()
        self.accounting_frame.setStyleSheet("background: transparent; border: none;")
        self.accounting_layout = QVBoxLayout(self.accounting_frame)
        self.accounting_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.accounting_frame, 1)

        return widget

    # ==================== VERİ YÜKLEME METOTLARI ====================

    def on_tab_changed(self, idx: int):
        self.load_active_tab_data()

    def load_active_tab_data(self):
        cur_idx = self.tabs.currentIndex()
        if cur_idx == 0:
            self.load_finances_data()
        elif cur_idx == 1:
            self.load_customers_data()
        elif cur_idx == 2:
            self.load_accounting_report()

    def load_finances_data(self):
        """Şubenin kazanç, gider, fire ve kâr analizini yükle"""
        try:
            start = self.start_date.date().toString("yyyy-MM-dd")
            end = self.end_date.date().toString("yyyy-MM-dd")

            overview = turnover_service.get_branch_financial_overview(self.branch_id, start, end)
            inc = overview['income']
            cash = overview['cash_income']
            card = overview['card_income']
            exp = overview['expense']
            waste = overview['waste']
            waste_qty = overview['waste_qty']
            net = overview['net_profit']
            margin = overview['profit_margin']

            # KPI Kartlarını Güncelle
            while self.fin_kpi_layout.count():
                it = self.fin_kpi_layout.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()

            kpi_income = self._create_large_kpi_card(
                "💰", "Toplam Gelir / Ciro",
                f"{inc:,.2f} ₺",
                f"Nakit: {cash:,.2f} ₺ • POS/Kart: {card:,.2f} ₺",
                AppStyles.GREEN
            )
            kpi_expense = self._create_large_kpi_card(
                "💸", "Toplam Faaliyet Gideri",
                f"{exp:,.2f} ₺",
                "İşletme ve tedarik harcamaları",
                AppStyles.RED
            )
            kpi_waste = self._create_large_kpi_card(
                "🔥", "Toplam Fire / Zayiat Zararı",
                f"{waste:,.2f} ₺",
                f"{waste_qty:,.1f} Adet/Kg zayiat kaybı",
                AppStyles.DANGER
            )
            net_col = AppStyles.CYAN if net >= 0 else AppStyles.RED
            kpi_net = self._create_large_kpi_card(
                "⚖️", "Net Kazanç (Gelir - Gider - Fire)",
                f"{net:,.2f} ₺",
                f"Kâr Marjı: %{margin:.1f} • {'Kârda' if net >= 0 else 'Zararda'}",
                net_col
            )

            self.fin_kpi_layout.addWidget(kpi_income)
            self.fin_kpi_layout.addWidget(kpi_expense)
            self.fin_kpi_layout.addWidget(kpi_waste)
            self.fin_kpi_layout.addWidget(kpi_net)

            # Kategori Dağılım Tablosu
            cat_data = turnover_service.get_category_summary(self.branch_id, start, end) or []

            # Fire kategorisini tek satırda birleştirmek için filtrele
            filtered_cats = []
            dt_internal_fire = 0.0
            for c in cat_data:
                cname = str(c.get('category', ''))
                if 'Fire' in cname or 'Zayiat' in cname or c.get('entry_type') == 'Waste':
                    dt_internal_fire += float(c.get('total_amount', 0.0))
                else:
                    filtered_cats.append(c)

            total_single_fire = max(waste, dt_internal_fire)

            self.fin_cat_table.setRowCount(0)
            row_idx = 0
            grand_flow = inc + exp + total_single_fire

            for item in filtered_cats:
                self.fin_cat_table.insertRow(row_idx)
                etype = item.get('entry_type', 'Income')
                cname = item.get('category', '-')
                amt = float(item.get('total_amount', 0.0))
                ratio = (amt / inc * 100.0) if (etype == 'Income' and inc > 0) else ((amt / exp * 100.0) if (etype != 'Income' and exp > 0) else 0.0)

                t_item = QTableWidgetItem("🟢 Gelir" if etype == 'Income' else "🔴 Gider")
                t_item.setForeground(QColor(AppStyles.GREEN if etype == 'Income' else AppStyles.RED))
                t_item.setTextAlignment(Qt.AlignCenter)
                self.fin_cat_table.setItem(row_idx, 0, t_item)

                c_item = QTableWidgetItem(cname)
                c_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.fin_cat_table.setItem(row_idx, 1, c_item)

                a_item = QTableWidgetItem(f"{amt:,.2f} ₺")
                a_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                a_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                a_item.setForeground(QColor(AppStyles.GREEN if etype == 'Income' else AppStyles.RED))
                self.fin_cat_table.setItem(row_idx, 2, a_item)

                r_item = QTableWidgetItem(f"%{ratio:.1f}")
                r_item.setTextAlignment(Qt.AlignCenter)
                r_item.setForeground(QColor(AppStyles.TEXT_MUTED))
                self.fin_cat_table.setItem(row_idx, 3, r_item)

                row_idx += 1

            # Tek satırda Fire Ekle
            if total_single_fire > 0:
                self.fin_cat_table.insertRow(row_idx)
                f_type = QTableWidgetItem("🔥 Fire")
                f_type.setForeground(QColor(AppStyles.DANGER))
                f_type.setTextAlignment(Qt.AlignCenter)
                self.fin_cat_table.setItem(row_idx, 0, f_type)

                f_cat = QTableWidgetItem("🔥 Toplam Fire / Zayiat Zararı")
                f_cat.setFont(QFont("Segoe UI", 9, QFont.Bold))
                f_cat.setForeground(QColor(AppStyles.DANGER))
                self.fin_cat_table.setItem(row_idx, 1, f_cat)

                f_amt = QTableWidgetItem(f"{total_single_fire:,.2f} ₺")
                f_amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                f_amt.setFont(QFont("Segoe UI", 9, QFont.Bold))
                f_amt.setForeground(QColor(AppStyles.DANGER))
                self.fin_cat_table.setItem(row_idx, 2, f_amt)

                fire_ratio = (total_single_fire / inc * 100.0) if inc > 0 else 0.0
                f_ratio = QTableWidgetItem(f"%{fire_ratio:.1f}")
                f_ratio.setTextAlignment(Qt.AlignCenter)
                f_ratio.setForeground(QColor(AppStyles.DANGER))
                self.fin_cat_table.setItem(row_idx, 3, f_ratio)

            # Detaylı Finansal Hareketler Tablosu
            b_cond, b_params = turnover_service._build_branch_filter(self.branch_id)
            entries = db.fetch_all(f"""
                SELECT entry_date, entry_type, category, description, payment_method, amount
                FROM DailyTurnovers
                WHERE {b_cond} AND entry_date BETWEEN %s AND %s
                ORDER BY entry_date DESC, id DESC
                LIMIT 300
            """, tuple(b_params + [start, end])) or []

            self.fin_details_table.setRowCount(0)
            for d_idx, row in enumerate(entries):
                self.fin_details_table.insertRow(d_idx)

                dt_str = row['entry_date'].strftime('%d.%m.%Y') if hasattr(row['entry_date'], 'strftime') else str(row['entry_date'])
                etype = row['entry_type']
                amt = float(row['amount'])

                d_item = QTableWidgetItem(dt_str)
                d_item.setTextAlignment(Qt.AlignCenter)
                self.fin_details_table.setItem(d_idx, 0, d_item)

                if 'Fire' in str(row.get('category', '')):
                    t_lbl = "🔥 Fire"
                    t_col = AppStyles.DANGER
                elif etype == 'Income':
                    t_lbl = "🟢 Gelir"
                    t_col = AppStyles.GREEN
                else:
                    t_lbl = "🔴 Gider"
                    t_col = AppStyles.RED

                t_item = QTableWidgetItem(t_lbl)
                t_item.setForeground(QColor(t_col))
                t_item.setTextAlignment(Qt.AlignCenter)
                self.fin_details_table.setItem(d_idx, 1, t_item)

                self.fin_details_table.setItem(d_idx, 2, QTableWidgetItem(str(row.get('category') or '-')))
                self.fin_details_table.setItem(d_idx, 3, QTableWidgetItem(str(row.get('description') or '')))

                m_item = QTableWidgetItem(str(row.get('payment_method') or 'Nakit'))
                m_item.setTextAlignment(Qt.AlignCenter)
                self.fin_details_table.setItem(d_idx, 4, m_item)

                amt_item = QTableWidgetItem(f"{amt:,.2f} ₺")
                amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                amt_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                amt_item.setForeground(QColor(t_col))
                self.fin_details_table.setItem(d_idx, 5, amt_item)

        except Exception as e:
            logger.error(f"ReportsPage load_finances_data hatası: {e}")

    def load_customers_data(self):
        """Şubenin müşteri listesini ve cari hesaplarını yükle"""
        try:
            summary = self.customer_service.get_companies_balance_summary(self.branch_id)
            self._all_companies_data = summary.get('companies', [])

            # KPI Kartlarını Güncelle
            tot_cust = summary.get('total_companies', len(self._all_companies_data))
            tot_sales = summary.get('total_sales', 0.0)
            tot_paid = summary.get('total_paid', 0.0)
            tot_rec = summary.get('total_receivables', 0.0)

            while self.cust_kpi_layout.count():
                it = self.cust_kpi_layout.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()

            kpi_cnt = self._create_large_kpi_card("👥", "Kayıtlı Müşteri Sayısı", f"{tot_cust} Firma / Kişi", "Şubeye bağlı cariler", AppStyles.PRIMARY)
            kpi_sales = self._create_large_kpi_card("💰", "Toplam Fatura / Satış", f"{tot_sales:,.2f} ₺", "Tüm satış faturaları", AppStyles.GREEN)
            kpi_paid = self._create_large_kpi_card("💸", "Tahsil Edilen Tutar", f"{tot_paid:,.2f} ₺", "Kasa ve banka tahsilatları", AppStyles.CYAN)
            kpi_rec = self._create_large_kpi_card("⏳", "Bekleyen Açık Alacak", f"{tot_rec:,.2f} ₺", "Tahsil edilecek müşteri borçları", AppStyles.ORANGE if tot_rec > 0 else AppStyles.GREEN)

            self.cust_kpi_layout.addWidget(kpi_cnt)
            self.cust_kpi_layout.addWidget(kpi_sales)
            self.cust_kpi_layout.addWidget(kpi_paid)
            self.cust_kpi_layout.addWidget(kpi_rec)

            self.filter_customers_table()
        except Exception as e:
            logger.error(f"ReportsPage load_customers_data hatası: {e}")

    def filter_customers_table(self):
        """Arama ve filtreye göre müşteri tablosunu tazele"""
        query = self.cust_search_input.text().strip().lower()
        mode_idx = self.cust_filter_combo.currentIndex()

        self.cust_table.setRowCount(0)
        row_idx = 0

        tot_sales = 0.0
        tot_paid = 0.0
        tot_bal = 0.0

        for c in self._all_companies_data:
            code = str(c.get('customer_code') or '')
            title = str(c.get('title') or '')
            phone = str(c.get('phone') or '-')
            sales = float(c.get('sales_total') or 0.0)
            paid = float(c.get('total_paid') or 0.0)
            bal = float(c.get('balance') or 0.0)
            inv_cnt = int(c.get('invoice_count') or 0)

            # Arama filtresi
            if query and query not in title.lower() and query not in phone.lower() and query not in code.lower():
                continue

            # Durum filtresi: 1 = Borçlu olanlar (bal > 0), 2 = Sıfır (bal == 0), 3 = Alacaklı (bal < 0)
            if mode_idx == 1 and bal <= 0:
                continue
            elif mode_idx == 2 and abs(bal) > 0.01:
                continue
            elif mode_idx == 3 and bal >= 0:
                continue

            self.cust_table.insertRow(row_idx)

            # 0: Kod
            self.cust_table.setItem(row_idx, 0, QTableWidgetItem(code))

            # 1: Ünvan
            u_item = QTableWidgetItem(title)
            u_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.cust_table.setItem(row_idx, 1, u_item)

            # 2: Telefon
            p_item = QTableWidgetItem(phone)
            p_item.setTextAlignment(Qt.AlignCenter)
            self.cust_table.setItem(row_idx, 2, p_item)

            # 3: Fatura Sayısı
            cnt_item = QTableWidgetItem(str(inv_cnt))
            cnt_item.setTextAlignment(Qt.AlignCenter)
            self.cust_table.setItem(row_idx, 3, cnt_item)

            # 4: Satış
            s_item = QTableWidgetItem(f"{sales:,.2f} ₺")
            s_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            s_item.setForeground(QColor(AppStyles.GREEN))
            self.cust_table.setItem(row_idx, 4, s_item)

            # 5: Tahsilat
            pd_item = QTableWidgetItem(f"{paid:,.2f} ₺")
            pd_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            pd_item.setForeground(QColor(AppStyles.CYAN))
            self.cust_table.setItem(row_idx, 5, pd_item)

            # 6: Kalan Bakiye
            b_item = QTableWidgetItem(f"{bal:,.2f} ₺")
            b_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            b_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            if bal > 0:
                b_item.setForeground(QColor(AppStyles.RED))
            elif bal < 0:
                b_item.setForeground(QColor(AppStyles.CYAN))
            else:
                b_item.setForeground(QColor(AppStyles.TEXT_MUTED))
            self.cust_table.setItem(row_idx, 6, b_item)

            # 7: Cari Durum
            if bal > 0:
                status_txt = "⚠️ Borçlu (Alacağımız Var)"
                status_col = AppStyles.RED
            elif bal < 0:
                status_txt = "🟢 Alacaklı (Avans)"
                status_col = AppStyles.CYAN
            else:
                status_txt = "✅ Hesap Dengede"
                status_col = AppStyles.GREEN

            st_item = QTableWidgetItem(status_txt)
            st_item.setTextAlignment(Qt.AlignCenter)
            st_item.setForeground(QColor(status_col))
            self.cust_table.setItem(row_idx, 7, st_item)

            tot_sales += sales
            tot_paid += paid
            tot_bal += bal
            row_idx += 1

        # Alt Toplam Satırı
        if row_idx > 0:
            self.cust_table.insertRow(row_idx)
            tot_name = QTableWidgetItem(f"🏆 TOPLAM ({row_idx} Müşteri)")
            tot_name.setFont(QFont("Segoe UI", 9, QFont.Bold))
            tot_name.setBackground(QColor(AppStyles.PRIMARY).darker(200))
            tot_name.setForeground(QColor("#FFFFFF"))
            self.cust_table.setItem(row_idx, 1, tot_name)

            col_tots = [
                (4, tot_sales, AppStyles.GREEN),
                (5, tot_paid, AppStyles.CYAN),
                (6, tot_bal, AppStyles.RED if tot_bal > 0 else AppStyles.GREEN),
            ]
            for col_i, val, col_c in col_tots:
                ti = QTableWidgetItem(f"{val:,.2f} ₺")
                ti.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                ti.setFont(QFont("Segoe UI", 9, QFont.Bold))
                ti.setForeground(QColor(col_c))
                ti.setBackground(QColor(AppStyles.PRIMARY).darker(200))
                self.cust_table.setItem(row_idx, col_i, ti)

    # ==================== SEKME 3: MUHASEBE RAPORU OLUŞTURUCU ====================

    def load_accounting_report(self):
        """Mevcut standart muhasebe raporunu çağır"""
        while self.accounting_layout.count():
            item = self.accounting_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        report_type = self.report_type.currentText()
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")

        try:
            if report_type == "Bilanço":
                self.show_balance_sheet(end)
            elif report_type == "Gelir Tablosu":
                self.show_income_statement(start, end)
            elif report_type == "Deneme Bilançosu":
                self.show_trial_balance(end)
            elif report_type == "Fatura Özeti":
                self.show_invoice_summary(start, end)
            elif report_type == "Cari Yaşlandırma":
                self.show_aging(end)
            elif report_type == "Günlük Özet":
                self.show_daily_summary(end)
        except Exception as e:
            logger.error(f"Muhasebe rapor hatası: {e}")
            err = QLabel(f"⚠️ Rapor oluşturulamadı: {e}")
            err.setStyleSheet(f"color: {AppStyles.RED}; font-size: 11pt;")
            self.accounting_layout.addWidget(err)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def show_balance_sheet(self, end_date):
        title = QLabel(f"📊 Bilanço Raporu - {end_date}")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        self.accounting_layout.addWidget(title)

        data = self.report_service.get_balance_sheet(self.branch_id, end_date)
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(['Hesap Kodu', 'Hesap Adı', 'Bakiye'])
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)
        table.setStyleSheet(self._table_style())
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        rows = []
        rows.append(("", "AKTİFLER", ""))
        for a in data.get('assets', []):
            bal = a.get('balance') or 0
            rows.append((a.get('account_code', ''), a.get('account_name', ''), f"{bal:,.2f} ₺"))
        tot_assets = data.get('total_assets') or 0
        rows.append(("", "TOPLAM AKTİF", f"{tot_assets:,.2f} ₺"))
        rows.append(("", "", ""))
        rows.append(("", "PASİFLER", ""))
        for l in data.get('liabilities', []):
            bal = l.get('balance') or 0
            rows.append((l.get('account_code', ''), l.get('account_name', ''), f"{bal:,.2f} ₺"))
        tot_liab = data.get('total_liabilities') or 0
        equity = data.get('equity') or 0
        rows.append(("", "TOPLAM PASİF", f"{tot_liab:,.2f} ₺"))
        rows.append(("", "ÖZ SERMAYE", f"{equity:,.2f} ₺"))

        table.setRowCount(len(rows))
        for i, (code, name, balance) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(code))
            table.setItem(i, 1, QTableWidgetItem(name))
            table.setItem(i, 2, QTableWidgetItem(balance))

        self.accounting_layout.addWidget(table)

    def show_income_statement(self, start, end):
        title = QLabel(f"📊 Gelir Tablosu - {start} / {end}")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        self.accounting_layout.addWidget(title)

        data = self.report_service.get_income_statement(self.branch_id, start, end)
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(['Hesap Kodu', 'Hesap Adı', 'Tutar'])
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)
        table.setStyleSheet(self._table_style())
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        rows = []
        rows.append(("", "GELİRLER", ""))
        for r in data.get('revenues', []):
            amt = r.get('net_amount') or 0
            rows.append((r.get('account_code', ''), r.get('account_name', ''), f"{amt:,.2f} ₺"))
        tot_rev = data.get('total_revenue') or 0
        rows.append(("", "TOPLAM GELİR", f"{tot_rev:,.2f} ₺"))
        rows.append(("", "", ""))
        rows.append(("", "GİDERLER", ""))
        for e in data.get('expenses', []):
            amt = e.get('net_amount') or 0
            rows.append((e.get('account_code', ''), e.get('account_name', ''), f"{amt:,.2f} ₺"))
        tot_exp = data.get('total_expenses') or 0
        rows.append(("", "TOPLAM GİDER", f"{tot_exp:,.2f} ₺"))
        rows.append(("", "", ""))
        net = data.get('net_profit') or 0
        rows.append(("", "NET KAR/ZARAR", f"{net:,.2f} ₺"))

        table.setRowCount(len(rows))
        for i, (code, name, val) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(code))
            table.setItem(i, 1, QTableWidgetItem(name))
            item = QTableWidgetItem(val)
            if "TOPLAM" in name or "NET" in name:
                item.setForeground(QColor(AppStyles.GREEN if net >= 0 else AppStyles.RED))
                item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            table.setItem(i, 2, item)

        self.accounting_layout.addWidget(table)

    def show_trial_balance(self, end_date):
        title = QLabel(f"📊 Deneme Bilançosu - {end_date}")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        self.accounting_layout.addWidget(title)

        data = self.report_service.get_trial_balance(self.branch_id, end_date)
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(['Hesap Kodu', 'Hesap Adı', 'Borç', 'Alacak'])
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)
        table.setStyleSheet(self._table_style())
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        table.setRowCount(len(data))
        for i, t in enumerate(data):
            debit = t.get('total_debit') or 0
            credit = t.get('total_credit') or 0
            table.setItem(i, 0, QTableWidgetItem(str(t.get('account_code', ''))))
            table.setItem(i, 1, QTableWidgetItem(str(t.get('account_name', ''))))
            table.setItem(i, 2, QTableWidgetItem(f"{debit:,.2f} ₺"))
            table.setItem(i, 3, QTableWidgetItem(f"{credit:,.2f} ₺"))

        self.accounting_layout.addWidget(table)

    def show_invoice_summary(self, start, end):
        title = QLabel(f"📊 Fatura Özeti - {start} / {end}")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        self.accounting_layout.addWidget(title)

        stats = self.report_service.get_invoice_stats(self.branch_id, start, end)
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(['Kalem / Başlık', 'Değer'])
        table.verticalHeader().setVisible(False)
        table.setStyleSheet(self._table_style())
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        metrics = [
            ("📄 Toplam Fatura Sayısı", str(stats.get('total_invoices') or 0)),
            ("💰 Toplam Satış Tutarı", f"{float(stats.get('total_sales') or 0):,.2f} ₺"),
            ("💵 Nakit Satış", f"{float(stats.get('total_cash_sales') or 0):,.2f} ₺"),
            ("💳 Kredi Kartı / POS Satış", f"{float(stats.get('total_card_sales') or 0):,.2f} ₺"),
            ("🛒 Toplam Alış Tutarı", f"{float(stats.get('total_purchases') or 0):,.2f} ₺"),
            ("✅ Ödenen Fatura Sayısı", str(stats.get('paid_invoices') or 0)),
            ("⏳ Bekleyen / Ödenmemiş Fatura", str(stats.get('unpaid_invoices') or 0)),
            ("📈 Bekleyen Müşteri Alacağı", f"{float(stats.get('total_receivables') or 0):,.2f} ₺"),
            ("📉 Bekleyen Tedarikçi Borcu", f"{float(stats.get('total_payables') or 0):,.2f} ₺")
        ]
        table.setRowCount(len(metrics))
        for r_i, (k, v) in enumerate(metrics):
            table.setItem(r_i, 0, QTableWidgetItem(k))
            v_item = QTableWidgetItem(v)
            v_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            v_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            table.setItem(r_i, 1, v_item)

        self.accounting_layout.addWidget(table)

    def show_aging(self, as_of_date):
        title = QLabel(f"📊 Cari Yaşlandırma - {as_of_date}")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        self.accounting_layout.addWidget(title)

        data = self.report_service.get_customer_aging(self.branch_id, as_of_date)
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(['Müşteri', 'Bakiye', '0-30 Gün', '31-60 Gün', '60+ Gün'])
        table.verticalHeader().setVisible(False)
        table.setStyleSheet(self._table_style())
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        table.setRowCount(len(data))
        for i, a in enumerate(data):
            bal = a.get('balance') or 0
            d1 = a.get('day_1_30') or 0
            d2 = a.get('day_31_60') or 0
            d3 = a.get('day_61_90') or 0
            table.setItem(i, 0, QTableWidgetItem(str(a.get('customer_name', ''))))
            table.setItem(i, 1, QTableWidgetItem(f"{bal:,.2f} ₺"))
            table.setItem(i, 2, QTableWidgetItem(f"{d1:,.2f} ₺"))
            table.setItem(i, 3, QTableWidgetItem(f"{d2:,.2f} ₺"))
            table.setItem(i, 4, QTableWidgetItem(f"{d3:,.2f} ₺"))

        self.accounting_layout.addWidget(table)

    def show_daily_summary(self, date):
        title = QLabel(f"📊 Günlük Özet - {date}")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        self.accounting_layout.addWidget(title)

        data = self.report_service.get_daily_summary(self.branch_id, date)
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(['Kalem / Başlık', 'Değer'])
        table.verticalHeader().setVisible(False)
        table.setStyleSheet(self._table_style())
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        metrics = [
            ("📄 Fatura Sayısı", str(data.get('total_invoices') or 0)),
            ("👥 Aktif Müşteri", str(data.get('unique_customers') or 0)),
            ("💰 Günlük Satış", f"{float(data.get('daily_sales') or 0):,.2f} ₺"),
            ("💵 Nakit Satış", f"{float(data.get('daily_cash_sales') or 0):,.2f} ₺"),
            ("💳 Kredi Kartı / POS Satış", f"{float(data.get('daily_card_sales') or 0):,.2f} ₺"),
            ("🛒 Günlük Alış", f"{float(data.get('daily_purchases') or 0):,.2f} ₺"),
            ("💸 Günlük Tahsilat", f"{float(data.get('daily_collections') or 0):,.2f} ₺")
        ]
        table.setRowCount(len(metrics))
        for r_i, (k, v) in enumerate(metrics):
            table.setItem(r_i, 0, QTableWidgetItem(k))
            v_item = QTableWidgetItem(v)
            v_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            v_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            table.setItem(r_i, 1, v_item)

        self.accounting_layout.addWidget(table)

    # ==================== EXCEL AKTARIMI ====================

    def export_to_excel(self):
        """Aktif sekmedeki verileri tam formatlı Excel dosyasına aktarır"""
        cur_tab = self.tabs.currentIndex()
        now_str = datetime.now().strftime('%Y%m%d_%H%M')

        if cur_tab == 0:
            prefix = "Kazanc_Gider_Analizi"
        elif cur_tab == 1:
            prefix = "Musteri_Cari_Listesi"
        else:
            prefix = "Muhasebe_Raporu"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Raporu Excel Olarak Kaydet",
            f"{prefix}_{now_str}.xlsx",
            "Excel Dosyası (*.xlsx)"
        )
        if not file_path:
            return

        try:
            import pandas as pd

            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                if cur_tab == 0:
                    # Sekme 1: Kategori özeti + Detaylı hareketler
                    df_cat = self._table_to_dataframe(self.fin_cat_table)
                    df_det = self._table_to_dataframe(self.fin_details_table)
                    df_cat.to_excel(writer, sheet_name="Kategori Dagilimi", index=False)
                    df_det.to_excel(writer, sheet_name="Detayli Hareketler", index=False)

                elif cur_tab == 1:
                    # Sekme 2: Müşteri listesi
                    df_cust = self._table_to_dataframe(self.cust_table)
                    df_cust.to_excel(writer, sheet_name="Musteriler ve Cariler", index=False)

                else:
                    # Sekme 3: Standart muhasebe tablosu
                    tables = self.accounting_frame.findChildren(QTableWidget)
                    if tables:
                        df_acc = self._table_to_dataframe(tables[0])
                        df_acc.to_excel(writer, sheet_name="Muhasebe Raporu", index=False)
                    else:
                        QMessageBox.warning(self, "Uyarı", "Aktarılacak rapor tablosu bulunamadı!")
                        return

            QMessageBox.information(self, "Başarılı", f"✅ Rapor başarıyla Excel'e aktarıldı:\n\n{file_path}")
        except Exception as e:
            logger.error(f"ReportsPage export_to_excel hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Excel'e aktarım sırasında hata oluştu:\n{e}")

    def _table_to_dataframe(self, table: QTableWidget):
        """QTableWidget'ı temiz bir pandas DataFrame'e dönüştürür"""
        import pandas as pd
        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        rows = []
        for r in range(table.rowCount()):
            row_vals = []
            for c in range(table.columnCount()):
                it = table.item(r, c)
                txt = it.text().replace(" ₺", "").replace(".", "").replace(",", ".") if it else ""
                try:
                    row_vals.append(float(txt))
                except Exception:
                    row_vals.append(it.text() if it else "")
            rows.append(row_vals)
        return pd.DataFrame(rows, columns=headers)

    # ==================== HIZLI TARİH FİLTRELERİ ====================

    def _set_this_month(self):
        now = QDate.currentDate()
        self.start_date.setDate(QDate(now.year(), now.month(), 1))
        self.end_date.setDate(now)

    def _set_last_month(self):
        now = datetime.now()
        first_this = datetime(now.year, now.month, 1)
        last_prev = first_this - timedelta(days=1)
        first_prev = datetime(last_prev.year, last_prev.month, 1)
        self.start_date.setDate(QDate(first_prev.year, first_prev.month, 1))
        self.end_date.setDate(QDate(last_prev.year, last_prev.month, last_prev.day))

    def _set_this_year(self):
        now = QDate.currentDate()
        self.start_date.setDate(QDate(now.year(), 1, 1))
        self.end_date.setDate(now)

    def _set_last_30_days(self):
        now = QDate.currentDate()
        self.start_date.setDate(now.addDays(-30))
        self.end_date.setDate(now)

    # ==================== ORTAK STİLLER ====================

    def _table_style(self):
        return f"""
            QTableWidget {{
                background-color: transparent;
                border: none;
                gridline-color: {AppStyles.BORDER};
                color: {AppStyles.TEXT_PRIMARY};
                font-size: 9pt;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
                border: none;
            }}
            QTableWidget::item:selected {{
                background-color: {AppStyles.PRIMARY}40;
                color: white;
            }}
            QHeaderView {{
                background-color: #1e1e28;
                border: none;
            }}
            QHeaderView::section {{
                background-color: #1e1e28;
                color: #FFFFFF !important;
                padding: 8px 6px;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                border-right: 1px solid #282838;
                font-weight: bold;
                font-size: 8.5pt;
                min-height: 36px;
            }}
        """

    def _input_style(self):
        return f"""
            background-color: {AppStyles.BG_DARK};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 9pt;
        """
