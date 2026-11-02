# src/ui/pages/reports_page.py
"""
Gelişmiş Raporlar Sayfası
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QDateEdit, QComboBox, QMessageBox, QFileDialog, QScrollArea,
    QGraphicsDropShadowEffect, QHeaderView, QTabWidget
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor
from datetime import datetime, timedelta
import re

from ..core.database import db
from ..core.logger import logger
from ..models.user import User
from ..services.report_service import ReportService
from ..services.excel_service import ExcelService
from .styles import AppStyles


class ReportsPage(QWidget):
    """Gelişmiş raporlar sayfası"""

    def __init__(self, user: User, branch_id: int, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window
        self.report_service = ReportService()
        self.excel_service = ExcelService()

        self.init_ui()
        self.generate_report()

    def init_ui(self):
        self.setObjectName("ReportsPage")
        self.setStyleSheet(f"#ReportsPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)

        # Üst bar
        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(3)
        title = QLabel("📈 Gelişmiş Raporlar")
        title.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)
        subtitle = QLabel("Detaylı finansal raporlar ve analizler")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        top_bar.addLayout(left)
        top_bar.addStretch()

        export_btn = QPushButton("📤  Excel'e Aktar")
        export_btn.clicked.connect(self.export_to_excel)
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setMinimumHeight(42)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.GREEN};
                color: white; border: none; border-radius: 8px;
                font-weight: bold; font-size: 11pt; padding: 0 25px;
            }}
            QPushButton:hover {{ background-color: #059669; }}
        """)
        top_bar.addWidget(export_btn)
        layout.addLayout(top_bar)

        # Filtreler
        filters = QFrame()
        filters.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                border: 1px solid {AppStyles.BORDER};
                padding: 15px;
            }}
        """)
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("📊 Rapor Tipi:"))
        self.report_type = QComboBox()
        self.report_type.addItems([
            "Bilanço", "Gelir Tablosu", "Deneme Bilançosu",
            "Fatura Özeti", "Cari Yaşlandırma", "Günlük Özet"
        ])
        self.report_type.setMinimumHeight(40)
        self.report_type.setMinimumWidth(200)
        self.report_type.currentTextChanged.connect(self.generate_report)
        filter_layout.addWidget(self.report_type)

        filter_layout.addWidget(QLabel("📅 Başlangıç:"))
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd.MM.yyyy")
        self.start_date.setMinimumHeight(40)
        filter_layout.addWidget(self.start_date)

        filter_layout.addWidget(QLabel("📅 Bitiş:"))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("dd.MM.yyyy")
        self.end_date.setMinimumHeight(40)
        filter_layout.addWidget(self.end_date)

        generate_btn = QPushButton("📊 Rapor Oluştur")
        generate_btn.clicked.connect(self.generate_report)
        generate_btn.setMinimumHeight(40)
        generate_btn.setStyleSheet(
            f"background-color: {AppStyles.PRIMARY}; color: white; "
            "border: none; border-radius: 8px; font-weight: bold; padding: 0 20px;"
        )
        filter_layout.addWidget(generate_btn)

        filter_layout.addStretch()
        filters.setLayout(filter_layout)
        layout.addWidget(filters)

        # Rapor içeriği
        self.report_frame = QFrame()
        self.report_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                border: 1px solid {AppStyles.BORDER};
                padding: 20px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 5)
        self.report_frame.setGraphicsEffect(shadow)

        self.report_layout = QVBoxLayout()
        self.report_frame.setLayout(self.report_layout)
        layout.addWidget(self.report_frame)

        self.setLayout(layout)

    def showEvent(self, event):
        """Sayfa her görüntülendiğinde raporu tazele"""
        super().showEvent(event)
        self.generate_report()

    def generate_report(self):
        """Rapor oluştur"""
        # Eski içeriği temizle
        while self.report_layout.count():
            item = self.report_layout.takeAt(0)
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
            logger.error(f"Rapor hatası: {e}")
            error = QLabel(f"⚠️ Rapor oluşturulamadı: {str(e)}")
            error.setStyleSheet(f"color: {AppStyles.RED}; font-size: 11pt;")
            self.report_layout.addWidget(error)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def show_balance_sheet(self, end_date):
        """Bilanço"""
        title = QLabel(f"📊 Bilanço Raporu - {end_date}")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        self.report_layout.addWidget(title)

        data = self.report_service.get_balance_sheet(self.branch_id, end_date)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(['Hesap Kodu', 'Hesap Adı', 'Bakiye'])
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(40)
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

        self.report_layout.addWidget(table)

    def show_income_statement(self, start, end):
        """Gelir tablosu"""
        title = QLabel(f"📊 Gelir Tablosu - {start} / {end}")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        self.report_layout.addWidget(title)

        data = self.report_service.get_income_statement(self.branch_id, start, end)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(['Hesap Kodu', 'Hesap Adı', 'Tutar'])
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(40)
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
            table.setItem(i, 2, item)

        self.report_layout.addWidget(table)

    def show_trial_balance(self, end_date):
        """Deneme bilançosu"""
        title = QLabel(f"📊 Deneme Bilançosu - {end_date}")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        self.report_layout.addWidget(title)

        data = self.report_service.get_trial_balance(self.branch_id, end_date)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(['Hesap Kodu', 'Hesap Adı', 'Borç', 'Alacak'])
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(40)
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

        self.report_layout.addWidget(table)

    def show_invoice_summary(self, start, end):
        """Fatura özeti"""
        title = QLabel(f"📊 Fatura Özeti - {start} / {end}")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        self.report_layout.addWidget(title)

        stats = self.report_service.get_invoice_stats(self.branch_id, start, end)

        tot_inv = stats.get('total_invoices') or 0
        tot_sales = stats.get('total_sales') or 0
        cash_sales = stats.get('total_cash_sales') or 0
        card_sales = stats.get('total_card_sales') or 0
        tot_purch = stats.get('total_purchases') or 0
        paid_inv = stats.get('paid_invoices') or 0
        unpaid_inv = stats.get('unpaid_invoices') or 0
        tot_rec = stats.get('total_receivables') or 0
        tot_pay = stats.get('total_payables') or 0

        info = f"""
        📄 Toplam Fatura: {tot_inv}
        💰 Toplam Satış: {tot_sales:,.2f} ₺
           💵 Nakit Satış: {cash_sales:,.2f} ₺
           💳 Kredi Kartı / POS Satış: {card_sales:,.2f} ₺
        🛒 Toplam Alış: {tot_purch:,.2f} ₺
        ✅ Ödenen Fatura: {paid_inv}
        ⏳ Ödenmemiş Fatura: {unpaid_inv}
        📈 Bekleyen Müşteri Alacağı: {tot_rec:,.2f} ₺
        📉 Bekleyen Tedarikçi Borcu: {tot_pay:,.2f} ₺
        """

        info_label = QLabel(info)
        info_label.setStyleSheet(f"font-size: 12pt; color: {AppStyles.TEXT_PRIMARY}; line-height: 1.8;")
        self.report_layout.addWidget(info_label)

    def show_aging(self, as_of_date):
        """Cari yaşlandırma"""
        title = QLabel(f"📊 Cari Yaşlandırma - {as_of_date}")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        self.report_layout.addWidget(title)

        data = self.report_service.get_customer_aging(self.branch_id, as_of_date)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(['Müşteri', 'Bakiye', '0-30 Gün', '31-60 Gün', '60+ Gün'])
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(40)
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

        self.report_layout.addWidget(table)

    def show_daily_summary(self, date):
        """Günlük özet"""
        title = QLabel(f"📊 Günlük Özet - {date}")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        self.report_layout.addWidget(title)

        data = self.report_service.get_daily_summary(self.branch_id, date)

        tot_inv = data.get('total_invoices') or 0
        uniq_cust = data.get('unique_customers') or 0
        d_sales = data.get('daily_sales') or 0
        d_cash = data.get('daily_cash_sales') or 0
        d_card = data.get('daily_card_sales') or 0
        d_purch = data.get('daily_purchases') or 0
        d_coll = data.get('daily_collections') or 0

        info = f"""
        📄 Fatura Sayısı: {tot_inv}
        👥 Aktif Müşteri: {uniq_cust}
        💰 Günlük Satış: {d_sales:,.2f} ₺
           💵 Nakit Satış: {d_cash:,.2f} ₺
           💳 Kredi Kartı / POS Satış: {d_card:,.2f} ₺
        🛒 Günlük Alış: {d_purch:,.2f} ₺
        💸 Günlük Tahsilat: {d_coll:,.2f} ₺
        """

        info_label = QLabel(info)
        info_label.setStyleSheet(f"font-size: 12pt; color: {AppStyles.TEXT_PRIMARY}; line-height: 1.8;")
        self.report_layout.addWidget(info_label)

    def _table_style(self):
        return f"""
            QTableWidget {{
                background-color: transparent; border: none;
                gridline-color: {AppStyles.BORDER}; color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{ padding: 10px; border: none; }}
            QHeaderView {{
                background-color: #1e1e28;
                border: none;
            }}
            QHeaderView::section {{
                background-color: #1e1e28;
                color: #FFFFFF !important;
                padding: 6px 10px; border: none;
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
        """

    def _sanitize_sheet_name(self, name: str, used_names: set) -> str:
        """
        Excel sheet ismi için geçerli hale getir.
        - Yasak karakterleri kaldır: \\ / * ? : [ ]
        - Maksimum 31 karakter
        - Boş veya çakışıyorsa numaralandır
        """
        # Yasak karakterleri temizle
        clean = re.sub(r'[\\/*?:\[\]]', '', name).strip()
        if not clean:
            clean = "Rapor"

        # 31 karakter sınırı
        clean = clean[:31]

        # Çakışma varsa numaralandır
        base = clean
        counter = 1
        while clean in used_names:
            suffix = f"_{counter}"
            clean = base[:31 - len(suffix)] + suffix
            counter += 1

        used_names.add(clean)
        return clean

    def export_to_excel(self):
        """Excel'e aktar — TÜM tabloları her biri ayrı sheet'e yazar"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Raporu Kaydet",
            f"rapor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx)"
        )

        if not file_path:
            return

        try:
            import pandas as pd

            report_type = self.report_type.currentText()
            start = self.start_date.date().toString("yyyy-MM-dd")
            end = self.end_date.date().toString("yyyy-MM-dd")

            # Rapor çerçevesinde bulunan tüm tabloları al
            tables = self.report_frame.findChildren(QTableWidget)

            if not tables:
                QMessageBox.warning(
                    self, "Uyarı",
                    "Bu raporda Excel'e aktarılacak tablo bulunamadı.\n"
                    "(Özet raporlar grafikseldir, tablo içermez.)"
                )
                return

            used_sheet_names = set()

            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                for idx, table in enumerate(tables):
                    # Tablo verilerini al
                    rows_data = []
                    headers = []
                    for col in range(table.columnCount()):
                        header_item = table.horizontalHeaderItem(col)
                        headers.append(header_item.text() if header_item else f"Sütun {col+1}")

                    for row in range(table.rowCount()):
                        row_data = []
                        for col in range(table.columnCount()):
                            item = table.item(row, col)
                            row_data.append(item.text() if item else '')
                        rows_data.append(row_data)

                    if not rows_data:
                        continue

                    # Sheet ismi üret
                    if len(tables) == 1:
                        base_name = report_type
                    else:
                        base_name = f"{report_type} - Tablo {idx + 1}"

                    sheet_name = self._sanitize_sheet_name(base_name, used_sheet_names)

                    # DataFrame oluştur ve yaz
                    df = pd.DataFrame(rows_data, columns=headers)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

            logger.info(f"✅ Rapor Excel'e kaydedildi: {file_path} ({len(tables)} tablo)")
            QMessageBox.information(
                self, "Başarılı",
                f"🎉 Rapor Excel'e kaydedildi:\n\n"
                f"📂 {file_path}\n"
                f"📊 Toplam {len(tables)} tablo aktarıldı."
            )
        except Exception as e:
            logger.error(f"Excel export hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Aktarım hatası:\n{str(e)}")