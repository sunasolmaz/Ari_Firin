# src/ui/pages/company_expenses_page.py
"""
Genel Şirket & Ortak Giderleri Yönetim Sayfası
Şube ve imalathane işletme giderleri haricinde, şirket ortaklarının
şirketten aldıkları paralar, özel harcamalar, kurumsal temsil ve genel merkez
harcamalarını yönetir.

Özellikler:
1. Ana Tablo (Sekme 1): Ortaklar ve harcama yapan kişilerin listesi ve Şirketten
   aldıkları TOPLAM GİDER tutarı.
2. Açılır Pencere (PersonExpensesDialog): Bir kişiye tıklandığında o kişiye ait
   farklı tarihlerdeki tüm giderlerin ekstra detay olarak listelenmesi ve
   o kişiye anında birden fazla yeni gider eklenebilmesi.
3. Tekil Detay Penceresi (ExpenseDetailDialog): Harcamanın nereye yapıldığını ve
   detaylı gerekçesini gösteren açılır pencere.
4. Günlük, Aylık, Yıllık periyot butonları ve tarih filtreleri (Tıpkı Faturalar sayfası gibi).
5. Tüm buton ve tablo kolonlarının diğer modüllerle (Faturalar, Depo, vb.) tam uyumu.
"""

from typing import Optional, Dict, List, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import pandas as pd

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QDoubleSpinBox, QMessageBox, QFileDialog, QHeaderView,
    QScrollArea, QDialog, QDateEdit, QTextEdit, QTabWidget,
    QButtonGroup, QRadioButton
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont

from ...models.user import User
from ...core.database import db
from ...core.logger import logger
from ...services.company_expense_service import company_expense_service
from ..styles import AppStyles


# ==================== STANDART STİLLER (DİĞER TABLOLARLA BİREBİR AYNI) ====================

def get_table_style() -> str:
    """Faturalar ve diğer sayfalardaki tablo stili"""
    return f"""
        QTableWidget {{
            background-color: {AppStyles.BG_DARK};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 8px;
            gridline-color: #242434;
            color: {AppStyles.TEXT_PRIMARY};
            font-size: 9.5pt;
        }}
        QTableWidget::item {{
            padding: 4px 6px;
            border: none;
            color: {AppStyles.TEXT_PRIMARY};
        }}
        QTableWidget::item:selected {{
            background-color: rgba(37, 99, 235, 0.35);
            color: #FFFFFF;
        }}
        QHeaderView {{
            background-color: #1e1e28;
            border: none;
        }}
        QHeaderView::section {{
            background-color: #1e1e28;
            color: #FFFFFF !important;
            border: none;
            border-bottom: 2px solid {AppStyles.PRIMARY};
            border-right: 1px solid #282838;
            height: 38px;
            padding: 4px 6px;
            font-weight: bold;
            font-size: 9.5pt;
        }}
        QHeaderView::section:hover {{
            background-color: #282838;
            color: #FFFFFF !important;
        }}
    """

def get_input_style() -> str:
    """Giriş alanları stili"""
    return f"""
        QLineEdit, QComboBox, QDateEdit, QTextEdit {{
            background-color: {AppStyles.BG_DARK};
            color: {AppStyles.TEXT_PRIMARY};
            border: 1px solid {AppStyles.BORDER};
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 9pt;
            min-height: 32px;
        }}
        QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus {{
            border-color: {AppStyles.PRIMARY};
        }}
        QComboBox QAbstractItemView {{
            background-color: {AppStyles.BG_DARK};
            color: {AppStyles.TEXT_PRIMARY};
            selection-background-color: {AppStyles.PRIMARY};
            selection-color: white;
        }}
    """


# ==================== DİALOG 1: TEKİL HARCAMA DETAY AÇILIR PENCERESİ ====================

