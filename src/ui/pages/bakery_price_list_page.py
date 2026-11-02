# src/ui/pages/bakery_price_list_page.py
"""
İmalathane Özel Fiyat Listesi Yönetim Sayfası
Şubelere Veriliş (İç Transfer) ve Dış Müşterilere (Toptan/Perakende) Veriliş Fiyatları
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox, QMessageBox,
    QDialog, QDialogButtonBox, QDoubleSpinBox, QTextEdit, QHeaderView,
    QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from datetime import datetime

from ...core.database import db
from ...core.logger import logger
from ...models.user import User
from ..styles import AppStyles


class PriceItemDialog(QDialog):
    """Fiyat listesine yeni ürün ekleme veya düzenleme penceresi"""

    def __init__(self, parent=None, item_id: int = None):
        super().__init__(parent)
        self.item_id = item_id
        self.setWindowTitle("Yeni Fiyat Tanımı" if not item_id else "Fiyat Tanımını Düzenle")
        self.setMinimumWidth(440)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; font-weight: 500; }}
            QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10pt;
            }}
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{
                border-color: {AppStyles.PRIMARY};
            }}
        """)
        self.init_ui()
        if item_id:
            self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("🏷️ " + ("Yeni Fiyat Tanımı" if not self.item_id else "Fiyat Düzenle"))
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        layout.addWidget(title)

        layout.addWidget(QLabel("Ürün Adı *"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: Somun Ekmek (250g), Simit, Poğaça...")
        layout.addWidget(self.name_input)

        cat_lay = QHBoxLayout()
        v1 = QVBoxLayout()
        v1.addWidget(QLabel("Kategori"))
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["Ekmek", "Simit & Poğaça", "Unlu Mamül", "Börek", "Tatlı", "Pasta", "Diğer"])
        self.cat_combo.setEditable(True)
        v1.addWidget(self.cat_combo)
        cat_lay.addLayout(v1)

        v2 = QVBoxLayout()
        v2.addWidget(QLabel("Birim"))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["Adet", "kg", "Tepsi", "Koli", "Porsiyon"])
        self.unit_combo.setEditable(True)
        v2.addWidget(self.unit_combo)
        cat_lay.addLayout(v2)
        layout.addLayout(cat_lay)

        # Fiyatlar
        price_box = QFrame()
        price_box.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_DARK};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        pb_lay = QVBoxLayout(price_box)
        pb_lay.setSpacing(8)

        # 1. Şubelere Veriliş Fiyatı
        p1_lay = QHBoxLayout()
        lbl1 = QLabel("🏢 Şubelere Veriliş Fiyatı:")
        lbl1.setStyleSheet("color: #34d399; font-weight: bold;")
        p1_lay.addWidget(lbl1, 2)
        self.branch_price_spin = QDoubleSpinBox()
        self.branch_price_spin.setRange(0, 999999.99)
        self.branch_price_spin.setDecimals(2)
        self.branch_price_spin.setPrefix("₺ ")
        self.branch_price_spin.setFixedHeight(34)
        p1_lay.addWidget(self.branch_price_spin, 3)
        pb_lay.addLayout(p1_lay)

        # 2. Dış Müşterilere Veriliş Fiyatı
        p2_lay = QHBoxLayout()
        lbl2 = QLabel("👥 Dış Müşteri / Toptan:")
        lbl2.setStyleSheet("color: #fbbf24; font-weight: bold;")
        p2_lay.addWidget(lbl2, 2)
        self.customer_price_spin = QDoubleSpinBox()
        self.customer_price_spin.setRange(0, 999999.99)
        self.customer_price_spin.setDecimals(2)
        self.customer_price_spin.setPrefix("₺ ")
        self.customer_price_spin.setFixedHeight(34)
        p2_lay.addWidget(self.customer_price_spin, 3)
        pb_lay.addLayout(p2_lay)

        layout.addWidget(price_box)

        layout.addWidget(QLabel("Açıklama / Reçete Notu (Opsiyonel)"))
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Örn: Taş fırın pişirim, 50 adet altı verilmez vb.")
        layout.addWidget(self.notes_input)

        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Save).setText("💾 Kaydet")
        btn_box.button(QDialogButtonBox.Cancel).setText("❌ İptal")
        btn_box.accepted.connect(self.save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def load_data(self):
        try:
            res = db.fetch_one("SELECT * FROM BakeryPriceList WHERE id = %s", (self.item_id,))
            if res:
                self.name_input.setText(res.get('product_name', ''))
                self.cat_combo.setCurrentText(res.get('category', 'Genel'))
                self.unit_combo.setCurrentText(res.get('unit', 'Adet'))
                self.branch_price_spin.setValue(float(res.get('branch_price', 0)))
                self.customer_price_spin.setValue(float(res.get('customer_price', 0)))
                self.notes_input.setText(res.get('notes', '') or '')
        except Exception as e:
            logger.error(f"Fiyat detayı yükleme hatası: {e}")

    def save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Uyarı", "Lütfen ürün adını giriniz!")
            return

        cat = self.cat_combo.currentText().strip() or "Genel"
        unit = self.unit_combo.currentText().strip() or "Adet"
        bp = self.branch_price_spin.value()
        cp = self.customer_price_spin.value()
        notes = self.notes_input.text().strip()

        try:
            if not self.item_id:
                db.execute_query("""
                    INSERT INTO BakeryPriceList (product_name, category, unit, branch_price, customer_price, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (name, cat, unit, bp, cp, notes))
            else:
                db.execute_query("""
                    UPDATE BakeryPriceList 
                    SET product_name = %s, category = %s, unit = %s, branch_price = %s, customer_price = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (name, cat, unit, bp, cp, notes, self.item_id))

            self.accept()
        except Exception as e:
            logger.error(f"Fiyat kaydetme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Kaydedilemedi:\n{e}")


class BatchPriceUpdateDialog(QDialog):
    """Toplu Yüzdelik Fiyat Güncelleme (Zam / İndirim)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Toplu Fiyat Güncelle (% Zam / İndirim)")
        self.setMinimumWidth(380)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {AppStyles.BG_MEDIUM}; color: {AppStyles.TEXT_PRIMARY}; }}
            QLabel {{ color: {AppStyles.TEXT_PRIMARY}; font-size: 10pt; }}
            QComboBox, QDoubleSpinBox {{
                background-color: {AppStyles.BG_DARK};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10.5pt;
                font-weight: bold;
            }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("🔢 Yüzdelik Toplu Fiyat Revizesi")
        title.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {AppStyles.PRIMARY};")
        layout.addWidget(title)

        layout.addWidget(QLabel("Uygulanacak Fiyat Türü:"))
        self.target_combo = QComboBox()
        self.target_combo.addItems([
            "🏢 Sadece Şube Fiyatlarına",
            "👥 Sadece Dış Müşteri Fiyatlarına",
            "✨ Her İki Fiyata Da (Şube + Müşteri)"
        ])
        layout.addWidget(self.target_combo)

        layout.addWidget(QLabel("Değişim Oranı (%):"))
        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(-90.0, 500.0)
        self.rate_spin.setDecimals(1)
        self.rate_spin.setValue(10.0)
        self.rate_spin.setSuffix(" %")
        layout.addWidget(self.rate_spin)

        info = QLabel("💡 Örnek: %10 girerseniz fiyatlar %10 artar. -%5 girerseniz %5 indirim yapılır.")
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 8.5pt;")
        layout.addWidget(info)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Ok).setText("⚡ Güncellemeyi Uygula")
        btn_box.button(QDialogButtonBox.Cancel).setText("İptal")
        btn_box.accepted.connect(self.apply_update)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def apply_update(self):
        rate = self.rate_spin.value()
        multiplier = 1.0 + (rate / 100.0)
        t_idx = self.target_combo.currentIndex()

        try:
            if t_idx == 0:
                db.execute_query("UPDATE BakeryPriceList SET branch_price = ROUND(branch_price * %s, 2), updated_at = CURRENT_TIMESTAMP WHERE is_active = TRUE", (multiplier,))
            elif t_idx == 1:
                db.execute_query("UPDATE BakeryPriceList SET customer_price = ROUND(customer_price * %s, 2), updated_at = CURRENT_TIMESTAMP WHERE is_active = TRUE", (multiplier,))
            else:
                db.execute_query("UPDATE BakeryPriceList SET branch_price = ROUND(branch_price * %s, 2), customer_price = ROUND(customer_price * %s, 2), updated_at = CURRENT_TIMESTAMP WHERE is_active = TRUE", (multiplier, multiplier))

            QMessageBox.information(self, "Başarılı", f"Fiyatlar %{rate:g} oranında güncellendi!")
            self.accept()
        except Exception as e:
            logger.error(f"Toplu fiyat güncelleme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Güncelleme yapılamadı:\n{e}")


class BakeryPriceListPage(QWidget):
    """İmalathane Özel Fiyat Listesi Ekranı"""

    def __init__(self, user: User, branch_id: int, main_window=None):
        super().__init__()
        self.user = user
        self.branch_id = branch_id
        self.main_window = main_window

        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setObjectName("BakeryPriceListPage")
        self.setStyleSheet(f"#BakeryPriceListPage {{ background-color: {AppStyles.BG_DARK}; }}")

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # Üst Başlık Barı
        top_bar = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(2)

        title = QLabel("🏷️ İmalathane Özel Fiyat Listesi")
        title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        left.addWidget(title)

        sub = QLabel("Şubelere transfer fiyatları ve dış toptan müşterilere özel çift kademeli fiyat listesi")
        sub.setStyleSheet(f"font-size: 10pt; color: {AppStyles.TEXT_SECONDARY};")
        left.addWidget(sub)
        top_bar.addLayout(left)
        top_bar.addStretch()

        batch_btn = QPushButton("🔢 Toplu % Fiyat Güncelle")
        batch_btn.setCursor(Qt.PointingHandCursor)
        batch_btn.setFixedHeight(36)
        batch_btn.clicked.connect(self.open_batch_dialog)
        batch_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.CYAN};
                border: 1px solid {AppStyles.CYAN};
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.CYAN};
                color: white;
            }}
        """)
        top_bar.addWidget(batch_btn)

        add_btn = QPushButton("➕ Yeni Ürün / Fiyat Ekle")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFixedHeight(36)
        add_btn.clicked.connect(self.add_item)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.PRIMARY}, stop:1 {AppStyles.CYAN});
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 9.5pt;
                padding: 4px 16px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppStyles.CYAN}, stop:1 {AppStyles.PRIMARY});
            }}
        """)
        top_bar.addWidget(add_btn)

        layout.addLayout(top_bar)

        # 4 KPI Gösterge Kartı
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(12)

        self.kpi_count = self._create_card("🏷️", "Toplam Çeşit", "0 Ürün", AppStyles.CYAN)
        self.kpi_avg_branch = self._create_card("🏢", "Ort. Şube Fiyatı", "0.00 ₺", AppStyles.GREEN)
        self.kpi_avg_cust = self._create_card("👥", "Ort. Müşteri Fiyatı", "0.00 ₺", AppStyles.ORANGE)
        self.kpi_avg_margin = self._create_card("📈", "Ortalama Marj", "%0.0", AppStyles.PURPLE)

        kpi_layout.addWidget(self.kpi_count)
        kpi_layout.addWidget(self.kpi_avg_branch)
        kpi_layout.addWidget(self.kpi_avg_cust)
        kpi_layout.addWidget(self.kpi_avg_margin)
        layout.addLayout(kpi_layout)

        # Filtre Barı
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Ürün adı veya kategori ara...")
        self.search_input.setFixedHeight(36)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 10pt;
            }}
            QLineEdit:focus {{ border-color: {AppStyles.PRIMARY}; }}
        """)
        self.search_input.textChanged.connect(self.load_data)
        filter_bar.addWidget(self.search_input, 3)

        self.category_combo = QComboBox()
        self.category_combo.addItems(["Tüm Kategoriler", "Ekmek", "Simit & Poğaça", "Unlu Mamül", "Börek", "Tatlı", "Pasta", "Diğer"])
        self.category_combo.setFixedHeight(36)
        self.category_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
        """)
        self.category_combo.currentTextChanged.connect(self.load_data)
        filter_bar.addWidget(self.category_combo, 1)

        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setFixedHeight(36)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.BG_MEDIUM};
                color: {AppStyles.TEXT_PRIMARY};
                border: 1px solid {AppStyles.BORDER};
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: 600;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{ background-color: {AppStyles.BG_LIGHT}; }}
        """)
        filter_bar.addWidget(refresh_btn)
        layout.addLayout(filter_bar)

        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            'Ürün Adı', 'Kategori', 'Birim', '🏢 Şube Veriliş Fiyatı',
            '👥 Dış Müşteri Fiyatı', 'Fiyat Farkı / Marj', 'Son Güncelleme', 'Notlar'
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setVisible(True)
        self.table.horizontalHeader().setFixedHeight(38)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemDoubleClicked.connect(self.edit_item)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                border: 1px solid {AppStyles.BORDER};
                border-radius: 8px;
                gridline-color: {AppStyles.BORDER};
                color: {AppStyles.TEXT_PRIMARY};
            }}
            QTableWidget::item {{ padding: 8px 10px; border: none; font-size: 10pt; }}
            QTableWidget::item:selected {{ background-color: {AppStyles.PRIMARY}30; }}
            QHeaderView {{ background-color: {AppStyles.BG_DARKEST}; border: none; }}
            QHeaderView::section {{
                background-color: {AppStyles.BG_DARKEST};
                color: #FFFFFF;
                padding: 0 10px;
                border: none;
                border-bottom: 2px solid {AppStyles.PRIMARY};
                font-weight: bold;
                font-size: 9.5pt;
                height: 38px;
            }}
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        # Boş Durum
        self.empty_box = QFrame()
        self.empty_box.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px dashed {AppStyles.BORDER};
                border-radius: 10px;
                padding: 40px 20px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        eb_lay = QVBoxLayout(self.empty_box)
        eb_lay.setAlignment(Qt.AlignCenter)
        eb_lay.setSpacing(6)
        ic = QLabel("🏷️")
        ic.setStyleSheet("font-size: 32pt;")
        eb_lay.addWidget(ic)
        t_lbl = QLabel("Fiyat Listesinde Ürün Bulunmuyor")
        t_lbl.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {AppStyles.TEXT_PRIMARY};")
        eb_lay.addWidget(t_lbl)
        s_lbl = QLabel("Yukarıdaki '➕ Yeni Ürün / Fiyat Ekle' butonunu kullanarak şube ve müşteri fiyatlarını tanımlayabilirsiniz.")
        s_lbl.setStyleSheet(f"font-size: 9.5pt; color: {AppStyles.TEXT_MUTED};")
        eb_lay.addWidget(s_lbl)
        self.empty_box.hide()
        layout.addWidget(self.empty_box)

        # Alt Butonlar
        bot_lay = QHBoxLayout()
        self.total_lbl = QLabel("Toplam: 0 fiyat kaydı")
        self.total_lbl.setStyleSheet(f"color: {AppStyles.TEXT_SECONDARY}; font-size: 10pt;")
        bot_lay.addWidget(self.total_lbl)
        bot_lay.addStretch()

        edit_btn = QPushButton("✏️ Düzenle")
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.setFixedHeight(34)
        edit_btn.clicked.connect(self.edit_item)
        edit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.ORANGE};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 16px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{ background-color: #d97706; }}
        """)
        bot_lay.addWidget(edit_btn)

        del_btn = QPushButton("🗑️ Sil")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setFixedHeight(34)
        del_btn.clicked.connect(self.delete_item)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AppStyles.RED};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 16px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{ background-color: #dc2626; }}
        """)
        bot_lay.addWidget(del_btn)

        layout.addLayout(bot_lay)

    def _create_card(self, icon: str, title: str, val: str, color: str) -> QFrame:
        card = QFrame()
        card.setFixedHeight(82)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AppStyles.BG_MEDIUM};
                border: 1px solid {AppStyles.BORDER};
                border-left: 4px solid {color};
                border-radius: 8px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        lay = QVBoxLayout(card)
        lay.setSpacing(4)
        lay.setContentsMargins(14, 10, 14, 10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        i_lbl = QLabel(icon)
        i_lbl.setStyleSheet("font-size: 11pt;")
        top_row.addWidget(i_lbl)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 9.5pt; color: {AppStyles.TEXT_SECONDARY}; font-weight: 600;")
        top_row.addWidget(t_lbl)
        top_row.addStretch()
        lay.addLayout(top_row)

        v_lbl = QLabel(val)
        v_lbl.setObjectName("cardVal")
        v_lbl.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {color};")
        lay.addWidget(v_lbl)
        return card

    def load_data(self):
        try:
            search = self.search_input.text().strip()
            cat = self.category_combo.currentText() if hasattr(self, 'category_combo') else "Tüm Kategoriler"

            query = "SELECT * FROM BakeryPriceList WHERE is_active = TRUE"
            params = []

            if search:
                query += " AND (product_name ILIKE %s OR category ILIKE %s)"
                params.extend([f"%{search}%", f"%{search}%"])

            if cat and not cat.startswith("Tüm"):
                query += " AND category = %s"
                params.append(cat)

            query += " ORDER BY category ASC, product_name ASC"
            items = db.fetch_all(query, tuple(params))

            self.table.setRowCount(0)
            tot_branch = 0.0
            tot_cust = 0.0

            for i, row in enumerate(items or []):
                self.table.insertRow(i)

                bp = float(row.get('branch_price', 0))
                cp = float(row.get('customer_price', 0))
                tot_branch += bp
                tot_cust += cp
                diff = cp - bp
                margin = ((diff / bp) * 100.0) if bp > 0 else 0.0

                unit = row.get('unit', 'Adet')

                # Col 0: Ürün Adı
                self.table.setItem(i, 0, QTableWidgetItem(str(row.get('product_name', ''))))
                # Col 1: Kategori
                self.table.setItem(i, 1, QTableWidgetItem(str(row.get('category', 'Genel'))))
                # Col 2: Birim
                self.table.setItem(i, 2, QTableWidgetItem(unit))

                # Col 3: Şube Veriliş Fiyatı
                bp_item = QTableWidgetItem(f"{bp:,.2f} ₺")
                bp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                bp_item.setForeground(QColor(AppStyles.GREEN))
                bp_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                self.table.setItem(i, 3, bp_item)

                # Col 4: Müşteri Veriliş Fiyatı
                cp_item = QTableWidgetItem(f"{cp:,.2f} ₺")
                cp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                cp_item.setForeground(QColor(AppStyles.YELLOW))
                cp_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                self.table.setItem(i, 4, cp_item)

                # Col 5: Fark & Marj
                diff_text = f"+{diff:,.2f} ₺ (%{margin:.1f})" if diff >= 0 else f"{diff:,.2f} ₺ (%{margin:.1f})"
                diff_item = QTableWidgetItem(diff_text)
                diff_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                diff_item.setForeground(QColor(AppStyles.CYAN if diff >= 0 else AppStyles.RED))
                self.table.setItem(i, 5, diff_item)

                # Col 6: Güncelleme
                u_date = str(row.get('updated_at', ''))[:16]
                self.table.setItem(i, 6, QTableWidgetItem(u_date))

                # Col 7: Notlar
                self.table.setItem(i, 7, QTableWidgetItem(str(row.get('notes') or '')))

                self.table.item(i, 0).setData(Qt.UserRole, row.get('id'))

            count = len(items or [])
            self.total_lbl.setText(f"Toplam: {count} fiyat tanımı listelendi")

            # Empty state
            if count == 0:
                self.table.hide()
                self.empty_box.show()
            else:
                self.table.show()
                self.empty_box.hide()

            # KPI Kartlarını güncelle
            c1 = self.kpi_count.findChild(QLabel, "cardVal")
            if c1: c1.setText(f"{count} Çeşit")

            c2 = self.kpi_avg_branch.findChild(QLabel, "cardVal")
            avg_b = (tot_branch / count) if count > 0 else 0.0
            if c2: c2.setText(f"{avg_b:,.2f} ₺")

            c3 = self.kpi_avg_cust.findChild(QLabel, "cardVal")
            avg_c = (tot_cust / count) if count > 0 else 0.0
            if c3: c3.setText(f"{avg_c:,.2f} ₺")

            c4 = self.kpi_avg_margin.findChild(QLabel, "cardVal")
            overall_margin = (((avg_c - avg_b) / avg_b) * 100.0) if avg_b > 0 else 0.0
            if c4: c4.setText(f"%{overall_margin:.1f}")

        except Exception as e:
            logger.error(f"Fiyat listesi yükleme hatası: {e}")

    def add_item(self):
        dlg = PriceItemDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def edit_item(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek istediğiniz ürünü seçin!")
            return

        item_id = self.table.item(row, 0).data(Qt.UserRole)
        dlg = PriceItemDialog(self, item_id=item_id)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()

    def delete_item(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz ürünü seçin!")
            return

        item_id = self.table.item(row, 0).data(Qt.UserRole)
        p_name = self.table.item(row, 0).text()

        res = QMessageBox.question(
            self, "Silme Onayı",
            f"'{p_name}' ürününü fiyat listesinden kaldırmak istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if res == QMessageBox.Yes:
            try:
                db.execute_query("UPDATE BakeryPriceList SET is_active = FALSE WHERE id = %s", (item_id,))
                self.load_data()
            except Exception as e:
                logger.error(f"Fiyat silme hatası: {e}")
                QMessageBox.critical(self, "Hata", f"Silinemedi:\n{e}")

    def open_batch_dialog(self):
        dlg = BatchPriceUpdateDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self.load_data()
