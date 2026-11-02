# src/ui/styles.py
import os
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt


class AppStyles:
    """Profesyonel monokrom tema"""

    # ✅ CSS cache (performans)
    _main_style_cache = None

    @staticmethod
    def load_colored_icon(path: str, size: int = 40, color: str = "#ffffff") -> QPixmap:
        """PNG ikonunu yükleyip istenen renge boyar (şeffaflığı korur)"""
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return pixmap

        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        colored = QPixmap(pixmap.size())
        colored.fill(Qt.transparent)

        painter = QPainter(colored)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(colored.rect(), QColor(color))
        painter.end()

        return colored

    # ==================== KOYU ARKA PLANLAR ====================
    BG_DARKEST = "#0d0d0f"
    BG_DARK = "#16161a"
    BG_MEDIUM = "#1e1e24"
    BG_LIGHT = "#2a2a32"
    BG_ELEVATED = "#242430"

    # ==================== SIDEBAR ====================
    SIDEBAR_BG = "#0d0d0f"
    SIDEBAR_HOVER = "#1e1e24"
    SIDEBAR_ACTIVE = "#10b98122"

    # ==================== VURGU RENKLERİ ====================
    PRIMARY = "#10b981"
    PRIMARY_HOVER = "#059669"
    PRIMARY_DARK = "#059669"
    PRIMARY_LIGHT = "#34d399"

    SUCCESS = "#10b981"
    DANGER = "#ef4444"
    WARNING = "#f59e0b"
    INFO = "#3b82f6"

    CYAN = "#34d399"
    PURPLE = "#8b5cf6"
    ORANGE = "#f59e0b"
    YELLOW = "#fbbf24"
    PINK = "#ec4899"
    GREEN = "#10b981"
    RED = "#ef4444"
    BLUE = "#3b82f6"

    # Nötr tonlar
    WHITE = "#ffffff"
    GRAY_100 = "#f3f4f6"
    GRAY_200 = "#e5e7eb"
    GRAY_300 = "#d1d5db"
    GRAY_400 = "#9ca3af"
    GRAY_500 = "#6b7280"
    GRAY_600 = "#4b5563"
    GRAY_700 = "#374151"
    GRAY_800 = "#1f2937"
    GRAY_900 = "#111827"

    # ==================== METİN RENKLERİ ====================
    TEXT_PRIMARY = "#f9fafb"
    TEXT_SECONDARY = "#9ca3af"
    TEXT_MUTED = "#6b7280"
    TEXT_ON_PRIMARY = "#0d0d0f"

    # ==================== BORDER ====================
    BORDER = "#2a2a32"
    BORDER_LIGHT = "#3a3a44"
    BORDER_FOCUS = "#10b981"

    # ==================== BUTON STİLLERİ ====================
    @classmethod
    def btn_primary(cls) -> str:
        return f"""
            QPushButton {{
                background-color: {cls.PRIMARY};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 9.5pt;
                font-weight: 600;
                min-height: 28px;
            }}
            QPushButton:hover {{
                background-color: {cls.PRIMARY_HOVER};
            }}
        """

    @classmethod
    def btn_secondary(cls) -> str:
        return f"""
            QPushButton {{
                background-color: {cls.BG_LIGHT};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 9.5pt;
                font-weight: 500;
                min-height: 28px;
            }}
            QPushButton:hover {{
                background-color: {cls.SIDEBAR_HOVER};
                border-color: {cls.PRIMARY};
            }}
        """

    @classmethod
    def btn_success(cls) -> str:
        return f"""
            QPushButton {{
                background-color: {cls.SUCCESS};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 9.5pt;
                font-weight: 600;
                min-height: 28px;
            }}
            QPushButton:hover {{
                background-color: {cls.PRIMARY_HOVER};
            }}
        """

    @classmethod
    def btn_danger(cls) -> str:
        return f"""
            QPushButton {{
                background-color: {cls.DANGER};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 9.5pt;
                font-weight: 600;
                min-height: 28px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """

    # ==================== ANA STİL (CACHE'Lİ) ====================
    @classmethod
    def get_main_style(cls):
        # ✅ Cache kontrolü
        if cls._main_style_cache is not None:
            return cls._main_style_cache

        cls._main_style_cache = f"""
            /* ==================== GENEL ==================== */
            QMainWindow, QDialog {{
                background-color: {cls.BG_DARK};
            }}

            QWidget {{
                background-color: transparent;
                color: {cls.TEXT_PRIMARY};
                font-family: 'Segoe UI', 'SF Pro Display', 'Arial', sans-serif;
                font-size: 10pt;
            }}

            /* ==================== MENU BAR ==================== */
            QMenuBar {{
                background-color: {cls.BG_DARKEST};
                color: {cls.TEXT_PRIMARY};
                font-weight: 500;
                padding: 4px;
                border-bottom: 1px solid {cls.BORDER};
            }}

            QMenuBar::item {{
                padding: 8px 16px;
                border-radius: 6px;
                background-color: transparent;
            }}

            QMenuBar::item:selected {{
                background-color: {cls.BG_LIGHT};
                color: {cls.PRIMARY};
            }}

            QMenu {{
                background-color: {cls.BG_MEDIUM};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                padding: 6px;
            }}

            QMenu::item {{
                padding: 8px 24px;
                border-radius: 6px;
                color: {cls.TEXT_PRIMARY};
            }}

            QMenu::item:selected {{
                background-color: {cls.PRIMARY};
                color: {cls.TEXT_ON_PRIMARY};
            }}

            QMenu::separator {{
                height: 1px;
                background: {cls.BORDER};
                margin: 4px 8px;
            }}

            /* ==================== BUTONLAR ==================== */
            QPushButton {{
                background-color: {cls.PRIMARY};
                color: {cls.TEXT_ON_PRIMARY};
                border: none;
                padding: 7px 16px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 9.5pt;
                min-height: 26px;
            }}

            QPushButton:hover {{
                background-color: {cls.PRIMARY_HOVER};
            }}

            QPushButton:pressed {{
                background-color: {cls.PRIMARY_HOVER};
                padding-top: 8px;
                padding-bottom: 6px;
            }}

            QPushButton:disabled {{
                background-color: {cls.BG_LIGHT};
                color: {cls.TEXT_MUTED};
            }}

            /* ==================== INPUT ALANLARI ==================== */
            QLineEdit, QTextEdit, QPlainTextEdit {{
                background-color: {cls.BG_MEDIUM};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                color: {cls.TEXT_PRIMARY};
                font-size: 10pt;
                selection-background-color: {cls.PRIMARY};
                selection-color: {cls.TEXT_ON_PRIMARY};
            }}

            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
                border: 2px solid {cls.PRIMARY};
                background-color: {cls.BG_ELEVATED};
            }}

            QLineEdit:disabled {{
                background-color: {cls.BG_DARKEST};
                color: {cls.TEXT_MUTED};
            }}

            /* ==================== COMBOBOX ==================== */
            QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit {{
                background-color: {cls.BG_MEDIUM};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                color: {cls.TEXT_PRIMARY};
                font-size: 10pt;
                min-height: 22px;
            }}

            QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
            QDateEdit:focus, QTimeEdit:focus {{
                border: 2px solid {cls.PRIMARY};
            }}

            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}

            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {cls.TEXT_SECONDARY};
                margin-right: 10px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {cls.BG_MEDIUM};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                selection-background-color: {cls.PRIMARY};
                selection-color: {cls.TEXT_ON_PRIMARY};
                padding: 4px;
                outline: none;
            }}

            /* ==================== TABLOLAR ==================== */
            QTableView, QTableWidget, QTreeView, QListView {{
                background-color: {cls.BG_MEDIUM};
                alternate-background-color: {cls.BG_ELEVATED};
                gridline-color: {cls.BORDER};
                border: 1px solid {cls.BORDER};
                border-radius: 10px;
                color: {cls.TEXT_PRIMARY};
                selection-background-color: {cls.PRIMARY};
                selection-color: {cls.TEXT_ON_PRIMARY};
                outline: none;
            }}

            QTableView::item, QTableWidget::item {{
                padding: 6px 10px;
                border: none;
            }}

            QTableView::item:selected, QTableWidget::item:selected {{
                background-color: {cls.PRIMARY};
                color: {cls.TEXT_ON_PRIMARY};
            }}

            /* Tablo içi butonların ve hücre bileşenlerinin asla kesilmemesi için global kural */
            QTableView QPushButton, QTableWidget QPushButton,
            QTableView QWidget QPushButton, QTableWidget QWidget QPushButton,
            QDialog QTableView QPushButton, QDialog QTableWidget QPushButton,
            QDialog QTableView QWidget QPushButton, QDialog QTableWidget QWidget QPushButton {{
                padding: 3px 8px !important;
                min-height: 24px !important;
                max-height: 32px !important;
                min-width: 24px !important;
                font-size: 9pt !important;
                font-weight: 600 !important;
                border-radius: 5px !important;
                margin: 0px !important;
            }}

            QHeaderView {{
                background-color: #1e1e28;
                border: none;
            }}

            QHeaderView::section {{
                background-color: #1e1e28;
                color: #FFFFFF !important;
                padding: 10px 12px;
                border: none;
                border-bottom: 2px solid {cls.PRIMARY};
                border-right: 1px solid #282838;
                font-weight: bold;
                font-size: 9.5pt;
            }}

            QHeaderView::section:hover {{
                background-color: #282838;
                color: #FFFFFF !important;
            }}

            QHeaderView::section:first {{
                border-top-left-radius: 8px;
            }}

            QHeaderView::section:last {{
                border-top-right-radius: 8px;
            }}

            /* ==================== TAB WIDGET ==================== */
            QTabWidget::pane {{
                border: 1px solid {cls.BORDER};
                background-color: {cls.BG_MEDIUM};
                border-radius: 10px;
                top: -1px;
            }}

            QTabBar::tab {{
                background-color: transparent;
                color: {cls.TEXT_SECONDARY};
                padding: 10px 20px;
                margin-right: 4px;
                border: none;
                border-bottom: 2px solid transparent;
                font-weight: 500;
                font-size: 10pt;
            }}

            QTabBar::tab:selected {{
                color: {cls.PRIMARY};
                border-bottom: 2px solid {cls.PRIMARY};
                font-weight: 600;
            }}

            QTabBar::tab:hover:!selected {{
                color: {cls.TEXT_PRIMARY};
                background-color: {cls.BG_LIGHT};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}

            /* ==================== SCROLLBAR ==================== */
            QScrollBar:vertical {{
                background-color: transparent;
                width: 10px;
                border-radius: 5px;
                margin: 4px;
            }}

            QScrollBar::handle:vertical {{
                background-color: {cls.BORDER_LIGHT};
                border-radius: 5px;
                min-height: 40px;
            }}

            QScrollBar::handle:vertical:hover {{
                background-color: {cls.PRIMARY};
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}

            QScrollBar::horizontal {{
                background-color: transparent;
                height: 10px;
                border-radius: 5px;
                margin: 4px;
            }}

            QScrollBar::handle:horizontal {{
                background-color: {cls.BORDER_LIGHT};
                border-radius: 5px;
                min-width: 40px;
            }}

            QScrollBar::handle:horizontal:hover {{
                background-color: {cls.PRIMARY};
            }}

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}

            /* ==================== DİĞER ==================== */
            QLabel {{
                color: {cls.TEXT_PRIMARY};
                background-color: transparent;
            }}

            QToolTip {{
                background-color: {cls.BG_ELEVATED};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.PRIMARY};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 9pt;
            }}

            /* ==================== CHECKBOX ==================== */
            QCheckBox {{
                color: {cls.TEXT_PRIMARY};
                spacing: 10px;
                font-size: 10pt;
            }}

            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 5px;
                border: 2px solid {cls.BORDER_LIGHT};
                background-color: {cls.BG_MEDIUM};
            }}

            QCheckBox::indicator:hover {{
                border-color: {cls.PRIMARY};
            }}

            QCheckBox::indicator:checked {{
                background-color: {cls.PRIMARY};
                border-color: {cls.PRIMARY};
                image: none;
            }}

            /* ==================== RADIO ==================== */
            QRadioButton {{
                color: {cls.TEXT_PRIMARY};
                spacing: 10px;
                font-size: 10pt;
            }}

            QRadioButton::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 10px;
                border: 2px solid {cls.BORDER_LIGHT};
                background-color: {cls.BG_MEDIUM};
            }}

            QRadioButton::indicator:checked {{
                background-color: {cls.PRIMARY};
                border-color: {cls.PRIMARY};
            }}

            /* ==================== GROUPBOX ==================== */
            QGroupBox {{
                border: 1px solid {cls.BORDER};
                border-radius: 12px;
                margin-top: 16px;
                padding-top: 24px;
                background-color: {cls.BG_MEDIUM};
                color: {cls.TEXT_PRIMARY};
                font-weight: 600;
                font-size: 10pt;
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 12px;
                color: {cls.PRIMARY};
                background-color: {cls.BG_MEDIUM};
                border-radius: 6px;
            }}

            /* ==================== STATUS BAR ==================== */
            QStatusBar {{
                background-color: {cls.BG_DARKEST};
                color: {cls.TEXT_SECONDARY};
                border-top: 1px solid {cls.BORDER};
                padding: 4px;
            }}

            /* ==================== PROGRESS BAR ==================== */
            QProgressBar {{
                background-color: {cls.BG_MEDIUM};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                text-align: center;
                color: {cls.TEXT_PRIMARY};
                font-weight: 600;
                height: 20px;
            }}

            QProgressBar::chunk {{
                background-color: {cls.PRIMARY};
                border-radius: 7px;
            }}

            /* ==================== SPLITTER ==================== */
            QSplitter::handle {{
                background-color: {cls.BORDER};
            }}

            QSplitter::handle:hover {{
                background-color: {cls.PRIMARY};
            }}

            /* ==================== TOOLBAR ==================== */
            QToolBar {{
                background-color: {cls.BG_DARKEST};
                border: none;
                padding: 6px;
                spacing: 4px;
            }}

            QToolBar QToolButton {{
                background-color: transparent;
                color: {cls.TEXT_PRIMARY};
                border: none;
                padding: 8px 14px;
                border-radius: 8px;
                font-weight: 500;
            }}

            /* ==================== MESSAGEBOX & DIALOG BUTTONS ==================== */
            QMessageBox {{
                background-color: {cls.BG_MEDIUM};
                border: 1px solid {cls.BORDER};
                border-radius: 12px;
            }}

            QMessageBox QLabel {{
                color: {cls.TEXT_PRIMARY};
                font-size: 11pt;
                background: transparent;
                border: none;
                padding: 10px;
            }}

            QMessageBox QPushButton,
            QMessageBox QDialogButtonBox QPushButton,
            QDialogButtonBox QPushButton {{
                background-color: {cls.PRIMARY};
                color: #ffffff;
                border: 1px solid {cls.PRIMARY};
                border-radius: 8px;
                padding: 6px 18px;
                font-weight: bold;
                font-size: 10pt;
                min-width: 75px;
                min-height: 28px;
            }}

            QMessageBox QPushButton:hover,
            QMessageBox QDialogButtonBox QPushButton:hover,
            QDialogButtonBox QPushButton:hover {{
                background-color: {cls.PRIMARY_HOVER};
                color: #ffffff;
                border: 1px solid {cls.PRIMARY_HOVER};
            }}

            QMessageBox QPushButton:pressed,
            QMessageBox QDialogButtonBox QPushButton:pressed,
            QDialogButtonBox QPushButton:pressed {{
                background-color: {cls.PRIMARY_DARK};
                color: #ffffff;
                border: 1px solid {cls.PRIMARY_DARK};
            }}
        """
        return cls._main_style_cache

    # ==================== YARDIMCI STİLLER ====================

    @classmethod
    def get_card_style(cls):
        """Kart stili"""
        return f"""
            background-color: {cls.BG_MEDIUM};
            border-radius: 12px;
            border: 1px solid {cls.BORDER};
            padding: 16px;
        """

    @classmethod
    def get_stat_card_style(cls):
        """İstatistik kartı stili"""
        return f"""
            background-color: {cls.BG_MEDIUM};
            border-radius: 12px;
            border-left: 4px solid {cls.PRIMARY};
            padding: 16px;
        """

    @classmethod
    def get_gradient_style(cls, color1=None, color2=None):
        """Gradient stil (monokrom)"""
        c1 = color1 or cls.BG_ELEVATED
        c2 = color2 or cls.BG_MEDIUM
        return f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {c1}, stop:1 {c2});
            border-radius: 12px;
        """

    @classmethod
    def get_primary_gradient(cls):
        """Ana yeşil gradient (vurgu)"""
        return f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {cls.PRIMARY}, stop:1 {cls.PRIMARY_LIGHT});
            border-radius: 12px;
        """

    @classmethod
    def get_sidebar_button_style(cls, active: bool = False):
        """Sidebar buton stili"""
        if active:
            return f"""
                QPushButton {{
                    background-color: {cls.SIDEBAR_ACTIVE};
                    color: {cls.PRIMARY};
                    text-align: left;
                    padding: 12px 20px;
                    border: none;
                    border-left: 3px solid {cls.PRIMARY};
                    border-radius: 8px;
                    font-size: 10pt;
                    font-weight: 600;
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background-color: transparent;
                    color: {cls.TEXT_SECONDARY};
                    text-align: left;
                    padding: 12px 20px;
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 8px;
                    font-size: 10pt;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {cls.SIDEBAR_HOVER};
                    color: {cls.TEXT_PRIMARY};
                    border-left: 3px solid {cls.BORDER_LIGHT};
                }}
            """