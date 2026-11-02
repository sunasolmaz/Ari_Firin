# src/ui/pages/daily_turnover_page.py
"""
Günlük / Aylık / Yıllık Ciro Yönetimi
3 sekmeli modern tasarım
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QDateEdit, QComboBox, QLineEdit,
    QDoubleSpinBox, QRadioButton, QButtonGroup, QMessageBox, QFileDialog,
    QHeaderView, QGraphicsDropShadowEffect, QScrollArea, QCompleter,
    QTabWidget, QSpinBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont
from datetime import datetime, timedelta
import pandas as pd

from ...models.user import User
from ...models.branch import Branch
from ...core.logger import logger
from ...services.turnover_service import turnover_service
from ..styles import AppStyles


class DailyTurnoverPage(QWidget):
    """Günlük / Aylık / Yıllık Ciro Sayfası"""

    def __init__(self, user: User, branch_id: int, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window

        self.init_ui()
        self.load_categories()
        self.load_data()

    # ==================== ANA LAYOUT ====================

    def init_ui(self):
        self.setObjectName("DailyTurnoverPage")
        self.setStyleSheet(f"#DailyTurnoverPage {{ background-color: {AppStyles.BG_DARK}; }}")

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24, 18, 24, 18)
        main_layout.setSpacing(12)

        # 1. ÜST BAŞLIK
        header = self.create_header()
        main_layout.addWidget(header)

        # 2. SEKMELER
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(self._tab_style())

        # --- Günlük Sekmesi ---
        self.daily_tab = self.create_daily_tab()
        self.tabs.addTab(self.daily_tab, "📅 Günlük")

        # --- Aylık Sekmesi ---
        self.monthly_tab = self.create_monthly_tab()
        self.tabs.addTab(self.monthly_tab, "📆 Aylık")

        # --- Yıllık Sekmesi ---
        self.yearly_tab = self.create_yearly_tab()
        self.tabs.addTab(self.yearly_tab, "🗓️ Yıllık")

        self.tabs.currentChanged.connect(self.on_tab_changed)

        main_layout.addWidget(self.tabs, 1)
        self.setLayout(main_layout)

    # ==================== 1. ÜST BAŞLIK ====================

    def create_header(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(14)

        # Sol: Başlık
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel("🪙 Ciro Yönetimi")
        title.setStyleSheet(f"""
            font-size: 18pt; font-weight: bold;
            color: {AppStyles.TEXT_PRIMARY};
            background: transparent; border: none;
        """)
        title_box.addWidget(title)

        branch = Branch.get_by_id(self.branch_id)
        branch_name = branch.name if branch else "Şube"
        subtitle = QLabel(f"📍 {branch_name}")
        subtitle.setStyleSheet(f"""
            font-size: 9.5pt; color: {AppStyles.TEXT_SECONDARY};
            background: transparent; border: none;
        """)
        title_box.addWidget(subtitle)

        layout.addLayout(title_box)
        layout.addStretch()

        # Sağ: Yenile butonu
        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setToolTip("Ciro ve Kasa verilerini yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setFixedHeight(38)
        refresh_btn.clicked.connect(self.refresh_data)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                font-weight: bold; font-size: 10pt; padding: 0 16px;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """)
        layout.addWidget(refresh_btn)

        # Sağ: Excel butonu
        export_btn = QPushButton("📤 Excel'e Aktar")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setFixedHeight(38)
        export_btn.clicked.connect(self.export_to_excel)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.GREEN};
                color: white; border: none; border-radius: 8px;
                font-weight: bold; font-size: 10pt; padding: 0 18px;
            }}
            QPushButton:hover {{ background-color: #059669; }}
        """)
        layout.addWidget(export_btn)

        return bar

    # ==================== GÜNLÜK SEKME ====================

    def create_daily_tab(self) -> QWidget:
        """Günlük görünüm"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 12, 0, 0)

        # Tarih seçici çubuğu
        date_bar = self.create_daily_date_bar()
        layout.addWidget(date_bar)

        # KPI kartları
        self.daily_kpi_row = self.create_daily_kpi_row()
        layout.addWidget(self.daily_kpi_row)

        # Hızlı ekleme çubuğu
        quick_add = self.create_quick_add_bar()
        layout.addWidget(quick_add)

        # Tablo
        table_section = self.create_daily_table_section()
        layout.addWidget(table_section, 1)

        return tab

    def create_daily_date_bar(self) -> QFrame:
        """Günlük için tarih seçici çubuğu"""
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(6)

        layout.addWidget(QLabel("📅 Gün:"))

        prev_btn = QPushButton("◀")
        prev_btn.setToolTip("Önceki Gün")
        prev_btn.setCursor(Qt.PointingHandCursor)
        prev_btn.setFixedSize(34, 34)
        prev_btn.clicked.connect(self.go_previous_day)
        prev_btn.setStyleSheet(self._icon_btn_style())
        layout.addWidget(prev_btn)

        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)
        self.date_picker.setDate(QDate.currentDate())
        self.date_picker.setDisplayFormat("dd MMMM yyyy dddd")
        self.date_picker.setMinimumHeight(34)
        self.date_picker.setMinimumWidth(220)
        self.date_picker.dateChanged.connect(self.on_date_changed)
        self.date_picker.setStyleSheet(self._date_edit_style())
        layout.addWidget(self.date_picker)

        today_btn = QPushButton("Bugün")
        today_btn.setCursor(Qt.PointingHandCursor)
        today_btn.setFixedHeight(34)
        today_btn.clicked.connect(self.go_today)
        today_btn.setStyleSheet(self._secondary_btn_style())
        layout.addWidget(today_btn)

        next_btn = QPushButton("▶")
        next_btn.setToolTip("Sonraki Gün")
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.setFixedSize(34, 34)
        next_btn.clicked.connect(self.go_next_day)
        next_btn.setStyleSheet(self._icon_btn_style())
        layout.addWidget(next_btn)

        layout.addStretch()
        return bar

    def create_daily_kpi_row(self) -> QWidget:
        """Günlük KPI kartları"""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.daily_kpi = {}
        cards = [
            ("income",     "🟢", "Günün Geliri",    AppStyles.GREEN),
            ("expense",    "🔴", "Günün Gideri",    AppStyles.RED),
            ("net",        "⚖️", "Günün Neti",      AppStyles.CYAN),
            ("month",      "📆", "Bu Ayın Cirosu",  AppStyles.PRIMARY),
        ]
        for key, icon, title, color in cards:
            card = self._create_kpi_card(f"daily_{key}", icon, title, color)
            layout.addWidget(card)
            self.daily_kpi[key] = card

        return container

    def create_quick_add_bar(self) -> QFrame:
        """Gelir/gider ekleme çubuğu"""
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        add_icon = QLabel("➕")
        add_icon.setStyleSheet("font-size: 14pt; background: transparent; border: none;")
        layout.addWidget(add_icon)

        # Gelir / Gider toggle
        self.radio_income = QRadioButton("Gelir")
        self.radio_expense = QRadioButton("Gider")
        self.radio_income.setChecked(True)
        self.radio_income.setCursor(Qt.PointingHandCursor)
        self.radio_expense.setCursor(Qt.PointingHandCursor)
        self.radio_income.setStyleSheet(self._pill_radio_style(AppStyles.GREEN))
        self.radio_expense.setStyleSheet(self._pill_radio_style(AppStyles.RED))

        self.type_group = QButtonGroup(self)
        self.type_group.addButton(self.radio_income, 1)
        self.type_group.addButton(self.radio_expense, 2)
        self.type_group.buttonClicked.connect(self.on_type_changed)

        layout.addWidget(self.radio_income)
        layout.addWidget(self.radio_expense)

        # Ayırıcı
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {AppStyles.BORDER};")
        layout.addWidget(sep)

        # Kategori
        cat_lbl = QLabel("Tanım:")
        cat_lbl.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9.5pt; background: transparent; border: none;")
        layout.addWidget(cat_lbl)

        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        self.cat_combo.setInsertPolicy(QComboBox.NoInsert)
        self.cat_combo.setMinimumHeight(38)
        self.cat_combo.setMinimumWidth(220)
        self.cat_combo.lineEdit().setPlaceholderText("Seçin veya yazın...")
        self.cat_combo.setStyleSheet(self._combo_style())
        layout.addWidget(self.cat_combo, 3)

        # Tutar
        amt_lbl = QLabel("Tutar:")
        amt_lbl.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9.5pt; background: transparent; border: none;")
        layout.addWidget(amt_lbl)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 999999999999.99)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSingleStep(50.0)
        self.amount_spin.setSuffix(" ₺")
        self.amount_spin.setMinimumHeight(38)
        self.amount_spin.setMinimumWidth(150)
        self.amount_spin.setStyleSheet(self._spin_style())
        layout.addWidget(self.amount_spin)

        # Ödeme
        pay_lbl = QLabel("Ödeme:")
        pay_lbl.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9.5pt; background: transparent; border: none;")
        layout.addWidget(pay_lbl)

        self.payment_combo = QComboBox()
        self.payment_combo.addItems(["Nakit", "Kredi Kartı / POS", "Havale / EFT"])
        self.payment_combo.setMinimumHeight(38)
        self.payment_combo.setMinimumWidth(140)
        self.payment_combo.setStyleSheet(self._combo_style())
        layout.addWidget(self.payment_combo)

        # Not
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Not (opsiyonel)")
        self.desc_input.setMinimumHeight(38)
        self.desc_input.setMinimumWidth(180)
        self.desc_input.setStyleSheet(self._input_style())
        self.desc_input.returnPressed.connect(self.save_entry)
        layout.addWidget(self.desc_input, 2)

        # Kaydet
        save_btn = QPushButton("💾 Ekle")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFixedHeight(38)
        save_btn.setMinimumWidth(100)
        save_btn.clicked.connect(self.save_entry)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                color: white; border: none; border-radius: 8px;
                font-weight: bold; font-size: 10pt; padding: 0 18px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
            }}
        """)
        layout.addWidget(save_btn)

        return bar

    def create_daily_table_section(self) -> QFrame:
        """Günlük tablo"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("📋 Günün Hareketleri")
        title.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; background: transparent; border: none;")
        header.addWidget(title)
        header.addStretch()

        self.daily_count_label = QLabel("0 kayıt")
        self.daily_count_label.setStyleSheet(f"font-size: 9.5pt; color: {AppStyles.TEXT_SECONDARY}; background: transparent; border: none;")
        header.addWidget(self.daily_count_label)
        layout.addLayout(header)

        self.daily_table = self._create_standard_table()
        layout.addWidget(self.daily_table, 1)

        self.daily_empty_label = self._create_empty_label(
            "📭 Bu gün için kayıt bulunmuyor. Yukarıdan ekleyebilirsiniz."
        )
        layout.addWidget(self.daily_empty_label)

        return frame

    # ==================== AYLIK SEKME ====================

    def create_monthly_tab(self) -> QWidget:
        """Aylık görünüm"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 12, 0, 0)

        # Ay/Yıl seçici çubuğu
        date_bar = self.create_monthly_date_bar()
        layout.addWidget(date_bar)

        # KPI kartları (aylık)
        self.monthly_kpi_row = self.create_monthly_kpi_row()
        layout.addWidget(self.monthly_kpi_row)

        # İki bölmeli: Sol özet, Sağ günlük dağılım
        split = QHBoxLayout()
        split.setSpacing(12)

        # Sol: Kategori bazlı özet
        self.monthly_cat_table = self.create_category_summary_section(
            "📊 Aylık Kategori Dağılımı", "monthly_cat"
        )
        split.addWidget(self.monthly_cat_table, 1)

        # Sağ: Günlük dağılım
        self.monthly_daily_table = self.create_daily_breakdown_section(
            "📅 Ayın Günleri", "monthly_daily"
        )
        split.addWidget(self.monthly_daily_table, 1)

        layout.addLayout(split, 1)
        return tab

    def create_monthly_date_bar(self) -> QFrame:
        """Aylık için ay/yıl seçici"""
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(6)

        layout.addWidget(QLabel("📆 Ay:"))

        prev_btn = QPushButton("◀")
        prev_btn.setToolTip("Önceki Ay")
        prev_btn.setCursor(Qt.PointingHandCursor)
        prev_btn.setFixedSize(34, 34)
        prev_btn.clicked.connect(self.go_previous_month)
        prev_btn.setStyleSheet(self._icon_btn_style())
        layout.addWidget(prev_btn)

        # Ay seçici
        self.month_combo = QComboBox()
        self.month_combo.addItems([
            "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
        ])
        self.month_combo.setCurrentIndex(datetime.now().month - 1)
        self.month_combo.setMinimumHeight(34)
        self.month_combo.setMinimumWidth(120)
        self.month_combo.setStyleSheet(self._combo_style())
        self.month_combo.currentIndexChanged.connect(self.on_month_changed)
        layout.addWidget(self.month_combo)

        # Yıl seçici
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2100)
        self.year_spin.setValue(datetime.now().year)
        self.year_spin.setMinimumHeight(34)
        self.year_spin.setMinimumWidth(90)
        self.year_spin.setSuffix(" yılı")
        self.year_spin.setStyleSheet(self._spin_box_style())
        self.year_spin.valueChanged.connect(self.on_month_changed)
        layout.addWidget(self.year_spin)

        next_btn = QPushButton("▶")
        next_btn.setToolTip("Sonraki Ay")
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.setFixedSize(34, 34)
        next_btn.clicked.connect(self.go_next_month)
        next_btn.setStyleSheet(self._icon_btn_style())
        layout.addWidget(next_btn)

        # Bu Ay
        this_month_btn = QPushButton("Bu Ay")
        this_month_btn.setCursor(Qt.PointingHandCursor)
        this_month_btn.setFixedHeight(34)
        this_month_btn.clicked.connect(self.go_this_month)
        this_month_btn.setStyleSheet(self._secondary_btn_style())
        layout.addWidget(this_month_btn)

        layout.addStretch()
        return bar

    def create_monthly_kpi_row(self) -> QWidget:
        """Aylık KPI kartları"""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.monthly_kpi = {}
        cards = [
            ("income",     "🟢", "Aylık Gelir",     AppStyles.GREEN),
            ("expense",    "🔴", "Aylık Gider",     AppStyles.RED),
            ("net",        "⚖️", "Aylık Net",       AppStyles.CYAN),
            ("avg_daily",  "📊", "Günlük Ortalama", AppStyles.PRIMARY),
            ("best_day",   "🏆", "En İyi Gün",      AppStyles.PURPLE),
        ]
        for key, icon, title, color in cards:
            card = self._create_kpi_card(f"monthly_{key}", icon, title, color)
            layout.addWidget(card)
            self.monthly_kpi[key] = card

        return container

    # ==================== YILLIK SEKME ====================

    def create_yearly_tab(self) -> QWidget:
        """Yıllık görünüm"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 12, 0, 0)

        # Yıl seçici çubuğu
        date_bar = self.create_yearly_date_bar()
        layout.addWidget(date_bar)

        # KPI kartları (yıllık)
        self.yearly_kpi_row = self.create_yearly_kpi_row()
        layout.addWidget(self.yearly_kpi_row)

        # İki bölmeli: Sol aylık dağılım, Sağ kategori özet
        split = QHBoxLayout()
        split.setSpacing(12)

        self.yearly_month_table = self.create_monthly_breakdown_section()
        split.addWidget(self.yearly_month_table, 1)

        self.yearly_cat_table = self.create_category_summary_section(
            "📊 Yıllık Kategori Dağılımı", "yearly_cat"
        )
        split.addWidget(self.yearly_cat_table, 1)

        layout.addLayout(split, 1)
        return tab

    def create_yearly_date_bar(self) -> QFrame:
        """Yıllık için yıl seçici"""
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(6)

        layout.addWidget(QLabel("🗓️ Yıl:"))

        prev_btn = QPushButton("◀")
        prev_btn.setToolTip("Önceki Yıl")
        prev_btn.setCursor(Qt.PointingHandCursor)
        prev_btn.setFixedSize(34, 34)
        prev_btn.clicked.connect(self.go_previous_year)
        prev_btn.setStyleSheet(self._icon_btn_style())
        layout.addWidget(prev_btn)

        self.year_combo = QSpinBox()
        self.year_combo.setRange(2020, 2100)
        self.year_combo.setValue(datetime.now().year)
        self.year_combo.setMinimumHeight(34)
        self.year_combo.setMinimumWidth(120)
        self.year_combo.setStyleSheet(self._spin_box_style())
        self.year_combo.valueChanged.connect(self.on_year_changed)
        layout.addWidget(self.year_combo)

        next_btn = QPushButton("▶")
        next_btn.setToolTip("Sonraki Yıl")
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.setFixedSize(34, 34)
        next_btn.clicked.connect(self.go_next_year)
        next_btn.setStyleSheet(self._icon_btn_style())
        layout.addWidget(next_btn)

        # Bu Yıl
        this_year_btn = QPushButton("Bu Yıl")
        this_year_btn.setCursor(Qt.PointingHandCursor)
        this_year_btn.setFixedHeight(34)
        this_year_btn.clicked.connect(self.go_this_year)
        this_year_btn.setStyleSheet(self._secondary_btn_style())
        layout.addWidget(this_year_btn)

        layout.addStretch()
        return bar

    def create_yearly_kpi_row(self) -> QWidget:
        """Yıllık KPI kartları"""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.yearly_kpi = {}
        cards = [
            ("income",     "🟢", "Yıllık Gelir",     AppStyles.GREEN),
            ("expense",    "🔴", "Yıllık Gider",     AppStyles.RED),
            ("net",        "⚖️", "Yıllık Net",       AppStyles.CYAN),
            ("avg_monthly","📊", "Aylık Ortalama",   AppStyles.PRIMARY),
            ("best_month", "🏆", "En İyi Ay",        AppStyles.PURPLE),
        ]
        for key, icon, title, color in cards:
            card = self._create_kpi_card(f"yearly_{key}", icon, title, color)
            layout.addWidget(card)
            self.yearly_kpi[key] = card

        return container

    # ==================== ORTAK BİLEŞENLER ====================

    def _create_kpi_card(self, key: str, icon: str, title: str, color: str) -> QFrame:
        card = QFrame()
        card.setMinimumHeight(80)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border-left: 4px solid {color};
                border-top: 1px solid {AppStyles.BORDER};
                border-right: 1px solid {AppStyles.BORDER};
                border-bottom: 1px solid {AppStyles.BORDER};
            }}
            QFrame QLabel {{ background: transparent; border: none; }}
        """)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(f"background-color: {color}20; border-radius: 18px; font-size: 14pt;")
        layout.addWidget(icon_lbl)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_SECONDARY}; font-weight: 600;")
        text_box.addWidget(title_lbl)

        value_lbl = QLabel("0,00 ₺")
        value_lbl.setObjectName(f"kpi_value_{key}")
        value_lbl.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {color};")
        text_box.addWidget(value_lbl)

        layout.addLayout(text_box)
        layout.addStretch()
        return card

    def _update_kpi_value(self, card: QFrame, key: str, text: str, color: str = None):
        value_lbl = card.findChild(QLabel, f"kpi_value_{key}")
        if value_lbl:
            value_lbl.setText(text)
            if color:
                value_lbl.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {color};")

    def _create_standard_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels([
            'Saat', 'Tür', 'Tanım / Kategori', 'Ödeme', 'Tutar', 'Not', ''
        ])
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setShowGrid(False)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        # ✅ Buton sütunu — daha geniş ve yeterli yükseklik
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        table.setColumnWidth(6, 75)
        # ✅ Satır yüksekliği butonlar için yeterli olsun
        table.verticalHeader().setDefaultSectionSize(44)

        table.setStyleSheet(self._table_style())
        return table

    def _create_empty_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"""
            color: {AppStyles.TEXT_MUTED}; font-size: 10pt;
            font-style: italic; padding: 20px;
            background: transparent; border: none;
        """)
        label.setVisible(False)
        return label

    def create_category_summary_section(self, title_text: str, prefix: str) -> QFrame:
        """Kategori bazlı özet tablosu"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(title_text)
        title.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; background: transparent; border: none;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Tür", "Kategori", "Tutar"])
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(42)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setShowGrid(False)
        table.setObjectName(f"{prefix}_table")

        h = table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        table.setStyleSheet(self._table_style())
        layout.addWidget(table, 1)
        return frame

    def create_daily_breakdown_section(self, title_text: str, prefix: str) -> QFrame:
        """Aylık görünüm için günlük dağılım tablosu"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        title = QLabel(title_text)
        title.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; background: transparent; border: none;")
        layout.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Gün", "Gelir", "Gider", "Net"])
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(42)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setShowGrid(False)

        h = table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.Stretch)

        table.setStyleSheet(self._table_style())
        table.setObjectName(f"{prefix}_table")
        layout.addWidget(table, 1)
        return frame

    def create_monthly_breakdown_section(self) -> QFrame:
        """Yıllık görünüm için aylık dağılım tablosu"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        title = QLabel("📅 Yılın Ayları")
        title.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; background: transparent; border: none;")
        layout.addWidget(title)

        self.yearly_month_table_widget = QTableWidget()
        self.yearly_month_table_widget.setColumnCount(4)
        self.yearly_month_table_widget.setHorizontalHeaderLabels(["Ay", "Gelir", "Gider", "Net"])
        self.yearly_month_table_widget.setAlternatingRowColors(True)
        self.yearly_month_table_widget.verticalHeader().setVisible(False)
        self.yearly_month_table_widget.verticalHeader().setDefaultSectionSize(42)
        self.yearly_month_table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        self.yearly_month_table_widget.setShowGrid(False)

        h = self.yearly_month_table_widget.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.Stretch)

        self.yearly_month_table_widget.setStyleSheet(self._table_style())
        layout.addWidget(self.yearly_month_table_widget, 1)
        return frame

    # ==================== SEKMELER ARASI GEÇİŞ ====================

    def on_tab_changed(self, index: int):
        """Sekme değiştiğinde veriyi yenile"""
        if index == 0:
            self.load_daily_data()
        elif index == 1:
            self.load_monthly_data()
        elif index == 2:
            self.load_yearly_data()

    # ==================== GÜNLÜK VERİ ====================

    def get_selected_date_str(self) -> str:
        return self.date_picker.date().toString("yyyy-MM-dd")

    def go_previous_day(self):
        self.date_picker.setDate(self.date_picker.date().addDays(-1))

    def go_today(self):
        self.date_picker.setDate(QDate.currentDate())

    def go_next_day(self):
        self.date_picker.setDate(self.date_picker.date().addDays(1))

    def on_date_changed(self):
        self.load_daily_data()

    def load_daily_data(self):
        """Günlük veriyi yükle"""
        date_str = self.get_selected_date_str()

        daily = turnover_service.get_daily_summary(self.branch_id, date_str)
        # KPI güncelle
        self._update_kpi_value(self.daily_kpi["income"], "daily_income",
                            f"{daily.get('total_income', 0):,.2f} ₺")
        self._update_kpi_value(self.daily_kpi["expense"], "daily_expense",
                            f"{daily.get('total_expense', 0):,.2f} ₺")

        net = daily.get('net_turnover', 0)
        net_color = AppStyles.CYAN if net >= 0 else AppStyles.RED
        self._update_kpi_value(self.daily_kpi["net"], "daily_net",
                            f"{net:,.2f} ₺", net_color)

        # Seçilen günün ait olduğu ayın toplam cirosu
        qdate = self.date_picker.date()
        m_summary = turnover_service.get_monthly_summary(self.branch_id, qdate.year(), qdate.month())
        month_income = m_summary.get('total_income', 0)
        self._update_kpi_value(self.daily_kpi["month"], "daily_month",
                            f"{month_income:,.2f} ₺")

        # Tablo
        entries = turnover_service.get_entries_by_date(self.branch_id, date_str)
        self.populate_daily_table(entries)

    def populate_daily_table(self, entries: list):
        """Günlük tabloyu doldur"""
        self.daily_table.setRowCount(0)

        if not entries:
            self.daily_table.setVisible(False)
            self.daily_empty_label.setVisible(True)
            self.daily_count_label.setText("0 kayıt")
            return

        self.daily_table.setVisible(True)
        self.daily_empty_label.setVisible(False)
        self.daily_count_label.setText(f"{len(entries)} kayıt")

        for row_idx, item in enumerate(entries):
            self.daily_table.insertRow(row_idx)

            e_id = item.get('id')
            created_at = item.get('created_at')
            time_str = created_at.strftime('%H:%M') if isinstance(created_at, datetime) else "-"
            e_type = item.get('entry_type', 'Income')
            cat = item.get('category', '-')
            pay = item.get('payment_method', 'Nakit')
            amt = float(item.get('amount', 0))
            desc = item.get('description', '') or ''

            time_item = QTableWidgetItem(time_str)
            time_item.setTextAlignment(Qt.AlignCenter)
            time_item.setForeground(QColor(AppStyles.TEXT_SECONDARY))
            self.daily_table.setItem(row_idx, 0, time_item)

            if e_type == 'Income':
                type_item = QTableWidgetItem("🟢 Gelir")
                type_item.setForeground(QColor(AppStyles.GREEN))
            else:
                type_item = QTableWidgetItem("🔴 Gider")
                type_item.setForeground(QColor(AppStyles.RED))
            type_item.setTextAlignment(Qt.AlignCenter)
            type_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.daily_table.setItem(row_idx, 1, type_item)

            cat_item = QTableWidgetItem(cat)
            cat_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.daily_table.setItem(row_idx, 2, cat_item)

            pay_item = QTableWidgetItem(pay)
            pay_item.setForeground(QColor(AppStyles.TEXT_SECONDARY))
            pay_item.setTextAlignment(Qt.AlignCenter)
            self.daily_table.setItem(row_idx, 3, pay_item)

            sign = "+" if e_type == 'Income' else "-"
            amt_item = QTableWidgetItem(f"{sign}{amt:,.2f} ₺")
            amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amt_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            amt_item.setForeground(QColor(AppStyles.GREEN if e_type == 'Income' else AppStyles.RED))
            self.daily_table.setItem(row_idx, 4, amt_item)

            desc_item = QTableWidgetItem(desc or "—")
            desc_item.setForeground(QColor(AppStyles.TEXT_MUTED))
            if desc:
                desc_item.setToolTip(desc)
            self.daily_table.setItem(row_idx, 5, desc_item)

                        # ✅ Sil butonunu container widget içine koy (hizalama için)
            del_container = QWidget()
            del_container.setStyleSheet("background: transparent;")
            del_lay = QHBoxLayout(del_container)
            del_lay.setContentsMargins(2, 2, 2, 2)
            del_lay.setAlignment(Qt.AlignCenter)

            del_btn = QPushButton("🗑️")
            del_btn.setToolTip("Kaydı Sil")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setFixedSize(34, 30)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.RED}25;
                    color: {AppStyles.RED};
                    border: 1px solid {AppStyles.RED}50;
                    border-radius: 6px;
                    font-size: 11pt;
                    padding: 0px;
                }}
                QPushButton:hover {{ background-color: {AppStyles.RED}; color: white; }}
            """)
            del_btn.clicked.connect(lambda checked, eid=e_id: self.delete_entry(eid))
            del_lay.addWidget(del_btn)

            self.daily_table.setCellWidget(row_idx, 6, del_container)

    # ==================== AYLIK VERİ ====================

    def go_previous_month(self):
        idx = self.month_combo.currentIndex()
        year = self.year_spin.value()
        if idx == 0:
            self.month_combo.setCurrentIndex(11)
            self.year_spin.setValue(year - 1)
        else:
            self.month_combo.setCurrentIndex(idx - 1)

    def go_next_month(self):
        idx = self.month_combo.currentIndex()
        year = self.year_spin.value()
        if idx == 11:
            self.month_combo.setCurrentIndex(0)
            self.year_spin.setValue(year + 1)
        else:
            self.month_combo.setCurrentIndex(idx + 1)

    def go_this_month(self):
        now = datetime.now()
        self.month_combo.setCurrentIndex(now.month - 1)
        self.year_spin.setValue(now.year)

    def on_month_changed(self):
        self.load_monthly_data()

    def load_monthly_data(self):
        """Aylık veriyi yükle"""
        year = self.year_spin.value()
        month = self.month_combo.currentIndex() + 1  # 1-12

        month_start = datetime(year, month, 1).strftime('%Y-%m-%d')
        # Ayın son günü
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)
        month_end = (next_month - timedelta(days=1)).strftime('%Y-%m-%d')

        # KPI
        monthly = turnover_service.get_range_summary(self.branch_id, month_start, month_end)
        total_income = monthly.get('total_income', 0)
        total_expense = monthly.get('total_expense', 0)
        net = total_income - total_expense

        # Günlük ortalama
        days_in_month = (next_month - datetime(year, month, 1)).days
        avg_daily = total_income / days_in_month if days_in_month > 0 else 0

        # En iyi gün
        daily_data = turnover_service.get_daily_range(self.branch_id, month_start, month_end)
        best_day = 0
        best_day_str = "—"
        for d in daily_data:
            if d.get('total_income', 0) > best_day:
                best_day = d.get('total_income', 0)
                best_day_str = d.get('date', '—')

        self._update_kpi_value(self.monthly_kpi["income"], "monthly_income",
                            f"{total_income:,.2f} ₺")
        self._update_kpi_value(self.monthly_kpi["expense"], "monthly_expense",
                            f"{total_expense:,.2f} ₺")
        net_color = AppStyles.CYAN if net >= 0 else AppStyles.RED
        self._update_kpi_value(self.monthly_kpi["net"], "monthly_net",
                            f"{net:,.2f} ₺", net_color)
        self._update_kpi_value(self.monthly_kpi["avg_daily"], "monthly_avg_daily",
                            f"{avg_daily:,.2f} ₺")
        self._update_kpi_value(self.monthly_kpi["best_day"], "monthly_best_day",
                            f"{best_day:,.2f} ₺")

        # Kategori dağılımı
        cat_data = turnover_service.get_category_summary(self.branch_id, month_start, month_end)
        self.populate_category_table(
            self.monthly_cat_table.findChild(QTableWidget, "monthly_cat_table"),
            cat_data
        )

        # Günlük dağılım
        self.populate_daily_breakdown_table(
            self.monthly_daily_table.findChild(QTableWidget, "monthly_daily_table"),
            daily_data
        )

    # ==================== YILLIK VERİ ====================

    def go_previous_year(self):
        self.year_combo.setValue(self.year_combo.value() - 1)

    def go_next_year(self):
        self.year_combo.setValue(self.year_combo.value() + 1)

    def go_this_year(self):
        self.year_combo.setValue(datetime.now().year)

    def on_year_changed(self):
        self.load_yearly_data()

    def load_yearly_data(self):
        """Yıllık veriyi yükle"""
        year = self.year_combo.value()
        year_start = f"{year}-01-01"
        year_end = f"{year}-12-31"

        # KPI
        yearly = turnover_service.get_range_summary(self.branch_id, year_start, year_end)
        total_income = yearly.get('total_income', 0)
        total_expense = yearly.get('total_expense', 0)
        net = total_income - total_expense

        avg_monthly = total_income / 12 if total_income > 0 else 0

        # Aylık dağılım
        monthly_data = turnover_service.get_monthly_range(self.branch_id, year_start, year_end)

        # En iyi ay
        best_month = 0
        best_month_name = "—"
        month_names = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        for m in monthly_data:
            if m.get('total_income', 0) > best_month:
                best_month = m.get('total_income', 0)
                m_idx = m.get('month', 1) - 1
                if 0 <= m_idx < 12:
                    best_month_name = month_names[m_idx]

        self._update_kpi_value(self.yearly_kpi["income"], "yearly_income",
                            f"{total_income:,.2f} ₺")
        self._update_kpi_value(self.yearly_kpi["expense"], "yearly_expense",
                            f"{total_expense:,.2f} ₺")
        net_color = AppStyles.CYAN if net >= 0 else AppStyles.RED
        self._update_kpi_value(self.yearly_kpi["net"], "yearly_net",
                            f"{net:,.2f} ₺", net_color)
        self._update_kpi_value(self.yearly_kpi["avg_monthly"], "yearly_avg_monthly",
                            f"{avg_monthly:,.2f} ₺")
        self._update_kpi_value(self.yearly_kpi["best_month"], "yearly_best_month",
                            f"{best_month:,.2f} ₺")

        # Aylık tablo
        self.populate_monthly_breakdown_table(self.yearly_month_table_widget, monthly_data)

        # Kategori dağılımı
        cat_data = turnover_service.get_category_summary(self.branch_id, year_start, year_end)
        self.populate_category_table(
            self.yearly_cat_table.findChild(QTableWidget, "yearly_cat_table"),
            cat_data
        )

    # ==================== TABLO DOLDURMA ====================

    def populate_category_table(self, table: QTableWidget, cat_data: list):
        """Kategori özet tablosu"""
        if table is None:
            return

        table.setRowCount(0)

        if not cat_data:
            return

        for row_idx, item in enumerate(cat_data):
            table.insertRow(row_idx)

            e_type = item.get('entry_type', 'Income')
            cat = item.get('category', '-')
            amt = float(item.get('total_amount', 0))

            if e_type == 'Income':
                type_item = QTableWidgetItem("🟢 Gelir")
                type_item.setForeground(QColor(AppStyles.GREEN))
            else:
                type_item = QTableWidgetItem("🔴 Gider")
                type_item.setForeground(QColor(AppStyles.RED))
            type_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row_idx, 0, type_item)

            cat_item = QTableWidgetItem(cat)
            cat_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            table.setItem(row_idx, 1, cat_item)

            amt_item = QTableWidgetItem(f"{amt:,.2f} ₺")
            amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amt_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            amt_item.setForeground(QColor(AppStyles.GREEN if e_type == 'Income' else AppStyles.RED))
            table.setItem(row_idx, 2, amt_item)

    def populate_daily_breakdown_table(self, table: QTableWidget, daily_data: list):
        """Aylık görünüm için günlük dağılım"""
        if table is None:
            return

        table.setRowCount(0)

        if not daily_data:
            return

        for row_idx, item in enumerate(daily_data):
            table.insertRow(row_idx)

            date_str = item.get('date', '-')
            income = float(item.get('total_income', 0))
            expense = float(item.get('total_expense', 0))
            net = income - expense

            # Gün
            day_item = QTableWidgetItem(str(date_str))
            day_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row_idx, 0, day_item)

            # Gelir
            inc_item = QTableWidgetItem(f"{income:,.2f} ₺")
            inc_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            inc_item.setForeground(QColor(AppStyles.GREEN))
            table.setItem(row_idx, 1, inc_item)

            # Gider
            exp_item = QTableWidgetItem(f"{expense:,.2f} ₺")
            exp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            exp_item.setForeground(QColor(AppStyles.RED))
            table.setItem(row_idx, 2, exp_item)

            # Net
            net_item = QTableWidgetItem(f"{net:,.2f} ₺")
            net_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            net_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            net_item.setForeground(QColor(AppStyles.CYAN if net >= 0 else AppStyles.RED))
            table.setItem(row_idx, 3, net_item)

    def populate_monthly_breakdown_table(self, table: QTableWidget, monthly_data: list):
        """Yıllık görünüm için aylık dağılım"""
        if table is None:
            return

        table.setRowCount(0)

        month_names = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

        if not monthly_data:
            # 12 ayı boş göster
            for i, name in enumerate(month_names):
                table.insertRow(i)
                table.setItem(i, 0, QTableWidgetItem(name))
                table.setItem(i, 1, QTableWidgetItem("0,00 ₺"))
                table.setItem(i, 2, QTableWidgetItem("0,00 ₺"))
                table.setItem(i, 3, QTableWidgetItem("0,00 ₺"))
            return

        # Ay verilerini dictionary'e al
        month_dict = {}
        for m in monthly_data:
            month_dict[m.get('month', 0)] = m

        for i, name in enumerate(month_names):
            month_num = i + 1
            table.insertRow(i)

            m = month_dict.get(month_num, {})
            income = float(m.get('total_income', 0))
            expense = float(m.get('total_expense', 0))
            net = income - expense

            month_item = QTableWidgetItem(name)
            month_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 0, month_item)

            inc_item = QTableWidgetItem(f"{income:,.2f} ₺")
            inc_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            inc_item.setForeground(QColor(AppStyles.GREEN))
            table.setItem(i, 1, inc_item)

            exp_item = QTableWidgetItem(f"{expense:,.2f} ₺")
            exp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            exp_item.setForeground(QColor(AppStyles.RED))
            table.setItem(i, 2, exp_item)

            net_item = QTableWidgetItem(f"{net:,.2f} ₺")
            net_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            net_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            net_item.setForeground(QColor(AppStyles.CYAN if net >= 0 else AppStyles.RED))
            table.setItem(i, 3, net_item)

    # ==================== KATEGORİ YÜKLEME ====================

    def load_categories(self):
        cur_text = self.cat_combo.currentText().strip()
        is_income = self.radio_income.isChecked()
        cat_type = "Income" if is_income else "Expense"

        categories = turnover_service.get_categories(self.branch_id, cat_type)

        self.cat_combo.clear()
        self.cat_combo.addItems(categories)

        completer = QCompleter(categories, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.cat_combo.setCompleter(completer)

        if cur_text:
            idx = self.cat_combo.findText(cur_text)
            if idx >= 0:
                self.cat_combo.setCurrentIndex(idx)
            else:
                self.cat_combo.setEditText(cur_text)
        else:
            self.cat_combo.setCurrentIndex(-1)

    def on_type_changed(self):
        self.load_categories()

    # ==================== KAYDET / SİL ====================

    def save_entry(self):
        cat = self.cat_combo.currentText().strip()
        amt = self.amount_spin.value()
        is_income = self.radio_income.isChecked()
        entry_type = "Income" if is_income else "Expense"
        pay_method = self.payment_combo.currentText()
        desc = self.desc_input.text().strip()
        date_str = self.get_selected_date_str()
        user_id = getattr(self.user, 'id', None)

        if not cat:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir tanım/kategori girin!")
            self.cat_combo.setFocus()
            return

        if amt <= 0:
            QMessageBox.warning(self, "Uyarı", "Tutar 0'dan büyük olmalı!")
            self.amount_spin.setFocus()
            return

        success, msg, _ = turnover_service.add_entry(
            branch_id=self.branch_id,
            entry_date=date_str,
            entry_type=entry_type,
            category=cat,
            amount=amt,
            payment_method=pay_method,
            description=desc,
            user_id=user_id
        )

        if success:
            self.amount_spin.setValue(0.0)
            self.desc_input.clear()
            self.load_categories()
            # Tüm sekmeleri yenile
            self.load_daily_data()
            self.load_monthly_data()
            self.load_yearly_data()
            self.cat_combo.setFocus()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def delete_entry(self, entry_id):
        is_invoice = isinstance(entry_id, str) and str(entry_id).startswith('inv_')
        msg_text = (
            "Bu fatura kaydını silmek istediğinize emin misiniz?\n\n"
            "Fatura kaydı ve ilgili cari hesap bakiyesi geri alınacaktır."
            if is_invoice else
            "Bu ciro hareketini silmek istediğinize emin misiniz?"
        )
        reply = QMessageBox.question(
            self, "Silme Onayı",
            msg_text,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = turnover_service.delete_entry(entry_id)
            if success:
                self.load_daily_data()
                self.load_monthly_data()
                self.load_yearly_data()
            else:
                QMessageBox.critical(self, "Hata", msg)

    # ==================== EXCEL ====================

    def export_to_excel(self):
        """Aktif sekmeye göre Excel'e aktar"""
        current_tab = self.tabs.currentIndex()

        if current_tab == 0:
            self._export_daily()
        elif current_tab == 1:
            self._export_monthly()
        elif current_tab == 2:
            self._export_yearly()

    def _export_daily(self):
        date_str = self.get_selected_date_str()
        entries = turnover_service.get_entries_by_date(self.branch_id, date_str)

        if not entries:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak kayıt yok.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel Olarak Kaydet",
            f"Gunluk_Ciro_{date_str}.xlsx", "Excel (*.xlsx)"
        )
        if not file_path:
            return

        try:
            data = []
            for e in entries:
                data.append({
                    "Saat": e.get('created_at').strftime('%H:%M') if isinstance(e.get('created_at'), datetime) else '',
                    "Tür": "Gelir" if e.get('entry_type') == 'Income' else 'Gider',
                    "Kategori": e.get('category'),
                    "Ödeme": e.get('payment_method'),
                    "Tutar (₺)": float(e.get('amount', 0)),
                    "Not": e.get('description', ''),
                })
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False, engine='openpyxl')
            QMessageBox.information(self, "Başarılı", f"Kaydedildi:\n{file_path}")
        except Exception as e:
            logger.error(f"Excel hatası: {e}")
            QMessageBox.critical(self, "Hata", str(e))

    def _export_monthly(self):
        year = self.year_spin.value()
        month = self.month_combo.currentIndex() + 1

        month_start = datetime(year, month, 1).strftime('%Y-%m-%d')
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)
        month_end = (next_month - timedelta(days=1)).strftime('%Y-%m-%d')

        daily_data = turnover_service.get_daily_range(self.branch_id, month_start, month_end)

        if not daily_data:
            QMessageBox.information(self, "Bilgi", "Bu ay için kayıt yok.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel Olarak Kaydet",
            f"Aylik_Ciro_{year}_{month:02d}.xlsx", "Excel (*.xlsx)"
        )
        if not file_path:
            return

        try:
            data = []
            for d in daily_data:
                data.append({
                    "Tarih": d.get('date'),
                    "Gelir (₺)": float(d.get('total_income', 0)),
                    "Gider (₺)": float(d.get('total_expense', 0)),
                    "Net (₺)": float(d.get('total_income', 0)) - float(d.get('total_expense', 0)),
                })
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False, engine='openpyxl')
            QMessageBox.information(self, "Başarılı", f"Kaydedildi:\n{file_path}")
        except Exception as e:
            logger.error(f"Excel hatası: {e}")
            QMessageBox.critical(self, "Hata", str(e))

    def _export_yearly(self):
        year = self.year_combo.value()
        monthly_data = turnover_service.get_monthly_range(
            self.branch_id, f"{year}-01-01", f"{year}-12-31"
        )

        if not monthly_data:
            QMessageBox.information(self, "Bilgi", "Bu yıl için kayıt yok.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel Olarak Kaydet",
            f"Yillik_Ciro_{year}.xlsx", "Excel (*.xlsx)"
        )
        if not file_path:
            return

        try:
            month_names = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                        "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
            month_dict = {m.get('month', 0): m for m in monthly_data}

            data = []
            for i, name in enumerate(month_names):
                m = month_dict.get(i + 1, {})
                income = float(m.get('total_income', 0))
                expense = float(m.get('total_expense', 0))
                data.append({
                    "Ay": name,
                    "Gelir (₺)": income,
                    "Gider (₺)": expense,
                    "Net (₺)": income - expense,
                })
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False, engine='openpyxl')
            QMessageBox.information(self, "Başarılı", f"Kaydedildi:\n{file_path}")
        except Exception as e:
            logger.error(f"Excel hatası: {e}")
            QMessageBox.critical(self, "Hata", str(e))

    # ==================== GENEL VERİ YÜKLEME ====================

    def load_data(self):
        """Tüm sekmeleri yükle"""
        self.load_daily_data()
        self.load_monthly_data()
        self.load_yearly_data()

    def refresh_data(self):
        """Ciro ve kasa verilerini, kategorileri yenile"""
        try:
            self.load_categories()
            self.load_data()
            logger.info("✅ Günlük ciro verileri yenilendi")
        except Exception as e:
            logger.error(f"Ciro yenileme hatası: {e}")

    # ==================== STİLLER ====================

    def _tab_style(self) -> str:
        return f"""
            QTabWidget::pane {{
                border: none;
                background-color: transparent;
                top: 0px;
            }}
            QTabBar::tab {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_SECONDARY};
                padding: 12px 32px;
                margin-right: 8px;
                min-width: 140px;
                border: 1px solid {AppStyles.BORDER};
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                font-weight: 600;
                font-size: 10.5pt;
            }}
            QTabBar::tab:selected {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.PRIMARY};
                border-color: {AppStyles.PRIMARY};
                border-bottom: 2px solid {AppStyles.BG_DARK};
            }}
            QTabBar::tab:hover:!selected {{
                color: {AppStyles.TEXT_PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """

    def _date_edit_style(self) -> str:
        return f"""
            QDateEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 10pt;
                font-weight: 600;
            }}
            QDateEdit:focus {{ border-color: {AppStyles.PRIMARY}; }}
        """

    def _spin_box_style(self) -> str:
        return f"""
            QSpinBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 10pt;
                font-weight: 600;
            }}
            QSpinBox:focus {{ border-color: {AppStyles.PRIMARY}; }}
        """

    def _secondary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 0 12px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.BG_LIGHT};
                border-color: {AppStyles.PRIMARY};
            }}
        """

    def _icon_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                font-size: 11pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.BG_LIGHT};
                border-color: {AppStyles.PRIMARY};
                color: {AppStyles.PRIMARY};
            }}
        """

    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 10pt;
            }}
            QComboBox:focus {{ border-color: {AppStyles.PRIMARY}; }}
            QComboBox QAbstractItemView {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                selection-background-color: {AppStyles.PRIMARY};
                selection-color: white;
                border: 1px solid {AppStyles.BORDER};
                outline: none;
            }}
        """

    def _spin_style(self) -> str:
        return f"""
            QDoubleSpinBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 10pt;
                font-weight: 600;
            }}
            QDoubleSpinBox:focus {{ border-color: {AppStyles.PRIMARY}; }}
        """

    def _input_style(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 10pt;
            }}
            QLineEdit:focus {{ border-color: {AppStyles.PRIMARY}; }}
        """

    def _pill_radio_style(self, color: str) -> str:
        return f"""
            QRadioButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 10pt;
                font-weight: 600;
                spacing: 0px;
            }}
            QRadioButton::indicator {{ width: 0px; height: 0px; }}
            QRadioButton:hover {{ border-color: {color}; color: {color}; }}
            QRadioButton:checked {{
                background-color: {color}25;
                color: {color};
                border: 1px solid {color};
            }}
        """

    def _table_style(self) -> str:
        return f"""
            QTableWidget {{
                background-color: {AppStyles.BG_DARK};
                alternate-background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                gridline-color: transparent;
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{
                padding: 8px 6px;
                border-bottom: 1px solid {AppStyles.BORDER};
            }}
            QTableWidget::item:selected {{
                background-color: {AppStyles.PRIMARY}30;
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QHeaderView {{
                background-color: {AppStyles.BG_DARKEST};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARKEST};
                color: #FFFFFF;
                padding: 8px 6px;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                font-weight: bold;
                font-size: 9.5pt;
                height: 36px;
            }}
        """