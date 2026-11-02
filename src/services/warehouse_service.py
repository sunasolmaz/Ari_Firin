# src/services/warehouse_service.py
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Tuple, Optional, Any
from ..core.database import db
from ..core.logger import logger
from ..core.decimal_utils import to_decimal, round_currency, round_quantity


class WarehouseService:
    """Merkez Depo, Stok Yönetimi ve Şubelere Sevkiyat Servisi"""

    def __init__(self):
        try:
            db.ensure_warehouse_tables()
        except Exception as e:
            logger.warning(f"WarehouseService tablo denetim uyarısı: {e}")

    # ==================== ÜRÜN YÖNETİMİ ====================

    def get_products(
        self,
        search: str = "",
        category: str = "",
        low_stock_only: bool = False
    ) -> List[Dict]:
        """Depodaki ürünleri listeler ve filtreler"""
        try:
            sql = """
                SELECT 
                    id, product_code, barcode, name, category, unit,
                    purchase_price, sale_price, stock_quantity, critical_stock,
                    is_active, notes, created_at, updated_at
                FROM WarehouseProducts
                WHERE is_active = TRUE
            """
            params = []

            if search:
                sql += " AND (LOWER(name) LIKE LOWER(%s) OR LOWER(product_code) LIKE LOWER(%s))"
                params.extend([f"%{search.strip()}%", f"%{search.strip()}%"])

            if category and category != "Tümü":
                sql += " AND category = %s"
                params.append(category)

            if low_stock_only:
                sql += " AND stock_quantity <= critical_stock"

            sql += " ORDER BY name ASC"

            return db.fetch_all(sql, tuple(params)) if params else db.fetch_all(sql)
        except Exception as e:
            logger.error(f"get_products hatası: {e}")
            return []

    def get_product(self, product_id: int) -> Optional[Dict]:
        """Tek ürün detayı"""
        try:
            return db.fetch_one("SELECT * FROM WarehouseProducts WHERE id = %s", (product_id,))
        except Exception as e:
            logger.error(f"get_product hatası: {e}")
            return None

    def add_product(self, data: Dict, user_id: Optional[int] = None) -> Tuple[bool, str, Optional[int]]:
        """Yeni depo ürünü / hammaddesi ekler"""
        try:
            name = (data.get('name') or '').strip()
            if not name:
                return False, "Ürün adı boş bırakılamaz!", None

            code = (data.get('product_code') or '').strip()
            if not code:
                # Otomatik kod üret
                seq_row = db.fetch_one("SELECT COALESCE(MAX(id), 0) + 1 as next_id FROM WarehouseProducts")
                next_id = seq_row['next_id'] if seq_row else 1
                code = f"DEP-{next_id:04d}"

            # Kod benzersizlik kontrolü
            existing = db.fetch_one("SELECT id FROM WarehouseProducts WHERE product_code = %s", (code,))
            if existing:
                return False, f"'{code}' kodlu ürün zaten mevcut!", None

            category = (data.get('category') or 'Hammadde').strip()
            unit = (data.get('unit') or 'Adet').strip()
            purchase_price = float(to_decimal(data.get('purchase_price', 0)))
            sale_price = float(to_decimal(data.get('sale_price', 0)))
            stock_qty = float(to_decimal(data.get('stock_quantity', 0)))
            critical_stock = float(to_decimal(data.get('critical_stock', 10)))
            notes = (data.get('notes') or '').strip()

            new_id = db.execute_query("""
                INSERT INTO WarehouseProducts (
                    product_code, barcode, name, category, unit,
                    purchase_price, sale_price, stock_quantity, critical_stock, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                code, data.get('barcode', ''), name, category, unit,
                purchase_price, sale_price, stock_qty, critical_stock, notes
            ))

            # Başlangıç stoğu varsa 'IN' hareketi oluştur
            if stock_qty > 0 and new_id:
                db.execute_query("""
                    INSERT INTO WarehouseStockMovements (
                        warehouse_product_id, movement_type, quantity, unit,
                        movement_date, document_no, description, created_by
                    ) VALUES (%s, 'IN', %s, %s, CURRENT_DATE, 'AÇILIŞ', 'Başlangıç stok girişi', %s)
                """, (new_id, stock_qty, unit, user_id))

            logger.info(f"✅ Yeni depo ürünü eklendi: ID={new_id}, Kod={code}, İsim={name}")
            return True, "Ürün başarıyla eklendi.", new_id
        except Exception as e:
            logger.error(f"add_product hatası: {e}")
            return False, f"Ürün eklenirken hata: {str(e)}", None

    def update_product(self, product_id: int, data: Dict) -> Tuple[bool, str]:
        """Ürün bilgilerini günceller"""
        try:
            name = (data.get('name') or '').strip()
            if not name:
                return False, "Ürün adı boş bırakılamaz!"

            purchase_price = float(to_decimal(data.get('purchase_price', 0)))
            sale_price = float(to_decimal(data.get('sale_price', 0)))
            critical_stock = float(to_decimal(data.get('critical_stock', 10)))

            db.execute_query("""
                UPDATE WarehouseProducts SET
                    name = %s,
                    category = %s,
                    unit = %s,
                    purchase_price = %s,
                    sale_price = %s,
                    critical_stock = %s,
                    barcode = %s,
                    notes = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                name,
                data.get('category', 'Hammadde'),
                data.get('unit', 'Adet'),
                purchase_price,
                sale_price,
                critical_stock,
                data.get('barcode', ''),
                data.get('notes', ''),
                product_id
            ))
            return True, "Ürün güncellendi."
        except Exception as e:
            logger.error(f"update_product hatası: {e}")
            return False, f"Güncelleme hatası: {str(e)}"

    def delete_product(self, product_id: int) -> Tuple[bool, str]:
        """Ürünü pasife alır (soft delete)"""
        try:
            db.execute_query("UPDATE WarehouseProducts SET is_active = FALSE WHERE id = %s", (product_id,))
            return True, "Ürün silindi."
        except Exception as e:
            logger.error(f"delete_product hatası: {e}")
            return False, f"Silme hatası: {str(e)}"

    # ==================== STOK GİRİŞİ (ARTIRMA) VE ÇIKIŞI (AZALTMA) ====================

    def add_stock_in(
        self,
        product_id: Optional[int] = None,
        quantity: float = 0.0,
        document_no: str = "",
        description: str = "",
        user_id: Optional[int] = None,
        product_name: Optional[str] = None,
        unit: Optional[str] = None,
        supplier_name: Optional[str] = None,
        category: Optional[str] = "Hammadde",
        purchase_price: float = 0.0
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Depoya malzeme kabulü ve stok girişi yapar.
        - Ürün sistemde kayıtlı ise stoğu artırır.
        - Ürün depoda ilk defa geliyorsa otomatik olarak WarehouseProducts kaydı açar ve stok girişi yapar.
        - Malzemenin hangi firmadan/tedarikçiden geldiğini WarehouseStockMovements tablosuna kaydeder.
        """
        try:
            qty_dec = to_decimal(quantity)
            if qty_dec <= Decimal('0'):
                return False, "Giriş miktarı 0'dan büyük olmalıdır!", None

            # Ürünü bul veya ada göre ara
            product = None
            if product_id:
                product = self.get_product(product_id)

            clean_name = (product_name or '').strip()
            if not product and clean_name:
                product = db.fetch_one("""
                    SELECT * FROM WarehouseProducts 
                    WHERE LOWER(TRIM(name)) = LOWER(TRIM(%s)) AND is_active = TRUE
                """, (clean_name,))

            supp_val = (supplier_name or '').strip()
            doc_val = (document_no or 'GİRİŞ').strip()
            desc_val = (description or '').strip()

            if product:
                # ─── VAR OLAN ÜRÜN: STOK MİKTARINI ARTIR ───
                p_id = product['id']
                p_name = product['name']
                prev_stock = to_decimal(product.get('stock_quantity', 0))
                new_stock = prev_stock + qty_dec
                unit_val = (unit or product.get('unit') or 'Adet').strip()

                with db.transaction():
                    db.execute_query("""
                        UPDATE WarehouseProducts 
                        SET stock_quantity = stock_quantity + %s,
                            unit = COALESCE(NULLIF(%s, ''), unit),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (float(qty_dec), unit_val, p_id))

                    mov_desc = desc_val or (f"Tedarikçi: {supp_val}" if supp_val else "Depo stok girişi")
                    db.execute_query("""
                        INSERT INTO WarehouseStockMovements (
                            warehouse_product_id, movement_type, quantity, unit,
                            previous_stock, new_stock,
                            movement_date, document_no, supplier_name, description, created_by
                        ) VALUES (%s, 'IN', %s, %s, %s, %s, CURRENT_DATE, %s, %s, %s, %s)
                    """, (
                        p_id, float(qty_dec), unit_val,
                        float(prev_stock), float(new_stock),
                        doc_val, supp_val or None, mov_desc, user_id
                    ))

                logger.info(f"📥 Depo Stok Artırıldı: {p_name} +{qty_dec} {unit_val} (Tedarikçi: {supp_val or '-'})")
                msg = f"'{p_name}' stoğu başarıyla güncellendi.\n\nEski Stok: {prev_stock:,.2f} {unit_val}\nEklenen: +{qty_dec:,.2f} {unit_val}\nYeni Stok: {new_stock:,.2f} {unit_val}"
                return True, msg, p_id

            else:
                # ─── YENİ ÜRÜN: DEPOYA İLK GİRİŞ OTOMATİK TANIMLANSIN ───
                if not clean_name:
                    return False, "Lütfen ürün adını giriniz veya listeden seçiniz!", None

                unit_val = (unit or 'Adet').strip()
                cat_val = (category or 'Hammadde').strip()

                # Otomatik benzersiz ürün kodu üret
                seq_row = db.fetch_one("SELECT COALESCE(MAX(id), 0) + 1 as next_id FROM WarehouseProducts")
                next_id = int(seq_row['next_id']) if seq_row and seq_row.get('next_id') else 1
                code = f"DEP-{next_id:04d}"
                while db.fetch_one("SELECT id FROM WarehouseProducts WHERE product_code = %s", (code,)):
                    next_id += 1
                    code = f"DEP-{next_id:04d}"

                with db.transaction():
                    notes_txt = f"Malzeme kabul ile otomatik eklendi. İlk tedarikçi: {supp_val}" if supp_val else "Malzeme kabul ile eklendi."
                    new_id = db.execute_query("""
                        INSERT INTO WarehouseProducts (
                            product_code, barcode, name, category, unit,
                            purchase_price, sale_price, stock_quantity, critical_stock, notes
                        ) VALUES (%s, '', %s, %s, %s, %s, 0, %s, 10, %s)
                        RETURNING id
                    """, (
                        code, clean_name, cat_val, unit_val,
                        float(purchase_price), float(qty_dec), notes_txt
                    ))

                    mov_desc = desc_val or (f"İlk malzeme kabulü & stok girişi ({supp_val})" if supp_val else "İlk malzeme kabulü & stok girişi")
                    db.execute_query("""
                        INSERT INTO WarehouseStockMovements (
                            warehouse_product_id, movement_type, quantity, unit,
                            previous_stock, new_stock,
                            movement_date, document_no, supplier_name, description, created_by
                        ) VALUES (%s, 'IN', %s, %s, 0, %s, CURRENT_DATE, %s, %s, %s, %s)
                    """, (
                        new_id, float(qty_dec), unit_val,
                        float(qty_dec), doc_val, supp_val or None, mov_desc, user_id
                    ))

                logger.info(f"✨ Yeni Ürün Depoya Eklendi & Giriş Yapıldı: {clean_name} ({code}) - Miktar: {qty_dec} {unit_val}")
                msg = f"'{clean_name}' ürünü depoya başarıyla tanımlandı!\n\nÜrün Kodu: {code}\nİlk Stok Girişi: {qty_dec:,.2f} {unit_val}\nFirma / Tedarikçi: {supp_val or '-'}"
                return True, msg, new_id

        except Exception as e:
            logger.error(f"add_stock_in hatası: {e}")
            return False, f"Stok girişi hatası: {str(e)}", None

    def add_stock_out(
        self,
        product_id: int,
        quantity: float,
        reason: str = "Fire / Zayiat",
        description: str = "",
        user_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Depodan stok çıkışı / fire / azaltma"""
        try:
            qty_dec = to_decimal(quantity)
            if qty_dec <= Decimal('0'):
                return False, "Çıkış miktarı 0'dan büyük olmalıdır!"

            product = self.get_product(product_id)
            if not product:
                return False, "Ürün bulunamadı!"

            current_stock = to_decimal(product.get('stock_quantity', 0))
            if current_stock < qty_dec:
                return False, f"Yetersiz stok! Mevcut: {current_stock} {product.get('unit')}, Çıkış: {qty_dec} {product.get('unit')}"

            new_stock = current_stock - qty_dec

            with db.transaction():
                # Stok azalt
                db.execute_query("""
                    UPDATE WarehouseProducts 
                    SET stock_quantity = stock_quantity - %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (float(qty_dec), product_id))

                desc_text = f"Neden: {reason}. {description}".strip()

                # Hareket kaydet
                db.execute_query("""
                    INSERT INTO WarehouseStockMovements (
                        warehouse_product_id, movement_type, quantity, unit,
                        previous_stock, new_stock,
                        movement_date, document_no, description, created_by
                    ) VALUES (%s, 'OUT', %s, %s, %s, %s, CURRENT_DATE, %s, %s, %s)
                """, (
                    product_id, float(qty_dec), product.get('unit', 'Adet'),
                    float(current_stock), float(new_stock),
                    reason, desc_text, user_id
                ))

            logger.info(f"📤 Depo Stok Çıkışı: Ürün={product['name']}, Miktar={qty_dec} {product.get('unit')}")
            return True, f"{qty_dec} {product.get('unit')} stok depodan düşüldü."
        except Exception as e:
            logger.error(f"add_stock_out hatası: {e}")
            return False, f"Stok çıkışı hatası: {str(e)}"

    # ==================== ŞUBELERE SEVKİYAT / DAĞITIM ====================

    def dispatch_to_branch(
        self,
        product_id: int,
        target_branch_id: int,
        quantity: float,
        dispatch_date: Optional[str] = None,
        document_no: str = "",
        description: str = "",
        user_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Merkez depodan şubeye ürün sevkiyatı yapar:
        1. Merkez depo stoğundan düşer (azaltır).
        2. 'DISPATCH' türünde sevkiyat hareketi oluşturur.
        3. Hedef şubenin `Products` envanterine bu stoğu ekler/senkronize eder.
        """
        try:
            qty_dec = to_decimal(quantity)
            if qty_dec <= Decimal('0'):
                return False, "Sevkiyat miktarı 0'dan büyük olmalıdır!"

            if not target_branch_id:
                return False, "Hedef şube seçilmelidir!"

            product = self.get_product(product_id)
            if not product:
                return False, "Depo ürünü bulunamadı!"

            current_stock = to_decimal(product.get('stock_quantity', 0))
            if current_stock < qty_dec:
                return False, f"Depoda yetersiz stok! Kalan: {current_stock} {product.get('unit')}, İstenen: {qty_dec} {product.get('unit')}"

            new_stock = current_stock - qty_dec

            if not dispatch_date:
                dispatch_date = datetime.now().date().strftime('%Y-%m-%d')

            with db.transaction():
                # 1. Merkez Depo Stoğundan Düş
                db.execute_query("""
                    UPDATE WarehouseProducts 
                    SET stock_quantity = stock_quantity - %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (float(qty_dec), product_id))

                # 2. Sevkiyat Hareket Kaydı
                db.execute_query("""
                    INSERT INTO WarehouseStockMovements (
                        warehouse_product_id, movement_type, quantity, unit,
                        previous_stock, new_stock,
                        target_branch_id, movement_date, document_no, description, created_by
                    ) VALUES (%s, 'DISPATCH', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    product_id, float(qty_dec), product.get('unit', 'Adet'),
                    float(current_stock), float(new_stock),
                    target_branch_id, dispatch_date, document_no or 'SEVKIYAT',
                    (description or 'Şubeye ürün sevkiyatı').strip(), user_id
                ))

                # 3. Hedef Şubenin Products Tablosundaki Stoğunu Artır / Eşle
                # İlgili şubede aynı isimde ürün var mı kontrol et
                prod_name = product['name'].strip()
                branch_prod = db.fetch_one("""
                    SELECT id, stock_quantity 
                    FROM Products 
                    WHERE branch_id = %s AND LOWER(name) = LOWER(%s) AND is_active = TRUE
                """, (target_branch_id, prod_name))

                if branch_prod:
                    # Şubedeki mevcut ürünün stoğunu artır
                    db.execute_query("""
                        UPDATE Products 
                        SET stock_quantity = stock_quantity + %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (float(qty_dec), branch_prod['id']))
                else:
                    # Şubede bu ürün henüz yoksa şube envanterine ekle
                    branch_code = f"PRD-B{target_branch_id}-{product['id']:03d}"
                    db.execute_query("""
                        INSERT INTO Products (
                            branch_id, product_code, name, category, unit,
                            purchase_price, sale_price, stock_quantity, critical_stock, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                    """, (
                        target_branch_id, branch_code, prod_name,
                        product.get('category', 'Hammadde'), product.get('unit', 'Adet'),
                        float(product.get('purchase_price', 0)), float(product.get('sale_price', 0)),
                        float(qty_dec), float(product.get('critical_stock', 5))
                    ))

            logger.info(f"🚚 Şube Sevkiyatı Tamamlandı: Şube={target_branch_id}, Ürün={product['name']}, Miktar={qty_dec}")
            return True, f"{qty_dec} {product.get('unit')} başarıyla sevk edildi ve şube stoğu güncellendi."
        except Exception as e:
            logger.error(f"dispatch_to_branch hatası: {e}")
            return False, f"Sevkiyat hatası: {str(e)}"

    def get_branch_dispatches(
        self,
        branch_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """Şubelere verilen / sevk edilen ürünlerin dökümünü getirir"""
        try:
            sql = """
                SELECT 
                    wsm.id,
                    wsm.warehouse_product_id,
                    wsm.movement_date,
                    wsm.quantity,
                    wsm.unit,
                    wsm.document_no,
                    wsm.description,
                    wsm.created_at,
                    wp.name as product_name,
                    wp.product_code,
                    wp.category as product_category,
                    b.id as branch_id,
                    b.name as branch_name,
                    u.full_name as created_by_name
                FROM WarehouseStockMovements wsm
                JOIN WarehouseProducts wp ON wsm.warehouse_product_id = wp.id
                LEFT JOIN Branches b ON wsm.target_branch_id = b.id
                LEFT JOIN Users u ON wsm.created_by = u.id
                WHERE wsm.movement_type = 'DISPATCH'
            """
            params = []

            if branch_id:
                sql += " AND wsm.target_branch_id = %s"
                params.append(branch_id)

            if start_date:
                sql += " AND wsm.movement_date >= %s"
                params.append(start_date)

            if end_date:
                sql += " AND wsm.movement_date <= %s"
                params.append(end_date)

            sql += " ORDER BY wsm.movement_date DESC, wsm.id DESC"

            return db.fetch_all(sql, tuple(params)) if params else db.fetch_all(sql)
        except Exception as e:
            logger.error(f"get_branch_dispatches hatası: {e}")
            return []

    def get_dispatches(
        self,
        branch_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """Şubelere sevk edilen ürünlerin dökümünü getirir (alias)"""
        return self.get_branch_dispatches(branch_id=branch_id, start_date=start_date, end_date=end_date)

    def get_stock_movements(
        self,
        movement_type: Optional[str] = None,
        product_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 200
    ) -> List[Dict]:
        """Depo stok giriş, çıkış ve sevkiyat hareketlerini listeler"""
        try:
            sql = """
                SELECT 
                    wsm.id,
                    wsm.warehouse_product_id,
                    wsm.movement_type,
                    wsm.quantity,
                    wsm.unit,
                    wsm.target_branch_id,
                    wsm.movement_date,
                    wsm.document_no,
                    wsm.supplier_name,
                    COALESCE(wsm.previous_stock, 0) as previous_stock,
                    COALESCE(wsm.new_stock, 0) as new_stock,
                    wsm.description,
                    wsm.created_at,
                    wp.name as product_name,
                    wp.product_code,
                    wp.category as product_category,
                    wp.stock_quantity as current_stock,
                    b.name as branch_name,
                    u.full_name as created_by_name
                FROM WarehouseStockMovements wsm
                JOIN WarehouseProducts wp ON wsm.warehouse_product_id = wp.id
                LEFT JOIN Branches b ON wsm.target_branch_id = b.id
                LEFT JOIN Users u ON wsm.created_by = u.id
                WHERE 1=1
            """
            params = []

            if movement_type and movement_type != 'ALL':
                sql += " AND UPPER(wsm.movement_type) = UPPER(%s)"
                params.append(movement_type)

            if product_id:
                sql += " AND wsm.warehouse_product_id = %s"
                params.append(product_id)

            if start_date:
                sql += " AND wsm.movement_date >= %s"
                params.append(start_date)

            if end_date:
                sql += " AND wsm.movement_date <= %s"
                params.append(end_date)

            sql += " ORDER BY wsm.movement_date DESC, wsm.id DESC LIMIT %s"
            params.append(limit)

            return db.fetch_all(sql, tuple(params))
        except Exception as e:
            logger.error(f"get_stock_movements hatası: {e}")
            return []

    # ==================== KRİTİK STOK VE İSTATİSTİKLER ====================

    def get_critical_stock_products(self) -> List[Dict]:
        """Kritik seviyeye gelen / altındaki depo ürünlerini bildirim paneli için listeler"""
        try:
            return db.fetch_all("""
                SELECT 
                    id, product_code, name, category, unit,
                    stock_quantity, critical_stock
                FROM WarehouseProducts
                WHERE is_active = TRUE 
                AND stock_quantity <= critical_stock
                ORDER BY (stock_quantity / NULLIF(critical_stock, 0)) ASC, stock_quantity ASC
            """)
        except Exception as e:
            logger.error(f"get_critical_stock_products hatası: {e}")
            return []

    def get_warehouse_stats(self) -> Dict:
        """Depo genel istatistikleri"""
        try:
            prod_stats = db.fetch_one("""
                SELECT 
                    COUNT(*) as total_products,
                    COALESCE(SUM(stock_quantity), 0) as total_stock,
                    COUNT(CASE WHEN stock_quantity <= critical_stock THEN 1 END) as critical_count
                FROM WarehouseProducts
                WHERE is_active = TRUE
            """)

            today_str = datetime.now().date().strftime('%Y-%m-%d')
            today_dispatch = db.fetch_one("""
                SELECT 
                    COUNT(*) as count,
                    COALESCE(SUM(quantity), 0) as total_qty
                FROM WarehouseStockMovements
                WHERE movement_type = 'DISPATCH' AND movement_date = %s
            """, (today_str,))

            return {
                'total_products': int(prod_stats['total_products']) if prod_stats else 0,
                'total_stock': float(prod_stats['total_stock']) if prod_stats else 0.0,
                'critical_count': int(prod_stats['critical_count']) if prod_stats else 0,
                'today_dispatch_count': int(today_dispatch['count']) if today_dispatch else 0,
                'today_dispatch_qty': float(today_dispatch['total_qty']) if today_dispatch else 0.0
            }
        except Exception as e:
            logger.error(f"get_warehouse_stats hatası: {e}")
            return {
                'total_products': 0,
                'total_stock': 0.0,
                'critical_count': 0,
                'today_dispatch_count': 0,
                'today_dispatch_qty': 0.0
            }


    # ==================== HAREKET DÜZENLEME VE SİLME (SEVKİYAT / KABUL / ÇIKIŞ) ====================

    def get_stock_movement(self, movement_id: int) -> Optional[Dict]:
        """Tekil bir stok hareketini detaylarıyla getirir"""
        try:
            return db.fetch_one("""
                SELECT 
                    wsm.*,
                    wp.name as product_name,
                    wp.product_code,
                    wp.category as product_category,
                    wp.stock_quantity as current_stock,
                    b.name as branch_name,
                    u.full_name as created_by_name
                FROM WarehouseStockMovements wsm
                JOIN WarehouseProducts wp ON wsm.warehouse_product_id = wp.id
                LEFT JOIN Branches b ON wsm.target_branch_id = b.id
                LEFT JOIN Users u ON wsm.created_by = u.id
                WHERE wsm.id = %s
            """, (movement_id,))
        except Exception as e:
            logger.error(f"get_stock_movement hatası: {e}")
            return None

    def delete_stock_movement(self, movement_id: int, user_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Depo hareketini (Sevkiyat, Malzeme Kabul, Fire/Çıkış) siler ve
        stokları otomatik olarak ters işlemle eski haline getirir.
        """
        try:
            mov = db.fetch_one("SELECT * FROM WarehouseStockMovements WHERE id = %s", (movement_id,))
            if not mov:
                return False, "Hareket kaydı bulunamadı!"

            m_type = mov.get('movement_type')
            p_id = mov.get('warehouse_product_id')
            qty = to_decimal(mov.get('quantity', 0))
            target_branch_id = mov.get('target_branch_id')

            wp = db.fetch_one("SELECT * FROM WarehouseProducts WHERE id = %s", (p_id,))
            prod_name = wp['name'] if wp else "Ürün"

            with db.transaction():
                if m_type == 'IN':
                    # Giriş iptal ediliyor: Merkez depo stoğundan düş
                    db.execute_query("""
                        UPDATE WarehouseProducts 
                        SET stock_quantity = stock_quantity - %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (float(qty), p_id))

                elif m_type == 'OUT':
                    # Çıkış iptal ediliyor: Merkez depo stoğuna geri ekle
                    db.execute_query("""
                        UPDATE WarehouseProducts 
                        SET stock_quantity = stock_quantity + %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (float(qty), p_id))

                elif m_type == 'DISPATCH':
                    # Sevkiyat iptal ediliyor:
                    # 1. Merkez depoya geri ekle
                    db.execute_query("""
                        UPDATE WarehouseProducts 
                        SET stock_quantity = stock_quantity + %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (float(qty), p_id))

                    # 2. Hedef şubenin stoğundan düş
                    if target_branch_id and wp:
                        db.execute_query("""
                            UPDATE Products 
                            SET stock_quantity = stock_quantity - %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE branch_id = %s AND LOWER(TRIM(name)) = LOWER(TRIM(%s)) AND is_active = TRUE
                        """, (float(qty), target_branch_id, wp['name']))

                # Hareketi sil
                db.execute_query("DELETE FROM WarehouseStockMovements WHERE id = %s", (movement_id,))

            type_label = "Giriş" if m_type == 'IN' else "Çıkış" if m_type == 'OUT' else "Sevkiyat"
            logger.info(f"🗑️ Depo Hareketi Silindi (ID={movement_id}, Tür={m_type}): {prod_name} - Miktar: {qty}")
            return True, f"'{prod_name}' {type_label} hareketi başarıyla silindi ve stoklar otomatik geri alındı."
        except Exception as e:
            logger.error(f"delete_stock_movement hatası: {e}")
            return False, f"Hareket silinirken hata oluştu: {str(e)}"

    def update_stock_movement(self, movement_id: int, data: Dict, user_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Depo hareketini günceller ve miktar/hedef şube farklarını ilgili stoklara yansıtır.
        """
        try:
            mov = db.fetch_one("SELECT * FROM WarehouseStockMovements WHERE id = %s", (movement_id,))
            if not mov:
                return False, "Hareket kaydı bulunamadı!"

            m_type = mov.get('movement_type')
            p_id = mov.get('warehouse_product_id')
            old_qty = to_decimal(mov.get('quantity', 0))
            new_qty = to_decimal(data.get('quantity', old_qty))
            if new_qty <= Decimal('0'):
                return False, "Miktar 0'dan büyük olmalıdır!"

            qty_diff = new_qty - old_qty
            old_branch_id = mov.get('target_branch_id')
            new_branch_id = data.get('target_branch_id', old_branch_id)
            if new_branch_id is not None:
                new_branch_id = int(new_branch_id) if new_branch_id else None

            unit = data.get('unit') or mov.get('unit') or 'Adet'
            doc_no = data.get('document_no') if 'document_no' in data else mov.get('document_no')
            supp_name = data.get('supplier_name') if 'supplier_name' in data else mov.get('supplier_name')
            desc = data.get('description') if 'description' in data else mov.get('description')
            mov_date = data.get('movement_date') or mov.get('movement_date')

            wp = db.fetch_one("SELECT * FROM WarehouseProducts WHERE id = %s", (p_id,))
            prod_name = wp['name'] if wp else "Ürün"

            with db.transaction():
                if m_type == 'IN':
                    # Giriş miktarı değişti: Merkez depoya diff ekle
                    if qty_diff != Decimal('0'):
                        db.execute_query("""
                            UPDATE WarehouseProducts 
                            SET stock_quantity = stock_quantity + %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (float(qty_diff), p_id))

                elif m_type == 'OUT':
                    # Çıkış miktarı değişti: Merkez depodan diff düş
                    if qty_diff != Decimal('0'):
                        db.execute_query("""
                            UPDATE WarehouseProducts 
                            SET stock_quantity = stock_quantity - %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (float(qty_diff), p_id))

                elif m_type == 'DISPATCH':
                    # Sevkiyat miktarı veya şubesi değişti
                    # 1. Merkez depo stoğu güncelle
                    if qty_diff != Decimal('0'):
                        db.execute_query("""
                            UPDATE WarehouseProducts 
                            SET stock_quantity = stock_quantity - %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (float(qty_diff), p_id))

                    # 2. Şube stoğunu güncelle
                    if wp:
                        if old_branch_id == new_branch_id:
                            if qty_diff != Decimal('0') and new_branch_id:
                                db.execute_query("""
                                    UPDATE Products 
                                    SET stock_quantity = stock_quantity + %s,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE branch_id = %s AND LOWER(TRIM(name)) = LOWER(TRIM(%s)) AND is_active = TRUE
                                """, (float(qty_diff), new_branch_id, wp['name']))
                        else:
                            # Eski şubeden eski miktarı geri al
                            if old_branch_id:
                                db.execute_query("""
                                    UPDATE Products 
                                    SET stock_quantity = stock_quantity - %s,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE branch_id = %s AND LOWER(TRIM(name)) = LOWER(TRIM(%s)) AND is_active = TRUE
                                """, (float(old_qty), old_branch_id, wp['name']))
                            # Yeni şubeye yeni miktarı ekle
                            if new_branch_id:
                                b_prod = db.fetch_one("""
                                    SELECT id FROM Products 
                                    WHERE branch_id = %s AND LOWER(TRIM(name)) = LOWER(TRIM(%s)) AND is_active = TRUE
                                """, (new_branch_id, wp['name']))
                                if b_prod:
                                    db.execute_query("""
                                        UPDATE Products 
                                        SET stock_quantity = stock_quantity + %s,
                                            updated_at = CURRENT_TIMESTAMP
                                        WHERE id = %s
                                    """, (float(new_qty), b_prod['id']))
                                else:
                                    b_code = f"PRD-B{new_branch_id}-{wp['id']:03d}"
                                    db.execute_query("""
                                        INSERT INTO Products (
                                            branch_id, product_code, name, category, unit,
                                            purchase_price, sale_price, stock_quantity, critical_stock, is_active
                                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 5, TRUE)
                                    """, (
                                        new_branch_id, b_code, wp['name'],
                                        wp.get('category', 'Hammadde'), unit,
                                        float(wp.get('purchase_price', 0)), float(wp.get('sale_price', 0)),
                                        float(new_qty)
                                    ))

                # Hareketi güncelle
                db.execute_query("""
                    UPDATE WarehouseStockMovements 
                    SET quantity = %s,
                        unit = %s,
                        document_no = %s,
                        supplier_name = %s,
                        description = %s,
                        target_branch_id = %s,
                        movement_date = %s
                    WHERE id = %s
                """, (
                    float(new_qty), unit, doc_no, supp_name, desc,
                    new_branch_id, mov_date, movement_id
                ))

            logger.info(f"✏️ Depo Hareketi Güncellendi (ID={movement_id}): {prod_name} Yeni Miktar={new_qty}")
            return True, f"'{prod_name}' hareket kaydı ve stokları başarıyla güncellendi."
        except Exception as e:
            logger.error(f"update_stock_movement hatası: {e}")
            return False, f"Güncelleme hatası: {str(e)}"


warehouse_service = WarehouseService()
