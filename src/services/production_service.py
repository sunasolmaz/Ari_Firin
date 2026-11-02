# src/services/production_service.py
"""
Fırın İmalathane & Üretim Yönetim Servisi
- Günlük fırın üretimi (Ekmek, Simit, Poğaça, Pasta, Tatlı)
- 3 Şubeye iç sevkiyat ve dağıtım (Armada, Çobançeşme, Rumeli)
- Dış müşterilere toptan satış yönetimi (Market, Restoran, Otel)
- Hammadde ve mamul stok takibi
"""

import uuid
import calendar
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Tuple, Optional, Any
from ..core.database import db
from ..core.logger import logger
from ..core.decimal_utils import to_decimal, round_currency, round_quantity


class ProductionService:
    """İmalathane, Üretim, Şube Sevkiyatı ve Dış Satış Servisi"""

    def __init__(self):
        self._ensured_tenants = set()
        try:
            self.ensure_tables()
        except Exception as e:
            logger.warning(f"ProductionService tablo başlatma uyarısı: {e}")

    # ==================== VERİTABANI TABLOLARI ====================

    def ensure_tables(self):
        """İmalathane şubesi ve üretim/sevkiyat tablolarını hazırlar"""
        # Multi-Tenant: public şemasında veya seçili tenant yokken işletme tabloları aranmaz
        tenant = db.get_tenant()
        if not tenant or tenant == 'public':
            return

        if getattr(self, '_ensured_tenants', None) is not None and tenant in self._ensured_tenants:
            return

        try:
            if hasattr(db, 'ensure_production_tables'):
                db.ensure_production_tables(tenant)
                if not hasattr(self, '_ensured_tenants'):
                    self._ensured_tenants = set()
                self._ensured_tenants.add(tenant)
                return

            with db.transaction():
                # 1. İmalathane Şubesini Branches tablosunda garanti et
                row = db.fetch_one("SELECT id FROM Branches WHERE LOWER(name) LIKE %s", ('%imalat%',))
                if not row:
                    db.execute_query("""
                        INSERT INTO Branches (name, city, address, is_active)
                        VALUES ('İmalathane', 'Tekirdağ', 'Çorlu Üretim & Fırın İmalat Merkezi', TRUE)
                    """)

                # 2. Üretim Tablosu
                db.execute_query("""
                    CREATE TABLE IF NOT EXISTS BakeryProductions (
                        id SERIAL PRIMARY KEY,
                        branch_id INTEGER REFERENCES Branches(id) ON DELETE SET NULL,
                        production_date DATE NOT NULL DEFAULT CURRENT_DATE,
                        product_name VARCHAR(200) NOT NULL,
                        category VARCHAR(50) DEFAULT 'Ekmek',
                        unit VARCHAR(30) DEFAULT 'Adet',
                        quantity DECIMAL(15,2) NOT NULL,
                        unit_cost DECIMAL(15,2) DEFAULT 0,
                        sale_price DECIMAL(15,2) DEFAULT 0,
                        shipped_quantity DECIMAL(15,2) DEFAULT 0,
                        external_sold_quantity DECIMAL(15,2) DEFAULT 0,
                        remaining_quantity DECIMAL(15,2) DEFAULT 0,
                        notes TEXT,
                        created_by INTEGER REFERENCES Users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 3. Şubelere Sevkiyat Tablosu (Armada, Çobançeşme, Rumeli)
                db.execute_query("""
                    CREATE TABLE IF NOT EXISTS BranchShipments (
                        id SERIAL PRIMARY KEY,
                        shipment_no VARCHAR(50) UNIQUE,
                        source_branch_id INTEGER REFERENCES Branches(id),
                        target_branch_id INTEGER REFERENCES Branches(id),
                        shipment_date DATE NOT NULL DEFAULT CURRENT_DATE,
                        product_name VARCHAR(200) NOT NULL,
                        quantity DECIMAL(15,2) NOT NULL,
                        unit VARCHAR(30) DEFAULT 'Adet',
                        unit_price DECIMAL(15,2) DEFAULT 0,
                        total_amount DECIMAL(15,2) DEFAULT 0,
                        status VARCHAR(30) DEFAULT 'Teslim Edildi',
                        driver_notes TEXT,
                        created_by INTEGER REFERENCES Users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 4. Dış Müşterilere Toptan Satış Tablosu
                db.execute_query("""
                    CREATE TABLE IF NOT EXISTS ExternalSales (
                        id SERIAL PRIMARY KEY,
                        sale_no VARCHAR(50) UNIQUE,
                        sale_date DATE NOT NULL DEFAULT CURRENT_DATE,
                        customer_id INTEGER REFERENCES Customers(id) ON DELETE SET NULL,
                        customer_name VARCHAR(200) NOT NULL,
                        product_name VARCHAR(200) NOT NULL,
                        quantity DECIMAL(15,2) NOT NULL,
                        unit VARCHAR(30) DEFAULT 'Adet',
                        unit_price DECIMAL(15,2) DEFAULT 0,
                        total_amount DECIMAL(15,2) DEFAULT 0,
                        payment_method VARCHAR(50) DEFAULT 'Nakit',
                        payment_status VARCHAR(30) DEFAULT 'Paid',
                        notes TEXT,
                        created_by INTEGER REFERENCES Users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 3b. Şubelere Sevkiyat Kalemleri Tablosu (Çoklu Kalem Desteği)
                db.execute_query("""
                    CREATE TABLE IF NOT EXISTS BranchShipmentItems (
                        id SERIAL PRIMARY KEY,
                        shipment_id INTEGER REFERENCES BranchShipments(id) ON DELETE CASCADE,
                        product_name VARCHAR(200) NOT NULL,
                        category VARCHAR(50) DEFAULT 'Unlu Mamül',
                        quantity DECIMAL(15,2) NOT NULL,
                        unit VARCHAR(30) DEFAULT 'Adet',
                        unit_price DECIMAL(15,2) DEFAULT 0,
                        total_amount DECIMAL(15,2) DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 4b. Dış Müşterilere Satış Kalemleri Tablosu (Çoklu Kalem Desteği)
                db.execute_query("""
                    CREATE TABLE IF NOT EXISTS ExternalSaleItems (
                        id SERIAL PRIMARY KEY,
                        sale_id INTEGER REFERENCES ExternalSales(id) ON DELETE CASCADE,
                        product_name VARCHAR(200) NOT NULL,
                        category VARCHAR(50) DEFAULT 'Unlu Mamül',
                        quantity DECIMAL(15,2) NOT NULL,
                        unit VARCHAR(30) DEFAULT 'Adet',
                        unit_price DECIMAL(15,2) DEFAULT 0,
                        total_amount DECIMAL(15,2) DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # İndeksler
                db.execute_query("""
                    CREATE INDEX IF NOT EXISTS idx_bp_date ON BakeryProductions(production_date);
                    CREATE INDEX IF NOT EXISTS idx_bs_target ON BranchShipments(target_branch_id, shipment_date);
                    CREATE INDEX IF NOT EXISTS idx_es_date ON ExternalSales(sale_date);
                    CREATE INDEX IF NOT EXISTS idx_bsi_shipment ON BranchShipmentItems(shipment_id);
                    CREATE INDEX IF NOT EXISTS idx_esi_sale ON ExternalSaleItems(sale_id);
                """)
            if not hasattr(self, '_ensured_tenants'):
                self._ensured_tenants = set()
            self._ensured_tenants.add(tenant)
        except Exception as e:
            logger.error(f"ensure_tables hatası: {e}")

    def get_production_branch(self) -> Optional[Dict]:
        """İmalathane şube kaydını getirir"""
        try:
            return db.fetch_one("SELECT * FROM Branches WHERE LOWER(name) LIKE %s LIMIT 1", ('%imalat%',))
        except Exception:
            return None

    def get_production_branch_id(self) -> int:
        """İmalathane şube ID'sini döndürür"""
        b = self.get_production_branch()
        return b['id'] if b else 1

    def get_retail_branches(self) -> List[Dict]:
        """3 Perakende Satış Şubesini (Armada, Çobançeşme, Rumeli) döndürür"""
        try:
            return db.fetch_all("""
                SELECT id, name, city, address 
                FROM Branches 
                WHERE is_active = TRUE AND LOWER(name) NOT LIKE %s
                ORDER BY id ASC
            """, ('%imalat%',))
        except Exception as e:
            logger.error(f"get_retail_branches hatası: {e}")
            return []

    # ==================== 1. ÜRETİM YÖNETİMİ ====================

    def add_production(self, data: Dict, user_id: Optional[int] = None) -> Tuple[bool, str, Optional[int]]:
        """Yeni bir üretim partisi kaydeder"""
        self.ensure_tables()
        try:
            p_name = (data.get('product_name') or '').strip()
            if not p_name:
                return False, "Ürün adı boş bırakılamaz!", None

            qty = float(to_decimal(data.get('quantity', 0)))
            if qty <= 0:
                return False, "Üretim miktarı 0'dan büyük olmalıdır!", None

            p_branch_id = self.get_production_branch_id()
            p_date = data.get('production_date') or datetime.now().date().strftime('%Y-%m-%d')
            cat = data.get('category', 'Ekmek')
            unit = data.get('unit', 'Adet')
            cost = float(to_decimal(data.get('unit_cost', 0)))
            price = float(to_decimal(data.get('sale_price', 0)))
            notes = (data.get('notes') or '').strip()

            new_id = db.execute_query("""
                INSERT INTO BakeryProductions (
                    branch_id, production_date, product_name, category, unit,
                    quantity, unit_cost, sale_price, shipped_quantity,
                    external_sold_quantity, remaining_quantity, notes, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, 0,
                    0, %s, %s, %s
                ) RETURNING id
            """, (
                p_branch_id, p_date, p_name, cat, unit,
                qty, cost, price, qty, notes, user_id
            ))

            logger.info(f"🍞 Yeni üretim kaydedildi: {qty} {unit} {p_name} (ID: {new_id})")
            return True, f"Üretim kaydedildi: {qty} {unit} {p_name}", new_id
        except Exception as e:
            logger.error(f"add_production hatası: {e}")
            return False, f"Üretim kaydedilemedi: {str(e)}", None

    def get_productions(self, target_date: Optional[str] = None, category: Optional[str] = None) -> List[Dict]:
        """Üretim kayıtlarını listeler"""
        self.ensure_tables()
        try:
            sql = "SELECT * FROM BakeryProductions WHERE 1=1"
            params = []
            if target_date:
                sql += " AND production_date = %s"
                params.append(target_date)
            if category and category != 'Tümü':
                sql += " AND category = %s"
                params.append(category)
            sql += " ORDER BY production_date DESC, id DESC"
            return db.fetch_all(sql, tuple(params)) if params else db.fetch_all(sql)
        except Exception as e:
            logger.error(f"get_productions hatası: {e}")
            return []

    def delete_production(self, prod_id: int) -> Tuple[bool, str]:
        """Üretim kaydını siler"""
        try:
            rowcount = db.execute_query("DELETE FROM BakeryProductions WHERE id = %s", (prod_id,))
            if rowcount and rowcount > 0:
                return True, "Üretim kaydı silindi."
            return False, "Kayıt bulunamadı."
        except Exception as e:
            logger.error(f"delete_production hatası: {e}")
            return False, f"Silme hatası: {str(e)}"

    # ==================== 2. 3 ŞUBEYE SEVKİYAT (İÇ DAĞITIM) ====================

    def add_multi_shipment(self, data: Dict, items: List[Dict], user_id: Optional[int] = None) -> Tuple[bool, str, Optional[int]]:
        """İmalathaneden şubeye çoklu kalem ürün sevkiyatı yapar ve şube stoklarına işler"""
        self.ensure_tables()
        try:
            target_branch_id = data.get('target_branch_id')
            if not target_branch_id:
                return False, "Hedef şube seçilmelidir!", None

            if not items:
                return False, "En az bir sevk kalemi eklenmelidir!", None

            source_branch_id = self.get_production_branch_id()
            ship_date = data.get('shipment_date') or datetime.now().date().strftime('%Y-%m-%d')
            notes = (data.get('driver_notes') or '').strip()
            ship_no = data.get('shipment_no') or f"SVK-{datetime.now().strftime('%y%m%d')}-{int(datetime.now().timestamp()) % 10000:04d}"

            # Toplam miktar ve tutar hesapla
            total_qty = 0.0
            total_amt = 0.0
            valid_items = []
            for itm in items:
                p_name = (itm.get('product_name') or '').strip()
                if not p_name:
                    continue
                q = float(to_decimal(itm.get('quantity', 0)))
                if q <= 0:
                    continue
                p = float(to_decimal(itm.get('unit_price', 0)))
                cat = itm.get('category', 'Unlu Mamül')
                u = itm.get('unit', 'Adet')
                line_tot = round(q * p, 2)
                total_qty += q
                total_amt += line_tot
                valid_items.append({
                    'product_name': p_name,
                    'category': cat,
                    'quantity': q,
                    'unit': u,
                    'unit_price': p,
                    'total_amount': line_tot
                })

            if not valid_items:
                return False, "Geçerli sevk edilecek ürün bulunamadı!", None

            summary_name = valid_items[0]['product_name'] if len(valid_items) == 1 else f"{valid_items[0]['product_name']} (+{len(valid_items)-1} kalem)"
            primary_unit = valid_items[0]['unit']

            with db.transaction():
                # 1. Ana Sevkiyat Kaydı
                new_id = db.execute_query("""
                    INSERT INTO BranchShipments (
                        shipment_no, source_branch_id, target_branch_id, shipment_date,
                        product_name, quantity, unit, unit_price, total_amount,
                        status, driver_notes, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Teslim Edildi', %s, %s)
                    RETURNING id
                """, (
                    ship_no, source_branch_id, target_branch_id, ship_date,
                    summary_name, total_qty, primary_unit,
                    round(total_amt / total_qty, 2) if total_qty > 0 else 0,
                    total_amt, notes, user_id
                ))

                # 2. Kalemleri Kaydet ve Stokları Güncelle
                for itm in valid_items:
                    db.execute_query("""
                        INSERT INTO BranchShipmentItems (
                            shipment_id, product_name, category, quantity, unit, unit_price, total_amount
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        new_id, itm['product_name'], itm['category'], itm['quantity'],
                        itm['unit'], itm['unit_price'], itm['total_amount']
                    ))

                    # İmalathane üretim kaydındaki 'shipped_quantity'yi artır
                    prod_row = db.fetch_one("""
                        SELECT id, quantity, shipped_quantity, remaining_quantity 
                        FROM BakeryProductions 
                        WHERE product_name = %s AND production_date <= %s 
                        ORDER BY production_date DESC, id DESC LIMIT 1
                    """, (itm['product_name'], ship_date))
                    if prod_row:
                        new_shipped = float(prod_row['shipped_quantity'] or 0) + itm['quantity']
                        new_rem = max(0.0, float(prod_row['quantity'] or 0) - new_shipped - float(prod_row.get('external_sold_quantity') or 0))
                        db.execute_query("""
                            UPDATE BakeryProductions 
                            SET shipped_quantity = %s, remaining_quantity = %s 
                            WHERE id = %s
                        """, (new_shipped, new_rem, prod_row['id']))

                    # Hedef şubenin ürün stoğuna ekle
                    p_exist = db.fetch_one("""
                        SELECT id, stock_quantity FROM Products 
                        WHERE branch_id = %s AND LOWER(name) = LOWER(%s) AND is_active = TRUE
                    """, (target_branch_id, itm['product_name']))
                    if p_exist:
                        db.execute_query("""
                            UPDATE Products SET stock_quantity = stock_quantity + %s, updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (itm['quantity'], p_exist['id']))
                    else:
                        db.execute_query("""
                            INSERT INTO Products (
                                branch_id, product_code, name, category, unit,
                                purchase_price, sale_price, stock_quantity, is_active
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                        """, (
                            target_branch_id,
                            f"PRD-{uuid.uuid4().hex[:8].upper()}",
                            itm['product_name'], itm['category'], itm['unit'],
                            itm['unit_price'], itm['unit_price'] * 1.3, itm['quantity']
                        ))

            logger.info(f"🚚 Şubeye çoklu sevkiyat yapıldı: {len(valid_items)} kalem -> Şube #{target_branch_id} (No: {ship_no})")
            return True, f"Sevkiyat başarıyla kaydedildi (Sevk No: {ship_no})", new_id
        except Exception as e:
            logger.error(f"add_multi_shipment hatası: {e}")
            return False, f"Sevkiyat kaydedilemedi: {str(e)}", None

    def add_shipment(self, data: Dict, user_id: Optional[int] = None) -> Tuple[bool, str, Optional[int]]:
        """Tek kalem sevkiyat (Geriye dönük uyumluluk sarmalayıcısı)"""
        items = [{
            'product_name': data.get('product_name'),
            'category': data.get('category', 'Unlu Mamül'),
            'quantity': data.get('quantity', 0),
            'unit': data.get('unit', 'Adet'),
            'unit_price': data.get('unit_price', 0),
            'total_amount': data.get('total_amount', 0)
        }]
        return self.add_multi_shipment(data, items, user_id)

    def get_shipment_details(self, shipment_id: int) -> Tuple[Optional[Dict], List[Dict]]:
        """Sevkiyatın ana bilgilerini ve tüm kalemlerini getirir"""
        self.ensure_tables()
        try:
            shipment = db.fetch_one("""
                SELECT bs.*, b.name as target_branch_name
                FROM BranchShipments bs
                LEFT JOIN Branches b ON b.id = bs.target_branch_id
                WHERE bs.id = %s
            """, (shipment_id,))
            if not shipment:
                return None, []

            items = db.fetch_all("""
                SELECT * FROM BranchShipmentItems 
                WHERE shipment_id = %s 
                ORDER BY id ASC
            """, (shipment_id,))

            if not items and shipment.get('product_name'):
                # Geriye dönük tek satır fallback
                items = [{
                    'id': shipment['id'],
                    'shipment_id': shipment['id'],
                    'product_name': shipment['product_name'],
                    'category': 'Unlu Mamül',
                    'quantity': shipment.get('quantity', 0),
                    'unit': shipment.get('unit', 'Adet'),
                    'unit_price': shipment.get('unit_price', 0),
                    'total_amount': shipment.get('total_amount', 0)
                }]

            return shipment, items or []
        except Exception as e:
            logger.error(f"get_shipment_details hatası: {e}")
            return None, []

    def update_multi_shipment(self, shipment_id: int, data: Dict, items: List[Dict], user_id: Optional[int] = None) -> Tuple[bool, str]:
        """Var olan bir sevkiyatı ve kalemlerini günceller"""
        self.ensure_tables()
        try:
            old_ship, old_items = self.get_shipment_details(shipment_id)
            if not old_ship:
                return False, "Sevkiyat kaydı bulunamadı!"

            with db.transaction():
                # 1. Eski kalemlerin stok etkilerini geri al
                target_branch_id = old_ship['target_branch_id']
                ship_date = str(old_ship['shipment_date'])[:10]

                for itm in old_items:
                    # İmalathane stoğunu geri yükle
                    p_name = itm.get('product_name')
                    q = float(itm.get('quantity') or 0)
                    prod_row = db.fetch_one("""
                        SELECT id, quantity, shipped_quantity, remaining_quantity 
                        FROM BakeryProductions 
                        WHERE product_name = %s AND production_date <= %s 
                        ORDER BY production_date DESC, id DESC LIMIT 1
                    """, (p_name, ship_date))
                    if prod_row:
                        new_shipped = max(0.0, float(prod_row['shipped_quantity'] or 0) - q)
                        new_rem = max(0.0, float(prod_row['quantity'] or 0) - new_shipped - float(prod_row.get('external_sold_quantity') or 0))
                        db.execute_query("""
                            UPDATE BakeryProductions 
                            SET shipped_quantity = %s, remaining_quantity = %s 
                            WHERE id = %s
                        """, (new_shipped, new_rem, prod_row['id']))

                    # Şube stoğundan düş
                    db.execute_query("""
                        UPDATE Products SET stock_quantity = GREATEST(0, stock_quantity - %s), updated_at = CURRENT_TIMESTAMP
                        WHERE branch_id = %s AND LOWER(name) = LOWER(%s) AND is_active = TRUE
                    """, (q, target_branch_id, p_name))

                # 2. Eski kalemleri sil
                db.execute_query("DELETE FROM BranchShipmentItems WHERE shipment_id = %s", (shipment_id,))

                # 3. Yeni verileri hesapla
                new_target_branch = data.get('target_branch_id') or target_branch_id
                new_date = data.get('shipment_date') or ship_date
                new_notes = (data.get('driver_notes') or '').strip()

                total_qty = 0.0
                total_amt = 0.0
                valid_items = []
                for itm in items:
                    p_name = (itm.get('product_name') or '').strip()
                    if not p_name:
                        continue
                    q = float(to_decimal(itm.get('quantity', 0)))
                    if q <= 0:
                        continue
                    p = float(to_decimal(itm.get('unit_price', 0)))
                    cat = itm.get('category', 'Unlu Mamül')
                    u = itm.get('unit', 'Adet')
                    line_tot = round(q * p, 2)
                    total_qty += q
                    total_amt += line_tot
                    valid_items.append({
                        'product_name': p_name,
                        'category': cat,
                        'quantity': q,
                        'unit': u,
                        'unit_price': p,
                        'total_amount': line_tot
                    })

                summary_name = valid_items[0]['product_name'] if len(valid_items) == 1 else f"{valid_items[0]['product_name']} (+{len(valid_items)-1} kalem)"
                primary_unit = valid_items[0]['unit'] if valid_items else 'Adet'

                # 4. Ana sevkiyat kaydını güncelle
                db.execute_query("""
                    UPDATE BranchShipments 
                    SET target_branch_id = %s, shipment_date = %s, product_name = %s,
                        quantity = %s, unit = %s, unit_price = %s, total_amount = %s,
                        driver_notes = %s
                    WHERE id = %s
                """, (
                    new_target_branch, new_date, summary_name, total_qty, primary_unit,
                    round(total_amt / total_qty, 2) if total_qty > 0 else 0,
                    total_amt, new_notes, shipment_id
                ))

                # 5. Yeni kalemleri ekle ve stokları güncelle
                for itm in valid_items:
                    db.execute_query("""
                        INSERT INTO BranchShipmentItems (
                            shipment_id, product_name, category, quantity, unit, unit_price, total_amount
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        shipment_id, itm['product_name'], itm['category'], itm['quantity'],
                        itm['unit'], itm['unit_price'], itm['total_amount']
                    ))

                    # İmalathane stoğundan düş
                    prod_row = db.fetch_one("""
                        SELECT id, quantity, shipped_quantity, remaining_quantity 
                        FROM BakeryProductions 
                        WHERE product_name = %s AND production_date <= %s 
                        ORDER BY production_date DESC, id DESC LIMIT 1
                    """, (itm['product_name'], new_date))
                    if prod_row:
                        new_shipped = float(prod_row['shipped_quantity'] or 0) + itm['quantity']
                        new_rem = max(0.0, float(prod_row['quantity'] or 0) - new_shipped - float(prod_row.get('external_sold_quantity') or 0))
                        db.execute_query("""
                            UPDATE BakeryProductions 
                            SET shipped_quantity = %s, remaining_quantity = %s 
                            WHERE id = %s
                        """, (new_shipped, new_rem, prod_row['id']))

                    # Hedef şube stoğuna ekle
                    p_exist = db.fetch_one("""
                        SELECT id, stock_quantity FROM Products 
                        WHERE branch_id = %s AND LOWER(name) = LOWER(%s) AND is_active = TRUE
                    """, (new_target_branch, itm['product_name']))
                    if p_exist:
                        db.execute_query("""
                            UPDATE Products SET stock_quantity = stock_quantity + %s, updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (itm['quantity'], p_exist['id']))
                    else:
                        db.execute_query("""
                            INSERT INTO Products (
                                branch_id, product_code, name, category, unit,
                                purchase_price, sale_price, stock_quantity, is_active
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                        """, (
                            new_target_branch,
                            f"PRD-{uuid.uuid4().hex[:8].upper()}",
                            itm['product_name'], itm['category'], itm['unit'],
                            itm['unit_price'], itm['unit_price'] * 1.3, itm['quantity']
                        ))

            return True, "Sevkiyat başarıyla güncellendi."
        except Exception as e:
            logger.error(f"update_multi_shipment hatası: {e}")
            return False, f"Güncelleme hatası: {str(e)}"

    def delete_shipment(self, shipment_id: int) -> Tuple[bool, str]:
        """Sevkiyat kaydını ve kalemlerini siler, stok etkilerini geri alır"""
        try:
            shipment, items = self.get_shipment_details(shipment_id)
            if not shipment:
                return False, "Sevkiyat kaydı bulunamadı!"

            target_branch_id = shipment['target_branch_id']
            ship_date = str(shipment['shipment_date'])[:10]

            with db.transaction():
                # 1. Stok etkilerini geri al
                for itm in items:
                    p_name = itm.get('product_name')
                    q = float(itm.get('quantity') or 0)

                    # İmalathane stoğunu geri artır
                    prod_row = db.fetch_one("""
                        SELECT id, quantity, shipped_quantity, remaining_quantity 
                        FROM BakeryProductions 
                        WHERE product_name = %s AND production_date <= %s 
                        ORDER BY production_date DESC, id DESC LIMIT 1
                    """, (p_name, ship_date))
                    if prod_row:
                        new_shipped = max(0.0, float(prod_row['shipped_quantity'] or 0) - q)
                        new_rem = max(0.0, float(prod_row['quantity'] or 0) - new_shipped - float(prod_row.get('external_sold_quantity') or 0))
                        db.execute_query("""
                            UPDATE BakeryProductions 
                            SET shipped_quantity = %s, remaining_quantity = %s 
                            WHERE id = %s
                        """, (new_shipped, new_rem, prod_row['id']))

                    # Hedef şube stoğundan düş
                    db.execute_query("""
                        UPDATE Products SET stock_quantity = GREATEST(0, stock_quantity - %s), updated_at = CURRENT_TIMESTAMP
                        WHERE branch_id = %s AND LOWER(name) = LOWER(%s) AND is_active = TRUE
                    """, (q, target_branch_id, p_name))

                # 2. Sevkiyatı sil (BranchShipmentItems ON DELETE CASCADE ile silinir)
                db.execute_query("DELETE FROM BranchShipments WHERE id = %s", (shipment_id,))

            logger.info(f"🗑️ Sevkiyat #{shipment_id} silindi ve stoklar geri yüklendi.")
            return True, "Sevkiyat ve kalemleri başarıyla silindi."
        except Exception as e:
            logger.error(f"delete_shipment hatası: {e}")
            return False, f"Silme hatası: {str(e)}"

    def get_shipments_summary(
        self,
        mode: str = "daily",
        target_date: Optional[str] = None
    ) -> Dict:
        """
        Şubelere yapılan sevkiyatların seçilen döneme (günlük/haftalık/aylık/yıllık/tüm)
        göre şube bazlı dağılımını ve konsolide toplamlarını döndürür.
        """
        self.ensure_tables()
        try:
            if not target_date:
                target_date = datetime.now().strftime("%Y-%m-%d")

            target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
            start_dt = None
            end_dt = None

            if mode == "weekly":
                start_dt = target_dt - timedelta(days=target_dt.weekday())
                end_dt = start_dt + timedelta(days=6)
                title = f"{start_dt.strftime('%d.%m.%Y')} - {end_dt.strftime('%d.%m.%Y')} Haftası Sevkiyatları"
            elif mode == "monthly":
                start_dt = target_dt.replace(day=1)
                _, last_day = calendar.monthrange(target_dt.year, target_dt.month)
                end_dt = target_dt.replace(day=last_day)
                aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
                title = f"{aylar[target_dt.month - 1]} {target_dt.year} Ayı Sevkiyatları"
            elif mode == "yearly":
                start_dt = date(target_dt.year, 1, 1)
                end_dt = date(target_dt.year, 12, 31)
                title = f"{target_dt.year} Yılı Sevkiyatları"
            elif mode == "all":
                title = "Tüm Kayıtlı Sevkiyatlar"
            else:  # daily
                start_dt = target_dt
                end_dt = target_dt
                title = f"{target_dt.strftime('%d.%m.%Y')} Günlük Sevkiyatları"

            start_str = start_dt.strftime("%Y-%m-%d") if start_dt else None
            end_str = end_dt.strftime("%Y-%m-%d") if end_dt else None

            date_where = ""
            sub_params = []
            if start_str and end_str:
                date_where = "WHERE bs.shipment_date BETWEEN %s AND %s"
                sub_params = [start_str, end_str]

            sql = f"""
                SELECT 
                    b.id as branch_id,
                    b.name as branch_name,
                    COALESCE(SUM(sub.calc_qty), 0) as total_qty,
                    COALESCE(SUM(sub.calc_total), 0) as total_amount,
                    COUNT(sub.id) as shipment_count
                FROM Branches b
                LEFT JOIN (
                    SELECT 
                        bs.id,
                        bs.target_branch_id,
                        bs.shipment_date,
                        COALESCE(SUM(bsi.quantity), bs.quantity, 0) as calc_qty,
                        COALESCE(SUM(bsi.total_amount), bs.total_amount, 0) as calc_total
                    FROM BranchShipments bs
                    LEFT JOIN BranchShipmentItems bsi ON bsi.shipment_id = bs.id
                    {date_where}
                    GROUP BY bs.id, bs.target_branch_id, bs.shipment_date, bs.quantity, bs.total_amount
                ) sub ON sub.target_branch_id = b.id
                WHERE b.is_active = TRUE AND LOWER(b.name) NOT LIKE %s
                GROUP BY b.id, b.name
                ORDER BY b.id ASC
            """
            all_params = sub_params + ['%imalat%']
            rows = db.fetch_all(sql, tuple(all_params)) or []

            branches = []
            grand_qty = 0.0
            grand_amt = 0.0
            grand_count = 0

            for r in rows:
                b_qty = float(r.get('total_qty') or 0.0)
                b_amt = float(r.get('total_amount') or 0.0)
                b_cnt = int(r.get('shipment_count') or 0)
                branches.append({
                    'branch_id': r.get('branch_id'),
                    'branch_name': r.get('branch_name') or 'Şube',
                    'total_qty': b_qty,
                    'total_amount': b_amt,
                    'shipment_count': b_cnt
                })
                grand_qty += b_qty
                grand_amt += b_amt
                grand_count += b_cnt

            return {
                'mode': mode,
                'title': title,
                'target_date': target_date,
                'start_date': start_str,
                'end_date': end_str,
                'branches': branches,
                'grand_total_qty': grand_qty,
                'grand_total_amount': grand_amt,
                'grand_shipment_count': grand_count
            }
        except Exception as e:
            logger.error(f"get_shipments_summary hatası: {e}")
            return {
                'mode': mode,
                'title': "Şube Sevkiyatları",
                'target_date': target_date,
                'start_date': None,
                'end_date': None,
                'branches': [],
                'grand_total_qty': 0.0,
                'grand_total_amount': 0.0,
                'grand_shipment_count': 0
            }

    def get_shipments(self, target_branch_id: Optional[int] = None, target_date: Optional[str] = None,
                      start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Şube sevkiyat kayıtlarını kalem sayıları ve özetleriyle birlikte listeler"""
        self.ensure_tables()
        try:
            sql = """
                SELECT bs.*, b.name as target_branch_name,
                       COALESCE(NULLIF(COUNT(bsi.id), 0), 1) as item_count,
                       COALESCE(SUM(bsi.quantity), bs.quantity) as calc_quantity,
                       COALESCE(SUM(bsi.total_amount), bs.total_amount) as calc_total,
                       STRING_AGG(COALESCE(bsi.product_name, ''), ', ') as items_text
                FROM BranchShipments bs
                LEFT JOIN Branches b ON b.id = bs.target_branch_id
                LEFT JOIN BranchShipmentItems bsi ON bsi.shipment_id = bs.id
                WHERE 1=1
            """
            params = []
            if target_branch_id:
                sql += " AND bs.target_branch_id = %s"
                params.append(target_branch_id)
            if target_date:
                sql += " AND bs.shipment_date = %s"
                params.append(target_date)
            if start_date:
                sql += " AND bs.shipment_date >= %s"
                params.append(start_date)
            if end_date:
                sql += " AND bs.shipment_date <= %s"
                params.append(end_date)
            sql += " GROUP BY bs.id, b.name ORDER BY bs.shipment_date DESC, bs.id DESC"
            return db.fetch_all(sql, tuple(params)) if params else db.fetch_all(sql)
        except Exception as e:
            logger.error(f"get_shipments hatası: {e}")
            return []

    # ==================== 3. DIŞ MÜŞTERİLERE TOPTAN SATIŞ ====================

    def add_multi_external_sale(self, data: Dict, items: List[Dict], user_id: Optional[int] = None) -> Tuple[bool, str, Optional[int]]:
        """İmalathaneden dış müşteriye çoklu kalem toptan satış yapar"""
        self.ensure_tables()
        try:
            c_name = (data.get('customer_name') or '').strip()
            if not c_name:
                return False, "Müşteri adı boş bırakılamaz!", None

            if not items:
                return False, "En az bir satış kalemi eklenmelidir!", None

            sale_date = data.get('sale_date') or datetime.now().date().strftime('%Y-%m-%d')
            pay_method = data.get('payment_method', 'Nakit')
            notes = (data.get('notes') or '').strip()
            sale_no = data.get('sale_no') or f"SAT-{datetime.now().strftime('%y%m%d')}-{int(datetime.now().timestamp()) % 10000:04d}"

            total_qty = 0.0
            total_amt = 0.0
            valid_items = []
            for itm in items:
                p_name = (itm.get('product_name') or '').strip()
                if not p_name:
                    continue
                q = float(to_decimal(itm.get('quantity', 0)))
                if q <= 0:
                    continue
                p = float(to_decimal(itm.get('unit_price', 0)))
                cat = itm.get('category', 'Unlu Mamül')
                u = itm.get('unit', 'Adet')
                line_tot = round(q * p, 2)
                total_qty += q
                total_amt += line_tot
                valid_items.append({
                    'product_name': p_name,
                    'category': cat,
                    'quantity': q,
                    'unit': u,
                    'unit_price': p,
                    'total_amount': line_tot
                })

            if not valid_items:
                return False, "Geçerli satış kalemi bulunamadı!", None

            summary_name = valid_items[0]['product_name'] if len(valid_items) == 1 else f"{valid_items[0]['product_name']} (+{len(valid_items)-1} kalem)"
            primary_unit = valid_items[0]['unit']
            p_branch_id = self.get_production_branch_id()

            # Müşteri çözümleme / Otomatik cari kayıt
            cust_id = data.get('customer_id')
            if not cust_id and c_name:
                existing_c = db.fetch_one("""
                    SELECT id FROM Customers 
                    WHERE (branch_id = %s OR branch_id IS NULL) AND LOWER(TRIM(title)) = LOWER(TRIM(%s)) AND is_active = TRUE
                    ORDER BY (CASE WHEN branch_id = %s THEN 0 ELSE 1 END) ASC
                    LIMIT 1
                """, (p_branch_id, c_name, p_branch_id))
                if existing_c:
                    cust_id = existing_c['id']
                    if p_branch_id:
                        db.execute_query("UPDATE Customers SET branch_id = %s WHERE id = %s AND branch_id IS NULL", (p_branch_id, cust_id))
                else:
                    cust_id = db.execute_query("""
                        INSERT INTO Customers (branch_id, title, is_supplier, is_active, balance)
                        VALUES (%s, %s, FALSE, TRUE, 0)
                        RETURNING id
                    """, (p_branch_id, c_name))

            with db.transaction():
                # 1. Ana Dış Satış Kaydı
                new_id = db.execute_query("""
                    INSERT INTO ExternalSales (
                        sale_no, sale_date, customer_id, customer_name,
                        product_name, quantity, unit, unit_price, total_amount,
                        payment_method, payment_status, notes, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Paid', %s, %s)
                    RETURNING id
                """, (
                    sale_no, sale_date, cust_id, c_name,
                    summary_name, total_qty, primary_unit,
                    round(total_amt / total_qty, 2) if total_qty > 0 else 0,
                    total_amt, pay_method, notes, user_id
                ))

                # Açık hesap ise cari bakiyeyi güncelle
                if pay_method == "Açık Hesap (Cari)" and cust_id:
                    db.execute_query("""
                        UPDATE Customers 
                        SET balance = balance + %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (total_amt, cust_id))

                # 2. Kalemleri Kaydet ve İmalathane Üretim Stoğundan Düş
                for itm in valid_items:
                    db.execute_query("""
                        INSERT INTO ExternalSaleItems (
                            sale_id, product_name, category, quantity, unit, unit_price, total_amount
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        new_id, itm['product_name'], itm['category'], itm['quantity'],
                        itm['unit'], itm['unit_price'], itm['total_amount']
                    ))

                    prod_row = db.fetch_one("""
                        SELECT id, quantity, shipped_quantity, external_sold_quantity, remaining_quantity 
                        FROM BakeryProductions 
                        WHERE product_name = %s AND production_date <= %s 
                        ORDER BY production_date DESC, id DESC LIMIT 1
                    """, (itm['product_name'], sale_date))
                    if prod_row:
                        new_sold = float(prod_row.get('external_sold_quantity') or 0) + itm['quantity']
                        new_rem = max(0.0, float(prod_row['quantity'] or 0) - float(prod_row.get('shipped_quantity') or 0) - new_sold)
                        db.execute_query("""
                            UPDATE BakeryProductions 
                            SET external_sold_quantity = %s, remaining_quantity = %s 
                            WHERE id = %s
                        """, (new_sold, new_rem, prod_row['id']))

                # 3. İmalathane Kasa / Banka hesabına geliri ekle
                self._record_external_sale_financials(p_branch_id, sale_no, c_name, total_amt, pay_method, sale_date, user_id)

            logger.info(f"🛒 Dış müşteriye çoklu satış yapıldı: {len(valid_items)} kalem -> {c_name} ({total_amt:,.2f} ₺)")
            return True, f"Satış kaydedildi (Satış No: {sale_no})", new_id
        except Exception as e:
            logger.error(f"add_multi_external_sale hatası: {e}")
            return False, f"Satış kaydedilemedi: {str(e)}", None

    def add_external_sale(self, data: Dict, user_id: Optional[int] = None) -> Tuple[bool, str, Optional[int]]:
        """Tek kalem satış (Geriye dönük uyumluluk sarmalayıcısı)"""
        items = [{
            'product_name': data.get('product_name'),
            'category': data.get('category', 'Unlu Mamül'),
            'quantity': data.get('quantity', 0),
            'unit': data.get('unit', 'Adet'),
            'unit_price': data.get('unit_price', 0),
            'total_amount': data.get('total_amount', 0)
        }]
        return self.add_multi_external_sale(data, items, user_id)

    def get_external_sale_details(self, sale_id: int) -> Tuple[Optional[Dict], List[Dict]]:
        """Dış satışın ana bilgilerini ve tüm kalemlerini getirir"""
        try:
            sale = db.fetch_one("SELECT * FROM ExternalSales WHERE id = %s", (sale_id,))
            if not sale:
                return None, []

            items = db.fetch_all("""
                SELECT * FROM ExternalSaleItems 
                WHERE sale_id = %s 
                ORDER BY id ASC
            """, (sale_id,))

            if not items and sale.get('product_name'):
                items = [{
                    'id': sale['id'],
                    'sale_id': sale['id'],
                    'product_name': sale['product_name'],
                    'category': 'Unlu Mamül',
                    'quantity': sale.get('quantity', 0),
                    'unit': sale.get('unit', 'Adet'),
                    'unit_price': sale.get('unit_price', 0),
                    'total_amount': sale.get('total_amount', 0)
                }]

            return sale, items or []
        except Exception as e:
            logger.error(f"get_external_sale_details hatası: {e}")
            return None, []

    def update_multi_external_sale(self, sale_id: int, data: Dict, items: List[Dict], user_id: Optional[int] = None) -> Tuple[bool, str]:
        """Var olan bir dış satışı ve kalemlerini günceller"""
        try:
            old_sale, old_items = self.get_external_sale_details(sale_id)
            if not old_sale:
                return False, "Satış kaydı bulunamadı!"

            p_branch_id = self.get_production_branch_id()
            sale_date = str(old_sale['sale_date'])[:10]
            old_sale_no = old_sale['sale_no']
            old_total = float(old_sale.get('total_amount') or 0)

            with db.transaction():
                # 1. Eski kalemlerin stok etkilerini geri al
                for itm in old_items:
                    p_name = itm.get('product_name')
                    q = float(itm.get('quantity') or 0)
                    prod_row = db.fetch_one("""
                        SELECT id, quantity, shipped_quantity, external_sold_quantity, remaining_quantity 
                        FROM BakeryProductions 
                        WHERE product_name = %s AND production_date <= %s 
                        ORDER BY production_date DESC, id DESC LIMIT 1
                    """, (p_name, sale_date))
                    if prod_row:
                        new_sold = max(0.0, float(prod_row.get('external_sold_quantity') or 0) - q)
                        new_rem = max(0.0, float(prod_row['quantity'] or 0) - float(prod_row.get('shipped_quantity') or 0) - new_sold)
                        db.execute_query("""
                            UPDATE BakeryProductions 
                            SET external_sold_quantity = %s, remaining_quantity = %s 
                            WHERE id = %s
                        """, (new_sold, new_rem, prod_row['id']))

                # 2. Eski finansal kayıtları geri al
                acc = db.fetch_one("""
                    SELECT id, balance FROM BankAccounts 
                    WHERE branch_id = %s AND is_active = TRUE 
                    ORDER BY id ASC LIMIT 1
                """, (p_branch_id,))
                if acc:
                    new_bal = max(0.0, float(acc['balance'] or 0) - old_total)
                    db.execute_query("UPDATE BankAccounts SET balance = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_bal, acc['id']))
                    db.execute_query("DELETE FROM BankTransactions WHERE reference_no = %s", (old_sale_no,))

                db.execute_query("DELETE FROM DailyTurnovers WHERE description LIKE %s", (f"%{old_sale_no}%",))

                # 3. Eski kalemleri sil
                db.execute_query("DELETE FROM ExternalSaleItems WHERE sale_id = %s", (sale_id,))

                # 4. Yeni verileri hesapla
                c_name = (data.get('customer_name') or old_sale.get('customer_name') or '').strip()
                new_date = data.get('sale_date') or sale_date
                new_pay_method = data.get('payment_method', old_sale.get('payment_method', 'Nakit'))
                new_notes = (data.get('notes') or '').strip()

                total_qty = 0.0
                total_amt = 0.0
                valid_items = []
                for itm in items:
                    p_name = (itm.get('product_name') or '').strip()
                    if not p_name:
                        continue
                    q = float(to_decimal(itm.get('quantity', 0)))
                    if q <= 0:
                        continue
                    p = float(to_decimal(itm.get('unit_price', 0)))
                    cat = itm.get('category', 'Unlu Mamül')
                    u = itm.get('unit', 'Adet')
                    line_tot = round(q * p, 2)
                    total_qty += q
                    total_amt += line_tot
                    valid_items.append({
                        'product_name': p_name,
                        'category': cat,
                        'quantity': q,
                        'unit': u,
                        'unit_price': p,
                        'total_amount': line_tot
                    })

                summary_name = valid_items[0]['product_name'] if len(valid_items) == 1 else f"{valid_items[0]['product_name']} (+{len(valid_items)-1} kalem)"
                primary_unit = valid_items[0]['unit'] if valid_items else 'Adet'

                # 5. Ana satışı güncelle
                db.execute_query("""
                    UPDATE ExternalSales 
                    SET customer_name = %s, sale_date = %s, product_name = %s,
                        quantity = %s, unit = %s, unit_price = %s, total_amount = %s,
                        payment_method = %s, notes = %s
                    WHERE id = %s
                """, (
                    c_name, new_date, summary_name, total_qty, primary_unit,
                    round(total_amt / total_qty, 2) if total_qty > 0 else 0,
                    total_amt, new_pay_method, new_notes, sale_id
                ))

                # 6. Yeni kalemleri ekle ve stokları düş
                for itm in valid_items:
                    db.execute_query("""
                        INSERT INTO ExternalSaleItems (
                            sale_id, product_name, category, quantity, unit, unit_price, total_amount
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        sale_id, itm['product_name'], itm['category'], itm['quantity'],
                        itm['unit'], itm['unit_price'], itm['total_amount']
                    ))

                    prod_row = db.fetch_one("""
                        SELECT id, quantity, shipped_quantity, external_sold_quantity, remaining_quantity 
                        FROM BakeryProductions 
                        WHERE product_name = %s AND production_date <= %s 
                        ORDER BY production_date DESC, id DESC LIMIT 1
                    """, (itm['product_name'], new_date))
                    if prod_row:
                        new_sold = float(prod_row.get('external_sold_quantity') or 0) + itm['quantity']
                        new_rem = max(0.0, float(prod_row['quantity'] or 0) - float(prod_row.get('shipped_quantity') or 0) - new_sold)
                        db.execute_query("""
                            UPDATE BakeryProductions 
                            SET external_sold_quantity = %s, remaining_quantity = %s 
                            WHERE id = %s
                        """, (new_sold, new_rem, prod_row['id']))

                # 7. Yeni finansal kayıtları oluştur
                self._record_external_sale_financials(p_branch_id, old_sale_no, c_name, total_amt, new_pay_method, new_date, user_id)

            return True, "Satış başarıyla güncellendi."
        except Exception as e:
            logger.error(f"update_multi_external_sale hatası: {e}")
            return False, f"Güncelleme hatası: {str(e)}"

    def delete_external_sale(self, sale_id: int) -> Tuple[bool, str]:
        """Dış satış kaydını ve kalemlerini siler, stok ve muhasebe kayıtlarını geri alır"""
        try:
            sale, items = self.get_external_sale_details(sale_id)
            if not sale:
                return False, "Satış kaydı bulunamadı!"

            p_branch_id = self.get_production_branch_id()
            sale_date = str(sale['sale_date'])[:10]
            sale_no = sale['sale_no']
            total_amt = float(sale.get('total_amount') or 0)

            with db.transaction():
                # 1. Stok etkilerini geri al
                for itm in items:
                    p_name = itm.get('product_name')
                    q = float(itm.get('quantity') or 0)
                    prod_row = db.fetch_one("""
                        SELECT id, quantity, shipped_quantity, external_sold_quantity, remaining_quantity 
                        FROM BakeryProductions 
                        WHERE product_name = %s AND production_date <= %s 
                        ORDER BY production_date DESC, id DESC LIMIT 1
                    """, (p_name, sale_date))
                    if prod_row:
                        new_sold = max(0.0, float(prod_row.get('external_sold_quantity') or 0) - q)
                        new_rem = max(0.0, float(prod_row['quantity'] or 0) - float(prod_row.get('shipped_quantity') or 0) - new_sold)
                        db.execute_query("""
                            UPDATE BakeryProductions 
                            SET external_sold_quantity = %s, remaining_quantity = %s 
                            WHERE id = %s
                        """, (new_sold, new_rem, prod_row['id']))

                # 2. Muhasebe ve Kasa/Banka kayıtlarını geri al
                acc = db.fetch_one("""
                    SELECT id, balance FROM BankAccounts 
                    WHERE branch_id = %s AND is_active = TRUE 
                    ORDER BY id ASC LIMIT 1
                """, (p_branch_id,))
                if acc:
                    new_bal = max(0.0, float(acc['balance'] or 0) - total_amt)
                    db.execute_query("UPDATE BankAccounts SET balance = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_bal, acc['id']))
                    db.execute_query("DELETE FROM BankTransactions WHERE reference_no = %s", (sale_no,))

                db.execute_query("DELETE FROM DailyTurnovers WHERE description LIKE %s", (f"%{sale_no}%",))

                # 3. Satışı sil (ExternalSaleItems ON DELETE CASCADE ile silinir)
                db.execute_query("DELETE FROM ExternalSales WHERE id = %s", (sale_id,))

            logger.info(f"🗑️ Dış satış #{sale_id} silindi, stok ve finansal kayıtlar geri alındı.")
            return True, "Satış kaydı başarıyla silindi."
        except Exception as e:
            logger.error(f"delete_external_sale hatası: {e}")
            return False, f"Silme hatası: {str(e)}"

    def _record_external_sale_financials(self, branch_id: int, sale_no: str, customer_name: str, amount: float, method: str, sale_date: str, user_id: Optional[int]):
        """Dış satış gelirini Kasa / Banka ve Ciro defterine otomatik işler"""
        try:
            # 1. DailyTurnovers tablosuna otomatik gelir olarak ekle
            db.execute_query("""
                INSERT INTO DailyTurnovers (
                    branch_id, entry_date, entry_type, category,
                    amount, payment_method, description, created_by
                ) VALUES (%s, %s, 'Income', 'Dış Satış & Toptan', %s, %s, %s, %s)
            """, (branch_id, sale_date, amount, method, f"Toptan Satış No: {sale_no} ({customer_name})", user_id))

            # 2. Şubenin Kasa/Banka hesabını güncelle
            acc = db.fetch_one("""
                SELECT id, balance FROM BankAccounts 
                WHERE branch_id = %s AND is_active = TRUE 
                ORDER BY id ASC LIMIT 1
            """, (branch_id,))
            if acc:
                new_bal = float(acc['balance'] or 0) + amount
                db.execute_query("UPDATE BankAccounts SET balance = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_bal, acc['id']))
                # BankTransactions
                db.execute_query("""
                    INSERT INTO BankTransactions (
                        branch_id, bank_account_id, transaction_date, transaction_type, amount,
                        description, reference_no, created_by
                    ) VALUES (%s, %s, %s, 'Deposit', %s, %s, %s, %s)
                """, (branch_id, acc['id'], sale_date, amount, f"İmalathane Toptan Satış ({customer_name})", sale_no, user_id))
        except Exception as e:
            logger.warning(f"Finansal entegrasyon uyarısı: {e}")

    def get_external_sales(self, target_date: Optional[str] = None) -> List[Dict]:
        """Dış müşteri satışlarını kalem sayıları ve özetleriyle birlikte listeler"""
        self.ensure_tables()
        try:
            sql = """
                SELECT es.*,
                       COALESCE(NULLIF(COUNT(esi.id), 0), 1) as item_count,
                       COALESCE(SUM(esi.quantity), es.quantity) as calc_quantity,
                       COALESCE(SUM(esi.total_amount), es.total_amount) as calc_total,
                       STRING_AGG(COALESCE(esi.product_name, ''), ', ') as items_text
                FROM ExternalSales es
                LEFT JOIN ExternalSaleItems esi ON esi.sale_id = es.id
                WHERE 1=1
            """
            params = []
            if target_date:
                sql += " AND es.sale_date = %s"
                params.append(target_date)
            sql += " GROUP BY es.id ORDER BY es.sale_date DESC, es.id DESC"
            return db.fetch_all(sql, tuple(params)) if params else db.fetch_all(sql)
        except Exception as e:
            logger.error(f"get_external_sales hatası: {e}")
            return []

    # ==================== 4. İMALATHANE ÖZET VE KPI İSTATİSTİKLERİ ====================

    def get_hub_stats(self, target_date: Optional[str] = None) -> Dict:
        """İmalathanenin günlük ve kümülatif üretim, sevkiyat ve satış özetini verir"""
        self.ensure_tables()
        if not target_date:
            target_date = datetime.now().date().strftime('%Y-%m-%d')

        try:
            # Günlük Üretim Toplamı
            p_res = db.fetch_one("""
                SELECT 
                    COALESCE(SUM(quantity), 0) as total_prod_qty,
                    COALESCE(SUM(shipped_quantity), 0) as total_shipped_qty,
                    COALESCE(SUM(external_sold_quantity), 0) as total_ext_qty,
                    COALESCE(SUM(remaining_quantity), 0) as total_rem_qty
                FROM BakeryProductions
                WHERE production_date = %s
            """, (target_date,))

            # 3 Şubeye Sevkiyat Tutarları ve Adetleri
            branches = self.get_retail_branches()
            branch_breakdown = {}
            total_ship_amount = 0.0

            for b in branches:
                s_res = db.fetch_one("""
                    SELECT 
                        COALESCE(SUM(quantity), 0) as qty,
                        COALESCE(SUM(total_amount), 0) as total
                    FROM BranchShipments
                    WHERE target_branch_id = %s AND shipment_date = %s
                """, (b['id'], target_date))
                b_qty = float(s_res['qty']) if s_res else 0.0
                b_tot = float(s_res['total']) if s_res else 0.0
                total_ship_amount += b_tot
                branch_breakdown[b['name']] = {'qty': b_qty, 'total': b_tot}

            # Dış Satış Cirosu
            ext_res = db.fetch_one("""
                SELECT 
                    COALESCE(SUM(quantity), 0) as qty,
                    COALESCE(SUM(total_amount), 0) as total,
                    COUNT(*) as count
                FROM ExternalSales
                WHERE sale_date = %s
            """, (target_date,))
            ext_qty = float(ext_res['qty']) if ext_res else 0.0
            ext_total = float(ext_res['total']) if ext_res else 0.0

            return {
                'target_date': target_date,
                'total_produced': float(p_res['total_prod_qty']) if p_res else 0.0,
                'total_shipped': float(p_res['total_shipped_qty']) if p_res else 0.0,
                'total_external_sold': float(p_res['total_ext_qty']) if p_res else 0.0,
                'total_remaining': float(p_res['total_rem_qty']) if p_res else 0.0,
                'total_ship_amount': total_ship_amount,
                'ext_sales_total': ext_total,
                'ext_sales_count': int(ext_res['count']) if ext_res else 0,
                'grand_production_value': total_ship_amount + ext_total,
                'branch_breakdown': branch_breakdown
            }
        except Exception as e:
            logger.error(f"get_hub_stats hatası: {e}")
            return {
                'target_date': target_date,
                'total_produced': 0.0,
                'total_shipped': 0.0,
                'total_external_sold': 0.0,
                'total_remaining': 0.0,
                'total_ship_amount': 0.0,
                'ext_sales_total': 0.0,
                'ext_sales_count': 0,
                'grand_production_value': 0.0,
                'branch_breakdown': {}
            }


production_service = ProductionService()
