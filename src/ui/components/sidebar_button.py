# src/ui/components/sidebar_button.py
"""
Sidebar Menü Butonu Bileşeni
"""

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt
from ..styles import AppStyles


class SidebarButton(QPushButton):
    """Modern sidebar menü butonu"""

    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(f"  {icon}   {text}", parent)
        self.setMinimumHeight(42)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {AppStyles.TEXT_SECONDARY};
                text-align: left;
                padding-left: 14px;
                border: none;
                border-radius: 8px;
                font-size: 10.5pt;
                font-weight: 500;
                margin: 1px 0;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.SIDEBAR_HOVER};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QPushButton:checked {{
                background-color: {AppStyles.SIDEBAR_ACTIVE};
                color: {AppStyles.PRIMARY};
                border-left: 3px solid {AppStyles.PRIMARY};
                font-weight: 600;
            }}
        """)
