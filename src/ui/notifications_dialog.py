# src/ui/notifications_dialog.py
"""
Modern Bildirimler & Hatırlatmalar Açılır Penceresi
Ana sayfadaki yer kaplayan bildirim bloğunu üst bardaki zil ikonuna taşır.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from .styles import AppStyles
from ..core.logger import logger


class NotificationItemWidget(QFrame):
    """Tek bir bildirim kartı"""

    def __init__(self, notif: dict, parent_dialog=None):
        super().__init__()
        self.notif = notif
        self.parent_dialog = parent_dialog
        self.init_ui()

    def init_ui(self):
        color = self.notif.get('color', AppStyles.PRIMARY)
        icon = self.notif.get('icon', '🔔')
        title = self.notif.get('title', 'Bildirim')
        desc = self.notif.get('desc', '')
        callback = self.notif.get('on_click')

        if callback:
            self.setCursor(Qt.PointingHandCursor)

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border-radius: 6px;
                border-left: 3px solid {color};
                border-top: 1px solid {AppStyles.BORDER};
                border-right: 1px solid {AppStyles.BORDER};
                border-bottom: 1px solid {AppStyles.BORDER};
                padding: 6px 10px;
            }}
            QFrame:hover {{
                background-color: {AppStyles.BG_MEDIUM};
                border-color: {color};
            }}
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        icon_lbl.setStyleSheet("font-size: 12pt; background: transparent; border: none;")
        layout.addWidget(icon_lbl)

        info_lay = QVBoxLayout()
        info_lay.setSpacing(1)

        t_lbl = QLabel(title)
        t_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        t_lbl.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {color}; background: transparent; border: none;")
        info_lay.addWidget(t_lbl)

        d_lbl = QLabel(desc)
        d_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        d_lbl.setStyleSheet(f"font-size: 8pt; color: {AppStyles.TEXT_PRIMARY}; background: transparent; border: none;")
        d_lbl.setWordWrap(True)
        info_lay.addWidget(d_lbl)

        layout.addLayout(info_lay, 1)

        if callback:
            act_btn = QPushButton("İncele ➔")
            act_btn.setCursor(Qt.PointingHandCursor)
            act_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {color};
                    font-weight: bold;
                    font-size: 8pt;
                    background-color: {color}15;
                    border: 1px solid {color}40;
                    border-radius: 4px;
                    padding: 3px 8px;
                }}
                QPushButton:hover {{
                    background-color: {color};
                    color: white;
                }}
            """)
            act_btn.clicked.connect(self._trigger_action)
            layout.addWidget(act_btn)

        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._trigger_action()
        super().mousePressEvent(event)

    def _trigger_action(self):
        callback = self.notif.get('on_click')
        if callback:
            if self.parent_dialog:
                self.parent_dialog.accept()
            try:
                callback()
            except Exception as e:
                logger.error(f"Bildirim aksiyon hatası: {e}")



class NotificationsDialog(QDialog):
    """Zil ikonuna tıklandığında açılan modern bildirim penceresi"""

    def __init__(self, notifications: list, parent=None):
        super().__init__(parent)
        self.notifications = notifications or []
        self.setWindowTitle("🔔 Bildirimler & Uyarılar")
        self.setMinimumWidth(440)
        self.setMinimumHeight(340)
        self.resize(480, 390)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {AppStyles.BG_DARKEST};
                color: {AppStyles.TEXT_PRIMARY};
            }}
        """)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(14, 12, 14, 12)

        # 1. Başlık Çubuğu
        top_bar = QHBoxLayout()
        title_box = QHBoxLayout()
        title_box.setSpacing(6)

        title = QLabel("🔔 Bildirimler & Akıllı Hatırlatmalar")
        title.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        title_box.addWidget(title)

        count = len(self.notifications)
        badge_color = AppStyles.RED if count > 0 else AppStyles.GREEN
        badge = QLabel(f" {count} Adet ")
        badge.setStyleSheet(f"""
            background-color: {badge_color}25;
            color: {badge_color};
            border: 1px solid {badge_color}50;
            border-radius: 8px;
            font-size: 8pt;
            font-weight: bold;
            padding: 1px 5px;
        """)
        title_box.addWidget(badge)
        top_bar.addLayout(title_box)
        top_bar.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {AppStyles.TEXT_MUTED};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 5px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
            }}
        """)
        close_btn.clicked.connect(self.accept)
        top_bar.addWidget(close_btn)

        main_layout.addLayout(top_bar)

        # Ayırıcı çizgi
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {AppStyles.BORDER}; margin: 1px 0;")
        main_layout.addWidget(sep)

        # 2. Bildirim Listesi (Scroll Area)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        c_lay = QVBoxLayout(content)
        c_lay.setSpacing(4)
        c_lay.setContentsMargins(0, 2, 2, 2)

        if not self.notifications:
            empty_box = QFrame()
            empty_box.setStyleSheet(f"""
                QFrame {{
                    background-color: {AppStyles.BG_DARK};
                    border: 1px dashed {AppStyles.BORDER};
                    border-radius: 8px;
                    padding: 30px 15px;
                }}
            """)
            e_lay = QVBoxLayout(empty_box)
            e_lay.setSpacing(6)
            e_lay.setAlignment(Qt.AlignCenter)

            e_icon = QLabel("✅")
            e_icon.setStyleSheet("font-size: 24pt;")
            e_icon.setAlignment(Qt.AlignCenter)
            e_lay.addWidget(e_icon)

            e_title = QLabel("Her Şey Yolunda!")
            e_title.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {AppStyles.GREEN};")
            e_title.setAlignment(Qt.AlignCenter)
            e_lay.addWidget(e_title)

            e_sub = QLabel("Şu anda bekleyen ödeme, gecikmiş taksit veya kritik stok uyarısı bulunmuyor.")
            e_sub.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_MUTED};")
            e_sub.setAlignment(Qt.AlignCenter)
            e_lay.addWidget(e_sub)

            c_lay.addWidget(empty_box)
        else:
            for notif in self.notifications:
                w = NotificationItemWidget(notif, self)
                c_lay.addWidget(w)

        c_lay.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        # 3. Alt Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        ok_btn = QPushButton("Tamam")
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.PRIMARY};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 4px 16px;
                font-weight: bold;
                font-size: 8.5pt;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        ok_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(ok_btn)
        main_layout.addLayout(bottom_bar)

        self.setLayout(main_layout)
