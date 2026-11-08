# src/ui/central_pages/all_reports_page.py
"""
Tüm Şubelerin Raporları - Genel Merkez Görünümü
Tüm şubelerin aylık ve yıllık net ciroları, giderleri, fire zararları ve cari hesapları
"""

import os
import calendar
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QGraphicsDropShadowEffect,
    QHeaderView, QPushButton, QComboBox, QSpinBox, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ...services.turnover_service import turnover_service
from ...services.stock_count_service import stock_count_service
from ...services.customer_service import CustomerService
from ..styles import AppStyles


class AllReportsPage(QWidget):
    """Tüm şubelerin aylık/yıllık konsolide finansal raporları"""

    def __init__(self, user: User, central_window=None):
        super().__init__()
        self.user = user
        self.central_window = central_window
        self.customer_service = CustomerService()
        self._cached_report_rows = []

        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setObjectName("AllReportsPage")
        self.setStyleSheet(f"#AllReportsPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(25, 20, 25, 20)

        # 1. ÜST BAŞLIK VE FİLTRE ÇUBUĞU
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
        top_layout.setSpacing(12)

        # Sol Başlık
        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel("📈 Tüm Şubeler Konsolide Raporları")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; border: none;")
        left.addWidget(title)
        subtitle = QLabel("Genel Merkez • Tüm şubelerin aylık & yıllık net ciroları, fire kayıpları ve cari bakiyeleri")
        subtitle.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_SECONDARY}; border: none;")
        left.addWidget(subtitle)
        top_layout.addLayout(left)

        top_layout.addStretch()

        # Ay Seçici
        top_layout.addWidget(QLabel("📆 Ay:"))
        self.month_combo = QComboBox()
        self.month_combo.addItems([
            "Tüm Aylar (1-12)",
            "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
        ])
        now_dt = datetime.now()
        self.month_combo.setCurrentIndex(now_dt.month)  # Index 1 = Ocak ... 11 = Kasım
        self.month_combo.setMinimumHeight(34)
        self.month_combo.setMinimumWidth(130)
        self.month_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: 500;
            }}
            QComboBox::drop-down {{ border: none; }}
        """)
        self.month_combo.currentIndexChanged.connect(self.load_data)
        top_layout.addWidget(self.month_combo)

        # Yıl Seçici
        top_layout.addWidget(QLabel("🗓️ Yıl:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2050)
        self.year_spin.setValue(now_dt.year)
        self.year_spin.setMinimumHeight(34)
        self.year_spin.setMinimumWidth(85)
        self.year_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 8px;
                font-weight: 500;
            }}
        """)
        self.year_spin.valueChanged.connect(self.load_data)
        top_layout.addWidget(self.year_spin)

        # Yenile Butonu
        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setMinimumHeight(34)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.BG_LIGHT};
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        refresh_btn.clicked.connect(self.load_data)
        top_layout.addWidget(refresh_btn)

        # Excel'e Aktar Butonu
        export_btn = QPushButton("📥 Excel'e Aktar")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setMinimumHeight(34)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.GREEN};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 16px;
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

        # 2. KONSOLİDE KPI KARTLARI (Genel Merkez Dashboard'undaki kartların Aylık & Yıllık Tutarları)
        self.kpi_cards_container = QFrame()
        self.kpi_cards_container.setStyleSheet("background: transparent; border: none;")
        self.kpi_layout = QGridLayout(self.kpi_cards_container)
        self.kpi_layout.setContentsMargins(0, 0, 0, 0)
        self.kpi_layout.setSpacing(10)
        for col_idx in range(4):
            self.kpi_layout.setColumnStretch(col_idx, 1)
        layout.addWidget(self.kpi_cards_container)

        # 3. ŞUBE KARŞILAŞTIRMA TABLOSU
        table_frame = QFrame()
        table_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
                padding: 12px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        table_frame.setGraphicsEffect(shadow)

        table_layout = QVBoxLayout(table_frame)
        table_layout.setSpacing(8)

        t_head = QHBoxLayout()
        table_title = QLabel("🏢 Şube Bazlı Detaylı Karşılaştırma & Bilanço Özeti")
        table_title.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; border: none;")
        t_head.addWidget(table_title)
        t_head.addStretch()
        table_layout.addLayout(t_head)

        self.table = QTableWidget()
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels([
            '🏢 Şube Adı',
            '📅 Aylık Ciro', '📉 Aylık Gider', '🔥 Aylık Fire', '⚖️ Aylık Net',
            '📆 Yıllık Ciro', '📉 Yıllık Gider', '🔥 Yıllık Fire', '🏆 Yıllık Net',
            '📈 Cari Alacak', '📉 Cari Borç', '⚖️ Net Cari Durum'
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setStyleSheet(f"""
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
                min-height: 38px;
            }}
        """)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for c in range(1, 12):
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.Stretch)

        table_layout.addWidget(self.table)
        layout.addWidget(table_frame, 1)

        self.setLayout(layout)

    def showEvent(self, event):
        super().showEvent(event)
        self.load_data()

    def create_stat_card(self, icon: str, title: str, monthly_val: float, yearly_val: float, color: str, sub_note: str = "") -> QFrame:
        """Aylık ve Yıllık değerleri dikey hizalayarak tam ve kesilmeden gösteren finansal kart"""
        card = QFrame()
        card.setFixedHeight(108)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 8px;
                border: 1px solid {AppStyles.BORDER};
                border-left: 4px solid {color};
                padding: 6px 10px;
            }}
            QFrame:hover {{
                border-color: {color};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 2)
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        # Üst başlık satırı
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 11pt;")
        top_row.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 8.5pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        top_row.addWidget(title_lbl)
        top_row.addStretch()

        if sub_note:
            note_lbl = QLabel(sub_note)
            note_lbl.setStyleSheet(f"font-size: 7.5pt; color: {AppStyles.TEXT_MUTED};")
            top_row.addWidget(note_lbl)
        layout.addLayout(top_row)

        # 1. Satır: Aylık Tutar
        m_row = QHBoxLayout()
        m_row.setContentsMargins(0, 0, 0, 0)
        m_tag = QLabel("📅 Aylık:")
        m_tag.setStyleSheet(f"font-size: 8pt; color: {AppStyles.TEXT_SECONDARY}; font-weight: 500;")
        m_row.addWidget(m_tag)

        m_val = QLabel(f"{monthly_val:,.2f} ₺")
        m_val.setStyleSheet(f"font-size: 11.5pt; font-weight: bold; color: {color};")
        m_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        m_row.addWidget(m_val, 1)
        layout.addLayout(m_row)

        # 2. Satır: Yıllık Tutar
        y_row = QHBoxLayout()
        y_row.setContentsMargins(0, 0, 0, 0)
        y_tag = QLabel("📆 Yıllık:")
        y_tag.setStyleSheet(f"font-size: 8pt; color: {AppStyles.TEXT_SECONDARY}; font-weight: 500;")
        y_row.addWidget(y_tag)

        y_val = QLabel(f"{yearly_val:,.2f} ₺")
        y_val.setStyleSheet(f"font-size: 10.5pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        y_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        y_row.addWidget(y_val, 1)
        layout.addLayout(y_row)

        return card

    def create_balance_card(self, icon: str, title: str, main_val: float, color: str, sub_info: str) -> QFrame:
        """Cari Bakiye Kartı - Ferah ve net görünüm"""
        card = QFrame()
        card.setFixedHeight(108)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 8px;
                border: 1px solid {AppStyles.BORDER};
                border-left: 4px solid {color};
                padding: 6px 10px;
            }}
            QFrame:hover {{
                border-color: {color};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 11pt;")
        top_row.addWidget(icon_lbl)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 8.5pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        top_row.addWidget(title_lbl)
        top_row.addStretch()
        layout.addLayout(top_row)

        val_lbl = QLabel(f"{main_val:,.2f} ₺")
        val_lbl.setStyleSheet(f"font-size: 13.5pt; font-weight: bold; color: {color}; min-height: 24px;")
        layout.addWidget(val_lbl)

        sub_lbl = QLabel(sub_info)
        sub_lbl.setStyleSheet(f"font-size: 8pt; color: {AppStyles.TEXT_MUTED};")
        sub_lbl.setWordWrap(True)
        layout.addWidget(sub_lbl)

        return card

    def load_data(self):
        """Tüm şubeler için aylık & yıllık verileri hesapla ve tabloya bas"""
        try:
            year = self.year_spin.value()
            m_idx = self.month_combo.currentIndex()  # 0 = Tüm Aylar, 1..12

            if m_idx == 0:
                month_start = f"{year}-01-01"
                month_end = f"{year}-12-31"
                month_label = f"Tüm {year} Yılı"
            else:
                month = m_idx
                month_start = f"{year:04d}-{month:02d}-01"
                _, last_day = calendar.monthrange(year, month)
                month_end = f"{year:04d}-{month:02d}-{last_day:02d}"
                month_names = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                               "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
                month_label = f"{month_names[m_idx-1]} {year}"

            year_start = f"{year}-01-01"
            year_end = f"{year}-12-31"

            # Şubeleri çek
            branches = db.fetch_all("""
                SELECT id, name, city
                FROM Branches
                WHERE is_active = TRUE
                ORDER BY id ASC
            """) or []

            # Cari Alacak & Borç verilerini CustomerService üzerinden çek
            cari_summary = self.customer_service.get_companies_balance_summary()
            total_rec = float(cari_summary.get('total_receivables', 0.0))
            total_pay = float(cari_summary.get('total_payables', 0.0))
            companies = cari_summary.get('companies', [])

            # Şube bazlı cari eşleme
            branch_cari_map = {}
            for c in companies:
                b_id = c.get('branch_id') or 0
                if b_id not in branch_cari_map:
                    branch_cari_map[b_id] = {'receivable': 0.0, 'payable': 0.0}
                branch_cari_map[b_id]['receivable'] += float(c.get('receivable') or 0.0)
                branch_cari_map[b_id]['payable'] += float(c.get('payable') or 0.0)

            # Toplam değişkenleri
            tot_m_inc = 0.0
            tot_m_exp = 0.0
            tot_m_waste = 0.0
            tot_m_net = 0.0

            tot_y_inc = 0.0
            tot_y_exp = 0.0
            tot_y_waste = 0.0
            tot_y_net = 0.0

            report_rows = []

            for b in branches:
                bid = b['id']
                bname = b['name']

                # 1. Aylık Finansal Veri
                m_fin = turnover_service.get_branch_financial_overview(bid, month_start, month_end)
                m_inc = m_fin['income']
                m_exp = m_fin['expense']
                m_waste = m_fin['waste']
                m_net = m_inc - m_exp - m_waste

                # 2. Yıllık Finansal Veri
                y_fin = turnover_service.get_branch_financial_overview(bid, year_start, year_end)
                y_inc = y_fin['income']
                y_exp = y_fin['expense']
                y_waste = y_fin['waste']
                y_net = y_inc - y_exp - y_waste

                # 3. Cari Veri
                b_c = branch_cari_map.get(bid, {'receivable': 0.0, 'payable': 0.0})
                b_rec = b_c['receivable']
                b_pay = b_c['payable']
                b_net_cari = b_rec - b_pay

                report_rows.append({
                    'branch_id': bid,
                    'branch_name': bname,
                    'm_inc': m_inc,
                    'm_exp': m_exp,
                    'm_waste': m_waste,
                    'm_net': m_net,
                    'y_inc': y_inc,
                    'y_exp': y_exp,
                    'y_waste': y_waste,
                    'y_net': y_net,
                    'rec': b_rec,
                    'pay': b_pay,
                    'net_cari': b_net_cari
                })

                tot_m_inc += m_inc
                tot_m_exp += m_exp
                tot_m_waste += m_waste
                tot_m_net += m_net

                tot_y_inc += y_inc
                tot_y_exp += y_exp
                tot_y_waste += y_waste
                tot_y_net += y_net

            self._cached_report_rows = report_rows

            # 4. KPI KARTLARINI GÜNCELLE
            # Eski kartları temizle
            while self.kpi_layout.count():
                item = self.kpi_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Kart 1: Ciro
            c_ciro = self.create_stat_card("💰", "Konsolide Gelir / Ciro", tot_m_inc, tot_y_inc, AppStyles.GREEN, month_label)
            self.kpi_layout.addWidget(c_ciro, 0, 0)

            # Kart 2: Gider
            c_gider = self.create_stat_card("💸", "Konsolide Faaliyet Gideri", tot_m_exp, tot_y_exp, AppStyles.RED, "Kasa Çıkışları")
            self.kpi_layout.addWidget(c_gider, 0, 1)

            # Kart 3: Fire Zararı
            c_fire = self.create_stat_card("🔥", "Konsolide Fire / Zayiat", tot_m_waste, tot_y_waste, AppStyles.DANGER, "Zayiat Kayıpları")
            self.kpi_layout.addWidget(c_fire, 0, 2)

            # Kart 4: Net Kâr (Gelir - Gider - Fire)
            net_col = AppStyles.CYAN if tot_m_net >= 0 else AppStyles.RED
            c_net = self.create_stat_card("🏆", "Net Kâr (Gelir - Gider - Fire)", tot_m_net, tot_y_net, net_col, "Net Kalan")
            self.kpi_layout.addWidget(c_net, 0, 3)

            # Kart 5: Cari Alacak
            c_rec = self.create_balance_card("📈", "Toplam Cari Alacak", total_rec, AppStyles.CYAN, "Müşteri Bekleyen Ödemeler")
            self.kpi_layout.addWidget(c_rec, 1, 0)

            # Kart 6: Cari Borç
            c_pay = self.create_balance_card("📉", "Toplam Cari Borç", total_pay, AppStyles.ORANGE, "Tedarikçilere Borçlar")
            self.kpi_layout.addWidget(c_pay, 1, 1)

            # Kart 7: Net Cari Bakiye
            net_cari_total = total_rec - total_pay
            cari_col = AppStyles.GREEN if net_cari_total >= 0 else AppStyles.RED
            cari_sub = "Net Alacak Fazlası" if net_cari_total >= 0 else "Net Borç Durumu"
            c_net_cari = self.create_balance_card("⚖️", "Net Cari Bakiye", net_cari_total, cari_col, cari_sub)
            self.kpi_layout.addWidget(c_net_cari, 1, 2)

            # Kart 8: Genel Kümülatif Net Rozeti
            gen_cum_net = turnover_service.get_three_branches_summary().get('grand_cumulative_net', 0.0)
            cum_col = AppStyles.GREEN if gen_cum_net >= 0 else AppStyles.DANGER
            c_cum = self.create_balance_card("🏆", "Tüm Zamanlar Net Kümülatif", gen_cum_net, cum_col, "Tüm Gelir - Gider - Fire")
            self.kpi_layout.addWidget(c_cum, 1, 3)

            # 5. TABLOYU DOLDUR
            self.table.setRowCount(0)
            row_idx = 0

            for r in report_rows:
                self.table.insertRow(row_idx)

                # 0: Şube Adı
                name_item = QTableWidgetItem(f"🏢 {r['branch_name']}")
                name_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(row_idx, 0, name_item)

                # 1: Aylık Gelir
                m_inc_item = QTableWidgetItem(f"{r['m_inc']:,.2f} ₺")
                m_inc_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                m_inc_item.setForeground(QColor(AppStyles.GREEN))
                self.table.setItem(row_idx, 1, m_inc_item)

                # 2: Aylık Gider
                m_exp_item = QTableWidgetItem(f"{r['m_exp']:,.2f} ₺")
                m_exp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                m_exp_item.setForeground(QColor(AppStyles.RED if r['m_exp'] > 0 else AppStyles.TEXT_MUTED))
                self.table.setItem(row_idx, 2, m_exp_item)

                # 3: Aylık Fire
                m_waste_item = QTableWidgetItem(f"{r['m_waste']:,.2f} ₺")
                m_waste_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                m_waste_item.setForeground(QColor(AppStyles.DANGER if r['m_waste'] > 0 else AppStyles.TEXT_MUTED))
                self.table.setItem(row_idx, 3, m_waste_item)

                # 4: Aylık Net
                m_net_item = QTableWidgetItem(f"{r['m_net']:,.2f} ₺")
                m_net_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                m_net_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                m_net_item.setForeground(QColor(AppStyles.CYAN if r['m_net'] >= 0 else AppStyles.RED))
                self.table.setItem(row_idx, 4, m_net_item)

                # 5: Yıllık Gelir
                y_inc_item = QTableWidgetItem(f"{r['y_inc']:,.2f} ₺")
                y_inc_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                y_inc_item.setForeground(QColor(AppStyles.GREEN))
                self.table.setItem(row_idx, 5, y_inc_item)

                # 6: Yıllık Gider
                y_exp_item = QTableWidgetItem(f"{r['y_exp']:,.2f} ₺")
                y_exp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                y_exp_item.setForeground(QColor(AppStyles.RED if r['y_exp'] > 0 else AppStyles.TEXT_MUTED))
                self.table.setItem(row_idx, 6, y_exp_item)

                # 7: Yıllık Fire
                y_waste_item = QTableWidgetItem(f"{r['y_waste']:,.2f} ₺")
                y_waste_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                y_waste_item.setForeground(QColor(AppStyles.DANGER if r['y_waste'] > 0 else AppStyles.TEXT_MUTED))
                self.table.setItem(row_idx, 7, y_waste_item)

                # 8: Yıllık Net
                y_net_item = QTableWidgetItem(f"{r['y_net']:,.2f} ₺")
                y_net_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                y_net_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                y_net_item.setForeground(QColor(AppStyles.CYAN if r['y_net'] >= 0 else AppStyles.RED))
                self.table.setItem(row_idx, 8, y_net_item)

                # 9: Cari Alacak
                rec_item = QTableWidgetItem(f"{r['rec']:,.2f} ₺")
                rec_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                rec_item.setForeground(QColor(AppStyles.CYAN if r['rec'] > 0 else AppStyles.TEXT_MUTED))
                self.table.setItem(row_idx, 9, rec_item)

                # 10: Cari Borç
                pay_item = QTableWidgetItem(f"{r['pay']:,.2f} ₺")
                pay_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                pay_item.setForeground(QColor(AppStyles.ORANGE if r['pay'] > 0 else AppStyles.TEXT_MUTED))
                self.table.setItem(row_idx, 10, pay_item)

                # 11: Net Cari Durum
                nc_item = QTableWidgetItem(f"{r['net_cari']:,.2f} ₺")
                nc_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                nc_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                nc_item.setForeground(QColor(AppStyles.GREEN if r['net_cari'] >= 0 else AppStyles.RED))
                self.table.setItem(row_idx, 11, nc_item)

                row_idx += 1

            # TOPLAM (KONSOLİDE) SATIRI EKLE
            self.table.insertRow(row_idx)

            tot_name = QTableWidgetItem("🏆 GENEL TOPLAM (KONSOLİDE)")
            tot_name.setFont(QFont("Segoe UI", 9, QFont.Bold))
            tot_name.setBackground(QColor(AppStyles.PRIMARY).darker(200))
            tot_name.setForeground(QColor("#FFFFFF"))
            self.table.setItem(row_idx, 0, tot_name)

            col_totals = [
                (1, tot_m_inc, AppStyles.GREEN),
                (2, tot_m_exp, AppStyles.RED),
                (3, tot_m_waste, AppStyles.DANGER),
                (4, tot_m_net, AppStyles.CYAN if tot_m_net >= 0 else AppStyles.RED),
                (5, tot_y_inc, AppStyles.GREEN),
                (6, tot_y_exp, AppStyles.RED),
                (7, tot_y_waste, AppStyles.DANGER),
                (8, tot_y_net, AppStyles.CYAN if tot_y_net >= 0 else AppStyles.RED),
                (9, total_rec, AppStyles.CYAN),
                (10, total_pay, AppStyles.ORANGE),
                (11, total_rec - total_pay, AppStyles.GREEN if (total_rec - total_pay) >= 0 else AppStyles.RED),
            ]

            for col_i, val, col_color in col_totals:
                t_item = QTableWidgetItem(f"{val:,.2f} ₺")
                t_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                t_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                t_item.setForeground(QColor(col_color))
                t_item.setBackground(QColor(AppStyles.PRIMARY).darker(200))
                self.table.setItem(row_idx, col_i, t_item)

        except Exception as e:
            logger.error(f"AllReportsPage load_data hatası: {e}")

    def export_to_excel(self):
        """Tüm şubelerin karşılaştırmalı konsolide raporunu Excel dosyasına aktarır"""
        try:
            now_str = datetime.now().strftime('%Y%m%d_%H%M')
            default_name = f"Genel_Merkez_Konsolide_Rapor_{now_str}.xlsx"

            file_path, _ = QFileDialog.getSaveFileName(
                self, "Konsolide Raporu Excel Olarak Kaydet",
                default_name,
                "Excel Dosyası (*.xlsx)"
            )
            if not file_path:
                return

            import pandas as pd

            headers = [
                "Şube Adı",
                "Aylık Gelir (TL)", "Aylık Gider (TL)", "Aylık Fire (TL)", "Aylık Net Kazanç (TL)",
                "Yıllık Gelir (TL)", "Yıllık Gider (TL)", "Yıllık Fire (TL)", "Yıllık Net Kazanç (TL)",
                "Cari Alacak (TL)", "Cari Borç (TL)", "Net Cari Durum (TL)"
            ]

            rows_data = []
            for r in range(self.table.rowCount()):
                row_vals = []
                for c in range(self.table.columnCount()):
                    it = self.table.item(r, c)
                    txt = it.text().replace("🏢 ", "").replace("🏆 ", "").replace(" ₺", "").replace(".", "").replace(",", ".") if it else ""
                    # Sayısala dönüştürmeyi dene
                    if c > 0:
                        try:
                            row_vals.append(float(txt))
                        except Exception:
                            row_vals.append(txt)
                    else:
                        row_vals.append(txt)
                rows_data.append(row_vals)

            df = pd.DataFrame(rows_data, columns=headers)

            # Excel writer ile formatlama
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="Konsolide Rapor", index=False)

            QMessageBox.information(
                self, "Başarılı",
                f"✅ Genel Merkez Konsolide Raporu başarıyla Excel'e aktarıldı:\n\n{file_path}"
            )
        except Exception as e:
            logger.error(f"AllReportsPage export_to_excel hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Excel'e aktarım sırasında bir hata oluştu:\n{e}")
