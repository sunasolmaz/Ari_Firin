# src/ui/pages/invoices_page.py
"""
Faturalar Sayfası - Cari Bakiye ve Fatura Yönetimi
Faturalar listesi kaldırıldı. Sadece firma alacak/verecek özeti ve fatura kesme var.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QDateEdit, QMessageBox, QDialog,
    QDialogButtonBox, QDoubleSpinBox, QTextEdit, QScrollArea,
    QGraphicsDropShadowEffect, QHeaderView, QInputDialog, QCompleter,
    QTabWidget, QCheckBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ...services.invoice_service import InvoiceService
from ...services.customer_service import CustomerService
from ..styles import AppStyles


class CustomerInvoicesDialog(QDialog):
    """
    Tek bir müşteri / firma için farklı tarihlerde kesilen tüm faturaları,
    ürün dökümlerini ve cari hesap durumunu gösteren modern açılır pencere
    """
    def __init__(self, user: User, branch_id: Optional[int], customer_id: int, customer_title: Optional[str] = None, parent=None, target_invoice_id: Optional[int] = None):
        super().__init__(parent)
        self.user = user
        self.branch_id = branch_id
        self.customer_id = customer_id
        self.customer_title = customer_title
        self.target_invoice_id = target_invoice_id
        self.customer_service = CustomerService()
        self.invoice_service = InvoiceService()
        self.customer_data = None
        self.invoices_data = []
        self.filtered_invoices = []

        c_name = customer_title or "Müşteri"
        self.setWindowTitle(f"🏢 {c_name} - Tüm Fatura & Cari Hesap Dökümü")
        self.resize(1260, 720)
        self.setMinimumSize(1020, 600)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; }}
            QLineEdit, QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10pt;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {AppStyles.PRIMARY};
            }}
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                gridline-color: #242430;
                font-size: 10pt;
            }}
            QTableWidget::item:selected {{
                background-color: rgba(37, 99, 235, 0.25);
            }}
        """)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Başlık & Firma Kartı
        header_card = QFrame()
        header_card.setObjectName("invoiceCustomerHeaderCard")
        header_card.setStyleSheet(f"""
            QFrame#invoiceCustomerHeaderCard {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-left: 5px solid {AppStyles.PRIMARY};
                border-radius: 8px;
                padding: 10px 14px;
            }}
        """)
        h_main_lay = QVBoxLayout(header_card)
        h_main_lay.setContentsMargins(4, 4, 4, 4)
        h_main_lay.setSpacing(10)

        v_info = QVBoxLayout()
        v_info.setSpacing(3)
        self.lbl_title = QLabel("Firma / Müşteri Ünvanı")
        self.lbl_title.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {AppStyles.CYAN};")
        v_info.addWidget(self.lbl_title)

        self.lbl_sub = QLabel("Cari Kodu: -   |   Tür: -   |   Tel: -   |   Vergi No: -")
        self.lbl_sub.setStyleSheet(f"font-size: 9pt; color: {AppStyles.TEXT_MUTED};")
        v_info.addWidget(self.lbl_sub)
        h_main_lay.addLayout(v_info)

        # 4 Mini İstatistik Kartı
        stats_box = QHBoxLayout()
        stats_box.setSpacing(10)

        c1, self.lbl_kpi_cnt = self._create_mini_kpi("Fatura Sayısı", "0 Adet", "#38bdf8")
        stats_box.addWidget(c1)

        c2, self.lbl_kpi_total = self._create_mini_kpi("Toplam Faturalaşma", "0.00 ₺", "#f1f5f9")
        stats_box.addWidget(c2)

        c3, self.lbl_kpi_paid = self._create_mini_kpi("Tahsilat / Ödeme", "0.00 ₺", "#10b981")
        stats_box.addWidget(c3)

        c4, self.lbl_kpi_rem = self._create_mini_kpi("Kalan Açık Bakiye", "0.00 ₺", "#ef4444")
        stats_box.addWidget(c4)

        h_main_lay.addLayout(stats_box)
        layout.addWidget(header_card)

        # 2. Filtre Barı
        filter_box = QHBoxLayout()
        filter_box.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Fatura No, Şube veya Ürün Ara...")
        self.search_input.textChanged.connect(self.apply_filters)
        filter_box.addWidget(self.search_input, 4)

        self.type_filter = QComboBox()
        self.type_filter.addItems(["Fatura Tipi: Tümü", "Satış Faturaları", "Alış Faturaları", "İade Faturaları"])
        self.type_filter.currentIndexChanged.connect(self.apply_filters)
        filter_box.addWidget(self.type_filter, 2)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["Durum: Tümü", "Açık Hesap (Ödenmemiş)", "Tamamen Ödenmiş", "Taslak"])
        self.status_filter.currentIndexChanged.connect(self.apply_filters)
        filter_box.addWidget(self.status_filter, 2)

        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        btn_refresh.clicked.connect(self.load_data)
        filter_box.addWidget(btn_refresh)

        layout.addLayout(filter_box)

        # 3. Faturalar Tablosu
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "Fatura No", "Tarih", "Şube", "Tip", "İçerik",
            "Toplam (₺)", "Ödenen (₺)", "Kalan (₺)", "Ödeme Şekli", "Durum", "İşlemler"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                alternate-background-color: #1e1e2d;
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                gridline-color: #242434;
                font-size: 10pt;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
                border: none;
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item:selected {{
                background-color: rgba(37, 99, 235, 0.35);
                color: #FFFFFF;
            }}
            QHeaderView {{
                background-color: #1e1e28;
                border: none;
            }}
            QHeaderView::section {{
                background-color: #1e1e28;
                color: #FFFFFF !important;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                border-right: 1px solid #282838;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 9.5pt;
                height: 38px;
                min-height: 38px;
            }}
            QHeaderView::section:hover {{
                background-color: #282838;
                color: #FFFFFF !important;
            }}
        """)
        h_h = self.table.horizontalHeader()
        h_h.setVisible(True)
        h_h.setFixedHeight(38)
        h_h.setFont(QFont("Segoe UI", 9, QFont.Bold))
        h_h.setDefaultAlignment(Qt.AlignCenter)
        h_h.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 120)
        h_h.setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 85)
        h_h.setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(2, 75)
        h_h.setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 60)
        h_h.setSectionResizeMode(4, QHeaderView.Stretch)
        h_h.setSectionResizeMode(5, QHeaderView.Interactive)
        self.table.setColumnWidth(5, 105)
        h_h.setSectionResizeMode(6, QHeaderView.Interactive)
        self.table.setColumnWidth(6, 95)
        h_h.setSectionResizeMode(7, QHeaderView.Interactive)
        self.table.setColumnWidth(7, 95)
        h_h.setSectionResizeMode(8, QHeaderView.Interactive)
        self.table.setColumnWidth(8, 95)
        h_h.setSectionResizeMode(9, QHeaderView.Interactive)
        self.table.setColumnWidth(9, 105)
        h_h.setSectionResizeMode(10, QHeaderView.Fixed)
        self.table.setColumnWidth(10, 240)
        self.table.cellDoubleClicked.connect(lambda r, c: self.on_row_double_clicked(r))
        layout.addWidget(self.table)

        # 4. Alt Bilgi ve Aksiyon Butonları
        bottom_bar = QHBoxLayout()
        self.lbl_summary = QLabel("Toplam: 0 fatura listelendi")
        self.lbl_summary.setStyleSheet(f"font-size: 10pt; font-weight: 600; color: {AppStyles.TEXT_SECONDARY};")
        bottom_bar.addWidget(self.lbl_summary)

        bottom_bar.addStretch()

        btn_new_inv = QPushButton("➕ Bu Firmaya Yeni Fatura Kes")
        btn_new_inv.setCursor(Qt.PointingHandCursor)
        btn_new_inv.setStyleSheet(f"""
            QPushButton {{
                background-color: #10b981;
                color: white;
                font-weight: bold;
                font-size: 10pt;
                padding: 8px 18px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        btn_new_inv.clicked.connect(self.create_new_invoice_for_customer)
        bottom_bar.addWidget(btn_new_inv)

        btn_close = QPushButton("Kapat")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 10pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        bottom_bar.addWidget(btn_close)

        layout.addLayout(bottom_bar)

    def _create_mini_kpi(self, title: str, val: str, color: str) -> Tuple[QFrame, QLabel]:
        fr = QFrame()
        fr.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-left: 3px solid {color};
                border-radius: 6px;
                padding: 6px 12px;
            }}
        """)
        lay = QVBoxLayout(fr)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(2)
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 8pt; color: {AppStyles.TEXT_MUTED}; font-weight: 600;")
        lay.addWidget(t_lbl)
        v_lbl = QLabel(val)
        v_lbl.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {color};")
        lay.addWidget(v_lbl)
        return fr, v_lbl

    def load_data(self):
        cust, invoices = self.customer_service.get_customer_all_invoices(self.customer_id, self.customer_title, self.branch_id)
        self.customer_data = cust
        self.invoices_data = invoices or []

        if cust:
            c_name = cust.get('title') or self.customer_title or 'Firma'
            is_supp = cust.get('is_supplier', False)
            t_type = "Tedarikçi (Hammadde / Malzeme)" if is_supp else "Müşteri (Perakende / Toptan)"
            self.lbl_title.setText(c_name)
            self.lbl_sub.setText(f"Cari Kodu: {cust.get('customer_code', '-')}   |   Tür: {t_type}   |   Tel: {cust.get('phone', '-')}   |   Vergi No: {cust.get('tax_no', '-')}")
        elif self.customer_title:
            self.lbl_title.setText(self.customer_title)
            self.lbl_sub.setText(f"Cari: {self.customer_title}   |   Farklı tarihlerdeki tüm faturalar")

        cnt = len(self.invoices_data)
        tot_grand = sum(float(inv.get('grand_total') or 0.0) for inv in self.invoices_data)
        tot_paid = sum(float(inv.get('paid_amount') or 0.0) for inv in self.invoices_data)
        tot_rem = sum(float(inv.get('remaining_amount') or 0.0) for inv in self.invoices_data)

        self.lbl_kpi_cnt.setText(f"{cnt} Adet")
        self.lbl_kpi_total.setText(f"{tot_grand:,.2f} ₺")
        self.lbl_kpi_paid.setText(f"{tot_paid:,.2f} ₺")
        if tot_rem > 0.001:
            self.lbl_kpi_rem.setText(f"{tot_rem:,.2f} ₺ (Açık)")
            self.lbl_kpi_rem.setStyleSheet("font-size: 10pt; font-weight: bold; color: #ef4444;")
        else:
            self.lbl_kpi_rem.setText("0.00 ₺ (Kapalı)")
            self.lbl_kpi_rem.setStyleSheet("font-size: 10pt; font-weight: bold; color: #10b981;")

        self.apply_filters()

    def apply_filters(self):
        s_text = self.search_input.text().strip().lower()
        t_filter = self.type_filter.currentText()
        st_filter = self.status_filter.currentText()

        filtered = []
        for inv in self.invoices_data:
            inv_type = inv.get('invoice_type', '')

            if s_text:
                no = str(inv.get('invoice_no') or '').lower()
                branch = str(inv.get('branch_name') or '').lower()
                summary = str(inv.get('items_summary') or '').lower()
                notes = str(inv.get('notes') or '').lower()
                if s_text not in no and s_text not in branch and s_text not in summary and s_text not in notes:
                    continue

            if "Satış" in t_filter and inv_type not in ['Sales', 'Satış']:
                continue
            if "Alış" in t_filter and inv_type not in ['Purchase', 'Alış']:
                continue
            if "İade" in t_filter and inv_type not in ['Return', 'İade']:
                continue

            rem = float(inv.get('remaining_amount') or 0.0)
            status = inv.get('status', '')
            p_status = inv.get('payment_status', '')
            if "Açık Hesap" in st_filter and rem <= 0.001:
                continue
            if "Tamamen Ödenmiş" in st_filter and (rem > 0.001 or p_status != 'Paid'):
                continue
            if "Taslak" in st_filter and status != 'Draft':
                continue

            filtered.append(inv)

        self.filtered_invoices = filtered
        self.table.setRowCount(len(filtered))

        filt_grand = sum(float(inv.get('grand_total') or 0.0) for inv in filtered)
        filt_rem = sum(float(inv.get('remaining_amount') or 0.0) for inv in filtered)

        for row, inv in enumerate(filtered):
            inv_type = inv.get('invoice_type', '')

            no_item = QTableWidgetItem(inv.get('invoice_no') or f"FAT-{inv['id']}")
            no_item.setTextAlignment(Qt.AlignCenter)
            no_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row, 0, no_item)

            dt = inv.get('invoice_date')
            dt_str = dt.strftime('%d.%m.%Y') if hasattr(dt, 'strftime') else str(dt or '-')
            d_item = QTableWidgetItem(dt_str)
            d_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, d_item)

            b_item = QTableWidgetItem(inv.get('branch_name') or 'Merkez')
            b_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, b_item)

            t_str = {'Sales': 'Satış', 'Purchase': 'Alış', 'Return': 'İade'}.get(inv_type, inv_type)
            type_item = QTableWidgetItem(t_str)
            type_item.setTextAlignment(Qt.AlignCenter)
            type_item.setForeground(QColor(
                AppStyles.GREEN if inv_type in ['Sales', 'Satış'] else
                AppStyles.RED if inv_type in ['Purchase', 'Alış'] else
                AppStyles.ORANGE
            ))
            type_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row, 3, type_item)

            summary_txt = inv.get('items_summary') or inv.get('notes') or '-'
            cnt = int(inv.get('item_count') or 0)
            if cnt > 0:
                cell_txt = f"{cnt} Kalem: {summary_txt}"
            else:
                cell_txt = summary_txt
            item_c = QTableWidgetItem(cell_txt)
            item_c.setToolTip(cell_txt)
            self.table.setItem(row, 4, item_c)

            tot_val = float(inv.get('grand_total') or 0.0)
            tot_item = QTableWidgetItem(f"{tot_val:,.2f} ₺")
            tot_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 5, tot_item)

            paid_val = float(inv.get('paid_amount') or 0.0)
            paid_item = QTableWidgetItem(f"{paid_val:,.2f} ₺")
            paid_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            paid_item.setForeground(QColor(AppStyles.GREEN if paid_val > 0 else AppStyles.TEXT_MUTED))
            self.table.setItem(row, 6, paid_item)

            rem_val = float(inv.get('remaining_amount') or 0.0)
            rem_item = QTableWidgetItem(f"{rem_val:,.2f} ₺")
            rem_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            rem_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            rem_item.setForeground(QColor("#ef4444" if rem_val > 0.001 else "#10b981"))
            self.table.setItem(row, 7, rem_item)

            pay_m = inv.get('payment_method') or 'Nakit'
            pm_item = QTableWidgetItem(pay_m)
            pm_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 8, pm_item)

            status = inv.get('status', '')
            p_status = inv.get('payment_status', '')
            if status == 'Approved':
                if p_status == 'Paid' or rem_val <= 0.001:
                    badge_txt = "✅ Onaylı (Ödendi)"
                    badge_color = AppStyles.GREEN
                elif p_status == 'Partial' or paid_val > 0:
                    badge_txt = "✅ Onaylı (Kısmi)"
                    badge_color = AppStyles.ORANGE
                else:
                    badge_txt = "✅ Onaylı (Açık)"
                    badge_color = AppStyles.CYAN
            else:
                badge_txt = "📝 Taslak (Onaysız)"
                badge_color = "#f59e0b"

            b_item = QTableWidgetItem(badge_txt)
            b_item.setTextAlignment(Qt.AlignCenter)
            b_item.setForeground(QColor(badge_color))
            b_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row, 9, b_item)

            act_w = QWidget()
            act_lay = QHBoxLayout(act_w)
            act_lay.setContentsMargins(3, 2, 3, 2)
            act_lay.setSpacing(4)
            act_lay.setAlignment(Qt.AlignCenter)

            btn_det = QPushButton("Kalemler")
            btn_det.setToolTip("Fatura İçeriğini ve Kalemlerini İncele")
            btn_det.setFixedSize(62, 28)
            btn_det.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    border-radius: 5px;
                    font-size: 8.5pt;
                    font-weight: 600;
                    border: none;
                }
                QPushButton:hover { background-color: #0369a1; }
            """)
            btn_det.clicked.connect(lambda ch, i_id=inv['id']: self.open_invoice_detail(i_id))
            act_lay.addWidget(btn_det)

            no_str = inv.get('invoice_no') or f"FAT-{inv['id']}"
            if status != 'Approved':
                btn_appr = QPushButton("Onayla")
                btn_appr.setToolTip("Taslak Faturayı Onayla (Stok ve Cari Bakiyeye Yansıt)")
                btn_appr.setFixedSize(58, 28)
                btn_appr.setStyleSheet("""
                    QPushButton {
                        background-color: #10b981;
                        color: white;
                        border-radius: 5px;
                        font-size: 8.5pt;
                        font-weight: bold;
                        border: none;
                    }
                    QPushButton:hover { background-color: #059669; }
                """)
                btn_appr.clicked.connect(lambda ch, i_id=inv['id'], i_no=no_str: self.approve_invoice_action(i_id, i_no))
                act_lay.addWidget(btn_appr)

            if rem_val > 0.001:
                btn_pay = QPushButton("Öde")
                btn_pay.setToolTip("Tahsilat / Ödeme Yap")
                btn_pay.setFixedSize(46, 28)
                btn_pay.setStyleSheet("""
                    QPushButton {
                        background-color: #2563eb;
                        color: white;
                        border-radius: 5px;
                        font-size: 8.5pt;
                        font-weight: 600;
                        border: none;
                    }
                    QPushButton:hover { background-color: #1d4ed8; }
                """)
                btn_pay.clicked.connect(lambda ch, i_id=inv['id']: self.pay_invoice(i_id))
                act_lay.addWidget(btn_pay)

            btn_del = QPushButton("Sil")
            btn_del.setToolTip("Bu Faturayı Tamamen Sil")
            btn_del.setFixedSize(42, 28)
            btn_del.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    color: white;
                    border-radius: 5px;
                    font-size: 8.5pt;
                    font-weight: 600;
                    border: none;
                }
                QPushButton:hover { background-color: #dc2626; }
            """)
            btn_del.clicked.connect(lambda ch, i_id=inv['id'], i_no=no_str: self.delete_invoice_action(i_id, i_no))
            act_lay.addWidget(btn_del)

            self.table.setCellWidget(row, 10, act_w)

        # Kalan tutarın satış veya alış faturası olmasına göre Alacak / Borç olarak dinamik belirlenmesi
        has_sales = any(inv.get('invoice_type') in ['Sales', 'Satış'] for inv in filtered)
        has_purchases = any(inv.get('invoice_type') in ['Purchase', 'Alış'] for inv in filtered)
        sales_rem = sum(float(inv.get('remaining_amount') or 0.0) for inv in filtered if inv.get('invoice_type') in ['Sales', 'Satış'])
        purch_rem = sum(float(inv.get('remaining_amount') or 0.0) for inv in filtered if inv.get('invoice_type') in ['Purchase', 'Alış'])

        if has_sales and has_purchases and sales_rem > 0.001 and purch_rem > 0.001:
            rem_html = f"Kalan Açık Alacak: <b style='color:#38bdf8;'>{sales_rem:,.2f} ₺</b>  |  Kalan Açık Borç: <b style='color:#ef4444;'>{purch_rem:,.2f} ₺</b>"
        elif has_sales and (not has_purchases or sales_rem > 0.001):
            rem_color = "#38bdf8" if filt_rem > 0.001 else "#10b981"
            rem_html = f"Kalan Açık Alacak: <b style='color:{rem_color};'>{filt_rem:,.2f} ₺</b>"
        elif has_purchases:
            rem_color = "#ef4444" if filt_rem > 0.001 else "#10b981"
            rem_html = f"Kalan Açık Borç: <b style='color:{rem_color};'>{filt_rem:,.2f} ₺</b>"
        else:
            is_supp = bool(self.customer_data and self.customer_data.get('is_supplier'))
            if is_supp:
                rem_color = "#ef4444" if filt_rem > 0.001 else "#10b981"
                rem_html = f"Kalan Açık Borç: <b style='color:{rem_color};'>{filt_rem:,.2f} ₺</b>"
            else:
                rem_color = "#38bdf8" if filt_rem > 0.001 else "#10b981"
                rem_html = f"Kalan Açık Alacak: <b style='color:{rem_color};'>{filt_rem:,.2f} ₺</b>"

        self.lbl_summary.setText(f"Toplam <b>{len(filtered)}</b> fatura listelendi  |  Filtrelenen Tutar: <b>{filt_grand:,.2f} ₺</b>  |  {rem_html}")

        if getattr(self, 'target_invoice_id', None):
            for r_idx, inv in enumerate(filtered):
                if inv.get('id') == self.target_invoice_id:
                    self.table.selectRow(r_idx)
                    item = self.table.item(r_idx, 0)
                    if item:
                        self.table.scrollToItem(item)
                    break

    def approve_invoice_action(self, invoice_id: int, invoice_no: str):
        reply = QMessageBox.question(
            self,
            "Fatura Onaylama Onayı",
            f"<b>{invoice_no}</b> numaralı taslak faturayı onaylamak istediğinize emin misiniz?<br><br>"
            "Bu işlem sonucunda:<br>"
            "• Faturadaki ürünlerin stok miktarları güncellenecek,<br>"
            "• Cari hesap bakiyesine yansıtılacak,<br>"
            "• Muhasebe kaydı kesinleştirilecektir.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            success, msg = self.invoice_service.approve_invoice(invoice_id)
            if success:
                QMessageBox.information(self, "Başarılı", f"✅ {msg}")
                self.load_data()
                if self.parent() and hasattr(self.parent(), 'load_companies_summary'):
                    self.parent().load_companies_summary()
                if self.parent() and hasattr(self.parent(), 'load_invoices'):
                    self.parent().load_invoices()
                if self.parent() and hasattr(self.parent(), 'load_data'):
                    self.parent().load_data()
            else:
                QMessageBox.warning(self, "Hata", f"❌ Fatura onaylanamadı:\n{msg}")

    def delete_invoice_action(self, invoice_id: int, invoice_no: str):
        reply = QMessageBox.question(
            self, "Fatura Silme Onayı",
            f"<b>{invoice_no}</b> numaralı faturayı silmek istediğinize emin misiniz?<br><br>"
            "<span style='color: #ef4444;'>⚠️ Bu işlem faturayı ve tüm kalemlerini kalıcı olarak silecek, "
            "varsa stok ve cari hesap bakiyesi etkilerini otomatik olarak düzeltecektir.</span>",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = self.invoice_service.delete_invoice(invoice_id)
            if success:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_data()
                if self.parent() and hasattr(self.parent(), 'load_companies_summary'):
                    self.parent().load_companies_summary()
                if self.parent() and hasattr(self.parent(), 'load_data'):
                    self.parent().load_data()
            else:
                QMessageBox.warning(self, "Hata", msg)

    def on_row_double_clicked(self, row: int):
        if row < 0 or row >= len(self.filtered_invoices):
            return
        inv = self.filtered_invoices[row]
        self.open_invoice_detail(inv['id'])

    def open_invoice_detail(self, invoice_id: int):
        if getattr(self, '_is_opening_detail', False):
            return
        self._is_opening_detail = True
        try:
            dlg = InvoiceDialog(self.user, self.branch_id, self, invoice_id=invoice_id)
            if dlg.exec_() == QDialog.Accepted:
                self.load_data()
                if self.parent() and hasattr(self.parent(), 'load_companies_summary'):
                    self.parent().load_companies_summary()
        finally:
            self._is_opening_detail = False

    def pay_invoice(self, invoice_id: int):
        invoice = self.invoice_service.get_invoice(invoice_id)
        if not invoice:
            return
        rem = float(invoice.remaining_amount or 0.0)
        tot = float(invoice.grand_total or 0.0)
        paid = float(invoice.paid_amount or 0.0)
        if rem <= 0.001 and tot > paid:
            rem = max(0.0, tot - paid)

        amount, ok = QInputDialog.getDouble(
            self, "Tahsilat / Ödeme Yap",
            f"Fatura No: {invoice.invoice_no}\n"
            f"Genel Toplam: {tot:,.2f} ₺\n"
            f"Ödenen Tutar: {paid:,.2f} ₺\n"
            f"Kalan Tutar: {rem:,.2f} ₺\n\n"
            f"Ödenecek / Tahsil Edilecek Tutar (₺):",
            value=rem,
            min=0.01,
            max=rem,
            decimals=2
        )
        if ok and amount > 0:
            ok_pay, msg = self.invoice_service.make_payment(invoice_id, amount)
            if ok_pay:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_data()
                if self.parent() and hasattr(self.parent(), 'load_companies_summary'):
                    self.parent().load_companies_summary()
            else:
                QMessageBox.warning(self, "Hata", msg)

    def create_new_invoice_for_customer(self):
        dlg = InvoiceDialog(self.user, self.branch_id, self, customer_id=self.customer_id)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()
            if self.parent() and hasattr(self.parent(), 'load_companies_summary'):
                self.parent().load_companies_summary()


class InvoicesPage(QWidget):
    """
    Faturalar ve Firmalar Alacak / Verecek Yönetim Sayfası
    - Faturalar listesi kaldırıldı, sadece firma alacak/verecek özeti var
    - Yeni fatura kesme ve firma detayı açma mevcut
    """

    def __init__(self, user: User, branch_id: int, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window
        self.invoice_service = InvoiceService()
        self.customer_service = CustomerService()
        self.current_page = 1
        self.selected_invoice = None
        self.current_invoices = []
        self.companies_data = []
        self.filtered_companies = []

        self.init_ui()
        self.load_companies_summary()

    def init_ui(self):
        self.setObjectName("InvoicesPage")
        self.setStyleSheet(f"#InvoicesPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 16, 18, 16)

        # 1. Üst Bar
        top_bar = self.create_top_bar()
        layout.addWidget(top_bar)

        # 2. Tüm Firmaların Alacak / Verecek KPI Özet Kartları
        kpi_cards = self.create_balance_kpi_cards()
        layout.addWidget(kpi_cards)

        # 3. Firmalar Alacak/Verecek Özeti (sekmeli yapı kaldırıldı)
        companies_tab = self.create_companies_tab()
        layout.addWidget(companies_tab, 1)

    def create_top_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(2)

        title = QLabel("📄 Faturalar & Cari Bakiye Yönetimi")
        title.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; background: transparent; border: none;")
        left.addWidget(title)

        subtitle = QLabel("Satış, alış ve iade faturalarını yönetin, tüm firmaların alacak / verecek bakiyelerini takip edin")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY}; background: transparent; border: none;")
        left.addWidget(subtitle)

        layout.addLayout(left)
        layout.addStretch()

        btn_cust_invoices = QPushButton("🏢 Müşteri Faturalarını Gör")
        btn_cust_invoices.setCursor(Qt.PointingHandCursor)
        btn_cust_invoices.setMinimumHeight(38)
        btn_cust_invoices.setStyleSheet(f"""
            QPushButton {{
                background-color: #0284c7;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 10pt;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background-color: #0369a1;
            }}
        """)
        btn_cust_invoices.clicked.connect(self.quick_select_customer_dialog)
        layout.addWidget(btn_cust_invoices)

        new_btn = QPushButton("➕  Yeni Fatura")
        new_btn.clicked.connect(self.new_invoice)
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.setMinimumHeight(38)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 10pt;
                padding: 0 18px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
            }}
        """)
        layout.addWidget(new_btn)

        return bar

    def create_balance_kpi_cards(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 10px;
            }}
        """)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(10)

        c1 = self._build_kpi_card(
            "🟢 Toplam Müşteri Alacağı", "0.00 ₺", "Bize borçlu 0 firma",
            "#10b981", "alacak_card"
        )
        self.lbl_kpi_rec = c1.findChild(QLabel, "kpi_val")
        self.lbl_kpi_rec_sub = c1.findChild(QLabel, "kpi_sub")
        lay.addWidget(c1)

        c2 = self._build_kpi_card(
            "🔴 Toplam Tedarikçi Borcu", "0.00 ₺", "Bizden alacaklı 0 firma",
            "#ef4444", "verecek_card"
        )
        self.lbl_kpi_pay = c2.findChild(QLabel, "kpi_val")
        self.lbl_kpi_pay_sub = c2.findChild(QLabel, "kpi_sub")
        lay.addWidget(c2)

        c3 = self._build_kpi_card(
            "⚖️ Net Cari Bakiye", "0.00 ₺", "Genel Net Durum",
            "#38bdf8", "net_card"
        )
        self.lbl_kpi_net = c3.findChild(QLabel, "kpi_val")
        self.lbl_kpi_net_sub = c3.findChild(QLabel, "kpi_sub")
        lay.addWidget(c3)

        c4 = self._build_kpi_card(
            "📑 Bekleyen Açık Faturalar", "0.00 ₺", "0 adet açık fatura",
            "#f59e0b", "unpaid_card"
        )
        self.lbl_kpi_unpaid = c4.findChild(QLabel, "kpi_val")
        self.lbl_kpi_unpaid_sub = c4.findChild(QLabel, "kpi_sub")
        lay.addWidget(c4)

        return frame

    def _build_kpi_card(self, title: str, val: str, sub: str, color: str, obj_name: str) -> QFrame:
        c = QFrame()
        c.setObjectName(obj_name)
        c.setStyleSheet(f"""
            QFrame#{obj_name} {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-left: 4px solid {color};
                border-radius: 8px;
            }}
        """)
        v_lay = QVBoxLayout(c)
        v_lay.setContentsMargins(10, 8, 10, 8)
        v_lay.setSpacing(3)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 9pt; font-weight: 600; color: {AppStyles.TEXT_MUTED};")
        v_lay.addWidget(t_lbl)

        v_lbl = QLabel(val)
        v_lbl.setObjectName("kpi_val")
        v_lbl.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {color};")
        v_lay.addWidget(v_lbl)

        s_lbl = QLabel(sub)
        s_lbl.setObjectName("kpi_sub")
        s_lbl.setStyleSheet(f"font-size: 8pt; color: {AppStyles.TEXT_SECONDARY};")
        v_lay.addWidget(s_lbl)

        return c

    # ==================== FİRMALAR ALACAK / VERECEK ÖZETİ ====================

    def create_companies_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(12)

        filter_frame = QFrame()
        filter_frame.setObjectName("companiesFilterFrame")
        filter_frame.setStyleSheet(f"""
            QFrame#companiesFilterFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
                padding: 8px 12px;
            }}
        """)
        f_lay = QHBoxLayout(filter_frame)
        f_lay.setContentsMargins(4, 4, 4, 4)
        f_lay.setSpacing(10)

        f_style = f"""
            QLineEdit, QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 9pt;
                min-height: 32px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {AppStyles.PRIMARY};
            }}
            QComboBox QAbstractItemView {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                selection-background-color: {AppStyles.PRIMARY};
                selection-color: white;
            }}
        """
        self.search_company_input = QLineEdit()
        self.search_company_input.setPlaceholderText("🔍 Firma adı, cari kodu, telefon veya vergi no ile ara...")
        self.search_company_input.setStyleSheet(f_style)
        self.search_company_input.textChanged.connect(self.apply_company_filters)
        f_lay.addWidget(self.search_company_input, 4)

        self.company_type_combo = QComboBox()
        self.company_type_combo.addItems(["Firma Türü: Tümü", "👤 Sadece Müşteriler", "🚚 Sadece Tedarikçiler"])
        self.company_type_combo.setStyleSheet(f_style)
        self.company_type_combo.currentIndexChanged.connect(self.apply_company_filters)
        f_lay.addWidget(self.company_type_combo, 2)

        self.balance_status_combo = QComboBox()
        self.balance_status_combo.addItems([
            "Bakiye: Tümü",
            "📑 Sadece Faturası Olan Firmalar",
            "🟢 Sadece Alacaklı Olduğumuz (Bize Borçlu)",
            "🔴 Sadece Borçlu Olduğumuz (Vereceğimiz)",
            "✓ Bakiye Sıfır / Kapalı"
        ])
        self.balance_status_combo.setStyleSheet(f_style)
        self.balance_status_combo.currentIndexChanged.connect(self.apply_company_filters)
        f_lay.addWidget(self.balance_status_combo, 3)

        btn_refresh_comp = QPushButton("🔄 Yenile")
        btn_refresh_comp.setCursor(Qt.PointingHandCursor)
        btn_refresh_comp.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        btn_refresh_comp.clicked.connect(self.load_companies_summary)
        f_lay.addWidget(btn_refresh_comp)

        layout.addWidget(filter_frame)

        table_frame = QFrame()
        table_frame.setObjectName("companiesTableFrame")
        table_frame.setStyleSheet(f"""
            QFrame#companiesTableFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        t_lay = QVBoxLayout(table_frame)
        t_lay.setContentsMargins(12, 12, 12, 12)

        self.companies_table = QTableWidget()
        self.companies_table.setColumnCount(11)
        self.companies_table.setHorizontalHeaderLabels([
            "Cari Kodu", "Firma / Cari Ünvanı", "Tür", "Telefon",
            "Fatura", "Toplam (₺)", "Ödenen (₺)",
            "Alacak (₺)", "Borç (₺)", "Net Bakiye", "Detay"
        ])
        self.companies_table.setAlternatingRowColors(True)
        self.companies_table.verticalHeader().setVisible(False)
        self.companies_table.verticalHeader().setDefaultSectionSize(48)
        self.companies_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.companies_table.setSelectionMode(QTableWidget.SingleSelection)
        self.companies_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.companies_table.cellDoubleClicked.connect(lambda r, c: self.on_company_double_clicked(r))
        self.companies_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                alternate-background-color: #1e1e2d;
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                gridline-color: #242434;
                color: {AppStyles.TEXT_PRIMARY};
                font-size: 10pt;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
                border: none;
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item:selected {{
                background-color: rgba(37, 99, 235, 0.35);
                color: #FFFFFF;
            }}
            QHeaderView {{
                background-color: #1e1e28;
                border: none;
            }}
            QHeaderView::section {{
                background-color: #1e1e28;
                color: #FFFFFF !important;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                border-right: 1px solid #282838;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 9.5pt;
                height: 38px;
                min-height: 38px;
            }}
            QHeaderView::section:hover {{
                background-color: #282838;
                color: #FFFFFF !important;
            }}
        """)

        c_head = self.companies_table.horizontalHeader()
        c_head.setVisible(True)
        c_head.setFixedHeight(38)
        c_head.setFont(QFont("Segoe UI", 9, QFont.Bold))
        c_head.setDefaultAlignment(Qt.AlignCenter)
        
        c_head.setStretchLastSection(False)
        c_head.setSectionResizeMode(0, QHeaderView.Interactive)
        self.companies_table.setColumnWidth(0, 95)
        c_head.setSectionResizeMode(1, QHeaderView.Stretch)
        c_head.setSectionResizeMode(2, QHeaderView.Interactive)
        self.companies_table.setColumnWidth(2, 80)
        c_head.setSectionResizeMode(3, QHeaderView.Interactive)
        self.companies_table.setColumnWidth(3, 110)
        c_head.setSectionResizeMode(4, QHeaderView.Interactive)
        self.companies_table.setColumnWidth(4, 75)
        c_head.setSectionResizeMode(5, QHeaderView.Interactive)
        self.companies_table.setColumnWidth(5, 115)
        c_head.setSectionResizeMode(6, QHeaderView.Interactive)
        self.companies_table.setColumnWidth(6, 110)
        c_head.setSectionResizeMode(7, QHeaderView.Interactive)
        self.companies_table.setColumnWidth(7, 115)
        c_head.setSectionResizeMode(8, QHeaderView.Interactive)
        self.companies_table.setColumnWidth(8, 115)
        c_head.setSectionResizeMode(9, QHeaderView.Interactive)
        self.companies_table.setColumnWidth(9, 120)
        c_head.setSectionResizeMode(10, QHeaderView.Fixed)
        self.companies_table.setColumnWidth(10, 75)
        t_lay.addWidget(self.companies_table)

        self.lbl_companies_summary = QLabel("Toplam 0 firma listelendi")
        self.lbl_companies_summary.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 10pt; font-weight: 600; padding: 4px;")
        t_lay.addWidget(self.lbl_companies_summary)

        layout.addWidget(table_frame)
        return widget

    def load_companies_summary(self):
        """Tüm firmaların alacak / verecek özetini ve KPI kartlarını yükler"""
        try:
            sel_branch = self.branch_id if self.branch_id else None
            summary = self.customer_service.get_companies_balance_summary(sel_branch)
            self.companies_data = summary.get('companies', [])

            rec = summary.get('total_receivables', 0.0)
            pay = summary.get('total_payables', 0.0)
            net = summary.get('net_balance', 0.0)
            c_cnt = summary.get('cust_debtor_count', 0)
            s_cnt = summary.get('supp_creditor_count', 0)
            u_amt = summary.get('unpaid_invoices_amount', 0.0)
            u_cnt = summary.get('unpaid_invoices_count', 0)
            tot_sales = summary.get('total_sales', 0.0)
            tot_purch = summary.get('total_purchases', 0.0)
            tot_inv = summary.get('total_invoiced', 0.0)

            self.lbl_kpi_rec.setText(f"{rec:,.2f} ₺")
            self.lbl_kpi_rec_sub.setText(f"Toplam Satış (Gelir): {tot_sales:,.2f} ₺ ({c_cnt} firma)")

            self.lbl_kpi_pay.setText(f"{pay:,.2f} ₺")
            self.lbl_kpi_pay_sub.setText(f"Toplam Alış (Gider): {tot_purch:,.2f} ₺ ({s_cnt} firma)")

            if net >= 0:
                self.lbl_kpi_net.setText(f"+{net:,.2f} ₺")
                self.lbl_kpi_net.setStyleSheet("font-size: 15pt; font-weight: bold; color: #10b981;")
                self.lbl_kpi_net_sub.setText("🟢 Net Alacaklı Durum")
            else:
                self.lbl_kpi_net.setText(f"{net:,.2f} ₺")
                self.lbl_kpi_net.setStyleSheet("font-size: 15pt; font-weight: bold; color: #ef4444;")
                self.lbl_kpi_net_sub.setText("🔴 Net Borçlu Durum")

            self.lbl_kpi_unpaid.setText(f"{u_amt:,.2f} ₺")
            self.lbl_kpi_unpaid_sub.setText(f"{u_cnt} açık fatura | Toplam Kesilen: {tot_inv:,.2f} ₺")

            self.apply_company_filters()
        except Exception as e:
            logger.error(f"load_companies_summary hatası: {e}")

    def apply_company_filters(self):
        """Firmalar sekmesindeki filtreleri uygular"""
        s_text = self.search_company_input.text().strip().lower()
        t_filter = self.company_type_combo.currentText()
        b_filter = self.balance_status_combo.currentText()

        filtered = []
        for c in self.companies_data:
            if s_text:
                title = str(c.get('title') or '').lower()
                code = str(c.get('customer_code') or '').lower()
                phone = str(c.get('phone') or '').lower()
                tax = str(c.get('tax_no') or '').lower()
                if s_text not in title and s_text not in code and s_text not in phone and s_text not in tax:
                    continue

            is_supp = c.get('is_supplier', False)
            if "Müşteriler" in t_filter and is_supp:
                continue
            if "Tedarikçiler" in t_filter and not is_supp:
                continue

            rec = float(c.get('receivable') or 0.0)
            pay = float(c.get('payable') or 0.0)
            net = float(c.get('net_balance') or 0.0)
            inv_cnt = int(c.get('invoice_count') or 0)

            if "Sadece Faturası Olan Firmalar" in b_filter and inv_cnt == 0:
                continue
            if "Alacaklı Olduğumuz" in b_filter and rec <= 0.001:
                continue
            if "Borçlu Olduğumuz" in b_filter and pay <= 0.001:
                continue
            if "Bakiye Sıfır" in b_filter and (abs(net) > 0.001 or rec > 0.001 or pay > 0.001):
                continue

            filtered.append(c)

        self.filtered_companies = filtered
        self.companies_table.setRowCount(len(filtered))

        tot_rec = sum(float(c.get('receivable') or 0.0) for c in filtered)
        tot_pay = sum(float(c.get('payable') or 0.0) for c in filtered)
        tot_net = tot_rec - tot_pay
        f_tot_sales = sum(float(c.get('sales_total') or 0.0) for c in filtered)
        f_tot_purch = sum(float(c.get('purchase_total') or 0.0) for c in filtered)

        for row, c in enumerate(filtered):
            code_item = QTableWidgetItem(c.get('customer_code') or '-')
            code_item.setTextAlignment(Qt.AlignCenter)
            code_item.setForeground(QColor(AppStyles.TEXT_SECONDARY))
            self.companies_table.setItem(row, 0, code_item)

            title_item = QTableWidgetItem(c.get('title') or '-')
            title_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            title_item.setForeground(QColor(AppStyles.TEXT_PRIMARY))
            self.companies_table.setItem(row, 1, title_item)

            is_supp = c.get('is_supplier', False)
            type_item = QTableWidgetItem("Tedarikçi" if is_supp else "Müşteri")
            type_item.setTextAlignment(Qt.AlignCenter)
            type_item.setForeground(QColor(AppStyles.ORANGE if is_supp else AppStyles.CYAN))
            type_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.companies_table.setItem(row, 2, type_item)

            phone_item = QTableWidgetItem(c.get('phone') or '-')
            phone_item.setTextAlignment(Qt.AlignCenter)
            phone_item.setForeground(QColor(AppStyles.TEXT_SECONDARY))
            self.companies_table.setItem(row, 3, phone_item)

            c_inv_cnt = int(c.get('invoice_count') or 0)
            cnt_item = QTableWidgetItem(f"{c_inv_cnt} Fatura")
            cnt_item.setTextAlignment(Qt.AlignCenter)
            cnt_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            cnt_item.setForeground(QColor("#38bdf8" if c_inv_cnt > 0 else AppStyles.TEXT_MUTED))
            self.companies_table.setItem(row, 4, cnt_item)

            tot_inv = float(c.get('total_invoiced') or 0.0)
            ti_item = QTableWidgetItem(f"{tot_inv:,.2f} ₺")
            ti_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            ti_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            s_val = float(c.get('sales_total') or 0.0)
            p_val = float(c.get('purchase_total') or 0.0)
            ti_item.setToolTip(f"Toplam Kesilen: {tot_inv:,.2f} ₺\nGelir (Satış): {s_val:,.2f} ₺\nGider (Alış): {p_val:,.2f} ₺")
            self.companies_table.setItem(row, 5, ti_item)

            tot_paid = float(c.get('total_paid') or 0.0)
            tp_item = QTableWidgetItem(f"{tot_paid:,.2f} ₺")
            tp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tp_item.setForeground(QColor(AppStyles.GREEN if tot_paid > 0 else AppStyles.TEXT_MUTED))
            self.companies_table.setItem(row, 6, tp_item)

            rec_val = float(c.get('receivable') or 0.0)
            rec_item = QTableWidgetItem(f"{rec_val:,.2f} ₺")
            rec_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            rec_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            rec_item.setForeground(QColor("#10b981" if rec_val > 0.001 else AppStyles.TEXT_MUTED))
            self.companies_table.setItem(row, 7, rec_item)

            pay_val = float(c.get('payable') or 0.0)
            pay_item = QTableWidgetItem(f"{pay_val:,.2f} ₺")
            pay_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            pay_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            pay_item.setForeground(QColor("#ef4444" if pay_val > 0.001 else AppStyles.TEXT_MUTED))
            self.companies_table.setItem(row, 8, pay_item)

            net_val = float(c.get('net_balance') or 0.0)
            net_item = QTableWidgetItem(f"{net_val:,.2f} ₺")
            net_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            net_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if net_val > 0.001:
                net_item.setForeground(QColor("#10b981"))
            elif net_val < -0.001:
                net_item.setForeground(QColor("#ef4444"))
            else:
                net_item.setForeground(QColor(AppStyles.TEXT_MUTED))
            self.companies_table.setItem(row, 9, net_item)

            act_w = QWidget()
            act_lay = QHBoxLayout(act_w)
            act_lay.setContentsMargins(1, 1, 1, 1)
            act_lay.setAlignment(Qt.AlignCenter)

            btn_see = QPushButton("👁️")
            btn_see.setToolTip("Bu firmanın farklı tarihlerde kesilen tüm faturalarını açılır pencerede incele")
            btn_see.setFixedSize(38, 30)
            btn_see.setCursor(Qt.PointingHandCursor)
            btn_see.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    border-radius: 6px;
                    font-size: 11pt;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover { background-color: #0369a1; }
            """)
            btn_see.clicked.connect(lambda ch, cid=c['id'], ctitle=c['title']: self.open_customer_invoices(cid, ctitle))
            act_lay.addWidget(btn_see)
            self.companies_table.setCellWidget(row, 10, act_w)

        self.lbl_companies_summary.setText(
            f"Listelenen: <b>{len(filtered)}</b> Firma  |  "
            f"Toplam Gelir (Satış): <b style='color:#10b981;'>{f_tot_sales:,.2f} ₺</b>  |  "
            f"Toplam Gider (Alış): <b style='color:#ef4444;'>{f_tot_purch:,.2f} ₺</b>  |  "
            f"Toplam Alacak: <b style='color:#38bdf8;'>{tot_rec:,.2f} ₺</b>  |  "
            f"Toplam Verecek: <b style='color:#f59e0b;'>{tot_pay:,.2f} ₺</b>  |  "
            f"Net: <b style='color:{'#10b981' if tot_net >= 0 else '#ef4444'};'>{tot_net:,.2f} ₺</b>"
        )

    def on_company_double_clicked(self, row: int):
        if row < 0 or row >= len(self.filtered_companies):
            return
        c = self.filtered_companies[row]
        self.open_customer_invoices(c['id'], c['title'])

    def open_customer_invoices(self, customer_id: int, customer_title: Optional[str] = None, target_invoice_id: Optional[int] = None):
        if not customer_id and not customer_title:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir müşteri kaydı bulunamadı!")
            return
        dlg = CustomerInvoicesDialog(
            user=self.user,
            branch_id=self.branch_id,
            customer_id=customer_id or 0,
            customer_title=customer_title,
            parent=self,
            target_invoice_id=target_invoice_id
        )
        dlg.exec_()
        self.load_companies_summary()

    def quick_select_customer_dialog(self):
        try:
            customers, _ = self.customer_service.get_customers(self.branch_id, 1, 9999)
            if not customers:
                QMessageBox.information(self, "Bilgi", "Kayıtlı cari hesap bulunamadı!")
                return
            items = [f"{c.title} ({c.customer_code or 'Cari'})" for c in customers]
            item, ok = QInputDialog.getItem(
                self, "Müşteri / Firma Seç",
                "Farklı tarihlerdeki tüm faturalarını görüntülemek istediğiniz firmayı seçin:",
                items, 0, False
            )
            if ok and item:
                idx = items.index(item)
                sel_cust = customers[idx]
                self.open_customer_invoices(sel_cust.id, sel_cust.title)
        except Exception as e:
            logger.error(f"quick_select_customer_dialog hatası: {e}")

    def new_invoice(self):
        dialog = InvoiceDialog(self.user, self.branch_id, self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_companies_summary()

    def load_data(self):
        self.load_companies_summary()

    def load_invoices(self):
        self.load_companies_summary()


class InvoiceDialog(QDialog):
    """Fatura ekleme/düzenleme dialog'u"""

    def __init__(self, user, branch_id, parent=None, invoice_id=None, customer_id=None):
        super().__init__(parent)
        self.user = user
        self.branch_id = branch_id
        self.invoice_id = invoice_id
        self.preselected_customer_id = customer_id
        self.customer_service = CustomerService()
        self.invoice_service = InvoiceService()
        self.items = []
        self.products_cache = []

        self.setWindowTitle("Yeni Fatura" if not invoice_id else "Fatura Düzenle")
        self.setMinimumSize(950, 720)
        self.setStyleSheet(AppStyles.get_main_style())
        
        self.init_ui()
        
        if invoice_id:
            self.load_invoice()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 20, 25, 20)
        
        self.title_label = QLabel("📄 " + ("Yeni Fatura / Sipariş" if not self.invoice_id else "Fatura Detayı"))
        self.title_label.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        layout.addWidget(self.title_label)
        
        info_frame = QFrame()
        info_frame.setObjectName("invoiceInfoFrame")
        info_frame.setStyleSheet(f"""
            QFrame#invoiceInfoFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                padding: 15px;
                border: 1px solid {AppStyles.BORDER};
            }}
            QFrame#invoiceInfoFrame QLabel {{
                background: transparent;
                border: none;
                padding: 0px;
                font-size: 10pt;
                font-weight: bold;
                color: {AppStyles.TEXT_PRIMARY};
            }}
        """)
        
        info_layout = QGridLayout()
        info_layout.setSpacing(12)
        
        spin_style = f"""
            QDoubleSpinBox, QLineEdit, QComboBox, QDateEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10pt;
                font-weight: 500;
            }}
            QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
                border: 2px solid {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_ELEVATED};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QComboBox QAbstractItemView {{
                background-color: {AppStyles.BG_ELEVATED};
                color: {AppStyles.TEXT_PRIMARY};
                selection-background-color: {AppStyles.PRIMARY};
                selection-color: white;
                border: 1px solid {AppStyles.BORDER};
            }}
        """

        info_layout.addWidget(QLabel("📄 Fatura No:"), 0, 0)
        self.invoice_no_input = QLineEdit()
        self.invoice_no_input.setPlaceholderText("Otomatik Üretilir" if not self.invoice_id else "")
        self.invoice_no_input.setReadOnly(bool(self.invoice_id))
        self.invoice_no_input.setMinimumHeight(38)
        self.invoice_no_input.setStyleSheet(spin_style)
        info_layout.addWidget(self.invoice_no_input, 0, 1)

        info_layout.addWidget(QLabel("📅 Tarih:"), 0, 2)
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd.MM.yyyy")
        self.date_input.setMinimumHeight(38)
        self.date_input.setStyleSheet(spin_style)
        info_layout.addWidget(self.date_input, 0, 3)
        
        info_layout.addWidget(QLabel("📌 Tip:"), 0, 4)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Satış", "Alış", "İade"])
        self.type_combo.setMinimumHeight(38)
        self.type_combo.setStyleSheet(spin_style)
        info_layout.addWidget(self.type_combo, 0, 5)
        
        info_layout.addWidget(QLabel("👤 Müşteri / Firma:"), 1, 0)
        self.customer_combo = QComboBox()
        self.customer_combo.setEditable(True)
        self.customer_combo.setInsertPolicy(QComboBox.NoInsert)
        self.customer_combo.setMinimumHeight(38)
        self.customer_combo.setStyleSheet(spin_style)
        self.load_customers()
        self.customer_combo.currentIndexChanged.connect(self.on_customer_changed)
        info_layout.addWidget(self.customer_combo, 1, 1)
        
        info_layout.addWidget(QLabel("💳 Ödeme Yöntemi:"), 1, 2)
        self.payment_method_combo = QComboBox()
        self.payment_method_combo.addItems(["Nakit", "Kredi Kartı / POS", "Havale / EFT"])
        self.payment_method_combo.setMinimumHeight(38)
        self.payment_method_combo.setStyleSheet(spin_style)
        info_layout.addWidget(self.payment_method_combo, 1, 3)
        
        info_layout.addWidget(QLabel("💰 Ödeme Durumu:"), 1, 4)
        self.payment_status_combo = QComboBox()
        self.payment_status_combo.addItems(["Ödenmedi (Açık Hesap / Vadeli)", "Ödendi (Peşin / Tahsil Edildi)"])
        self.payment_status_combo.setMinimumHeight(38)
        self.payment_status_combo.setStyleSheet(spin_style)
        info_layout.addWidget(self.payment_status_combo, 1, 5)
        
        info_layout.addWidget(QLabel("📝 Notlar:"), 2, 0)
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(50)
        self.notes_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px;
                font-size: 10pt;
            }}
            QTextEdit:focus {{
                border: 2px solid {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_ELEVATED};
            }}
        """)
        info_layout.addWidget(self.notes_input, 2, 1, 1, 5)
        
        info_frame.setLayout(info_layout)
        layout.addWidget(info_frame)

        self.customer_details_card = QFrame()
        self.customer_details_card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-left: 4px solid {AppStyles.PRIMARY};
                border-radius: 6px;
                padding: 6px 12px;
            }}
        """)
        c_det_lay = QHBoxLayout(self.customer_details_card)
        c_det_lay.setContentsMargins(4, 4, 4, 4)
        self.customer_details_lbl = QLabel("ℹ️ Müşteri bilgileri...")
        self.customer_details_lbl.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 10pt;")
        c_det_lay.addWidget(self.customer_details_lbl)
        layout.addWidget(self.customer_details_card)
        
        items_header_layout = QHBoxLayout()
        items_title = QLabel("📋 Fatura / Sipariş Kalemleri")
        items_title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; margin-top: 5px;")
        items_header_layout.addWidget(items_title)
        items_header_layout.addStretch()
        
        self.stock_info_label = QLabel("")
        items_header_layout.addWidget(self.stock_info_label)
        layout.addLayout(items_header_layout)
        
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(6)
        self.items_table.setHorizontalHeaderLabels(['Ürün / Hizmet', 'Miktar', 'Birim Fiyat (₺)', 'İskonto %', 'KDV %', 'Toplam (₺)'])
        self.items_table.setAlternatingRowColors(True)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.verticalHeader().setDefaultSectionSize(42)
        self.items_table.horizontalHeader().setVisible(True)
        self.items_table.horizontalHeader().setFixedHeight(38)
        self.items_table.horizontalHeader().setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.items_table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.items_table.setSelectionMode(QTableWidget.SingleSelection)
        self.items_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                alternate-background-color: #1e1e2d;
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                gridline-color: #242434;
                font-size: 10pt;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
                border: none;
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item:selected {{
                background-color: rgba(37, 99, 235, 0.35);
                color: #FFFFFF;
            }}
            QHeaderView {{
                background-color: {AppStyles.BG_DARKEST};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARKEST};
                color: #FFFFFF;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                border-right: 1px solid #1e1e2d;
                height: 38px;
                padding: 8px 10px;
                text-transform: none;
            }}
        """)
        it_h = self.items_table.horizontalHeader()
        it_h.setSectionResizeMode(0, QHeaderView.Stretch)
        it_h.setSectionResizeMode(1, QHeaderView.Interactive)
        self.items_table.setColumnWidth(1, 85)
        it_h.setSectionResizeMode(2, QHeaderView.Interactive)
        self.items_table.setColumnWidth(2, 120)
        it_h.setSectionResizeMode(3, QHeaderView.Interactive)
        self.items_table.setColumnWidth(3, 90)
        it_h.setSectionResizeMode(4, QHeaderView.Interactive)
        self.items_table.setColumnWidth(4, 85)
        it_h.setSectionResizeMode(5, QHeaderView.Interactive)
        self.items_table.setColumnWidth(5, 130)
        self.items_table.setMinimumHeight(190)
        layout.addWidget(self.items_table)
        
        add_layout = QHBoxLayout()
        add_layout.setSpacing(8)
        
        self.product_input = QLineEdit()
        self.product_input.setPlaceholderText("Ürün / Hizmet Adı")
        self.product_input.setMinimumHeight(40)
        self.product_input.setStyleSheet(spin_style)
        add_layout.addWidget(self.product_input, 3)
        
        self.qty_input = QDoubleSpinBox()
        self.qty_input.setRange(0.001, 999999999.99999)
        self.qty_input.setValue(1)
        self.qty_input.setPrefix("x ")
        self.qty_input.setDecimals(2)
        self.qty_input.setMinimumHeight(40)
        self.qty_input.setMinimumWidth(110)
        self.qty_input.setStyleSheet(spin_style)
        add_layout.addWidget(self.qty_input, 1)
        
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 999999999999.99999)
        self.price_input.setPrefix("₺ ")
        self.price_input.setDecimals(2)
        self.price_input.setMinimumHeight(40)
        self.price_input.setMinimumWidth(150)
        self.price_input.setStyleSheet(spin_style)
        add_layout.addWidget(self.price_input, 1)
        
        self.discount_input = QDoubleSpinBox()
        self.discount_input.setRange(0, 100)
        self.discount_input.setValue(0)
        self.discount_input.setSuffix(" %")
        self.discount_input.setDecimals(1)
        self.discount_input.setMinimumHeight(40)
        self.discount_input.setMinimumWidth(90)
        self.discount_input.setStyleSheet(spin_style)
        add_layout.addWidget(self.discount_input, 1)
        
        self.vat_input = QDoubleSpinBox()
        self.vat_input.setRange(0, 100)
        self.vat_input.setValue(18)
        self.vat_input.setSuffix(" %")
        self.vat_input.setDecimals(0)
        self.vat_input.setMinimumHeight(40)
        self.vat_input.setMinimumWidth(90)
        self.vat_input.setStyleSheet(spin_style)
        add_layout.addWidget(self.vat_input, 1)
        
        self.add_item_btn = QPushButton("➕ Ekle")
        self.add_item_btn.setMinimumHeight(40)
        self.add_item_btn.clicked.connect(self.add_item)
        self.add_item_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.GREEN};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{ background-color: #059669; }}
        """)
        add_layout.addWidget(self.add_item_btn)
        
        self.del_item_btn = QPushButton("🗑️ Kalemi Çıkar")
        self.del_item_btn.setToolTip("Seçili fatura kalemini tablodan çıkarır")
        self.del_item_btn.setMinimumHeight(40)
        self.del_item_btn.clicked.connect(self.remove_item)
        self.del_item_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.RED};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 14px;
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{ background-color: #dc2626; }}
        """)
        add_layout.addWidget(self.del_item_btn)
        
        layout.addLayout(add_layout)
        
        total_frame = QFrame()
        total_frame.setObjectName("invoiceTotalFrame")
        total_frame.setStyleSheet(f"""
            QFrame#invoiceTotalFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 8px;
                border: 1px solid {AppStyles.BORDER};
                padding: 10px 18px;
            }}
        """)
        
        total_layout = QHBoxLayout()
        total_layout.setContentsMargins(0, 0, 0, 0)
        total_layout.addStretch()
        
        self.total_label = QLabel("Genel Toplam: 0,00 ₺")
        self.total_label.setStyleSheet(f"""
            font-size: 13pt;
            font-weight: bold;
            color: {AppStyles.PRIMARY};
            background: transparent;
            border: none;
        """)
        total_layout.addWidget(self.total_label)
        
        total_frame.setLayout(total_layout)
        layout.addWidget(total_frame)
        
        bottom_action_layout = QHBoxLayout()
        if self.invoice_id:
            self.delete_invoice_btn = QPushButton("🗑️ Bu Faturayı Sil")
            self.delete_invoice_btn.setCursor(Qt.PointingHandCursor)
            self.delete_invoice_btn.setMinimumHeight(38)
            self.delete_invoice_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.RED};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 0 18px;
                    font-weight: bold;
                    font-size: 10pt;
                }}
                QPushButton:hover {{ background-color: #dc2626; }}
            """)
            self.delete_invoice_btn.clicked.connect(self.delete_current_invoice)
            bottom_action_layout.addWidget(self.delete_invoice_btn)

        bottom_action_layout.addStretch()

        if self.invoice_id:
            self.approve_invoice_btn = QPushButton("✅ Faturayı Onayla")
            self.approve_invoice_btn.setCursor(Qt.PointingHandCursor)
            self.approve_invoice_btn.setMinimumHeight(38)
            self.approve_invoice_btn.setStyleSheet("""
                QPushButton {
                    background-color: #10b981;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 0 20px;
                    font-weight: bold;
                    font-size: 10pt;
                }
                QPushButton:hover { background-color: #059669; }
            """)
            self.approve_invoice_btn.clicked.connect(self.approve_current_invoice)
            bottom_action_layout.addWidget(self.approve_invoice_btn)

        self.btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.btn_box.button(QDialogButtonBox.Save).setText("💾 Kaydet")
        self.btn_box.button(QDialogButtonBox.Cancel).setText("❌ İptal")
        self.btn_box.accepted.connect(self.save_invoice)
        self.btn_box.rejected.connect(self.reject)
        bottom_action_layout.addWidget(self.btn_box)

        layout.addLayout(bottom_action_layout)
        
        self.setLayout(layout)
        self.load_products()
    
    def load_customers(self):
        try:
            sql = "SELECT id, customer_code, title, tax_no, phone, address FROM Customers WHERE is_active = TRUE"
            params = []
            if self.branch_id:
                sql += " AND branch_id = %s"
                params.append(self.branch_id)
            sql += " ORDER BY title ASC"
            customers = db.fetch_all(sql, tuple(params))
            self.customer_combo.clear()
            self.customer_combo.addItem("Müşteri / Firma Seçiniz veya Yazınız...", None)
            for c in customers:
                self.customer_combo.addItem(f"{c.get('customer_code') or ''} - {c['title']}", c['id'])
            if self.preselected_customer_id:
                for idx in range(self.customer_combo.count()):
                    if self.customer_combo.itemData(idx) == self.preselected_customer_id:
                        self.customer_combo.setCurrentIndex(idx)
                        break
        except Exception as e:
            logger.error(f"Müşteri yükleme hatası: {e}")

    def on_customer_changed(self):
        if not hasattr(self, 'customer_details_lbl'):
            return
        cid = self.customer_combo.currentData()
        if cid:
            try:
                cust = db.fetch_one("SELECT title, tax_no, tax_office, phone, address, balance FROM Customers WHERE id = %s", (cid,))
                if cust:
                    tax_info = f"Vergi No: {cust.get('tax_no') or '-'}"
                    if cust.get('tax_office'):
                        tax_info += f" ({cust.get('tax_office')})"
                    ph = cust.get('phone') or '-'
                    addr = cust.get('address') or '-'
                    bal = float(cust.get('balance') or 0)
                    self.customer_details_lbl.setText(
                        f"👤 <b>{cust.get('title')}</b>  |  🏢 {tax_info}  |  📞 Tel: <b>{ph}</b>  |  📍 Adres: <b>{addr}</b>  |  💰 Bakiye: <b>{bal:,.2f} ₺</b>"
                    )
                    return
            except Exception as e:
                logger.error(f"Müşteri detay getirme hatası: {e}")
        c_text = self.customer_combo.currentText().strip()
        self.customer_details_lbl.setText("ℹ️ Müşteri / Firma Adı: " + (c_text if c_text else "-"))
    
    def load_products(self):
        try:
            self.products_cache = db.fetch_all("""
                SELECT id, name, product_code, sale_price, purchase_price, stock_quantity, critical_stock, unit, vat_rate
                FROM Products
                WHERE branch_id = %s AND is_active = TRUE
                ORDER BY name ASC
            """, (self.branch_id,))
            names = [p['name'] for p in self.products_cache if p.get('name')]
            completer = QCompleter(names, self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            self.product_input.setCompleter(completer)
            
            self.product_input.textChanged.connect(self.on_product_text_changed)
        except Exception as e:
            logger.error(f"Ürün yükleme hatası: {e}")
    
    def on_product_text_changed(self, text):
        name = text.strip()
        matched = None
        for p in getattr(self, 'products_cache', []):
            if p.get('name', '').strip().lower() == name.lower():
                matched = p
                break
        
        if matched:
            inv_type = self.type_combo.currentText()
            price = float(matched.get('sale_price' if inv_type == 'Satış' else 'purchase_price') or 0)
            if self.price_input.value() == 0 and price > 0:
                self.price_input.setValue(price)
            if matched.get('vat_rate') is not None:
                self.vat_input.setValue(float(matched['vat_rate']))
            
            stock = float(matched.get('stock_quantity') or 0)
            crit = float(matched.get('critical_stock') or 5)
            unit = matched.get('unit') or 'Adet'
            
            if stock <= 0:
                self.stock_info_label.setText(f"🚨 Mevcut Stok: 0 {unit} (TÜKENDİ)")
                self.stock_info_label.setStyleSheet(f"color: {AppStyles.RED}; font-weight: bold; font-size: 10pt;")
            elif stock <= crit:
                self.stock_info_label.setText(f"⚠️ Mevcut Stok: {stock:g} {unit} (Kritik)")
                self.stock_info_label.setStyleSheet(f"color: {AppStyles.WARNING}; font-weight: bold; font-size: 10pt;")
            else:
                self.stock_info_label.setText(f"✅ Mevcut Stok: {stock:g} {unit}")
                self.stock_info_label.setStyleSheet(f"color: {AppStyles.GREEN}; font-weight: 600; font-size: 10pt;")
        else:
            self.stock_info_label.setText("")
    
    def load_invoice(self):
        try:
            invoice = self.invoice_service.get_invoice(self.invoice_id)
            if not invoice:
                return
            
            if hasattr(self, 'invoice_no_input') and getattr(invoice, 'invoice_no', None):
                self.invoice_no_input.setText(str(invoice.invoice_no))

            if getattr(invoice, 'invoice_date', None):
                d_str = str(invoice.invoice_date)[:10]
                q_d = QDate.fromString(d_str, "yyyy-MM-dd")
                if q_d.isValid():
                    self.date_input.setDate(q_d)
            
            type_map = {'Sales': 'Satış', 'Purchase': 'Alış', 'Return': 'İade'}
            self.type_combo.setCurrentText(type_map.get(getattr(invoice, 'invoice_type', 'Sales'), 'Satış'))
            
            cust_row = None
            if getattr(invoice, 'customer_id', None):
                try:
                    cust_row = db.fetch_one(
                        "SELECT id, customer_code, title, tax_no, tax_office, phone, address, balance FROM Customers WHERE id = %s",
                        (invoice.customer_id,)
                    )
                except Exception as ex:
                    logger.error(f"Cari bilgisi sorgulama hatası: {ex}")
            
            if cust_row:
                idx = self.customer_combo.findData(cust_row['id'])
                if idx >= 0:
                    self.customer_combo.setCurrentIndex(idx)
                else:
                    self.customer_combo.addItem(f"{cust_row.get('customer_code') or ''} - {cust_row['title']}", cust_row['id'])
                    self.customer_combo.setCurrentIndex(self.customer_combo.count() - 1)
                
                tax_info = f"Vergi No: {cust_row.get('tax_no') or '-'}"
                if cust_row.get('tax_office'):
                    tax_info += f" ({cust_row.get('tax_office')})"
                ph = cust_row.get('phone') or '-'
                addr = cust_row.get('address') or '-'
                bal = float(cust_row.get('balance') or 0)
                self.customer_details_lbl.setText(
                    f"👤 <b>{cust_row.get('title')}</b>  |  🏢 {tax_info}  |  📞 Tel: <b>{ph}</b>  |  📍 Adres: <b>{addr}</b>  |  💰 Bakiye: <b>{bal:,.2f} ₺</b>"
                )
            else:
                self.on_customer_changed()
            
            if hasattr(invoice, 'payment_method') and invoice.payment_method:
                self.payment_method_combo.setCurrentText(str(invoice.payment_method))
            
            if hasattr(invoice, 'payment_status') and invoice.payment_status == 'Paid':
                self.payment_status_combo.setCurrentIndex(1)
            else:
                self.payment_status_combo.setCurrentIndex(0)
            
            self.notes_input.setText(str(invoice.notes or ''))
            
            self.items = []
            for item in (invoice.items or []):
                u_price = float(getattr(item, 'unit_price', 0) or 0)
                qty = float(getattr(item, 'quantity', 1) or 1)
                subtotal = u_price * qty
                
                d_rate = float(getattr(item, 'discount_rate', 0) or 0)
                d_amt_val = getattr(item, 'discount_amount', None)
                if d_amt_val is not None and float(d_amt_val or 0) > 0:
                    disc_amt = float(d_amt_val)
                else:
                    disc_amt = subtotal * (d_rate / 100.0)
                
                v_rate = float(getattr(item, 'vat_rate', 18) or 0)
                v_amt_val = getattr(item, 'vat_amount', None)
                if v_amt_val is not None:
                    vat_amt = float(v_amt_val)
                else:
                    vat_amt = (subtotal - disc_amt) * (v_rate / 100.0)
                
                l_tot_val = getattr(item, 'line_total', None)
                if l_tot_val is not None:
                    line_tot = float(l_tot_val)
                else:
                    line_tot = subtotal - disc_amt + vat_amt
                
                self.items.append({
                    'product_id': getattr(item, 'product_id', None),
                    'product_name': str(getattr(item, 'product_name', '') or 'Ürün'),
                    'quantity': qty,
                    'unit_price': u_price,
                    'discount_rate': d_rate,
                    'discount_amount': disc_amt,
                    'vat_rate': v_rate,
                    'vat_amount': vat_amt,
                    'line_total': line_tot
                })
            
            self.refresh_items_table()
            self.update_total()

            inv_no = getattr(invoice, 'invoice_no', None) or f"FAT-{invoice.id}"
            is_approved = (getattr(invoice, 'status', '') == 'Approved')
            
            if is_approved:
                self.setWindowTitle(f"📄 Fatura Detayı [ ✅ ONAYLANDI ] - {inv_no}")
                if hasattr(self, 'title_label'):
                    self.title_label.setText(f"📄 Fatura Detayı [ ✅ ONAYLANDI: {inv_no} ]")
                if hasattr(self, 'approve_invoice_btn'):
                    self.approve_invoice_btn.setVisible(False)
                if hasattr(self, 'btn_box'):
                    save_btn = self.btn_box.button(QDialogButtonBox.Save)
                    if save_btn:
                        save_btn.setVisible(False)
                    cancel_btn = self.btn_box.button(QDialogButtonBox.Cancel)
                    if cancel_btn:
                        cancel_btn.setText("Kapat")
                if hasattr(self, 'add_item_btn'):
                    self.add_item_btn.setEnabled(False)
                if hasattr(self, 'del_item_btn'):
                    self.del_item_btn.setEnabled(False)
                if hasattr(self, 'product_input'):
                    self.product_input.setEnabled(False)
                if hasattr(self, 'qty_input'):
                    self.qty_input.setEnabled(False)
                if hasattr(self, 'price_input'):
                    self.price_input.setEnabled(False)
                if hasattr(self, 'discount_input'):
                    self.discount_input.setEnabled(False)
                if hasattr(self, 'vat_input'):
                    self.vat_input.setEnabled(False)
                if hasattr(self, 'type_combo'):
                    self.type_combo.setEnabled(False)
                if hasattr(self, 'customer_combo'):
                    self.customer_combo.setEnabled(False)
                if hasattr(self, 'payment_method_combo'):
                    self.payment_method_combo.setEnabled(False)
                if hasattr(self, 'payment_status_combo'):
                    self.payment_status_combo.setEnabled(False)
                if hasattr(self, 'date_input'):
                    self.date_input.setEnabled(False)
                if hasattr(self, 'notes_input'):
                    self.notes_input.setReadOnly(True)
                if hasattr(self, 'stock_info_label'):
                    self.stock_info_label.setText("✅ Bu fatura ONAYLANMIŞTIR. Kalemler ve tutarlar stoklara ve cari hesaba yansıtılmıştır.")
                    self.stock_info_label.setStyleSheet(f"color: {AppStyles.GREEN}; font-size: 10pt; font-weight: 600;")
            else:
                self.setWindowTitle(f"📄 Fatura Detayı [ 📝 TASLAK ] - {inv_no}")
                if hasattr(self, 'title_label'):
                    self.title_label.setText(f"📄 Fatura Detayı [ 📝 TASLAK - ONAY BEKLİYOR: {inv_no} ]")
                if hasattr(self, 'approve_invoice_btn'):
                    self.approve_invoice_btn.setVisible(True)
                if hasattr(self, 'stock_info_label'):
                    self.stock_info_label.setText("⚠️ Bu fatura henüz TASLAK durumundadır. Stoklara ve cari bakiyeye yansıması için 'Faturayı Onayla' butonuna tıklayınız.")
                    self.stock_info_label.setStyleSheet("color: #f59e0b; font-size: 10pt; font-weight: 600;")
        except Exception as e:
            logger.error(f"Fatura yükleme hatası: {e}")
    
    def add_item(self):
        name = self.product_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Uyarı", "Ürün adı giriniz!")
            return
        
        qty = self.qty_input.value()
        price = self.price_input.value()
        discount = self.discount_input.value()
        vat = self.vat_input.value()
        inv_type = self.type_combo.currentText()
        
        matched_product = None
        for p in getattr(self, 'products_cache', []):
            if p.get('name', '').strip().lower() == name.lower():
                matched_product = p
                break
        
        if inv_type == 'Satış' and matched_product:
            curr_stock = float(matched_product.get('stock_quantity') or 0)
            unit = matched_product.get('unit') or 'Adet'
            if curr_stock <= 0:
                QMessageBox.warning(
                    self, 
                    "⚠️ Stok Yok Uyarısı",
                    f"<b>'{name}'</b> ürününden stokta hiç kalmamıştır! (Mevcut Stok: <b>0 {unit}</b>)<br><br>"
                    f"Sipariş / Fatura kaydına <b>yine de devam edilecek</b> ve bildirim paneline uyarı gönderilecektir."
                )
            elif qty > curr_stock:
                QMessageBox.warning(
                    self,
                    "⚠️ Yetersiz Stok Uyarısı",
                    f"<b>'{name}'</b> ürünü için talep edilen miktar (<b>{qty:g} {unit}</b>), "
                    f"mevcut stoktan (<b>{curr_stock:g} {unit}</b>) fazladır!<br><br>"
                    f"Sipariş / Fatura kaydına <b>yine de devam edilecek</b> ve bildirim paneline uyarı gönderilecektir."
                )
        
        subtotal = qty * price
        discount_amount = subtotal * (discount / 100)
        subtotal_after_discount = subtotal - discount_amount
        vat_amount = subtotal_after_discount * (vat / 100)
        total = subtotal_after_discount + vat_amount
        
        self.items.append({
            'product_id': matched_product['id'] if matched_product else None,
            'product_name': name,
            'quantity': qty,
            'unit_price': price,
            'discount_rate': discount,
            'discount_amount': discount_amount,
            'vat_rate': vat,
            'vat_amount': vat_amount,
            'line_total': total
        })
        
        self.refresh_items_table()
        self.update_total()
        
        self.product_input.clear()
        self.qty_input.setValue(1)
        self.price_input.setValue(0)
        self.discount_input.setValue(0)
        self.stock_info_label.setText("")
    
    def remove_item(self):
        row = self.items_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen tablodan silinecek kalemi seçin!")
            return
        del self.items[row]
        self.refresh_items_table()
        self.update_total()

    def approve_current_invoice(self):
        if not self.invoice_id:
            return
        reply = QMessageBox.question(
            self,
            "Fatura Onaylama Onayı",
            "Bu taslak faturayı onaylamak istediğinize emin misiniz?<br><br>"
            "Bu işlem sonucunda:<br>"
            "• Faturadaki ürünlerin stok miktarları güncellenecek,<br>"
            "• Cari hesap bakiyesine yansıtılacak,<br>"
            "• Muhasebe kaydı kesinleştirilecektir.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            success, msg = self.invoice_service.approve_invoice(self.invoice_id)
            if success:
                QMessageBox.information(self, "Başarılı", f"✅ {msg}")
                self.load_invoice()
                self.accept()
            else:
                QMessageBox.warning(self, "Hata", f"❌ Fatura onaylanamadı:\n{msg}")

    def delete_current_invoice(self):
        if not self.invoice_id:
            return
        reply = QMessageBox.question(
            self, "Fatura Silme Onayı",
            "Bu faturayı sistemden kalıcı olarak silmek istediğinize emin misiniz?\n\n"
            "Silme işlemi sonrasında stok miktarları ve cari hesap bakiyesi otomatik olarak düzeltilecektir.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = self.invoice_service.delete_invoice(self.invoice_id)
            if success:
                QMessageBox.information(self, "Başarılı", msg)
                self.accept()
            else:
                QMessageBox.warning(self, "Hata", msg)
    
    def refresh_items_table(self):
        self.items_table.setRowCount(len(self.items))
        for i, item in enumerate(self.items):
            p_item = QTableWidgetItem(str(item.get('product_name') or ''))
            p_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.items_table.setItem(i, 0, p_item)

            q_val = float(item.get('quantity') or 1)
            q_item = QTableWidgetItem(f"{q_val:g}")
            q_item.setTextAlignment(Qt.AlignCenter)
            self.items_table.setItem(i, 1, q_item)

            pr_val = float(item.get('unit_price') or 0)
            pr_item = QTableWidgetItem(f"{pr_val:,.2f} ₺")
            pr_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(i, 2, pr_item)

            disc_val = float(item.get('discount_rate') or 0)
            disc_item = QTableWidgetItem(f"%{disc_val:g}")
            disc_item.setTextAlignment(Qt.AlignCenter)
            self.items_table.setItem(i, 3, disc_item)

            vat_val = float(item.get('vat_rate') or 0)
            vat_item = QTableWidgetItem(f"%{vat_val:g}")
            vat_item.setTextAlignment(Qt.AlignCenter)
            self.items_table.setItem(i, 4, vat_item)

            tot_val = float(item.get('line_total') or 0)
            tot_item = QTableWidgetItem(f"{tot_val:,.2f} ₺")
            tot_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(i, 5, tot_item)
    
    def update_total(self):
        subtotal = sum((float(item.get('unit_price') or 0) * float(item.get('quantity') or 0)) - float(item.get('discount_amount') or 0) for item in self.items)
        discount_total = sum(float(item.get('discount_amount') or 0) for item in self.items)
        vat_total = sum(float(item.get('vat_amount') or 0) for item in self.items)
        grand_total = sum(float(item.get('line_total') or 0) for item in self.items)
        
        status_text = self.payment_status_combo.currentText()
        pay_info = "  |  💰 Ödeme Durumu: ÖDENDİ" if "Ödendi" in status_text else "  |  💰 Ödeme Durumu: BEKLİYOR (Açık Hesap)"

        if discount_total > 0:
            self.total_label.setText(
                f"Ara Toplam: <b>{subtotal:,.2f} ₺</b>  |  İskonto: <b>-{discount_total:,.2f} ₺</b>  |  KDV: <b>{vat_total:,.2f} ₺</b>  |  Genel Toplam: <b style='color:#38bdf8;'>{grand_total:,.2f} ₺</b>{pay_info}"
            )
        else:
            self.total_label.setText(
                f"Ara Toplam: <b>{subtotal:,.2f} ₺</b>  |  KDV: <b>{vat_total:,.2f} ₺</b>  |  Genel Toplam: <b style='color:#38bdf8;'>{grand_total:,.2f} ₺</b>{pay_info}"
            )
    
    def save_invoice(self):
        cust_id = self.customer_combo.currentData()
        cust_title = self.customer_combo.currentText().strip()
        if "Seçiniz" in cust_title:
            cust_title = ""
        
        if not cust_id and not cust_title:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir müşteri seçiniz veya firma adı giriniz!")
            return
        
        if not self.items:
            QMessageBox.warning(self, "Uyarı", "En az bir kalem ekleyiniz!")
            return
        
        type_map = {'Satış': 'Sales', 'Alış': 'Purchase', 'İade': 'Return'}
        status_text = self.payment_status_combo.currentText()
        payment_status = 'Paid' if 'Ödendi' in status_text else 'Unpaid'
        
        data = {
            'branch_id': self.branch_id,
            'invoice_date': self.date_input.date().toString("yyyy-MM-dd"),
            'invoice_type': type_map.get(self.type_combo.currentText(), 'Sales'),
            'customer_id': cust_id,
            'customer_title': cust_title,
            'payment_method': self.payment_method_combo.currentText(),
            'payment_status': payment_status,
            'notes': self.notes_input.toPlainText().strip(),
            'auto_journal': True
        }
        
        try:
            if self.invoice_id:
                success, message = self.invoice_service.update_invoice(self.invoice_id, data)
            else:
                success, message, invoice = self.invoice_service.create_invoice(
                    data, self.items, self.user.id
                )
            
            if success:
                QMessageBox.information(self, "Başarılı", message)
                self.accept()
            else:
                QMessageBox.warning(self, "Hata", message)
        except Exception as e:
            logger.error(f"Fatura kaydetme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Kayıt hatası:\n{str(e)}")