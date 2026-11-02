# src/ui/central_pages/all_customers_page.py
"""
Tüm Şubelerin Cari Hesapları - Genel Merkez Görünümü
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QGraphicsDropShadowEffect, QHeaderView, QScrollArea
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ...services.customer_service import CustomerService
from ..styles import AppStyles


class AllCustomersPage(QWidget):
    """Tüm şubelerin cari hesapları"""

    def __init__(self, user: User, central_window=None):
        super().__init__()
        self.user = user
        self.central_window = central_window
        self.customer_service = CustomerService()

        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setObjectName("AllCustomersPage")
        self.setStyleSheet(f"#AllCustomersPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)

        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(3)
        title = QLabel("👥 Tüm Cari Hesaplar")
        title.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)
        subtitle = QLabel("Şubelerin cari hesapları")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        top_bar.addLayout(left)
        top_bar.addStretch()

        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setToolTip("Cari hesap listesini ve bakiyeleri yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setMinimumHeight(42)
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                font-weight: bold; font-size: 10.5pt; padding: 0 20px;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """)
        top_bar.addWidget(refresh_btn)

        new_btn = QPushButton("📄 Yeni Fatura Kes")
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.setMinimumHeight(42)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                color: white; border: none; border-radius: 8px;
                font-weight: bold; font-size: 11pt; padding: 0 25px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
            }}
        """)
        new_btn.clicked.connect(self.new_invoice)
        top_bar.addWidget(new_btn)

        layout.addLayout(top_bar)

        # İstatistik kartları
        stats = self.create_stats_cards()
        layout.addLayout(stats)

        # Filtreler
        filters = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Ara...")
        self.search_input.setMinimumHeight(42)
        self.search_input.textChanged.connect(self.load_data)
        filters.addWidget(self.search_input, 3)

        self.branch_combo = QComboBox()
        self.branch_combo.setMinimumHeight(42)
        self.branch_combo.addItem("Tüm Şubeler", None)
        branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY name")
        for b in branches:
            self.branch_combo.addItem(b['name'], b['id'])
        self.branch_combo.currentIndexChanged.connect(self.load_data)
        filters.addWidget(self.branch_combo, 1)

        layout.addLayout(filters)

        # Tablo
        table_frame = QFrame()
        table_frame.setObjectName("allCustomersTableFrame")
        table_frame.setStyleSheet(f"""
            QFrame#allCustomersTableFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 5)
        table_frame.setGraphicsEffect(shadow)

        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(15, 15, 15, 15)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            'Şube', 'Kod', 'Ünvan', 'Vergi No', 'Telefon', 'Fatura', 'Bakiye', 'Bakiye Durumu', 'Tür', 'Detay'
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                border: none;
                gridline-color: {AppStyles.BORDER};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{ padding: 10px; border: none; }}
            QTableWidget::item:selected {{ background-color: {AppStyles.PRIMARY}30; }}
            QHeaderView {{
                background-color: #1e1e28;
                border: none;
            }}
            QHeaderView::section {{
                background-color: #1e1e28;
                color: #FFFFFF !important;
                padding: 4px 8px;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                border-right: 1px solid #282838;
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
        h_h.setSectionResizeMode(QHeaderView.Stretch)
        h_h.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        h_h.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        table_layout.addWidget(self.table)

        self.total_label = QLabel("Toplam: 0 cari hesap")
        self.total_label.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; padding: 10px;")
        table_layout.addWidget(self.total_label)

        table_frame.setLayout(table_layout)
        layout.addWidget(table_frame)

        self.setLayout(layout)

    def create_stats_cards(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(15)

        try:
            summary = self.customer_service.get_companies_balance_summary()
            c_list = summary.get('companies', [])
            rec = summary.get('total_receivables', 0.0)
            pay = summary.get('total_payables', 0.0)
            net = summary.get('net_balance', 0.0)

            c1, self.lbl_card_total = self.create_stat_card("👥", "Toplam Cari (Faturalı)", str(len(c_list)), AppStyles.PRIMARY)
            c2, self.lbl_card_rec = self.create_stat_card("🛒", "Müşteri Alacağı", f"{rec:,.0f} ₺", AppStyles.GREEN)
            c3, self.lbl_card_pay = self.create_stat_card("🚚", "Tedarikçi Borcu", f"{pay:,.0f} ₺", AppStyles.RED)
            c4, self.lbl_card_net = self.create_stat_card("⚖️", "Net Bakiye", f"{net:+,.0f} ₺", AppStyles.CYAN)

            for card in [c1, c2, c3, c4]:
                layout.addWidget(card)
        except Exception as e:
            logger.error(f"İstatistik hatası: {e}")

        return layout

    def create_stat_card(self, icon, title, value, color):
        card = QFrame()
        card.setMinimumHeight(100)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                border-left: 4px solid {color};
                padding: 15px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        layout.setSpacing(5)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 18pt; background: transparent; border: none;")
        layout.addWidget(icon_lbl)

        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {color}; background: transparent; border: none;")
        layout.addWidget(value_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY}; background: transparent; border: none;")
        layout.addWidget(title_lbl)

        card.setLayout(layout)
        return card, value_lbl

    def load_data(self):
        """Verileri yükle - Sadece faturası kesilmiş firmalar"""
        try:
            search = self.search_input.text().strip()
            branch_id = self.branch_combo.currentData()

            # İstatistik kartlarını güncelle (Invoices ve Customers ile 100% senkronize)
            summary = self.customer_service.get_companies_balance_summary(branch_id)
            c_list = summary.get('companies', [])
            rec = summary.get('total_receivables', 0.0)
            pay = summary.get('total_payables', 0.0)
            net = summary.get('net_balance', 0.0)

            if hasattr(self, 'lbl_card_total') and self.lbl_card_total:
                self.lbl_card_total.setText(str(len(c_list)))
            if hasattr(self, 'lbl_card_rec') and self.lbl_card_rec:
                self.lbl_card_rec.setText(f"{rec:,.0f} ₺")
            if hasattr(self, 'lbl_card_pay') and self.lbl_card_pay:
                self.lbl_card_pay.setText(f"{pay:,.0f} ₺")
            if hasattr(self, 'lbl_card_net') and self.lbl_card_net:
                self.lbl_card_net.setText(f"{net:+,.0f} ₺")

            query = """
                SELECT c.*, b.name as branch_name,
                       COUNT(i.id) as invoice_count,
                       COALESCE(SUM(CASE WHEN i.invoice_type IN ('Sales', 'Satış') AND (i.status IS NULL OR i.status != 'Cancelled') THEN 
                           CASE WHEN i.payment_status = 'Paid' THEN 0 
                                ELSE COALESCE(i.remaining_amount, i.grand_total - COALESCE(i.paid_amount, 0)) 
                           END ELSE 0 END), 0) as sales_unpaid,
                       COALESCE(SUM(CASE WHEN i.invoice_type IN ('Purchase', 'Alış') AND (i.status IS NULL OR i.status != 'Cancelled') THEN 
                           CASE WHEN i.payment_status = 'Paid' THEN 0 
                                ELSE COALESCE(i.remaining_amount, i.grand_total - COALESCE(i.paid_amount, 0)) 
                           END ELSE 0 END), 0) as purchase_unpaid
                FROM Customers c
                LEFT JOIN Invoices i ON i.customer_id = c.id AND (i.status IS NULL OR i.status != 'Cancelled')
                LEFT JOIN Branches b ON b.id = c.branch_id
                WHERE c.is_active = TRUE
            """
            params = []

            if branch_id:
                query += " AND c.branch_id = %s"
                params.append(branch_id)

            if search:
                query += " AND (c.title ILIKE %s OR c.tax_no ILIKE %s OR c.phone ILIKE %s)"
                params.extend([f"%{search}%"] * 3)

            query += """
                GROUP BY c.id, c.customer_code, c.title, c.tax_no, c.tax_office, c.phone, c.email, c.address, c.balance, c.is_supplier, c.branch_id, b.name
                ORDER BY c.title ASC LIMIT 1000
            """

            customers = db.fetch_all(query, tuple(params))

            self.table.setRowCount(0)
            tot_rec = 0.0
            tot_pay = 0.0
            for i, c in enumerate(customers):
                self.table.insertRow(i)
                self.table.setItem(i, 0, QTableWidgetItem(str(c.get('branch_name') or '')))
                self.table.setItem(i, 1, QTableWidgetItem(str(c.get('customer_code') or '')))
                self.table.setItem(i, 2, QTableWidgetItem(str(c.get('title') or '')))
                self.table.setItem(i, 3, QTableWidgetItem(str(c.get('tax_no') or '')))
                self.table.setItem(i, 4, QTableWidgetItem(str(c.get('phone') or '')))

                inv_cnt = int(c.get('invoice_count') or 0)
                inv_item = QTableWidgetItem(f"📄 {inv_cnt} Fatura")
                inv_item.setTextAlignment(Qt.AlignCenter)
                inv_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(i, 5, inv_item)

                is_sup = c.get('is_supplier', False)
                s_unpaid = float(c.get('sales_unpaid') or 0)
                p_unpaid = float(c.get('purchase_unpaid') or 0)
                c_bal = float(c.get('balance') or 0)

                if inv_cnt > 0:
                    receivable = s_unpaid
                    payable = p_unpaid
                else:
                    if is_sup:
                        payable = max(0.0, c_bal)
                        receivable = max(0.0, -c_bal)
                    else:
                        receivable = max(0.0, c_bal)
                        payable = max(0.0, -c_bal)

                tot_rec += receivable
                tot_pay += payable

                if not is_sup:  # Müşteri
                    net = receivable - payable
                    if net > 0.001:
                        balance_text = f"{net:,.2f} ₺"
                        status_text = "🟢 Alacağımız (Müşteri Borçlu)"
                        status_color = AppStyles.GREEN
                    elif net < -0.001:
                        balance_text = f"{abs(net):,.2f} ₺"
                        status_text = "🔴 Borcumuz (Avans / Fazla Ödeme)"
                        status_color = AppStyles.RED
                    else:
                        balance_text = "0.00 ₺"
                        status_text = "⚪ Hesap Kapalı (0.00 ₺)"
                        status_color = AppStyles.TEXT_SECONDARY
                else:  # Tedarikçi
                    net = payable - receivable
                    if net > 0.001:
                        balance_text = f"{net:,.2f} ₺"
                        status_text = "🔴 Borcumuz (Tedarikçiye Ödenecek)"
                        status_color = AppStyles.RED
                    elif net < -0.001:
                        balance_text = f"{abs(net):,.2f} ₺"
                        status_text = "🟢 Alacağımız (Verilen Avans)"
                        status_color = AppStyles.GREEN
                    else:
                        balance_text = "0.00 ₺"
                        status_text = "⚪ Hesap Kapalı (0.00 ₺)"
                        status_color = AppStyles.TEXT_SECONDARY

                balance_item = QTableWidgetItem(balance_text)
                balance_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                balance_item.setForeground(QColor(status_color))
                self.table.setItem(i, 6, balance_item)

                status_item = QTableWidgetItem(status_text)
                status_item.setForeground(QColor(status_color))
                self.table.setItem(i, 7, status_item)

                type_item = QTableWidgetItem("Tedarikçi" if is_sup else "Müşteri")
                type_item.setForeground(QColor(AppStyles.ORANGE if is_sup else AppStyles.PRIMARY))
                type_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, 8, type_item)

                det_btn = QPushButton("📋 Detay")
                det_btn.setFixedSize(65, 30)
                det_btn.setCursor(Qt.PointingHandCursor)
                det_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0284c7;
                        color: white;
                        border-radius: 6px;
                        font-size: 8.5pt;
                        font-weight: 600;
                        border: none;
                    }
                    QPushButton:hover { background-color: #0369a1; }
                """)
                cust_id = c['id']
                cust_title = c.get('title') or ''
                c_branch = c.get('branch_id')
                det_btn.clicked.connect(lambda ch, cid=cust_id, ct=cust_title, cb=c_branch: self.open_customer_detail(cid, ct, cb))
                self.table.setCellWidget(i, 9, det_btn)

                self.table.item(i, 0).setData(Qt.UserRole, cust_id)

            self.total_label.setText(
                f"Toplam: <b>{len(customers)}</b> Faturalı Firma  |  "
                f"Toplam Alacağımız: <b style='color:{AppStyles.GREEN};'>{tot_rec:,.2f} ₺</b>  |  "
                f"Toplam Borcumuz: <b style='color:{AppStyles.RED};'>{tot_pay:,.2f} ₺</b>"
            )
        except Exception as e:
            logger.error(f"Cari hesap yükleme hatası: {e}")

    def on_cell_double_clicked(self, row: int, col: int):
        item = self.table.item(row, 0)
        if not item:
            return
        cust_id = item.data(Qt.UserRole)
        c_title = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
        self.open_customer_detail(cust_id, c_title)

    def open_customer_detail(self, customer_id: int, customer_title: str, branch_id: int = None):
        try:
            from ..pages.invoices_page import CustomerInvoicesDialog
            dlg = CustomerInvoicesDialog(self.user, branch_id, customer_id, customer_title, self)
            dlg.exec_()
            self.load_data()
        except Exception as e:
            logger.error(f"Firma detay açma hatası: {e}")

    def new_invoice(self):
        if self.central_window and hasattr(self.central_window, 'navigate_to'):
            self.central_window.navigate_to("all_invoices")
        else:
            try:
                from ..pages.invoices_page import InvoiceDialog
                b = db.fetch_one("SELECT id FROM Branches WHERE is_active = TRUE ORDER BY id LIMIT 1")
                b_id = b['id'] if b else 1
                dialog = InvoiceDialog(self.user, b_id, self)
                if dialog.exec_() == 1:
                    self.load_data()
            except Exception as e:
                logger.error(f"Fatura açma hatası: {e}")