class ExpenseDetailDialog(QDialog):
    """
    Satıra tıklandığında açılan, harcamanın nereye yapıldığını ve
    tüm detaylarını gösteren açılır pencere
    """

    def __init__(self, user: User, expense: Dict, parent=None):
        super().__init__(parent)
        self.user = user
        self.expense = expense
        self.is_deleted = False
        self.is_updated = False

        p_name = expense.get('person_name') or 'Ortak'
        self.setWindowTitle(f"🔍 Harcama Detayı - {p_name}")
        self.setMinimumWidth(620)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 22, 22, 22)

        # Üst Başlık & İkon
        top_h = QHBoxLayout()
        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        lbl_head = QLabel("🔍 HARCAMA DETAY BİLGİSİ")
        lbl_head.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.CYAN}; letter-spacing: 0.5px;")
        v_title.addWidget(lbl_head)

        lbl_sub = QLabel("Bu harcamanın nereye yapıldığı, kim tarafından alındığı ve gerekçe detayları")
        lbl_sub.setStyleSheet(f"font-size: 9pt; color: {AppStyles.TEXT_SECONDARY};")
        v_title.addWidget(lbl_sub)
        top_h.addLayout(v_title)
        top_h.addStretch()
        layout.addLayout(top_h)

        # 1. ÖNE ÇIKAN HARCAMA YERİ (NEREYE YAPILDI) KARTI
        loc_card = QFrame()
        loc_card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-left: 5px solid {AppStyles.CYAN};
                border-top: 1px solid {AppStyles.BORDER};
                border-right: 1px solid {AppStyles.BORDER};
                border-bottom: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 12px 16px;
            }}
        """)
        loc_lay = QVBoxLayout(loc_card)
        loc_lay.setSpacing(4)
        loc_tag = QLabel("📍 HARCAMA YERİ (NEREYE YAPILDI):")
        loc_tag.setStyleSheet(f"font-size: 8.5pt; font-weight: bold; color: {AppStyles.TEXT_MUTED};")
        loc_lay.addWidget(loc_tag)

        dest_text = self.expense.get('location_destination') or "Belirtilmemiş / Özel Harcama"
        loc_val = QLabel(f"📍 {dest_text}")
        loc_val.setWordWrap(True)
        loc_val.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {AppStyles.CYAN};")
        loc_lay.addWidget(loc_val)
        layout.addWidget(loc_card)

        # 2. AYRINTILI BİLGİ KARTLARI (GRID)
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 14px 16px;
            }}
        """)
        grid = QGridLayout(info_frame)
        grid.setSpacing(12)
        grid.setContentsMargins(6, 6, 6, 6)

        # Kişi / Ortak
        grid.addWidget(self._make_label("👤 Kişi / Ortak:"), 0, 0)
        p_val = QLabel(f"<b>{self.expense.get('person_name') or '-'}</b>")
        p_val.setStyleSheet(f"font-size: 10.5pt; color: {AppStyles.TEXT_PRIMARY};")
        grid.addWidget(p_val, 0, 1)

        # Tutar
        grid.addWidget(self._make_label("💰 Alınan Tutar:"), 0, 2)
        amt = float(self.expense.get('amount') or 0.0)
        amt_val = QLabel(f"<b>{amt:,.2f} ₺</b>")
        amt_val.setStyleSheet(f"font-size: 12.5pt; font-weight: bold; color: {AppStyles.ORANGE};")
        grid.addWidget(amt_val, 0, 3)

        # Tarih
        grid.addWidget(self._make_label("📅 Harcama Tarihi:"), 1, 0)
        d_val = str(self.expense.get('expense_date') or "")[:10]
        grid.addWidget(QLabel(d_val), 1, 1)

        # Kategori
        grid.addWidget(self._make_label("🏷️ Kategori:"), 1, 2)
        cat_val = QLabel(self.expense.get('category') or "-")
        cat_val.setStyleSheet(f"font-weight: bold; color: {AppStyles.PRIMARY};")
        grid.addWidget(cat_val, 1, 3)

        # Ödeme Şekli
        grid.addWidget(self._make_label("💳 Ödeme Şekli:"), 2, 0)
        grid.addWidget(QLabel(self.expense.get('payment_method') or "Nakit"), 2, 1)

        # Belge No
        grid.addWidget(self._make_label("🧾 Belge No:"), 2, 2)
        grid.addWidget(QLabel(self.expense.get('document_no') or "Yok / Kayıtsız"), 2, 3)

        layout.addWidget(info_frame)

        # 3. DETAYLI AÇIKLAMA KUTUSU
        desc_card = QFrame()
        desc_card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 12px 16px;
            }}
        """)
        desc_lay = QVBoxLayout(desc_card)
        desc_lay.setSpacing(6)
        desc_lbl_tag = QLabel("📝 Harcamanın Gerekçesi ve Detaylı Açıklaması:")
        desc_lbl_tag.setStyleSheet(f"font-size: 8.5pt; font-weight: bold; color: {AppStyles.TEXT_SECONDARY};")
        desc_lay.addWidget(desc_lbl_tag)

        desc_content = self.expense.get('description') or "Herhangi bir açıklama girilmemiş."
        desc_text = QLabel(desc_content)
        desc_text.setWordWrap(True)
        desc_text.setStyleSheet(f"font-size: 9.5pt; color: {AppStyles.TEXT_PRIMARY}; line-height: 1.4; padding: 4px 0;")
        desc_lay.addWidget(desc_text)

        creator = self.expense.get('created_by_name') or "Sistem"
        c_at = str(self.expense.get('created_at') or "")[:16]
        meta_lbl = QLabel(f"ℹ️ Kaydeden: {creator}  •  Kayıt Zamanı: {c_at}")
        meta_lbl.setStyleSheet(f"font-size: 8.5pt; color: {AppStyles.TEXT_MUTED}; margin-top: 4px;")
        desc_lay.addWidget(meta_lbl)

        layout.addWidget(desc_card)

        # 4. ALT AKSİYON BUTONLARI (Diğer pencereler gibi)
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)

        del_btn = QPushButton("🗑️ Sil")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(self.delete_expense)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.RED};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 9.5pt;
                min-height: 32px;
            }}
            QPushButton:hover {{ background-color: #dc2626; }}
        """)
        btn_bar.addWidget(del_btn)

        edit_btn = QPushButton("✏️ Düzenle")
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.clicked.connect(self.edit_expense)
        edit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.ORANGE};
                color: black;
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: bold;
                font-size: 9.5pt;
                min-height: 32px;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)
        btn_bar.addWidget(edit_btn)

        btn_bar.addStretch()

        close_btn = QPushButton("Kapat")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 20px;
                font-weight: bold;
                font-size: 9.5pt;
                min-height: 32px;
            }}
            QPushButton:hover {{ background-color: {AppStyles.BORDER}; }}
        """)
        btn_bar.addWidget(close_btn)

        layout.addLayout(btn_bar)

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 9pt; color: {AppStyles.TEXT_SECONDARY};")
        return lbl

    def edit_expense(self):
        dlg = CompanyExpenseDialog(self.user, expense=self.expense, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.is_updated = True
            updated = company_expense_service.get_expense(self.expense['id'])
            if updated:
                self.expense = updated
                self.accept()

    def delete_expense(self):
        p_name = self.expense.get('person_name', 'Ortak')
        amt = float(self.expense.get('amount', 0.0))
        dest = self.expense.get('location_destination') or 'Harcama'

        reply = QMessageBox.question(
            self,
            "Harcama Kaydını Sil",
            f"<b>{p_name}</b> adına kayıtlı <b>{amt:,.2f} ₺</b> tutarındaki harcamayı silmek istediğinize emin misiniz?<br><br>"
            f"<b>Harcama Yeri:</b> {dest}<br><br>"
            f"⚠️ <i>Bu işlem geri alınamaz.</i>",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = company_expense_service.delete_expense(self.expense['id'], user_id=getattr(self.user, 'id', None))
            if success:
                self.is_deleted = True
                QMessageBox.information(self, "Başarılı", msg)
                self.accept()
            else:
                QMessageBox.critical(self, "Hata", msg)


# ==================== DİALOG 2: KİŞİYE AİT TÜM GİDERLERİN AÇILIR PENCERESİ ====================

class PersonExpensesDialog(QDialog):
    """
    Kullanıcı ana tablodaki bir kişiye tıkladığında açılan pencere:
    - Aynı kişiye ait tüm giderlerin ekstra detay olarak listelendiği tablo
    - "➕ Bu Kişiye Yeni Gider Ekle" butonu (Aynı kişiye birden fazla yeni gider girebilme)
    - Kişi toplamı, özel çekimleri ve şirket masrafları özeti
    """

    def __init__(self, user: User, person_name: str, branch_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.user = user
        self.person_name = person_name
        self.branch_id = branch_id
        self.expenses_data = []
        self.filtered_expenses = []
        self.has_changes = False

        self.setWindowTitle(f"👤 {person_name} - Gider & Harcama Detayları")
        self.resize(1150, 680)
        self.setMinimumSize(980, 560)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; }}
        """)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # 1. Başlık & Kişi Özet Kartı
        header_card = QFrame()
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-left: 5px solid {AppStyles.PRIMARY};
                border-radius: 8px;
                padding: 10px 16px;
            }}
        """)
        h_lay = QVBoxLayout(header_card)
        h_lay.setSpacing(10)

        top_info = QHBoxLayout()
        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        self.lbl_person_title = QLabel(f"👤 {self.person_name}")
        self.lbl_person_title.setStyleSheet(f"font-size: 14.5pt; font-weight: bold; color: {AppStyles.CYAN};")
        v_title.addWidget(self.lbl_person_title)

        lbl_sub = QLabel("Bu ortağın / kişinin şirket üzerinden yaptığı tüm harcamalar ve para çekimleri")
        lbl_sub.setStyleSheet(f"font-size: 9pt; color: {AppStyles.TEXT_MUTED};")
        v_title.addWidget(lbl_sub)
        top_info.addLayout(v_title)
        top_info.addStretch()

        # "➕ Bu Kişiye Yeni Gider Ekle" Butonu
        btn_add = QPushButton("➕ Bu Kişiye Yeni Gider Ekle")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self.add_new_for_person)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-size: 9.5pt;
                min-height: 32px;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)
        top_info.addWidget(btn_add)
        h_lay.addLayout(top_info)

        # 4 Mini KPI Kartı
        stats_box = QHBoxLayout()
        stats_box.setSpacing(10)

        c1, self.lbl_kpi_total = self._create_mini_kpi("Toplam Gider (₺)", "0.00 ₺", AppStyles.ORANGE)
        stats_box.addWidget(c1)

        c2, self.lbl_kpi_personal = self._create_mini_kpi("Özel / Şahsi Çekim (₺)", "0.00 ₺", AppStyles.PURPLE)
        stats_box.addWidget(c2)

        c3, self.lbl_kpi_company = self._create_mini_kpi("Şirket Masrafı (₺)", "0.00 ₺", AppStyles.PRIMARY)
        stats_box.addWidget(c3)

        c4, self.lbl_kpi_cnt = self._create_mini_kpi("İşlem Sayısı", "0 Adet", AppStyles.CYAN)
        stats_box.addWidget(c4)

        h_lay.addLayout(stats_box)
        layout.addWidget(header_card)

        # 2. Tablo Üstü Arama ve Aksiyon Barı
        t_info = QHBoxLayout()
        t_info.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Harcama yeri, açıklama veya belge no ile filtrele...")
        self.search_input.setStyleSheet(get_input_style())
        self.search_input.textChanged.connect(self.filter_expenses)
        t_info.addWidget(self.search_input, 4)

        t_info.addStretch()

        btn_export = QPushButton("📤 Excel Dökümü Al")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self.export_person_to_excel)
        btn_export.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.GREEN};
                border: 1px solid {AppStyles.GREEN};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 9pt;
                font-weight: bold;
                min-height: 32px;
            }}
            QPushButton:hover {{ background-color: {AppStyles.GREEN}; color: white; }}
        """)
        t_info.addWidget(btn_export)
        layout.addLayout(t_info)

        # 3. Detay Tablosu (Standart Kolonlar ve Stiller)
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Tarih", "Tutar (₺)", "Harcama Yeri", "Kategori",
            "Ödeme Şekli", "Belge No", "Açıklama", "İşlemler"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setStyleSheet(get_table_style())

        header = self.table.horizontalHeader()
        header.setFixedHeight(38)
        header.setFont(QFont("Segoe UI", 9, QFont.Bold))
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setSectionResizeMode(QHeaderView.Stretch)

        header.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 110)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 130)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(2, 180)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 140)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.setColumnWidth(4, 120)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        self.table.setColumnWidth(5, 105)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 135)

        self.table.cellClicked.connect(self.on_cell_clicked)
        self.table.cellDoubleClicked.connect(self.on_cell_clicked)
        layout.addWidget(self.table, 1)

        # 4. Alt Bilgi & Kapat Butonu
        bot_bar = QHBoxLayout()
        self.lbl_detail_summary = QLabel("Toplam: 0 gider kaydı listelendi")
        self.lbl_detail_summary.setStyleSheet(f"font-size: 9pt; color: {AppStyles.TEXT_SECONDARY};")
        bot_bar.addWidget(self.lbl_detail_summary)
        bot_bar.addStretch()

        close_btn = QPushButton("Kapat")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 22px;
                font-weight: bold;
                font-size: 9.5pt;
                min-height: 32px;
            }}
            QPushButton:hover {{ background-color: {AppStyles.BORDER}; }}
        """)
        bot_bar.addWidget(close_btn)
        layout.addLayout(bot_bar)

    def _create_mini_kpi(self, title: str, default_val: str, color: str):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-left: 4px solid {color};
                border-radius: 6px;
                padding: 6px 10px;
            }}
            QFrame QLabel {{ background: transparent; border: none; }}
        """)
        c_lay = QVBoxLayout(card)
        c_lay.setSpacing(2)
        c_lay.setContentsMargins(4, 4, 4, 4)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 8pt; color: {AppStyles.TEXT_MUTED}; font-weight: bold;")
        c_lay.addWidget(t_lbl)

        v_lbl = QLabel(default_val)
        v_lbl.setStyleSheet(f"font-size: 11.5pt; font-weight: bold; color: {color};")
        c_lay.addWidget(v_lbl)

        return card, v_lbl

    def load_data(self):
        """Veritabanından bu kişinin tüm giderlerini çeker"""
        self.expenses_data = company_expense_service.get_expenses_by_person(self.person_name)
        self.filter_expenses()

    def filter_expenses(self):
        """Arama kutusuna göre detay listesini filtreler ve tabloyu doldurur"""
        query = self.search_input.text().strip().lower()
        if query:
            self.filtered_expenses = [
                e for e in self.expenses_data
                if query in str(e.get('location_destination') or '').lower()
                or query in str(e.get('description') or '').lower()
                or query in str(e.get('category') or '').lower()
                or query in str(e.get('document_no') or '').lower()
            ]
        else:
            self.filtered_expenses = list(self.expenses_data)

        self.populate_table()

    def populate_table(self):
        self.table.setRowCount(len(self.filtered_expenses))

        total_amt = 0.0
        personal_amt = 0.0
        company_amt = 0.0

        for row, exp in enumerate(self.filtered_expenses):
            d_val = str(exp.get('expense_date') or "")[:10]
            amt = float(exp.get('amount') or 0.0)
            dest = exp.get('location_destination') or "-"
            cat = exp.get('category') or "-"
            pay_m = exp.get('payment_method') or "Nakit"
            doc = exp.get('document_no') or "-"
            desc = exp.get('description') or "-"

            total_amt += amt
            if "Ortak" in cat:
                personal_amt += amt
            else:
                company_amt += amt

            # 0: Tarih
            d_item = QTableWidgetItem(d_val)
            d_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, d_item)

            # 1: Tutar
            amt_item = QTableWidgetItem(f"{amt:,.2f} ₺")
            amt_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amt_item.setForeground(QColor(AppStyles.ORANGE))
            self.table.setItem(row, 1, amt_item)

            # 2: Harcama Yeri
            dest_item = QTableWidgetItem(f"📍 {dest}")
            dest_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            dest_item.setForeground(QColor(AppStyles.CYAN))
            self.table.setItem(row, 2, dest_item)

            # 3: Kategori
            cat_item = QTableWidgetItem(cat)
            if "Ortak" in cat:
                cat_item.setForeground(QColor(AppStyles.PURPLE))
            else:
                cat_item.setForeground(QColor(AppStyles.PRIMARY))
            self.table.setItem(row, 3, cat_item)

            # 4: Ödeme Şekli
            pay_item = QTableWidgetItem(pay_m)
            pay_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, pay_item)

            # 5: Belge No
            doc_item = QTableWidgetItem(doc)
            doc_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 5, doc_item)

            # 6: Açıklama
            self.table.setItem(row, 6, QTableWidgetItem(desc))

            # 7: İşlem Butonları (Detay 👁️, Düzenle ✏️, Sil 🗑️)
            act_w = QWidget()
            act_w.setStyleSheet("background: transparent;")
            a_lay = QHBoxLayout(act_w)
            a_lay.setContentsMargins(1, 1, 1, 1)
            a_lay.setSpacing(4)
            a_lay.setAlignment(Qt.AlignCenter)

            btn_view = QPushButton("👁️")
            btn_view.setToolTip("Harcama Detayını Gör")
            btn_view.setFixedSize(36, 28)
            btn_view.setCursor(Qt.PointingHandCursor)
            btn_view.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    border-radius: 6px;
                    font-size: 11pt;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover { background-color: #0369a1; }
            """)
            btn_view.clicked.connect(lambda ch, e=exp: self.open_single_detail(e))

            btn_edit = QPushButton("✏️")
            btn_edit.setToolTip("Bu Gideri Düzenle")
            btn_edit.setFixedSize(36, 28)
            btn_edit.setCursor(Qt.PointingHandCursor)
            btn_edit.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.ORANGE};
                    color: white;
                    border-radius: 6px;
                    font-size: 11pt;
                    font-weight: bold;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #d97706; }}
            """)
            btn_edit.clicked.connect(lambda ch, e=exp: self.edit_single_expense(e))

            btn_del = QPushButton("🗑️")
            btn_del.setToolTip("Bu Gideri Sil")
            btn_del.setFixedSize(36, 28)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.RED};
                    color: white;
                    border-radius: 6px;
                    font-size: 11pt;
                    font-weight: bold;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #dc2626; }}
            """)
            btn_del.clicked.connect(lambda ch, e=exp: self.delete_single_expense(e))

            a_lay.addWidget(btn_view)
            a_lay.addWidget(btn_edit)
            a_lay.addWidget(btn_del)
            self.table.setCellWidget(row, 7, act_w)

        # Üst KPI Kartlarını güncelle (Tüm kayıtlar üzerinden hesaplanır)
        tot_all = sum(float(e.get('amount') or 0.0) for e in self.expenses_data)
        pers_all = sum(float(e.get('amount') or 0.0) for e in self.expenses_data if "Ortak" in str(e.get('category') or ''))
        comp_all = tot_all - pers_all

        self.lbl_kpi_total.setText(f"{tot_all:,.2f} ₺")
        self.lbl_kpi_personal.setText(f"{pers_all:,.2f} ₺")
        self.lbl_kpi_company.setText(f"{comp_all:,.2f} ₺")
        self.lbl_kpi_cnt.setText(f"{len(self.expenses_data)} Adet")

        self.lbl_detail_summary.setText(f"Toplam <b>{len(self.filtered_expenses)}</b> gider listelendi | Listelenen Tutar: <b style='color:{AppStyles.ORANGE};'>{total_amt:,.2f} ₺</b>")

    def on_cell_clicked(self, row: int, col: int = 0):
        if col == 7:  # İşlemler kolonu hariç
            return
        if 0 <= row < len(self.filtered_expenses):
            self.open_single_detail(self.filtered_expenses[row])

    def open_single_detail(self, exp: Dict):
        """Harcamanın nereye yapıldığını ve açıklamasını detaylı açar"""
        dlg = ExpenseDetailDialog(self.user, exp, parent=self)
        dlg.exec_()
        if dlg.is_deleted or dlg.is_updated:
            self.has_changes = True
            self.load_data()

    def edit_single_expense(self, exp: Dict):
        dlg = CompanyExpenseDialog(self.user, expense=exp, branch_id=self.branch_id, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.has_changes = True
            self.load_data()

    def delete_single_expense(self, exp: Dict):
        amt = float(exp.get('amount', 0.0))
        dest = exp.get('location_destination') or 'Harcama'
        reply = QMessageBox.question(
            self, "Silme Onayı",
            f"<b>{amt:,.2f} ₺</b> tutarındaki bu harcamayı silmek istediğinize emin misiniz?<br><b>Yer:</b> {dest}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = company_expense_service.delete_expense(exp['id'], user_id=getattr(self.user, 'id', None))
            if success:
                self.has_changes = True
                self.load_data()
            else:
                QMessageBox.critical(self, "Hata", msg)

    def add_new_for_person(self):
        """Kişi adı önceden doldurulmuş harcama dialogu açar - Yeni gider girilince listeye eklenir"""
        prefill = {'person_name': self.person_name}
        dlg = CompanyExpenseDialog(self.user, expense=prefill, branch_id=self.branch_id, parent=self)
        dlg.is_edit = False
        dlg.expense = None
        dlg.person_combo.setCurrentText(self.person_name)
        dlg.person_combo.setEnabled(False)  # Bu kişi için kilitli
        if dlg.exec_() == QDialog.Accepted:
            self.has_changes = True
            self.load_data()

    def export_person_to_excel(self):
        if not self.expenses_data:
            return
        f_name, _ = QFileDialog.getSaveFileName(
            self, "Excel Olarak Kaydet", f"{self.person_name}_Gider_Dokumu.xlsx", "Excel (*.xlsx)"
        )
        if f_name:
            data = []
            for e in self.expenses_data:
                data.append({
                    "Tarih": str(e.get('expense_date')),
                    "Kişi / Ortak": self.person_name,
                    "Tutar (₺)": float(e.get('amount') or 0.0),
                    "Harcama Yeri": e.get('location_destination') or "",
                    "Kategori": e.get('category') or "",
                    "Ödeme Şekli": e.get('payment_method') or "",
                    "Belge No": e.get('document_no') or "",
                    "Açıklama": e.get('description') or ""
                })
            pd.DataFrame(data).to_excel(f_name, index=False)
            QMessageBox.information(self, "Başarılı", f"Dosya kaydedildi:\n{f_name}")


# ==================== DİALOG 3: HARCAMA EKLE / DÜZENLE ====================

class CompanyExpenseDialog(QDialog):
    """Genel Şirket veya Ortak Harcaması Ekleme / Düzenleme Dialogu"""

    def __init__(self, user: User, expense: Optional[Dict] = None, branch_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.user = user
        self.expense = expense
        self.branch_id = branch_id
        self.is_edit = expense is not None and 'id' in expense

        title_text = "✏️ Şirket / Ortak Harcamasını Düzenle" if self.is_edit else "➕ Yeni Genel Şirket / Ortak Harcaması Ekle"
        self.setWindowTitle(title_text)
        self.setMinimumWidth(560)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_DARK}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(22, 22, 22, 22)

        title_color = AppStyles.ORANGE if self.is_edit else AppStyles.PRIMARY
        title_icon = "✏️" if self.is_edit else "➕"
        title_text = "Şirket / Ortak Harcamasını Düzenle" if self.is_edit else "Yeni Şirket / Ortak Harcaması"

        title = QLabel(f"{title_icon} {title_text}")
        title.setStyleSheet(f"font-size: 15pt; font-weight: bold; color: {title_color};")
        layout.addWidget(title)

        info_lbl = QLabel("ℹ️ Şube veya imalat işletme giderleri dışındaki şirket geneli ve ortak özel harcamaları buraya kaydedilir.")
        info_lbl.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 9pt;")
        layout.addWidget(info_lbl)

        form = QGridLayout()
        form.setSpacing(10)
        row = 0

        # 1. Kime / Ortak Adı
        form.addWidget(QLabel("Kişi / Ortak Adı *:"), row, 0)
        self.person_combo = QComboBox()
        self.person_combo.setEditable(True)
        self.person_combo.setPlaceholderText("Ortak veya harcama yapılan kişinin adı")
        existing_persons = company_expense_service.get_distinct_persons()
        for p in existing_persons:
            self.person_combo.addItem(p)
        if self.expense:
            self.person_combo.setCurrentText(self.expense.get('person_name') or "")
        self.person_combo.setStyleSheet(get_input_style())
        form.addWidget(self.person_combo, row, 1)
        row += 1

        # 2. Harcama Tutarı
        form.addWidget(QLabel("Tutar (₺) *:"), row, 0)
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 100000000.0)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSuffix(" ₺")
        if self.is_edit:
            self.amount_spin.setValue(float(self.expense.get('amount') or 0.0))
        else:
            self.amount_spin.setValue(1000.0)
        self.amount_spin.setStyleSheet(get_input_style())
        form.addWidget(self.amount_spin, row, 1)
        row += 1

        # 3. Harcama Yeri (Nereye Yapıldı)
        form.addWidget(QLabel("Harcama Yeri (Nereye Yapıldı) *:"), row, 0)
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("Örn: Divan Lokantası (İş Yemeği), Noter Masrafı, Özel Harcama...")
        if self.is_edit:
            self.location_input.setText(self.expense.get('location_destination') or "")
        self.location_input.setStyleSheet(get_input_style())
        form.addWidget(self.location_input, row, 1)
        row += 1

        # 4. Tarih
        form.addWidget(QLabel("Harcama Tarihi *:"), row, 0)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        if self.is_edit and self.expense.get('expense_date'):
            exp_d = self.expense.get('expense_date')
            try:
                if isinstance(exp_d, str):
                    qd = QDate.fromString(exp_d[:10], "yyyy-MM-dd")
                elif hasattr(exp_d, 'year'):
                    qd = QDate(exp_d.year, exp_d.month, exp_d.day)
                else:
                    qd = QDate.currentDate()
                self.date_edit.setDate(qd)
            except Exception:
                self.date_edit.setDate(QDate.currentDate())
        else:
            self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setStyleSheet(get_input_style())
        form.addWidget(self.date_edit, row, 1)
        row += 1

        # 5. Kategori
        form.addWidget(QLabel("Kategori:"), row, 0)
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(company_expense_service.DEFAULT_CATEGORIES)
        if self.is_edit:
            cur_cat = self.expense.get('category') or ""
            idx = self.cat_combo.findText(cur_cat)
            if idx >= 0:
                self.cat_combo.setCurrentIndex(idx)
        self.cat_combo.setStyleSheet(get_input_style())
        form.addWidget(self.cat_combo, row, 1)
        row += 1

        # 6. Ödeme Şekli
        form.addWidget(QLabel("Ödeme Şekli:"), row, 0)
        self.pay_combo = QComboBox()
        self.pay_combo.addItems(company_expense_service.PAYMENT_METHODS)
        if self.is_edit:
            cur_pay = self.expense.get('payment_method') or ""
            idx = self.pay_combo.findText(cur_pay)
            if idx >= 0:
                self.pay_combo.setCurrentIndex(idx)
        self.pay_combo.setStyleSheet(get_input_style())
        form.addWidget(self.pay_combo, row, 1)
        row += 1

        # 7. Belge No
        form.addWidget(QLabel("Belge No:"), row, 0)
        self.doc_input = QLineEdit()
        self.doc_input.setPlaceholderText("İsteğe bağlı fiş/dekont numarası")
        if self.is_edit:
            self.doc_input.setText(self.expense.get('document_no') or "")
        self.doc_input.setStyleSheet(get_input_style())
        form.addWidget(self.doc_input, row, 1)
        row += 1

        # 8. Açıklama
        form.addWidget(QLabel("Açıklama:"), row, 0)
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Harcamanın gerekçesi veya detayları...")
        self.desc_input.setMaximumHeight(85)
        if self.is_edit:
            self.desc_input.setPlainText(self.expense.get('description') or "")
        self.desc_input.setStyleSheet(get_input_style())
        form.addWidget(self.desc_input, row, 1)

        layout.addLayout(form)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_LIGHT};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: bold;
                min-height: 32px;
            }}
            QPushButton:hover {{ background-color: {AppStyles.BORDER}; }}
        """)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Kaydet" if self.is_edit else "➕ Kaydet")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.save)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {title_color};
                color: {'#000000' if title_color in (AppStyles.CYAN, AppStyles.ORANGE) else 'white'};
                border: none;
                border-radius: 6px;
                padding: 6px 22px;
                font-weight: bold;
                font-size: 9.5pt;
                min-height: 32px;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        self.setLayout(layout)

    def save(self):
        person_name = self.person_combo.currentText().strip()
        if not person_name:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen kişi / ortak adı alanını doldurun!")
            return

        amount = self.amount_spin.value()
        if amount <= 0:
            QMessageBox.warning(self, "Eksik Bilgi", "Harcama tutarı 0'dan büyük olmalıdır!")
            return

        data = {
            'person_name': person_name,
            'amount': amount,
            'location_destination': self.location_input.text().strip() or None,
            'expense_date': self.date_edit.date().toString("yyyy-MM-dd"),
            'category': self.cat_combo.currentText().strip(),
            'payment_method': self.pay_combo.currentText().strip(),
            'document_no': self.doc_input.text().strip() or None,
            'description': self.desc_input.toPlainText().strip() or None,
            'branch_id': self.branch_id
        }

        user_id = getattr(self.user, 'id', None)

        if self.is_edit:
            success, msg = company_expense_service.update_expense(self.expense['id'], data, user_id=user_id)
        else:
            success, msg, _ = company_expense_service.add_expense(data, user_id=user_id)

        if success:
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", msg)


