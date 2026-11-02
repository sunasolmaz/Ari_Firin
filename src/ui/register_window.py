# src/ui/register_window.py
"""
Modern Kayıt Ekranı - Parabol Tarzı Koyu Tema
PostgreSQL Multi-Tenant mimarisi ile tam uyumlu.
"""

import os
import re
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFrame,
    QCheckBox, QScrollArea, QComboBox, QApplication,
    QProgressBar, QToolButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QColor, QPixmap, QPainter, QPalette

from ..core.logger import logger
from ..models.user import User
from ..models.branch import Branch
from .styles import AppStyles


# ═══════════════════════════════════════════════════════════════════
#  SABİTLER
# ═══════════════════════════════════════════════════════════════════

class RegisterConfig:
    WINDOW_MIN_WIDTH = 1000
    WINDOW_MIN_HEIGHT = 700
    INPUT_MIN_HEIGHT = 45
    FOCUS_DELAY_MS = 300
    MIN_FULLNAME_LEN = 3
    MIN_USERNAME_LEN = 3
    RATE_LIMIT_SECONDS = 2

    COLOR_ERROR = "#ef4444"
    COLOR_WARN = "#f59e0b"
    COLOR_OK = "#22c55e"

    USERNAME_RE = re.compile(r'^[a-zA-Z0-9._]+$')
    EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_RE = re.compile(r'^0?5\d{9}$')


@dataclass
class RegisterData:
    full_name: str
    username: str
    email: Optional[str]
    phone: Optional[str]
    password: str
    password_confirm: str
    branch_id: Optional[int]
    branch_name: str
    terms_accepted: bool


# ═══════════════════════════════════════════════════════════════════
#  VALİDASYON
# ═══════════════════════════════════════════════════════════════════

