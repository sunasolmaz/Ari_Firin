# src/ui/setup_window.py
"""
Modern İlk Kurulum Ekranı
Gradient arka plan, şık tasarım
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFrame,
    QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
import re

from ..core.database import db
from ..core.logger import logger
from ..models.user import User
from ..models.branch import Branch


class ModernInput(QLineEdit):
    """Modern input alanı"""

    def __init__(self, placeholder: str = "", is_password: bool = False):
        super().__init__()
        self.setPlaceholderText(placeholder)
        if is_password:
            self.setEchoMode(QLineEdit.Password)

        self.setMinimumHeight(45)
        self.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e24;
                border: 2px solid #2a2a32;
                border-radius: 8px;
                padding: 10px 15px;
                font-size: 12pt;
                color: #f9fafb;
            }
            QLineEdit:focus {
                border: 2px solid #10b981;
                background-color: #1e1e24;
            }
        """)


class SetupWindow(QMainWindow):
    """Modern ilk kurulum ekranı"""

    setup_completed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("☕ Muhasebe Uygulaması - İlk Kurulum")
        self.setMinimumSize(900, 700)
        self.showMaximized()

        self.center_window()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #10b981, stop:1 #059669);
            }
        """)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(30, 30, 30, 30)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1e1e24;
                border-radius: 20px;
                padding: 30px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 10)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout()
        card_layout.setSpacing(15)

        logo = QLabel("☕")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("font-size: 50pt; background: transparent; border: none;")
        card_layout.addWidget(logo)

        title = QLabel("🎉 Hoş Geldiniz!")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 24pt;
            font-weight: bold;
            color: #f9fafb;
            background: transparent;
            border: none;
        """)
        card_layout.addWidget(title)

        subtitle = QLabel("İlk kurulum için bir yönetici hesabı oluşturun")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("""
            font-size: 11pt;
            color: #9ca3af;
            background: transparent;
            border: none;
            margin-bottom: 10px;
        """)
        card_layout.addWidget(subtitle)

        form_layout = QGridLayout()
        form_layout.setSpacing(12)

        form_layout.addWidget(self.create_label("👤 Ad Soyad:*"), 0, 0)
        self.full_name_input = ModernInput("Örn: Ahmet Yılmaz")
        form_layout.addWidget(self.full_name_input, 0, 1)

        form_layout.addWidget(self.create_label("🔑 Kullanıcı Adı:*"), 1, 0)
        self.username_input = ModernInput("Örn: ahmet.yilmaz")
        form_layout.addWidget(self.username_input, 1, 1)

        form_layout.addWidget(self.create_label("📧 Email:"), 2, 0)
        self.email_input = ModernInput("ornek@email.com")
        form_layout.addWidget(self.email_input, 2, 1)

        form_layout.addWidget(self.create_label("📞 Telefon:"), 3, 0)
        self.phone_input = ModernInput("05XX XXX XX XX")
        form_layout.addWidget(self.phone_input, 3, 1)

        form_layout.addWidget(self.create_label("🔒 Şifre:*"), 4, 0)
        self.password_input = ModernInput("En az 8 karakter, büyük/küçük harf ve rakam", is_password=True)
        form_layout.addWidget(self.password_input, 4, 1)

        form_layout.addWidget(self.create_label("🔒 Şifre Tekrar:*"), 5, 0)
        self.password_confirm_input = ModernInput("Şifreyi tekrar girin", is_password=True)
        self.password_confirm_input.returnPressed.connect(self.create_admin)
        form_layout.addWidget(self.password_confirm_input, 5, 1)

        card_layout.addLayout(form_layout)
        card_layout.addSpacing(10)

        self.create_btn = QPushButton("✅ Hesabı Oluştur ve Başla")
        self.create_btn.clicked.connect(self.create_admin)
        self.create_btn.setMinimumHeight(50)
        self.create_btn.setCursor(Qt.PointingHandCursor)
        self.create_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                color: #f9fafb;
                font-size: 13pt;
                font-weight: bold;
                border-radius: 10px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #059669, stop:1 #10b981);
            }
        """)
        card_layout.addWidget(self.create_btn)

        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setMinimumHeight(30)
        self.message_label.setStyleSheet("""
            color: #ef4444;
            background: transparent;
            border: none;
            font-size: 10pt;
            font-weight: bold;
        """)
        card_layout.addWidget(self.message_label)

        card.setLayout(card_layout)
        main_layout.addWidget(card)

        central_widget.setLayout(main_layout)

        QTimer.singleShot(300, lambda: self.full_name_input.setFocus())

    def center_window(self):
        """Pencereyi ortala"""
        screen = self.screen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def create_label(self, text: str) -> QLabel:
        """Form etiketi oluştur"""
        label = QLabel(text)
        label.setStyleSheet("""
            font-size: 11pt;
            font-weight: bold;
            color: #f9fafb;
            background: transparent;
            border: none;
        """)
        return label

    def create_admin(self):
        """Yönetici hesabını oluştur"""
        full_name = self.full_name_input.text().strip()
        username = self.username_input.text().strip()
        email = self.email_input.text().strip()
        phone = self.phone_input.text().strip()
        password = self.password_input.text()
        password_confirm = self.password_confirm_input.text()

        # Validasyon
        if not full_name or len(full_name) < 3:
            self.show_error("Ad Soyad en az 3 karakter olmalıdır!")
            self.full_name_input.setFocus()
            return

        if not username or len(username) < 3:
            self.show_error("Kullanıcı adı en az 3 karakter olmalıdır!")
            self.username_input.setFocus()
            return

        if not re.match(r'^[a-zA-Z0-9._]+$', username):
            self.show_error("Kullanıcı adı sadece harf, rakam, nokta ve alt çizgi içerebilir!")
            self.username_input.setFocus()
            return

        if email and not self._validate_email(email):
            self.show_error("Geçersiz email formatı!")
            self.email_input.setFocus()
            return

        # ✅ Şifre politikası — User modelindeki tek kaynak
        is_strong, msg = User.validate_password_strength(password)
        if not is_strong:
            self.show_error(msg)
            self.password_input.setFocus()
            return

        if password != password_confirm:
            self.show_error("Şifreler eşleşmiyor!")
            self.password_confirm_input.setFocus()
            return

        try:
            existing = User.get_by_username(username)
            if existing:
                self.show_error("Bu kullanıcı adı zaten kullanılıyor!")
                self.username_input.setFocus()
                return

            branches = Branch.get_all(active_only=True)
            target_branch_id = branches[0].id if branches else None
            branch_name_for_tenant = "Merkez Şube"

            if not target_branch_id:
                # Ortak (public) şemaya şube yazılmaz; şube kullanıcının kendi şemasında oluşturulur.
                branch_name_for_tenant = "Armada"
            else:
                branch_name_for_tenant = branches[0].name

            # Her yeni kullanıcı kendi izole alanının yöneticisidir; uygulamanın tüm bölümlerini görür.
            # (Veriler kullanıcıya özel şemada tutulduğu için diğer kullanıcıların verilerine erişemez.)
            role = 'Admin'

            user = User({
                'branch_id': target_branch_id,
                'username': username,
                'password_hash': User.hash_password(password),
                'full_name': full_name,
                'email': email if email else None,
                'phone': phone if phone else None,
                'role': role,
                'is_active': True
            })

            if user.save(branch_name=branch_name_for_tenant):
                logger.info(f"✅ İlk yönetici oluşturuldu: {username} (rol: {role})")

                QMessageBox.information(
                    self, "Başarılı",
                    f"🎉 Hoş geldiniz {full_name}!\n\n"
                    f"👤 Kullanıcı Adı: {username}\n"
                    f"🔑 Şifrenizle giriş yapabilirsiniz."
                )

                self.setup_completed.emit()
                self.close()
            else:
                self.show_error("Hesap oluşturulamadı!")

        except Exception as e:
            logger.error(f"❌ Setup hatası: {e}")
            self.show_error(f"Sistem hatası: {str(e)}")

    def _validate_email(self, email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def show_error(self, message: str):
        """Hata mesajı göster"""
        self.message_label.setStyleSheet("""
            color: #ef4444;
            background: transparent;
            border: none;
            font-size: 10pt;
            font-weight: bold;
        """)
        self.message_label.setText(f"❌ {message}")