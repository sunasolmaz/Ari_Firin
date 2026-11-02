# src/ui/pages/payment_plans_page.py
"""
Ödeme Planları, Personel ve Avans Yönetimi Sayfası
- KPI kartları (Bu ay ödenecek / Yaklaşan / Gecikmiş / Ödenen)
- 3 sekmeli yapı:
    Tab 1: Ödeme Planları (maaş, kira, taksit, diğer)
    Tab 2: Personel (çalışan listesi + cari ekstre)
    Tab 3: Avanslar (açık avanslar + mahsup takibi)
- Tam CRUD dialogları
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QDoubleSpinBox, QMessageBox, QHeaderView, QGraphicsDropShadowEffect,
    QScrollArea, QTabWidget, QDialog, QDateEdit, QTextEdit,
    QDialogButtonBox, QCheckBox, QSpinBox, QFormLayout, QRadioButton,
    QButtonGroup, QFileDialog
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont
from datetime import datetime, timedelta
import pandas as pd

from ...models.user import User
from ...models.branch import Branch
from ...core.database import db
from ...core.logger import logger
from ...core.decimal_utils import to_decimal, round_currency
from ...services.payment_plan_service import (
    payment_plan_service, PLAN_TYPES, PAYMENT_METHODS, STATUS
)
from ...services.employee_service import employee_service
from ..styles import AppStyles


# ==================== DİALOG PENCERELERİ ====================

class NewPaymentPlanDialog(QDialog):
    """Yeni Ödeme Planı Dialog'u (Taksitli destekli)"""

    def __init__(self, user: User, branch_id: int = None, parent=None):
        super().__init__(parent)
        self.user = user
        self.branch_id = branch_id
        self.setWindowTitle("➕ Yeni Ödeme Planı")
        self.setMinimumWidth(560)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("➕ Yeni Ödeme Planı Oluştur")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        layout.addWidget(title)

        form = QGridLayout()
        form.setSpacing(10)

        # Plan Tipi
        form.addWidget(QLabel("Plan Tipi *:"), 0, 0)
        self.type_combo = QComboBox()
        for key, val in PLAN_TYPES.items():
            if key != 'avans':  # avans ayrı dialog ile verilir
                self.type_combo.addItem(val, key)
        self.type_combo.setStyleSheet(self._input_style())
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        form.addWidget(self.type_combo, 0, 1)

        # Şube
        form.addWidget(QLabel("Şube:"), 1, 0)
        self.branch_combo = QComboBox()
        self.branch_combo.addItem("Genel Merkez (Tümü)", None)
        try:
            branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY name")
            for b in branches:
                self.branch_combo.addItem(f"🏢 {b['name']}", b['id'])
        except Exception:
            pass
        if self.branch_id:
            idx = self.branch_combo.findData(self.branch_id)
            if idx >= 0:
                self.branch_combo.setCurrentIndex(idx)
        self.branch_combo.setStyleSheet(self._input_style())
        form.addWidget(self.branch_combo, 1, 1)

        # Başlık
        form.addWidget(QLabel("Başlık *:"), 2, 0)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Örn: Merkez Şube Ekim Kirası")
        self.title_input.setStyleSheet(self._input_style())
        form.addWidget(self.title_input, 2, 1)

        # Muhatap
        form.addWidget(QLabel("Muhatap Adı:"), 3, 0)
        self.payee_input = QLineEdit()
        self.payee_input.setPlaceholderText("Örn: Ahmet Yılmaz, ABC Emlak...")
        self.payee_input.setStyleSheet(self._input_style())
        form.addWidget(self.payee_input, 3, 1)

        # Toplam Tutar
        form.addWidget(QLabel("Toplam Tutar (₺) *:"), 4, 0)
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 999999999999.99)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setValue(0)
        self.amount_spin.setStyleSheet(self._input_style())
        self.amount_spin.valueChanged.connect(self.update_installment_hint)
        form.addWidget(self.amount_spin, 4, 1)

        # Taksit
        form.addWidget(QLabel("Taksit Sayısı:"), 5, 0)
        self.installment_spin = QSpinBox()
        self.installment_spin.setRange(1, 120)
        self.installment_spin.setValue(1)
        self.installment_spin.setSuffix(" taksit")
        self.installment_spin.setStyleSheet(self._input_style())
        self.installment_spin.valueChanged.connect(self.update_installment_hint)
        form.addWidget(self.installment_spin, 5, 1)

        # Taksit bilgisi
        self.installment_info = QLabel("")
        self.installment_info.setStyleSheet(f"color: {AppStyles.TEXT_MUTED}; font-size: 9pt;")
        form.addWidget(self.installment_info, 5, 2)

        # İlk Vade Tarihi
        form.addWidget(QLabel("İlk Vade Tarihi *:"), 6, 0)
        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDate(QDate.currentDate().addDays(7))
        self.due_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.due_date_edit.setStyleSheet(self._input_style())
        form.addWidget(self.due_date_edit, 6, 1)

        # Ödeme Yöntemi
        form.addWidget(QLabel("Ödeme Yöntemi:"), 7, 0)
        self.method_combo = QComboBox()
        self.method_combo.addItems(PAYMENT_METHODS)
        self.method_combo.setStyleSheet(self._input_style())
        form.addWidget(self.method_combo, 7, 1)

        # Ödenecek Hesap (Kasa/Banka)
        form.addWidget(QLabel("Ödenecek Hesap:"), 8, 0)
        self.account_combo = QComboBox()
        self.account_combo.addItem("(Şimdi seçme - ödeme anında belirle)", None)
        try:
            accounts = db.fetch_all(
                "SELECT id, bank_name, account_name FROM BankAccounts WHERE is_active = TRUE ORDER BY account_name"
            )
            for a in accounts:
                label = f"🏦 {a.get('bank_name') or ''} - {a.get('account_name') or ''}"
                self.account_combo.addItem(label.strip(), a['id'])
        except Exception:
            pass
        self.account_combo.setStyleSheet(self._input_style())
        form.addWidget(self.account_combo, 8, 1)

        # Hatırlatma Günü
        form.addWidget(QLabel("Hatırlatma (gün önce):"), 9, 0)
        self.reminder_spin = QSpinBox()
        self.reminder_spin.setRange(0, 30)
        self.reminder_spin.setValue(3)
        self.reminder_spin.setSuffix(" gün önce")
        self.reminder_spin.setStyleSheet(self._input_style())
        form.addWidget(self.reminder_spin, 9, 1)

        # Not
        form.addWidget(QLabel("Notlar:"), 10, 0)
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(70)
        self.notes_input.setStyleSheet(self._input_style())
        form.addWidget(self.notes_input, 10, 1, 1, 2)

        layout.addLayout(form)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"background-color: transparent; color: {AppStyles.TEXT_SECONDARY}; border: 1px solid {AppStyles.BORDER}; border-radius: 8px; padding: 8px 16px;")
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Kaydet")
        save_btn.clicked.connect(self.save)
        save_btn.setStyleSheet(f"background-color: {AppStyles.PRIMARY}; color: white; border: none; border-radius: 8px; padding: 8px 22px; font-weight: bold;")
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        self.setLayout(layout)

    def on_type_changed(self):
        """Plan tipi değiştiğinde başlık placeholder'ı güncelle"""
        plan_type = self.type_combo.currentData()
        placeholders = {
            'personel': 'Örn: Ahmet Yılmaz Ekim Maaşı',
            'kira':     'Örn: Merkez Şube Ekim Kirası',
            'taksit':   'Örn: Ford Transit Kredisi 3. Taksit',
            'diger':    'Örn: Muhasebe Danışmanlık Ödemesi',
        }
        self.title_input.setPlaceholderText(placeholders.get(plan_type, 'Ödeme başlığı'))

    def update_installment_hint(self):
        val = self.installment_spin.value()
        total_amount = self.amount_spin.value()
        if val > 1 and total_amount > 0:
            per = total_amount / val
            self.installment_info.setText(f"→ Aylık {per:,.2f} ₺ × {val} taksit")
        else:
            self.installment_info.setText("")

    def save(self):
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Uyarı", "Başlık boş bırakılamaz!")
            return

        total_amount = self.amount_spin.value()
        if total_amount <= 0:
            QMessageBox.warning(self, "Uyarı", "Toplam tutar 0'dan büyük olmalıdır!")
            return

        installment_count = self.installment_spin.value()
        # Backend servisi 'amount' alanını her bir taksit için ödenecek tutar olarak kaydeder.
        # Kullanıcı 'Toplam Tutar' girdiğinden her taksit başına düşen tutarı hesaplayıp servise iletiyoruz:
        installment_amount = round(total_amount / installment_count, 2) if installment_count > 1 else total_amount

        data = {
            'branch_id': self.branch_combo.currentData(),
            'plan_type': self.type_combo.currentData(),
            'title': title,
            'payee_type': self.type_combo.currentData(),
            'payee_name': self.payee_input.text().strip(),
            'amount': installment_amount,
            'total_amount': total_amount,
            'installment_count': installment_count,
            'due_date': self.due_date_edit.date().toString("yyyy-MM-dd"),
            'payment_method': self.method_combo.currentText(),
            'account_id': self.account_combo.currentData(),
            'reminder_days': self.reminder_spin.value(),
            'notes': self.notes_input.toPlainText().strip(),
        }

        user_id = getattr(self.user, 'id', None)
        success, msg, _ = payment_plan_service.create_plan(data, user_id)
        if success:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _input_style(self):
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 10pt;
        """


class MarkPaidDialog(QDialog):
    """Ödeme Yap Dialog'u"""

    def __init__(self, plan: dict, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.setWindowTitle("💰 Ödeme Yap")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("💰 Ödeme Yap")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.GREEN};")
        layout.addWidget(title)

        # Plan bilgisi
        info = QFrame()
        info.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                padding: 12px;
                border: 1px solid {AppStyles.BORDER};
            }}
        """)
        info_layout = QVBoxLayout(info)
        info_layout.setSpacing(4)

        t_lbl = QLabel(f"<b>{self.plan.get('title', '-')}</b>")
        t_lbl.setStyleSheet(f"font-size: 11pt; color: {AppStyles.TEXT_PRIMARY};")
        info_layout.addWidget(t_lbl)

        amt = float(self.plan.get('amount') or 0)
        a_lbl = QLabel(f"Ödenecek Tutar: <b style='color:{AppStyles.GREEN};'>{amt:,.2f} ₺</b>")
        a_lbl.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_PRIMARY};")
        info_layout.addWidget(a_lbl)

        if self.plan.get('due_date'):
            d_lbl = QLabel(f"Vade: {self.plan.get('due_date')}")
            d_lbl.setStyleSheet(f"font-size: 9pt; color: {AppStyles.TEXT_MUTED};")
            info_layout.addWidget(d_lbl)

        layout.addWidget(info)

        form = QGridLayout()
        form.setSpacing(10)

        # Ödeme Tarihi
        form.addWidget(QLabel("Ödeme Tarihi *:"), 0, 0)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setStyleSheet(self._input_style())
        form.addWidget(self.date_edit, 0, 1)

        # Hesap
        form.addWidget(QLabel("Ödenecek Hesap *:"), 1, 0)
        self.account_combo = QComboBox()
        self.account_combo.addItem("(Hesap seçilmedi - sadece işaretle)", None)
        try:
            accounts = db.fetch_all(
                "SELECT id, bank_name, account_name, balance FROM BankAccounts WHERE is_active = TRUE ORDER BY account_name"
            )
            for a in accounts:
                label = f"🏦 {a.get('bank_name') or ''} - {a.get('account_name') or ''} ({float(a.get('balance') or 0):,.2f} ₺)"
                self.account_combo.addItem(label.strip(), a['id'])
        except Exception:
            pass
        if self.plan.get('account_id'):
            idx = self.account_combo.findData(self.plan['account_id'])
            if idx >= 0:
                self.account_combo.setCurrentIndex(idx)
        self.account_combo.setStyleSheet(self._input_style())
        form.addWidget(self.account_combo, 1, 1)

        # Açıklama
        form.addWidget(QLabel("Açıklama:"), 2, 0)
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Ödeme notu (opsiyonel)")
        self.desc_input.setStyleSheet(self._input_style())
        form.addWidget(self.desc_input, 2, 1)

        layout.addLayout(form)

        warning = QLabel("ℹ️ Hesap seçilirse kasa/banka bakiyesinden otomatik düşülür ve hareket kaydı oluşturulur.")
        warning.setStyleSheet(f"color: {AppStyles.CYAN}; font-size: 9pt;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"background-color: transparent; color: {AppStyles.TEXT_SECONDARY}; border: 1px solid {AppStyles.BORDER}; border-radius: 8px; padding: 8px 16px;")
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("✅ Ödemeyi Kaydet")
        save_btn.clicked.connect(self.save)
        save_btn.setStyleSheet(f"background-color: {AppStyles.GREEN}; color: white; border: none; border-radius: 8px; padding: 8px 22px; font-weight: bold;")
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        self.setLayout(layout)

    def save(self):
        plan_id = self.plan['id']
        paid_date = self.date_edit.date().toString("yyyy-MM-dd")
        account_id = self.account_combo.currentData()
        desc = self.desc_input.text().strip()

        user_id = None
        parent = self.parent()
        if parent and hasattr(parent, 'user'):
            user_id = getattr(parent.user, 'id', None)

        success, msg = payment_plan_service.mark_as_paid(
            plan_id=plan_id,
            paid_date=paid_date,
            account_id=account_id,
            description=desc,
            user_id=user_id
        )
        if success:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _input_style(self):
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 10pt;
        """


