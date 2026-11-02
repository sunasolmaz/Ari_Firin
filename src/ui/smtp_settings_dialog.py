# src/ui/smtp_settings_dialog.py
"""
E-posta (SMTP) Yapılandırma ve Test Diyaloğu
"""

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QComboBox,
    QFrame, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from ..core.logger import logger
from ..services.email_service import EmailService
from .styles import AppStyles


class SmtpSettingsDialog(QDialog):
    """E-posta (SMTP) Ayarları Diyaloğu"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ E-posta (SMTP) Bildirim Ayarları")
        self.setFixedSize(620, 710)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {AppStyles.BG_DARKEST};
            }}
        """)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(35, 30, 35, 30)
        main_layout.setSpacing(16)
        
        # ==================== ÜST BAŞLIK ====================
        title_layout = QHBoxLayout()
        title_layout.setSpacing(15)
        
        title_icon = QLabel("📧")
        title_icon.setStyleSheet("font-size: 28pt; background: transparent;")
        title_layout.addWidget(title_icon)
        
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(4)
        title = QLabel("Merkezi E-posta (SMTP) Ayarları")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY}; background: transparent;")
        title_vbox.addWidget(title)
        
        subtitle = QLabel("Tüm şubeler için ortak şifre sıfırlama ve bildirim e-posta sunucusu")
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY}; background: transparent;")
        title_vbox.addWidget(subtitle)
        
        title_layout.addLayout(title_vbox)
        main_layout.addLayout(title_layout)
        
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {AppStyles.BORDER}; border: none;")
        main_layout.addWidget(divider)
        
        # ==================== HIZLI SERVİS ŞABLONU ====================
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(12)
        
        preset_lbl = QLabel("Hızlı Şablon:")
        preset_lbl.setStyleSheet(f"color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; font-weight: 600;")
        preset_layout.addWidget(preset_lbl)
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "Gmail (smtp.gmail.com)", 
            "Outlook / Office 365 (smtp.office365.com)", 
            "Yandex Mail (smtp.yandex.com)", 
            "Özel SMTP Sunucusu"
        ])
        self.preset_combo.setMinimumHeight(44)
        self.preset_combo.setStyleSheet(self._combo_style())
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.preset_combo, 1)
        main_layout.addLayout(preset_layout)
        
        # ==================== FORM ALANI ====================
        form_frame = QFrame()
        form_frame.setStyleSheet(f"""
            QFrame#formFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 12px;
                padding: 15px;
            }}
        """)
        form_frame.setObjectName("formFrame")
        
        form_layout = QGridLayout()
        form_layout.setSpacing(14)
        form_layout.setColumnMinimumWidth(0, 150)
        form_layout.setColumnStretch(1, 1)
        
        # 1. SMTP Server
        form_layout.addWidget(self._create_label("SMTP Sunucusu:"), 0, 0, Qt.AlignVCenter)
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("smtp.gmail.com")
        self.server_input.setMinimumHeight(44)
        self.server_input.setStyleSheet(self._input_style())
        form_layout.addWidget(self.server_input, 0, 1)
        
        # 2. Port
        form_layout.addWidget(self._create_label("Port Numarası:"), 1, 0, Qt.AlignVCenter)
        self.port_input = QLineEdit("587")
        self.port_input.setPlaceholderText("587 veya 465")
        self.port_input.setMinimumHeight(44)
        self.port_input.setStyleSheet(self._input_style())
        form_layout.addWidget(self.port_input, 1, 1)
        
        # 3. Gönderici E-posta
        form_layout.addWidget(self._create_label("Gönderici E-posta:"), 2, 0, Qt.AlignVCenter)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("ornek@gmail.com")
        self.email_input.setMinimumHeight(44)
        self.email_input.setStyleSheet(self._input_style())
        form_layout.addWidget(self.email_input, 2, 1)
        
        # 4. Şifre
        form_layout.addWidget(self._create_label("Uygulama Şifresi:"), 3, 0, Qt.AlignVCenter)
        pass_layout = QHBoxLayout()
        pass_layout.setSpacing(8)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("16 Haneli Google Uygulama Şifresi")
        self.password_input.setMinimumHeight(44)
        self.password_input.setStyleSheet(self._input_style())
        pass_layout.addWidget(self.password_input)
        
        self.show_pass_btn = QPushButton("👁")
        self.show_pass_btn.setFixedSize(44, 44)
        self.show_pass_btn.setCursor(Qt.PointingHandCursor)
        self.show_pass_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                border: 1.5px solid {AppStyles.BORDER};
                border-radius: 8px;
                font-size: 12pt;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        self.show_pass_btn.clicked.connect(self._toggle_password_visibility)
        pass_layout.addWidget(self.show_pass_btn)
        form_layout.addLayout(pass_layout, 3, 1)
        
        # 5. Güvenlik Protokolü
        form_layout.addWidget(self._create_label("Güvenlik Protokolü:"), 4, 0, Qt.AlignVCenter)
        proto_layout = QHBoxLayout()
        proto_layout.setSpacing(20)
        
        self.tls_checkbox = QCheckBox("STARTTLS (Port 587)")
        self.tls_checkbox.setChecked(True)
        self.tls_checkbox.setStyleSheet(f"color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; font-weight: 500;")
        self.tls_checkbox.toggled.connect(self._on_tls_toggled)
        proto_layout.addWidget(self.tls_checkbox)
        
        self.ssl_checkbox = QCheckBox("SSL (Port 465)")
        self.ssl_checkbox.setStyleSheet(f"color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; font-weight: 500;")
        self.ssl_checkbox.toggled.connect(self._on_ssl_toggled)
        proto_layout.addWidget(self.ssl_checkbox)
        proto_layout.addStretch()
        form_layout.addLayout(proto_layout, 4, 1)
        
        form_frame.setLayout(form_layout)
        main_layout.addWidget(form_frame)
        
        # ==================== BİLGİ İPUCU KUTUSU ====================
        self.info_box = QLabel(
            "💡 <b>Gmail Bilgisi:</b> Gmail kullanıyorsanız normal giriş şifreniz değil, "
            "Google Hesabı > Güvenlik > <b>2 Adımlı Doğrulama</b> altındaki "
            "<b>Uygulama Şifreleri</b> kısmından oluşturulan 16 harfli şifre girilmelidir."
        )
        self.info_box.setWordWrap(True)
        self.info_box.setStyleSheet(f"""
            background-color: rgba(59, 130, 246, 0.1);
            color: #93c5fd;
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 9pt;
            line-height: 1.4;
        """)
        main_layout.addWidget(self.info_box)
        
        # ==================== DURUM MESAJI ====================
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(32)
        self.status_label.setStyleSheet("font-size: 9.5pt; font-weight: bold; background: transparent;")
        self.status_label.setVisible(False)
        main_layout.addWidget(self.status_label)
        
        # ==================== BUTONLAR ====================
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.test_btn = QPushButton("🧪 Bağlantıyı Test Et")
        self.test_btn.setMinimumHeight(46)
        self.test_btn.setCursor(Qt.PointingHandCursor)
        self.test_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1.5px solid {AppStyles.BORDER};
                border-radius: 8px;
                font-weight: bold;
                font-size: 10pt;
                padding: 0 18px;
            }}
            QPushButton:hover {{
                border-color: {AppStyles.PRIMARY};
                color: {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
            QPushButton:disabled {{
                color: {AppStyles.TEXT_MUTED};
                border-color: rgba(148, 163, 184, 0.2);
            }}
        """)
        self.test_btn.clicked.connect(self.test_smtp)
        btn_layout.addWidget(self.test_btn)
        
        self.save_btn = QPushButton("💾 Ayarları Kaydet")
        self.save_btn.setMinimumHeight(46)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.GREEN};
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 10.5pt;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background-color: #15803d;
            }}
        """)
        self.save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(btn_layout)
        
        # İptal / Kapat
        close_btn = QPushButton("Vazgeç / Kapat")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
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
        close_btn.clicked.connect(self.reject)
        main_layout.addWidget(close_btn, alignment=Qt.AlignCenter)
        
        self.setLayout(main_layout)
        
    def _create_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_PRIMARY}; font-weight: 600;")
        return lbl

    def _input_style(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1.5px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 0px 14px;
                font-size: 10.5pt;
            }}
            QLineEdit:focus {{
                border-color: {AppStyles.PRIMARY};
                background-color: #181824;
            }}
        """

    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1.5px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 10pt;
                font-weight: 500;
            }}
            QComboBox:focus {{
                border-color: {AppStyles.PRIMARY};
            }}
            QComboBox QAbstractItemView {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                selection-background-color: {AppStyles.PRIMARY};
            }}
        """

    def _on_preset_changed(self, index: int):
        if index == 0:  # Gmail
            self.server_input.setText("smtp.gmail.com")
            self.port_input.setText("587")
            self.tls_checkbox.setChecked(True)
            self.ssl_checkbox.setChecked(False)
        elif index == 1:  # Outlook
            self.server_input.setText("smtp.office365.com")
            self.port_input.setText("587")
            self.tls_checkbox.setChecked(True)
            self.ssl_checkbox.setChecked(False)
        elif index == 2:  # Yandex
            self.server_input.setText("smtp.yandex.com")
            self.port_input.setText("465")
            self.tls_checkbox.setChecked(False)
            self.ssl_checkbox.setChecked(True)

    def _on_tls_toggled(self, checked: bool):
        if checked:
            self.ssl_checkbox.setChecked(False)
            if self.port_input.text() == "465":
                self.port_input.setText("587")

    def _on_ssl_toggled(self, checked: bool):
        if checked:
            self.tls_checkbox.setChecked(False)
            if self.port_input.text() == "587":
                self.port_input.setText("465")

    def _toggle_password_visibility(self):
        if self.password_input.echoMode() == QLineEdit.Password:
            self.password_input.setEchoMode(QLineEdit.Normal)
            self.show_pass_btn.setText("🔒")
        else:
            self.password_input.setEchoMode(QLineEdit.Password)
            self.show_pass_btn.setText("👁")

    def load_settings(self):
        email_cfg = EmailService.get_smtp_config()
        self.server_input.setText(email_cfg.get('smtp_server', 'smtp.gmail.com'))
        self.port_input.setText(str(email_cfg.get('smtp_port', 587)))
        self.email_input.setText(email_cfg.get('sender_email', ''))
        self.password_input.setText(email_cfg.get('sender_password', ''))
        self.tls_checkbox.setChecked(email_cfg.get('use_tls', True))
        self.ssl_checkbox.setChecked(email_cfg.get('use_ssl', False))

    def test_smtp(self):
        server = self.server_input.text().strip()
        port = self.port_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text().strip()
        use_tls = self.tls_checkbox.isChecked()
        use_ssl = self.ssl_checkbox.isChecked()
        
        self.status_label.setStyleSheet(f"""
            color: {AppStyles.PRIMARY};
            background-color: rgba(59, 130, 246, 0.12);
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 8px;
            padding: 8px 12px;
        """)
        self.status_label.setText("⏳ SMTP sunucusuna bağlanılıyor...")
        self.status_label.setVisible(True)
        self.test_btn.setEnabled(False)
        
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()
        
        success, msg = EmailService.test_connection(
            server, int(port) if port.isdigit() else 587,
            email, password, use_tls, use_ssl
        )
        
        self.test_btn.setEnabled(True)
        if success:
            self.status_label.setStyleSheet(f"""
                color: {AppStyles.GREEN};
                background-color: rgba(34, 197, 94, 0.12);
                border: 1px solid rgba(34, 197, 94, 0.3);
                border-radius: 8px;
                padding: 8px 12px;
            """)
            self.status_label.setText(msg)
        else:
            self.status_label.setStyleSheet(f"""
                color: {AppStyles.RED};
                background-color: rgba(239, 68, 68, 0.12);
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 8px;
                padding: 8px 12px;
            """)
            self.status_label.setText(msg)

    def save_settings(self):
        server = self.server_input.text().strip()
        port_str = self.port_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text().strip()
        use_tls = self.tls_checkbox.isChecked()
        use_ssl = self.ssl_checkbox.isChecked()
        
        if not server or not email:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen SMTP Sunucusu ve Gönderici E-posta adresini giriniz.")
            return
            
        try:
            port = int(port_str) if port_str.isdigit() else 587
        except ValueError:
            port = 587
            
        EmailService.save_smtp_config(server, port, email, password, use_tls, use_ssl)
        
        logger.info(f"✅ E-posta ayarları kaydedildi: Sunucu={server}, Gönderici={email}")
        QMessageBox.information(
            self, "Başarılı", 
            "✅ E-posta (SMTP) ayarları merkezi veritabanına ve sisteme başarıyla kaydedildi!\n\n"
            "Bu ayar sayesinde tüm şubeler ve diğer bilgisayarlar da aynı merkezi gönderici üzerinden bildirim/şifre kodu gönderecektir."
        )
        self.accept()
