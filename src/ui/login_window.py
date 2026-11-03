# src/ui/login_window.py
"""
Modern Giriş Ekranı - Parabol Tarzı Koyu Tema

İyileştirmeler:
- Şifre göster/gizle butonu (👁️ / 🙈)
- Caps Lock uyarısı (GERÇEK duruma göre)
- Enter tuşu ile alanlar arası geçiş
"""

import os
import sys
import ctypes
import subprocess

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFrame,
    QScrollArea, QToolButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPixmap, QPainter, QPalette
from PyQt5.QtWidgets import QApplication

from ..core.logger import logger
from ..core.database import db
from ..models.user import User
from ..core.version import APP_VERSION
from .styles import AppStyles


class LoginWindow(QMainWindow):
    """Modern koyu tema giriş ekranı"""

    login_successful = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        # Güvenlik & İzolasyon: Giriş ekranı açıldığında oturumu ve tenant'ı temizle
        try:
            db.clear_tenant()
        except Exception:
            pass

        self.setWindowTitle("☕ Muhasebe Uygulaması - Giriş")
        self.setMinimumSize(850, 520)

        # ── Siyah ekran önlemi ──
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(AppStyles.BG_DARKEST))
        palette.setColor(QPalette.Base, QColor(AppStyles.BG_DARKEST))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        self.icon_path = self._resolve_logo_path()
        self._current_mode = None
        self.stat_widgets = []

        # Güvenlik: Kaba kuvvet (brute-force) saldırı koruması
        self._failed_attempts = 0
        self._lockout_until = None
        self._lockout_timer = None

        central_widget = QWidget()
        central_widget.setAutoFillBackground(True)
        central_widget.setStyleSheet(f"background-color: {AppStyles.BG_DARKEST};")

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.left_panel = self.create_left_panel()
        main_layout.addWidget(self.left_panel, 1)

        self.right_panel = self.create_right_panel()
        main_layout.addWidget(self.right_panel, 1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.viewport().setAutoFillBackground(True)
        vp_palette = scroll_area.viewport().palette()
        vp_palette.setColor(QPalette.Window, QColor(AppStyles.BG_DARKEST))
        scroll_area.viewport().setPalette(vp_palette)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {AppStyles.BG_DARKEST};
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {AppStyles.BG_DARKEST};
            }}
            QScrollBar:vertical {{
                background: {AppStyles.BG_DARKEST};
                width: 7px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {AppStyles.BORDER};
                min-height: 25px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {AppStyles.PRIMARY};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: {AppStyles.BG_DARKEST};
                height: 7px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {AppStyles.BORDER};
                min-width: 25px;
                border-radius: 3px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {AppStyles.PRIMARY};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
                width: 0px;
            }}
        """)
        scroll_area.setWidget(central_widget)
        self.setCentralWidget(scroll_area)

        self.show()
        QApplication.processEvents()
        self.setWindowState(Qt.WindowMaximized)
        QTimer.singleShot(300, lambda: self.username_input.setFocus())

        # ✅ İlk açılışta Caps Lock durumunu kontrol et
        QTimer.singleShot(500, self._check_caps_lock)

    # ==================== CAPS LOCK KONTROLÜ ====================

    def _is_caps_lock_on(self) -> bool:
        """
        Caps Lock gerçekten açık mı? (Platforma özgü)

        - Windows: ctypes ile GetKeyState(0x14)
        - macOS: ioreg komutu
        - Linux: xset veya /sys/class/leds
        """
        try:
            if sys.platform == "win32":
                # Windows: GetKeyState
                # 0x14 = VK_CAPITAL
                # Dönüş değeri & 1 → Caps Lock açık mı
                return bool(ctypes.windll.user32.GetKeyState(0x14) & 1)

            elif sys.platform == "darwin":
                # macOS: ioreg
                try:
                    result = subprocess.run(
                        ["ioreg", "-G", "-c", "IOHIDSystem"],
                        capture_output=True, text=True, timeout=0.5
                    )
                    return "CapsLock" in result.stdout
                except Exception:
                    return False

            else:
                # Linux: önce xset, sonra /sys/class/leds
                try:
                    result = subprocess.run(
                        ["xset", "q"],
                        capture_output=True, text=True, timeout=0.5
                    )
                    return "Caps Lock:   on" in result.stdout
                except Exception:
                    # Fallback: /sys/class/leds
                    for led in [
                        "/sys/class/leds/input::capslock/brightness",
                        "/sys/class/leds/capslock/brightness"
                    ]:
                        if os.path.exists(led):
                            try:
                                with open(led, "r") as f:
                                    return f.read().strip() == "1"
                            except Exception:
                                pass
                    return False

        except Exception as e:
            logger.debug(f"Caps Lock kontrol hatası: {e}")
            return False

    def _check_caps_lock(self):
        """Caps Lock durumunu kontrol et ve uyarıyı göster/gizle"""
        try:
            is_on = self._is_caps_lock_on()
            self.caps_warning.setVisible(is_on)
        except Exception:
            self.caps_warning.setVisible(False)

    def keyPressEvent(self, event):
        """Tuşa basıldığında Caps Lock kontrolü"""
        if event.key() == Qt.Key_CapsLock:
            # Caps Lock tuşuna basıldı → 50ms sonra gerçek durumu kontrol et
            # (OS'nin durumu güncellemesi için kısa bir gecikme)
            QTimer.singleShot(50, self._check_caps_lock)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Tuş bırakıldığında Caps Lock kontrolü"""
        if event.key() == Qt.Key_CapsLock:
            QTimer.singleShot(50, self._check_caps_lock)
        super().keyReleaseEvent(event)

    # ==================== YARDIMCILAR ====================

    def _resolve_logo_path(self) -> str:
        """Logo dosyasını hem geliştirme hem derlenmiş .exe ortamında arar"""
        candidates = [
            os.path.join(os.path.dirname(__file__), "assets", "logo.png"),
            os.path.join(os.path.dirname(sys.executable), "src", "ui", "assets", "logo.png"),
            os.path.join(os.path.dirname(sys.executable), "_internal", "src", "ui", "assets", "logo.png"),
            os.path.join(getattr(sys, '_MEIPASS', ''), "src", "ui", "assets", "logo.png"),
            os.path.join(os.path.dirname(sys.executable), "resources", "icons", "app.png"),
            "src/ui/assets/logo.png",
            "resources/icons/app.png",
        ]
        for p in candidates:
            if p and os.path.exists(p):
                return p
        return os.path.join(os.path.dirname(__file__), "assets", "logo.png")

    def center_window(self):
        screen = self.screen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _load_colored_icon(self, path: str, size: int = 110, color: str = "#ffffff") -> QPixmap:
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

    def create_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0d0d0f, stop:1 #242430);
            }
        """)

        self.left_layout = QVBoxLayout(panel)
        self.left_layout.setSpacing(0)
        self.left_layout.addStretch(1)

        # Logo + Başlık
        self.header_layout = QHBoxLayout()
        self.header_layout.setAlignment(Qt.AlignCenter)

        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setStyleSheet("background: transparent; border: none;")
        self.header_layout.addWidget(self.logo, alignment=Qt.AlignVCenter)

        self.brand_title = QLabel("ARI FIRIN")
        self.brand_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.header_layout.addWidget(self.brand_title, alignment=Qt.AlignVCenter)

        self.left_layout.addLayout(self.header_layout)
        self.left_layout.addSpacing(6)

        # Dekoratif çizgi
        self.divider = QFrame()
        self.divider.setFixedHeight(2)
        self.divider.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 transparent,
                    stop:0.5 #4a9eff,
                    stop:1 transparent);
                border: none;
            }
        """)
        self.left_layout.addWidget(self.divider, alignment=Qt.AlignCenter)
        self.left_layout.addSpacing(8)

        self.brand_subtitle = QLabel("HALİTOĞULLARI")
        self.brand_subtitle.setAlignment(Qt.AlignCenter)
        self.left_layout.addWidget(self.brand_subtitle)
        self.left_layout.addSpacing(2)

        self.since_label = QLabel("1976'dan beri...")
        self.since_label.setAlignment(Qt.AlignCenter)
        self.left_layout.addWidget(self.since_label)
        self.left_layout.addStretch(2)

        # İstatistikler
        self.stats_layout = QHBoxLayout()
        stats = [
            ("📊", "Sınırsız", "Şube"),
            ("💰", "1M+", "İşlem"),
            ("👥", "100+", "Kullanıcı")
        ]

        for icon, value, label in stats:
            stat_widget = QFrame()
            stat_layout = QVBoxLayout(stat_widget)

            icon_lbl = QLabel(icon)
            icon_lbl.setAlignment(Qt.AlignCenter)
            stat_layout.addWidget(icon_lbl)

            value_lbl = QLabel(value)
            value_lbl.setAlignment(Qt.AlignCenter)
            stat_layout.addWidget(value_lbl)

            label_lbl = QLabel(label)
            label_lbl.setAlignment(Qt.AlignCenter)
            stat_layout.addWidget(label_lbl)

            self.stats_layout.addWidget(stat_widget)
            self.stat_widgets.append((stat_widget, stat_layout, icon_lbl, value_lbl, label_lbl, value))

        self.left_layout.addLayout(self.stats_layout)
        self.left_layout.addStretch(1)

        self.version_lbl = QLabel(f"v{APP_VERSION} • 2026")
        self.version_lbl.setAlignment(Qt.AlignCenter)
        self.left_layout.addWidget(self.version_lbl)

        return panel

    def create_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background-color: {AppStyles.BG_DARK};")

        self.right_layout = QVBoxLayout(panel)
        self.right_layout.addStretch()

        self.welcome_title = QLabel("👋 Hoş Geldiniz")
        self.right_layout.addWidget(self.welcome_title)

        self.welcome_subtitle = QLabel("Devam etmek için giriş yapın")
        self.right_layout.addWidget(self.welcome_subtitle)

        # Kullanıcı Adı
        self.user_lbl = self.create_label("👤 Kullanıcı Adı")
        self.right_layout.addWidget(self.user_lbl)
        self.username_input = self.create_input("Kullanıcı adınızı girin")
        self.username_input.textChanged.connect(self.clear_message)
        self.username_input.returnPressed.connect(self._focus_password)
        self.right_layout.addWidget(self.username_input)

        # Şifre (Göster/Gizle butonlu)
        self.pass_lbl = self.create_label("🔒 Şifre")
        self.right_layout.addWidget(self.pass_lbl)

        password_container = QWidget()
        password_container.setStyleSheet("background: transparent; border: none;")
        password_row = QHBoxLayout(password_container)
        password_row.setContentsMargins(0, 0, 0, 0)
        password_row.setSpacing(6)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Şifrenizi girin")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(48)
        self.password_input.setStyleSheet(self._input_style())
        # ✅ Şifre değiştiğinde Caps Lock kontrolü
        self.password_input.textChanged.connect(self._on_password_changed)
        self.password_input.returnPressed.connect(self.login)

        self.toggle_password_btn = QToolButton()
        self.toggle_password_btn.setText("👁️")
        self.toggle_password_btn.setCheckable(True)
        self.toggle_password_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_password_btn.setFixedSize(48, 48)
        self.toggle_password_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                font-size: 14pt;
            }}
            QToolButton:hover {{ background-color: {AppStyles.BG_LIGHT}; }}
            QToolButton:checked {{
                background-color: {AppStyles.BG_LIGHT};
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        self.toggle_password_btn.toggled.connect(self._toggle_password_visibility)

        password_row.addWidget(self.password_input, 1)
        password_row.addWidget(self.toggle_password_btn, 0)

        self.right_layout.addWidget(password_container)

        # ⭐ Caps Lock uyarısı
        self.caps_warning = QLabel("⚠️ Caps Lock açık!")
        self.caps_warning.setStyleSheet(
            f"color: #f59e0b; font-size: 9pt; background: transparent; border: none;"
        )
        self.caps_warning.setVisible(False)
        self.right_layout.addWidget(self.caps_warning)

        # Şifremi unuttum
        forgot_layout = QHBoxLayout()
        forgot_layout.addStretch()
        self.forgot_btn = QPushButton("🔑 Şifremi Unuttum?")
        self.forgot_btn.setCursor(Qt.PointingHandCursor)
        self.forgot_btn.clicked.connect(self.open_forgot_password)
        forgot_layout.addWidget(self.forgot_btn)
        self.right_layout.addLayout(forgot_layout)

        self.right_layout.addSpacing(6)

        self.login_btn = QPushButton("🚀 GİRİŞ YAP")
        self.login_btn.clicked.connect(self.login)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.right_layout.addWidget(self.login_btn)

        # Kayıt ol linki
        register_layout = QHBoxLayout()
        register_layout.addStretch()
        self.register_text = QLabel("Hesabınız yok mu?")
        register_layout.addWidget(self.register_text)

        self.register_btn = QPushButton("Üye Ol")
        self.register_btn.setCursor(Qt.PointingHandCursor)
        self.register_btn.clicked.connect(self.go_to_register)
        register_layout.addWidget(self.register_btn)
        register_layout.addStretch()
        self.right_layout.addLayout(register_layout)

        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setMinimumHeight(30)
        self.message_label.setStyleSheet(
            f"color: {AppStyles.RED}; background: transparent; "
            "border: none; font-size: 9.5pt; font-weight: bold;"
        )
        self.right_layout.addWidget(self.message_label)

        self.right_layout.addStretch()
        return panel

    def _input_style(self) -> str:
        """Standart input stili"""
        return f"""
            QLineEdit {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 0px 14px;
                color: {AppStyles.TEXT_PRIMARY};
                font-size: 11pt;
            }}
            QLineEdit:focus {{
                border: 2px solid {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """

    def _focus_password(self):
        """Enter'a basınca şifre alanına odaklan"""
        self.password_input.setFocus()

    def _toggle_password_visibility(self, checked: bool):
        """Şifre göster/gizle"""
        self.password_input.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self.toggle_password_btn.setText("🙈" if checked else "👁️")

    def _on_password_changed(self):
        """Şifre yazılırken Caps Lock kontrolü"""
        self.clear_message()
        self._check_caps_lock()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, 'left_layout') or not hasattr(self, 'welcome_title'):
            return
        self._update_responsive_layout()

    def _update_responsive_layout(self, force: bool = False):
        """Pencere boyutuna göre responsive"""
        if not hasattr(self, 'left_layout') or not hasattr(self, 'welcome_title'):
            return

        is_large = self.width() >= 1100 and self.height() >= 620
        mode = "large" if is_large else "compact"
        if not force and mode == self._current_mode:
            return
        self._current_mode = mode

        if is_large:
            # BÜYÜK EKRAN
            self.left_layout.setContentsMargins(50, 40, 50, 40)
            self.header_layout.setSpacing(20)

            logo_px = self._load_colored_icon(self.icon_path, 130, "#ffffff")
            self.logo.setFixedSize(135, 135)
            if not logo_px.isNull():
                self.logo.setPixmap(logo_px)
            else:
                self.logo.setText("♨️\n☕")
                self.logo.setStyleSheet("font-size: 60pt; background: transparent; border: none;")

            self.brand_title.setStyleSheet("""
                font-size: 44pt; font-weight: bold;
                font-family: "Brush Script MT"; color: #ffffff;
                letter-spacing: 4px; background: transparent;
                border: none; padding-top: 25px;
            """)
            self.divider.setMaximumWidth(380)
            self.brand_subtitle.setStyleSheet("""
                font-size: 16pt; color: #cbd5e1; letter-spacing: 9px;
                font-weight: 700; background: transparent; border: none;
            """)
            self.since_label.setStyleSheet("""
                font-size: 13.5pt; color: #94a3b8; font-style: italic;
                font-family: "Brush Script MT"; letter-spacing: 2.5px;
                background: transparent; border: none;
            """)

            self.stats_layout.setSpacing(14)
            for w, sl, il, vl, ll, val in self.stat_widgets:
                w.setStyleSheet("""
                    QFrame {
                        background-color: rgba(148, 163, 184, 0.08);
                        border: 1px solid rgba(148, 163, 184, 0.25);
                        border-radius: 12px;
                        padding: 16px 12px;
                    }
                """)
                sl.setContentsMargins(4, 10, 4, 10)
                sl.setSpacing(6)
                il.setStyleSheet("font-size: 24pt; background: transparent; border: none;")
                fs = "17pt" if len(val) > 4 else "20pt"
                vl.setStyleSheet(f"font-size: {fs}; font-weight: bold; color: #22c55e; background: transparent; border: none;")
                ll.setStyleSheet("font-size: 10.5pt; color: #94a3b8; background: transparent; border: none;")

            self.version_lbl.setStyleSheet("font-size: 10.5pt; color: #64748b; background: transparent; border: none;")

            self.right_layout.setContentsMargins(70, 50, 70, 50)
            self.right_layout.setSpacing(16)
            self.welcome_title.setStyleSheet(f"font-size: 32pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; background: transparent; border: none;")
            self.welcome_subtitle.setStyleSheet(f"font-size: 13.5pt; color: {AppStyles.TEXT_SECONDARY}; background: transparent; border: none; margin-bottom: 20px;")

            self.user_lbl.setStyleSheet(f"font-size: 12pt; font-weight: 600; color: {AppStyles.TEXT_SECONDARY}; background: transparent; border: none; margin-top: 8px;")
            self.pass_lbl.setStyleSheet(f"font-size: 12pt; font-weight: 600; color: {AppStyles.TEXT_SECONDARY}; background: transparent; border: none; margin-top: 8px;")

            self.username_input.setFixedHeight(52)
            self.password_input.setFixedHeight(52)
            self.toggle_password_btn.setFixedSize(52, 52)

            self.forgot_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {AppStyles.TEXT_SECONDARY};
                    font-size: 10.5pt; border: none; padding: 4px 6px;
                }}
                QPushButton:hover {{
                    color: {AppStyles.PRIMARY}; text-decoration: underline;
                }}
            """)
            self.login_btn.setFixedHeight(52)
            self.login_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                    color: #0d0d0f; font-size: 14pt; font-weight: bold;
                    border-radius: 10px; border: none; letter-spacing: 1px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
                }}
                QPushButton:disabled {{ background-color: {AppStyles.BORDER}; color: {AppStyles.TEXT_MUTED}; }}
            """)
            self.register_text.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 11pt; background: transparent; border: none;")
            self.register_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {AppStyles.PRIMARY}; font-size: 11pt; font-weight: bold; border: none; text-decoration: underline; padding: 5px; }}
                QPushButton:hover {{ color: {AppStyles.CYAN}; }}
            """)
        else:
            # KOMPAKT EKRAN
            self.left_layout.setContentsMargins(25, 18, 25, 18)
            self.header_layout.setSpacing(12)

            logo_px = self._load_colored_icon(self.icon_path, 80, "#ffffff")
            self.logo.setFixedSize(85, 85)
            if not logo_px.isNull():
                self.logo.setPixmap(logo_px)
            else:
                self.logo.setText("♨️\n☕")
                self.logo.setStyleSheet("font-size: 40pt; background: transparent; border: none;")

            self.brand_title.setStyleSheet("""
                font-size: 28pt; font-weight: bold;
                font-family: "Brush Script MT"; color: #ffffff;
                letter-spacing: 2px; background: transparent;
                border: none; padding-top: 10px;
            """)
            self.divider.setMaximumWidth(250)
            self.brand_subtitle.setStyleSheet("""
                font-size: 11pt; color: #94a3b8; letter-spacing: 5px;
                font-weight: 600; background: transparent; border: none;
            """)
            self.since_label.setStyleSheet("""
                font-size: 9.5pt; color: #64748b; font-style: italic;
                font-family: "Brush Script MT"; letter-spacing: 1.5px;
                background: transparent; border: none;
            """)

            self.stats_layout.setSpacing(8)
            for w, sl, il, vl, ll, val in self.stat_widgets:
                w.setStyleSheet("""
                    QFrame {
                        background-color: rgba(148, 163, 184, 0.08);
                        border: 1px solid rgba(148, 163, 184, 0.25);
                        border-radius: 10px;
                        padding: 8px 4px;
                    }
                """)
                sl.setContentsMargins(2, 6, 2, 6)
                sl.setSpacing(3)
                il.setStyleSheet("font-size: 16pt; background: transparent; border: none;")
                fs = "13pt" if len(val) > 4 else "15pt"
                vl.setStyleSheet(f"font-size: {fs}; font-weight: bold; color: #22c55e; background: transparent; border: none;")
                ll.setStyleSheet("font-size: 8.5pt; color: #94a3b8; background: transparent; border: none;")

            self.version_lbl.setStyleSheet("font-size: 8.5pt; color: #64748b; background: transparent; border: none;")

            self.right_layout.setContentsMargins(40, 24, 40, 24)
            self.right_layout.setSpacing(10)
            self.welcome_title.setStyleSheet(f"font-size: 21pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; background: transparent; border: none;")
            self.welcome_subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY}; background: transparent; border: none; margin-bottom: 8px;")

            self.user_lbl.setStyleSheet(f"font-size: 9.5pt; font-weight: 600; color: {AppStyles.TEXT_SECONDARY}; background: transparent; border: none; margin-top: 4px;")
            self.pass_lbl.setStyleSheet(f"font-size: 9.5pt; font-weight: 600; color: {AppStyles.TEXT_SECONDARY}; background: transparent; border: none; margin-top: 4px;")

            self.username_input.setFixedHeight(44)
            self.password_input.setFixedHeight(44)
            self.toggle_password_btn.setFixedSize(44, 44)

            self.forgot_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {AppStyles.TEXT_SECONDARY};
                    font-size: 9pt; border: none; padding: 2px;
                }}
                QPushButton:hover {{
                    color: {AppStyles.PRIMARY}; text-decoration: underline;
                }}
            """)
            self.login_btn.setFixedHeight(46)
            self.login_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                    color: #0d0d0f; font-size: 11.5pt; font-weight: bold;
                    border-radius: 8px; border: none; letter-spacing: 0.5px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
                }}
                QPushButton:disabled {{ background-color: {AppStyles.BORDER}; color: {AppStyles.TEXT_MUTED}; }}
            """)
            self.register_text.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9.5pt; background: transparent; border: none;")
            self.register_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {AppStyles.PRIMARY}; font-size: 9.5pt; font-weight: bold; border: none; text-decoration: underline; padding: 2px; }}
                QPushButton:hover {{ color: {AppStyles.CYAN}; }}
            """)

    def create_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"font-size: 10pt; font-weight: 600; color: {AppStyles.TEXT_SECONDARY}; background: transparent; border: none; margin-top: 5px;")
        return label

    def create_input(self, placeholder: str, is_password: bool = False) -> QLineEdit:
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        if is_password:
            inp.setEchoMode(QLineEdit.Password)
        inp.setMinimumHeight(48)
        inp.setStyleSheet(self._input_style())
        return inp

    def clear_message(self):
        self.message_label.setText("")

    def login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username:
            self.show_message("❌ Kullanıcı adı giriniz!", "danger")
            self.username_input.setFocus()
            return

        if not password:
            self.show_message("❌ Şifre giriniz!", "danger")
            self.password_input.setFocus()
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("⏳ Giriş yapılıyor...")

        # Kaba kuvvet (brute-force) kilit kontrolü
        if self._lockout_until and datetime.now() < self._lockout_until:
            remaining = max(1, int((self._lockout_until - datetime.now()).total_seconds()))
            self.show_message(f"🔒 Çok fazla başarısız deneme! Lütfen {remaining} saniye bekleyin.", "danger")
            self.login_btn.setText(f"🔒 Kilitlendi ({remaining}s)")
            return

        try:
            user = User.get_by_username(username)

            # Kullanıcı adı veya şifre hatalı kontrolü (User Enumeration & Brute-force önleme)
            if not user or not user.authenticate(password):
                self._failed_attempts += 1
                if user:
                    logger.warning(f"❌ Başarısız giriş - Yanlış şifre: {username} (Deneme: {self._failed_attempts}/5)")
                else:
                    logger.warning(f"❌ Başarısız giriş - Kullanıcı yok: {username} (Deneme: {self._failed_attempts}/5)")

                if self._failed_attempts >= 5:
                    self.show_message("🔒 5 kez hatalı giriş yapıldı! Giriş 60 saniye süreyle kilitlendi.", "danger")
                    self._start_lockout(60)
                else:
                    kalan = 5 - self._failed_attempts
                    self.show_message(f"❌ Kullanıcı adı veya şifre hatalı! (Kalan hak: {kalan})", "danger")
                    self.reset_button()
                return

            if not user.is_active:
                self.show_message("❌ Hesabınız devre dışı bırakılmıştır. Lütfen sistem yöneticisine başvurun.", "danger")
                self.reset_button()
                return

            # Başarılı girişte deneme sayacını sıfırla
            self._failed_attempts = 0
            self._lockout_until = None
            if self._lockout_timer and self._lockout_timer.isActive():
                self._lockout_timer.stop()

            # Multi-Tenant İzolasyon: Giriş yapan kullanıcının özel şemasını hemen aktif et ve hazırla
            tenant_schema = user.get_tenant_schema()
            db.set_tenant(tenant_schema)
            db.ensure_tenant_schema(tenant_schema)

            user.set_online(True)
            logger.info(f"✅ Kullanıcı giriş yaptı: {username} (Tenant: {tenant_schema})")

            self.show_message(f"✅ Hoş geldiniz, {user.full_name}!", "success")
            self.login_btn.setText("✅ Giriş Başarılı")

            QTimer.singleShot(80, lambda: self._emit_login(user))
        except Exception as e:
            logger.error(f"❌ Giriş hatası: {e}")
            # Yarım kalan girişte aktif kullanıcı alanını temizle (başka verilere düşmeyi önler)
            try:
                db.clear_tenant()
            except Exception:
                pass
            self.show_message(f"❌ Sistem Hatası: {str(e)}", "danger")
            self.reset_button()

    def _start_lockout(self, duration_seconds: int = 60):
        # Kaba kuvvet koruma kilidini baslatir
        self._lockout_until = datetime.now() + timedelta(seconds=duration_seconds)
        self._remaining_lockout = duration_seconds
        self.login_btn.setEnabled(False)
        self.login_btn.setText(f"🔒 Kilitlendi ({self._remaining_lockout}s)")

        if self._lockout_timer is None:
            self._lockout_timer = QTimer(self)
            self._lockout_timer.timeout.connect(self._update_lockout_timer)
        self._lockout_timer.start(1000)

    def _update_lockout_timer(self):
        self._remaining_lockout -= 1
        if self._remaining_lockout > 0:
            self.login_btn.setText(f"🔒 Kilitlendi ({self._remaining_lockout}s)")
        else:
            if self._lockout_timer:
                self._lockout_timer.stop()
            self._lockout_until = None
            self.reset_button()
            self.show_message("Giriş kilidi açıldı. Lütfen tekrar deneyin.", "info")

    def reset_button(self):
        self.login_btn.setEnabled(True)
        self.login_btn.setText("🚀 GİRİŞ YAP")

    def _emit_login(self, user):
        self.login_successful.emit(user)

    def show_message(self, message: str, message_type: str = "info"):
        colors = {
            "info": AppStyles.PRIMARY,
            "success": AppStyles.GREEN,
            "warning": AppStyles.ORANGE,
            "danger": AppStyles.RED
        }
        self.message_label.setStyleSheet(
            f"color: {colors.get(message_type, '#fff')}; "
            "background: transparent; border: none; font-size: 10pt; font-weight: bold;"
        )
        self.message_label.setText(message)

    def go_to_register(self):
        from .register_window import RegisterWindow
        self.register_window = RegisterWindow(login_window_factory=self._restore_from_register)
        self.register_window.register_successful.connect(self._on_register_success)
        self.register_window.show()
        self.hide()

    def _restore_from_register(self):
        self.show()
        return self

    def _on_register_success(self):
        self.show()
        self.clear_message()
        reg_username = getattr(self.register_window, 'registered_username', None)
        if reg_username:
            self.username_input.setText(reg_username)
        self.password_input.clear()
        self.password_input.setFocus()
        self.show_message("🎉 Kayıt başarılı! Lütfen şifrenizi girerek giriş yapınız.", "success")

    def open_forgot_password(self):
        from .forgot_password_window import ForgotPasswordDialog
        initial_val = self.username_input.text().strip()
        dialog = ForgotPasswordDialog(self, initial_identifier=initial_val)
        dialog.password_reset_successful.connect(self._on_password_reset_success)
        dialog.exec_()

    def _on_password_reset_success(self, username: str):
        self.username_input.setText(username)
        self.password_input.clear()
        self.password_input.setFocus()
        self.show_message("✅ Şifreniz sıfırlandı. Yeni şifrenizle giriş yapabilirsiniz!", "success")