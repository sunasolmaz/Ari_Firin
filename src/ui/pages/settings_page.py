# src/ui/pages/settings_page.py
"""
Ayarlar Sayfası - Şifre Değiştirme ve E-posta Ayarları
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles


class SettingsPage(QWidget):
    """Ayarlar sayfası - Şifre Değiştirme ve E-posta Ayarları"""

    def __init__(self, user: User, branch_id: int = None, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window

        self.init_ui()

    def init_ui(self):
        self.setObjectName("SettingsPage")
        self.setStyleSheet(f"#SettingsPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout()
        layout.setSpacing(25)
        layout.setContentsMargins(35, 30, 35, 30)

        # Başlık
        title = QLabel("⚙️ Ayarlar")
        title.setStyleSheet(f"font-size: 22pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Hesap güvenliğinizi ve e-posta (SMTP) bildirim ayarlarınızı bu sayfadan yönetebilirsiniz.")
        subtitle.setStyleSheet(f"font-size: 10.5pt; color: {AppStyles.TEXT_SECONDARY};")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # 1. Şifre Değiştirme Bölümü
        password_group = self.create_password_group()
        layout.addWidget(password_group)

        # 2. E-posta (SMTP) Ayarları Bölümü — SADECE ADMIN
        if self.user and self.user.role == 'Admin':
            email_group = self.create_email_group()
            layout.addWidget(email_group)

        layout.addStretch()
        self.setLayout(layout)

    def create_password_group(self) -> QGroupBox:
        """Şifre değişikliği grubu"""
        group = QGroupBox("🔒 Şifre Değiştir")
        group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {AppStyles.BORDER};
                border-radius: 12px;
                margin-top: 15px;
                padding: 25px;
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                font-weight: bold;
                font-size: 12pt;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 10px;
                color: {AppStyles.PRIMARY};
            }}
        """)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        form = QGridLayout()
        form.setSpacing(14)

        lbl_old = QLabel("Mevcut Şifre:")
        lbl_old.setStyleSheet(f"font-size: 10.5pt; color: {AppStyles.TEXT_PRIMARY};")
        form.addWidget(lbl_old, 0, 0)

        self.old_pass = QLineEdit()
        self.old_pass.setEchoMode(QLineEdit.Password)
        self.old_pass.setPlaceholderText("Mevcut şifrenizi girin")
        form.addWidget(self.old_pass, 0, 1)

        lbl_new = QLabel("Yeni Şifre:")
        lbl_new.setStyleSheet(f"font-size: 10.5pt; color: {AppStyles.TEXT_PRIMARY};")
        form.addWidget(lbl_new, 1, 0)

        self.new_pass = QLineEdit()
        self.new_pass.setEchoMode(QLineEdit.Password)
        self.new_pass.setPlaceholderText("En az 8 karakter, büyük/küçük harf ve rakam")
        form.addWidget(self.new_pass, 1, 1)

        lbl_confirm = QLabel("Yeni Şifre Tekrar:")
        lbl_confirm.setStyleSheet(f"font-size: 10.5pt; color: {AppStyles.TEXT_PRIMARY};")
        form.addWidget(lbl_confirm, 2, 0)

        self.new_pass_confirm = QLineEdit()
        self.new_pass_confirm.setEchoMode(QLineEdit.Password)
        self.new_pass_confirm.setPlaceholderText("Yeni şifrenizi tekrar girin")
        form.addWidget(self.new_pass_confirm, 2, 1)

        layout.addLayout(form)
        layout.addSpacing(10)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        change_btn = QPushButton("🔒 Şifreyi Güncelle")
        change_btn.setMinimumHeight(44)
        change_btn.setCursor(Qt.PointingHandCursor)
        change_btn.clicked.connect(self.change_password)
        change_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.ORANGE};
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 11pt;
                padding: 10px 30px;
            }}
            QPushButton:hover {{
                background-color: #d97706;
            }}
        """)
        btn_layout.addWidget(change_btn)

        layout.addLayout(btn_layout)
        group.setLayout(layout)
        return group

    def change_password(self):
        """Şifre değiştir — User modelinin standart politikasını kullanır"""
        old = self.old_pass.text()
        new = self.new_pass.text()
        confirm = self.new_pass_confirm.text()

        if not old or not new or not confirm:
            QMessageBox.warning(self, "Uyarı", "Lütfen tüm şifre alanlarını doldurun!")
            return

        if new != confirm:
            QMessageBox.warning(self, "Uyarı", "Yeni şifreler eşleşmiyor!")
            return

        # ✅ Şifre politikası — User modelindeki TEK KAYNAK
        is_strong, msg = User.validate_password_strength(new)
        if not is_strong:
            QMessageBox.warning(self, "Zayıf Şifre", msg)
            return

        # ✅ User.change_password() metodunu kullan — kod tekrarı yok, güvenli
        if self.user.change_password(old, new):
            logger.info(f"✅ Şifre güncellendi: {self.user.username}")
            QMessageBox.information(self, "Başarılı", "🎉 Şifreniz başarıyla değiştirildi!")

            self.old_pass.clear()
            self.new_pass.clear()
            self.new_pass_confirm.clear()
        else:
            QMessageBox.warning(self, "Hata", "Mevcut şifreniz yanlış veya şifre güncellenemedi!")

    def create_email_group(self) -> QGroupBox:
        """E-posta (SMTP) ayarları grubu — Sadece Admin'e görünür"""
        from ...core.config import config
        from ...services.email_service import EmailService

        group = QGroupBox("📧 E-posta (SMTP) Bildirim & Şifre Sıfırlama Ayarları")
        group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {AppStyles.BORDER};
                border-radius: 12px;
                margin-top: 15px;
                padding: 25px;
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                font-weight: bold;
                font-size: 12pt;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 10px;
                color: {AppStyles.PRIMARY};
            }}
        """)

        layout = QVBoxLayout()
        layout.setSpacing(12)

        desc = QLabel(
            "Kullanıcıların 'Şifremi Unuttum' dediğinde sistemde kayıtlı e-posta adreslerine gerçek doğrulama kodu "
            "ulaşabilmesi için gönderici SMTP e-posta sunucusunun (örn: Gmail, Outlook veya şirket e-postası) yapılandırılması gerekir."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 9.5pt; color: {AppStyles.TEXT_SECONDARY}; line-height: 1.4;")
        layout.addWidget(desc)

        status_bar = QHBoxLayout()
        is_cfg = EmailService.is_smtp_configured()
        sender_email = config.get('email.sender_email', '')

        if is_cfg:
            status_text = f"🟢 E-posta Gönderimi Aktif (Gönderici: {sender_email})"
            status_color = AppStyles.GREEN
        else:
            status_text = "🟠 E-posta Gönderimi Henüz Yapılandırılmamış (Şifre sıfırlama kodları gerçek maile gidemez)"
            status_color = AppStyles.ORANGE

        self.email_status_label = QLabel(status_text)
        self.email_status_label.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {status_color};")
        status_bar.addWidget(self.email_status_label)
        status_bar.addStretch()

        smtp_btn = QPushButton("⚙️ E-posta (SMTP) Ayarlarını Düzenle ve Test Et")
        smtp_btn.setMinimumHeight(40)
        smtp_btn.setCursor(Qt.PointingHandCursor)
        smtp_btn.clicked.connect(self.open_smtp_settings)
        smtp_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.PRIMARY};
                color: #0d0d0f;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 10pt;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.CYAN};
            }}
        """)
        status_bar.addWidget(smtp_btn)
        layout.addLayout(status_bar)

        group.setLayout(layout)
        return group

    def open_smtp_settings(self):
        """E-posta ayarları penceresini aç ve kaydedildikten sonra durumu güncelle"""
        from ..smtp_settings_dialog import SmtpSettingsDialog
        from ...core.config import config
        from ...services.email_service import EmailService

        dlg = SmtpSettingsDialog(self)
        if dlg.exec_():
            is_cfg = EmailService.is_smtp_configured()
            sender_email = config.get('email.sender_email', '')
            if is_cfg:
                self.email_status_label.setText(f"🟢 E-posta Gönderimi Aktif (Gönderici: {sender_email})")
                self.email_status_label.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {AppStyles.GREEN};")
            else:
                self.email_status_label.setText("🟠 E-posta Gönderimi Henüz Yapılandırılmamış")
                self.email_status_label.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {AppStyles.ORANGE};")