class NewEmployeeDialog(QDialog):
    """Yeni Personel Dialog'u"""

    def __init__(self, branch_id: int = None, employee_id: int = None, parent=None):
        super().__init__(parent)
        self.branch_id = branch_id
        self.employee_id = employee_id
        self.setWindowTitle("➕ Yeni Personel" if not employee_id else "✏️ Personel Düzenle")
        self.setMinimumWidth(560)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()
        if employee_id:
            self.load_employee()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title_text = "➕ Yeni Personel Ekle" if not self.employee_id else "✏️ Personel Düzenle"
        title = QLabel(title_text)
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        layout.addWidget(title)

        form = QGridLayout()
        form.setSpacing(10)

        # Personel Kodu
        form.addWidget(QLabel("Personel Kodu:"), 0, 0)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Boş bırakılırsa otomatik üretilir (EMP-XXXX)")
        self.code_input.setStyleSheet(self._input_style())
        form.addWidget(self.code_input, 0, 1)

        # Ad Soyad
        form.addWidget(QLabel("Ad Soyad *:"), 1, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: Ahmet Yılmaz")
        self.name_input.setStyleSheet(self._input_style())
        form.addWidget(self.name_input, 1, 1)

        # TC Kimlik
        form.addWidget(QLabel("TC Kimlik No:"), 2, 0)
        self.tc_input = QLineEdit()
        self.tc_input.setPlaceholderText("11 haneli")
        self.tc_input.setMaxLength(11)
        self.tc_input.setStyleSheet(self._input_style())
        form.addWidget(self.tc_input, 2, 1)

        # Telefon
        form.addWidget(QLabel("Telefon:"), 3, 0)
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("05XX XXX XX XX")
        self.phone_input.setStyleSheet(self._input_style())
        form.addWidget(self.phone_input, 3, 1)

        # Email
        form.addWidget(QLabel("E-posta:"), 4, 0)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("ornek@email.com")
        self.email_input.setStyleSheet(self._input_style())
        form.addWidget(self.email_input, 4, 1)

        # Şube
        form.addWidget(QLabel("Şube:"), 5, 0)
        self.branch_combo = QComboBox()
        self.branch_combo.addItem("(Şube seçilmedi)", None)
        try:
            branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY name")
            for b in branches:
                self.branch_combo.addItem(f"🏢 {b['name']}", b['id'])
        except Exception:
            pass
        if self.branch_id:
            idx = self.branch_combo.findData(self.branch_id)
            if idx >= 0:
                self.branch_combo.setCurrentIndex(idx)
        self.branch_combo.setStyleSheet(self._input_style())
        form.addWidget(self.branch_combo, 5, 1)

        # Pozisyon
        form.addWidget(QLabel("Pozisyon:"), 6, 0)
        self.position_input = QLineEdit()
        self.position_input.setPlaceholderText("Örn: Fırın Ustası, Kasiyer")
        self.position_input.setStyleSheet(self._input_style())
        form.addWidget(self.position_input, 6, 1)

        # Departman
        form.addWidget(QLabel("Departman:"), 7, 0)
        self.dept_input = QLineEdit()
        self.dept_input.setPlaceholderText("Örn: Üretim, Satış, Muhasebe")
        self.dept_input.setStyleSheet(self._input_style())
        form.addWidget(self.dept_input, 7, 1)

        # İşe Giriş
        form.addWidget(QLabel("İşe Giriş Tarihi:"), 8, 0)
        self.hire_date_edit = QDateEdit()
        self.hire_date_edit.setCalendarPopup(True)
        self.hire_date_edit.setDate(QDate.currentDate())
        self.hire_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.hire_date_edit.setStyleSheet(self._input_style())
        form.addWidget(self.hire_date_edit, 8, 1)

        # Aylık Maaş
        form.addWidget(QLabel("Aylık Brüt Maaş (₺) *:"), 9, 0)
        self.salary_spin = QDoubleSpinBox()
        self.salary_spin.setRange(0, 999999999999.99)
        self.salary_spin.setDecimals(2)
        self.salary_spin.setValue(0)
        self.salary_spin.setStyleSheet(self._input_style())
        form.addWidget(self.salary_spin, 9, 1)

        # Maaş Günü
        form.addWidget(QLabel("Maaş Ödeme Günü:"), 10, 0)
        self.salary_day_spin = QSpinBox()
        self.salary_day_spin.setRange(1, 28)
        self.salary_day_spin.setValue(1)
        self.salary_day_spin.setSuffix(". gün")
        self.salary_day_spin.setStyleSheet(self._input_style())
        form.addWidget(self.salary_day_spin, 10, 1)

        # IBAN
        form.addWidget(QLabel("IBAN:"), 11, 0)
        self.iban_input = QLineEdit()
        self.iban_input.setPlaceholderText("TR__ ____ ____ ____ ____ ____ __")
        self.iban_input.setMaxLength(34)
        self.iban_input.setStyleSheet(self._input_style())
        form.addWidget(self.iban_input, 11, 1)

        # Adres
        form.addWidget(QLabel("Adres:"), 12, 0)
        self.address_input = QTextEdit()
        self.address_input.setMaximumHeight(60)
        self.address_input.setStyleSheet(self._input_style())
        form.addWidget(self.address_input, 12, 1)

        # Not
        form.addWidget(QLabel("Notlar:"), 13, 0)
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(60)
        self.notes_input.setStyleSheet(self._input_style())
        form.addWidget(self.notes_input, 13, 1)

        layout.addLayout(form)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"background-color: transparent; color: {AppStyles.TEXT_SECONDARY}; border: 1px solid {AppStyles.BORDER}; border-radius: 8px; padding: 8px 16px;")
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Kaydet")
        save_btn.clicked.connect(self.save)
        save_btn.setStyleSheet(f"background-color: {AppStyles.PRIMARY}; color: white; border: none; border-radius: 8px; padding: 8px 22px; font-weight: bold;")
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        self.setLayout(layout)

    def load_employee(self):
        emp = employee_service.get_employee(self.employee_id)
        if not emp:
            return
        self.code_input.setText(emp.get('employee_code') or '')
        self.name_input.setText(emp.get('full_name') or '')
        self.tc_input.setText(emp.get('national_id') or '')
        self.phone_input.setText(emp.get('phone') or '')
        self.email_input.setText(emp.get('email') or '')
        idx = self.branch_combo.findData(emp.get('branch_id'))
        if idx >= 0:
            self.branch_combo.setCurrentIndex(idx)
        self.position_input.setText(emp.get('position') or '')
        self.dept_input.setText(emp.get('department') or '')
        if emp.get('hire_date'):
            self.hire_date_edit.setDate(QDate.fromString(str(emp['hire_date']), "yyyy-MM-dd"))
        self.salary_spin.setValue(float(emp.get('monthly_salary') or 0))
        self.salary_day_spin.setValue(int(emp.get('salary_day') or 1))
        self.iban_input.setText(emp.get('iban') or '')
        self.address_input.setText(emp.get('address') or '')
        self.notes_input.setText(emp.get('notes') or '')

    def save(self):
        full_name = self.name_input.text().strip()
        if not full_name:
            QMessageBox.warning(self, "Uyarı", "Ad Soyad boş bırakılamaz!")
            return

        if self.salary_spin.value() <= 0:
            QMessageBox.warning(self, "Uyarı", "Aylık brüt maaş 0'dan büyük olmalıdır!")
            return

        data = {
            'employee_code': self.code_input.text().strip(),
            'full_name': full_name,
            'national_id': self.tc_input.text().strip(),
            'phone': self.phone_input.text().strip(),
            'email': self.email_input.text().strip(),
            'branch_id': self.branch_combo.currentData(),
            'position': self.position_input.text().strip(),
            'department': self.dept_input.text().strip(),
            'hire_date': self.hire_date_edit.date().toString("yyyy-MM-dd"),
            'monthly_salary': self.salary_spin.value(),
            'salary_day': self.salary_day_spin.value(),
            'iban': self.iban_input.text().strip(),
            'address': self.address_input.toPlainText().strip(),
            'notes': self.notes_input.toPlainText().strip(),
        }

        if self.employee_id:
            success, msg = employee_service.update_employee(self.employee_id, data)
        else:
            success, msg, _ = employee_service.add_employee(data)

        if success:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _input_style(self):
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 10pt;
        """


class GiveAdvanceDialog(QDialog):
    """Avans Verme Dialog'u (Tam / Taksitli)"""

    def __init__(self, employee_id: int = None, branch_id: int = None, parent=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.branch_id = branch_id
        self.setWindowTitle("💵 Personel Avansı Ver")
        self.setMinimumWidth(520)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("💵 Personel Avansı Ver")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.ORANGE};")
        layout.addWidget(title)

        form = QGridLayout()
        form.setSpacing(10)

        # Personel
        form.addWidget(QLabel("Personel *:"), 0, 0)
        self.emp_combo = QComboBox()
        try:
            employees = employee_service.get_employees(active_only=True, branch_id=self.branch_id if self.branch_id else None)
            if not employees and self.branch_id:
                employees = employee_service.get_employees(active_only=True)
            for e in employees:
                label = f"{e.get('employee_code') or ''} - {e.get('full_name')} ({e.get('position') or ''})"
                self.emp_combo.addItem(label.strip(), e['id'])
        except Exception:
            pass
        if self.employee_id:
            idx = self.emp_combo.findData(self.employee_id)
            if idx >= 0:
                self.emp_combo.setCurrentIndex(idx)
        self.emp_combo.setStyleSheet(self._input_style())
        self.emp_combo.currentIndexChanged.connect(self.update_emp_info)
        form.addWidget(self.emp_combo, 0, 1)

        # Personel bilgisi (açık avans)
        self.emp_info = QLabel("")
        self.emp_info.setStyleSheet(f"color: {AppStyles.TEXT_MUTED}; font-size: 9pt;")
        form.addWidget(self.emp_info, 1, 1)

        # Avans Tutarı
        form.addWidget(QLabel("Avans Tutarı (₺) *:"), 2, 0)
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 999999999999.99)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setStyleSheet(self._input_style())
        self.amount_spin.valueChanged.connect(self.update_deduction_hint)
        form.addWidget(self.amount_spin, 2, 1)

        # Kesinti Modu
        form.addWidget(QLabel("Kesinti Şekli:"), 3, 0)
        mode_layout = QHBoxLayout()
        self.mode_full = QRadioButton("Tam kesinti")
        self.mode_inst = QRadioButton("Taksitli")
        self.mode_full.setChecked(True)
        self.mode_full.setStyleSheet(f"color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt;")
        self.mode_inst.setStyleSheet(f"color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt;")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.mode_full, 1)
        self.mode_group.addButton(self.mode_inst, 2)
        self.mode_full.toggled.connect(self.update_deduction_hint)
        mode_layout.addWidget(self.mode_full)
        mode_layout.addWidget(self.mode_inst)
        mode_layout.addStretch()
        form.addLayout(mode_layout, 3, 1)

        # Taksit Ayı
        form.addWidget(QLabel("Kaç Ayda Kesilsin:"), 4, 0)
        self.months_spin = QSpinBox()
        self.months_spin.setRange(1, 24)
        self.months_spin.setValue(1)
        self.months_spin.setSuffix(" ay")
        self.months_spin.setEnabled(False)
        self.months_spin.setStyleSheet(self._input_style())
        self.months_spin.valueChanged.connect(self.update_deduction_hint)
        self.mode_inst.toggled.connect(lambda checked: self.months_spin.setEnabled(checked))
        form.addWidget(self.months_spin, 4, 1)

        # Kesinti özeti
        self.deduction_hint = QLabel("")
        self.deduction_hint.setStyleSheet(f"color: {AppStyles.CYAN}; font-size: 9.5pt; font-weight: bold;")
        form.addWidget(self.deduction_hint, 5, 1)

        # Tarih
        form.addWidget(QLabel("Avans Tarihi *:"), 6, 0)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setStyleSheet(self._input_style())
        form.addWidget(self.date_edit, 6, 1)

        # Kasa/Banka Hesap
        form.addWidget(QLabel("Ödenecek Hesap:"), 7, 0)
        self.account_combo = QComboBox()
        self.account_combo.addItem("(Hesap seçilmedi - sadece kayıt)", None)
        try:
            accounts = db.fetch_all(
                "SELECT id, bank_name, account_name, balance FROM BankAccounts WHERE is_active = TRUE ORDER BY account_name"
            )
            for a in accounts:
                label = f"🏦 {a.get('bank_name') or ''} - {a.get('account_name') or ''} ({float(a.get('balance') or 0):,.2f} ₺)"
                self.account_combo.addItem(label.strip(), a['id'])
        except Exception:
            pass
        self.account_combo.setStyleSheet(self._input_style())
        form.addWidget(self.account_combo, 7, 1)

        # Açıklama
        form.addWidget(QLabel("Açıklama:"), 8, 0)
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Örn: Ev kirası için avans")
        self.desc_input.setStyleSheet(self._input_style())
        form.addWidget(self.desc_input, 8, 1)

        layout.addLayout(form)

        info_lbl = QLabel(
            "ℹ️ Avans, personele verilen borç olarak cari hesabına işlenir. "
            "Maaş ödemesi yapılırken otomatik olarak kesilir (maks. %25 brüt maaş)."
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet(f"color: {AppStyles.TEXT_MUTED}; font-size: 9pt; padding: 6px; background-color: {AppStyles.BG_MEDIUM}; border-radius: 6px;")
        layout.addWidget(info_lbl)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"background-color: transparent; color: {AppStyles.TEXT_SECONDARY}; border: 1px solid {AppStyles.BORDER}; border-radius: 8px; padding: 8px 16px;")
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("💵 Avansı Kaydet")
        save_btn.clicked.connect(self.save)
        save_btn.setStyleSheet(f"background-color: {AppStyles.ORANGE}; color: white; border: none; border-radius: 8px; padding: 8px 22px; font-weight: bold;")
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        self.setLayout(layout)
        self.update_emp_info()

    def update_emp_info(self):
        emp_id = self.emp_combo.currentData()
        if not emp_id:
            self.emp_info.setText("")
            return
        try:
            total = payment_plan_service.get_total_open_advance(emp_id)
            self.emp_info.setText(f"ℹ️ Açık avans toplamı: {total:,.2f} ₺")
        except Exception:
            self.emp_info.setText("")

    def update_deduction_hint(self):
        amt = self.amount_spin.value()
        if self.mode_full.isChecked():
            self.deduction_hint.setText(f"→ Bu ayki maaştan {amt:,.2f} ₺ kesilecek")
        else:
            months = self.months_spin.value()
            if months > 0:
                per = amt / months
                self.deduction_hint.setText(f"→ Ayda {per:,.2f} ₺ × {months} ay = {amt:,.2f} ₺")

    def save(self):
        emp_id = self.emp_combo.currentData()
        if not emp_id:
            QMessageBox.warning(self, "Uyarı", "Personel seçiniz!")
            return
        if self.amount_spin.value() <= 0:
            QMessageBox.warning(self, "Uyarı", "Avans tutarı 0'dan büyük olmalıdır!")
            return

        mode = 'full' if self.mode_full.isChecked() else 'installment'
        months = self.months_spin.value() if mode == 'installment' else 1

        success, msg, _ = payment_plan_service.give_advance(
            employee_id=emp_id,
            amount=self.amount_spin.value(),
            advance_date=self.date_edit.date().toString("yyyy-MM-dd"),
            deduction_mode=mode,
            installment_months=months,
            account_id=self.account_combo.currentData(),
            description=self.desc_input.text().strip()
        )
        if success:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _input_style(self):
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 10pt;
        """


class CreateSalaryPlanDialog(QDialog):
    """Maaş Planı Oluştur Dialog'u (Otomatik avans mahsuplu)"""

    def __init__(self, employee_id: int = None, branch_id: int = None, parent=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.branch_id = branch_id
        self.setWindowTitle("📅 Maaş Planı Oluştur")
        self.setMinimumWidth(520)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("📅 Maaş Planı Oluştur")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        layout.addWidget(title)

        form = QGridLayout()
        form.setSpacing(10)

        # Personel
        form.addWidget(QLabel("Personel *:"), 0, 0)
        self.emp_combo = QComboBox()
        try:
            employees = employee_service.get_employees(active_only=True, branch_id=self.branch_id if self.branch_id else None)
            if not employees and self.branch_id:
                employees = employee_service.get_employees(active_only=True)
            for e in employees:
                label = f"{e.get('employee_code') or ''} - {e.get('full_name')}"
                self.emp_combo.addItem(label.strip(), e['id'])
        except Exception:
            pass
        if self.employee_id:
            idx = self.emp_combo.findData(self.employee_id)
            if idx >= 0:
                self.emp_combo.setCurrentIndex(idx)
        self.emp_combo.setStyleSheet(self._input_style())
        self.emp_combo.currentIndexChanged.connect(self.on_emp_changed)
        form.addWidget(self.emp_combo, 0, 1)

        # Dönem Ay
        form.addWidget(QLabel("Dönem Ay *:"), 1, 0)
        self.month_combo = QComboBox()
        months = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        for i, m in enumerate(months, start=1):
            self.month_combo.addItem(m, i)
        self.month_combo.setCurrentIndex(datetime.now().month - 1)
        self.month_combo.setStyleSheet(self._input_style())
        form.addWidget(self.month_combo, 1, 1)

        # Dönem Yıl
        form.addWidget(QLabel("Dönem Yıl *:"), 2, 0)
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2100)
        self.year_spin.setValue(datetime.now().year)
        self.year_spin.setStyleSheet(self._input_style())
        form.addWidget(self.year_spin, 2, 1)

        # Brüt Maaş
        form.addWidget(QLabel("Brüt Maaş (₺):"), 3, 0)
        self.gross_spin = QDoubleSpinBox()
        self.gross_spin.setRange(0, 999999999999.99)
        self.gross_spin.setDecimals(2)
        self.gross_spin.setStyleSheet(self._input_style())
        self.gross_spin.valueChanged.connect(self.on_gross_changed)
        form.addWidget(self.gross_spin, 3, 1)

        # Vade Tarihi
        form.addWidget(QLabel("Ödeme Tarihi *:"), 4, 0)
        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        next_month = QDate.currentDate().addMonths(1)
        self.due_date_edit.setDate(QDate(next_month.year(), next_month.month(), 1))
        self.due_date_edit.setDisplayFormat("dd.MM.yyyy")
        self.due_date_edit.setStyleSheet(self._input_style())
        form.addWidget(self.due_date_edit, 4, 1)

        # Hesap
        form.addWidget(QLabel("Ödeme Hesabı:"), 5, 0)
        self.account_combo = QComboBox()
        self.account_combo.addItem("(Ödeme anında seç)", None)
        try:
            accounts = db.fetch_all(
                "SELECT id, bank_name, account_name FROM BankAccounts WHERE is_active = TRUE ORDER BY account_name"
            )
            for a in accounts:
                label = f"🏦 {a.get('bank_name') or ''} - {a.get('account_name') or ''}"
                self.account_combo.addItem(label.strip(), a['id'])
        except Exception:
            pass
        self.account_combo.setStyleSheet(self._input_style())
        form.addWidget(self.account_combo, 5, 1)

        # Not
        form.addWidget(QLabel("Not:"), 6, 0)
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("(opsiyonel)")
        self.notes_input.setStyleSheet(self._input_style())
        form.addWidget(self.notes_input, 6, 1)

        layout.addLayout(form)

        # Avans mahsup bilgisi
        self.advance_info = QLabel("")
        self.advance_info.setWordWrap(True)
        self.advance_info.setStyleSheet(f"""
            background-color: rgba(245, 158, 11, 0.15);
            color: {AppStyles.ORANGE};
            border: 1px solid {AppStyles.ORANGE};
            border-radius: 8px;
            padding: 10px;
            font-size: 9.5pt;
            font-weight: bold;
        """)
        self.advance_info.setVisible(False)
        layout.addWidget(self.advance_info)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"background-color: transparent; color: {AppStyles.TEXT_SECONDARY}; border: 1px solid {AppStyles.BORDER}; border-radius: 8px; padding: 8px 16px;")
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("📅 Maaş Planı Oluştur")
        save_btn.clicked.connect(self.save)
        save_btn.setStyleSheet(f"background-color: {AppStyles.PRIMARY}; color: white; border: none; border-radius: 8px; padding: 8px 22px; font-weight: bold;")
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        self.setLayout(layout)
        self.on_emp_changed()

    def on_emp_changed(self):
        """Personel seçildiğinde maaş ve avans bilgisini getir"""
        emp_id = self.emp_combo.currentData()
        if not emp_id:
            return
        emp = employee_service.get_employee(emp_id)
        if emp:
            if self.gross_spin.value() == 0:
                self.gross_spin.setValue(float(emp.get('monthly_salary') or 0))
            # Maaş gününe göre vade tarihini ayarla
            salary_day = int(emp.get('salary_day') or 1)
            today = QDate.currentDate()
            next_month = today.addMonths(1)
            try:
                due = QDate(next_month.year(), next_month.month(), min(salary_day, 28))
                self.due_date_edit.setDate(due)
            except Exception:
                pass

        # Avans bilgisi
        try:
            total_adv = payment_plan_service.get_total_open_advance(emp_id)
            if total_adv > 0:
                gross = self.gross_spin.value()
                max_ded = gross * 0.25
                actual_ded = min(total_adv, max_ded)
                net = gross - actual_ded
                self.advance_info.setText(
                    f"⚠️ Bu personelin <b>{total_adv:,.2f} ₺</b> açık avansı var.<br>"
                    f"Maaştan <b>{actual_ded:,.2f} ₺</b> kesilecek (maks. %25).<br>"
                    f"Net ödenecek: <b>{net:,.2f} ₺</b>"
                )
                self.advance_info.setVisible(True)
            else:
                self.advance_info.setVisible(False)
        except Exception:
            self.advance_info.setVisible(False)

    def on_gross_changed(self):
        self.on_emp_changed()

    def save(self):
        emp_id = self.emp_combo.currentData()
        if not emp_id:
            QMessageBox.warning(self, "Uyarı", "Personel seçiniz!")
            return
        if self.gross_spin.value() <= 0:
            QMessageBox.warning(self, "Uyarı", "Brüt maaş 0'dan büyük olmalıdır!")
            return

        success, msg, _ = payment_plan_service.create_salary_plan(
            employee_id=emp_id,
            period_month=self.month_combo.currentData(),
            period_year=self.year_spin.value(),
            due_date=self.due_date_edit.date().toString("yyyy-MM-dd"),
            gross_salary=self.gross_spin.value(),
            account_id=self.account_combo.currentData(),
            notes=self.notes_input.text().strip()
        )
        if success:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _input_style(self):
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 10pt;
        """


# ==================== DETAY VE DÜZENLEME DİALOG'U ====================

class PaymentPlanDetailDialog(QDialog):
    """
    Ödeme Planı Detay ve Düzenleme Dialog'u
    - Plan ve taksit verilerini detaylı gözlemleme
    - Başlık, muhatap, ödeme yöntemi, şube, notlar ve taksit detaylarını düzenleme
    - Taksitli planlarda her bir taksitin durumunu ve ödeme detaylarını detaylı tabloda listeleme
    - Taksitleri doğrudan ödeme veya silme
    - Tüm planı güvenle silme
    """

    def __init__(self, record: dict, user: User, parent=None):
        super().__init__(parent)
        self.record = record
        self.user = user
        self.parent_page = parent
        self.items = list(record.get('group_items') or [record.get('item')])
        self.items.sort(key=lambda x: (int(x.get('installment_no') or 0), str(x.get('due_date') or '')))
        self.is_installment = (len(self.items) > 1) or record.get('is_installment', False)

        self.setWindowTitle("📋 Ödeme Planı Detayı ve Düzenleme")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        self.setMinimumWidth(980)
        self.setMinimumHeight(660)
        self.resize(1100, 800)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(22, 16, 22, 16)

        # 1. Başlık ve Açıklama
        top_box = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        self.dialog_title = QLabel("📋 Ödeme Planı Detayı")
        self.dialog_title.setStyleSheet(f"font-size: 15pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        title_box.addWidget(self.dialog_title)

        sub_desc = QLabel("Plan verilerini gözlemleyebilir, taksitleri yönetebilir, düzenleyebilir veya silebilirsiniz.")
        sub_desc.setStyleSheet(f"font-size: 9pt; color: {AppStyles.TEXT_SECONDARY};")
        title_box.addWidget(sub_desc)
        top_box.addLayout(title_box)
        top_box.addStretch()
        main_layout.addLayout(top_box)

        # 2. KPI / Özet Kartları
        self.kpi_layout = QHBoxLayout()
        self.kpi_layout.setSpacing(10)

        self.kpi_total_card = self._create_kpi_card("💰", "Toplam Tutar", "0,00 ₺", AppStyles.CYAN)
        self.kpi_rem_card = self._create_kpi_card("⏳", "Kalan Tutar", "0,00 ₺", AppStyles.ORANGE)
        self.kpi_inst_card = self._create_kpi_card("📅", "Taksit Durumu", "1 / 1", AppStyles.PURPLE)
        self.kpi_status_card = self._create_kpi_card("📌", "Genel Durum", "Bekliyor", AppStyles.GREEN)

        self.kpi_layout.addWidget(self.kpi_total_card)
        self.kpi_layout.addWidget(self.kpi_rem_card)
        self.kpi_layout.addWidget(self.kpi_inst_card)
        self.kpi_layout.addWidget(self.kpi_status_card)
        main_layout.addLayout(self.kpi_layout)

        # 3. Genel Bilgiler Formu
        form_frame = QFrame()
        form_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 10px;
                padding: 6px 12px;
            }}
        """)
        form_layout = QGridLayout(form_frame)
        form_layout.setSpacing(6)
        form_layout.setContentsMargins(10, 8, 10, 8)

        first_item = self.items[0] if self.items else {}

        # Satır 0: Başlık ve Plan Tipi
        form_layout.addWidget(QLabel("Başlık *:"), 0, 0)
        self.title_input = QLineEdit()
        raw_title = self.record.get('title', first_item.get('title', ''))
        import re
        base_title = re.sub(r'\s*\(\d+/\d+\)$', '', raw_title).strip()
        base_title = re.sub(r'\s*\(Sıradaki:.*?\)$', '', base_title).strip()
        base_title = re.sub(r'\s*\(Tamamı Ödendi\)$', '', base_title).strip()
        self.title_input.setText(base_title)
        self.title_input.setStyleSheet(self._input_style())
        form_layout.addWidget(self.title_input, 0, 1)

        form_layout.addWidget(QLabel("Plan Tipi:"), 0, 2)
        self.type_combo = QComboBox()
        for k, v in PLAN_TYPES.items():
            self.type_combo.addItem(v, k)
        p_type = first_item.get('plan_type', 'diger')
        idx = self.type_combo.findData(p_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.setStyleSheet(self._input_style())
        form_layout.addWidget(self.type_combo, 0, 3)

        # Satır 1: Muhatap ve Şube
        form_layout.addWidget(QLabel("Muhatap Adı:"), 1, 0)
        self.payee_input = QLineEdit()
        self.payee_input.setText(first_item.get('payee_name', '') or '')
        self.payee_input.setStyleSheet(self._input_style())
        form_layout.addWidget(self.payee_input, 1, 1)

        form_layout.addWidget(QLabel("Şube:"), 1, 2)
        self.branch_combo = QComboBox()
        self.branch_combo.addItem("🏢 Genel Merkez (Tümü)", None)
        try:
            branches = db.fetch_all("SELECT id, name FROM Branches WHERE is_active = TRUE ORDER BY name")
            for b in branches:
                self.branch_combo.addItem(f"🏢 {b['name']}", b['id'])
        except Exception:
            pass
        cur_branch = first_item.get('branch_id')
        if cur_branch:
            b_idx = self.branch_combo.findData(cur_branch)
            if b_idx >= 0:
                self.branch_combo.setCurrentIndex(b_idx)
        self.branch_combo.setStyleSheet(self._input_style())
        form_layout.addWidget(self.branch_combo, 1, 3)

        # Satır 2: Ödeme Yöntemi ve Ödeme Hesabı
        form_layout.addWidget(QLabel("Ödeme Yöntemi:"), 2, 0)
        self.method_combo = QComboBox()
        self.method_combo.addItems(PAYMENT_METHODS)
        cur_method = first_item.get('payment_method', 'Havale / EFT')
        m_idx = self.method_combo.findText(cur_method)
        if m_idx >= 0:
            self.method_combo.setCurrentIndex(m_idx)
        self.method_combo.setStyleSheet(self._input_style())
        form_layout.addWidget(self.method_combo, 2, 1)

        form_layout.addWidget(QLabel("Ödeme Hesabı:"), 2, 2)
        self.account_combo = QComboBox()
        self.account_combo.addItem("(Ödeme anında seç / Genel)", None)
        try:
            accounts = db.fetch_all(
                "SELECT id, bank_name, account_name FROM BankAccounts WHERE is_active = TRUE ORDER BY account_name"
            )
            for a in accounts:
                lbl = f"🏦 {a.get('bank_name') or ''} - {a.get('account_name') or ''}".strip(' -')
                self.account_combo.addItem(lbl, a['id'])
        except Exception:
            pass
        cur_acc = first_item.get('account_id')
        if cur_acc:
            a_idx = self.account_combo.findData(cur_acc)
            if a_idx >= 0:
                self.account_combo.setCurrentIndex(a_idx)
        self.account_combo.setStyleSheet(self._input_style())
        form_layout.addWidget(self.account_combo, 2, 3)

        # Satır 3: Hatırlatma ve Notlar
        form_layout.addWidget(QLabel("Hatırlatma (gün):"), 3, 0)
        self.reminder_spin = QSpinBox()
        self.reminder_spin.setRange(0, 30)
        self.reminder_spin.setValue(int(first_item.get('reminder_days') or 3))
        self.reminder_spin.setSuffix(" gün önce")
        self.reminder_spin.setStyleSheet(self._input_style())
        form_layout.addWidget(self.reminder_spin, 3, 1)

        form_layout.addWidget(QLabel("Notlar:"), 3, 2)
        self.notes_input = QLineEdit()
        self.notes_input.setText(first_item.get('notes', '') or '')
        self.notes_input.setPlaceholderText("Opsiyonel ödeme notu...")
        self.notes_input.setStyleSheet(self._input_style())
        form_layout.addWidget(self.notes_input, 3, 3)

        # Tekil plan ise Vade Tarihi ve Tutar form alanlarını da ekle
        if not self.is_installment:
            form_layout.addWidget(QLabel("Vade Tarihi *:"), 4, 0)
            self.single_due_edit = QDateEdit()
            self.single_due_edit.setCalendarPopup(True)
            self.single_due_edit.setDisplayFormat("dd.MM.yyyy")
            d_str = first_item.get('due_date')
            if d_str:
                try:
                    dt = datetime.strptime(str(d_str), '%Y-%m-%d').date()
                    self.single_due_edit.setDate(QDate(dt.year, dt.month, dt.day))
                except Exception:
                    self.single_due_edit.setDate(QDate.currentDate())
            else:
                self.single_due_edit.setDate(QDate.currentDate())
            self.single_due_edit.setStyleSheet(self._input_style())
            form_layout.addWidget(self.single_due_edit, 4, 1)

            form_layout.addWidget(QLabel("Tutar (₺) *:"), 4, 2)
            self.single_amount_spin = QDoubleSpinBox()
            self.single_amount_spin.setRange(0.01, 100000000)
            self.single_amount_spin.setDecimals(2)
            self.single_amount_spin.setValue(float(first_item.get('amount') or 0))
            self.single_amount_spin.setStyleSheet(self._input_style())
            form_layout.addWidget(self.single_amount_spin, 4, 3)

        main_layout.addWidget(form_frame)

        # 4. Taksit Tablosu (Taksitli Plan ise detaylı tablo açılır)
        if self.is_installment:
            sec_header = QHBoxLayout()
            table_lbl = QLabel(f"📑 Taksit Dağılımı ve Detaylı Durum Tablosu ({len(self.items)} Taksit)")
            table_lbl.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {AppStyles.CYAN};")
            sec_header.addWidget(table_lbl)
            sec_header.addStretch()

            hint_lbl = QLabel("ℹ️ Ödenmemiş taksitlerin vade tarihlerini ve tutarlarını satır üzerinden düzenleyebilirsiniz.")
            hint_lbl.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_MUTED};")
            sec_header.addWidget(hint_lbl)
            main_layout.addLayout(sec_header)

            self.inst_table = QTableWidget()
            self.inst_table.setColumnCount(8)
            self.inst_table.setHorizontalHeaderLabels([
                '#', 'Taksit No', 'Vade Tarihi', 'Tutar (₺)',
                'Ödeme Yöntemi', 'Durum', 'Ödenen Tarih', 'İşlem'
            ])
            self.inst_table.setAlternatingRowColors(True)
            self.inst_table.verticalHeader().setVisible(False)
            self.inst_table.setShowGrid(True)
            self.inst_table.setSelectionBehavior(QTableWidget.SelectRows)
            self.inst_table.setSelectionMode(QTableWidget.SingleSelection)
            self.inst_table.setStyleSheet(self._table_style())
            self.inst_table.verticalHeader().setDefaultSectionSize(44)
            self.inst_table.setMinimumHeight(280)

            i_hdr = self.inst_table.horizontalHeader()
            i_hdr.setStretchLastSection(False)
            i_hdr.setSectionResizeMode(QHeaderView.Interactive)
            self.inst_table.setColumnWidth(0, 48)   # #
            self.inst_table.setColumnWidth(1, 95)   # Taksit No
            i_hdr.setSectionResizeMode(2, QHeaderView.Stretch)  # Vade alanı
            i_hdr.setSectionResizeMode(3, QHeaderView.Stretch)  # Tutar alanı
            self.inst_table.setColumnWidth(4, 150)  # Ödeme Yöntemi
            self.inst_table.setColumnWidth(5, 130)  # Durum
            self.inst_table.setColumnWidth(6, 120)  # Ödenen Tarih
            self.inst_table.setColumnWidth(7, 100)  # İşlem

            main_layout.addWidget(self.inst_table, 1)

        # 5. Alt Butonlar (Silme ve Kaydetme)
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 8, 0, 0)

        # Sol taraf: Planı Sil Butonu
        del_plan_btn = QPushButton("🗑️ Planı Sil")
        del_plan_btn.setCursor(Qt.PointingHandCursor)
        del_plan_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.RED}25;
                color: {AppStyles.RED};
                border: 1px solid {AppStyles.RED}70;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.RED};
                color: white;
            }}
        """)
        del_plan_btn.clicked.connect(self.delete_entire_plan)
        btn_bar.addWidget(del_plan_btn)

        btn_bar.addStretch()

        cancel_btn = QPushButton("İptal / Kapat")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_bar.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Değişiklikleri Kaydet")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        save_btn.clicked.connect(self.save_changes)
        btn_bar.addWidget(save_btn)

        main_layout.addLayout(btn_bar)
        self.setLayout(main_layout)

    def _create_kpi_card(self, icon: str, title: str, val: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 10px;
                border-left: 4px solid {color};
                border-top: 1px solid {AppStyles.BORDER};
                border-right: 1px solid {AppStyles.BORDER};
                border-bottom: 1px solid {AppStyles.BORDER};
                padding: 8px 12px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setSpacing(2)
        lay.setContentsMargins(8, 6, 8, 6)

        t_lbl = QLabel(f"{icon} {title}")
        t_lbl.setStyleSheet(f"font-size: 8.5pt; font-weight: bold; color: {AppStyles.TEXT_SECONDARY};")
        lay.addWidget(t_lbl)

        v_lbl = QLabel(val)
        v_lbl.setObjectName("val_label")
        v_lbl.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {color};")
        lay.addWidget(v_lbl)
        return card

    def load_data(self):
        """Verileri yükle, özet kartlarını ve taksit tablosunu doldur"""
        if not self.items:
            return

        total_amt = 0.0
        remaining_amt = 0.0
        paid_count = 0
        total_count = len(self.items)

        for it in self.items:
            amt = float(it.get('amount') or 0)
            st = it.get('status', 'bekliyor')
            total_amt += amt
            if st == 'odendi':
                paid_count += 1
            else:
                remaining_amt += amt

        # KPI kartlarını güncelle
        val_lbl_tot = self.kpi_total_card.findChild(QLabel, "val_label")
        if val_lbl_tot:
            val_lbl_tot.setText(f"{total_amt:,.2f} ₺")

        val_lbl_rem = self.kpi_rem_card.findChild(QLabel, "val_label")
        if val_lbl_rem:
            val_lbl_rem.setText(f"{remaining_amt:,.2f} ₺")
            color = AppStyles.GREEN if remaining_amt <= 0 else AppStyles.ORANGE
            val_lbl_rem.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {color};")

        val_lbl_inst = self.kpi_inst_card.findChild(QLabel, "val_label")
        if val_lbl_inst:
            if self.is_installment:
                val_lbl_inst.setText(f"{paid_count} / {total_count} Ödendi")
            else:
                val_lbl_inst.setText("Tek Seferlik")

        val_lbl_st = self.kpi_status_card.findChild(QLabel, "val_label")
        if val_lbl_st:
            if remaining_amt <= 0:
                st_text = "Ödendi"
                st_color = AppStyles.GREEN
            elif any(it.get('status') == 'gecikti' for it in self.items):
                st_text = "Gecikti"
                st_color = AppStyles.RED
            else:
                st_text = "Bekliyor"
                st_color = AppStyles.ORANGE
            val_lbl_st.setText(st_text)
            val_lbl_st.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {st_color};")

        # Taksit tablosunu doldur
        if self.is_installment and hasattr(self, 'inst_table'):
            self.load_installments_table()

    def load_installments_table(self):
        """Taksitli plandaki tüm taksitleri ayrıntılı tabloya doldurur"""
        self.inst_table.setRowCount(len(self.items))
        self.table_editors = {}  # row_idx -> {date_edit, amount_spin, item_id}

        for row_idx, it in enumerate(self.items):
            inst_id = it['id']
            inst_no = it.get('installment_no') or (row_idx + 1)
            inst_cnt = it.get('installment_count') or len(self.items)
            amt = float(it.get('amount') or 0)
            due_date = str(it.get('due_date') or '')
            method = it.get('payment_method') or 'Havale / EFT'
            status_key = it.get('status', 'bekliyor')
            paid_date = str(it.get('paid_date') or '-') if status_key == 'odendi' else '-'

            # 0. Sıra No
            idx_item = QTableWidgetItem(str(row_idx + 1))
            idx_item.setTextAlignment(Qt.AlignCenter)
            self.inst_table.setItem(row_idx, 0, idx_item)

            # 1. Taksit No
            no_item = QTableWidgetItem(f"{inst_no} / {inst_cnt}")
            no_item.setTextAlignment(Qt.AlignCenter)
            no_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.inst_table.setItem(row_idx, 1, no_item)

            # 2. Vade Tarihi (Ödenmemişse düzenlenebilir QDateEdit, ödenmişse sabit)
            if status_key != 'odendi':
                d_edit = QDateEdit()
                d_edit.setCalendarPopup(True)
                d_edit.setDisplayFormat("dd.MM.yyyy")
                try:
                    dt = datetime.strptime(due_date, '%Y-%m-%d').date()
                    d_edit.setDate(QDate(dt.year, dt.month, dt.day))
                except Exception:
                    d_edit.setDate(QDate.currentDate())
                d_edit.setStyleSheet(self._table_input_style())
                self.inst_table.setCellWidget(row_idx, 2, d_edit)
            else:
                d_item = QTableWidgetItem(due_date)
                d_item.setTextAlignment(Qt.AlignCenter)
                d_item.setFont(QFont("Segoe UI", 9))
                self.inst_table.setItem(row_idx, 2, d_item)
                d_edit = None

            # 3. Tutar (Ödenmemişse düzenlenebilir QDoubleSpinBox, ödenmişse sabit)
            if status_key != 'odendi':
                sp = QDoubleSpinBox()
                sp.setRange(0.01, 100000000)
                sp.setDecimals(2)
                sp.setValue(amt)
                sp.setSuffix(" ₺")
                sp.setStyleSheet(self._table_input_style())
                self.inst_table.setCellWidget(row_idx, 3, sp)
            else:
                a_item = QTableWidgetItem(f"{amt:,.2f} ₺")
                a_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                a_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.inst_table.setItem(row_idx, 3, a_item)
                sp = None

            self.table_editors[row_idx] = {
                'item_id': inst_id,
                'status': status_key,
                'date_edit': d_edit,
                'amount_spin': sp
            }

            # 4. Ödeme Yöntemi
            m_item = QTableWidgetItem(method)
            m_item.setTextAlignment(Qt.AlignCenter)
            self.inst_table.setItem(row_idx, 4, m_item)

            # 5. Durum
            status_labels = {
                'bekliyor': ('🟠 Bekliyor', AppStyles.ORANGE),
                'odendi':   ('✅ Ödendi', AppStyles.GREEN),
                'gecikti':  ('🔴 Gecikti', AppStyles.RED),
                'iptal':    ('⚪ İptal', AppStyles.TEXT_MUTED),
            }
            s_label, s_color = status_labels.get(status_key, (status_key, AppStyles.TEXT_SECONDARY))
            st_item = QTableWidgetItem(s_label)
            st_item.setTextAlignment(Qt.AlignCenter)
            st_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            st_item.setForeground(QColor(s_color))
            self.inst_table.setItem(row_idx, 5, st_item)

            # 6. Ödenen Tarih
            p_item = QTableWidgetItem(paid_date)
            p_item.setTextAlignment(Qt.AlignCenter)
            self.inst_table.setItem(row_idx, 6, p_item)

            # 7. İşlemler (Öde & Sil)
            act_w = QWidget()
            a_lay = QHBoxLayout(act_w)
            a_lay.setContentsMargins(2, 2, 2, 2)
            a_lay.setSpacing(4)
            a_lay.setAlignment(Qt.AlignCenter)

            if status_key != 'odendi':
                # Ödeme Yap butonu
                pay_btn = QPushButton("💰")
                pay_btn.setToolTip("Bu Taksiti Öde")
                pay_btn.setFixedSize(32, 30)
                pay_btn.setStyleSheet(self._mini_btn_style(AppStyles.GREEN))
                pay_btn.clicked.connect(lambda checked, item=it: self.open_installment_pay(item))
                a_lay.addWidget(pay_btn)

                # Taksit Sil butonu
                del_btn = QPushButton("🗑️")
                del_btn.setToolTip("Sadece Bu Taksiti Sil")
                del_btn.setFixedSize(32, 30)
                del_btn.setStyleSheet(self._mini_btn_style(AppStyles.RED))
                del_btn.clicked.connect(lambda checked, item=it: self.delete_single_installment(item))
                a_lay.addWidget(del_btn)
            else:
                ok_lbl = QLabel("✅")
                ok_lbl.setToolTip("Ödeme tamamlandı")
                ok_lbl.setAlignment(Qt.AlignCenter)
                a_lay.addWidget(ok_lbl)

            self.inst_table.setCellWidget(row_idx, 7, act_w)

    def reload_from_db(self):
        """Veritabanından en güncel taksit verilerini çeker ve arayüzü yeniler"""
        fresh_items = []
        for it in self.items:
            fresh = payment_plan_service.get_plan(it['id'])
            if fresh:
                fresh_items.append(fresh)
        self.items = fresh_items
        self.items.sort(key=lambda x: (int(x.get('installment_no') or 0), str(x.get('due_date') or '')))
        self.load_data()

    def open_installment_pay(self, item: dict):
        """Taksit için ödeme dialog'u açar"""
        dlg = MarkPaidDialog(item, self)
        if dlg.exec_() == QDialog.Accepted:
            self.reload_from_db()

    def delete_single_installment(self, item: dict):
        """Tek bir taksit satırını siler"""
        if item.get('status') == 'odendi':
            QMessageBox.warning(self, "Uyarı", "Ödenmiş taksit silinemez!")
            return

        title = item.get('title', 'Bu taksit')
        reply = QMessageBox.question(
            self, "Taksit Sil",
            f"<b>{title}</b> kaydını silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = payment_plan_service.delete_plan(item['id'])
            if success:
                self.items = [x for x in self.items if x['id'] != item['id']]
                if not self.items:
                    QMessageBox.information(self, "Bilgi", "Plandaki tüm taksitler silindi.")
                    self.accept()
                else:
                    self.load_data()
            else:
                QMessageBox.warning(self, "Hata", msg)

    def delete_entire_plan(self):
        """Tüm ödeme planını siler"""
        if not self.items:
            self.reject()
            return

        paid_items = [x for x in self.items if x.get('status') == 'odendi']
        unpaid_items = [x for x in self.items if x.get('status') != 'odendi']

        if not unpaid_items:
            QMessageBox.warning(self, "Uyarı", "Bu plana ait tüm taksitler ödenmiştir. Ödenmiş planlar silinemez!")
            return

        if len(self.items) == 1:
            msg_text = "Bu ödeme planını silmek istediğinize emin misiniz?"
        elif paid_items:
            msg_text = (
                f"Bu plana ait <b>{len(paid_items)}</b> adet ödenmiş taksit korunacaktır.<br>"
                f"Kalan <b>{len(unpaid_items)}</b> adet ödenmemiş taksit silinecektir.<br><br>"
                "Devam etmek istiyor musunuz?"
            )
        else:
            msg_text = (
                f"Bu plana ait <b>tüm {len(unpaid_items)} adet taksit</b> silinecektir.<br><br>"
                "Devam etmek istiyor musunuz?"
            )

        reply = QMessageBox.question(
            self, "Planı Silme Onayı", msg_text,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            unpaid_ids = [x['id'] for x in unpaid_items]
            success, msg, _ = payment_plan_service.delete_plans(unpaid_ids)
            if success:
                QMessageBox.information(self, "Başarılı", msg)
                self.accept()
            else:
                QMessageBox.warning(self, "Hata", msg)

    def save_changes(self):
        """Kullanıcının form ve tablodan yaptığı tüm değişiklikleri kaydeder"""
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Uyarı", "Başlık boş bırakılamaz!")
            return

        payee_name = self.payee_input.text().strip()
        plan_type = self.type_combo.currentData()
        branch_id = self.branch_combo.currentData()
        payment_method = self.method_combo.currentText()
        account_id = self.account_combo.currentData()
        reminder_days = self.reminder_spin.value()
        notes = self.notes_input.text().strip()

        try:
            if not self.is_installment:
                # Tekil plan güncellemesi
                first_id = self.items[0]['id']
                due_date_str = self.single_due_edit.date().toString("yyyy-MM-dd")
                amount_val = self.single_amount_spin.value()
                if amount_val <= 0:
                    QMessageBox.warning(self, "Uyarı", "Tutar 0'dan büyük olmalıdır!")
                    return

                data = {
                    'title': title,
                    'plan_type': plan_type,
                    'payee_name': payee_name,
                    'branch_id': branch_id,
                    'payment_method': payment_method,
                    'account_id': account_id,
                    'reminder_days': reminder_days,
                    'notes': notes,
                    'amount': amount_val,
                    'total_amount': amount_val,
                    'due_date': due_date_str,
                }
                success, msg = payment_plan_service.update_plan(first_id, data)
                if not success:
                    QMessageBox.warning(self, "Hata", msg)
                    return
            else:
                # Taksitli plan serisi güncellemesi
                plan_ids = [x['id'] for x in self.items]
                common_data = {
                    'title': title,
                    'plan_type': plan_type,
                    'payee_name': payee_name,
                    'branch_id': branch_id,
                    'payment_method': payment_method,
                    'account_id': account_id,
                    'reminder_days': reminder_days,
                    'notes': notes,
                }
                # Ortak alanları güncelle
                payment_plan_service.update_plan_series(plan_ids, common_data)

                # Tablodan her bir ödenmemiş taksitin vade tarihi ve tutarını güncelle
                new_total = 0.0
                for row_idx, ed_info in getattr(self, 'table_editors', {}).items():
                    inst_id = ed_info['item_id']
                    if ed_info['status'] != 'odendi':
                        d_edit = ed_info['date_edit']
                        sp = ed_info['amount_spin']
                        if d_edit and sp:
                            new_date = d_edit.date().toString("yyyy-MM-dd")
                            new_amt = sp.value()
                            new_total += new_amt
                            payment_plan_service.update_plan(inst_id, {
                                'due_date': new_date,
                                'amount': new_amt,
                                'payment_method': payment_method,
                                'branch_id': branch_id,
                                'account_id': account_id,
                            })
                    else:
                        # Ödenmiş taksit tutarını ekle
                        paid_plan = payment_plan_service.get_plan(inst_id)
                        if paid_plan:
                            new_total += float(paid_plan.get('amount') or 0)

                # Toplam tutarı güncelle
                if new_total > 0:
                    for pid in plan_ids:
                        db.execute_query(
                            "UPDATE PaymentPlans SET total_amount = %s WHERE id = %s",
                            (new_total, pid)
                        )

            QMessageBox.information(self, "Başarılı", "Ödeme planı ve taksit bilgileri başarıyla güncellendi.")
            self.accept()
        except Exception as e:
            logger.error(f"save_changes hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Değişiklikler kaydedilemedi: {str(e)}")

    def _mini_btn_style(self, color: str, text_color: str = "white") -> str:
        return f"""
            QPushButton {{
                background-color: {color}25;
                color: {color};
                border: 1px solid {color}50;
                border-radius: 6px;
                font-size: 11pt;
                padding: 0px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: {text_color};
            }}
        """

    def _input_style(self) -> str:
        return f"""
            background-color: {AppStyles.BG_DARK};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 6px;
            padding: 5px 8px;
            font-size: 9.5pt;
        """

    def _table_input_style(self) -> str:
        return f"""
            QDateEdit, QDoubleSpinBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 2px 6px;
                font-size: 9.5pt;
                font-weight: 500;
            }}
            QDateEdit:focus, QDoubleSpinBox:focus {{
                border-color: {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_DARKEST};
            }}
        """

    def _table_style(self) -> str:
        return f"""
            QTableWidget {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                gridline-color: {AppStyles.BORDER}50;
                color: {AppStyles.TEXT_PRIMARY};
                font-size: 9.5pt;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
                border-bottom: 1px solid {AppStyles.BORDER}30;
            }}
            QTableWidget::item:selected {{
                background-color: {AppStyles.PRIMARY}25;
                color: white;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARKEST};
                color: {AppStyles.TEXT_SECONDARY};
                padding: 8px 10px;
                border: none;
                border-bottom: 2px solid {AppStyles.BORDER};
                font-size: 9.5pt;
                font-weight: bold;
            }}
            QScrollBar:vertical {{
                background: {AppStyles.BG_DARK};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {AppStyles.BORDER};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {AppStyles.TEXT_MUTED};
            }}
        """


# ==================== ANA SAYFA ====================

class PaymentPlansPage(QWidget):
    """Ödeme Planları, Personel ve Avans Yönetim Sayfası"""

    def __init__(self, user: User, branch_id: int = None, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window

        # Gecikmiş planları güncelle
        try:
            payment_plan_service.refresh_overdue_status()
        except Exception as e:
            logger.warning(f"refresh_overdue_status hatası: {e}")

        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setObjectName("PaymentPlansPage")
        self.setStyleSheet(f"#PaymentPlansPage {{ background-color: {AppStyles.BG_DARK}; }}")

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        content = QWidget()
        content.setStyleSheet(f"background-color: {AppStyles.BG_DARK};")

        self.layout = QVBoxLayout()
        self.layout.setSpacing(18)
        self.layout.setContentsMargins(25, 20, 25, 20)

        # Üst bar
        top_bar = self.create_top_bar()
        self.layout.addWidget(top_bar)

        # KPI kartları
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(12)
        self.layout.addLayout(self.stats_layout)

        # Sekmeli alan
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(self._tab_style())
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Tab 1: Ödeme Planları
        self.tab_plans = self.create_plans_tab()
        self.tabs.addTab(self.tab_plans, "📅 Ödeme Planları")

        # Tab 2: Personel
        self.tab_employees = self.create_employees_tab()
        self.tabs.addTab(self.tab_employees, "👥 Personel")

        # Tab 3: Avanslar
        self.tab_advances = self.create_advances_tab()
        self.tabs.addTab(self.tab_advances, "💵 Avanslar")

        self.layout.addWidget(self.tabs)

        content.setLayout(self.layout)
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    # ==================== ÜST BAR ====================

    def create_top_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        left = QVBoxLayout()
        left.setSpacing(3)
        title = QLabel("💰 Ödeme Planları & Personel")
        title.setStyleSheet(f"font-size: 20pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)

        subtitle_text = "Personel maaşları, avanslar, şube kiraları, taksitler ve diğer ödemeler"
        if self.branch_id:
            try:
                b = Branch.get_by_id(self.branch_id)
                if b:
                    subtitle_text = f"{b.name} • Personel maaşları, avanslar, taksitler ve gider ödemeleri"
            except Exception:
                pass
        subtitle = QLabel(subtitle_text)
        subtitle.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        layout.addLayout(left)
        layout.addStretch()

        # Yenile butonu
        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_SECONDARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                color: {AppStyles.TEXT_PRIMARY};
                border-color: {AppStyles.PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """)
        layout.addWidget(refresh_btn)

        bar.setLayout(layout)
        return bar

    # ==================== KPI ====================

    def update_stats_cards(self):
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        stats = payment_plan_service.get_plan_stats(
            branch_id=self.branch_id if self.branch_id else None
        )

        cards = [
            ("📅", "Bu Ay Ödenecek", f"{stats['month_pending_total']:,.0f} ₺",
            AppStyles.PRIMARY, f"{stats['month_pending_count']} ödeme"),
            ("⏰", "Yaklaşan (7 Gün)", f"{stats['upcoming_total']:,.0f} ₺",
            AppStyles.ORANGE, f"{stats['upcoming_count']} ödeme"),
            ("🔴", "Gecikmiş", f"{stats['overdue_total']:,.0f} ₺",
            AppStyles.RED if stats['overdue_count'] > 0 else AppStyles.GREEN,
            f"{stats['overdue_count']} ödeme"),
            ("✅", "Bu Ay Ödenen", f"{stats['paid_this_month_total']:,.0f} ₺",
            AppStyles.GREEN, f"{stats['paid_this_month_count']} ödeme"),
            ("💰", "Bekleyen Toplam", f"{stats['waiting_total']:,.0f} ₺",
            AppStyles.CYAN, f"{stats['waiting_count']} plan"),
        ]

        for icon, title, val, color, sub in cards:
            card = self.create_kpi_card(icon, title, val, color, sub)
            self.stats_layout.addWidget(card)

    def create_kpi_card(self, icon: str, title: str, val: str, color: str, sub: str) -> QFrame:
        card = QFrame()
        card.setMinimumHeight(100)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                border-left: 4px solid {color};
                border-top: 1px solid {AppStyles.BORDER};
                border-right: 1px solid {AppStyles.BORDER};
                border-bottom: 1px solid {AppStyles.BORDER};
                padding: 12px 16px;
            }}
            QFrame QLabel {{ background: transparent; border: none; }}
        """)
        lay = QVBoxLayout()
        lay.setSpacing(3)

        top = QHBoxLayout()
        t_lbl = QLabel(f"{icon} {title}")
        t_lbl.setStyleSheet(f"font-size: 9.5pt; font-weight: bold; color: {AppStyles.TEXT_SECONDARY};")
        top.addWidget(t_lbl)
        top.addStretch()
        lay.addLayout(top)

        val_lbl = QLabel(val)
        val_lbl.setStyleSheet(f"font-size: 15pt; font-weight: bold; color: {color};")
        lay.addWidget(val_lbl)

        sub_lbl = QLabel(sub)
        sub_lbl.setStyleSheet(f"font-size: 8pt; color: {AppStyles.TEXT_MUTED};")
        lay.addWidget(sub_lbl)

        card.setLayout(lay)
        return card

    # ==================== TAB 1: ÖDEME PLANLARI ====================

    def create_plans_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Filtre çubuğu
        f_row = QHBoxLayout()
        f_row.setSpacing(10)

        self.plan_search = QLineEdit()
        self.plan_search.setPlaceholderText("🔍 Başlık, muhatap ara...")
        self.plan_search.setMinimumHeight(38)
        self.plan_search.textChanged.connect(self.load_plans)
        self.plan_search.setStyleSheet(self._input_style())
        f_row.addWidget(self.plan_search, 3)

        self.plan_type_filter = QComboBox()
        self.plan_type_filter.addItem("Tüm Tipler", "Tümü")
        for key, val in PLAN_TYPES.items():
            self.plan_type_filter.addItem(val, key)
        self.plan_type_filter.setMinimumHeight(38)
        self.plan_type_filter.currentIndexChanged.connect(self.load_plans)
        self.plan_type_filter.setStyleSheet(self._input_style())
        f_row.addWidget(self.plan_type_filter, 2)

        self.plan_status_filter = QComboBox()
        self.plan_status_filter.addItem("Tüm Durumlar", "Tümü")
        for key, val in STATUS.items():
            self.plan_status_filter.addItem(val, key)
        self.plan_status_filter.setMinimumHeight(38)
        self.plan_status_filter.currentIndexChanged.connect(self.load_plans)
        self.plan_status_filter.setStyleSheet(self._input_style())
        f_row.addWidget(self.plan_status_filter, 2)

        self.crit_filter_btn = QPushButton("⚠️ Yaklaşan/Gecikmiş")
        self.crit_filter_btn.setCheckable(True)
        self.crit_filter_btn.setCursor(Qt.PointingHandCursor)
        self.crit_filter_btn.setMinimumHeight(38)
        self.crit_filter_btn.toggled.connect(self.load_plans)
        self.crit_filter_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 0 14px;
                font-weight: 600;
            }}
            QPushButton:checked {{
                background-color: {AppStyles.RED}25;
                color: {AppStyles.RED};
                border-color: {AppStyles.RED};
            }}
        """)
        f_row.addWidget(self.crit_filter_btn)

        refresh_btn = QPushButton("🔄")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setFixedSize(38, 38)
        refresh_btn.setStyleSheet(self._btn_style(AppStyles.BG_DARK))
        f_row.addWidget(refresh_btn)

        # Tab 1 Butonları
        new_plan_btn = QPushButton("➕ Yeni Ödeme Planı")
        new_plan_btn.setCursor(Qt.PointingHandCursor)
        new_plan_btn.clicked.connect(self.open_new_plan)
        new_plan_btn.setStyleSheet(self._btn_style(AppStyles.GREEN))
        f_row.addWidget(new_plan_btn)

        salary_btn = QPushButton("📅 Maaş Planı")
        salary_btn.setCursor(Qt.PointingHandCursor)
        salary_btn.clicked.connect(self.open_create_salary)
        salary_btn.setStyleSheet(self._btn_style(AppStyles.PRIMARY))
        f_row.addWidget(salary_btn)

        layout.addLayout(f_row)

        # Tablo
        self.plans_table = QTableWidget()
        self.plans_table.setColumnCount(11)
        self.plans_table.setHorizontalHeaderLabels([
            'Vade', 'Tip', 'Başlık', 'Muhatap',
            'Toplam Tutar', 'Taksit Tutarı', 'Kalan Taksit Tutarı',
            'Ödeme Yöntemi', 'Durum', 'Şube', 'İşlemler'
        ])
        self.plans_table.setAlternatingRowColors(True)
        self.plans_table.verticalHeader().setVisible(False)
        self.plans_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        header = self.plans_table.horizontalHeader()
        header.setHighlightSections(False)
        header.setMinimumSectionSize(85)
        # Sütun bazlı esneklik: Başlık genişler, işlemler sabittir, diğerleri içeriğe göre ayarlanır
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Stretch)   # Başlık sütunu esnek
        header.setSectionResizeMode(10, QHeaderView.Fixed)    # İşlemler sütunu sabit
        self.plans_table.setColumnWidth(10, 110)
        self.plans_table.setColumnWidth(6, 175)  # Kalan Taksit Tutarı
        self.plans_table.setColumnWidth(7, 155)  # Ödeme Yöntemi
        # ✅ Satır yüksekliği
        self.plans_table.verticalHeader().setDefaultSectionSize(44)

        self.plans_table.setStyleSheet(self._table_style())
        layout.addWidget(self.plans_table)

        w.setLayout(layout)
        return w

    def load_plans(self):
        import re
        search = self.plan_search.text().strip()
        plan_type = self.plan_type_filter.currentData()
        status = self.plan_status_filter.currentData()
        crit_only = self.crit_filter_btn.isChecked()

        plans = payment_plan_service.get_plans(
            plan_type=plan_type,
            status=status,
            branch_id=self.branch_id if self.branch_id else None,
            search=search
        )

        if crit_only:
            today = datetime.now().date()
            plans = [p for p in plans if p['status'] in ('gecikti',) or
                    (p['status'] == 'bekliyor' and self._parse_date(p['due_date']) and
                    (self._parse_date(p['due_date']) - today).days <= 7)]

        # Taksitli planları tek satırda birleştirme (her taksiti ayrı satır eklemek yerine gruplayarak özetleme)
        grouped_records = []
        installment_groups = {}  # group_key -> list of items

        for p in plans:
            inst_count = int(p.get('installment_count') or 1)
            if inst_count > 1:
                # Başlıktaki (1/4) benzeri taksit ekini temizleyerek kök başlığı bul
                raw_title = p.get('title', '')
                base_title = re.sub(r'\s*\(\d+/\d+\)$', '', raw_title).strip()
                group_key = (
                    p.get('branch_id'),
                    p.get('plan_type'),
                    p.get('payee_name'),
                    inst_count,
                    base_title
                )
                if group_key not in installment_groups:
                    installment_groups[group_key] = []
                installment_groups[group_key].append(p)
            else:
                amt = float(p.get('amount') or 0)
                tot = float(p.get('total_amount') or amt or 0)
                is_paid = (p.get('status') == 'odendi')
                grouped_records.append({
                    'item': p,
                    'is_installment': False,
                    'title': p.get('title', '-'),
                    'total_amount': tot if tot > 0 else amt,
                    'installment_amount': amt,
                    'remaining_amount': 0.0 if is_paid else amt,
                    'remaining_count': 0 if is_paid else 1,
                    'installment_count': 1,
                    'installment_no': 1,
                    'status_key': p.get('status', 'bekliyor'),
                    'status_label': STATUS.get(p.get('status', 'bekliyor'), p.get('status', 'bekliyor')),
                    'due_date': str(p.get('due_date') or ''),
                    'group_items': [p]
                })

        for group_key, items in installment_groups.items():
            # Taksitleri installment_no veya due_date'e göre sırala
            items.sort(key=lambda x: (int(x.get('installment_no') or 0), str(x.get('due_date') or '')))

            inst_count = int(items[0].get('installment_count') or len(items))
            inst_amt = float(items[0].get('amount') or 0)
            tot_amt = float(items[0].get('total_amount') or 0)
            if tot_amt <= 0:
                tot_amt = sum(float(x.get('amount') or 0) for x in items)

            unpaid = [x for x in items if x.get('status') != 'odendi']
            rem_amt = sum(float(x.get('amount') or 0) for x in unpaid)
            rem_cnt = len(unpaid)

            base_title = group_key[4]

            if unpaid:
                # Sıradaki ilk ödenmemiş taksit aktif temsilcidir
                active = unpaid[0]
                curr_no = int(active.get('installment_no') or (inst_count - rem_cnt + 1))
                display_title = f"{base_title} (Sıradaki: {curr_no}/{inst_count})"
                st_key = active.get('status', 'bekliyor')
                st_lbl = STATUS.get(st_key, st_key)
                d_date = str(active.get('due_date') or '')
            else:
                # Tüm taksitler ödendi
                active = items[-1]
                display_title = f"{base_title} ({inst_count}/{inst_count} - Tamamı Ödendi)"
                st_key = 'odendi'
                st_lbl = "Ödendi"
                d_date = str(active.get('due_date') or active.get('paid_date') or '')

            grouped_records.append({
                'item': active,
                'is_installment': True,
                'title': display_title,
                'total_amount': tot_amt,
                'installment_amount': inst_amt,
                'remaining_amount': rem_amt,
                'remaining_count': rem_cnt,
                'installment_count': inst_count,
                'installment_no': int(active.get('installment_no') or 1),
                'status_key': st_key,
                'status_label': st_lbl,
                'due_date': d_date,
                'group_items': items
            })

        # Tarihe göre sırala
        grouped_records.sort(key=lambda x: x['due_date'])

        self.plans_table.setRowCount(len(grouped_records))

        for row_idx, rec in enumerate(grouped_records):
            p = rec['item']
            p_id = p['id']
            due_date = rec['due_date']
            plan_type_key = p.get('plan_type', 'diger')
            plan_type_label = PLAN_TYPES.get(plan_type_key, plan_type_key)
            title = rec['title']
            payee = p.get('payee_name', '-') or '-'
            total_amt = rec['total_amount']
            inst_amt = rec['installment_amount']
            rem_amt = rec['remaining_amount']
            rem_cnt = rec['remaining_count']
            inst_cnt = rec['installment_count']
            method = p.get('payment_method', '-')
            status_key = rec['status_key']
            status_label = rec['status_label']
            branch_name = p.get('branch_name', '') or 'Genel'

            # 0. Vade
            due_item = QTableWidgetItem(due_date)
            due_item.setTextAlignment(Qt.AlignCenter)
            if status_key == 'gecikti':
                due_item.setForeground(QColor(AppStyles.RED))
            elif status_key == 'bekliyor':
                days_left = 999
                try:
                    d = datetime.strptime(due_date, '%Y-%m-%d').date()
                    days_left = (d - datetime.now().date()).days
                except Exception:
                    pass
                if days_left < 0:
                    due_item.setForeground(QColor(AppStyles.RED))
                elif days_left <= 3:
                    due_item.setForeground(QColor(AppStyles.ORANGE))
                else:
                    due_item.setForeground(QColor(AppStyles.TEXT_PRIMARY))
            self.plans_table.setItem(row_idx, 0, due_item)

            # 1. Tip
            type_item = QTableWidgetItem(plan_type_label)
            type_item.setTextAlignment(Qt.AlignCenter)
            type_colors = {
                'personel': AppStyles.PRIMARY,
                'kira': AppStyles.PURPLE,
                'taksit': AppStyles.CYAN,
                'diger': AppStyles.TEXT_SECONDARY,
            }
            type_item.setForeground(QColor(type_colors.get(plan_type_key, AppStyles.TEXT_SECONDARY)))
            type_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.plans_table.setItem(row_idx, 1, type_item)

            # 2. Başlık
            t_item = QTableWidgetItem(title)
            t_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.plans_table.setItem(row_idx, 2, t_item)

            # 3. Muhatap
            self.plans_table.setItem(row_idx, 3, QTableWidgetItem(payee))

            # 4. Toplam Tutar
            tot_item = QTableWidgetItem(f"{total_amt:,.2f} ₺")
            tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tot_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            tot_item.setForeground(QColor(AppStyles.TEXT_PRIMARY))
            self.plans_table.setItem(row_idx, 4, tot_item)

            # 5. Taksit Tutarı
            inst_item = QTableWidgetItem(f"{inst_amt:,.2f} ₺")
            inst_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            inst_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            inst_item.setForeground(QColor(AppStyles.CYAN if inst_cnt > 1 else AppStyles.TEXT_PRIMARY))
            if inst_cnt > 1:
                inst_item.setToolTip(f"Aylık Taksit Tutarı: {inst_amt:,.2f} ₺\nToplam Taksit: {inst_cnt}")
            self.plans_table.setItem(row_idx, 5, inst_item)

            # 6. Kalan Taksit Tutarı
            rem_item = QTableWidgetItem(f"{rem_amt:,.2f} ₺" if rem_amt > 0 else "0,00 ₺ (Bitti)")
            rem_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            rem_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            if rem_amt <= 0:
                rem_item.setForeground(QColor(AppStyles.GREEN))
            elif status_key == 'gecikti':
                rem_item.setForeground(QColor(AppStyles.RED))
            else:
                rem_item.setForeground(QColor(AppStyles.ORANGE))
            if inst_cnt > 1:
                rem_item.setToolTip(f"Kalan: {rem_cnt}/{inst_cnt} taksit ({rem_amt:,.2f} ₺)")
            self.plans_table.setItem(row_idx, 6, rem_item)

            # 7. Ödeme Yöntemi
            self.plans_table.setItem(row_idx, 7, QTableWidgetItem(method))

            # 8. Durum
            status_item = QTableWidgetItem(status_label)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            status_colors = {
                'bekliyor': AppStyles.ORANGE,
                'odendi': AppStyles.GREEN,
                'gecikti': AppStyles.RED,
                'iptal': AppStyles.TEXT_MUTED,
            }
            status_item.setForeground(QColor(status_colors.get(status_key, AppStyles.TEXT_SECONDARY)))
            self.plans_table.setItem(row_idx, 8, status_item)

            # 9. Şube
            self.plans_table.setItem(row_idx, 9, QTableWidgetItem(branch_name))

            # 10. İşlemler
            action_widget = QWidget()
            a_lay = QHBoxLayout()
            a_lay.setContentsMargins(2, 2, 2, 2)
            a_lay.setSpacing(6)
            a_lay.setAlignment(Qt.AlignCenter)

            if status_key in ('bekliyor', 'gecikti') and rem_amt > 0:
                pay_btn = QPushButton("💰")
                pay_btn.setToolTip("Sıradaki Taksiti Öde" if inst_cnt > 1 else "Ödeme Yap")
                pay_btn.setFixedSize(35, 32)
                pay_btn.setStyleSheet(self._mini_btn_style(AppStyles.GREEN))
                pay_btn.clicked.connect(lambda checked, pid=p_id: self.open_mark_paid(pid))
                a_lay.addWidget(pay_btn)

            # Sil butonu yerine Detay & Düzenleme butonu (Detay penceresinde silme ve düzenleme mevcuttur)
            edit_btn = QPushButton("✏️")
            edit_btn.setToolTip("Planı İncele, Düzenle veya Sil")
            edit_btn.setFixedSize(35, 32)
            edit_btn.setStyleSheet(self._mini_btn_style(AppStyles.ORANGE))
            edit_btn.clicked.connect(lambda checked, record=rec: self.open_plan_detail(record))
            a_lay.addWidget(edit_btn)

            action_widget.setLayout(a_lay)
            self.plans_table.setCellWidget(row_idx, 10, action_widget)

        # Sütun içeriklerinin ve başlıklarının tam sığması için genişlik ayarları:
        for col_idx in (0, 1, 3, 4, 5, 6, 7, 8, 9):
            self.plans_table.resizeColumnToContents(col_idx)

        # "Kalan Taksit Tutarı" ve "Ödeme Yöntemi" başlık ve değerlerinin kutucuklara rahatça sığması için garantili genişlikler:
        if self.plans_table.columnWidth(6) < 175:
            self.plans_table.setColumnWidth(6, 175)
        if self.plans_table.columnWidth(7) < 155:
            self.plans_table.setColumnWidth(7, 155)
        if self.plans_table.columnWidth(0) < 100:
            self.plans_table.setColumnWidth(0, 100)
        if self.plans_table.columnWidth(1) < 115:
            self.plans_table.setColumnWidth(1, 115)
        if self.plans_table.columnWidth(4) < 130:
            self.plans_table.setColumnWidth(4, 130)
        if self.plans_table.columnWidth(5) < 130:
            self.plans_table.setColumnWidth(5, 130)
        if self.plans_table.columnWidth(8) < 100:
            self.plans_table.setColumnWidth(8, 100)
        if self.plans_table.columnWidth(9) < 110:
            self.plans_table.setColumnWidth(9, 110)

    def _parse_date(self, val):
        try:
            return datetime.strptime(str(val), '%Y-%m-%d').date()
        except Exception:
            return None

    # ==================== TAB 2: PERSONEL ====================

    def create_employees_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(12)

        f_row = QHBoxLayout()
        f_row.setSpacing(10)

        self.emp_search = QLineEdit()
        self.emp_search.setPlaceholderText("🔍 Ad, kod, telefon ara...")
        self.emp_search.setMinimumHeight(38)
        self.emp_search.textChanged.connect(self.load_employees)
        self.emp_search.setStyleSheet(self._input_style())
        f_row.addWidget(self.emp_search, 3)

        self.emp_active_filter = QComboBox()
        self.emp_active_filter.addItem("Aktif Personel", True)
        self.emp_active_filter.addItem("Tümü (Aktif + Pasif)", False)
        self.emp_active_filter.setMinimumHeight(38)
        self.emp_active_filter.currentIndexChanged.connect(self.load_employees)
        self.emp_active_filter.setStyleSheet(self._input_style())
        f_row.addWidget(self.emp_active_filter, 2)

        refresh_btn = QPushButton("🔄")
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setFixedSize(38, 38)
        refresh_btn.setStyleSheet(self._btn_style(AppStyles.BG_DARK))
        f_row.addWidget(refresh_btn)

        # Tab 2 Butonu
        employee_btn = QPushButton("👥 Yeni Personel Ekle")
        employee_btn.setCursor(Qt.PointingHandCursor)
        employee_btn.clicked.connect(self.open_add_employee)
        employee_btn.setStyleSheet(self._btn_style(AppStyles.CYAN, text_color="#000"))
        f_row.addWidget(employee_btn)

        layout.addLayout(f_row)

        self.emp_table = QTableWidget()
        self.emp_table.setColumnCount(9)
        self.emp_table.setHorizontalHeaderLabels([
            'Kod', 'Ad Soyad', 'Pozisyon', 'Departman', 'Şube', 'Telefon',
            'Aylık Maaş', 'Açık Avans', 'İşlemler'
        ])
        self.emp_table.setAlternatingRowColors(True)
        self.emp_table.verticalHeader().setVisible(False)

        header = self.emp_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        # ✅ İşlemler sütunu — 4 buton var, geniş olmalı
        header.setSectionResizeMode(8, QHeaderView.Fixed)
        self.emp_table.setColumnWidth(8, 175)
        # ✅ Satır yüksekliği
        self.emp_table.verticalHeader().setDefaultSectionSize(46)

        self.emp_table.setStyleSheet(self._table_style())
        layout.addWidget(self.emp_table)

        w.setLayout(layout)
        return w

    def load_employees(self):
        search = self.emp_search.text().strip()
        active_only = self.emp_active_filter.currentData()

        employees = employee_service.get_employees(
            search=search,
            branch_id=self.branch_id if self.branch_id else None,
            active_only=active_only
        )

        self.emp_table.setRowCount(len(employees))

        for row_idx, e in enumerate(employees):
            emp_id = e['id']
            code = e.get('employee_code', '-')
            full_name = e.get('full_name', '-')
            position = e.get('position', '-') or '-'
            department = e.get('department', '-') or '-'
            branch_name = e.get('branch_name', '-') or '-'
            phone = e.get('phone', '-') or '-'
            salary = float(e.get('monthly_salary') or 0)

            # Açık avans
            try:
                open_adv = payment_plan_service.get_total_open_advance(emp_id)
            except Exception:
                open_adv = 0.0

            self.emp_table.setItem(row_idx, 0, QTableWidgetItem(code))

            name_item = QTableWidgetItem(full_name)
            name_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            if not e.get('is_active', True):
                name_item.setForeground(QColor(AppStyles.TEXT_MUTED))
            self.emp_table.setItem(row_idx, 1, name_item)

            self.emp_table.setItem(row_idx, 2, QTableWidgetItem(position))
            self.emp_table.setItem(row_idx, 3, QTableWidgetItem(department))
            self.emp_table.setItem(row_idx, 4, QTableWidgetItem(branch_name))
            self.emp_table.setItem(row_idx, 5, QTableWidgetItem(phone))

            sal_item = QTableWidgetItem(f"{salary:,.2f} ₺")
            sal_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.emp_table.setItem(row_idx, 6, sal_item)

            adv_item = QTableWidgetItem(f"{open_adv:,.2f} ₺")
            adv_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if open_adv > 0:
                adv_item.setForeground(QColor(AppStyles.ORANGE))
                adv_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            else:
                adv_item.setForeground(QColor(AppStyles.TEXT_MUTED))
            self.emp_table.setItem(row_idx, 7, adv_item)

            # İşlemler
            action_widget = QWidget()
            a_lay = QHBoxLayout()
            a_lay.setContentsMargins(2, 2, 2, 2)
            a_lay.setSpacing(4)
            a_lay.setAlignment(Qt.AlignCenter)

            adv_btn = QPushButton("💵")
            adv_btn.setToolTip("Avans Ver")
            adv_btn.setFixedSize(34, 30)
            adv_btn.setStyleSheet(self._mini_btn_style(AppStyles.CYAN))
            adv_btn.clicked.connect(lambda checked, eid=emp_id: self.open_give_advance(eid))
            a_lay.addWidget(adv_btn)

            sal_btn = QPushButton("📅")
            sal_btn.setToolTip("Maaş Planı Oluştur")
            sal_btn.setFixedSize(34, 30)
            sal_btn.setStyleSheet(self._mini_btn_style(AppStyles.GREEN))
            sal_btn.clicked.connect(lambda checked, eid=emp_id: self.open_create_salary(eid))
            a_lay.addWidget(sal_btn)

            edit_btn = QPushButton("✏️")
            edit_btn.setToolTip("Düzenle")
            edit_btn.setFixedSize(34, 30)
            edit_btn.setStyleSheet(self._mini_btn_style(AppStyles.ORANGE))
            edit_btn.clicked.connect(lambda checked, eid=emp_id: self.open_edit_employee(eid))
            a_lay.addWidget(edit_btn)

            del_btn = QPushButton("🗑️")
            del_btn.setToolTip("Sil (Pasife Al)")
            del_btn.setFixedSize(34, 30)
            del_btn.setStyleSheet(self._mini_btn_style(AppStyles.RED))
            del_btn.clicked.connect(lambda checked, eid=emp_id: self.delete_employee(eid))
            a_lay.addWidget(del_btn)

            action_widget.setLayout(a_lay)
            self.emp_table.setCellWidget(row_idx, 8, action_widget)

    # ==================== TAB 3: AVANSLAR ====================

    def create_advances_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(12)

        top_bar = QHBoxLayout()
        info = QLabel("💡 Açık (kapatılmamış) personel avansları. "
                    "Avanslar maaş ödemesi yapılırken otomatik olarak mahsup edilir.")
        info.setStyleSheet(f"color: {AppStyles.CYAN}; font-size: 9.5pt; padding: 8px 12px; background-color: {AppStyles.BG_MEDIUM}; border-radius: 8px;")
        info.setWordWrap(True)
        top_bar.addWidget(info, 1)

        advance_btn = QPushButton("💵 Personel Avansı Ver")
        advance_btn.setCursor(Qt.PointingHandCursor)
        advance_btn.clicked.connect(self.open_give_advance)
        advance_btn.setStyleSheet(self._btn_style(AppStyles.ORANGE))
        top_bar.addWidget(advance_btn)
        layout.addLayout(top_bar)

        self.advances_table = QTableWidget()
        self.advances_table.setColumnCount(8)
        self.advances_table.setHorizontalHeaderLabels([
            'Tarih', 'Personel', 'Açıklama', 'Avans Tutarı', 'Kalan Tutar',
            'Kesinti Şekli', 'Durum', 'İşlemler'
        ])
        self.advances_table.setAlternatingRowColors(True)
        self.advances_table.verticalHeader().setVisible(False)

        header = self.advances_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        # ✅ İşlemler sütunu
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        self.advances_table.setColumnWidth(7, 95)
        # ✅ Satır yüksekliği
        self.advances_table.verticalHeader().setDefaultSectionSize(46)

        self.advances_table.setStyleSheet(self._table_style())
        layout.addWidget(self.advances_table)

        w.setLayout(layout)
        return w

    def load_advances(self):
        """Tüm açık avansları listeler"""
        try:
            # Açık avansları olan tüm personeli ve avanslarını çek
            sql = """
                SELECT 
                    el.id,
                    el.employee_id,
                    el.amount,
                    el.entry_date,
                    el.description,
                    el.remaining_amount,
                    el.is_closed,
                    e.full_name AS employee_name,
                    e.employee_code
                FROM EmployeeLedger el
                JOIN Employees e ON e.id = el.employee_id
                WHERE el.entry_type = 'avans' AND el.is_closed = 0
            """
            params = []
            if self.branch_id:
                sql += " AND e.branch_id = %s"
                params.append(self.branch_id)
            sql += " ORDER BY el.entry_date ASC, el.id ASC"
            advances = db.fetch_all(sql, tuple(params)) if params else db.fetch_all(sql)

            self.advances_table.setRowCount(len(advances))

            for row_idx, a in enumerate(advances):
                adv_id = a['id']
                entry_date = str(a.get('entry_date') or '')
                emp_name = a.get('employee_name', '-')
                emp_code = a.get('employee_code', '')
                description = a.get('description', '') or '-'
                amount = float(a.get('amount') or 0)
                remaining = float(a.get('remaining_amount') or 0)

                self.advances_table.setItem(row_idx, 0, QTableWidgetItem(entry_date))

                name_item = QTableWidgetItem(f"{emp_code} - {emp_name}".strip(' -'))
                name_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                self.advances_table.setItem(row_idx, 1, name_item)

                self.advances_table.setItem(row_idx, 2, QTableWidgetItem(description))

                amt_item = QTableWidgetItem(f"{amount:,.2f} ₺")
                amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.advances_table.setItem(row_idx, 3, amt_item)

                rem_item = QTableWidgetItem(f"{remaining:,.2f} ₺")
                rem_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                rem_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                rem_item.setForeground(QColor(AppStyles.ORANGE))
                self.advances_table.setItem(row_idx, 4, rem_item)

                # Kesinti şekli (açıklamadan anlamaya çalış)
                mode_text = "Taksitli" if "taksitli" in description.lower() else "Tam"
                self.advances_table.setItem(row_idx, 5, QTableWidgetItem(mode_text))

                status_item = QTableWidgetItem("🟠 Açık")
                status_item.setForeground(QColor(AppStyles.ORANGE))
                status_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                status_item.setTextAlignment(Qt.AlignCenter)
                self.advances_table.setItem(row_idx, 6, status_item)

                action_widget = QWidget()
                a_lay = QHBoxLayout()
                a_lay.setContentsMargins(2, 2, 2, 2)
                a_lay.setSpacing(4)
                a_lay.setAlignment(Qt.AlignCenter)

                close_btn = QPushButton("✅ Kapat")
                close_btn.setToolTip("Avansı Manuel Kapat (Tahsil Et)")
                close_btn.setFixedSize(74, 30)
                close_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #10b981;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 4px 6px;
                        font-size: 8.5pt;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #059669;
                    }
                """)
                close_btn.clicked.connect(lambda checked, aid=adv_id: self.manual_close_advance(aid))
                a_lay.addWidget(close_btn)

                action_widget.setLayout(a_lay)
                self.advances_table.setCellWidget(row_idx, 7, action_widget)

        except Exception as e:
            logger.error(f"load_advances hatası: {e}")

    # ==================== DİALOG AÇMA ====================

    def open_new_plan(self):
        dlg = NewPaymentPlanDialog(self.user, self.branch_id, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_plan_detail(self, record: dict):
        dlg = PaymentPlanDetailDialog(record, self.user, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_mark_paid(self, plan_id: int):
        plan = payment_plan_service.get_plan(plan_id)
        if not plan:
            QMessageBox.warning(self, "Uyarı", "Plan bulunamadı!")
            return
        dlg = MarkPaidDialog(plan, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_add_employee(self):
        dlg = NewEmployeeDialog(self.branch_id, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_edit_employee(self, employee_id: int):
        dlg = NewEmployeeDialog(self.branch_id, employee_id=employee_id, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_give_advance(self, employee_id: int = None):
        dlg = GiveAdvanceDialog(employee_id, self.branch_id, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_create_salary(self, employee_id: int = None):
        dlg = CreateSalaryPlanDialog(employee_id, self.branch_id, self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    # ==================== SİLME / İŞLEM ====================

    def delete_plan(self, plan_id: int):
        reply = QMessageBox.question(
            self, "Silme Onayı",
            "Bu ödeme planını silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = payment_plan_service.delete_plan(plan_id)
            if success:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_data()
            else:
                QMessageBox.warning(self, "Hata", msg)

    def delete_employee(self, employee_id: int):
        reply = QMessageBox.question(
            self, "Silme Onayı",
            "Bu personeli silmek (pasife almak) istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = employee_service.delete_employee(employee_id)
            if success:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_data()
            else:
                QMessageBox.warning(self, "Hata", msg)

    def manual_close_advance(self, advance_ledger_id: int):
        """Avansı manuel kapat (nakit tahsil edildi vs.)"""
        reply = QMessageBox.question(
            self, "Avansı Kapat",
            "Bu avansı manuel olarak kapatmak (tamamen kesilmiş saymak) istiyor musunuz?\n"
            "Bu işlem geri alınamaz.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            with db.transaction():
                # Kalan tutarı bul
                row = db.fetch_one(
                    "SELECT remaining_amount FROM EmployeeLedger WHERE id = %s",
                    (advance_ledger_id,)
                )
                if not row:
                    QMessageBox.warning(self, "Hata", "Avans kaydı bulunamadı!")
                    return
                remaining = float(row['remaining_amount'] or 0)

                # Avansı kapat
                db.execute_query("""
                    UPDATE EmployeeLedger 
                    SET remaining_amount = 0, is_closed = 1
                    WHERE id = %s
                """, (advance_ledger_id,))

                # Mahsup hareketi
                adv = db.fetch_one(
                    "SELECT employee_id FROM EmployeeLedger WHERE id = %s",
                    (advance_ledger_id,)
                )
                if adv and remaining > 0:
                    db.execute_query("""
                        INSERT INTO EmployeeLedger (
                            employee_id, entry_type, amount, entry_date, description,
                            remaining_amount, is_closed, created_by
                        ) VALUES (%s, 'mahsup', %s, CURRENT_DATE, %s, 0, 1, %s)
                    """, (
                        adv['employee_id'],
                        remaining,
                        f"Manuel kapatma (Ledger #{advance_ledger_id})",
                        getattr(self.user, 'id', None)
                    ))

            QMessageBox.information(self, "Başarılı", f"Avans kapatıldı ({remaining:,.2f} ₺).")
            self.load_data()
        except Exception as e:
            logger.error(f"manual_close_advance hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Avans kapatılamadı: {e}")

    # ==================== VERİ YÜKLEME ====================

    def load_data(self):
        self.update_stats_cards()
        self.load_plans()
        self.load_employees()
        self.load_advances()

    def on_tab_changed(self, index):
        if index == 0:
            self.load_plans()
        elif index == 1:
            self.load_employees()
        elif index == 2:
            self.load_advances()

    # ==================== STİLLER ====================

    def _btn_style(self, color: str, text_color: str = "white") -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: {text_color};
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """

    def _mini_btn_style(self, color: str, text_color: str = "white") -> str:
        return f"""
            QPushButton {{
                background-color: {color}25;
                color: {color};
                border: 1px solid {color}50;
                border-radius: 7px;
                font-size: 14pt;
                font-weight: normal;
                padding: 0px;
                text-align: center;
                min-width: 0px;
                min-height: 0px;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: {text_color};
            }}
        """

    def _input_style(self) -> str:
        return f"""
            background-color: {AppStyles.BG_MEDIUM};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 10pt;
        """

    def _table_style(self) -> str:
        return f"""
            QTableWidget {{
                background-color: transparent;
                border: none;
                gridline-color: {AppStyles.BORDER};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{
                padding: 10px;
                border: none;
            }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARKEST};
                color: {AppStyles.TEXT_SECONDARY};
                padding: 10px;
                border: none;
                border-bottom: 1px solid {AppStyles.BORDER};
                font-weight: 600;
            }}
        """

    def _tab_style(self) -> str:
        return f"""
            QTabWidget::pane {{
                border: 1px solid {AppStyles.BORDER};
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 12px;
                padding: 15px;
            }}
            QTabBar::tab {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_SECONDARY};
                padding: 14px 30px;
                min-width: 220px;
                font-weight: bold;
                font-size: 10.5pt;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 6px;
            }}
            QTabBar::tab:selected {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.PRIMARY};
                border-bottom: 2px solid {AppStyles.PRIMARY};
            }}
            QTabBar::tab:hover:!selected {{
                color: {AppStyles.TEXT_PRIMARY};
                background-color: {AppStyles.BG_LIGHT};
            }}
        """