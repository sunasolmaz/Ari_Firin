# src/ui/central_pages/all_invoices_page.py
"""
Tüm Şubelerin Faturaları - Genel Merkez Görünümü
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QDateEdit, QGraphicsDropShadowEffect, QHeaderView,
    QMessageBox, QPushButton, QInputDialog
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont
from datetime import datetime, timedelta

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles


class AllInvoicesPage(QWidget):
    """Tüm şubelerin faturaları"""

    def __init__(self, user: User, central_window=None):
        super().__init__()
        self.user = user
        self.central_window = central_window

        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setObjectName("AllInvoicesPage")
        self.setStyleSheet(f"#AllInvoicesPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)

        # Üst bar
        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(3)
        title = QLabel("📄 Tüm Faturalar")
        title.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)
        subtitle = QLabel("Tüm şubelerin faturaları")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        top_bar.addLayout(left)
        top_bar.addStretch()

        cust_inv_btn = QPushButton("🏢 Müşteri Faturalarını Gör")
        cust_inv_btn.setCursor(Qt.PointingHandCursor)
        cust_inv_btn.setMinimumHeight(38)
        cust_inv_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #0284c7;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 16px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{ background-color: #0369a1; }}
        """)
        cust_inv_btn.clicked.connect(self.open_customer_invoices_dialog)
        top_bar.addWidget(cust_inv_btn)

        approve_btn = QPushButton("✅ Seçili Faturayı Onayla")
        approve_btn.setCursor(Qt.PointingHandCursor)
        approve_btn.setMinimumHeight(38)
        approve_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 18px;
                font-weight: bold;
                font-size: 9.5pt;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        approve_btn.clicked.connect(self.approve_invoice)
        top_bar.addWidget(approve_btn)

        delete_btn = QPushButton("🗑️ Seçili Faturayı Sil")
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setMinimumHeight(38)
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.RED};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 18px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{ background-color: #dc2626; }}
        """)
        delete_btn.clicked.connect(self.delete_invoice)
        top_bar.addWidget(delete_btn)

        layout.addLayout(top_bar)

        # İstatistik kartları
        stats = self.create_stats_cards()
        layout.addLayout(stats)

        # Filtreler
        filter_frame = QFrame()
        filter_frame.setObjectName("invoicesFilterFrame")
        filter_frame.setStyleSheet(f"""
            QFrame#invoicesFilterFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                padding: 15px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("📅 Başlangıç:"))
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd.MM.yyyy")
        self.start_date.setMinimumHeight(40)
        filter_layout.addWidget(self.start_date)

        filter_layout.addWidget(QLabel("📅 Bitiş:"))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate().addDays(30))
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("dd.MM.yyyy")
        self.end_date.setMinimumHeight(40)
        filter_layout.addWidget(self.end_date)

        filter_layout.addWidget(QLabel("☕ Şube:"))
        self.branch_combo = QComboBox()
        self.branch_combo.setMinimumHeight(40)
        self.branch_combo.addItem("Tüm Şubeler", None)
        branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY name")
        for b in branches:
            self.branch_combo.addItem(b['name'], b['id'])
        filter_layout.addWidget(self.branch_combo)

        filter_layout.addWidget(QLabel("📌 Tip:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Tümü", "Satış", "Alış", "İade"])
        self.type_combo.setMinimumHeight(40)
        filter_layout.addWidget(self.type_combo)

        filter_layout.addWidget(QLabel("📊 Durum:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Tümü", "Taslak", "Onaylı"])
        self.status_combo.setMinimumHeight(40)
        filter_layout.addWidget(self.status_combo)

        search_btn = QPushButton("🔍 Filtrele")
        search_btn.clicked.connect(self.load_data)
        search_btn.setMinimumHeight(40)
        search_btn.setStyleSheet(f"background-color: {AppStyles.PRIMARY}; color: white; border: none; border-radius: 8px; font-weight: bold; padding: 0 20px;")
        filter_layout.addWidget(search_btn)

        filter_layout.addStretch()
        filter_frame.setLayout(filter_layout)
        layout.addWidget(filter_frame)

        # Tablo
        table_frame = QFrame()
        table_frame.setObjectName("allInvoicesTableFrame")
        table_frame.setStyleSheet(f"""
            QFrame#allInvoicesTableFrame {{
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
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            'Şube', 'Fatura No', 'Tarih', 'Tip', 'Müşteri', 'Tutar', 'KDV', 'Durum'
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
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
        table_layout.addWidget(self.table)

        self.total_label = QLabel("Toplam: 0 fatura")
        self.total_label.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; padding: 10px;")
        table_layout.addWidget(self.total_label)

        table_frame.setLayout(table_layout)
        layout.addWidget(table_frame)

        self.setLayout(layout)

    def create_stats_cards(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(15)

        try:
            stats = db.fetch_one("""
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(CASE WHEN invoice_type IN ('Sales', 'Satış') THEN grand_total END), 0) as total_sales,
                    COALESCE(SUM(CASE WHEN invoice_type IN ('Purchase', 'Alış') THEN grand_total END), 0) as total_purchases,
                    COALESCE(SUM(CASE WHEN status = 'Approved' THEN 1 END), 0) as approved
                FROM Invoices
            """)

            cards = [
                ("📄", "Toplam Fatura", str(stats.get('total', 0)), AppStyles.PRIMARY),
                ("💰", "Toplam Satış", f"{stats.get('total_sales', 0):,.0f} ₺", AppStyles.GREEN),
                ("💳", "Toplam Alış", f"{stats.get('total_purchases', 0):,.0f} ₺", AppStyles.RED),
                ("✅", "Onaylı", str(stats.get('approved', 0)), AppStyles.CYAN),
            ]

            for icon, title, value, color in cards:
                card = self.create_stat_card(icon, title, value, color)
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
        return card

    def load_data(self):
        try:
            start = self.start_date.date().toString("yyyy-MM-dd")
            end = self.end_date.date().toString("yyyy-MM-dd")
            branch_id = self.branch_combo.currentData()
            type_filter = self.type_combo.currentText()
            # ✅ Gereksiz hasattr kaldırıldı
            status_filter = self.status_combo.currentText()

            query = """
                SELECT i.*, b.name as branch_name, c.title as customer_name
                FROM Invoices i
                LEFT JOIN Branches b ON b.id = i.branch_id
                LEFT JOIN Customers c ON c.id = i.customer_id
                WHERE i.invoice_date BETWEEN %s AND %s
            """
            params = [start, end]

            if branch_id:
                query += " AND i.branch_id = %s"
                params.append(branch_id)

            if type_filter != "Tümü":
                type_map = {"Satış": "Sales", "Alış": "Purchase", "İade": "Return"}
                query += " AND i.invoice_type = %s"
                params.append(type_map.get(type_filter, type_filter))

            if status_filter != "Tümü":
                status_map = {"Taslak": "Draft", "Onaylı": "Approved"}
                query += " AND i.status = %s"
                params.append(status_map.get(status_filter, status_filter))

            query += " ORDER BY i.invoice_date DESC, i.id DESC LIMIT 1000"

            invoices = db.fetch_all(query, tuple(params))

            self.table.setRowCount(0)
            for i, inv in enumerate(invoices):
                self.table.insertRow(i)

                b_item = QTableWidgetItem(str(inv.get('branch_name') or ''))
                b_item.setData(Qt.UserRole, inv.get('branch_id'))
                self.table.setItem(i, 0, b_item)

                no_item = QTableWidgetItem(str(inv.get('invoice_no') or ''))
                no_item.setData(Qt.UserRole, inv.get('id'))
                self.table.setItem(i, 1, no_item)

                self.table.setItem(i, 2, QTableWidgetItem(str(inv.get('invoice_date') or '')))

                inv_type = inv.get('invoice_type') or ''
                type_text = {'Sales': 'Satış', 'Purchase': 'Alış', 'Return': 'İade'}.get(inv_type, inv_type)
                type_item = QTableWidgetItem(type_text)
                type_item.setForeground(QColor(
                    AppStyles.GREEN if inv_type == 'Sales' else
                    AppStyles.RED if inv_type == 'Purchase' else
                    AppStyles.ORANGE
                ))
                type_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, 3, type_item)

                cust_name_str = str(inv.get('customer_name') or 'Tanımsız Müşteri')
                c_item = QTableWidgetItem(f"🏢 {cust_name_str}")
                c_item.setData(Qt.UserRole, inv.get('customer_id'))
                c_item.setData(Qt.UserRole + 1, inv.get('customer_name'))
                c_item.setToolTip("Müşterinin farklı tarihlerdeki tüm faturalarını açılır pencerede görmek için çift tıklayın")
                c_item.setForeground(QColor("#38bdf8"))
                c_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(i, 4, c_item)

                # Tutar (sağa hizalı)
                tot_item = QTableWidgetItem(f"{float(inv.get('grand_total') or 0):,.2f} ₺")
                tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 5, tot_item)

                # KDV (sağa hizalı)
                vat_item = QTableWidgetItem(f"{float(inv.get('vat_total') or 0):,.2f} ₺")
                vat_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 6, vat_item)

                status = inv.get('status') or ''
                status_item = QTableWidgetItem("✅ Onaylı" if status == 'Approved' else "📝 Taslak")
                status_item.setForeground(QColor(AppStyles.GREEN if status == 'Approved' else "#f59e0b"))
                status_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                status_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, 7, status_item)

            self.total_label.setText(f"Toplam: {len(invoices)} fatura (Müşterinin tüm faturaları için müşteri hücresine çift tıklayın)")
        except Exception as e:
            logger.error(f"Fatura yükleme hatası: {e}")

    def on_cell_double_clicked(self, row: int, col: int):
        """Hücreye çift tıklandığında müşteri hücresi ise müşteri faturalarını, değilse fatura düzenlemeyi açar"""
        if row < 0:
            return
        if col == 4:
            c_item = self.table.item(row, 4)
            if c_item:
                c_id = c_item.data(Qt.UserRole)
                c_title = c_item.data(Qt.UserRole + 1)
                b_item = self.table.item(row, 0)
                b_id = b_item.data(Qt.UserRole) if b_item else None
                if c_id or c_title:
                    try:
                        from ..pages.invoices_page import CustomerInvoicesDialog
                        dlg = CustomerInvoicesDialog(self.user, b_id, c_id or 0, c_title, self)
                        dlg.exec_()
                        self.load_data()
                        return
                    except Exception as e:
                        logger.error(f"CustomerInvoicesDialog açma hatası: {e}")
        self.edit_invoice()

    def open_customer_invoices_dialog(self):
        """Müşteri seçerek tüm tarihlerdeki faturalarını açılır pencerede inceleme"""
        try:
            from ...services.customer_service import CustomerService
            from ..pages.invoices_page import CustomerInvoicesDialog
            cs = CustomerService()
            branch_id = self.branch_combo.currentData()
            customers, _ = cs.get_customers(branch_id, 1, 9999)
            if not customers:
                QMessageBox.information(self, "Bilgi", "Kayıtlı cari hesap / müşteri bulunamadı!")
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
                dlg = CustomerInvoicesDialog(self.user, branch_id, sel_cust.id, sel_cust.title, self)
                dlg.exec_()
                self.load_data()
        except Exception as e:
            logger.error(f"open_customer_invoices_dialog hatası: {e}")

    def edit_invoice(self):
        """Faturayı düzenle"""
        row = self.table.currentRow()
        if row < 0:
            return

        inv_id = self.table.item(row, 1).data(Qt.UserRole)
        branch_id = self.table.item(row, 0).data(Qt.UserRole)
        if inv_id and branch_id:
            try:
                from ..pages.invoices_page import InvoiceDialog
                from PyQt5.QtWidgets import QDialog
                dialog = InvoiceDialog(self.user, branch_id, self, invoice_id=inv_id)
                if dialog.exec_() == QDialog.Accepted:
                    self.load_data()
            except Exception as e:
                logger.error(f"Fatura dialog hatası: {e}")

    def approve_invoice(self):
        """Genel merkezden seçili taslak faturayı onayla"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen onaylamak istediğiniz taslak faturayı seçin!")
            return

        inv_id = self.table.item(row, 1).data(Qt.UserRole)
        branch_name = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
        inv_no = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
        cust_name = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
        status_text = self.table.item(row, 7).text() if self.table.item(row, 7) else ""

        if not inv_id:
            QMessageBox.warning(self, "Uyarı", "Geçersiz fatura seçimi!")
            return

        if "Onaylı" in status_text:
            QMessageBox.information(self, "Bilgi", "Bu fatura zaten onaylanmıştır.")
            return

        confirm_msg = f"<b>{inv_no}</b> numaralı taslak faturayı ({branch_name}) onaylamak istediğinize emin misiniz?"
        if cust_name:
            confirm_msg += f"<br><b>Müşteri:</b> {cust_name}"
        confirm_msg += (
            "<br><br>Bu işlem sonucunda:<br>"
            "• Faturadaki ürünlerin stok miktarları güncellenecek,<br>"
            "• Cari hesap bakiyesine yansıtılacak,<br>"
            "• Muhasebe kaydı kesinleştirilecektir."
        )

        reply = QMessageBox.question(
            self, "Fatura Onaylama Onayı",
            confirm_msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            from ...services.invoice_service import InvoiceService
            invoice_service = InvoiceService()
            success, message = invoice_service.approve_invoice(inv_id)
            if success:
                QMessageBox.information(self, "Başarılı", f"✅ {message}")
                self.load_data()
            else:
                QMessageBox.warning(self, "Hata", f"❌ Fatura onaylanamadı:\n{message}")

    def delete_invoice(self):
        """Genel merkezden seçili faturayı sil"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz faturayı seçin!")
            return

        inv_id = self.table.item(row, 1).data(Qt.UserRole)
        branch_name = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
        inv_no = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
        cust_name = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
        status_text = self.table.item(row, 7).text() if self.table.item(row, 7) else ""

        if not inv_id:
            QMessageBox.warning(self, "Uyarı", "Geçersiz fatura seçimi!")
            return

        warn_msg = f"<b>{inv_no}</b> numaralı faturayı ({branch_name}) silmek istediğinize emin misiniz?"
        if cust_name:
            warn_msg += f"<br><b>Müşteri:</b> {cust_name}"
        if status_text == "Onaylı":
            warn_msg += f"<br><br><span style='color: {AppStyles.ORANGE};'>⚠️ <b>Dikkat:</b> Bu fatura <b>ONAYLANMIŞ</b> bir faturadır.<br>Silindiğinde cari hesap bakiyesi ve muhasebe kayıtları otomatik olarak düzeltilecektir.</span>"
        else:
            warn_msg += "<br><br>Bu taslak faturayı kalıcı olarak silmek istiyor musunuz?"

        reply = QMessageBox.question(
            self, "Fatura Silme Onayı",
            warn_msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            from ...services.invoice_service import InvoiceService
            invoice_service = InvoiceService()
            success, message = invoice_service.delete_invoice(inv_id)
            if success:
                QMessageBox.information(self, "Başarılı", message)
                self.load_data()
            else:
                QMessageBox.warning(self, "Hata", message)