# ==================== ANA SAYFA BİLEŞENİ ====================

class CompanyExpensesPage(QWidget):
    """
    Genel Şirket & Ortak Giderleri Yönetim Sayfası
    - Ana Tablo: Kişi & Ortaklar Listesi ve Şirketten Alınan TOPLAM GİDER
    - Satıra tıklandığında: Açılır pencerede o kişiye ait giderlerin ekstra detay olarak listelenmesi
    - Aynı kişiye birden fazla yeni gider ekleyebilme
    """

    def __init__(self, user: User, branch_id: Optional[int] = None, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window
        self.persons_cache: List[Dict] = []
        self.expenses_cache: List[Dict] = []
        self.current_period = "all"

        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setObjectName("CompanyExpensesPage")
        self.setStyleSheet(f"#CompanyExpensesPage {{ background-color: {AppStyles.BG_DARK}; }}")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 16, 22, 16)
        main_layout.setSpacing(12)

        # 1. ÜST BAŞLIK VE HIZLI BUTONLAR
        top_bar = self.create_top_bar()
        main_layout.addWidget(top_bar)

        # 2. KPI İSTATİSTİK KARTLARI (4 Adet)
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(12)
        main_layout.addLayout(self.stats_layout)

        # 3. HIZLI DÖNEM VE TARİH ÇUBUĞU (Günlük / Aylık / Yıllık / Tüm Zamanlar)
        self.period_bar = self.create_period_selector_bar()
        main_layout.addWidget(self.period_bar)

        # 4. İKİ ANA SEKME (Ana Tablo: Ortaklar & Kişi Toplamları | İkinci Tab: Tüm Hareketler)
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {AppStyles.BORDER};
                background-color: {AppStyles.BG_DARK};
                border-radius: 8px;
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_SECONDARY};
                font-size: 10pt;
                font-weight: bold;
                padding: 9px 20px;
                border: 1px solid {AppStyles.BORDER};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 6px;
            }}
            QTabBar::tab:selected {{
                background-color: {AppStyles.PRIMARY};
                color: white;
                border-color: {AppStyles.PRIMARY};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {AppStyles.BG_LIGHT};
                color: white;
            }}
        """)

        # ANA TABLO: Ortak & Şirket Giderleri (Kişi Bazlı Toplam)
        tab_persons = self.create_persons_summary_tab()
        self.tab_widget.addTab(tab_persons, "👥 Ortak & Şirket Giderleri (Kişi Bazlı Toplam)")

        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.tab_widget, 1)

    # ==================== 1. ÜST BAŞLIK ====================

    def create_top_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel("💼 Genel Şirket & Ortak Giderleri")
        title.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)

        subtitle = QLabel("Şube ve imalat dışındaki ortak çekimleri, özel harcamalar ve şirket geneli masraf takibi")
        subtitle.setStyleSheet(f"font-size: 9.5pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(subtitle)
        layout.addLayout(left)

        layout.addStretch()

        # Butonlar (Standart Yükseklik ve Tasarım)
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 9pt;
                min-height: 32px;
            }}
            QPushButton:hover {{ border-color: {AppStyles.PRIMARY}; }}
        """)
        btn_box.addWidget(refresh_btn)

        export_btn = QPushButton("📤 Excel'e Aktar")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self.export_current_tab)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.GREEN};
                border: 1px solid {AppStyles.GREEN};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 9pt;
                min-height: 32px;
            }}
            QPushButton:hover {{ background-color: {AppStyles.GREEN}; color: white; }}
        """)
        btn_box.addWidget(export_btn)

        add_btn = QPushButton("➕ Yeni Harcama Ekle")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self.open_add_dialog)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.GREEN};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 9.5pt;
                min-height: 32px;
            }}
            QPushButton:hover {{ background-color: #059669; }}
        """)
        btn_box.addWidget(add_btn)

        layout.addLayout(btn_box)
        return bar

    # ==================== 2. KPI KARTLARI ====================

    def update_stats_cards(self):
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        stats = company_expense_service.get_summary_stats(start_date=start, end_date=end)

        tot_amt = stats.get('total_amount', 0.0)
        p_draw = stats.get('partner_drawings', 0.0)
        comp_exp = stats.get('company_expenses', 0.0)
        m_tot = stats.get('month_total', 0.0)
        cnt = stats.get('total_count', 0)

        cards = [
            ("💰", "Toplam Gider", f"{tot_amt:,.2f} ₺", AppStyles.ORANGE, f"Seçili dönem ({cnt} işlem)"),
            ("🤝", "Ortak Çekimleri / Özel", f"{p_draw:,.2f} ₺", AppStyles.PURPLE, "Ortak şahsi avans ve çekimleri"),
            ("🏢", "Şirket Masrafları", f"{comp_exp:,.2f} ₺", AppStyles.PRIMARY, "Yönetim, temsil & genel giderler"),
            ("📅", "Bu Ayki Toplam", f"{m_tot:,.2f} ₺", AppStyles.CYAN, f"Cari ay ({stats.get('month_count', 0)} işlem)")
        ]

        for icon, title, val, color, sub in cards:
            card = self.create_kpi_card(icon, title, val, color, sub)
            self.stats_layout.addWidget(card)

    def create_kpi_card(self, icon: str, title: str, val: str, color: str, sub: str) -> QFrame:
        card = QFrame()
        card.setMinimumHeight(84)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border-radius: 8px;
                border-left: 4px solid {color};
                border-top: 1px solid {AppStyles.BORDER};
                border-right: 1px solid {AppStyles.BORDER};
                border-bottom: 1px solid {AppStyles.BORDER};
                padding: 8px 14px;
            }}
            QFrame QLabel {{ background: transparent; border: none; }}
        """)
        lay = QVBoxLayout(card)
        lay.setSpacing(2)

        top = QHBoxLayout()
        top_lbl = QLabel(f"{icon} {title}")
        top_lbl.setStyleSheet(f"font-size: 8.5pt; font-weight: bold; color: {AppStyles.TEXT_SECONDARY};")
        top.addWidget(top_lbl)
        top.addStretch()
        lay.addLayout(top)

        val_lbl = QLabel(val)
        val_lbl.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {color}; margin-top: 1px;")
        lay.addWidget(val_lbl)

        sub_lbl = QLabel(sub)
        sub_lbl.setStyleSheet(f"font-size: 8pt; color: {AppStyles.TEXT_MUTED};")
        lay.addWidget(sub_lbl)

        return card

    # ==================== DÖNEM VE TARİH ÇUBUĞU ====================

    def create_period_selector_bar(self) -> QFrame:
        """Kullanıcının Günlük, Aylık, Yıllık tek tuşla geçiş yapabileceği genel periyot ve tarih çubuğu"""
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 6px 12px;
            }}
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(10)

        lbl = QLabel("⏳ Hızlı Dönem:")
        lbl.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {AppStyles.TEXT_SECONDARY};")
        lay.addWidget(lbl)

        self.btn_period_today = QPushButton("📅 Günlük (Bugün)")
        self.btn_period_month = QPushButton("📆 Aylık (Bu Ay)")
        self.btn_period_year = QPushButton("🗓️ Yıllık (Bu Yıl)")
        self.btn_period_all = QPushButton("Tüm Zamanlar / Özel")

        buttons = [
            (self.btn_period_today, "today"),
            (self.btn_period_month, "month"),
            (self.btn_period_year, "year"),
            (self.btn_period_all, "all")
        ]

        self.period_btn_group = QButtonGroup(self)
        for btn, key in buttons:
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.BG_DARK};
                    color: {AppStyles.TEXT_PRIMARY};
                    border: 1px solid {AppStyles.BORDER};
                    border-radius: 6px;
                    padding: 0 14px;
                    font-size: 9pt;
                    font-weight: 600;
                }}
                QPushButton:checked {{
                    background-color: {AppStyles.PRIMARY};
                    color: white;
                    border-color: {AppStyles.PRIMARY};
                }}
                QPushButton:hover:!checked {{
                    background-color: {AppStyles.BG_LIGHT};
                }}
            """)
            btn.clicked.connect(lambda ch, k=key: self.set_period(k))
            self.period_btn_group.addButton(btn)
            lay.addWidget(btn)

        self.btn_period_all.setChecked(True)

        lay.addStretch()

        # Tarih Aralığı Seçicileri
        d_lbl = QLabel("📅 Tarih Aralığı:")
        d_lbl.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {AppStyles.TEXT_SECONDARY};")
        lay.addWidget(d_lbl)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addYears(-10))
        self.start_date.setDisplayFormat("dd.MM.yyyy")
        self.start_date.setMinimumHeight(32)
        self.start_date.dateChanged.connect(self.on_date_filter_changed)
        self.start_date.setStyleSheet(get_input_style())
        lay.addWidget(self.start_date)

        dash_lbl = QLabel("-")
        dash_lbl.setStyleSheet(f"color: {AppStyles.TEXT_MUTED}; font-weight: bold;")
        lay.addWidget(dash_lbl)

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate().addYears(1))
        self.end_date.setDisplayFormat("dd.MM.yyyy")
        self.end_date.setMinimumHeight(32)
        self.end_date.dateChanged.connect(self.on_date_filter_changed)
        self.end_date.setStyleSheet(get_input_style())
        lay.addWidget(self.end_date)

        return bar

    # ==================== SEKME 1 (ANA TABLO): ORTAKLAR VE TOPLAM GİDERLER ====================

    def create_persons_summary_tab(self) -> QWidget:
        """
        ANA TABLO:
        Kişi ve ortakların listesi ve şirketten aldıkları TOPLAM GİDER tutarı.
        Satıra tıklanınca PersonExpensesDialog açılır penceresi açılır.
        """
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Üst Arama & Bilgi
        top_h = QHBoxLayout()
        top_h.setSpacing(8)

        self.person_search_input = QLineEdit()
        self.person_search_input.setPlaceholderText("🔍 Kişi veya ortak adı ile ara...")
        self.person_search_input.setStyleSheet(get_input_style())
        self.person_search_input.textChanged.connect(self.load_persons_table)
        top_h.addWidget(self.person_search_input, 3)

        top_h.addStretch()

        hint_lbl = QLabel("💡 Bir kişinin satırına tıklayarak tüm gider detaylarını görebilir ve yeni giderler ekleyebilirsiniz.")
        hint_lbl.setStyleSheet(f"font-size: 9pt; color: {AppStyles.CYAN};")
        top_h.addWidget(hint_lbl)
        lay.addLayout(top_h)

        # Tablo (Faturalar ve diğer tablolar ile birebir aynı kolon düzeni)
        self.person_table = QTableWidget()
        self.person_table.setColumnCount(7)
        self.person_table.setHorizontalHeaderLabels([
            "Kişi / Ortak Adı", "İşlem Sayısı", "Son İşlem Tarihi",
            "Özel / Şahsi (₺)", "Şirket Masrafı (₺)", "Toplam Gider (₺)", "İşlemler"
        ])
        self.person_table.setAlternatingRowColors(True)
        self.person_table.verticalHeader().setVisible(False)
        self.person_table.verticalHeader().setDefaultSectionSize(46)
        self.person_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.person_table.setSelectionMode(QTableWidget.SingleSelection)
        self.person_table.setStyleSheet(get_table_style())

        header = self.person_table.horizontalHeader()
        header.setFixedHeight(38)
        header.setFont(QFont("Segoe UI", 9, QFont.Bold))
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setSectionResizeMode(QHeaderView.Stretch)

        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        self.person_table.setColumnWidth(1, 110)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        self.person_table.setColumnWidth(2, 120)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        self.person_table.setColumnWidth(3, 150)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        self.person_table.setColumnWidth(4, 150)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        self.person_table.setColumnWidth(5, 170)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        self.person_table.setColumnWidth(6, 95)

        # Satıra tıklanınca açılır pencerede ekstra detaylar listelensin
        self.person_table.cellClicked.connect(self.on_person_row_clicked)
        self.person_table.cellDoubleClicked.connect(self.on_person_row_clicked)
        lay.addWidget(self.person_table, 1)

        # Alt Bilgi Paneli
        bot_bar = QHBoxLayout()
        self.lbl_person_summary = QLabel("Toplam: 0 kişi / ortak listelendi")
        self.lbl_person_summary.setStyleSheet(f"font-size: 9.5pt; font-weight: 600; color: {AppStyles.TEXT_SECONDARY};")
        bot_bar.addWidget(self.lbl_person_summary)
        bot_bar.addStretch()

        lay.addLayout(bot_bar)
        return w

    # ==================== SEKME 2: TÜM GİDER HAREKETLERİ LİSTESİ ====================

    def create_expenses_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Filtreler (Arama, Kişi, Kategori)
        filters = self.create_expense_filters()
        lay.addWidget(filters)

        # Tablo
        self.exp_table = QTableWidget()
        self.exp_table.setColumnCount(8)
        self.exp_table.setHorizontalHeaderLabels([
            "Tarih", "Kişi / Ortak", "Tutar (₺)", "Harcama Yeri",
            "Kategori", "Ödeme Şekli", "Belge No", "İşlemler"
        ])
        self.exp_table.setAlternatingRowColors(True)
        self.exp_table.verticalHeader().setVisible(False)
        self.exp_table.verticalHeader().setDefaultSectionSize(44)
        self.exp_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.exp_table.setSelectionMode(QTableWidget.SingleSelection)
        self.exp_table.setStyleSheet(get_table_style())

        header = self.exp_table.horizontalHeader()
        header.setFixedHeight(38)
        header.setFont(QFont("Segoe UI", 9, QFont.Bold))
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setSectionResizeMode(QHeaderView.Stretch)

        header.setSectionResizeMode(0, QHeaderView.Interactive)
        self.exp_table.setColumnWidth(0, 110)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        self.exp_table.setColumnWidth(1, 160)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        self.exp_table.setColumnWidth(2, 130)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        self.exp_table.setColumnWidth(4, 140)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        self.exp_table.setColumnWidth(5, 120)
        header.setSectionResizeMode(6, QHeaderView.Interactive)
        self.exp_table.setColumnWidth(6, 105)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        self.exp_table.setColumnWidth(7, 135)

        self.exp_table.cellClicked.connect(self.on_expense_row_clicked)
        self.exp_table.cellDoubleClicked.connect(self.on_expense_row_clicked)
        lay.addWidget(self.exp_table, 1)

        # Alt Bilgi Paneli
        bot_bar = QHBoxLayout()
        self.lbl_exp_summary = QLabel("Toplam: 0 gider listelendi")
        self.lbl_exp_summary.setStyleSheet(f"font-size: 9.5pt; font-weight: 600; color: {AppStyles.TEXT_SECONDARY};")
        bot_bar.addWidget(self.lbl_exp_summary)
        bot_bar.addStretch()

        lay.addLayout(bot_bar)
        return w

    def create_expense_filters(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 6px 10px;
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setSpacing(10)
        layout.setContentsMargins(4, 2, 4, 2)

        # 1. Arama
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Kişi, harcama yeri, açıklama veya belge no ara...")
        self.search_input.textChanged.connect(self.load_expenses_table)
        self.search_input.setStyleSheet(get_input_style())
        layout.addWidget(self.search_input, 4)

        # 2. Kişi Filtresi
        layout.addWidget(QLabel("Kişi:"))
        self.person_filter = QComboBox()
        self.person_filter.addItem("Tüm Kişiler", "Tümü")
        self.person_filter.currentIndexChanged.connect(self.load_expenses_table)
        self.person_filter.setStyleSheet(get_input_style())
        layout.addWidget(self.person_filter, 2)

        # 3. Kategori Filtresi
        layout.addWidget(QLabel("Kategori:"))
        self.cat_filter = QComboBox()
        self.cat_filter.addItem("Tüm Kategoriler", "Tümü")
        for cat in company_expense_service.DEFAULT_CATEGORIES:
            self.cat_filter.addItem(cat, cat)
        self.cat_filter.currentIndexChanged.connect(self.load_expenses_table)
        self.cat_filter.setStyleSheet(get_input_style())
        layout.addWidget(self.cat_filter, 2)

        return bar

    # ==================== VERİ YÜKLEME & DÖNEM GEÇİŞLERİ ====================

    def set_period(self, period: str):
        """Günlük, Aylık, Yıllık veya Özel periyodu ayarlar"""
        self.current_period = period
        today = QDate.currentDate()

        self.start_date.blockSignals(True)
        self.end_date.blockSignals(True)

        if period == "today":
            self.start_date.setDate(today)
            self.end_date.setDate(today)
        elif period == "month":
            first_day = QDate(today.year(), today.month(), 1)
            self.start_date.setDate(first_day)
            self.end_date.setDate(today)
        elif period == "year":
            first_day = QDate(today.year(), 1, 1)
            self.start_date.setDate(first_day)
            self.end_date.setDate(today)
        else:
            self.start_date.setDate(today.addYears(-10))
            self.end_date.setDate(today.addYears(1))

        self.start_date.blockSignals(False)
        self.end_date.blockSignals(False)

        self.load_data()

    def on_date_filter_changed(self):
        self.update_stats_cards()
        self.load_persons_table()
        if hasattr(self, 'exp_table'):
            self.load_expenses_table()

    def on_tab_changed(self, idx: int):
        if idx == 0:
            self.load_persons_table()
        elif hasattr(self, 'exp_table'):
            self.load_expenses_table()

    def load_data(self):
        if hasattr(self, 'person_filter'):
            self.refresh_person_filter()
        self.update_stats_cards()
        self.load_persons_table()
        if hasattr(self, 'exp_table'):
            self.load_expenses_table()

    def refresh_person_filter(self):
        current = self.person_filter.currentData() or "Tümü"
        self.person_filter.blockSignals(True)
        self.person_filter.clear()
        self.person_filter.addItem("Tüm Kişiler", "Tümü")
        persons = company_expense_service.get_distinct_persons()
        for p in persons:
            self.person_filter.addItem(f"👤 {p}", p)
        idx = self.person_filter.findData(current)
        if idx >= 0:
            self.person_filter.setCurrentIndex(idx)
        else:
            self.person_filter.setCurrentIndex(0)
        self.person_filter.blockSignals(False)

    # ==================== ANA TABLO: ORTAKLAR VE TOPLAM GİDERLER ====================

    def load_persons_table(self):
        """Kişilerin ve şirket ortaklarının TOPLAM GİDERLERİNİ ana tabloda listeler"""
        search = self.person_search_input.text().strip()
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")

        self.persons_cache = company_expense_service.get_persons_summary(
            start_date=start,
            end_date=end,
            search=search
        )

        self.person_table.setRowCount(len(self.persons_cache))
        tot_all_persons = 0.0

        for row, p in enumerate(self.persons_cache):
            p_name = p.get('person_name') or "-"
            tot_amt = float(p.get('total_amount') or 0.0)
            pers_amt = float(p.get('personal_amount') or 0.0)
            comp_amt = float(p.get('company_amount') or 0.0)
            cnt = int(p.get('expense_count') or 0)
            last_d = str(p.get('last_expense_date') or "-")[:10]
            tot_all_persons += tot_amt

            # 0: Kişi / Ortak Adı
            name_item = QTableWidgetItem(f"👤 {p_name}")
            name_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            name_item.setForeground(QColor(AppStyles.CYAN))
            self.person_table.setItem(row, 0, name_item)

            # 1: İşlem Sayısı
            cnt_item = QTableWidgetItem(f"{cnt} Adet")
            cnt_item.setTextAlignment(Qt.AlignCenter)
            self.person_table.setItem(row, 1, cnt_item)

            # 2: Son İşlem Tarihi
            last_item = QTableWidgetItem(last_d)
            last_item.setTextAlignment(Qt.AlignCenter)
            self.person_table.setItem(row, 2, last_item)

            # 3: Özel / Şahsi Harcama
            pers_item = QTableWidgetItem(f"{pers_amt:,.2f} ₺")
            pers_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            pers_item.setForeground(QColor(AppStyles.PURPLE))
            self.person_table.setItem(row, 3, pers_item)

            # 4: Şirket Masrafı
            comp_item = QTableWidgetItem(f"{comp_amt:,.2f} ₺")
            comp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            comp_item.setForeground(QColor(AppStyles.PRIMARY))
            self.person_table.setItem(row, 4, comp_item)

            # 5: TOPLAM GİDER (Ana tabloda toplam gider yazar)
            tot_item = QTableWidgetItem(f"{tot_amt:,.2f} ₺")
            tot_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tot_item.setForeground(QColor(AppStyles.ORANGE))
            self.person_table.setItem(row, 5, tot_item)

            # 6: İşlemler Butonları (Detay 👁️, Gider Ekle ➕)
            act_w = QWidget()
            act_w.setStyleSheet("background: transparent;")
            a_lay = QHBoxLayout(act_w)
            a_lay.setContentsMargins(1, 1, 1, 1)
            a_lay.setSpacing(4)
            a_lay.setAlignment(Qt.AlignCenter)

            btn_open = QPushButton("👁️")
            btn_open.setToolTip("Bu kişinin tüm giderlerini açılır pencerede incele")
            btn_open.setFixedSize(36, 28)
            btn_open.setCursor(Qt.PointingHandCursor)
            btn_open.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    border-radius: 6px;
                    font-size: 11pt;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover { background-color: #0369a1; }
            """)
            btn_open.clicked.connect(lambda ch, name=p_name: self.open_person_popup(name))

            btn_quick_add = QPushButton("➕")
            btn_quick_add.setToolTip("Bu kişiye yeni bir gider / para çekimi ekle")
            btn_quick_add.setFixedSize(36, 28)
            btn_quick_add.setCursor(Qt.PointingHandCursor)
            btn_quick_add.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.GREEN};
                    color: white;
                    border-radius: 6px;
                    font-size: 10pt;
                    font-weight: bold;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #059669; }}
            """)
            btn_quick_add.clicked.connect(lambda ch, name=p_name: self.add_expense_for_person_name(name))

            a_lay.addWidget(btn_open)
            a_lay.addWidget(btn_quick_add)
            self.person_table.setCellWidget(row, 6, act_w)

        self.lbl_person_summary.setText(f"Toplam <b>{len(self.persons_cache)}</b> kişi / ortak  |  Genel Toplam Gider: <b style='color:{AppStyles.ORANGE};'>{tot_all_persons:,.2f} ₺</b>")

    def on_person_row_clicked(self, row: int, col: int = 0):
        if col == 6:  # İşlemler kolonu hariç
            return
        if 0 <= row < len(self.persons_cache):
            p_name = self.persons_cache[row].get('person_name')
            if p_name:
                self.open_person_popup(p_name)

    def show_selected_person_detail(self):
        row = self.person_table.currentRow()
        if row < 0 or row >= len(self.persons_cache):
            QMessageBox.warning(self, "Uyarı", "Lütfen listeden bir kişi veya ortak seçin!")
            return
        p_name = self.persons_cache[row].get('person_name')
        if p_name:
            self.open_person_popup(p_name)

    def add_expense_to_selected_person(self):
        row = self.person_table.currentRow()
        if 0 <= row < len(self.persons_cache):
            name = self.persons_cache[row].get('person_name')
            self.add_expense_for_person_name(name)
        else:
            self.open_add_dialog()

    def add_expense_for_person_name(self, person_name: str):
        prefill = {'person_name': person_name}
        dlg = CompanyExpenseDialog(self.user, expense=prefill, branch_id=self.branch_id, parent=self)
        dlg.is_edit = False
        dlg.expense = None
        dlg.person_combo.setCurrentText(person_name)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_person_popup(self, person_name: str):
        """Aynı kişiye ait birden fazla gideri açılır pencerede ekstra detay olarak listeler"""
        dlg = PersonExpensesDialog(self.user, person_name, branch_id=self.branch_id, parent=self)
        dlg.exec_()
        if dlg.has_changes:
            self.load_data()

    # ==================== SEKME 2: TÜM GİDER HAREKETLERİ ====================

    def load_expenses_table(self):
        search = self.search_input.text().strip()
        person = self.person_filter.currentData()
        cat = self.cat_filter.currentData()
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")

        self.expenses_cache = company_expense_service.get_expenses(
            start_date=start,
            end_date=end,
            person_name=person,
            category=cat,
            search=search
        )

        self.exp_table.setRowCount(len(self.expenses_cache))
        tot_shown = 0.0

        for row, exp in enumerate(self.expenses_cache):
            d_val = str(exp.get('expense_date') or "")[:10]
            person_name = exp.get('person_name') or "-"
            amt = float(exp.get('amount') or 0.0)
            dest = exp.get('location_destination') or "-"
            cat_name = exp.get('category') or "-"
            pay_m = exp.get('payment_method') or "Nakit"
            doc = exp.get('document_no') or "-"
            tot_shown += amt

            # 0: Tarih
            d_item = QTableWidgetItem(d_val)
            d_item.setTextAlignment(Qt.AlignCenter)
            self.exp_table.setItem(row, 0, d_item)

            # 1: Kişi / Ortak
            p_item = QTableWidgetItem(f"👤 {person_name}")
            p_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            p_item.setForeground(QColor(AppStyles.TEXT_PRIMARY))
            self.exp_table.setItem(row, 1, p_item)

            # 2: Tutar
            amt_item = QTableWidgetItem(f"{amt:,.2f} ₺")
            amt_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amt_item.setForeground(QColor(AppStyles.ORANGE))
            self.exp_table.setItem(row, 2, amt_item)

            # 3: Harcama Yeri
            dest_item = QTableWidgetItem(f"📍 {dest}")
            dest_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            dest_item.setForeground(QColor(AppStyles.CYAN))
            self.exp_table.setItem(row, 3, dest_item)

            # 4: Kategori
            cat_item = QTableWidgetItem(cat_name)
            if "Ortak" in cat_name:
                cat_item.setForeground(QColor(AppStyles.PURPLE))
            else:
                cat_item.setForeground(QColor(AppStyles.PRIMARY))
            self.exp_table.setItem(row, 4, cat_item)

            # 5: Ödeme Şekli
            pay_item = QTableWidgetItem(pay_m)
            pay_item.setTextAlignment(Qt.AlignCenter)
            self.exp_table.setItem(row, 5, pay_item)

            # 6: Belge No
            doc_item = QTableWidgetItem(doc)
            doc_item.setTextAlignment(Qt.AlignCenter)
            self.exp_table.setItem(row, 6, doc_item)

            # 7: İşlemler (Detay 👁️, Düzenle ✏️, Sil 🗑️)
            act_w = QWidget()
            act_w.setStyleSheet("background: transparent;")
            a_lay = QHBoxLayout(act_w)
            a_lay.setContentsMargins(1, 1, 1, 1)
            a_lay.setSpacing(4)
            a_lay.setAlignment(Qt.AlignCenter)

            btn_view = QPushButton("👁️")
            btn_view.setToolTip("Harcama Detayını Açılır Pencerede Gör")
            btn_view.setFixedSize(36, 28)
            btn_view.setCursor(Qt.PointingHandCursor)
            btn_view.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    border-radius: 6px;
                    font-size: 11pt;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover { background-color: #0369a1; }
            """)
            btn_view.clicked.connect(lambda ch, e=exp: self.open_detail_popup(e))

            btn_edit = QPushButton("✏️")
            btn_edit.setToolTip("Harcamayı Düzenle")
            btn_edit.setFixedSize(36, 28)
            btn_edit.setCursor(Qt.PointingHandCursor)
            btn_edit.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.ORANGE};
                    color: white;
                    border-radius: 6px;
                    font-size: 11pt;
                    font-weight: bold;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #d97706; }}
            """)
            btn_edit.clicked.connect(lambda ch, e=exp: self.open_edit_dialog(e))

            btn_del = QPushButton("🗑️")
            btn_del.setToolTip("Harcamayı Sil")
            btn_del.setFixedSize(36, 28)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AppStyles.RED};
                    color: white;
                    border-radius: 6px;
                    font-size: 11pt;
                    font-weight: bold;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #dc2626; }}
            """)
            btn_del.clicked.connect(lambda ch, e=exp: self.delete_expense(e))

            a_lay.addWidget(btn_view)
            a_lay.addWidget(btn_edit)
            a_lay.addWidget(btn_del)
            self.exp_table.setCellWidget(row, 7, act_w)

        self.lbl_exp_summary.setText(f"Toplam <b>{len(self.expenses_cache)}</b> gider listelendi | Listelenen Tutar: <b style='color:{AppStyles.ORANGE};'>{tot_shown:,.2f} ₺</b>")

    def on_expense_row_clicked(self, row: int, col: int = 0):
        if col == 7:
            return
        if 0 <= row < len(self.expenses_cache):
            self.open_detail_popup(self.expenses_cache[row])

    def show_selected_expense_detail(self):
        row = self.exp_table.currentRow()
        if row < 0 or row >= len(self.expenses_cache):
            QMessageBox.warning(self, "Uyarı", "Lütfen bir harcama satırı seçin!")
            return
        self.open_detail_popup(self.expenses_cache[row])

    def edit_selected_expense(self):
        row = self.exp_table.currentRow()
        if row < 0 or row >= len(self.expenses_cache):
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek için bir harcama seçin!")
            return
        self.open_edit_dialog(self.expenses_cache[row])

    def delete_selected_expense(self):
        row = self.exp_table.currentRow()
        if row < 0 or row >= len(self.expenses_cache):
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir harcama seçin!")
            return
        self.delete_expense(self.expenses_cache[row])

    def open_detail_popup(self, exp: Dict):
        full_exp = company_expense_service.get_expense(exp['id']) or exp
        dlg = ExpenseDetailDialog(self.user, full_exp, parent=self)
        dlg.exec_()
        if dlg.is_deleted or dlg.is_updated:
            self.load_data()

    # ==================== DİALOGLAR & AKSİYONLAR ====================

    def open_add_dialog(self):
        dlg = CompanyExpenseDialog(self.user, branch_id=self.branch_id, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def open_edit_dialog(self, exp: Dict):
        full_exp = company_expense_service.get_expense(exp['id']) or exp
        dlg = CompanyExpenseDialog(self.user, expense=full_exp, branch_id=self.branch_id, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def delete_expense(self, exp: Dict):
        p_name = exp.get('person_name', 'Ortak')
        amt = float(exp.get('amount', 0.0))
        dest = exp.get('location_destination') or 'Harcama'

        reply = QMessageBox.question(
            self,
            "Harcama Kaydını Sil",
            f"<b>{p_name}</b> adına kayıtlı <b>{amt:,.2f} ₺</b> tutarındaki harcamayı silmek istediğinize emin misiniz?<br><br>"
            f"<b>Harcama Yeri:</b> {dest}<br><br>"
            f"⚠️ <i>Bu işlem geri alınamaz.</i>",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = company_expense_service.delete_expense(exp['id'], user_id=getattr(self.user, 'id', None))
            if success:
                QMessageBox.information(self, "Başarılı", msg)
                self.load_data()
            else:
                QMessageBox.critical(self, "Hata", msg)

    def export_current_tab(self):
        current_tab_idx = self.tab_widget.currentIndex()
        if current_tab_idx == 0 or not hasattr(self, 'exp_table'):
            self.export_persons_to_excel()
        else:
            self.export_expenses_to_excel()

    def export_persons_to_excel(self):
        if not self.persons_cache:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak kişi özeti bulunamadı.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel Olarak Kaydet", f"Ortaklar_Toplam_Giderler_{datetime.now().strftime('%Y%m%d')}.xlsx", "Excel Dosyaları (*.xlsx)"
        )
        if not file_path:
            return

        try:
            data = []
            for p in self.persons_cache:
                data.append({
                    "Kişi / Ortak": p.get('person_name'),
                    "İşlem Sayısı": int(p.get('expense_count') or 0),
                    "Son İşlem Tarihi": str(p.get('last_expense_date') or ""),
                    "Özel / Şahsi (₺)": float(p.get('personal_amount') or 0.0),
                    "Şirket Masrafı (₺)": float(p.get('company_amount') or 0.0),
                    "Toplam Gider (₺)": float(p.get('total_amount') or 0.0)
                })
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)
            QMessageBox.information(self, "Başarılı", f"Kişi ve ortaklar toplam giderleri başarıyla Excel'e aktarıldı:\n{file_path}")
        except Exception as e:
            logger.error(f"Excel aktarım hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Excel kaydedilirken hata oluştu:\n{str(e)}")

    def export_expenses_to_excel(self):
        if not self.expenses_cache:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak harcama kaydı bulunamadı.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel Olarak Kaydet", f"Sirket_Ortak_Giderleri_{datetime.now().strftime('%Y%m%d')}.xlsx", "Excel Dosyaları (*.xlsx)"
        )
        if not file_path:
            return

        try:
            data = []
            for e in self.expenses_cache:
                data.append({
                    "Tarih": str(e.get('expense_date')),
                    "Kişi / Ortak": e.get('person_name'),
                    "Tutar (₺)": float(e.get('amount') or 0.0),
                    "Harcama Yeri": e.get('location_destination') or "",
                    "Kategori": e.get('category') or "",
                    "Ödeme Şekli": e.get('payment_method') or "",
                    "Belge No": e.get('document_no') or "",
                    "Açıklama": e.get('description') or "",
                    "Kaydeden": e.get('created_by_name') or ""
                })
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)
            QMessageBox.information(self, "Başarılı", f"Harcama listesi başarıyla Excel dosyasına kaydedildi:\n{file_path}")
        except Exception as e:
            logger.error(f"Excel aktarım hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Excel kaydedilirken hata oluştu:\n{str(e)}")
