# src/ui/forgot_password_window.py
"""
Şifremi Unuttum Penceresi - E-posta Doğrulama Kodu ile Şifre Sıfırlama
"""

import random
import hmac
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor

from ..core.logger import logger
from ..models.user import User
from ..services.email_service import EmailService
from .styles import AppStyles


class ForgotPasswordDialog(QDialog):
    """E-posta ile Şifre Sıfırlama Diyaloğu"""

    password_reset_successful = pyqtSignal(str)

    def __init__(self, parent=None, initial_identifier: str = ""):
        super().__init__(parent)
        self.setWindowTitle("🔑 Şifremi Unuttum - ARI FIRIN")
        self.setFixedSize(540, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.target_user = None
        self.verification_code = None
        self.code_expires_at = None
        self.countdown_seconds = 0
        self.initial_identifier = initial_identifier

        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {AppStyles.BG_DARKEST};
            }}
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(36, 26, 36, 26)
        main_layout.setSpacing(14)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)
        header_layout.setAlignment(Qt.AlignCenter)

        title_icon = QLabel("🔑")
        title_icon.setAlignment(Qt.AlignCenter)
        title_icon.setStyleSheet("font-size: 28pt; background: transparent;")
        header_layout.addWidget(title_icon)

        title = QLabel("Şifrenizi mi Unuttunuz?")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; background: transparent;")
        header_layout.addWidget(title)

        self.subtitle = QLabel("Hesabınıza bağlı kullanıcı adınızı veya kayıtlı e-posta adresinizi girin.")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet(f"font-size: 9.5pt; color: {AppStyles.TEXT_SECONDARY}; background: transparent;")
        header_layout.addWidget(self.subtitle)

        main_layout.addLayout(header_layout)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {AppStyles.BORDER}; border: none;")
        main_layout.addWidget(divider)

        # STEP 1
        self.step1_widget = QWidget()
        step1_layout = QVBoxLayout(self.step1_widget)
        step1_layout.setContentsMargins(0, 4, 0, 4)
        step1_layout.setSpacing(0)

        input_label = QLabel("👤 Kullanıcı Adı veya 📧 Kayıtlı E-posta")
        input_label.setStyleSheet(f"font-size: 10pt; font-weight: 600; color: {AppStyles.TEXT_PRIMARY}; margin-bottom: 6px;")
        step1_layout.addWidget(input_label)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Kullanıcı adınızı (örn: suna142) veya e-postanızı girin...")
        self.email_input.setFixedHeight(46)
        self.email_input.setStyleSheet(self._input_style())
        if self.initial_identifier:
            self.email_input.setText(self.initial_identifier)
        self.email_input.returnPressed.connect(self.send_verification_code)
        step1_layout.addWidget(self.email_input)

        step1_layout.addSpacing(14)

        self.send_code_btn = QPushButton("🚀 DOĞRULAMA KODU GÖNDER")
        self.send_code_btn.setFixedHeight(48)
        self.send_code_btn.setCursor(Qt.PointingHandCursor)
        self.send_code_btn.setStyleSheet(self._button_style())
        self.send_code_btn.clicked.connect(self.send_verification_code)
        step1_layout.addWidget(self.send_code_btn)

        step1_layout.addSpacing(10)

        smtp_btn = QPushButton("⚙️ E-posta Gönderici (SMTP) Ayarları")
        smtp_btn.setCursor(Qt.PointingHandCursor)
        smtp_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {AppStyles.TEXT_MUTED};
                font-size: 9.5pt;
                border: none;
                padding: 4px;
            }}
            QPushButton:hover {{
                color: {AppStyles.PRIMARY};
                text-decoration: underline;
            }}
        """)
        smtp_btn.clicked.connect(self.open_smtp_settings)
        step1_layout.addWidget(smtp_btn, alignment=Qt.AlignCenter)

        main_layout.addWidget(self.step1_widget)

        # STEP 2
        self.step2_widget = QWidget()
        step2_layout = QVBoxLayout(self.step2_widget)
        step2_layout.setContentsMargins(0, 4, 0, 4)
        step2_layout.setSpacing(0)

        code_label = QLabel("🔢 6 Haneli Doğrulama Kodu")
        code_label.setStyleSheet(f"font-size: 10pt; font-weight: 600; color: {AppStyles.TEXT_PRIMARY}; margin-bottom: 6px;")
        step2_layout.addWidget(code_label)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("1 2 3 4 5 6")
        self.code_input.setMaxLength(6)
        self.code_input.setAlignment(Qt.AlignCenter)
        self.code_input.setFixedHeight(46)
        self.code_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 2px solid {AppStyles.PRIMARY};
                border-radius: 8px;
                color: {AppStyles.PRIMARY};
                font-size: 16pt;
                font-weight: bold;
                padding: 0px;
            }}
            QLineEdit:focus {{
                background-color: {AppStyles.BG_LIGHT};
                border-color: {AppStyles.CYAN};
            }}
        """)
        step2_layout.addWidget(self.code_input)

        step2_layout.addSpacing(14)

        new_pass_label = QLabel("🔒 Yeni Şifre (En az 8 karakter, büyük/küçük harf ve rakam)")
        new_pass_label.setStyleSheet(f"font-size: 10pt; font-weight: 600; color: {AppStyles.TEXT_PRIMARY}; margin-bottom: 6px;")
        new_pass_label.setWordWrap(True)
        step2_layout.addWidget(new_pass_label)

        new_pass_layout = QHBoxLayout()
        new_pass_layout.setSpacing(8)
        self.new_password_input = QLineEdit()
        self.new_password_input.setPlaceholderText("Yeni şifrenizi girin")
        self.new_password_input.setEchoMode(QLineEdit.Password)
        self.new_password_input.setFixedHeight(44)
        self.new_password_input.setStyleSheet(self._input_style())
        new_pass_layout.addWidget(self.new_password_input)

        self.show_pass1_btn = QPushButton("👁")
        self.show_pass1_btn.setFixedSize(44, 44)
        self.show_pass1_btn.setCursor(Qt.PointingHandCursor)
        self.show_pass1_btn.setStyleSheet(self._eye_button_style())
        self.show_pass1_btn.clicked.connect(lambda: self._toggle_pass_visibility(self.new_password_input, self.show_pass1_btn))
        new_pass_layout.addWidget(self.show_pass1_btn)
        step2_layout.addLayout(new_pass_layout)

        step2_layout.addSpacing(14)

        confirm_pass_label = QLabel("🔒 Yeni Şifre Tekrar")
        confirm_pass_label.setStyleSheet(f"font-size: 10pt; font-weight: 600; color: {AppStyles.TEXT_PRIMARY}; margin-bottom: 6px;")
        step2_layout.addWidget(confirm_pass_label)

        confirm_pass_layout = QHBoxLayout()
        confirm_pass_layout.setSpacing(8)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("Yeni şifrenizi tekrar girin")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.setFixedHeight(44)
        self.confirm_password_input.setStyleSheet(self._input_style())
        self.confirm_password_input.returnPressed.connect(self.reset_password)
        confirm_pass_layout.addWidget(self.confirm_password_input)

        self.show_pass2_btn = QPushButton("👁")
        self.show_pass2_btn.setFixedSize(44, 44)
        self.show_pass2_btn.setCursor(Qt.PointingHandCursor)
        self.show_pass2_btn.setStyleSheet(self._eye_button_style())
        self.show_pass2_btn.clicked.connect(lambda: self._toggle_pass_visibility(self.confirm_password_input, self.show_pass2_btn))
        confirm_pass_layout.addWidget(self.show_pass2_btn)
        step2_layout.addLayout(confirm_pass_layout)

        step2_layout.addSpacing(16)

        self.reset_btn = QPushButton("✨ ŞİFREYİ SIFIRLA VE KAYDET")
        self.reset_btn.setFixedHeight(46)
        self.reset_btn.setCursor(Qt.PointingHandCursor)
        self.reset_btn.setStyleSheet(self._button_style())
        self.reset_btn.clicked.connect(self.reset_password)
        step2_layout.addWidget(self.reset_btn)

        step2_layout.addSpacing(8)

        self.resend_btn = QPushButton("🔄 Kodu Tekrar Gönder")
        self.resend_btn.setFixedHeight(36)
        self.resend_btn.setCursor(Qt.PointingHandCursor)
        self.resend_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                font-size: 9.5pt;
                font-weight: 600;
                padding: 0px 15px;
            }}
            QPushButton:hover {{
                color: {AppStyles.PRIMARY};
                border-color: {AppStyles.PRIMARY};
                background-color: rgba(59, 130, 246, 0.08);
            }}
            QPushButton:disabled {{
                color: {AppStyles.TEXT_MUTED};
                border-color: rgba(148, 163, 184, 0.15);
            }}
        """)
        self.resend_btn.clicked.connect(self.send_verification_code)
        step2_layout.addWidget(self.resend_btn)

        self.step2_widget.setVisible(False)
        main_layout.addWidget(self.step2_widget)

        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setFixedHeight(36)
        self.message_label.setVisible(False)
        main_layout.addWidget(self.message_label)

        cancel_btn = QPushButton("Giriş Ekranına Dön")
        cancel_btn.setFixedHeight(30)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {AppStyles.TEXT_MUTED};
                font-size: 9.5pt;
                border: none;
                padding: 4px;
            }}
            QPushButton:hover {{
                color: {AppStyles.TEXT_PRIMARY};
                text-decoration: underline;
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        main_layout.addWidget(cancel_btn, alignment=Qt.AlignCenter)

        self.setLayout(main_layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_countdown)

    def _input_style(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1.5px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 0px 14px;
                color: {AppStyles.TEXT_PRIMARY};
                font-size: 10.5pt;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """

    def _eye_button_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1.5px solid {AppStyles.BORDER};
                border-radius: 8px;
                font-size: 12pt;
                padding: 0px;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """

    def _button_style(self) -> str:
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                color: #0d0d0f; font-size: 11pt; font-weight: bold;
                border-radius: 8px; border: none; letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
            }}
            QPushButton:disabled {{ background-color: {AppStyles.BORDER}; color: {AppStyles.TEXT_MUTED}; }}
        """

    def _toggle_pass_visibility(self, line_edit: QLineEdit, btn: QPushButton):
        if line_edit.echoMode() == QLineEdit.Password:
            line_edit.setEchoMode(QLineEdit.Normal)
            btn.setText("🔒")
        else:
            line_edit.setEchoMode(QLineEdit.Password)
            btn.setText("👁")

    def show_message(self, text: str, msg_type: str = "danger"):
        colors = {
            "success": (AppStyles.GREEN, "rgba(34, 197, 94, 0.12)", "rgba(34, 197, 94, 0.3)"),
            "danger": (AppStyles.RED, "rgba(239, 68, 68, 0.12)", "rgba(239, 68, 68, 0.3)"),
            "info": (AppStyles.PRIMARY, "rgba(59, 130, 246, 0.12)", "rgba(59, 130, 246, 0.3)"),
            "warning": (AppStyles.ORANGE, "rgba(245, 158, 11, 0.12)", "rgba(245, 158, 11, 0.3)")
        }
        text_color, bg_color, border_color = colors.get(msg_type, (AppStyles.RED, "transparent", "transparent"))
        self.message_label.setStyleSheet(f"""
            color: {text_color};
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-radius: 8px;
            padding: 0px 12px;
            font-weight: bold;
            font-size: 9.5pt;
        """)
        self.message_label.setText(text)
        self.message_label.setVisible(True)

    def _mask_email(self, email: str) -> str:
        """E-postayı güvenlik amaçlı maskeleyerek döndürür (örn: s***z@gmail.com)"""
        try:
            name, domain = email.split('@')
            if len(name) <= 2:
                masked_name = name[0] + "*"
            else:
                masked_name = name[0] + "*" * (len(name) - 2) + name[-1]
            return f"{masked_name}@{domain}"
        except Exception:
            return email

    def open_smtp_settings(self):
        try:
            from .smtp_settings_dialog import SmtpSettingsDialog
            dlg = SmtpSettingsDialog(self)
            dlg.exec_()
        except Exception as e:
            logger.error(f"SMTP ayarları açma hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Ayarlar açılamadı: {str(e)}")

    def send_verification_code(self):
        query_val = self.email_input.text().strip()

        if not query_val:
            self.show_message("❌ Kullanıcı adı veya e-posta adresinizi giriniz!", "danger")
            self.email_input.setFocus()
            return

        self.send_code_btn.setEnabled(False)
        self.send_code_btn.setText("⏳ Kontrol Ediliyor...")
        self.show_message("⌛ Kullanıcı bilgileri kontrol ediliyor...", "info")

        # ✅ GENERIC MESAJ — User enumeration önlemi
        generic_message = (
            "✅ Eğer bu bilgi sistemde kayıtlıysa, doğrulama kodu "
            "kayıtlı e-posta adresinize gönderilecektir. "
            "Lütfen e-postanızı kontrol edin."
        )

        # Kullanıcıyı ara
        user = None
        if "@" in query_val:
            user = User.get_by_email(query_val)
        else:
            user = User.get_by_username(query_val)

        # Geçersiz kullanıcı/durum — generic mesaj göster (enumeration önlemi)
        if not user or not user.is_active or not user.email:
            # Kısa bir gecikme ekle (timing attack önlemi)
            import time
            time.sleep(0.4)
            self.show_message(generic_message, "info")
            self.send_code_btn.setEnabled(True)
            self.send_code_btn.setText("🚀 DOĞRULAMA KODU GÖNDER")
            return

        target_email = user.email.strip()

        # Kod üret
        self.target_user = user
        import secrets
        self.verification_code = "".join(secrets.choice("0123456789") for _ in range(6))
        self._failed_code_attempts = 0
        self.code_expires_at = datetime.now() + timedelta(minutes=10)

        # E-posta gönder
        success, info_msg = EmailService.send_password_reset_code(
            target_email, user.full_name, self.verification_code
        )

        if success:
            self.step1_widget.setVisible(False)
            self.step2_widget.setVisible(True)
            self.setFixedSize(540, 660)
            masked = self._mask_email(target_email)
            self.subtitle.setText(f"📧 6 haneli doğrulama kodu sistemde kayıtlı olan <b>{masked}</b> adresinize gönderildi.")
            self.show_message(f"✅ {info_msg}", "success")

            self.countdown_seconds = 60
            self.resend_btn.setEnabled(False)
            self.timer.start(1000)
            self.code_input.setFocus()
        else:
            self.show_message(f"❌ {info_msg}", "danger")
            self.send_code_btn.setEnabled(True)
            self.send_code_btn.setText("🚀 DOĞRULAMA KODU GÖNDER")

            if not EmailService.is_smtp_configured():
                reply = QMessageBox.question(
                    self, "E-posta (SMTP) Yapılandırması Gerekli",
                    "Doğrulama kodunun gerçek e-posta adresinize gönderilebilmesi için sistemde gönderici SMTP e-posta ayarlarının yapılması gerekmektedir.\n\nŞimdi ayarları yapılandırmak ister misiniz?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.open_smtp_settings()

    def _update_countdown(self):
        self.countdown_seconds -= 1
        if self.countdown_seconds > 0:
            self.resend_btn.setText(f"⏳ Kodu Tekrar Gönder ({self.countdown_seconds}s)")
        else:
            self.timer.stop()
            self.resend_btn.setEnabled(True)
            self.resend_btn.setText("🔄 Kodu Tekrar Gönder")

    def reset_password(self):
        entered_code = self.code_input.text().strip()
        new_password = self.new_password_input.text()
        confirm_password = self.confirm_password_input.text()

        if not entered_code:
            self.show_message("❌ Doğrulama kodunu giriniz!", "danger")
            self.code_input.setFocus()
            return

        if not getattr(self, 'verification_code', None):
            self.show_message("❌ Geçerli bir doğrulama kodu bulunamadı. Lütfen yeni kod talep edin.", "danger")
            return

        if datetime.now() > self.code_expires_at:
            self.show_message("❌ Doğrulama kodunun süresi dolmuş. Lütfen tekrar kod isteyin.", "danger")
            return

        # ✅ Timing attack koruması & OTP Kaba Kuvvet Koruması
        if not hmac.compare_digest(entered_code, self.verification_code):
            self._failed_code_attempts = getattr(self, '_failed_code_attempts', 0) + 1
            if self._failed_code_attempts >= 5:
                self.verification_code = None  # Kodu geçersiz kıl
                self.show_message("🔒 Çok fazla hatalı kod girildi! Doğrulama kodu güvenlik nedeniyle iptal edildi. Lütfen yeni kod isteyin.", "danger")
                self.reset_btn.setEnabled(False)
            else:
                kalan = 5 - self._failed_code_attempts
                self.show_message(f"❌ Yanlış doğrulama kodu girdiniz! (Kalan hak: {kalan})", "danger")
            self.code_input.setFocus()
            return

        if not new_password:
            self.show_message("❌ Yeni şifrenizi giriniz!", "danger")
            self.new_password_input.setFocus()
            return

        # ✅ Şifre politikası — User modelindeki tek kaynak
        is_strong, msg = User.validate_password_strength(new_password)
        if not is_strong:
            self.show_message(f"❌ {msg}", "danger")
            self.new_password_input.setFocus()
            return

        if new_password != confirm_password:
            self.show_message("❌ Şifreler birbiriyle eşleşmiyor!", "danger")
            self.confirm_password_input.setFocus()
            return

        self.reset_btn.setEnabled(False)
        self.reset_btn.setText("⏳ Şifre Güncelleniyor...")

        try:
            if self.target_user.reset_password(new_password):
                QMessageBox.information(
                    self, "Başarılı",
                    "🎉 Şifreniz başarıyla güncellendi!\nYeni şifrenizle giriş yapabilirsiniz."
                )
                self.password_reset_successful.emit(self.target_user.username)
                self.accept()
            else:
                self.show_message("❌ Şifre güncellenirken bir hata oluştu!", "danger")
                self.reset_btn.setEnabled(True)
                self.reset_btn.setText("✨ ŞİFREYİ SIFIRLA VE KAYDET")
        except Exception as e:
            logger.error(f"Şifre sıfırlama hatası: {e}")
            self.show_message(f"❌ Hata: {str(e)}", "danger")
            self.reset_btn.setEnabled(True)
            self.reset_btn.setText("✨ ŞİFREYİ SIFIRLA VE KAYDET")