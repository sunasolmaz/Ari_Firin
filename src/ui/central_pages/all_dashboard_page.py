# src/ui/central_pages/all_dashboard_page.py
"""
Genel Merkez Ana Panel - Tüm Şubelerin Genel Durumu
Toplu cari hesap özetleri, bildirimler & hatırlatmalar, istatistikler, şube performansları ve son faturalar
+ Ödeme planları ve personel avansı bildirimleri
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
    QGraphicsDropShadowEffect, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox
)
from PyQt5.QtCore import Qt, QDate, QTimer
from PyQt5.QtGui import QColor
from datetime import datetime, timedelta

from ...models.user import User
from ...models.branch import Branch
from ...core.database import db
from ...core.logger import logger
from ...services.turnover_service import turnover_service
from ...services.warehouse_service import warehouse_service
from ...services.payment_plan_service import payment_plan_service
from ...services.stock_count_service import stock_count_service
from ..styles import AppStyles
from ..notifications_dialog import NotificationsDialog


class AllDashboardPage(QWidget):
    """Genel Merkez Ana Panel Sayfası - tüm şubelerin toplu verisi ve bildirim alanı"""

    def __init__(self, user: User, central_window=None):
        super().__init__()
        self.user = user
        self.central_window = central_window
        self._branch_perf_sort_mode = 'total_sales'
        self.cached_branches = []

        # ✅ Canlı saat için referans
        self._clock_label = None
        self._clock_timer = None

        self.init_ui()

        # ✅ Saat timer'ı başlat
        self._start_clock_timer()

    def init_ui(self):
        """Arayüzü oluştur"""
        self.setObjectName("AllDashboardPage")
        self.setStyleSheet(f"#AllDashboardPage {{ background-color: {AppStyles.BG_DARK}; }}")

        # ✅ Eski layout varsa önce temizle
        existing_layout = self.layout()
        if existing_layout is not None:
            self._clear_layout(existing_layout)

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

        # ==================== İSTATİSTİK KARTLARI ====================
        stats_layout = self.create_stats_cards()
        layout.addLayout(stats_layout)

        # ==================== 3 ŞUBE GÜNLÜK VE TOPLAM CİRO VİTRİNİ ====================
        turnover_section = self.create_three_branches_turnover_section()
        layout.addWidget(turnover_section)

        # ==================== ORTA BÖLÜM ====================
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(12)

        recent_invoices = self.create_recent_invoices()
        middle_layout.addWidget(recent_invoices, 5)

        branch_performance = self.create_branch_performance()
        branch_performance.setMinimumWidth(380)
        middle_layout.addWidget(branch_performance, 4)

        layout.addLayout(middle_layout)
        layout.addStretch()

        content.setLayout(layout)
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # ✅ Ana layout'u widget'a ata
        self.setLayout(main_layout)

    # ==================== LAYOUT TEMİZLEME ====================

    def _clear_layout(self, layout):
        """Layout'u ve içindeki tüm widget'ları güvenli şekilde temizle"""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            else:
                child_layout = item.layout()
                if child_layout is not None:
                    self._clear_layout(child_layout)

    # ==================== CANLI SAAT ====================

    def _start_clock_timer(self):
        """Saat güncelleme timer'ını başlat"""
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
        """Sayfa gizlendiğinde timer'ı durdur"""
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
        left.setSpacing(1)

        title = QLabel("📊 Genel Merkez Paneli")
        title.setStyleSheet(f"""
            font-size: 14pt;
            font-weight: bold;
            color: {AppStyles.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)
        left.addWidget(title)

        subtitle = QLabel(f"🏢 Tüm Şubelerin Konsolide Durumu • 📅 {datetime.now().strftime('%d %B %Y, %A')}")
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
        refresh_btn.clicked.connect(self.load_data)
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
        """6 konsolide istatistik kartı - 2x3 Izgara (Gelir/Gider/Fire ve Alacak/Borç/Net Bakiye)"""
        layout = QGridLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)

        try:
            # 1. Aylık Ciro ve Gider
            now_dt = datetime.now().date()
            turnover_month = turnover_service.get_monthly_summary(0, now_dt.year, now_dt.month)
            sales = float(turnover_month.get('total_income') or 0.0)
            purchases = float(turnover_month.get('total_expense') or 0.0)

            # 2. Cari Alacak, Borç ve Net Bakiye
            from ...services.customer_service import CustomerService
            cs = CustomerService()
            summary = cs.get_companies_balance_summary()
            receivables = float(summary.get('total_receivables', 0.0))
            payables = float(summary.get('total_payables', 0.0))
            net_balance = float(summary.get('net_balance', receivables - payables))

            if net_balance > 0:
                net_display = f"+{net_balance:,.2f} ₺"
                net_color = AppStyles.GREEN
                net_trend = "↗"
                net_sub = "Net Alacak Fazlası"
            elif net_balance < 0:
                net_display = f"{net_balance:,.2f} ₺"
                net_color = AppStyles.RED
                net_trend = "↘"
                net_sub = "Net Borç Durumu"
            else:
                net_display = "0,00 ₺"
                net_color = AppStyles.TEXT_SECONDARY
                net_trend = "⚖️"
                net_sub = "Alacak/Borç Dengede"

            # 3. Haftalık Konsolide Fire Durumu
            weekly_waste = stock_count_service.get_weekly_consolidated_waste()
            self._cached_weekly_waste = weekly_waste
            waste_val = float(weekly_waste.get('total_waste_value', 0.0))
            waste_qty = float(weekly_waste.get('total_waste_qty', 0.0))
            waste_ratio = float(weekly_waste.get('waste_ratio', 0.0))

            if waste_val > 0 or waste_qty > 0:
                waste_sub = f"{waste_qty:,.1f} Adet • Cironun %{waste_ratio:.1f}'i"
                waste_color = AppStyles.DANGER
                waste_trend = "🔥"
            else:
                waste_sub = "Bu Hafta Fire Kaydı Yok"
                waste_color = AppStyles.TEXT_SECONDARY
                waste_trend = "✨"

            # 2x3 Izgara kartları: (row, col, icon, title, value, color, trend, sub_info, on_click)
            cards_data = [
                # Satır 0: Akışlar (Ciro, Gider, Fire Kaybı)
                (0, 0, "💰", "Aylık Toplam Ciro", f"{sales:,.2f} ₺", AppStyles.GREEN, "↗", "Konsolide Satışlar",
                 lambda: self.central_window.navigate_to("all_reports") if self.central_window else None),
                (0, 1, "💸", "Aylık Toplam Gider", f"{purchases:,.2f} ₺", AppStyles.RED, "↘", "Konsolide Alışlar",
                 lambda: self.central_window.navigate_to("all_reports") if self.central_window else None),
                (0, 2, "🔥", "Haftalık Toplam Fire", f"{waste_val:,.2f} ₺", waste_color, waste_trend, waste_sub,
                 lambda: self.central_window.navigate_to("all_reports") if self.central_window else None),

                # Satır 1: Bilanço / Bakiyeler (Alacak, Borç, Net Bakiye)
                (1, 0, "📈", "Toplam Cari Alacak", f"{receivables:,.2f} ₺", AppStyles.CYAN, "👤", "Müşteri Faturaları",
                 lambda: self.central_window.navigate_to("all_customers") if self.central_window else None),
                (1, 1, "📉", "Toplam Cari Borç", f"{payables:,.2f} ₺", AppStyles.ORANGE, "⚠️", "Tedarikçi Faturaları",
                 lambda: self.central_window.navigate_to("all_customers") if self.central_window else None),
                (1, 2, "⚖️", "Net Cari / Fatura Bakiye", net_display, net_color, net_trend, net_sub,
                 lambda: self.central_window.navigate_to("all_customers") if self.central_window else None),
            ]

            for r, c, icon, title, value, color, trend, sub_info, click_action in cards_data:
                card = self.create_stat_card(icon, title, value, color, trend, sub_info, on_click=click_action)
                layout.addWidget(card, r, c)
        except Exception as e:
            logger.error(f"Genel merkez istatistik hatası: {e}")

        return layout

    # ==================== 4 ŞUBE CİRO TAKİP VİTRİNİ ====================

    def create_three_branches_turnover_section(self) -> QFrame:
        """4 Şubenin (3 Şube + 1 İmalathane) Günlük ve Kümülatif Ciro Vitrini - 2'li Gruplar (Sol 2, Sağ 2)"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
                padding: 10px 14px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 70))
        shadow.setOffset(0, 3)
        frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        layout.setSpacing(10)

        header = QHBoxLayout()
        left_head = QVBoxLayout()
        left_head.setSpacing(2)

        title = QLabel("🪙 Şubeler Günlük & Kümülatif Ciro Durumu")
        title.setStyleSheet(f"font-size: 11.5pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; background: transparent; border: none;")
        left_head.addWidget(title)

        today_str = datetime.now().strftime('%d.%m.%Y')
        subtitle = QLabel(f"📅 Bugün ({today_str}) ve tüm zamanların kümülatif takibi")
        subtitle.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_SECONDARY}; background: transparent; border: none;")
        left_head.addWidget(subtitle)
        header.addLayout(left_head)

        header.addStretch()

        summary_data = turnover_service.get_three_branches_summary()
        grand_cum = summary_data.get('grand_cumulative_income', 0.0)
        grand_daily = summary_data.get('total_daily_income', 0.0)

        # Haftalık konsolide fire verileri
        weekly_waste = getattr(self, '_cached_weekly_waste', None) or stock_count_service.get_weekly_consolidated_waste()
        tot_waste_val = weekly_waste.get('total_waste_value', 0.0)
        tot_waste_qty = weekly_waste.get('total_waste_qty', 0.0)
        branch_waste_map = weekly_waste.get('branch_breakdown', {})

        daily_badge = QLabel(f"📅 Bugün Toplam: {grand_daily:,.2f} ₺")
        daily_badge.setStyleSheet(f"""
            font-size: 8.5pt;
            font-weight: bold;
            color: {AppStyles.GREEN};
            background-color: {AppStyles.BG_DARK};
            border: 1px solid {AppStyles.GREEN}40;
            border-radius: 6px;
            padding: 4px 10px;
        """)
        header.addWidget(daily_badge)

        header.addSpacing(6)

        waste_badge = QLabel(f"🔥 Bu Hafta Fire: {tot_waste_val:,.2f} ₺")
        waste_badge.setStyleSheet(f"""
            font-size: 8.5pt;
            font-weight: bold;
            color: {AppStyles.DANGER};
            background-color: {AppStyles.BG_DARK};
            border: 1px solid {AppStyles.DANGER}60;
            border-radius: 6px;
            padding: 4px 10px;
        """)
        waste_badge.setToolTip(f"Tüm şubeler haftalık toplam fire: {tot_waste_val:,.2f} ₺ ({tot_waste_qty:,.1f} Adet/Kg)")
        header.addWidget(waste_badge)

        header.addSpacing(6)

        total_badge = QLabel(f"🏆 Toplam Kümülatif: {grand_cum:,.2f} ₺")
        total_badge.setStyleSheet(f"""
            font-size: 9pt;
            font-weight: bold;
            color: white;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.PURPLE});
            border-radius: 6px;
            padding: 4px 12px;
            border: none;
        """)
        header.addWidget(total_badge)
        layout.addLayout(header)

        # Şubeler için meta eşleme (Armada, Çobançeşme, Rumeli, Orion, İmalathane)
        def _get_branch_meta(b_name: str, idx: int):
            nl = b_name.lower()
            if "armada" in nl:
                return "🥖 Armada Şubesi", AppStyles.PRIMARY
            elif "çoban" in nl or "coban" in nl:
                return "🥐 Çobançeşme Şubesi", AppStyles.CYAN
            elif "rumeli" in nl:
                return "🥨 Rumeli Şubesi", AppStyles.PURPLE
            elif "orion" in nl:
                return "🧁 Orion Şubesi", AppStyles.YELLOW
            elif "imalat" in nl:
                return "🏭 İmalathane", AppStyles.ORANGE
            else:
                palette = [AppStyles.PRIMARY, AppStyles.CYAN, AppStyles.PURPLE, AppStyles.YELLOW, AppStyles.ORANGE]
                return f"🏢 {b_name}", palette[idx % len(palette)]

        # 2'li gruplar: Sol tarafta 2 tanesi (col 0), sağ tarafta 2 tanesi (col 1)
        cards_grid = QGridLayout()
        cards_grid.setSpacing(10)
        cards_grid.setColumnStretch(0, 1)
        cards_grid.setColumnStretch(1, 1)

        branches = summary_data.get('branches', [])
        half = (len(branches) + 1) // 2

        for i, b in enumerate(branches):
            b_name = b.get('branch_name', f'Şube {i+1}')
            display_title, accent_color = _get_branch_meta(b_name, i)

            b_daily_inc = b.get('daily_income', 0.0)
            b_daily_exp = b.get('daily_expense', 0.0)
            b_daily_net = b.get('daily_net', 0.0)
            b_cum_inc = b.get('cumulative_income', 0.0)

            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {AppStyles.BG_DARK};
                    border-radius: 8px;
                    border: 1px solid {AppStyles.BORDER};
                    border-top: 3px solid {accent_color};
                    padding: 8px 12px;
                }}
                QFrame:hover {{
                    border-color: {accent_color};
                }}
                QFrame QLabel {{
                    background: transparent;
                    border: none;
                }}
            """)
            c_lay = QVBoxLayout()
            c_lay.setSpacing(5)

            name_lbl = QLabel(display_title)
            name_lbl.setStyleSheet(f"font-size: 10.5pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; min-height: 24px; padding: 1px 0;")
            c_lay.addWidget(name_lbl)

            grid = QGridLayout()
            grid.setSpacing(4)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(3, 1)

            lbl_today = QLabel("📅 Bugün:")
            lbl_today.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9.5pt;")
            grid.addWidget(lbl_today, 0, 0)

            daily_lbl = QLabel(f"{b_daily_inc:,.2f} ₺")
            daily_lbl.setStyleSheet(f"font-weight: bold; color: {AppStyles.GREEN}; font-size: 10pt;")
            daily_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(daily_lbl, 0, 1)

            lbl_net = QLabel("⚖️ Net:")
            lbl_net.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9.5pt;")
            grid.addWidget(lbl_net, 0, 2)

            net_lbl = QLabel(f"{b_daily_net:,.2f} ₺")
            net_lbl.setStyleSheet(f"font-weight: bold; color: {AppStyles.CYAN if b_daily_net >= 0 else AppStyles.RED}; font-size: 10pt;")
            net_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(net_lbl, 0, 3)

            lbl_exp = QLabel("📉 Gider:")
            lbl_exp.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9.5pt;")
            grid.addWidget(lbl_exp, 1, 0)

            exp_lbl = QLabel(f"{b_daily_exp:,.2f} ₺")
            exp_lbl.setStyleSheet(f"font-weight: bold; color: {AppStyles.RED}; font-size: 10pt;")
            exp_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(exp_lbl, 1, 1)

            lbl_cum = QLabel("🏆 Kümülatif:")
            lbl_cum.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9.5pt;")
            grid.addWidget(lbl_cum, 1, 2)

            cum_val = QLabel(f"{b_cum_inc:,.2f} ₺")
            cum_val.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {accent_color};")
            cum_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(cum_val, 1, 3)

            # Satır 2: Şubenin Bu Haftaki Fire Durumu
            bid = b.get('branch_id', 0)
            b_w = branch_waste_map.get(bid, {'waste_value': 0.0, 'waste_qty': 0.0})
            b_w_val = float(b_w.get('waste_value', 0.0))
            b_w_qty = float(b_w.get('waste_qty', 0.0))

            lbl_w = QLabel("🔥 Haftalık Fire:")
            lbl_w.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9pt;")
            grid.addWidget(lbl_w, 2, 0)

            w_val_lbl = QLabel(f"{b_w_val:,.2f} ₺")
            w_val_lbl.setStyleSheet(f"font-weight: bold; color: {AppStyles.DANGER if b_w_val > 0 else AppStyles.TEXT_MUTED}; font-size: 9.5pt;")
            w_val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(w_val_lbl, 2, 1)

            lbl_w_qty = QLabel("📦 Miktar:")
            lbl_w_qty.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9pt;")
            grid.addWidget(lbl_w_qty, 2, 2)

            w_qty_lbl = QLabel(f"{b_w_qty:,.1f} Adet")
            w_qty_lbl.setStyleSheet(f"font-weight: bold; color: {AppStyles.TEXT_PRIMARY if b_w_qty > 0 else AppStyles.TEXT_MUTED}; font-size: 9.5pt;")
            w_qty_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(w_qty_lbl, 2, 3)

            c_lay.addLayout(grid)
            card.setLayout(c_lay)

            # Sol tarafta 2 tanesi (col 0), sağ tarafta 2 tanesi (col 1)
            if i < half:
                cards_grid.addWidget(card, i, 0)
            else:
                cards_grid.addWidget(card, i - half, 1)

        layout.addLayout(cards_grid)
        frame.setLayout(layout)
        return frame

    def create_stat_card(self, icon: str, title: str, value: str, color: str, trend: str, sub_info: str = "", on_click=None) -> QFrame:
        """Kompakt ve okunaklı istatistik kartı"""
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
            QFrame#statCard:hover {{
                border-color: {color};
            }}
            QFrame#statCard QLabel {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
        """)
        if on_click:
            card.setCursor(Qt.PointingHandCursor)
            card.mousePressEvent = lambda e: on_click()

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 2)
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(12, 8, 12, 8)

        # Üst Satır: İkon + Başlık + Trend İkonu
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

        # Alt Satır: Değer + Sub info
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)

        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(f"""
            font-size: 15pt;
            font-weight: bold;
            color: {color};
        """)
        bottom_layout.addWidget(value_lbl)

        bottom_layout.addStretch()

        if sub_info:
            sub_lbl = QLabel(sub_info)
            sub_lbl.setStyleSheet(f"""
                font-size: 9.5pt;
                color: {AppStyles.TEXT_SECONDARY};
            """)
            bottom_layout.addWidget(sub_lbl)

        layout.addLayout(bottom_layout)

        card.setLayout(layout)
        return card

    # ==================== BİLDİRİMLER (ARKA PLAN TOPLAMA) ====================

    def fetch_notifications(self) -> list:
        """Tüm şubeler için bildirim ve akıllı hatırlatmaları toplayıp liste olarak döndürür"""
        notifications = []

        try:
            # 1. Yaklaşan Ödemeler (7 Gün)
            try:
                upcoming = payment_plan_service.get_upcoming_payments(days=7)
                for p in (upcoming or [])[:5]:
                    plan_id = p.get('id')
                    p_title = p.get('title') or 'Ödeme'
                    p_payee = p.get('payee_name') or '-'
                    p_amount = float(p.get('amount') or 0)
                    p_due = str(p.get('due_date') or '')
                    p_branch = p.get('branch_name') or 'Genel'
                    days_left = p.get('days_left', 0) or 0
                    p_type = p.get('plan_type')
                    is_salary = (p_type == 'personel')
                    try:
                        days_left = int(days_left)
                    except Exception:
                        days_left = 0

                    def click_payment(pid=plan_id):
                        if self.central_window:
                            self.central_window.navigate_to("payment_plans")

                    notifications.append({
                        'icon': "👤" if is_salary else "⏰",
                        'title': f"Yaklaşan Personel Maaşı — {p_payee} ({p_branch})" if is_salary else f"Yaklaşan Ödeme — {p_branch}",
                        'desc': f"<b>{p_title}</b> ({p_payee}) ödemesi <b>{days_left} gün</b> içinde! Tutar: <b>{p_amount:,.2f} ₺</b> (Vade: {p_due})",
                        'color': AppStyles.PRIMARY if is_salary else AppStyles.ORANGE,
                        'on_click': click_payment
                    })
            except Exception as e:
                logger.error(f"Yaklaşan ödeme bildirim hatası: {e}")

            # 2. Gecikmiş Ödemeler
            try:
                overdue = payment_plan_service.get_overdue_payments()
                for p in (overdue or [])[:5]:
                    plan_id = p.get('id')
                    p_title = p.get('title') or 'Ödeme'
                    p_payee = p.get('payee_name') or '-'
                    p_amount = float(p.get('amount') or 0)
                    p_due = str(p.get('due_date') or '')
                    p_branch = p.get('branch_name') or 'Genel'
                    days_overdue = p.get('days_overdue', 0) or 0
                    p_type = p.get('plan_type')
                    is_salary = (p_type == 'personel')
                    try:
                        days_overdue = int(days_overdue)
                    except Exception:
                        days_overdue = 0

                    def click_overdue_payment(pid=plan_id):
                        if self.central_window:
                            self.central_window.navigate_to("payment_plans")

                    notifications.append({
                        'icon': "🚨" if is_salary else "🔴",
                        'title': f"GECİKMİŞ PERSONEL MAAŞI — {p_payee} ({p_branch})" if is_salary else f"GECİKMİŞ ÖDEME — {p_branch}",
                        'desc': f"<b>{p_title}</b> ({p_payee}) ödemesi <b>{days_overdue} gün</b> gecikmiş! Tutar: <b>{p_amount:,.2f} ₺</b> (Vade: {p_due})",
                        'color': AppStyles.RED,
                        'on_click': click_overdue_payment
                    })
            except Exception as e:
                logger.error(f"Gecikmiş ödeme bildirim hatası: {e}")

            # 3. Açık Personel Avansları
            try:
                open_advances = db.fetch_all("""
                    SELECT el.id, el.amount, el.remaining_amount, e.full_name AS employee_name
                    FROM EmployeeLedger el
                    JOIN Employees e ON e.id = el.employee_id
                    WHERE el.entry_type = 'avans' AND el.remaining_amount > 0 AND (el.is_closed = 0 OR el.is_closed IS NULL)
                    ORDER BY el.entry_date DESC
                    LIMIT 3
                """)
                for adv in (open_advances or []):
                    emp_name = adv.get('employee_name') or 'Personel'
                    rem = float(adv.get('remaining_amount') or 0)

                    def click_adv():
                        if self.central_window:
                            self.central_window.navigate_to("payment_plans")

                    notifications.append({
                        'icon': "💸",
                        'title': "Açık Personel Avansı",
                        'desc': f"<b>{emp_name}</b> üzerinde <b>{rem:,.2f} ₺</b> açık avans bakiyesi bulunmaktadır.",
                        'color': AppStyles.PURPLE,
                        'on_click': click_adv
                    })
            except Exception as adv_err:
                logger.error(f"Avans bildirim hatası: {adv_err}")

            # 4. Merkez Depo Kritik Stok
            try:
                wh_critical = db.fetch_all("""
                    SELECT name, product_code, stock_quantity, critical_stock, unit
                    FROM WarehouseProducts
                    WHERE is_active = TRUE
                      AND (stock_quantity <= critical_stock OR stock_quantity <= 10)
                    ORDER BY stock_quantity ASC
                    LIMIT 3
                """)
                for wp in (wh_critical or []):
                    wp_name = wp.get('name') or 'Ürün'
                    wp_code = wp.get('product_code') or '-'
                    wp_qty = float(wp.get('stock_quantity') or 0)
                    wp_unit = wp.get('unit') or 'adet'
                    wp_crit = float(wp.get('critical_stock') or 10)

                    def click_wh():
                        if self.central_window:
                            self.central_window.navigate_to("warehouse")

                    notifications.append({
                        'icon': "⚠️",
                        'title': "Merkez Depo: Kritik Stok Uyarısı",
                        'desc': f"<b>{wp_name}</b> ({wp_code}) merkez depoda kritik seviyede! Kalan: <b>{wp_qty:g} {wp_unit}</b> (Kritik Eşik: {wp_crit:g} {wp_unit}).",
                        'color': AppStyles.WARNING,
                        'on_click': click_wh
                    })
            except Exception as wh_err:
                logger.error(f"Depo kritik stok bildirim hatası: {wh_err}")

            # 5. Günü Geçmiş Fatura Ödemeleri
            old_cutoff = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
            overdue_items = db.fetch_all("""
                SELECT i.invoice_no, i.invoice_date, i.remaining_amount, i.branch_id, c.title as customer_name, b.name as branch_name
                FROM Invoices i
                LEFT JOIN Customers c ON i.customer_id = c.id
                LEFT JOIN Branches b ON i.branch_id = b.id
                WHERE i.payment_status != 'Paid' AND (i.status IS NULL OR i.status != 'Cancelled')
                  AND i.invoice_date <= %s
                ORDER BY i.invoice_date ASC
                LIMIT 3
            """, (old_cutoff,))

            for item in (overdue_items or []):
                branch = item.get('branch_name') or 'Genel'
                cust = item.get('customer_name') or 'Müşteri'
                inv_no = item.get('invoice_no') or '-'
                amount = float(item.get('remaining_amount', 0))
                inv_date = str(item.get('invoice_date', ''))
                b_id = item.get('branch_id')

                def click_overdue(b_id=b_id):
                    if self.central_window:
                        self.central_window.navigate_to("all_invoices")

                notifications.append({
                    'icon': "🔴",
                    'title': f"Günü Geçmiş Fatura — {branch}",
                    'desc': f"<b>{cust}</b> firmasına ait <b>{inv_no}</b> nolu faturanın <b>{amount:,.2f} ₺</b> tutarındaki ödemesi gecikmiş! (Tarih: {inv_date})",
                    'color': AppStyles.RED,
                    'on_click': click_overdue
                })

            # 6. Kritik Şube Stokları
            stock_issues = db.fetch_all("""
                SELECT p.name as product_name, p.stock_quantity, p.critical_stock, p.unit, b.name as branch_name
                FROM Products p
                LEFT JOIN Branches b ON p.branch_id = b.id
                WHERE p.is_active = TRUE AND (p.stock_quantity <= 0 OR p.stock_quantity <= p.critical_stock)
                ORDER BY p.stock_quantity ASC
                LIMIT 3
            """)
            for p in (stock_issues or []):
                b_name = p.get('branch_name') or 'Şube'
                p_name = p.get('product_name') or 'Ürün'
                qty = float(p.get('stock_quantity', 0))
                unit = p.get('unit') or 'adet'

                def click_prod():
                    if self.central_window:
                        self.central_window.navigate_to("all_products")

                notifications.append({
                    'icon': "🚨" if qty <= 0 else "⚠️",
                    'title': f"Şube Kritik Stok: {p_name} — {b_name}",
                    'desc': f"<b>{b_name}</b> şubesinde <b>{p_name}</b> stoğu kritik seviyede! (Kalan: <b>{qty:g} {unit}</b>)",
                    'color': AppStyles.RED if qty <= 0 else AppStyles.WARNING,
                    'on_click': click_prod
                })

            # 7. Maaş Günü Yaklaşan Personeller (Tüm Şubeler)
            try:
                today = datetime.now().date()
                employees = db.fetch_all("""
                    SELECT e.id, e.full_name, e.monthly_salary, e.salary_day, b.name as branch_name
                    FROM Employees e
                    LEFT JOIN Branches b ON e.branch_id = b.id
                    WHERE e.is_active = TRUE AND e.salary_day IS NOT NULL
                """)
                for emp in (employees or []):
                    sal_day = int(emp.get('salary_day') or 1)
                    sal_amount = float(emp.get('monthly_salary') or 0)
                    emp_name = emp.get('full_name') or 'Personel'
                    branch_name = emp.get('branch_name') or 'Şube'
                    try:
                        sal_date = today.replace(day=sal_day)
                    except Exception:
                        sal_date = today.replace(day=28)
                    days_diff = (sal_date - today).days
                    if 0 <= days_diff <= 3:
                        def click_sal_emp():
                            if self.central_window:
                                self.central_window.navigate_to("payment_plans")

                        notifications.append({
                            'icon': "📅",
                            'title': f"Maaş Günü Yaklaşıyor — {emp_name} ({branch_name})",
                            'desc': f"<b>{emp_name}</b> ({branch_name}) için aylık maaş ödeme günü ({sal_day}. gün). Tutar: <b>{sal_amount:,.2f} ₺</b> ({days_diff} gün kaldı).",
                            'color': AppStyles.PRIMARY,
                            'on_click': click_sal_emp
                        })
            except Exception as e:
                logger.error(f"Genel merkez personel maaş günü bildirim hatası: {e}")

        except Exception as e:
            logger.error(f"Bildirim toplama hatası: {e}")

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

    # ==================== SON FATURALAR ====================

    def create_recent_invoices(self) -> QFrame:
        """Tüm Şubeler - Son Faturalar"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
                padding: 12px 14px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 70))
        shadow.setOffset(0, 3)
        frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        layout.setSpacing(8)

        header = QHBoxLayout()

        title = QLabel("📋 Tüm Şubeler - Son Faturalar")
        title.setStyleSheet(f"""
            font-size: 11pt;
            font-weight: bold;
            color: {AppStyles.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)
        header.addWidget(title)

        header.addStretch()

        view_all_btn = QPushButton("Tüm Faturaları Gör →")
        view_all_btn.setCursor(Qt.PointingHandCursor)
        if self.central_window:
            view_all_btn.clicked.connect(lambda: self.central_window.navigate_to("all_invoices"))
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
            recent = db.fetch_all("""
                SELECT i.invoice_no, i.invoice_date, c.title as customer_name, b.name as branch_name, 
                       i.grand_total, i.payment_status
                FROM Invoices i
                LEFT JOIN Customers c ON i.customer_id = c.id
                LEFT JOIN Branches b ON i.branch_id = b.id
                WHERE (i.status IS NULL OR i.status != 'Cancelled')
                ORDER BY i.created_at DESC, i.id DESC
                LIMIT 5
            """)

            table = QTableWidget()
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels(['Fatura No', 'Şube', 'Müşteri', 'Tarih', 'Tutar', 'Durum'])
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setDefaultSectionSize(38)
            table.horizontalHeader().setVisible(True)
            table.horizontalHeader().setHighlightSections(False)
            table.horizontalHeader().setFixedHeight(38)
            table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            table.setSelectionBehavior(QTableWidget.SelectRows)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setFixedHeight(230)
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
                    min-height: 38px;
                }}
                QHeaderView::section {{
                    background-color: {AppStyles.BG_DARKEST};
                    color: #FFFFFF;
                    padding: 0px 8px;
                    border: none;
                    border-bottom: 2px solid {AppStyles.PRIMARY};
                    font-weight: bold;
                    font-size: 9.5pt;
                    min-height: 38px;
                    height: 38px;
                }}
            """)

            if recent:
                table.setRowCount(len(recent))
                status_map = {
                    'Paid': ('Ödendi', AppStyles.GREEN),
                    'Partial': ('Kısmi Ödendi', AppStyles.ORANGE),
                    'Unpaid': ('Ödenmedi', AppStyles.RED),
                }

                for i, inv in enumerate(recent):
                    inv_no = inv.get('invoice_no', '-')
                    branch_name = inv.get('branch_name', '-')
                    cust_name = inv.get('customer_name', '-')
                    inv_date = str(inv.get('invoice_date', ''))
                    amount = f"{float(inv.get('grand_total', 0)):,.2f} ₺"
                    status_raw = inv.get('payment_status', 'Unpaid')
                    status_text, status_color = status_map.get(status_raw, ('Ödenmedi', AppStyles.RED))

                    table.setItem(i, 0, QTableWidgetItem(inv_no))
                    table.setItem(i, 1, QTableWidgetItem(branch_name or "Genel"))
                    table.setItem(i, 2, QTableWidgetItem(cust_name or "-"))
                    table.setItem(i, 3, QTableWidgetItem(inv_date))

                    amount_item = QTableWidgetItem(amount)
                    amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    table.setItem(i, 4, amount_item)

                    status_item = QTableWidgetItem(status_text)
                    status_item.setForeground(QColor(status_color))
                    status_item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(i, 5, status_item)
            else:
                table.setRowCount(1)
                empty_item = QTableWidgetItem("Henüz fatura kaydı yok")
                empty_item.setTextAlignment(Qt.AlignCenter)
                table.setItem(0, 0, empty_item)

            layout.addWidget(table)

        except Exception as e:
            logger.error(f"Genel merkez son faturalar hatası: {e}")

        frame.setLayout(layout)
        return frame

    # ==================== ŞUBE PERFORMANSI ====================

    def _on_branch_sort_changed(self, index: int):
        """Kullanıcı şube sıralama ayarını değiştirdiğinde listeyi anında yeniler"""
        if hasattr(self, 'branch_sort_combo') and self.branch_sort_combo is not None:
            self._branch_perf_sort_mode = self.branch_sort_combo.currentData()
            self._render_branch_performance_cards()

    def _render_branch_performance_cards(self):
        """Şube performans kartlarını seçili sıralama ayarına göre sıralayıp oluşturur"""
        if not hasattr(self, 'branch_list_layout') or self.branch_list_layout is None:
            return

        self._clear_layout(self.branch_list_layout)

        branches = getattr(self, 'cached_branches', []) or []
        if not branches:
            empty_lbl = QLabel("Aktif şube bulunamadı")
            empty_lbl.setStyleSheet(f"color: {AppStyles.TEXT_MUTED}; background: transparent; padding: 10px;")
            self.branch_list_layout.addWidget(empty_lbl)
            return

        sort_mode = getattr(self, '_branch_perf_sort_mode', 'total_sales')

        # Seçilen ayara göre sırala
        if sort_mode == 'total_sales':
            branches.sort(key=lambda b: (float(b.get('total_sales') or 0.0), float(b.get('monthly_sales') or 0.0)), reverse=True)
        elif sort_mode == 'monthly_sales':
            branches.sort(key=lambda b: (float(b.get('monthly_sales') or 0.0), float(b.get('total_sales') or 0.0)), reverse=True)
        elif sort_mode == 'customer_count':
            branches.sort(key=lambda b: (int(b.get('customer_count') or 0), float(b.get('total_sales') or 0.0)), reverse=True)
        elif sort_mode == 'invoice_count':
            branches.sort(key=lambda b: (int(b.get('invoice_count') or 0), float(b.get('total_sales') or 0.0)), reverse=True)
        else:
            branches.sort(key=lambda b: float(b.get('total_sales') or 0.0), reverse=True)

        for rank, branch in enumerate(branches, start=1):
            # Şube Logosu & Renk Eşlemesi
            b_raw_name = branch.get('name', 'Şube')
            nl = b_raw_name.lower()
            if "armada" in nl:
                b_logo = "🥖"
                b_clean_name = "Armada"
                b_color = AppStyles.PRIMARY
            elif "çoban" in nl or "coban" in nl:
                b_logo = "🥐"
                b_clean_name = "Çobançeşme"
                b_color = AppStyles.CYAN
            elif "rumeli" in nl:
                b_logo = "🥨"
                b_clean_name = "Rumeli"
                b_color = AppStyles.PURPLE
            elif "orion" in nl:
                b_logo = "🧁"
                b_clean_name = "Orion"
                b_color = AppStyles.YELLOW
            elif "imalat" in nl:
                b_logo = "🏭"
                b_clean_name = "İmalathane"
                b_color = AppStyles.ORANGE
            else:
                b_logo = "🏢"
                b_clean_name = b_raw_name
                b_color = AppStyles.PRIMARY

            # 🥇🥈🥉 Derece / Sıralama Rozetleri
            if rank == 1:
                rank_badge = "🥇"
                border_color = "#f59e0b"  # Altın
                rank_style = "color: #f59e0b; font-weight: bold; font-size: 13pt;"
            elif rank == 2:
                rank_badge = "🥈"
                border_color = "#94a3b8"  # Gümüş
                rank_style = "color: #94a3b8; font-weight: bold; font-size: 13pt;"
            elif rank == 3:
                rank_badge = "🥉"
                border_color = "#d97706"  # Bronz
                rank_style = "color: #d97706; font-weight: bold; font-size: 13pt;"
            else:
                rank_badge = f"#{rank}"
                border_color = AppStyles.BORDER
                rank_style = f"color: {AppStyles.TEXT_MUTED}; font-size: 9.5pt; font-weight: bold;"

            b_card = QFrame()
            b_card.setStyleSheet(f"""
                QFrame {{
                    background-color: {AppStyles.BG_DARK};
                    border-radius: 6px;
                    border: 1px solid {AppStyles.BORDER};
                    border-left: 3px solid {border_color};
                    padding: 6px 10px;
                }}
                QFrame:hover {{
                    border-color: {AppStyles.PRIMARY};
                }}
            """)
            b_card.setCursor(Qt.PointingHandCursor)
            if self.central_window:
                b_card.mousePressEvent = lambda e: self.central_window.navigate_to("all_invoices")

            b_layout = QHBoxLayout()
            b_layout.setContentsMargins(0, 0, 0, 0)
            b_layout.setSpacing(8)

            # Sıra Rozeti (🥇🥈🥉 veya #4) - Geniş, ferah ve asla sıkışmayan 30x30 boyut
            lbl_rank = QLabel(rank_badge)
            lbl_rank.setStyleSheet(f"""
                QLabel {{
                    {rank_style}
                    background-color: {border_color}18;
                    border: 1px solid {border_color}45;
                    border-radius: 6px;
                }}
            """)
            lbl_rank.setFixedSize(30, 30)
            lbl_rank.setAlignment(Qt.AlignCenter)
            b_layout.addWidget(lbl_rank)

            # Şube Logosu - 30x30 boyutunda geniş ve tam görünür
            lbl_logo = QLabel(b_logo)
            lbl_logo.setStyleSheet(f"""
                QLabel {{
                    font-size: 14pt;
                    background-color: {b_color}18;
                    border-radius: 6px;
                    border: 1px solid {b_color}35;
                }}
            """)
            lbl_logo.setFixedSize(30, 30)
            lbl_logo.setAlignment(Qt.AlignCenter)
            b_layout.addWidget(lbl_logo)

            # Şube Adı & Cari/Fatura Bilgisi
            b_info = QVBoxLayout()
            b_info.setSpacing(1)
            b_info.setAlignment(Qt.AlignVCenter)

            b_name = QLabel(b_clean_name)
            b_name.setStyleSheet(f"font-weight: bold; font-size: 10pt; color: {AppStyles.TEXT_PRIMARY}; background: transparent; border: none;")
            b_info.addWidget(b_name)

            c_cnt = branch.get('customer_count', 0)
            inv_cnt = branch.get('invoice_count', 0)
            b_sub = QLabel(f"👥 {c_cnt} Cari  •  📄 {inv_cnt} Fatura")
            b_sub.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_MUTED}; background: transparent; border: none;")
            b_info.addWidget(b_sub)

            b_layout.addLayout(b_info)
            b_layout.addStretch()

            # Sağ: Satış Rakamı ve Dönem Bilgisi
            right_box = QVBoxLayout()
            right_box.setSpacing(1)
            right_box.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            m_sales = float(branch.get('monthly_sales') or 0.0)
            tot_sales = float(branch.get('total_sales') or 0.0)

            if sort_mode == 'monthly_sales':
                if m_sales > 0:
                    primary_lbl = QLabel(f"{m_sales:,.2f} ₺")
                    primary_lbl.setStyleSheet(f"font-size: 10.5pt; font-weight: bold; color: {AppStyles.GREEN}; background: transparent;")
                    primary_lbl.setAlignment(Qt.AlignRight)
                    right_box.addWidget(primary_lbl)

                    secondary_lbl = QLabel(f"Toplam: {tot_sales:,.2f} ₺")
                    secondary_lbl.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_MUTED}; background: transparent;")
                    secondary_lbl.setAlignment(Qt.AlignRight)
                    right_box.addWidget(secondary_lbl)
                else:
                    primary_lbl = QLabel("0,00 ₺")
                    primary_lbl.setStyleSheet(f"font-size: 10.5pt; font-weight: bold; color: {AppStyles.TEXT_MUTED}; background: transparent;")
                    primary_lbl.setAlignment(Qt.AlignRight)
                    right_box.addWidget(primary_lbl)

                    secondary_lbl = QLabel(f"Toplam: {tot_sales:,.2f} ₺")
                    secondary_lbl.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_MUTED}; background: transparent;")
                    secondary_lbl.setAlignment(Qt.AlignRight)
                    right_box.addWidget(secondary_lbl)
            elif sort_mode == 'customer_count':
                primary_lbl = QLabel(f"{c_cnt} Cari")
                primary_lbl.setStyleSheet(f"font-size: 10.5pt; font-weight: bold; color: {AppStyles.CYAN}; background: transparent;")
                primary_lbl.setAlignment(Qt.AlignRight)
                right_box.addWidget(primary_lbl)

                secondary_lbl = QLabel(f"Toplam Gelir: {tot_sales:,.2f} ₺")
                secondary_lbl.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_MUTED}; background: transparent;")
                secondary_lbl.setAlignment(Qt.AlignRight)
                right_box.addWidget(secondary_lbl)
            elif sort_mode == 'invoice_count':
                primary_lbl = QLabel(f"{inv_cnt} Fatura")
                primary_lbl.setStyleSheet(f"font-size: 10.5pt; font-weight: bold; color: {AppStyles.PURPLE}; background: transparent;")
                primary_lbl.setAlignment(Qt.AlignRight)
                right_box.addWidget(primary_lbl)

                secondary_lbl = QLabel(f"Toplam Gelir: {tot_sales:,.2f} ₺")
                secondary_lbl.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_MUTED}; background: transparent;")
                secondary_lbl.setAlignment(Qt.AlignRight)
                right_box.addWidget(secondary_lbl)
            else:
                # Varsayılan: total_sales (En Yüksek Toplam Gelir)
                if tot_sales > 0:
                    primary_lbl = QLabel(f"{tot_sales:,.2f} ₺")
                    primary_lbl.setStyleSheet(f"font-size: 10.5pt; font-weight: bold; color: {AppStyles.GREEN if m_sales > 0 else AppStyles.CYAN}; background: transparent;")
                    primary_lbl.setAlignment(Qt.AlignRight)
                    right_box.addWidget(primary_lbl)

                    if m_sales > 0:
                        secondary_lbl = QLabel(f"Bu Ay: {m_sales:,.2f} ₺")
                    else:
                        secondary_lbl = QLabel("Toplam Satış Geliri")
                    secondary_lbl.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_MUTED}; background: transparent;")
                    secondary_lbl.setAlignment(Qt.AlignRight)
                    right_box.addWidget(secondary_lbl)
                else:
                    primary_lbl = QLabel("0,00 ₺")
                    primary_lbl.setStyleSheet(f"font-size: 10.5pt; font-weight: bold; color: {AppStyles.TEXT_MUTED}; background: transparent;")
                    primary_lbl.setAlignment(Qt.AlignRight)
                    right_box.addWidget(primary_lbl)

                    secondary_lbl = QLabel("Satış Faturası Yok")
                    secondary_lbl.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_MUTED}; background: transparent;")
                    secondary_lbl.setAlignment(Qt.AlignRight)
                    right_box.addWidget(secondary_lbl)

            b_layout.addLayout(right_box)
            b_card.setLayout(b_layout)
            self.branch_list_layout.addWidget(b_card)

    def create_branch_performance(self) -> QFrame:
        """Şube Performansı & Özet Tablosu (Faturalar ve Cariler)"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
                padding: 12px 14px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 70))
        shadow.setOffset(0, 3)
        frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        layout.setSpacing(8)

        # Başlık ve Sıralama Ayarı
        head_layout = QHBoxLayout()
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(8)

        title = QLabel("🏬 Şube Performansları")
        title.setStyleSheet(f"""
            font-size: 11pt;
            font-weight: bold;
            color: {AppStyles.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)
        head_layout.addWidget(title)

        head_layout.addStretch()

        aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                 "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        now_dt = datetime.now()
        cur_month_name = aylar[now_dt.month - 1]

        # Sıralama Ayarı Açılır Menüsü (En yüksek gelir varsayılan)
        self.branch_sort_combo = QComboBox()
        self.branch_sort_combo.setCursor(Qt.PointingHandCursor)
        self.branch_sort_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 8.5pt;
                font-weight: 600;
                min-width: 145px;
            }}
            QComboBox:hover {{
                border-color: {AppStyles.PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 16px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                selection-background-color: {AppStyles.PRIMARY};
                selection-color: white;
                border: 1px solid {AppStyles.BORDER};
                padding: 4px;
            }}
        """)
        self.branch_sort_combo.addItem("🏆 En Yüksek Gelir", "total_sales")
        self.branch_sort_combo.addItem(f"📅 Bu Ayki Satış ({cur_month_name})", "monthly_sales")
        self.branch_sort_combo.addItem("👥 En Çok Cari", "customer_count")
        self.branch_sort_combo.addItem("📄 En Çok Fatura", "invoice_count")

        current_sort = getattr(self, '_branch_perf_sort_mode', 'total_sales')
        idx = self.branch_sort_combo.findData(current_sort)
        if idx >= 0:
            self.branch_sort_combo.setCurrentIndex(idx)

        self.branch_sort_combo.currentIndexChanged.connect(self._on_branch_sort_changed)
        head_layout.addWidget(self.branch_sort_combo)

        layout.addLayout(head_layout)

        # Kartlar listesi layout'u
        self.branch_list_layout = QVBoxLayout()
        self.branch_list_layout.setSpacing(6)

        try:
            month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            branches = db.fetch_all("""
                SELECT b.id, b.name, b.city,
                    (SELECT COUNT(*) FROM Customers c 
                     WHERE c.branch_id = b.id AND (c.is_active = TRUE OR c.is_active IS NULL)) as customer_count,
                    (SELECT COUNT(*) FROM Invoices i 
                     WHERE i.branch_id = b.id 
                       AND (i.status IS NULL OR i.status != 'Cancelled') 
                       AND (LOWER(i.invoice_type) IN ('sales', 'satış', 'satis') OR i.invoice_type IS NULL)) as invoice_count,
                    (SELECT COALESCE(SUM(i.grand_total), 0) FROM Invoices i 
                     WHERE i.branch_id = b.id 
                       AND (i.status IS NULL OR i.status != 'Cancelled') 
                       AND (LOWER(i.invoice_type) IN ('sales', 'satış', 'satis') OR i.invoice_type IS NULL) 
                       AND i.invoice_date >= %s) as monthly_sales,
                    (SELECT COALESCE(SUM(i.grand_total), 0) FROM Invoices i 
                     WHERE i.branch_id = b.id 
                       AND (i.status IS NULL OR i.status != 'Cancelled') 
                       AND (LOWER(i.invoice_type) IN ('sales', 'satış', 'satis') OR i.invoice_type IS NULL)) as total_sales
                FROM Branches b
                WHERE b.is_active = TRUE
                ORDER BY total_sales DESC, monthly_sales DESC, b.id ASC
            """, (month_start,))

            self.cached_branches = branches or []
            self._render_branch_performance_cards()

        except Exception as e:
            logger.error(f"Şube performans hatası: {e}")
            err_lbl = QLabel("Veriler yüklenirken hata oluştu")
            err_lbl.setStyleSheet(f"color: {AppStyles.RED};")
            self.branch_list_layout.addWidget(err_lbl)

        layout.addLayout(self.branch_list_layout)
        frame.setLayout(layout)
        return frame

    # ==================== VERİ YENİLEME ====================

    def load_data(self):
        """Verileri yenile — arayüzü baştan oluşturmadan (bellek sızıntısı yok)"""
        try:
            # ✅ Sadece mevcut widget'ları temizle ve arayüzü yeniden oluştur
            # (init_ui içinde de temizlik var ama burada daha güvenli)
            old_layout = self.layout()
            if old_layout is not None:
                self._clear_layout(old_layout)
                # Üstteki main_layout'u da sil (kendisi de QVBoxLayout)
                if old_layout.parent() is not None:
                    pass

            self.init_ui()
            self._update_clock()
            logger.info("📊 Genel Merkez Ana Panel verileri güncellendi.")
        except Exception as e:
            logger.error(f"Genel Merkez panel yenileme hatası: {e}")