class RegisterValidator:
    """Kayıt verilerini doğrular (UI'dan bağımsız)."""

    @staticmethod
    def validate(data: RegisterData) -> Tuple[bool, Optional[str], Optional[str]]:
        if not data.full_name or len(data.full_name) < RegisterConfig.MIN_FULLNAME_LEN:
            return False, f"Ad Soyad en az {RegisterConfig.MIN_FULLNAME_LEN} karakter olmalıdır!", "full_name"

        if not data.username or len(data.username) < RegisterConfig.MIN_USERNAME_LEN:
            return False, f"Kullanıcı adı en az {RegisterConfig.MIN_USERNAME_LEN} karakter olmalıdır!", "username"

        if not RegisterConfig.USERNAME_RE.match(data.username):
            return False, "Kullanıcı adı sadece harf, rakam, nokta ve alt çizgi içerebilir!", "username"

        if data.email and not RegisterConfig.EMAIL_RE.match(data.email):
            return False, "Geçersiz email formatı!", "email"

        if data.phone:
            cleaned = data.phone.replace(" ", "").replace("-", "")
            if not RegisterConfig.PHONE_RE.match(cleaned):
                return False, "Geçersiz telefon formatı! (05XX XXX XX XX)", "phone"

        is_strong, msg = User.validate_password_strength(data.password)
        if not is_strong:
            return False, msg, "password"

        if data.password != data.password_confirm:
            return False, "Şifreler eşleşmiyor!", "password_confirm"

        if not data.terms_accepted:
            return False, "Kullanım koşullarını kabul etmelisiniz!", "terms"

        return True, None, None

    @staticmethod
    def password_strength(password: str) -> Tuple[int, str, str]:
        """Şifre gücü göstergesi için skor (0-5)"""
        if not password:
            return 0, "", "#333333"

        score = 0
        if len(password) >= 8:  score += 1
        if len(password) >= 12: score += 1
        if any(c.isupper() for c in password) and any(c.islower() for c in password): score += 1
        if any(c.isdigit() for c in password): score += 1
        if re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\/;`~]', password): score += 1

        score = min(score, 5)
        labels = ["", "Çok Zayıf", "Zayıf", "Orta", "Güçlü", "Çok Güçlü"]
        colors = ["#333333", "#ef4444", "#f59e0b", "#eab308", "#84cc16", "#22c55e"]
        return score, labels[score], colors[score]


# ═══════════════════════════════════════════════════════════════════
#  SERVİS
# ═══════════════════════════════════════════════════════════════════

class RegisterService:
    """Kullanıcı kaydı iş mantığı."""

    @staticmethod
    def register(data: RegisterData) -> Tuple[bool, Optional[str], Optional[User]]:
        try:
            if User.get_by_username(data.username):
                return False, "Bu kullanıcı adı zaten kullanılıyor!", None

            branch_id = data.branch_id
            if not branch_id:
                branches = Branch.get_all(active_only=True)
                if branches:
                    branch_id = branches[0].id

            # Multi-Tenant İzolasyon: Kayıt olan işletme sahibi kendi alanının yöneticisidir (Admin)
            role = 'Admin'

            user = User({
                'branch_id': branch_id,
                'username': data.username,
                'password_hash': User.hash_password(data.password),
                'full_name': data.full_name,
                'email': data.email or None,
                'phone': data.phone or None,
                'role': role,
                'is_active': True
            })

            if not user.save(branch_name=data.branch_name):
                return False, "Hesap oluşturulamadı!", None

            logger.info(f"✅ Yeni kullanıcı kaydedildi: {data.username} (rol: {user.role})")
            return True, None, user

        except Exception as e:
            logger.exception(f"❌ Kayıt hatası: {e}")
            return False, f"Sistem hatası: {str(e)}", None


# ═══════════════════════════════════════════════════════════════════
#  WORKER THREAD
# ═══════════════════════════════════════════════════════════════════

class RegisterWorker(QThread):
    finished_signal = pyqtSignal(bool, object, object)

    def __init__(self, data: RegisterData):
        super().__init__()
        self.data = data

    def run(self):
        success, error, user = RegisterService.register(self.data)
        self.finished_signal.emit(success, error, user)


# ═══════════════════════════════════════════════════════════════════
#  ANA PENCERE
# ═══════════════════════════════════════════════════════════════════

class RegisterWindow(QMainWindow):
    register_successful = pyqtSignal()

    def __init__(self, login_window_factory=None):
        super().__init__()
        self.login_window_factory = login_window_factory
        self.login_window = None
        self._last_register_time = 0.0
        self._worker: Optional[RegisterWorker] = None

        # ✅ ÖNCE branch_combo'yu None olarak tanımla
        self.branch_combo = None

        self.setWindowTitle("☕ Muhasebe Uygulaması - Kayıt Ol")
        self.setMinimumSize(RegisterConfig.WINDOW_MIN_WIDTH, RegisterConfig.WINDOW_MIN_HEIGHT)

        self._setup_palette()
        self._build_ui()
        self._setup_tab_order()
        self._connect_live_validators()

        self.show()
        QApplication.processEvents()
        self.setWindowState(Qt.WindowMaximized)
        QTimer.singleShot(RegisterConfig.FOCUS_DELAY_MS, self.full_name_input.setFocus)

    def _setup_palette(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(AppStyles.BG_DARKEST))
        palette.setColor(QPalette.Base, QColor(AppStyles.BG_DARKEST))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setAutoFillBackground(True)
        central.setStyleSheet(f"background-color: {AppStyles.BG_DARKEST};")

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._create_left_panel(), 1)
        main_layout.addWidget(self._create_right_panel(), 1)
        central.setLayout(main_layout)

    # ─────────── SOL PANEL ───────────

    def _create_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0d0d0f, stop:1 #242430);
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(15)

        header = QHBoxLayout()
        header.setSpacing(18)
        header.setAlignment(Qt.AlignCenter)

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(120, 120)
        logo.setStyleSheet("background: transparent; border: none;")

        icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
        pixmap = self._load_colored_icon(icon_path, 110, "#ffffff")
        if not pixmap.isNull():
            logo.setPixmap(pixmap)
        else:
            logo.setText("♨️\n☕")
            logo.setStyleSheet("font-size: 55pt; background: transparent; border: none;")
        header.addWidget(logo, alignment=Qt.AlignVCenter)

        title = QLabel("ARI FIRIN")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title.setStyleSheet("""
            font-size: 38pt; font-weight: bold;
            font-family: "Brush Script MT"; color: #ffffff;
            letter-spacing: 3px; background: transparent;
            border: none; padding-top: 25px;
        """)
        header.addWidget(title, alignment=Qt.AlignVCenter)
        layout.addLayout(header)

        layout.addSpacing(8)

        divider = QFrame()
        divider.setFixedHeight(2)
        divider.setMaximumWidth(320)
        divider.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 transparent, stop:0.5 #4a9eff, stop:1 transparent);
                border: none;
            }
        """)
        layout.addWidget(divider, alignment=Qt.AlignCenter)

        layout.addSpacing(12)

        subtitle = QLabel("HALİTOĞULLARI")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            font-size: 13pt; color: #94a3b8; letter-spacing: 8px;
            font-weight: 600; background: transparent; border: none;
        """)
        layout.addWidget(subtitle)

        layout.addSpacing(4)

        since_label = QLabel("1976'dan beri...")
        since_label.setAlignment(Qt.AlignCenter)
        since_label.setStyleSheet("""
            font-size: 11pt; color: #64748b; font-style: italic;
            font-family: "Brush Script MT"; letter-spacing: 2px;
            background: transparent; border: none;
        """)
        layout.addWidget(since_label)

        layout.addStretch(2)

        welcome = QLabel("Neden Bize Katılmalısınız?")
        welcome.setStyleSheet(
            "font-size: 14pt; font-weight: bold; color: #f9fafb; "
            "background: transparent; border: none; margin-bottom: 10px;"
        )
        layout.addWidget(welcome)

        features = [
            ("🚀", "Hızlı ve Modern Arayüz"),
            ("📊", "Detaylı Raporlama Sistemi"),
            ("🔒", "Güvenli Veri Saklama"),
            ("📱", "Çoklu Şube Yönetimi"),
            ("💾", "Otomatik Yedekleme"),
            ("📈", "Grafik ve Analizler"),
        ]
        for icon, text in features:
            item = QHBoxLayout()
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet("font-size: 14pt; background: transparent; border: none;")
            item.addWidget(icon_lbl)
            text_lbl = QLabel(text)
            text_lbl.setStyleSheet(
                "font-size: 10pt; color: #cbd5e1; background: transparent; "
                "border: none; padding-left: 8px;"
            )
            item.addWidget(text_lbl)
            item.addStretch()
            layout.addLayout(item)

        layout.addStretch()

        version = QLabel("v1.0.0 • 2026")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("font-size: 9pt; color: #64748b; background: transparent; border: none;")
        layout.addWidget(version)

        panel.setLayout(layout)
        return panel

    # ─────────── SAĞ PANEL ───────────

    def _create_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background-color: {AppStyles.BG_DARK};")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {AppStyles.BG_DARK}; }}")

        content = QWidget()
        content.setStyleSheet(f"background-color: {AppStyles.BG_DARK};")

        layout = QVBoxLayout()
        layout.setContentsMargins(50, 40, 50, 40)
        layout.setSpacing(12)

        title = QLabel("✨ Üye Ol")
        title.setStyleSheet(
            f"font-size: 26pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; "
            "background: transparent; border: none;"
        )
        layout.addWidget(title)

        subtitle = QLabel("Hesap oluşturmak için bilgilerinizi girin")
        subtitle.setStyleSheet(
            f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY}; "
            "background: transparent; border: none; margin-bottom: 15px;"
        )
        layout.addWidget(subtitle)

        # Ad Soyad
        layout.addWidget(self._create_label("👤 Ad Soyad *"))
        self.full_name_input = self._create_input("Adınızı ve soyadınızı girin", "Ad Soyad")
        layout.addWidget(self.full_name_input)

        # Şube
        layout.addWidget(self._create_label("☕ Şube *"))
        self.branch_combo = self._create_branch_combo()
        layout.addWidget(self.branch_combo)

        # Kullanıcı Adı
        layout.addWidget(self._create_label("🔑 Kullanıcı Adı *"))
        self.username_input = self._create_input("Kullanıcı adınızı girin", "Kullanıcı Adı")
        layout.addWidget(self.username_input)

        # Email
        layout.addWidget(self._create_label("📧 Email"))
        self.email_input = self._create_input("ornek@email.com", "Email")
        layout.addWidget(self.email_input)

        # Telefon
        layout.addWidget(self._create_label("📞 Telefon"))
        self.phone_input = self._create_input("05XX XXX XX XX", "Telefon")
        layout.addWidget(self.phone_input)

        # Şifre
        layout.addWidget(self._create_label("🔒 Şifre *"))
        pwd_row = self._create_password_row("En az 8 karakter")
        self.password_input = pwd_row["input"]
        layout.addWidget(pwd_row["container"])

        # Şifre gücü
        strength_container = QWidget()
        strength_layout = QVBoxLayout(strength_container)
        strength_layout.setContentsMargins(0, 0, 0, 0)
        strength_layout.setSpacing(4)

        self.strength_bar = QProgressBar()
        self.strength_bar.setRange(0, 5)
        self.strength_bar.setValue(0)
        self.strength_bar.setTextVisible(False)
        self.strength_bar.setFixedHeight(6)
        self.strength_bar.setStyleSheet("""
            QProgressBar { background-color: #1f2937; border: none; border-radius: 3px; }
            QProgressBar::chunk { background-color: #333333; border-radius: 3px; }
        """)
        strength_layout.addWidget(self.strength_bar)

        self.strength_label = QLabel("")
        self.strength_label.setStyleSheet(
            "font-size: 9pt; color: #64748b; background: transparent; border: none;"
        )
        strength_layout.addWidget(self.strength_label)
        layout.addWidget(strength_container)

        # Şifre Tekrar
        layout.addWidget(self._create_label("🔒 Şifre Tekrar *"))
        confirm_row = self._create_password_row("Şifrenizi tekrar girin")
        self.password_confirm_input = confirm_row["input"]
        self.password_confirm_input.returnPressed.connect(self.register)
        layout.addWidget(confirm_row["container"])

        # Caps Lock uyarısı
        self.caps_warning = QLabel("⚠️ Caps Lock açık!")
        self.caps_warning.setStyleSheet(
            f"color: {RegisterConfig.COLOR_WARN}; font-size: 9pt; "
            "background: transparent; border: none;"
        )
        self.caps_warning.setVisible(False)
        layout.addWidget(self.caps_warning)

        # Koşullar
        terms_row = QHBoxLayout()
        self.terms_check = QCheckBox("Kullanım koşullarını kabul ediyorum")
        self.terms_check.setStyleSheet(f"""
            QCheckBox {{ color: {AppStyles.TEXT_SECONDARY}; font-size: 10pt;
                spacing: 8px; margin-top: 8px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px;
                border: 2px solid {AppStyles.BORDER_LIGHT};
                background-color: {AppStyles.BG_MEDIUM}; }}
            QCheckBox::indicator:checked {{ background-color: {AppStyles.PRIMARY};
                border-color: {AppStyles.PRIMARY}; }}
        """)
        terms_row.addWidget(self.terms_check)

        terms_link = QLabel('<a href="#" style="color: #4a9eff; text-decoration: underline;">Koşulları oku</a>')
        terms_link.setStyleSheet("background: transparent; border: none; margin-top: 8px;")
        terms_row.addWidget(terms_link)
        terms_row.addStretch()
        layout.addLayout(terms_row)

        layout.addSpacing(8)

        # Kayıt butonu
        self.register_btn = QPushButton("✨ HESAP OLUŞTUR")
        self.register_btn.clicked.connect(self.register)
        self.register_btn.setMinimumHeight(48)
        self.register_btn.setCursor(Qt.PointingHandCursor)
        self.register_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                color: #0d0d0f; font-size: 12pt; font-weight: bold;
                border-radius: 10px; border: none; letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
            }}
            QPushButton:disabled {{ background: #374151; color: #9ca3af; }}
        """)
        layout.addWidget(self.register_btn)

        # Giriş linki
        login_layout = QHBoxLayout()
        login_layout.addStretch()
        login_text = QLabel("Zaten hesabınız var mı?")
        login_text.setStyleSheet(
            f"color: {AppStyles.TEXT_SECONDARY}; font-size: 10pt; "
            "background: transparent; border: none;"
        )
        login_layout.addWidget(login_text)

        login_btn = QPushButton("Giriş Yap")
        login_btn.setCursor(Qt.PointingHandCursor)
        login_btn.clicked.connect(self.go_to_login)
        login_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {AppStyles.PRIMARY};
                font-size: 10pt; font-weight: bold; border: none;
                text-decoration: underline; padding: 5px; }}
            QPushButton:hover {{ color: {AppStyles.CYAN}; }}
        """)
        login_layout.addWidget(login_btn)
        login_layout.addStretch()
        layout.addLayout(login_layout)

        # Mesaj alanı
        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setMinimumHeight(30)
        self.message_label.setStyleSheet(
            f"color: {RegisterConfig.COLOR_ERROR}; background: transparent; "
            "border: none; font-size: 10pt; font-weight: bold;"
        )
        layout.addWidget(self.message_label)

        layout.addStretch()

        content.setLayout(layout)
        scroll.setWidget(content)

        wrapper = QVBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(scroll)
        panel.setLayout(wrapper)
        return panel

    # ─────────── WIDGET FABRİKALARI ───────────

    def _create_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"font-size: 10pt; font-weight: 600; color: {AppStyles.TEXT_SECONDARY}; "
            "background: transparent; border: none; margin-top: 5px;"
        )
        return label

    def _create_input(self, placeholder: str, accessible: str = "") -> QLineEdit:
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setMinimumHeight(RegisterConfig.INPUT_MIN_HEIGHT)
        if accessible:
            inp.setAccessibleName(accessible)
        inp.setStyleSheet(self._input_style())
        return inp

    def _input_style(self, border_color: Optional[str] = None) -> str:
        border = border_color or AppStyles.BORDER
        return f"""
            QLineEdit {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 10px 15px;
                color: {AppStyles.TEXT_PRIMARY};
                font-size: 11pt;
            }}
            QLineEdit:focus {{
                border: 1px solid {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """

    def _create_password_row(self, placeholder: str) -> dict:
        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setEchoMode(QLineEdit.Password)
        inp.setMinimumHeight(RegisterConfig.INPUT_MIN_HEIGHT)
        inp.setStyleSheet(self._input_style())

        toggle = QToolButton()
        toggle.setText("👁️")
        toggle.setCheckable(True)
        toggle.setCursor(Qt.PointingHandCursor)
        toggle.setFixedSize(45, RegisterConfig.INPUT_MIN_HEIGHT)
        toggle.setStyleSheet(f"""
            QToolButton {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                font-size: 14pt;
            }}
            QToolButton:hover {{ background-color: {AppStyles.BG_LIGHT}; }}
            QToolButton:checked {{ background-color: {AppStyles.PRIMARY}; }}
        """)

        def _toggle_visibility(checked):
            inp.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
            toggle.setText("🙈" if checked else "👁️")

        toggle.toggled.connect(_toggle_visibility)

        row.addWidget(inp, 1)
        row.addWidget(toggle, 0)
        return {"container": container, "input": inp, "toggle": toggle}

    def _create_branch_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setMinimumHeight(42)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 5px 12px;
                font-size: 10pt;
            }}
            QComboBox QAbstractItemView {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                selection-background-color: {AppStyles.PRIMARY};
            }}
        """)
        # ✅ DÜZELTME: populate_branches'e combo'yu parametre olarak geç
        self._populate_branches_into(combo)
        return combo

    def _populate_branches_into(self, combo: QComboBox):
        """Şubeleri verilen combo'ya doldur (güvenli versiyon)."""
        combo.clear()
        try:
            branches = Branch.get_all(active_only=True)
        except Exception as e:
            logger.error(f"Şube listesi alınamadı: {e}")
            branches = []

        if not branches:
            # Giriş öncesi ortak (public) şemaya şube YAZMA: yeni kullanıcının
            # şubeleri kayıt sırasında kendi izole şemasında oluşturulur.
            b = Branch({'name': 'Armada', 'city': 'Tekirdağ'})
            branches = [b]

        for branch in branches:
            city_str = f" ({branch.city})" if branch.city else ""
            combo.addItem(f"☕ {branch.name}{city_str}", branch.id)

    # ─────────── TAB SIRASI ───────────

    def _setup_tab_order(self):
        self.setTabOrder(self.full_name_input, self.branch_combo)
        self.setTabOrder(self.branch_combo, self.username_input)
        self.setTabOrder(self.username_input, self.email_input)
        self.setTabOrder(self.email_input, self.phone_input)
        self.setTabOrder(self.phone_input, self.password_input)
        self.setTabOrder(self.password_input, self.password_confirm_input)
        self.setTabOrder(self.password_confirm_input, self.terms_check)
        self.setTabOrder(self.terms_check, self.register_btn)

        self.full_name_input.returnPressed.connect(self.branch_combo.setFocus)
        self.username_input.returnPressed.connect(self.email_input.setFocus)
        self.email_input.returnPressed.connect(self.phone_input.setFocus)
        self.phone_input.returnPressed.connect(self.password_input.setFocus)
        self.password_input.returnPressed.connect(self.password_confirm_input.setFocus)

    def _connect_live_validators(self):
        self.email_input.textChanged.connect(self._validate_email_live)
        self.password_input.textChanged.connect(self._update_password_strength)

    @pyqtSlot(str)
    def _validate_email_live(self, text: str):
        if not text:
            self.email_input.setStyleSheet(self._input_style())
        elif RegisterConfig.EMAIL_RE.match(text):
            self.email_input.setStyleSheet(self._input_style(RegisterConfig.COLOR_OK))
        else:
            self.email_input.setStyleSheet(self._input_style(RegisterConfig.COLOR_ERROR))

    @pyqtSlot(str)
    def _update_password_strength(self, text: str):
        score, label, color = RegisterValidator.password_strength(text)
        self.strength_bar.setValue(score)
        self.strength_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: #1f2937; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}
        """)
        self.strength_label.setText(label)
        self.strength_label.setStyleSheet(
            f"font-size: 9pt; color: {color}; background: transparent; border: none;"
        )

    # ─────────── KAYIT ───────────

    def register(self):
        now = time.time()
        if now - self._last_register_time < RegisterConfig.RATE_LIMIT_SECONDS:
            self.show_error("Çok hızlı deniyorsunuz, lütfen bekleyin.")
            return
        self._last_register_time = now

        data = self._collect_form_data()

        is_valid, error, field = RegisterValidator.validate(data)
        if not is_valid:
            self.show_error(error)
            self._focus_field(field)
            return

        self._set_loading(True)
        self._worker = RegisterWorker(data)
        self._worker.finished_signal.connect(self._on_register_finished)
        self._worker.start()

    def _collect_form_data(self) -> RegisterData:
        return RegisterData(
            full_name=self.full_name_input.text().strip(),
            username=self.username_input.text().strip(),
            email=self.email_input.text().strip(),
            phone=self.phone_input.text().strip(),
            password=self.password_input.text(),
            password_confirm=self.password_confirm_input.text(),
            branch_id=self.branch_combo.currentData(),
            branch_name=self.branch_combo.currentText().replace("☕", "").split("(")[0].strip(),
            terms_accepted=self.terms_check.isChecked()
        )

    def _focus_field(self, field: Optional[str]):
        mapping = {
            "full_name": self.full_name_input,
            "username": self.username_input,
            "email": self.email_input,
            "phone": self.phone_input,
            "password": self.password_input,
            "password_confirm": self.password_confirm_input,
            "terms": self.terms_check,
        }
        widget = mapping.get(field)
        if widget:
            widget.setFocus()

    @pyqtSlot(bool, object, object)
    def _on_register_finished(self, success: bool, error: Optional[str], user):
        self._set_loading(False)

        if not success:
            self.show_error(error or "Kayıt başarısız!")
            return

        logger.info(f"✅ Kayıt tamamlandı: {user.username}")
        QMessageBox.information(
            self, "Başarılı",
            f"🎉 Hesabınız oluşturuldu!\n\n"
            f"👤 Kullanıcı Adı: {user.username}\n"
            f"🔑 Şimdi giriş yapabilirsiniz."
        )
        self.registered_username = getattr(user, 'username', '')
        self.register_successful.emit()
        self.close()

    def _set_loading(self, loading: bool):
        self.register_btn.setEnabled(not loading)
        self.register_btn.setText("⏳ KAYDEDİLİYOR..." if loading else "✨ HESAP OLUŞTUR")

    # ─────────── YARDIMCILAR ───────────

    def _load_colored_icon(self, path: str, size: int = 110, color: str = "#ffffff") -> QPixmap:
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

    def show_error(self, message: str):
        self.message_label.setStyleSheet(
            f"color: {RegisterConfig.COLOR_ERROR}; background: transparent; "
            "border: none; font-size: 10pt; font-weight: bold;"
        )
        self.message_label.setText(f"❌ {message}")

    def populate_branches(self):
        """Geriye dönük uyumluluk için (dışarıdan çağrılırsa)."""
        if self.branch_combo is not None:
            self._populate_branches_into(self.branch_combo)

    def go_to_login(self):
        if self.login_window_factory:
            self.login_window = self.login_window_factory()
        else:
            from .login_window import LoginWindow
            self.login_window = LoginWindow()
        self.login_window.show()
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_CapsLock:
            self.caps_warning.setVisible(not self.caps_warning.isVisible())
        super().keyPressEvent(event)