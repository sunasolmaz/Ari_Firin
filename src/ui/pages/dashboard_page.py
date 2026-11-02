# src/ui/pages/dashboard_page.py
"""
Ana Panel - Şube Genel Durumu
Cari hesap özetleri, istatistikler, şube değiştirme
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
    QGraphicsDropShadowEffect, QTableWidget, QTableWidgetItem
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from datetime import datetime, timedelta

from ...models.user import User
from ...models.branch import Branch
from ...core.database import db
from ...core.logger import logger
from ...services.report_service import ReportService
from ...services.turnover_service import turnover_service
from ...services.payment_plan_service import payment_plan_service
from ..styles import AppStyles
from ..notifications_dialog import NotificationsDialog


class DashboardPage(QWidget):
    """Ana panel sayfası"""

    def __init__(self, user: User, branch_id: int, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window
        self.report_service = ReportService()

        # ✅ Canlı saat için referans
        self._clock_label = None
        self._clock_timer = None

        self.init_ui()
        self.load_data()

        # ✅ Saat timer'ı başlat (her dakika güncelle)
        self._start_clock_timer()

    def init_ui(self):
        """Arayüzü oluştur"""
        self.setObjectName("DashboardPage")
        self.setStyleSheet(f"#DashboardPage {{ background-color: {AppStyles.BG_DARK}; }}")

        # Ana scroll area
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        content = QWidget()
        content.setStyleSheet(f"background-color: {AppStyles.BG_DARK};")

        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)

        # 1. Bildirimleri topla
        self.notifications = self.fetch_notifications()

        # ==================== ÜST BAR ====================
        top_bar = self.create_top_bar()
        layout.addWidget(top_bar)

        # ==================== İSTATİSTİK KARTLARI (2x2 IZGARA) ====================
        stats_layout = self.create_stats_cards()
        layout.addLayout(stats_layout)

        # ==================== ORTA BÖLÜM ====================
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(8)

        recent_invoices = self.create_recent_invoices()
        middle_layout.addWidget(recent_invoices, 2)

        right_column = self.create_right_column()
        middle_layout.addWidget(right_column, 1)

        layout.addLayout(middle_layout)
        layout.addStretch()

        content.setLayout(layout)
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    # ==================== CANLI SAAT ====================

    def _start_clock_timer(self):
        """Saat güncelleme timer'ını başlat (her 30 saniyede bir)"""
        if self._clock_timer is None:
            self._clock_timer = QTimer(self)
            self._clock_timer.timeout.connect(self._update_clock)
            self._clock_timer.start(30 * 1000)  # 30 saniye

    def _update_clock(self):
        """Saat etiketini güncelle"""
        try:
            if self._clock_label is not None:
                self._clock_label.setText(f"🕐 {datetime.now().strftime('%H:%M')}")
        except Exception:
            pass

    def hideEvent(self, event):
        """Sayfa gizlendiğinde timer'ı durdur (kaynak tüketimini azalt)"""
        if self._clock_timer is not None:
            self._clock_timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        """Sayfa tekrar göründüğünde timer'ı başlat"""
        if self._clock_timer is not None:
            self._clock_timer.start(30 * 1000)
        self._update_clock()
        super().showEvent(event)

    # ==================== ÜST BAR ====================

    def create_top_bar(self) -> QWidget:
        """Üst başlık çubuğu - Kompakt ve orantılı"""
        bar = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Sol - Başlık ve Tarih
        left = QVBoxLayout()
        left.setSpacing(2)

        title = QLabel("📊 Genel Bakış")
        title.setStyleSheet(f"""
            font-size: 14pt;
            font-weight: bold;
            color: {AppStyles.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)
        left.addWidget(title)

        subtitle = QLabel(f"📅 {datetime.now().strftime('%d %B %Y, %A')}")
        subtitle.setStyleSheet(f"""
            font-size: 10pt;
            color: {AppStyles.TEXT_SECONDARY};
            background: transparent;
            border: none;
        """)
        left.addWidget(subtitle)
        layout.addLayout(left)

        # 🔔 BİLDİRİM BUTONU: Başlığın hemen yanında
        notif_cnt = len(self.notifications) if hasattr(self, 'notifications') else 0
        btn_txt = f"🔔  {notif_cnt} Bildirim" if notif_cnt > 0 else "🔔  Bildirimler"
        self.notif_btn = QPushButton(btn_txt)
        self.notif_btn.setCursor(Qt.PointingHandCursor)
        self.notif_btn.setFixedHeight(30)
        self.notif_btn.clicked.connect(self.open_notifications_dialog)
        if notif_cnt > 0:
            self.notif_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.RED}25;
                    color: {AppStyles.RED};
                    border: 1px solid {AppStyles.RED}80;
                    border-radius: 6px;
                    padding: 3px 12px;
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
                    border-radius: 6px;
                    padding: 3px 12px;
                    font-size: 9.5pt;
                }}
                QPushButton:hover {{
                    border-color: {AppStyles.PRIMARY};
                    color: {AppStyles.PRIMARY};
                }}
            """)
        layout.addWidget(self.notif_btn)

        layout.addStretch()

        # Sağ - Saat ve Yenileme
        right = QHBoxLayout()
        right.setSpacing(10)
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._clock_label = QLabel(f"🕐 {datetime.now().strftime('%H:%M')}")
        self._clock_label.setStyleSheet(f"""
            font-size: 10pt;
            font-weight: 500;
            color: {AppStyles.TEXT_SECONDARY};
            background: transparent;
            border: none;
        """)
        right.addWidget(self._clock_label)

        # Yenile butonu
        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setFixedHeight(30)
        refresh_btn.clicked.connect(self.refresh)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 3px 12px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.BG_LIGHT};
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        right.addWidget(refresh_btn)

        layout.addLayout(right)
        bar.setLayout(layout)
        return bar

    # ==================== İSTATİSTİK KARTLARI (2x2 IZGARA) ====================

    def create_stats_cards(self) -> QGridLayout:
        """4 istatistik kartı - 2x2 Izgara (ikisi yan yana, ikisi alt alta)"""
        layout = QGridLayout()
        layout.setSpacing(8)

        try:
            today = datetime.now().date().strftime('%Y-%m-%d')
            month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')

            turnover_daily = turnover_service.get_daily_summary(self.branch_id, today)
            turnover_cum = turnover_service.get_cumulative_turnover(self.branch_id, today)

            monthly_stats = self.report_service.get_invoice_stats(
                self.branch_id, month_start, today
            )

            daily_c = turnover_daily.get('total_income', 0.0)
            cum_c = turnover_cum.get('cumulative_income', 0.0)
            monthly_purchases = monthly_stats.get('total_purchases') or 0
            monthly_sales = monthly_stats.get('total_sales') or 0

            # Aylık Ciro: Fatura satışlarından değil, doğrudan Ciro servisinden alınır
            today_dt = datetime.now().date()
            turnover_month = turnover_service.get_monthly_summary(self.branch_id, today_dt.year, today_dt.month)
            monthly_c = turnover_month.get('total_income', 0.0)
            monthly_val = monthly_c if monthly_c > 0 else (cum_c if cum_c > 0 else daily_c)

            from ...services.customer_service import CustomerService
            cs = CustomerService()
            summary = cs.get_companies_balance_summary(self.branch_id)
            total_receivables = summary.get('total_receivables', 0.0)
            total_payables = summary.get('total_payables', 0.0)

            # 2x2 Izgara kartları:
            # (row, col, icon, title, value, color, trend, sub_info)
            cards_data = [
                (0, 0, "🪙", "Bugünkü Ciro", f"{daily_c:,.0f} ₺", AppStyles.GREEN, "↗", "Günlük Kasa Girişi"),
                (0, 1, "🏆", "Aylık Ciro", f"{monthly_val:,.0f} ₺", AppStyles.PURPLE, "📊", f"Kümülatif: {cum_c:,.0f} ₺"),
                (1, 0, "📈", "Toplam Cari Alacak", f"{total_receivables:,.0f} ₺", AppStyles.CYAN, "👤", "Müşteri Alacakları"),
                (1, 1, "📉", "Toplam Cari Borç", f"{total_payables:,.0f} ₺", AppStyles.ORANGE, "⚠️", f"Aylık Gider: {monthly_purchases:,.0f} ₺"),
            ]

            for r, c, icon, title, value, color, trend, sub_info in cards_data:
                card = self.create_stat_card(icon, title, value, color, trend, sub_info)
                layout.addWidget(card, r, c)
        except Exception as e:
            logger.error(f"İstatistik hatası: {e}")

        return layout

    def create_stat_card(self, icon: str, title: str, value: str, color: str, trend: str, sub_info: str = "") -> QFrame:
        """Kompakt ve okunaklı 2x2 istatistik kartı"""
        card = QFrame()
        card.setObjectName("statCard")
        card.setFixedHeight(82)
        card.setStyleSheet(f"""
            QFrame#statCard {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 8px;
                border: 1px solid {AppStyles.BORDER};
                border-left: 4px solid {color};
            }}
            QFrame#statCard QLabel {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 2)
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(12, 8, 12, 8)

        # Üst Satır: İkon + Başlık + Trend
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(22, 22)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(f"""
            background-color: {color}25;
            border-radius: 11px;
            font-size: 11pt;
            border: none;
        """)
        top_layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"""
            font-size: 10pt;
            color: {AppStyles.TEXT_SECONDARY};
            font-weight: 600;
        """)
        top_layout.addWidget(title_lbl)

        top_layout.addStretch()

        trend_lbl = QLabel(trend)
        trend_lbl.setStyleSheet(f"""
            font-size: 10pt;
            color: {color};
            font-weight: bold;
        """)
        top_layout.addWidget(trend_lbl)

        layout.addLayout(top_layout)

        # Alt Satır: Tutar + Alt Bilgi
        bot_layout = QHBoxLayout()
        bot_layout.setContentsMargins(0, 0, 0, 0)
        bot_layout.setSpacing(8)

        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(f"""
            font-size: 15pt;
            font-weight: bold;
            color: {color};
        """)
        bot_layout.addWidget(value_lbl)

        if sub_info:
            bot_layout.addStretch()
            sub_lbl = QLabel(sub_info)
            sub_lbl.setStyleSheet(f"""
                font-size: 9.5pt;
                color: {AppStyles.TEXT_SECONDARY};
            """)
            bot_layout.addWidget(sub_lbl)

        layout.addLayout(bot_layout)

        card.setLayout(layout)
        return card

    # ==================== SON FATURALAR ====================

    def create_recent_invoices(self) -> QFrame:
        """Son faturalar - Kompakt"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 8px;
                border: 1px solid {AppStyles.BORDER};
                padding: 8px 10px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 2)
        frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        layout.setSpacing(6)

        header = QHBoxLayout()

        title = QLabel("📋 Son Faturalar")
        title.setStyleSheet(f"""
            font-size: 11pt;
            font-weight: bold;
            color: {AppStyles.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)
        header.addWidget(title)

        header.addStretch()

        view_all_btn = QPushButton("Tümünü Gör →")
        view_all_btn.setCursor(Qt.PointingHandCursor)
        if self.main_window:
            view_all_btn.clicked.connect(lambda: self.main_window.navigate_to("invoices"))
        view_all_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {AppStyles.PRIMARY};
                font-size: 9.5pt;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                color: {AppStyles.CYAN};
            }}
        """)
        header.addWidget(view_all_btn)

        layout.addLayout(header)

        try:
            recent = self.report_service.get_invoice_report(
                self.branch_id,
                (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                datetime.now().strftime('%Y-%m-%d')
            )

            if recent and isinstance(recent, list):
                table = QTableWidget()
                table.setColumnCount(5)
                table.setHorizontalHeaderLabels(['Fatura No', 'Tarih', 'Müşteri', 'Tutar', 'Durum'])
                table.setRowCount(min(len(recent), 5))
                table.setAlternatingRowColors(True)
                table.verticalHeader().setVisible(False)
                table.verticalHeader().setDefaultSectionSize(38)
                table.horizontalHeader().setVisible(True)
                table.horizontalHeader().setFixedHeight(36)
                table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                table.setFixedHeight(210)
                table.setStyleSheet(f"""
                    QTableWidget {{
                        background-color: transparent;
                        border: none;
                        gridline-color: {AppStyles.BORDER};
                        color: {AppStyles.TEXT_PRIMARY};
                    }}
                    QTableWidget::item {{
                        padding: 6px 8px;
                        border: none;
                        font-size: 10pt;
                    }}
                    QTableWidget::item:selected {{
                        background-color: {AppStyles.PRIMARY}30;
                    }}
                    QHeaderView {{
                        background-color: {AppStyles.BG_DARKEST};
                        border: none;
                    }}
                    QHeaderView::section {{
                        background-color: {AppStyles.BG_DARKEST};
                        color: #FFFFFF;
                        padding: 0 8px;
                        border: none;
                        border-bottom: 2px solid {AppStyles.PRIMARY};
                        font-weight: bold;
                        font-size: 9.5pt;
                        height: 36px;
                    }}
                """)

                for i, invoice in enumerate(recent[:5]):
                    table.setItem(i, 0, QTableWidgetItem(str(invoice.get('invoice_no', ''))))
                    table.setItem(i, 1, QTableWidgetItem(str(invoice.get('invoice_date', ''))))
                    table.setItem(i, 2, QTableWidgetItem(str(invoice.get('customer_name') or '')[:25]))

                    amount = float(invoice.get('grand_total') or 0)
                    amount_item = QTableWidgetItem(f"{amount:,.2f} ₺")
                    inv_type = invoice.get('invoice_type', '')
                    amount_item.setForeground(QColor(AppStyles.GREEN if inv_type == 'Sales' else AppStyles.RED))
                    table.setItem(i, 3, amount_item)

                    status = invoice.get('status', '')
                    status_item = QTableWidgetItem("Onaylı" if status == 'Approved' else "Taslak")
                    status_item.setForeground(QColor(AppStyles.GREEN if status == 'Approved' else AppStyles.ORANGE))
                    table.setItem(i, 4, status_item)

                table.resizeColumnsToContents()
                layout.addWidget(table)
            else:
                no_data = QLabel("📭 Son 7 günde fatura bulunmuyor")
                no_data.setAlignment(Qt.AlignCenter)
                no_data.setStyleSheet(f"""
                    color: {AppStyles.TEXT_MUTED};
                    padding: 20px;
                    font-size: 9pt;
                    background: transparent;
                    border: none;
                """)
                layout.addWidget(no_data)

        except Exception as e:
            logger.error(f"Son faturalar hatası: {e}")

        frame.setLayout(layout)
        return frame

    # ==================== SAĞ KOLON ====================

    def create_right_column(self) -> QWidget:
        """Sağ kolon - Hızlı işlemler ve Şube Göstergeleri"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        quick_actions = self.create_quick_actions()
        layout.addWidget(quick_actions)

        summary_card = self.create_daily_summary_card()
        layout.addWidget(summary_card)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def create_daily_summary_card(self) -> QFrame:
        """Sağ kolon - Şube Hızlı Göstergeleri Kartı"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 8px;
                border: 1px solid {AppStyles.BORDER};
                padding: 10px 12px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 2)
        frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("📌 Şube Durum Göstergeleri")
        title.setStyleSheet(f"""
            font-size: 11pt;
            font-weight: bold;
            color: {AppStyles.TEXT_PRIMARY};
            background: transparent;
            border: none;
            margin-bottom: 2px;
        """)
        layout.addWidget(title)

        # 1. Kritik Stok
        critical_count = 0
        try:
            res = db.fetch_one("""
                SELECT COUNT(*) as cnt FROM Products 
                WHERE branch_id = %s AND is_active = TRUE AND (stock_quantity <= 0 OR stock_quantity <= critical_stock)
            """, (self.branch_id,))
            if res:
                critical_count = res.get('cnt', 0)
        except Exception:
            pass

        # 2. Bekleyen Taslak Fatura
        draft_count = 0
        try:
            res = db.fetch_one("""
                SELECT COUNT(*) as cnt FROM Invoices 
                WHERE branch_id = %s AND status = 'Draft'
            """, (self.branch_id,))
            if res:
                draft_count = res.get('cnt', 0)
        except Exception:
            pass

        # 3. Bugün Gelen Sevkiyat
        today_incoming = 0
        try:
            res = db.fetch_one("""
                SELECT COALESCE(SUM(quantity), 0) as total_qty FROM BranchShipments 
                WHERE target_branch_id = %s AND shipment_date = CURRENT_DATE
            """, (self.branch_id,))
            if res:
                today_incoming = float(res.get('total_qty', 0) or 0)
        except Exception:
            pass

        items = [
            ("📦", "Kritik Stok Uyarısı", f"{critical_count} Ürün", AppStyles.RED if critical_count > 0 else AppStyles.GREEN, "products"),
            ("🚚", "Bugün Gelen Sevkiyat", f"{today_incoming:,.0f} Adet", AppStyles.BLUE if today_incoming > 0 else AppStyles.TEXT_MUTED, "products"),
            ("📝", "Onay Bekleyen Taslak", f"{draft_count} Fatura", AppStyles.PURPLE if draft_count > 0 else AppStyles.TEXT_MUTED, "invoices"),
        ]

        for icon, label_text, val_text, val_color, target_page in items:
            row_btn = QPushButton()
            row_btn.setCursor(Qt.PointingHandCursor)
            row_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.BG_DARK};
                    border: 1px solid {AppStyles.BORDER};
                    border-radius: 6px;
                    padding: 8px 10px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    border-color: {AppStyles.PRIMARY};
                    background-color: {AppStyles.SIDEBAR_HOVER};
                }}
            """)
            if self.main_window:
                row_btn.clicked.connect(lambda ch, p=target_page: self.main_window.navigate_to(p))

            row_layout = QHBoxLayout(row_btn)
            row_layout.setContentsMargins(6, 4, 6, 4)
            row_layout.setSpacing(8)

            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet("background: transparent; border: none; font-size: 11pt;")
            row_layout.addWidget(icon_lbl)

            txt_lbl = QLabel(label_text)
            txt_lbl.setStyleSheet(f"background: transparent; border: none; font-size: 10pt; color: {AppStyles.TEXT_PRIMARY};")
            row_layout.addWidget(txt_lbl)

            row_layout.addStretch()

            badge_lbl = QLabel(val_text)
            badge_lbl.setStyleSheet(f"""
                background: {val_color}25;
                color: {val_color};
                font-weight: bold;
                font-size: 9.5pt;
                padding: 3px 8px;
                border-radius: 4px;
                border: none;
            """)
            row_layout.addWidget(badge_lbl)

            layout.addWidget(row_btn)

        frame.setLayout(layout)
        return frame

    def create_quick_actions(self) -> QFrame:
        """Hızlı işlemler - Kompakt"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 8px;
                border: 1px solid {AppStyles.BORDER};
                padding: 10px 12px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 2)
        frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        layout.setSpacing(6)

        title = QLabel("⚡ Hızlı İşlemler")
        title.setStyleSheet(f"""
            font-size: 11pt;
            font-weight: bold;
            color: {AppStyles.TEXT_PRIMARY};
            background: transparent;
            border: none;
            margin-bottom: 2px;
        """)
        layout.addWidget(title)

        actions = [
            ("📄", "Yeni Fatura", "invoices", AppStyles.PRIMARY),
            ("👥", "Yeni Müşteri", "people", AppStyles.GREEN),
            ("💰", "Para Transferi", "transfers", AppStyles.ORANGE),
            ("📊", "Rapor Al", "reports", AppStyles.PURPLE),
        ]

        for icon, text, page_key, color in actions:
            btn = QPushButton(f"  {icon}   {text}")
            btn.setFixedHeight(34)
            btn.setCursor(Qt.PointingHandCursor)
            if self.main_window:
                btn.clicked.connect(lambda checked, k=page_key: self.main_window.navigate_to(k))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.BG_DARK};
                    color: {AppStyles.TEXT_PRIMARY};
                    border: 1px solid {AppStyles.BORDER};
                    border-radius: 6px;
                    font-size: 10pt;
                    font-weight: 500;
                    text-align: left;
                    padding-left: 10px;
                }}
                QPushButton:hover {{
                    background-color: {color}25;
                    border: 1px solid {color};
                    color: {color};
                }}
            """)
            layout.addWidget(btn)

        frame.setLayout(layout)
        return frame

    # ==================== BİLDİRİMLER (ARKA PLAN TOPLAMA) ====================

    def fetch_notifications(self) -> list:
        """Şube için bildirim ve akıllı hatırlatmaları toplayıp liste olarak döndürür"""
        notifications = []
        try:
            # 1. Stok Uyarıları (Tükenen ve Kritik)
            stock_items = db.fetch_all("""
                SELECT id, name, stock_quantity, critical_stock, unit
                FROM Products
                WHERE branch_id = %s AND is_active = TRUE
                  AND (stock_quantity <= 0 OR stock_quantity <= critical_stock OR stock_quantity <= 5)
                ORDER BY stock_quantity ASC
                LIMIT 5
            """, (self.branch_id,))

            for prod in (stock_items or []):
                p_name = prod.get('name') or 'Ürün'
                qty = float(prod.get('stock_quantity') or 0)
                unit = prod.get('unit') or 'adet'

                def click_prod():
                    if self.main_window:
                        self.main_window.navigate_to("products")

                if qty <= 0:
                    notifications.append({
                        'icon': "🚨",
                        'title': f"Tükenen Ürün / Sipariş Uyarısı: {p_name}",
                        'desc': f"<b>{p_name}</b> ürünü stokta <b>tükenmiştir</b> (Kalan: <b>{qty:g} {unit}</b>)! Acil tedarik gereklidir.",
                        'color': AppStyles.RED,
                        'on_click': click_prod
                    })
                else:
                    notifications.append({
                        'icon': "⚠️",
                        'title': f"Kritik Stok Uyarısı: {p_name}",
                        'desc': f"<b>{p_name}</b> ürününün stoğu kritik seviyede (Kalan: <b>{qty:g} {unit}</b>).",
                        'color': AppStyles.WARNING,
                        'on_click': click_prod
                    })

            # 2. Onay Bekleyen Taslak Faturalar
            draft_items = db.fetch_all("""
                SELECT id, invoice_no, grand_total
                FROM Invoices
                WHERE branch_id = %s AND status = 'Draft'
                ORDER BY created_at DESC
                LIMIT 3
            """, (self.branch_id,))

            for draft in (draft_items or []):
                inv_no = draft.get('invoice_no') or '-'
                tot = float(draft.get('grand_total') or 0)

                def click_draft():
                    if self.main_window:
                        self.main_window.navigate_to("invoices")

                notifications.append({
                    'icon': "📝",
                    'title': "Onay Bekleyen Taslak Fatura",
                    'desc': f"<b>{inv_no}</b> numaralı <b>{tot:,.2f} ₺</b> tutarındaki fatura henüz onaylanmadı.",
                    'color': AppStyles.PURPLE,
                    'on_click': click_draft
                })

            # 3. Günü Geçmiş Fatura Ödemeleri
            old_cutoff = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
            overdue_items = db.fetch_all("""
                SELECT i.invoice_no, i.invoice_date, i.remaining_amount, c.title as customer_name
                FROM Invoices i
                LEFT JOIN Customers c ON i.customer_id = c.id
                WHERE i.branch_id = %s AND i.payment_status != 'Paid' AND (i.status IS NULL OR i.status != 'Cancelled')
                  AND i.invoice_date <= %s
                ORDER BY i.invoice_date ASC
                LIMIT 4
            """, (self.branch_id, old_cutoff))

            for item in (overdue_items or []):
                cust = item.get('customer_name') or 'Müşteri'
                inv_no = item.get('invoice_no') or '-'
                amount = float(item.get('remaining_amount') or 0)

                def click_overdue():
                    if self.main_window:
                        self.main_window.navigate_to("invoices")

                notifications.append({
                    'icon': "🔴",
                    'title': "Gecikmiş Fatura Ödeme Uyarısı",
                    'desc': f"<b>{cust}</b> firmasına ait <b>{inv_no}</b> nolu faturanın <b>{amount:,.2f} ₺</b> ödemesi gecikmiştir.",
                    'color': AppStyles.RED,
                    'on_click': click_overdue
                })

            # 4. Şube Yaklaşan Ödeme Planları & Personel Maaşları
            try:
                upcoming = payment_plan_service.get_upcoming_payments(branch_id=self.branch_id, days=7)
                for p in (upcoming or [])[:5]:
                    p_title = p.get('title') or 'Ödeme'
                    p_payee = p.get('payee_name') or '-'
                    p_amount = float(p.get('amount') or 0)
                    days_left = p.get('days_left', 0)
                    p_type = p.get('plan_type')
                    is_salary = (p_type == 'personel')

                    def click_plan():
                        if self.main_window:
                            self.main_window.navigate_to("payment_plans")

                    notifications.append({
                        'icon': "👤" if is_salary else "⏰",
                        'title': f"Yaklaşan Personel Maaşı — {p_payee}" if is_salary else "Yaklaşan Ödeme Planı Taksiti",
                        'desc': f"<b>{p_title}</b> ({p_payee}) ödemesine <b>{days_left} gün</b> kaldı! Tutar: <b>{p_amount:,.2f} ₺</b>",
                        'color': AppStyles.PRIMARY if is_salary else AppStyles.ORANGE,
                        'on_click': click_plan
                    })
            except Exception as e:
                logger.error(f"Yaklaşan ödeme bildirim hatası: {e}")

            # 5. Gecikmiş Ödeme Planları & Personel Maaşları
            try:
                overdue = payment_plan_service.get_overdue_payments(branch_id=self.branch_id)
                for p in (overdue or [])[:4]:
                    p_title = p.get('title') or 'Ödeme'
                    p_payee = p.get('payee_name') or '-'
                    p_amount = float(p.get('amount') or 0)
                    p_type = p.get('plan_type')
                    days_overdue = int(p.get('days_overdue', 0) or 0)
                    is_salary = (p_type == 'personel')

                    def click_overdue_plan():
                        if self.main_window:
                            self.main_window.navigate_to("payment_plans")

                    notifications.append({
                        'icon': "🚨" if is_salary else "🔴",
                        'title': f"GECİKMİŞ PERSONEL MAAŞI — {p_payee}" if is_salary else f"Gecikmiş Ödeme — {p_title}",
                        'desc': f"<b>{p_title}</b> ({p_payee}) ödemesi <b>{days_overdue} gün</b> gecikmiştir! Tutar: <b>{p_amount:,.2f} ₺</b>",
                        'color': AppStyles.RED,
                        'on_click': click_overdue_plan
                    })
            except Exception as e:
                logger.error(f"Gecikmiş ödeme bildirim hatası: {e}")

            # 6. Açık Personel Avansları
            try:
                open_advances = db.fetch_all("""
                    SELECT el.id, el.amount, el.remaining_amount, e.full_name AS employee_name
                    FROM EmployeeLedger el
                    JOIN Employees e ON e.id = el.employee_id
                    WHERE e.branch_id = %s AND el.entry_type = 'avans' 
                      AND el.remaining_amount > 0 AND (el.is_closed = 0 OR el.is_closed IS NULL)
                    ORDER BY el.entry_date DESC
                    LIMIT 3
                """, (self.branch_id,))
                for adv in (open_advances or []):
                    emp_name = adv.get('employee_name') or 'Personel'
                    rem = float(adv.get('remaining_amount') or 0)

                    def click_adv():
                        if self.main_window:
                            self.main_window.navigate_to("payment_plans")

                    notifications.append({
                        'icon': "💸",
                        'title': f"Açık Personel Avansı — {emp_name}",
                        'desc': f"<b>{emp_name}</b> üzerinde <b>{rem:,.2f} ₺</b> açık avans bakiyesi bulunmaktadır.",
                        'color': AppStyles.PURPLE,
                        'on_click': click_adv
                    })
            except Exception as e:
                logger.error(f"Açık avans bildirim hatası: {e}")

            # 7. Maaş Günü Yaklaşan Personeller (salary_day)
            try:
                today = datetime.now().date()
                employees = db.fetch_all("""
                    SELECT id, full_name, monthly_salary, salary_day
                    FROM Employees
                    WHERE branch_id = %s AND is_active = TRUE AND salary_day IS NOT NULL
                """, (self.branch_id,))
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
                            if self.main_window:
                                self.main_window.navigate_to("payment_plans")

                        notifications.append({
                            'icon': "📅",
                            'title': f"Maaş Günü Yaklaşıyor — {emp_name}",
                            'desc': f"<b>{emp_name}</b> personelinin maaş gününe <b>{days_diff} gün</b> kaldı. (Aylık: <b>{sal_amount:,.2f} ₺</b>)",
                            'color': AppStyles.CYAN,
                            'on_click': click_sal_emp
                        })
            except Exception as e:
                logger.error(f"Maaş günü bildirim hatası: {e}")

        except Exception as e:
            logger.error(f"Şube bildirimleri toplama hatası: {e}")

        return notifications

    def open_notifications_dialog(self):
        """Bildirimler & Hatırlatmalar modalını açar"""
        try:
            self.notifications = self.fetch_notifications()
            dlg = NotificationsDialog(self.notifications, self)
            dlg.exec_()
            cnt = len(self.notifications)
            self.notif_btn.setText(f"🔔  {cnt} Bildirim" if cnt > 0 else "🔔  Bildirimler")
        except Exception as e:
            logger.error(f"Bildirim penceresi açılırken hata: {e}")

    # ==================== VERİ YÜKLEME & YENİLEME ====================

    def load_data(self):
        """Verileri yükle"""
        try:
            logger.info(f"📊 Dashboard yüklendi - Şube: {self.branch_id}")
        except Exception as e:
            logger.error(f"Veri yükleme hatası: {e}")

    def refresh(self):
        """Sayfayı yenile — tüm içeriği yeniden oluştur"""
        try:
            logger.info("🔄 Dashboard yenileniyor...")

            # Mevcut layout'u temizle
            current_layout = self.layout()
            if current_layout is not None:
                while current_layout.count():
                    item = current_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                    elif item.layout():
                        self._clear_layout(item.layout())

            # Yeni layout oluştur
            self.init_ui()
            self.load_data()

            # Saat timer'ı yeniden başlat
            self._update_clock()

            logger.info("✅ Dashboard yenilendi")
        except Exception as e:
            logger.error(f"Yenileme hatası: {e}")

    def _clear_layout(self, layout):
        """Layout'u temizle"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())