# src/ui/central_pages/all_people_page.py
"""
Tüm Şubelerin Kişileri - Genel Merkez Görünümü
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QGraphicsDropShadowEffect, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles


class AllPeoplePage(QWidget):
    """Tüm şubelerin kişileri"""
    
    def __init__(self, user: User, central_window=None):
        super().__init__()
        self.user = user
        self.central_window = central_window
        
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        self.setObjectName("AllPeoplePage")
        self.setStyleSheet(f"#AllPeoplePage {{ background-color: {AppStyles.BG_DARK}; }}")
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)
        
        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(3)
        title = QLabel("👤 Tüm Kişiler")
        title.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)
        subtitle = QLabel("Tüm şubelerin kişi ve cari kayıtları")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        top_bar.addLayout(left)
        top_bar.addStretch()
        layout.addLayout(top_bar)
        
        # İstatistik
        stats = self.create_stats_cards()
        layout.addLayout(stats)
        
        # Filtreler
        filters = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 İsim, telefon, email ara...")
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
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Tümü", "Müşteri", "Tedarikçi"])
        self.type_combo.setMinimumHeight(42)
        self.type_combo.currentTextChanged.connect(self.load_data)
        filters.addWidget(self.type_combo, 1)
        
        layout.addLayout(filters)
        
        # Tablo
        table_frame = QFrame()
        table_frame.setObjectName("allPeopleTableFrame")
        table_frame.setStyleSheet(f"""
            QFrame#allPeopleTableFrame {{
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
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            'Şube', 'Kod', 'Ünvan', 'Telefon', 'Email', 'Bakiye', 'Tür'
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                border: none;
                gridline-color: {AppStyles.BORDER};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{ padding: 10px; border: none; }}
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
        h_h.setFont(QFont("Segoe UI", 9, QFont.Bold))
        h_h.setDefaultAlignment(Qt.AlignCenter)
        h_h.setFixedHeight(38)
        h_h.setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.table)
        
        self.total_label = QLabel("Toplam: 0 kişi")
        self.total_label.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; padding: 10px;")
        table_layout.addWidget(self.total_label)
        
        table_frame.setLayout(table_layout)
        layout.addWidget(table_frame)
        
        self.setLayout(layout)
    
    def create_stats_cards(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(15)
        
        try:
            from ...services.customer_service import CustomerService
            summary = CustomerService().get_companies_balance_summary()
            rec = summary.get('total_receivables', 0.0)
            pay = summary.get('total_payables', 0.0)
            net = summary.get('net_balance', 0.0)

            stats = db.fetch_one("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN is_supplier = FALSE THEN 1 ELSE 0 END) as customers,
                    SUM(CASE WHEN is_supplier = TRUE THEN 1 ELSE 0 END) as suppliers
                FROM Customers
                WHERE is_active = TRUE
            """) or {}

            c1, self.lbl_card_total = self.create_stat_card("👥", "Toplam Kişi", str(stats.get('total', 0)), AppStyles.PRIMARY)
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
        try:
            search = self.search_input.text().strip()
            branch_id = self.branch_combo.currentData()
            type_filter = self.type_combo.currentText()
            
            # İstatistik kartlarını güncelle
            try:
                from ...services.customer_service import CustomerService
                summary = CustomerService().get_companies_balance_summary(branch_id)
                c_list = summary.get('companies', [])
                rec = summary.get('total_receivables', 0.0)
                pay = summary.get('total_payables', 0.0)
                net = summary.get('net_balance', 0.0)

                if hasattr(self, 'lbl_card_rec') and self.lbl_card_rec:
                    self.lbl_card_rec.setText(f"{rec:,.0f} ₺")
                if hasattr(self, 'lbl_card_pay') and self.lbl_card_pay:
                    self.lbl_card_pay.setText(f"{pay:,.0f} ₺")
                if hasattr(self, 'lbl_card_net') and self.lbl_card_net:
                    self.lbl_card_net.setText(f"{net:+,.0f} ₺")
            except Exception as se:
                logger.error(f"AllPeoplePage kart güncelleme hatası: {se}")

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
                LEFT JOIN Invoices i ON i.customer_id = c.id
                LEFT JOIN Branches b ON b.id = i.branch_id
                WHERE c.is_active = TRUE
            """
            params = []
            
            if branch_id:
                query += " AND (i.branch_id = %s OR (i.id IS NULL AND c.branch_id = %s))"
                params.extend([branch_id, branch_id])
            
            if type_filter == "Müşteri":
                query += " AND c.is_supplier = FALSE"
            elif type_filter == "Tedarikçi":
                query += " AND c.is_supplier = TRUE"
            
            if search:
                query += " AND (c.title ILIKE %s OR c.phone ILIKE %s OR c.email ILIKE %s)"
                params.extend([f"%{search}%"] * 3)
            
            query += """
                GROUP BY c.id, c.customer_code, c.title, c.tax_no, c.tax_office, c.phone, c.email, c.address, c.balance, c.is_supplier, c.branch_id, b.name
                ORDER BY c.title LIMIT 1000
            """
            
            people = db.fetch_all(query, tuple(params))
            
            self.table.setRowCount(0)
            tot_rec = 0.0
            tot_pay = 0.0
            for i, c in enumerate(people):
                self.table.insertRow(i)
                self.table.setItem(i, 0, QTableWidgetItem(str(c.get('branch_name', ''))))
                self.table.setItem(i, 1, QTableWidgetItem(str(c.get('customer_code', ''))))
                self.table.setItem(i, 2, QTableWidgetItem(str(c.get('title', ''))))
                self.table.setItem(i, 3, QTableWidgetItem(str(c.get('phone', ''))))
                self.table.setItem(i, 4, QTableWidgetItem(str(c.get('email', ''))))
                
                inv_cnt = int(c.get('invoice_count') or 0)
                is_sup = c.get('is_supplier', False)
                s_unpaid = float(c.get('sales_unpaid') or 0)
                p_unpaid = float(c.get('purchase_unpaid') or 0)
                c_bal = float(c.get('balance', 0))

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
                        col = AppStyles.GREEN
                    elif net < -0.001:
                        balance_text = f"{abs(net):,.2f} ₺"
                        col = AppStyles.RED
                    else:
                        balance_text = "0.00 ₺"
                        col = AppStyles.TEXT_PRIMARY
                else:  # Tedarikçi
                    net = payable - receivable
                    if net > 0.001:
                        balance_text = f"{net:,.2f} ₺"
                        col = AppStyles.RED
                    elif net < -0.001:
                        balance_text = f"{abs(net):,.2f} ₺"
                        col = AppStyles.GREEN
                    else:
                        balance_text = "0.00 ₺"
                        col = AppStyles.TEXT_PRIMARY

                balance_item = QTableWidgetItem(balance_text)
                balance_item.setForeground(QColor(col))
                balance_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 5, balance_item)

                type_item = QTableWidgetItem("Tedarikçi" if is_sup else "Müşteri")
                type_item.setForeground(QColor(AppStyles.ORANGE if is_sup else AppStyles.PRIMARY))
                self.table.setItem(i, 6, type_item)

            self.total_label.setText(
                f"Toplam: <b>{len(people)}</b> Cari Hesap  |  "
                f"Toplam Alacağımız: <b style='color:{AppStyles.GREEN};'>{tot_rec:,.2f} ₺</b>  |  "
                f"Toplam Borcumuz: <b style='color:{AppStyles.RED};'>{tot_pay:,.2f} ₺</b>"
            )
        except Exception as e:
            logger.error(f"Kişi yükleme hatası: {e}")