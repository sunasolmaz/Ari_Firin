# src/services/stock_count_service.py
"""
Ay Sonu Stok ve Sayım Takibi Servisi
Şubelerin ay sonu stok sayımlarını, Excel formatındaki hesaplamalarla
(Toplam Mevcut, Satılan/Çıkan, Kalan Değer, Satılan Değer)
ve Gelen-Giden hareket loglarıyla yönetir.
"""

from typing import List, Dict, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, date, timedelta
import calendar
import os

from ..core.database import db
from ..core.logger import logger
from ..core.decimal_utils import to_decimal, round_currency


DEFAULT_STOCK_COUNT_TEMPLATE = []


class StockCountService:
    """Ay Sonu Stok Sayımı ve Gelen-Giden Takip Servisi"""

    def __init__(self):
        try:
            db.ensure_stock_count_tables()
        except Exception as e:
            logger.warning(f"StockCountService tablo denetim uyarısı: {e}")

    # ==================== DÖNEM (SESSION) YÖNETİMİ ====================

    def get_sessions(
        self,
        branch_id: int,
        mode: str = "all",
        target_date_str: Optional[str] = None
    ) -> List[Dict]:
        """
        Bir şubeye ait sayım dönemlerini listeler.
        mode: 'daily', 'weekly', 'monthly', 'all'
        target_date_str: 'YYYY-MM-DD'
        """
        try:
            db.ensure_stock_count_tables()
            date_clause = ""
            params = [branch_id]

            if mode != "all" and target_date_str:
                target_dt = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                if mode == "daily":
                    date_clause = "AND s.created_at::date = %s"
                    params.append(target_dt.strftime("%Y-%m-%d"))
                elif mode == "weekly":
                    start_dt = target_dt - timedelta(days=target_dt.weekday())
                    end_dt = start_dt + timedelta(days=6)
                    date_clause = "AND s.created_at::date BETWEEN %s AND %s"
                    params.extend([start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")])
                elif mode == "monthly":
                    start_dt = target_dt.replace(day=1)
                    _, last_day = calendar.monthrange(target_dt.year, target_dt.month)
                    end_dt = target_dt.replace(day=last_day)
                    date_clause = "AND s.created_at::date BETWEEN %s AND %s"
                    params.extend([start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")])
                elif mode == "yearly":
                    start_dt = date(target_dt.year, 1, 1)
                    end_dt = date(target_dt.year, 12, 31)
                    date_clause = "AND s.created_at::date BETWEEN %s AND %s"
                    params.extend([start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")])

            sql = f"""
                SELECT 
                    s.id,
                    s.branch_id,
                    s.period_name,
                    s.status,
                    s.notes,
                    s.created_at,
                    s.updated_at,
                    u.full_name as created_by_name,
                    COUNT(i.id) as item_count,
                    COALESCE(SUM(COALESCE(i.opening_stock, 0) + COALESCE(i.incoming_stock, 0)), 0) as total_available_qty,
                    COALESCE(SUM(COALESCE(i.physical_count, 0)), 0) as total_physical_qty,
                    COALESCE(SUM(COALESCE(i.sold_out, 0)), 0) as total_sold_qty,
                    COALESCE(SUM(COALESCE(i.transfer_out_qty, 0)), 0) as total_transfer_out_qty,
                    COALESCE(SUM(COALESCE(i.waste_qty, 0)), 0) as total_waste_qty,
                    COALESCE(SUM(COALESCE(i.waste_value, 0)), 0) as total_waste_value,
                    COALESCE(SUM(COALESCE(i.remaining_value, 0)), 0) as total_remaining_value,
                    COALESCE(SUM(COALESCE(i.sold_value, 0)), 0) as total_sold_value
                FROM StockCountSessions s
                LEFT JOIN Users u ON s.created_by = u.id
                LEFT JOIN StockCountItems i ON s.id = i.session_id
                WHERE s.branch_id = %s {date_clause}
                GROUP BY s.id, u.full_name
                ORDER BY s.created_at DESC, s.id DESC
            """
            rows = db.fetch_all(sql, tuple(params)) or []
            res = []
            for r in rows:
                d = dict(r)
                d['total_available_qty'] = float(d.get('total_available_qty') or 0)
                d['total_physical_qty'] = float(d.get('total_physical_qty') or 0)
                d['total_sold_qty'] = float(d.get('total_sold_qty') or 0)
                d['total_transfer_out_qty'] = float(d.get('total_transfer_out_qty') or 0)
                d['total_waste_qty'] = float(d.get('total_waste_qty') or 0)
                d['total_waste_value'] = float(d.get('total_waste_value') or 0)
                d['total_remaining_value'] = float(d.get('total_remaining_value') or 0)
                d['total_sold_value'] = float(d.get('total_sold_value') or 0)
                d['item_count'] = int(d.get('item_count') or 0)
                res.append(d)
            return res
        except Exception as e:
            logger.error(f"get_sessions hatası: {e}")
            return []

    def get_stock_overview(
        self,
        branch_id: int,
        mode: str = "daily",
        target_date_str: Optional[str] = None
    ) -> Dict:
        """Belirtilen dönem (günlük/haftalık/aylık/tüm) için stok özetini ve metriklerini döndürür"""
        try:
            if not target_date_str:
                target_date_str = datetime.now().strftime("%Y-%m-%d")

            target_dt = datetime.strptime(target_date_str, "%Y-%m-%d").date()

            if mode == "weekly":
                start_dt = target_dt - timedelta(days=target_dt.weekday())
                end_dt = start_dt + timedelta(days=6)
                title = f"{start_dt.strftime('%d.%m.%Y')} - {end_dt.strftime('%d.%m.%Y')} Haftası Stok Durumu"
            elif mode == "monthly":
                start_dt = target_dt.replace(day=1)
                _, last_day = calendar.monthrange(target_dt.year, target_dt.month)
                end_dt = target_dt.replace(day=last_day)
                aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
                title = f"{aylar[target_dt.month - 1]} {target_dt.year} Ayı Stok Durumu"
            elif mode == "yearly":
                start_dt = date(target_dt.year, 1, 1)
                end_dt = date(target_dt.year, 12, 31)
                title = f"{target_dt.year} Yılı Stok Durumu"
            elif mode == "all":
                title = "Tüm Kayıtlı Sayım Dönemleri"
            else:  # daily
                title = f"{target_dt.strftime('%d.%m.%Y')} Günlük Stok Durumu"

            sessions = self.get_sessions(branch_id, mode=mode, target_date_str=target_date_str)

            total_remaining = sum(s['total_remaining_value'] for s in sessions)
            total_sold_val = sum(s['total_sold_value'] for s in sessions)
            total_waste_val = sum(s['total_waste_value'] for s in sessions)
            total_waste_qty = sum(s['total_waste_qty'] for s in sessions)
            total_avail_qty = sum(s['total_available_qty'] for s in sessions)
            total_sold_qty = sum(s['total_sold_qty'] for s in sessions)

            return {
                "title": title,
                "mode": mode,
                "target_date": target_date_str,
                "sessions": sessions,
                "session_count": len(sessions),
                "total_remaining_value": total_remaining,
                "total_sold_value": total_sold_val,
                "total_waste_value": total_waste_val,
                "total_waste_qty": total_waste_qty,
                "total_available_qty": total_avail_qty,
                "total_sold_qty": total_sold_qty
            }
        except Exception as e:
            logger.error(f"get_stock_overview hatası: {e}")
            return {
                "title": "Stok Durumu",
                "mode": mode,
                "target_date": target_date_str,
                "sessions": [],
                "session_count": 0,
                "total_remaining_value": 0.0,
                "total_sold_value": 0.0,
                "total_waste_value": 0.0,
                "total_waste_qty": 0.0,
                "total_available_qty": 0.0,
                "total_sold_qty": 0.0
            }

    def get_session(self, session_id: int) -> Optional[Dict]:
        """Belirtilen dönemin bilgilerini döndürür"""
        try:
            sql = """
                SELECT 
                    s.id,
                    s.branch_id,
                    s.period_name,
                    s.status,
                    s.notes,
                    s.created_at,
                    s.updated_at,
                    u.full_name as created_by_name,
                    b.name as branch_name
                FROM StockCountSessions s
                LEFT JOIN Users u ON s.created_by = u.id
                LEFT JOIN Branches b ON s.branch_id = b.id
                WHERE s.id = %s
            """
            row = db.fetch_one(sql, (session_id,))
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_session hatası: {e}")
            return None

    def get_template_items(self) -> List[Dict]:
        """Kayıtlı şablon ürün listesini döndürür"""
        try:
            db.ensure_stock_count_tables()
            items = db.fetch_all("""
                SELECT category, product_name, unit, display_order 
                FROM StockCountTemplateItems 
                WHERE is_active = TRUE 
                ORDER BY display_order ASC, id ASC
            """) or []
            return [dict(x) for x in items]
        except Exception as e:
            logger.error(f"get_template_items hatası: {e}")
            return []

    def create_session(
        self,
        branch_id: int,
        period_name: str,
        user_id: Optional[int] = None,
        copy_from_previous: bool = False,
        load_template_items: bool = False
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Yeni bir sayım dönemi başlatır.
        Varsayılan olarak boş sayım tablosu başlatır; kullanıcı dilediği ürünleri teker teker ekler.
        Eğer copy_from_previous=True ise, önceki dönemin ürünlerini ve 'Fiziksel Sayım' miktarını
        bu dönemin 'Ay Başı Stok'u olarak devralır.
        Eğer load_template_items=True ise standart şablon ürünlerini ekler.
        """
        try:
            p_name = (period_name or "").strip()
            if not p_name:
                return False, "Dönem adı boş bırakılamaz! (Örn: Ekim 2026)", None

            db.ensure_stock_count_tables()

            # Bu şubede aynı isimde dönem var mı kontrolü
            existing = db.fetch_one(
                "SELECT id FROM StockCountSessions WHERE branch_id = %s AND period_name = %s LIMIT 1",
                (branch_id, p_name)
            )
            if existing:
                return False, f"'{p_name}' dönemi bu şube için zaten mevcut!", None

            # Önceki son dönemi bul (devir için)
            prev_session = None
            if copy_from_previous:
                prev_session = db.fetch_one("""
                    SELECT id FROM StockCountSessions 
                    WHERE branch_id = %s 
                    ORDER BY created_at DESC, id DESC 
                    LIMIT 1
                """, (branch_id,))

            items_to_insert = []
            if copy_from_previous and prev_session:
                prev_items = db.fetch_all("""
                    SELECT category, product_name, unit, physical_count, unit_cost, display_order 
                    FROM StockCountItems 
                    WHERE session_id = %s
                    ORDER BY display_order ASC, id ASC
                """, (prev_session['id'],)) or []
                for pi in prev_items:
                    items_to_insert.append({
                        'category': pi.get('category') or '',
                        'product_name': pi.get('product_name') or '',
                        'unit': pi.get('unit') or 'Adet',
                        'opening': float(pi.get('physical_count') or 0.0),
                        'cost': float(pi.get('unit_cost') or 0.0),
                        'order': int(pi.get('display_order') or 0)
                    })
            elif load_template_items:
                template_items = self.get_template_items()
                for itm in template_items:
                    items_to_insert.append({
                        'category': itm.get('category') or '',
                        'product_name': itm.get('product_name') or '',
                        'unit': itm.get('unit') or 'Adet',
                        'opening': 0.0,
                        'cost': 0.0,
                        'order': int(itm.get('display_order') or 0)
                    })

            with db.transaction():
                new_session_id = db.execute_query("""
                    INSERT INTO StockCountSessions (branch_id, period_name, status, created_by)
                    VALUES (%s, %s, 'Draft', %s)
                    RETURNING id
                """, (branch_id, p_name, user_id))

                if not new_session_id:
                    raise ValueError("Dönem kaydı oluşturulamadı!")

                for item in items_to_insert:
                    cat = item['category']
                    pname = item['product_name']
                    unit = item['unit']
                    opening = item['opening']
                    cost = item['cost']
                    order = item['order']

                    incoming = 0.0
                    physical = opening
                    sold_out = 0.0
                    rem_val = physical * cost
                    sold_val = 0.0

                    db.execute_query("""
                        INSERT INTO StockCountItems (
                            session_id, category, product_name, unit,
                            opening_stock, incoming_stock, physical_count,
                            sold_out, unit_cost, remaining_value, sold_value,
                            display_order
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        new_session_id, cat, pname, unit,
                        opening, incoming, physical,
                        sold_out, cost, rem_val, sold_val,
                        order
                    ))

            created = self.get_session(new_session_id)
            logger.info(f"✅ Yeni sayım dönemi başlatıldı: ID={new_session_id}, Şube={branch_id}, Dönem={p_name}, Kalem={len(items_to_insert)}")
            if len(items_to_insert) > 0:
                msg = f"'{p_name}' dönemi ve {len(items_to_insert)} kalem başarıyla oluşturuldu."
            else:
                msg = f"'{p_name}' dönemi boş olarak başlatıldı. '➕ Yeni Satır / Ürün Ekle' butonuyla ürünlerinizi ekleyebilirsiniz."
            return True, msg, created
        except Exception as e:
            logger.error(f"create_session hatası: {e}")
            return False, f"Dönem oluşturulamadı: {str(e)}", None

    def approve_session(self, session_id: int) -> Tuple[bool, str]:
        """Dönemi onaylar (Approved durumuna getirir)"""
        try:
            db.execute_query("""
                UPDATE StockCountSessions 
                SET status = 'Approved', updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (session_id,))
            logger.info(f"✅ Sayım dönemi onaylandı: ID={session_id}")
            return True, "Sayım dönemi başarıyla onaylandı ve kilitlendi."
        except Exception as e:
            logger.error(f"approve_session hatası: {e}")
            return False, f"Onaylama hatası: {str(e)}"

    def reopen_session(self, session_id: int) -> Tuple[bool, str]:
        """Dönemi tekrar düzenlemeye açar (Draft durumuna getirir)"""
        try:
            db.execute_query("""
                UPDATE StockCountSessions 
                SET status = 'Draft', updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (session_id,))
            logger.info(f"🔄 Sayım dönemi tekrar taslağa alındı: ID={session_id}")
            return True, "Sayım dönemi düzenlemeye açıldı."
        except Exception as e:
            logger.error(f"reopen_session hatası: {e}")
            return False, f"İşlem hatası: {str(e)}"

    def delete_session(self, session_id: int) -> Tuple[bool, str]:
        """Dönemi ve altındaki tüm kalemleri siler"""
        try:
            rowcount = db.execute_query("DELETE FROM StockCountSessions WHERE id = %s", (session_id,))
            if rowcount and rowcount > 0:
                logger.info(f"🗑️ Sayım dönemi silindi: ID={session_id}")
                return True, "Sayım dönemi ve tüm verileri silindi."
            return False, "Silinecek dönem bulunamadı."
        except Exception as e:
            logger.error(f"delete_session hatası: {e}")
            return False, f"Silme hatası: {str(e)}"

    # ==================== SAYIM KALEMLERİ (ITEMS) ====================

    def get_session_items(self, session_id: int) -> List[Dict]:
        """Bir döneme ait tüm sayım kalemlerini getirir ve formülleri hesaplar"""
        try:
            sql = """
                SELECT 
                    id,
                    session_id,
                    category,
                    product_name,
                    unit,
                    opening_stock,
                    incoming_stock,
                    transfer_out_qty,
                    waste_qty,
                    waste_value,
                    physical_count,
                    sold_out,
                    unit_cost,
                    remaining_value,
                    sold_value,
                    display_order
                FROM StockCountItems
                WHERE session_id = %s
                ORDER BY display_order ASC, id ASC
            """
            rows = db.fetch_all(sql, (session_id,)) or []
            res = []
            for r in rows:
                item = dict(r)
                opening = float(item.get('opening_stock') or 0.0)
                incoming = float(item.get('incoming_stock') or 0.0)
                physical = float(item.get('physical_count') or 0.0)
                cost = float(item.get('unit_cost') or 0.0)

                # Excel formülleri:
                transfer_out = float(item.get('transfer_out_qty') or 0.0)
                waste = float(item.get('waste_qty') or 0.0)
    
                # Toplam Mevcut = Ay Başı + Gelen
                total_avail = opening + incoming
                # Satılan / Çıkan = Toplam Mevcut - Fiziksel Sayım
                sold = max(0.0, total_avail - physical - transfer_out - waste)
                # Kalan Stok Değeri = Fiziksel Sayım * Birim Maliyet
                waste_val = waste * cost
                rem_val = physical * cost
                # Satılan Mal Değeri = Satılan * Birim Maliyet
                sold_val = sold * cost

                item['transfer_out_qty'] = transfer_out
                item['waste_qty'] = waste
                item['waste_value'] = waste_val
                item['opening_stock'] = opening
                item['incoming_stock'] = incoming
                item['total_available'] = total_avail
                item['physical_count'] = physical
                item['sold_out'] = sold
                item['unit_cost'] = cost
                item['remaining_value'] = rem_val
                item['sold_value'] = sold_val
                res.append(item)
            return res
        except Exception as e:
            logger.error(f"get_session_items hatası: {e}")
            return []

    def save_items(self, session_id: int, items_list: List[Dict]) -> Tuple[bool, str]:
        """
        Sayım tablosundaki tüm kalemleri toplu olarak kaydeder ve formülleri günceller.
        Excel formülleri garanti edilir.
        """
        try:
            if not items_list:
                return True, "Kaydedilecek kalem bulunamadı."

            with db.transaction():
                for idx, itm in enumerate(items_list):
                    item_id = itm.get('id')
                    cat = (itm.get('category') or '').strip()
                    pname = (itm.get('product_name') or '').strip()
                    unit = (itm.get('unit') or 'Adet').strip()
                    order = int(itm.get('display_order') or (idx + 1))

                    opening = float(itm.get('opening_stock') or 0.0)
                    incoming = float(itm.get('incoming_stock') or 0.0)
                    transfer_out = float(itm.get('transfer_out_qty') or 0.0)
                    waste = float(itm.get('waste_qty') or 0.0)
                    physical = float(itm.get('physical_count') or 0.0)
                    cost = float(itm.get('unit_cost') or 0.0)

                    # Otomatik Hesaplamalar:
                    total_avail = opening + incoming
                    sold = max(0.0, total_avail - physical - transfer_out - waste)
                    waste_val = waste * cost
                    rem_val = physical * cost
                    sold_val = sold * cost

                    if item_id:
                        db.execute_query("""
                            UPDATE StockCountItems SET
                                category = %s,
                                product_name = %s,
                                unit = %s,
                                opening_stock = %s,
                                incoming_stock = %s,
                                transfer_out_qty = %s,
                                waste_qty = %s,
                                waste_value = %s,
                                physical_count = %s,
                                sold_out = %s,
                                unit_cost = %s,
                                remaining_value = %s,
                                sold_value = %s,
                                display_order = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s AND session_id = %s
                        """, (
                            cat, pname, unit,
                            opening, incoming, transfer_out, waste, waste_val, physical,
                            sold, cost, rem_val, sold_val,
                            order, item_id, session_id
                        ))
                    else:
                        db.execute_query("""
                            INSERT INTO StockCountItems (
                                session_id, category, product_name, unit,
                                opening_stock, incoming_stock, transfer_out_qty, waste_qty, waste_value, physical_count,sold_out, unit_cost, remaining_value, sold_value,
                                display_order
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            session_id, cat, pname, unit,
                            opening, incoming, transfer_out, waste, waste_val, physical,
                            sold, cost, rem_val, sold_val,
                            order
                        ))

            logger.info(f"✅ Sayım kalemleri toplu kaydedildi: Session={session_id}, Adet={len(items_list)}")
            return True, "Sayım verileri ve hesaplamalar başarıyla kaydedildi."
        except Exception as e:
            logger.error(f"save_items hatası: {e}")
            return False, f"Kaydetme hatası: {str(e)}"

    def add_item(self, session_id: int, item_data: Dict) -> Tuple[bool, str, Optional[int]]:
        """
        Tabloya ürün/kalem ekler.
        Eğer ürün zaten tabloda varsa YENİ SATIR AÇMAZ; gelen/sayım miktarlarını mevcut satırın üzerine ekler/günceller.
        """
        try:
            cat = (item_data.get('category') or '').strip()
            pname = (item_data.get('product_name') or '').strip()
            unit = (item_data.get('unit') or 'Adet').strip()

            if not pname:
                return False, "Ürün adı boş bırakılamaz!", None

            opening = float(item_data.get('opening_stock') or 0.0)
            incoming = float(item_data.get('incoming_stock') or 0.0)
            transfer_out = float(item_data.get('transfer_out_qty') or 0.0)
            waste = float(item_data.get('waste_qty') or 0.0)
            physical = float(item_data.get('physical_count') or 0.0)
            cost = float(item_data.get('unit_cost') or 0.0)

            # 🔍 Bu ürün bu oturumda zaten var mı kontrol et (çift satır oluşmasını engelle)
            existing = db.fetch_one("""
                SELECT id, category, unit, opening_stock, incoming_stock, physical_count,
                       transfer_out_qty, waste_qty, unit_cost
                FROM StockCountItems
                WHERE session_id = %s AND LOWER(TRIM(product_name)) = LOWER(TRIM(%s))
                ORDER BY id ASC LIMIT 1
            """, (session_id, pname))

            if existing:
                item_id = existing['id']
                ex_opening = float(existing.get('opening_stock') or 0.0)
                ex_incoming = float(existing.get('incoming_stock') or 0.0)
                ex_physical = float(existing.get('physical_count') or 0.0)
                ex_transfer = float(existing.get('transfer_out_qty') or 0.0)
                ex_waste = float(existing.get('waste_qty') or 0.0)
                ex_cost = float(existing.get('unit_cost') or 0.0)

                # İmalattan veya şubeden ekstra gelen miktarı mevcut gelene ekle
                new_incoming = ex_incoming + incoming
                new_opening = opening if opening > 0 and ex_opening == 0 else ex_opening
                new_physical = physical if physical > 0 else ex_physical
                new_transfer = ex_transfer + transfer_out
                new_waste = ex_waste + waste if waste > 0 else ex_waste
                new_cost = cost if cost > 0 else ex_cost

                total_avail = new_opening + new_incoming
                sold = max(0.0, total_avail - new_physical - new_transfer - new_waste)
                waste_val = new_waste * new_cost
                rem_val = new_physical * new_cost
                sold_val = sold * new_cost

                db.execute_query("""
                    UPDATE StockCountItems
                    SET incoming_stock = %s,
                        opening_stock = %s,
                        physical_count = %s,
                        transfer_out_qty = %s,
                        waste_qty = %s,
                        waste_value = %s,
                        sold_out = %s,
                        unit_cost = %s,
                        remaining_value = %s,
                        sold_value = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    new_incoming, new_opening, new_physical, new_transfer,
                    new_waste, waste_val, sold, new_cost, rem_val, sold_val,
                    item_id
                ))

                if waste > 0:
                    try:
                        m_desc = f"Gün Sonu Fire | {pname} (+{waste} {unit}) - Maliyet: {new_cost:.2f} TL"
                        db.execute_query("""
                            INSERT INTO StockMovements (
                                session_id, date, category, product_name,
                                movement_type, quantity, unit, description
                            ) VALUES (%s, CURRENT_DATE, %s, %s, 'Zayi', %s, %s, %s)
                        """, (session_id, cat or existing.get('category'), pname, waste, unit, m_desc))
                    except Exception as me:
                        logger.warning(f"add_item fire güncelleme hatası: {me}")

                msg = f"'{pname}' zaten mevcuttu; gelen miktar ({incoming:g}) mevcut satırın üzerine eklendi (Toplam Gelen: {new_incoming:g})."
                return True, msg, item_id

            total_avail = opening + incoming
            sold = max(0.0, total_avail - physical - transfer_out - waste)
            waste_val = waste * cost
            rem_val = physical * cost
            sold_val = sold * cost

            # Son sıra numarasını bul
            max_order_row = db.fetch_one(
                "SELECT COALESCE(MAX(display_order), 0) as m FROM StockCountItems WHERE session_id = %s",
                (session_id,)
            )
            next_order = (max_order_row['m'] if max_order_row else 0) + 1

            new_id = db.execute_query("""
                INSERT INTO StockCountItems (
                    session_id, category, product_name, unit,
                    opening_stock, incoming_stock, transfer_out_qty, waste_qty, waste_value, physical_count,
                    sold_out, unit_cost, remaining_value, sold_value,
                    display_order
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                session_id, cat, pname, unit,
                opening, incoming, transfer_out, waste, waste_val, physical,
                sold, cost, rem_val, sold_val,
                next_order
            ))

            if new_id and waste > 0:
                try:
                    m_desc = f"Gün Sonu Fire | {pname} ({waste} {unit}) - Maliyet: {cost:.2f} TL"
                    db.execute_query("""
                        INSERT INTO StockMovements (
                            session_id, date, category, product_name,
                            movement_type, quantity, unit, description
                        ) VALUES (%s, CURRENT_DATE, %s, %s, 'Zayi', %s, %s, %s)
                    """, (session_id, cat, pname, waste, unit, m_desc))
                except Exception as me:
                    logger.warning(f"add_item fire hareketi eklenemedi: {me}")

            return True, f"'{pname}' kalemi eklendi.", new_id
        except Exception as e:
            logger.error(f"add_item hatası: {e}")
            return False, f"Kalem eklenemedi: {str(e)}", None

    def update_item(self, item_id: int, item_data: Dict) -> Tuple[bool, str]:
        """Tek bir ürün/kalem kaydını günceller ve formülleri anında yeniden hesaplar"""
        try:
            cat = (item_data.get('category') or '').strip()
            pname = (item_data.get('product_name') or '').strip()
            unit = (item_data.get('unit') or 'Adet').strip()

            if not pname:
                return False, "Ürün adı boş bırakılamaz!"

            opening = float(item_data.get('opening_stock') or 0.0)
            incoming = float(item_data.get('incoming_stock') or 0.0)
            transfer_out = float(item_data.get('transfer_out_qty') or 0.0)
            waste = float(item_data.get('waste_qty') or 0.0)
            physical = float(item_data.get('physical_count') or 0.0)
            cost = float(item_data.get('unit_cost') or 0.0)

            total_avail = opening + incoming
            sold = max(0.0, total_avail - physical - transfer_out - waste)
            waste_val = waste * cost
            rem_val = physical * cost
            sold_val = sold * cost

            db.execute_query("""
                UPDATE StockCountItems
                SET category = %s,
                    product_name = %s,
                    unit = %s,
                    opening_stock = %s,
                    incoming_stock = %s,
                    transfer_out_qty = %s,
                    waste_qty = %s,
                    waste_value = %s,
                    physical_count = %s,
                    sold_out = %s,
                    unit_cost = %s,
                    remaining_value = %s,
                    sold_value = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                cat, pname, unit,
                opening, incoming, transfer_out, waste, waste_val, physical,
                sold, cost, rem_val, sold_val,
                item_id
            ))
            return True, f"'{pname}' kalemi güncellendi."
        except Exception as e:
            logger.error(f"update_item hatası: {e}")
            return False, f"Güncelleme hatası: {str(e)}"

    def delete_item(self, item_id: int) -> Tuple[bool, str]:
        """Sayım tablosundan bir ürünü siler"""
        try:
            rowcount = db.execute_query("DELETE FROM StockCountItems WHERE id = %s", (item_id,))
            if rowcount and rowcount > 0:
                return True, "Kalem tablodan silindi."
            return False, "Kalem bulunamadı."
        except Exception as e:
            logger.error(f"delete_item hatası: {e}")
            return False, f"Silme hatası: {str(e)}"

    def calculate_totals(self, session_id: int) -> Dict:
        """Döneme ait alt toplamları hesaplar"""
        try:
            items = self.get_session_items(session_id)
            tot_items = len(items)
            tot_opening = sum(i['opening_stock'] for i in items)
            tot_incoming = sum(i['incoming_stock'] for i in items)
            tot_avail = sum(i['total_available'] for i in items)
            tot_physical = sum(i['physical_count'] for i in items)
            tot_transfer_out = sum(i['transfer_out_qty'] for i in items)
            tot_waste = sum(i['waste_qty'] for i in items)
            tot_waste_value = sum(i['waste_value'] for i in items)
            tot_sold = sum(i['sold_out'] for i in items)
            tot_remaining_val = sum(i['remaining_value'] for i in items)
            tot_sold_val = sum(i['sold_value'] for i in items)

            return {
                'total_items': tot_items,
                'total_opening_stock': tot_opening,
                'total_incoming_stock': tot_incoming,
                'total_available': tot_avail,
                'total_physical_count': tot_physical,
                'total_transfer_out': tot_transfer_out,
                'total_waste': tot_waste,
                'total_waste_value': tot_waste_value,
                'total_sold_out': tot_sold,
                'total_remaining_value': tot_remaining_val,
                'total_sold_value': tot_sold_val
            }
        except Exception as e:
            logger.error(f"calculate_totals hatası: {e}")
            return {
                'total_items': 0,
                'total_opening_stock': 0.0,
                'total_incoming_stock': 0.0,
                'total_available': 0.0,
                'total_physical_count': 0.0,
                'total_sold_out': 0.0,
                'total_remaining_value': 0.0,
                'total_sold_value': 0.0
            }

    # ==================== GELEN - GİDEN HAREKET LOGLARI ====================

    def get_movements(self, session_id: int) -> List[Dict]:
        """Döneme ait tüm hareket loglarını döndürür"""
        try:
            sql = """
                SELECT 
                    id,
                    session_id,
                    date,
                    category,
                    product_name,
                    movement_type,
                    quantity,
                    unit,
                    description,
                    created_at
                FROM StockMovements
                WHERE session_id = %s
                ORDER BY date DESC, id DESC
            """
            rows = db.fetch_all(sql, (session_id,)) or []
            res = []
            for r in rows:
                d = dict(r)
                d['quantity'] = float(d.get('quantity') or 0.0)
                res.append(d)
            return res
        except Exception as e:
            logger.error(f"get_movements hatası: {e}")
            return []

    def add_movement(self, session_id: int, movement_data: Dict) -> Tuple[bool, str, Optional[int]]:
        """
        Yeni bir hareket kaydı (Gelen/Çıkan/Zayi) ekler.
        Eğer işlem türü 'Gelen' ise, ilgili ürünün sayım tablosundaki
        'Gelen (Giren)' miktarına otomatik ekler ve formülleri günceller!
        """
        try:
            m_date = movement_data.get('date') or datetime.now().date().strftime('%Y-%m-%d')
            cat = (movement_data.get('category') or '').strip()
            pname = (movement_data.get('product_name') or '').strip()
            m_type = (movement_data.get('movement_type') or 'Gelen').strip()
            qty = float(movement_data.get('quantity') or 0.0)
            unit = (movement_data.get('unit') or 'Adet').strip()
            desc = (movement_data.get('description') or '').strip()

            if not pname:
                return False, "Ürün adı boş bırakılamaz!", None

            if qty <= 0:
                return False, "Miktar 0'dan büyük olmalıdır!", None

            with db.transaction():
                new_id = db.execute_query("""
                    INSERT INTO StockMovements (
                        session_id, date, category, product_name,
                        movement_type, quantity, unit, description
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    session_id, m_date, cat, pname,
                    m_type, qty, unit, desc
                ))

                # Eğer 'Gelen' ise sayım tablosunda aynı isimli ürünün 'incoming_stock'unu artır
                if m_type == 'Gelen':
                    matching_item = db.fetch_one("""
                        SELECT id, opening_stock, incoming_stock, physical_count, unit_cost
                        FROM StockCountItems
                        WHERE session_id = %s AND LOWER(TRIM(product_name)) = LOWER(TRIM(%s))
                        LIMIT 1
                    """, (session_id, pname))

                    if matching_item:
                        new_incoming = float(matching_item.get('incoming_stock') or 0.0) + qty
                        opening = float(matching_item.get('opening_stock') or 0.0)
                        physical = float(matching_item.get('physical_count') or 0.0)
                        cost = float(matching_item.get('unit_cost') or 0.0)

                        total_avail = opening + new_incoming
                        sold = max(0.0, total_avail - physical)
                        rem_val = physical * cost
                        sold_val = sold * cost

                        db.execute_query("""
                            UPDATE StockCountItems SET
                                incoming_stock = %s,
                                sold_out = %s,
                                remaining_value = %s,
                                sold_value = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (new_incoming, sold, rem_val, sold_val, matching_item['id']))

            logger.info(f"✅ Hareket kaydı eklendi: ID={new_id}, Tip={m_type}, Ürün={pname}, Miktar={qty}")
            return True, f"'{pname}' için {qty} {unit} {m_type} kaydı eklendi.", new_id
        except Exception as e:
            logger.error(f"add_movement hatası: {e}")
            return False, f"Hareket kaydı eklenemedi: {str(e)}", None

    def delete_movement(self, movement_id: int) -> Tuple[bool, str]:
        """Hareket kaydını siler"""
        try:
            # Önce hareketi bul
            mov = db.fetch_one("SELECT * FROM StockMovements WHERE id = %s", (movement_id,))
            if not mov:
                return False, "Silinecek hareket bulunamadı."

            session_id = mov.get('session_id')
            pname = mov.get('product_name')
            m_type = mov.get('movement_type')
            qty = float(mov.get('quantity') or 0.0)

            with db.transaction():
                db.execute_query("DELETE FROM StockMovements WHERE id = %s", (movement_id,))

                # Eğer 'Gelen' silindiyse sayım tablosundaki incoming_stock'tan düş
                if m_type == 'Gelen' and session_id and pname:
                    matching_item = db.fetch_one("""
                        SELECT id, opening_stock, incoming_stock, physical_count, unit_cost
                        FROM StockCountItems
                        WHERE session_id = %s AND LOWER(TRIM(product_name)) = LOWER(TRIM(%s))
                        LIMIT 1
                    """, (session_id, pname))

                    if matching_item:
                        new_incoming = max(0.0, float(matching_item.get('incoming_stock') or 0.0) - qty)
                        opening = float(matching_item.get('opening_stock') or 0.0)
                        physical = float(matching_item.get('physical_count') or 0.0)
                        cost = float(matching_item.get('unit_cost') or 0.0)

                        total_avail = opening + new_incoming
                        sold = max(0.0, total_avail - physical)
                        rem_val = physical * cost
                        sold_val = sold * cost

                        db.execute_query("""
                            UPDATE StockCountItems SET
                                incoming_stock = %s,
                                sold_out = %s,
                                remaining_value = %s,
                                sold_value = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (new_incoming, sold, rem_val, sold_val, matching_item['id']))

            return True, "Hareket kaydı silindi."
        except Exception as e:
            logger.error(f"delete_movement hatası: {e}")
            return False, f"Silme hatası: {str(e)}"

    # ==================== EXCEL IMPORT & EXPORT ====================

    def export_to_excel(self, session_id: int, file_path: str) -> Tuple[bool, str]:
        """
        Dönem verilerini Excel şablonunun birebir kopyası olarak .xlsx dosyasına aktarır.
        """
        try:
            session = self.get_session(session_id)
            if not session:
                return False, "Sayım dönemi bulunamadı!"

            items = self.get_session_items(session_id)
            movements = self.get_movements(session_id)

            wb = openpyxl.Workbook()

            # 1. SEKME: Stok ve Sayım Takibi
            ws1 = wb.active
            ws1.title = "Stok ve Sayım Takibi"

            # Başlık stilleri
            font_title = Font(name="Calibri", size=16, bold=True, color="1E3A8A")
            font_sub = Font(name="Calibri", size=11, italic=True, color="475569")
            font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            fill_header = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            fill_calc = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
            fill_total = PatternFill(start_color="FEF08A", end_color="FEF08A", fill_type="solid")
            font_total = Font(name="Calibri", size=11, bold=True, color="000000")

            thin_border = Border(
                left=Side(style='thin', color='CBD5E1'),
                right=Side(style='thin', color='CBD5E1'),
                top=Side(style='thin', color='CBD5E1'),
                bottom=Side(style='thin', color='CBD5E1')
            )

            # R1: Başlık
            ws1.merge_cells("A1:K1")
            cell_title = ws1["A1"]
            cell_title.value = "ARI FIRIN - AY SONU STOK VE SAYIM FORMU"
            cell_title.font = font_title
            cell_title.alignment = Alignment(horizontal="center", vertical="center")
            ws1.row_dimensions[1].height = 35

            # R2: Bilgi
            ws1.merge_cells("A2:K2")
            cell_sub = ws1["A2"]
            p_name = session.get('period_name', '')
            b_name = session.get('branch_name', '')
            c_by = session.get('created_by_name', '')
            cell_sub.value = f"Şube: {b_name} | Dönem: {p_name} | Sayımı Yapan: {c_by}"
            cell_sub.font = font_sub
            cell_sub.alignment = Alignment(horizontal="center", vertical="center")
            ws1.row_dimensions[2].height = 20

            # R4: Sütun Başlıkları
            headers = [
                "Kategori", "Ürün Adı", "Birim", "Ay Başı Stok", "Gelen (Giren)",
                "Toplam Mevcut", "Fiziksel Sayım (Kalan)", "Satılan / Çıkan",
                "Birim Maliyet (TL)", "Kalan Stok Değeri (TL)", "Satılan Mal Değeri (TL)"
            ]
            ws1.row_dimensions[4].height = 28
            for col_num, h_text in enumerate(headers, 1):
                cell = ws1.cell(row=4, column=col_num)
                cell.value = h_text
                cell.font = font_header
                cell.fill = fill_header
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = thin_border

            # Satırlar
            start_row = 5
            for idx, itm in enumerate(items):
                r = start_row + idx
                ws1.row_dimensions[r].height = 20

                ws1.cell(row=r, column=1, value=itm.get('category', '')).border = thin_border
                ws1.cell(row=r, column=2, value=itm.get('product_name', '')).border = thin_border
                c_unit = ws1.cell(row=r, column=3, value=itm.get('unit', 'Adet'))
                c_unit.alignment = Alignment(horizontal="center")
                c_unit.border = thin_border

                c_open = ws1.cell(row=r, column=4, value=itm.get('opening_stock', 0.0))
                c_open.number_format = '#,##0.00'
                c_open.border = thin_border

                c_inc = ws1.cell(row=r, column=5, value=itm.get('incoming_stock', 0.0))
                c_inc.number_format = '#,##0.00'
                c_inc.border = thin_border

                # Formüller (Excel formülü)
                c_tot = ws1.cell(row=r, column=6, value=f"=D{r}+E{r}")
                c_tot.fill = fill_calc
                c_tot.number_format = '#,##0.00'
                c_tot.border = thin_border

                c_phy = ws1.cell(row=r, column=7, value=itm.get('physical_count', 0.0))
                c_phy.number_format = '#,##0.00'
                c_phy.border = thin_border

                c_sold = ws1.cell(row=r, column=8, value=f"=MAX(0, F{r}-G{r})")
                c_sold.fill = fill_calc
                c_sold.number_format = '#,##0.00'
                c_sold.border = thin_border

                c_cost = ws1.cell(row=r, column=9, value=itm.get('unit_cost', 0.0))
                c_cost.number_format = '#,##0.00 ₺'
                c_cost.border = thin_border

                c_remval = ws1.cell(row=r, column=10, value=f"=G{r}*I{r}")
                c_remval.fill = fill_calc
                c_remval.number_format = '#,##0.00 ₺'
                c_remval.border = thin_border

                c_soldval = ws1.cell(row=r, column=11, value=f"=H{r}*I{r}")
                c_soldval.fill = fill_calc
                c_soldval.number_format = '#,##0.00 ₺'
                c_soldval.border = thin_border

            # Genel Toplam Satırı
            last_item_row = start_row + len(items) - 1
            tot_row = last_item_row + 1
            ws1.row_dimensions[tot_row].height = 25

            ws1.merge_cells(f"A{tot_row}:C{tot_row}")
            cell_lbl = ws1.cell(row=tot_row, column=1, value="GENEL TOPLAM")
            cell_lbl.font = font_total
            cell_lbl.fill = fill_total
            cell_lbl.alignment = Alignment(horizontal="center", vertical="center")

            for c in range(1, 12):
                cell = ws1.cell(row=tot_row, column=c)
                cell.border = thin_border
                cell.fill = fill_total
                cell.font = font_total

            ws1.cell(row=tot_row, column=4, value=f"=SUM(D{start_row}:D{last_item_row})").number_format = '#,##0.00'
            ws1.cell(row=tot_row, column=5, value=f"=SUM(E{start_row}:E{last_item_row})").number_format = '#,##0.00'
            ws1.cell(row=tot_row, column=6, value=f"=SUM(F{start_row}:F{last_item_row})").number_format = '#,##0.00'
            ws1.cell(row=tot_row, column=7, value=f"=SUM(G{start_row}:G{last_item_row})").number_format = '#,##0.00'
            ws1.cell(row=tot_row, column=8, value=f"=SUM(H{start_row}:H{last_item_row})").number_format = '#,##0.00'
            ws1.cell(row=tot_row, column=10, value=f"=SUM(J{start_row}:J{last_item_row})").number_format = '#,##0.00 ₺'
            ws1.cell(row=tot_row, column=11, value=f"=SUM(K{start_row}:K{last_item_row})").number_format = '#,##0.00 ₺'

            # Otomatik sütun genişliği
            for col in ws1.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    v_str = str(cell.value or '')
                    if len(v_str) > max_len and not v_str.startswith('='):
                        max_len = len(v_str)
                ws1.column_dimensions[col_letter].width = max(max_len + 4, 13)

            # 2. SEKME: Gelen-Giden Hareket Logu
            ws2 = wb.create_sheet(title="Gelen-Giden Hareket Logu")
            ws2.merge_cells("A1:G1")
            ws2["A1"].value = "GÜNLÜK GELEN - GİDEN - ZAYİ HAREKET KAYITLARI"
            ws2["A1"].font = font_title
            ws2["A1"].alignment = Alignment(horizontal="center", vertical="center")
            ws2.row_dimensions[1].height = 30

            mov_headers = [
                "Tarih", "Kategori", "Ürün Adı", "İşlem Türü", "Miktar", "Birim", "Açıklama / Tedarikçi"
            ]
            ws2.row_dimensions[3].height = 25
            for col_num, h_text in enumerate(mov_headers, 1):
                cell = ws2.cell(row=3, column=col_num)
                cell.value = h_text
                cell.font = font_header
                cell.fill = fill_header
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thin_border

            for idx, m in enumerate(movements):
                mr = 4 + idx
                ws2.row_dimensions[mr].height = 20
                m_date_str = str(m.get('date', ''))
                ws2.cell(row=mr, column=1, value=m_date_str).border = thin_border
                ws2.cell(row=mr, column=2, value=m.get('category', '')).border = thin_border
                ws2.cell(row=mr, column=3, value=m.get('product_name', '')).border = thin_border
                ws2.cell(row=mr, column=4, value=m.get('movement_type', '')).border = thin_border
                c_mqty = ws2.cell(row=mr, column=5, value=float(m.get('quantity') or 0.0))
                c_mqty.number_format = '#,##0.00'
                c_mqty.border = thin_border
                ws2.cell(row=mr, column=6, value=m.get('unit', '')).border = thin_border
                ws2.cell(row=mr, column=7, value=m.get('description', '')).border = thin_border

            for col in ws2.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    v_str = str(cell.value or '')
                    if len(v_str) > max_len:
                        max_len = len(v_str)
                ws2.column_dimensions[col_letter].width = max(max_len + 4, 13)

            wb.save(file_path)
            logger.info(f"✅ Stok sayımı Excel'e aktarıldı: {file_path}")
            return True, f"Sayım verileri Excel'e başarıyla aktarıldı: {os.path.basename(file_path)}"
        except Exception as e:
            logger.error(f"export_to_excel hatası: {e}")
            return False, f"Excel'e aktarma hatası: {str(e)}"

    def import_from_excel(self, session_id: int, file_path: str) -> Tuple[bool, str, int]:
        """
        Excel (.xlsx) dosyasından sayım kalemlerini okuyup oturuma aktarır.
        Mevcut ürünleri günceller, yeni olanları ekler.
        """
        try:
            if not os.path.exists(file_path):
                return False, "Dosya bulunamadı!", 0

            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet = None
            if "Stok ve Sayım Takibi" in wb.sheetnames:
                sheet = wb["Stok ve Sayım Takibi"]
            else:
                sheet = wb.active

            # Başlık satırını bul
            header_row = None
            for r in range(1, 15):
                row_vals = [str(sheet.cell(row=r, column=c).value or '').lower().strip() for c in range(1, 12)]
                if any("ürün" in v or "urun" in v for v in row_vals):
                    header_row = r
                    break

            if not header_row:
                return False, "Excel dosyasında geçerli sütun başlıkları bulunamadı!", 0

            # Sütun indekslerini tespit et
            col_map = {}
            for c in range(1, sheet.max_column + 1):
                val = str(sheet.cell(row=header_row, column=c).value or '').lower().strip()
                if "kategori" in val:
                    col_map['category'] = c
                elif "ürün" in val or "urun" in val:
                    col_map['product_name'] = c
                elif "birim" in val and "maliyet" not in val:
                    col_map['unit'] = c
                elif "ay başı" in val or "ay basi" in val:
                    col_map['opening_stock'] = c
                elif "gelen" in val or "giren" in val:
                    col_map['incoming_stock'] = c
                elif "fiziksel" in val or "sayım" in val or "kalan" in val and "değer" not in val:
                    col_map['physical_count'] = c
                elif "birim maliyet" in val or "maliyet" in val:
                    col_map['unit_cost'] = c

            if 'product_name' not in col_map:
                return False, "'Ürün Adı' sütunu tespit edilemedi!", 0

            imported_items = []
            for r in range(header_row + 1, sheet.max_row + 1):
                pname = sheet.cell(row=r, column=col_map['product_name']).value
                if not pname:
                    continue
                pname_clean = str(pname).strip()
                if "toplam" in pname_clean.lower() or "genel" in pname_clean.lower():
                    continue

                def _get_float(c_name, default=0.0):
                    if c_name not in col_map:
                        return default
                    raw = sheet.cell(row=r, column=col_map[c_name]).value
                    try:
                        return float(raw or 0.0)
                    except Exception:
                        return default

                def _get_str(c_name, default=""):
                    if c_name not in col_map:
                        return default
                    raw = sheet.cell(row=r, column=col_map[c_name]).value
                    return str(raw).strip() if raw is not None else default

                cat = _get_str('category', 'Diğer')
                unit = _get_str('unit', 'Adet')
                opening = _get_float('opening_stock', 0.0)
                incoming = _get_float('incoming_stock', 0.0)
                physical = _get_float('physical_count', 0.0)
                cost = _get_float('unit_cost', 0.0)

                imported_items.append({
                    'category': cat,
                    'product_name': pname_clean,
                    'unit': unit,
                    'opening_stock': opening,
                    'incoming_stock': incoming,
                    'physical_count': physical,
                    'unit_cost': cost,
                    'display_order': len(imported_items) + 1
                })

            if not imported_items:
                return False, "Excel dosyasından okunabilecek ürün kaydı bulunamadı!", 0

            # Mevcut kayıtlarla eşleştir / güncelle veya ekle
            existing_items = self.get_session_items(session_id)
            existing_map = {
                (e.get('product_name', '').lower().strip(), e.get('category', '').lower().strip()): e
                for e in existing_items
            }

            final_items_to_save = []
            for imp in imported_items:
                key = (imp['product_name'].lower().strip(), imp['category'].lower().strip())
                if key in existing_map:
                    # Mevcut kaydı güncelle
                    ex = existing_map[key]
                    ex['opening_stock'] = imp['opening_stock']
                    ex['incoming_stock'] = imp['incoming_stock']
                    ex['physical_count'] = imp['physical_count']
                    ex['unit_cost'] = imp['unit_cost']
                    final_items_to_save.append(ex)
                else:
                    # Yeni kayıt olarak ekle
                    final_items_to_save.append(imp)

            # Kaydet
            success, msg = self.save_items(session_id, final_items_to_save)
            if success:
                logger.info(f"✅ Excel'den {len(imported_items)} ürün içe aktarıldı.")
                return True, f"Excel'den {len(imported_items)} kalem başarıyla yüklendi.", len(imported_items)
            return False, f"Excel verisi kaydedilirken hata: {msg}", 0

        except Exception as e:
            logger.error(f"import_from_excel hatası: {e}")
            return False, f"Excel içe aktarma hatası: {str(e)}", 0

    # ==================== FİRE VE ZAYİAT ANALİTİĞİ ====================

    def get_weekly_consolidated_waste(self, target_date_str: Optional[str] = None) -> Dict:
        """
        Genel Merkez için içinde bulunulan haftanın (Pazartesi-Pazar) konsolide fire özetini
        ve şube bazlı dağılımını döndürür.
        """
        try:
            db.ensure_stock_count_tables()
            if not target_date_str:
                target_date_str = datetime.now().strftime("%Y-%m-%d")

            target_dt = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            start_dt = target_dt - timedelta(days=target_dt.weekday())
            end_dt = start_dt + timedelta(days=6)
            start_str = start_dt.strftime("%Y-%m-%d")
            end_str = end_dt.strftime("%Y-%m-%d")

            sql = """
                SELECT 
                    COALESCE(s.branch_id, 0) as branch_id,
                    sm.product_name,
                    sm.quantity,
                    sm.unit,
                    COALESCE(cost_sub.unit_cost, 0.0) as unit_cost,
                    sm.description as reason
                FROM StockMovements sm
                LEFT JOIN StockCountSessions s ON sm.session_id = s.id
                LEFT JOIN LATERAL (
                    SELECT unit_cost 
                    FROM StockCountItems 
                    WHERE LOWER(TRIM(product_name)) = LOWER(TRIM(sm.product_name))
                    ORDER BY id DESC LIMIT 1
                ) cost_sub ON TRUE
                WHERE sm.movement_type IN ('Zayi', 'Fire')
                  AND sm.date BETWEEN %s AND %s
            """
            rows = db.fetch_all(sql, (start_str, end_str)) or []

            grand_qty = 0.0
            grand_val = 0.0
            branch_breakdown = {}

            for r in rows:
                qty = float(r.get('quantity') or 0.0)
                cost = float(r.get('unit_cost') or 0.0)
                reason_str = str(r.get('reason') or '')
                if cost <= 0.0 and 'Birim Maliyet:' in reason_str:
                    try:
                        cost = float(reason_str.split('Birim Maliyet:')[1].split('TL')[0].strip())
                    except Exception:
                        pass
                val = qty * cost
                bid = int(r.get('branch_id') or 0)

                grand_qty += qty
                grand_val += val

                if bid not in branch_breakdown:
                    branch_breakdown[bid] = {'waste_value': 0.0, 'waste_qty': 0.0}
                branch_breakdown[bid]['waste_value'] += val
                branch_breakdown[bid]['waste_qty'] += qty

            # Konsolide haftalık ciro
            grand_turnover = 0.0
            try:
                turnover_row = db.fetch_one("""
                    SELECT COALESCE(SUM(amount), 0) as total_turnover
                    FROM DailyTurnovers
                    WHERE entry_type = 'Income'
                      AND entry_date BETWEEN %s AND %s
                """, (start_str, end_str))
                if turnover_row:
                    grand_turnover = float(turnover_row['total_turnover'])
            except Exception as te:
                logger.warning(f"Konsolide ciro çekilemedi: {te}")

            ratio = (grand_val / grand_turnover * 100.0) if grand_turnover > 0 else 0.0

            return {
                'start_date': start_str,
                'end_date': end_str,
                'total_waste_value': grand_val,
                'total_waste_qty': grand_qty,
                'total_turnover': grand_turnover,
                'waste_ratio': ratio,
                'branch_breakdown': branch_breakdown
            }
        except Exception as e:
            logger.error(f"get_weekly_consolidated_waste hatası: {e}")
            return {
                'start_date': '',
                'end_date': '',
                'total_waste_value': 0.0,
                'total_waste_qty': 0.0,
                'total_turnover': 0.0,
                'waste_ratio': 0.0,
                'branch_breakdown': {}
            }

    def get_waste_analytics(self, branch_id: int, mode: str = "daily", target_date_str: str = None) -> Dict:
        """
        Şubenin belirtilen zaman dilimindeki (Günlük / Haftalık / Aylık) zayiat analizini getirir:
        - Toplam zayiat miktarı ve parasal zararı (TL)
        - Günlük/dönemsel ciro ve ciroya fire oranı (%)
        - En çok fire veren ürünler sıralaması (Top 5)
        - Kategorilere göre fire dağılımı
        - Detaylı zayiat hareket listesi
        """
        try:
            if not target_date_str:
                target_date_str = datetime.now().strftime("%Y-%m-%d")

            target_dt = datetime.strptime(target_date_str, "%Y-%m-%d").date()

            if mode == "weekly":
                # Pazartesi - Pazar
                start_dt = target_dt - timedelta(days=target_dt.weekday())
                end_dt = start_dt + timedelta(days=6)
                title = f"{start_dt.strftime('%d.%m.%Y')} - {end_dt.strftime('%d.%m.%Y')} Haftalık Zayiat Raporu"
            elif mode == "monthly":
                start_dt = target_dt.replace(day=1)
                _, last_day = calendar.monthrange(target_dt.year, target_dt.month)
                end_dt = target_dt.replace(day=last_day)
                aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
                title = f"{aylar[target_dt.month - 1]} {target_dt.year} Aylık Zayiat Raporu"
            elif mode == "yearly":
                start_dt = date(target_dt.year, 1, 1)
                end_dt = date(target_dt.year, 12, 31)
                title = f"{target_dt.year} Yılı Zayiat Raporu"
            else:  # daily
                start_dt = target_dt
                end_dt = target_dt
                title = f"{target_dt.strftime('%d.%m.%Y')} Günlük Zayiat Raporu"

            start_str = start_dt.strftime("%Y-%m-%d")
            end_str = end_dt.strftime("%Y-%m-%d")

            # 1. Zayi hareketlerini çek
            branch_filter = ""
            params = [start_str, end_str]
            if branch_id and branch_id > 0:
                branch_filter = "AND (sm.session_id IN (SELECT id FROM StockCountSessions WHERE branch_id = %s) OR sm.session_id IS NULL)"
                params.append(branch_id)

            sql = f"""
                SELECT 
                    sm.id,
                    sm.session_id,
                    sm.date,
                    sm.category,
                    sm.product_name,
                    sm.movement_type,
                    sm.quantity,
                    sm.unit,
                    sm.description as reason,
                    COALESCE(cost_sub.unit_cost, 0.0) as unit_cost
                FROM StockMovements sm
                LEFT JOIN LATERAL (
                    SELECT unit_cost 
                    FROM StockCountItems 
                    WHERE LOWER(TRIM(product_name)) = LOWER(TRIM(sm.product_name))
                    ORDER BY id DESC LIMIT 1
                ) cost_sub ON TRUE
                WHERE sm.movement_type IN ('Zayi', 'Fire')
                  AND sm.date BETWEEN %s AND %s
                  {branch_filter}
                ORDER BY sm.date DESC, sm.id DESC
            """
            rows = db.fetch_all(sql, tuple(params)) or []

            records = []
            tot_qty = 0.0
            tot_val = 0.0
            prod_summary = {}
            cat_summary = {}

            for r in rows:
                item = dict(r)
                qty = float(item.get('quantity') or 0.0)
                cost = float(item.get('unit_cost') or 0.0)
                reason_str = str(item.get('reason') or '')
                if cost <= 0.0 and 'Birim Maliyet:' in reason_str:
                    try:
                        cost = float(reason_str.split('Birim Maliyet:')[1].split('TL')[0].strip())
                    except Exception:
                        pass
                val = qty * cost
                item['waste_value'] = val
                item['unit_cost'] = cost
                records.append(item)

                tot_qty += qty
                tot_val += val

                pname = item.get('product_name', 'Bilinmeyen')
                if pname not in prod_summary:
                    prod_summary[pname] = {'product_name': pname, 'category': item.get('category', ''), 'unit': item.get('unit', 'Adet'), 'qty': 0.0, 'val': 0.0}
                prod_summary[pname]['qty'] += qty
                prod_summary[pname]['val'] += val

                cat = item.get('category', 'Diğer') or 'Diğer'
                if cat not in cat_summary:
                    cat_summary[cat] = {'category': cat, 'qty': 0.0, 'val': 0.0}
                cat_summary[cat]['qty'] += qty
                cat_summary[cat]['val'] += val

            # 2. Aynı dönemdeki şube cirosunu çek (oran hesabı için)
            total_turnover = 0.0
            try:
                turnover_row = db.fetch_one("""
                    SELECT COALESCE(SUM(amount), 0) as total_turnover
                    FROM DailyTurnovers
                    WHERE (branch_id = %s OR branch_id IS NULL)
                      AND entry_type = 'Income'
                      AND entry_date BETWEEN %s AND %s
                """, (branch_id, start_str, end_str))
                if turnover_row:
                    total_turnover = float(turnover_row['total_turnover'])
            except Exception as te:
                logger.warning(f"Ciro çekilemedi (DailyTurnovers): {te}")

            ratio = (tot_val / total_turnover * 100.0) if total_turnover > 0 else 0.0

            top_products = sorted(prod_summary.values(), key=lambda x: x['val'], reverse=True)[:5]
            category_breakdown = sorted(cat_summary.values(), key=lambda x: x['val'], reverse=True)

            return {
                'mode': mode,
                'title': title,
                'start_date': start_str,
                'end_date': end_str,
                'records': records,
                'total_waste_qty': tot_qty,
                'total_waste_value': tot_val,
                'total_turnover': total_turnover,
                'waste_ratio': ratio,
                'top_products': top_products,
                'category_breakdown': category_breakdown
            }
        except Exception as e:
            logger.error(f"get_waste_analytics hatası: {e}")
            return {
                'mode': mode,
                'title': "Zayiat Raporu",
                'start_date': target_date_str or "",
                'end_date': target_date_str or "",
                'records': [],
                'total_waste_qty': 0.0,
                'total_waste_value': 0.0,
                'total_turnover': 0.0,
                'waste_ratio': 0.0,
                'top_products': [],
                'category_breakdown': []
            }

    def add_waste_record(
        self,
        branch_id: int,
        date_str: str,
        product_name: str,
        category: str,
        quantity: float,
        unit: str,
        reason: str,
        unit_cost: float = 0.0,
        sync_to_turnover: bool = True
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Tek adımda hızlı fire kaydı ekler.
        Hem StockMovements'a kaydeder, hem mevcut açık sayım oturumu varsa fire miktarını günceller,
        hem de DailyTurnovers'a 'Fire / Zayiat Kaybı' gideri olarak işler!
        """
        try:
            pname = (product_name or "").strip()
            if not pname:
                return False, "Ürün adı boş olamaz!", None

            qty = float(quantity or 0.0)
            if qty <= 0:
                return False, "Fire miktarı 0'dan büyük olmalıdır!", None

            active_session = db.fetch_one("""
                SELECT id FROM StockCountSessions 
                WHERE branch_id = %s AND status = 'Draft'
                ORDER BY id DESC LIMIT 1
            """, (branch_id,))
            session_id = active_session['id'] if active_session else None

            cost = float(unit_cost or 0.0)
            if cost <= 0:
                cost_row = db.fetch_one("""
                    SELECT unit_cost FROM StockCountItems 
                    WHERE LOWER(TRIM(product_name)) = LOWER(TRIM(%s)) AND unit_cost > 0
                    ORDER BY id DESC LIMIT 1
                """, (pname,))
                if cost_row:
                    cost = float(cost_row['unit_cost'] or 0.0)

            waste_value = qty * cost

            desc = f"{reason} | Birim Maliyet: {cost:.2f} TL" if cost > 0 else reason
            with db.transaction():
                mov_id = db.execute_query("""
                    INSERT INTO StockMovements (
                        session_id, date, category, product_name,
                        movement_type, quantity, unit, description
                    ) VALUES (%s, %s, %s, %s, 'Zayi', %s, %s, %s)
                    RETURNING id
                """, (
                    session_id, date_str, category, pname, qty, unit or "Adet", desc
                ))

                if session_id:
                    matching_item = db.fetch_one("""
                        SELECT id, opening_stock, incoming_stock, physical_count, transfer_out_qty, waste_qty, unit_cost
                        FROM StockCountItems
                        WHERE session_id = %s AND LOWER(TRIM(product_name)) = LOWER(TRIM(%s))
                        LIMIT 1
                    """, (session_id, pname))

                    if matching_item:
                        new_waste_qty = float(matching_item.get('waste_qty') or 0.0) + qty
                        item_cost = float(matching_item.get('unit_cost') or cost)
                        new_waste_val = new_waste_qty * item_cost
                        opening = float(matching_item.get('opening_stock') or 0.0)
                        incoming = float(matching_item.get('incoming_stock') or 0.0)
                        physical = float(matching_item.get('physical_count') or 0.0)
                        transfer = float(matching_item.get('transfer_out_qty') or 0.0)

                        total_avail = opening + incoming
                        sold = max(0.0, total_avail - physical - transfer - new_waste_qty)
                        rem_val = physical * item_cost
                        sold_val = sold * item_cost

                        db.execute_query("""
                            UPDATE StockCountItems SET
                                waste_qty = %s,
                                waste_value = %s,
                                sold_out = %s,
                                remaining_value = %s,
                                sold_value = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (new_waste_qty, new_waste_val, sold, rem_val, sold_val, matching_item['id']))

                if sync_to_turnover and waste_value > 0:
                    from .turnover_service import turnover_service
                    turnover_desc = f"Stok Fire Kaybı: {pname} ({qty} {unit or 'Adet'}) - {reason or 'Zayiat'}"
                    turnover_service.add_entry(
                        branch_id=branch_id,
                        entry_date=date_str,
                        entry_type='Expense',
                        category='Fire / Zayiat Kaybı',
                        amount=waste_value,
                        payment_method='Diğer',
                        description=turnover_desc[:250]
                    )

            logger.info(f"🔥 Fire kaydı eklendi: ID={mov_id}, Ürün={pname}, Miktar={qty}, Tutar={waste_value} TL")
            return True, f"'{pname}' için {qty} {unit} fire ve {waste_value:,.2f} ₺ zayiat kaydı işlendi.", mov_id

        except Exception as e:
            logger.error(f"add_waste_record hatası: {e}")
            return False, f"Fire kaydedilemedi: {str(e)}", None

    # ==================== GÜN SONU BİRLEŞİK SAYIM YÖNETİMİ ====================

    def get_available_categories(self, branch_id: Optional[int] = None) -> List[str]:
        """Sayım ve ürün kategorilerini getirir (veritabanından dinamik çeker)"""
        try:
            db.ensure_stock_count_tables()
            cats = set()
            try:
                rows = db.fetch_all("SELECT DISTINCT category FROM StockCountTemplateItems WHERE is_active = TRUE AND category IS NOT NULL") or []
                for r in rows:
                    if r.get('category') and r['category'].strip():
                        cats.add(r['category'].strip())
            except Exception:
                pass

            try:
                rows2 = db.fetch_all("SELECT DISTINCT category FROM StockCountItems WHERE category IS NOT NULL") or []
                for r in rows2:
                    if r.get('category') and r['category'].strip():
                        cats.add(r['category'].strip())
            except Exception:
                pass

            try:
                rows3 = db.fetch_all("SELECT DISTINCT category FROM Products WHERE is_active = TRUE AND category IS NOT NULL AND TRIM(category) != ''") or []
                for r in rows3:
                    if r.get('category') and r['category'].strip():
                        cats.add(r['category'].strip())
            except Exception:
                pass

            defaults = [
                "Tezgah Ürünleri",
                "Pastalar & Tatlılar",
                "Meşrubatlar",
                "Unlu Mamüller",
                "Pasta Süsleri & Malzemeler"
            ]
            for d in defaults:
                cats.add(d)

            return sorted(list(cats))
        except Exception as e:
            logger.error(f"get_available_categories hatası: {e}")
            return ["Tezgah Ürünleri", "Pastalar & Tatlılar", "Meşrubatlar", "Unlu Mamüller", "Pasta Süsleri & Malzemeler"]

    def get_or_create_daily_session(
        self,
        branch_id: int,
        date_str: str,
        user_id: Optional[int] = None,
        category: Optional[str] = None
    ) -> Tuple[bool, str, Dict, List[Dict]]:
        """
        Belirtilen tarih (YYYY-MM-DD) ve isteğe bağlı kategori için gün sonu sayım oturumunu getirir veya otomatik oluşturur.
        Müşteri kategori kategori (örn: Tezgah Ürünleri, Pastalar vb.) sayım yapabilir ve aynı günde birden fazla oturum açabilir.
        Döndürür: (success, message, session_dict, items_list)
        """
        try:
            db.ensure_stock_count_tables()
            if not date_str:
                date_str = datetime.now().strftime("%Y-%m-%d")

            target_dt = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Kategori adını temizle (emojiler veya Genel Sayım ifadeleri)
            clean_cat = None
            if category:
                raw_c = str(category).replace("🥖", "").replace("🎂", "").replace("🥤", "").replace("🧁", "").replace("⭐", "").strip()
                if raw_c and raw_c != "Tüm Kategoriler" and "Tüm Kategoriler" not in raw_c and raw_c != "Genel Sayım":
                    clean_cat = raw_c

            if clean_cat:
                period_name = f"{target_dt.strftime('%d.%m.%Y')} — {clean_cat}"
                existing_session = db.fetch_one("""
                    SELECT id, branch_id, period_name, status, notes, created_at, updated_at
                    FROM StockCountSessions
                    WHERE branch_id = %s AND (
                        (created_at::date = %s AND (period_name = %s OR period_name LIKE %s))
                        OR period_name = %s
                    )
                    ORDER BY id DESC LIMIT 1
                """, (branch_id, date_str, period_name, f"%{clean_cat}%", period_name))
            else:
                period_name = f"{target_dt.strftime('%d.%m.%Y')} Gün Sonu"
                existing_session = db.fetch_one("""
                    SELECT id, branch_id, period_name, status, notes, created_at, updated_at
                    FROM StockCountSessions
                    WHERE branch_id = %s AND (
                        (created_at::date = %s AND (period_name = %s OR period_name NOT LIKE '%%—%%'))
                        OR period_name = %s
                    )
                    ORDER BY id DESC LIMIT 1
                """, (branch_id, date_str, period_name, period_name))

            if existing_session:
                sess_id = existing_session['id']
                # İmalathaneden gelen sevkiyatları güncel tut
                self.sync_daily_production_shipments(branch_id, sess_id, date_str, category=clean_cat)
                items = self.get_session_items(sess_id)
                return True, "Mevcut sayım yüklendi.", dict(existing_session), items

            # 2. Yoksa bir önceki oturumu bul (dünden devir için)
            prev_session = None
            if clean_cat:
                prev_session = db.fetch_one("""
                    SELECT id FROM StockCountSessions
                    WHERE branch_id = %s AND created_at::date < %s AND period_name LIKE %s
                    ORDER BY created_at DESC, id DESC LIMIT 1
                """, (branch_id, date_str, f"%{clean_cat}%"))

            if not prev_session:
                prev_session = db.fetch_one("""
                    SELECT id FROM StockCountSessions
                    WHERE branch_id = %s AND created_at::date < %s
                    ORDER BY created_at DESC, id DESC LIMIT 1
                """, (branch_id, date_str))

            if not prev_session:
                prev_session = db.fetch_one("""
                    SELECT id FROM StockCountSessions
                    WHERE branch_id = %s
                    ORDER BY created_at DESC, id DESC LIMIT 1
                """, (branch_id,))

            items_to_insert = []
            if prev_session:
                prev_items = db.fetch_all("""
                    SELECT category, product_name, unit, physical_count, unit_cost, display_order 
                    FROM StockCountItems 
                    WHERE session_id = %s
                    ORDER BY display_order ASC, id ASC
                """, (prev_session['id'],)) or []
                for pi in prev_items:
                    items_to_insert.append({
                        'category': pi.get('category') or '',
                        'product_name': pi.get('product_name') or '',
                        'unit': pi.get('unit') or 'Adet',
                        'opening': float(pi.get('physical_count') or 0.0),
                        'cost': float(pi.get('unit_cost') or 0.0),
                        'order': int(pi.get('display_order') or 0)
                    })

            if clean_cat:
                items_to_insert = [
                    itm for itm in items_to_insert 
                    if clean_cat.lower() in (itm.get('category') or '').lower() or (itm.get('category') or '').lower() in clean_cat.lower()
                ]

            if not items_to_insert:
                branch_products = []
                # Önce StockCountTemplateItems tablosundan çekmeyi dene
                try:
                    if clean_cat:
                        branch_products = db.fetch_all("""
                            SELECT product_name as name, category, unit, 0.0 as purchase_price 
                            FROM StockCountTemplateItems 
                            WHERE is_active = TRUE AND (category ILIKE %s OR product_name ILIKE %s)
                            ORDER BY display_order ASC, product_name ASC
                        """, (f"%{clean_cat}%", f"%{clean_cat}%")) or []
                    else:
                        branch_products = db.fetch_all("""
                            SELECT product_name as name, category, unit, 0.0 as purchase_price 
                            FROM StockCountTemplateItems 
                            WHERE is_active = TRUE
                            ORDER BY category ASC, display_order ASC, product_name ASC
                        """) or []
                except Exception as te:
                    logger.warning(f"StockCountTemplateItems okunamadı: {te}")

                # Alternatif olarak Products tablosunu güvenli dene
                if not branch_products:
                    try:
                        if clean_cat:
                            branch_products = db.fetch_all("""
                                SELECT name, category, unit, purchase_price 
                                FROM Products 
                                WHERE is_active = TRUE AND (category ILIKE %s OR name ILIKE %s)
                                ORDER BY name ASC
                            """, (f"%{clean_cat}%", f"%{clean_cat}%")) or []
                        else:
                            branch_products = db.fetch_all("""
                                SELECT name, category, unit, purchase_price 
                                FROM Products 
                                WHERE is_active = TRUE
                                ORDER BY category ASC, name ASC
                            """) or []
                    except Exception:
                        branch_products = []

                for idx, bp in enumerate(branch_products):
                    items_to_insert.append({
                        'category': bp.get('category') or (clean_cat or 'Unlu Mamül'),
                        'product_name': bp.get('name') or '',
                        'unit': bp.get('unit') or 'Adet',
                        'opening': 0.0,
                        'cost': float(bp.get('purchase_price') or 0.0),
                        'order': idx + 1
                    })

            with db.transaction():
                new_session_id = db.execute_query("""
                    INSERT INTO StockCountSessions (branch_id, period_name, status, created_by, created_at, updated_at)
                    VALUES (%s, %s, 'Draft', %s, %s, %s)
                    RETURNING id
                """, (branch_id, period_name, user_id, f"{date_str} 20:00:00", f"{date_str} 20:00:00"))

                if not new_session_id:
                    raise ValueError("Gün sonu oturumu açılamadı!")

                for item in items_to_insert:
                    db.execute_query("""
                        INSERT INTO StockCountItems (
                            session_id, category, product_name, unit,
                            opening_stock, incoming_stock, physical_count,
                            sold_out, unit_cost, remaining_value, sold_value,
                            display_order
                        ) VALUES (%s, %s, %s, %s, %s, 0.0, %s, 0.0, %s, %s, 0.0, %s)
                    """, (
                        new_session_id, item['category'], item['product_name'], item['unit'],
                        item['opening'], item['opening'], item['cost'],
                        item['opening'] * item['cost'], item['order']
                    ))

            # İmalathaneden gelen güncel sevkiyatları yeni oturuma da entegre et
            self.sync_daily_production_shipments(branch_id, new_session_id, date_str, category=clean_cat)

            created_sess = self.get_session(new_session_id)
            items = self.get_session_items(new_session_id)
            logger.info(f"✅ Günlük sayım oturumu hazırlandı: ID={new_session_id}, İsim={period_name}, Tarih={date_str}, Kalem={len(items)}")
            return True, f"{period_name} sayımı hazırlandı.", created_sess, items

        except Exception as e:
            logger.error(f"get_or_create_daily_session hatası: {e}")
            return False, f"Oturum hatası: {str(e)}", {}, []

    def sync_daily_production_shipments(self, branch_id: int, session_id: int, date_str: str, category: Optional[str] = None):
        """
        İmalathaneden bu şubeye belirtilen tarihte sevk edilen tüm ürünleri
        StockCountItems tablosuna 'Gelen (incoming_stock)' olarak yansıtır.
        """
        try:
            sql = """
                SELECT bsi.product_name, bsi.category, bsi.unit,
                       COALESCE(SUM(bsi.quantity), 0) as total_incoming,
                       COALESCE(AVG(bsi.unit_price), 0) as avg_price
                FROM BranchShipmentItems bsi
                JOIN BranchShipments bs ON bs.id = bsi.shipment_id
                WHERE bs.target_branch_id = %s AND bs.shipment_date = %s
                GROUP BY bsi.product_name, bsi.category, bsi.unit
            """
            shipped_items = db.fetch_all(sql, (branch_id, date_str)) or []
            if not shipped_items:
                return

            with db.transaction():
                for s in shipped_items:
                    pname = (s.get('product_name') or '').strip()
                    if not pname:
                        continue
                    cat = s.get('category') or 'Unlu Mamül'
                    unit = s.get('unit') or 'Adet'
                    incoming_qty = float(s.get('total_incoming') or 0.0)
                    cost = float(s.get('avg_price') or 0.0)

                    # Bu oturumda ürün var mı?
                    exist = db.fetch_one("""
                        SELECT id, opening_stock, incoming_stock, physical_count, unit_cost
                        FROM StockCountItems
                        WHERE session_id = %s AND LOWER(TRIM(product_name)) = LOWER(TRIM(%s))
                        LIMIT 1
                    """, (session_id, pname))

                    if exist:
                        cur_incoming = float(exist.get('incoming_stock') or 0.0)
                        final_incoming = max(cur_incoming, incoming_qty)
                        db.execute_query("""
                            UPDATE StockCountItems 
                            SET incoming_stock = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (final_incoming, exist['id']))
                    else:
                        # Eğer belirli bir kategori sayımı ise, farklı kategorideki ürünü ekleme
                        if category:
                            c_low = category.lower()
                            if c_low not in cat.lower() and cat.lower() not in c_low:
                                continue

                        db.execute_query("""
                            INSERT INTO StockCountItems (
                                session_id, category, product_name, unit,
                                opening_stock, incoming_stock, physical_count,
                                sold_out, unit_cost, remaining_value, sold_value,
                                display_order
                            ) VALUES (%s, %s, %s, %s, 0.0, %s, 0.0, 0.0, %s, 0.0, 0.0, 99)
                        """, (session_id, cat, pname, unit, incoming_qty, cost))

            logger.info(f"✅ İmalat sevkiyatları sayım oturumuna senkronize edildi: Oturum={session_id}, Şube={branch_id}, Tarih={date_str}")
        except Exception as e:
            logger.error(f"sync_daily_production_shipments hatası: {e}")

    def save_daily_closing(
        self,
        branch_id: int,
        session_id: int,
        date_str: str,
        items_data: List[Dict],
        sync_to_turnover: bool = True
    ) -> Tuple[bool, str]:
        """
        Gün sonu sayımını tek adımda kaydeder:
        1. StockCountItems tablosundaki stokları ve fireleri günceller.
        2. StockMovements tablosuna girilen fireleri (Zayi) otomatik işler.
        3. İsteğe bağlı olarak DailyTurnovers tablosuna o günün fire giderini otomatik senkronize eder.
        """
        try:
            if not session_id:
                return False, "Geçersiz sayım dönemi ID'si."

            with db.transaction():
                total_waste_value = 0.0
                total_waste_qty = 0.0

                # Önce bu oturuma ait daha önce otomatik eklenmiş gün sonu fire hareketlerini temizle
                db.execute_query("""
                    DELETE FROM StockMovements 
                    WHERE session_id = %s AND movement_type IN ('Zayi', 'Fire') AND description LIKE '%%Gün Sonu Fire%%'
                """, (session_id,))

                # Kalemleri güncelle
                for itm in items_data:
                    item_id = itm.get('id')
                    opening = float(itm.get('opening_stock') or 0.0)
                    incoming = float(itm.get('incoming_stock') or 0.0)
                    physical = float(itm.get('physical_count') or 0.0)
                    transfer_out = float(itm.get('transfer_out_qty') or 0.0)
                    waste = float(itm.get('waste_qty') or 0.0)
                    cost = float(itm.get('unit_cost') or 0.0)

                    total_avail = opening + incoming
                    sold_out = max(0.0, total_avail - physical - transfer_out - waste)
                    waste_val = waste * cost
                    rem_val = physical * cost
                    sold_val = sold_out * cost

                    total_waste_value += waste_val
                    total_waste_qty += waste

                    if item_id:
                        db.execute_query("""
                            UPDATE StockCountItems SET
                                opening_stock = %s,
                                incoming_stock = %s,
                                physical_count = %s,
                                transfer_out_qty = %s,
                                waste_qty = %s,
                                waste_value = %s,
                                sold_out = %s,
                                unit_cost = %s,
                                remaining_value = %s,
                                sold_value = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s AND session_id = %s
                        """, (
                            opening, incoming, physical, transfer_out,
                            waste, waste_val, sold_out, cost, rem_val, sold_val,
                            item_id, session_id
                        ))

                    # Eğer fire > 0 ise StockMovements'a zayiat hareketi olarak ekle
                    if waste > 0:
                        cat = itm.get('category', '')
                        pname = itm.get('product_name', '')
                        unit = itm.get('unit', 'Adet')
                        desc = f"Gün Sonu Fire | {pname} ({waste} {unit}) - Maliyet: {cost:.2f} TL"
                        db.execute_query("""
                            INSERT INTO StockMovements (
                                session_id, date, category, product_name,
                                movement_type, quantity, unit, description
                            ) VALUES (%s, %s, %s, %s, 'Zayi', %s, %s, %s)
                        """, (
                            session_id, date_str, cat, pname, waste, unit, desc
                        ))

                # Oturum güncelleme tarihi
                db.execute_query("""
                    UPDATE StockCountSessions SET updated_at = CURRENT_TIMESTAMP WHERE id = %s
                """, (session_id,))

                # Günlük ciro senkronizasyonu
                if sync_to_turnover:
                    from .turnover_service import turnover_service
                    db.execute_query("""
                        DELETE FROM DailyTurnovers
                        WHERE branch_id = %s AND entry_date = %s
                          AND category = 'Fire / Zayiat Kaybı'
                          AND description LIKE '%%Gün Sonu Toplam Fire%%'
                    """, (branch_id, date_str))

                    if total_waste_value > 0:
                        desc = f"Gün Sonu Toplam Fire Zararı ({total_waste_qty:,.1f} Adet/Kg)"
                        turnover_service.add_entry(
                            branch_id=branch_id,
                            entry_date=date_str,
                            entry_type='Expense',
                            category='Fire / Zayiat Kaybı',
                            amount=total_waste_value,
                            payment_method='Diğer',
                            description=desc
                        )

            logger.info(f"✅ Gün sonu sayımı kaydedildi: Oturum={session_id}, Tarih={date_str}, Fire={total_waste_value:.2f} TL")
            return True, f"Gün sonu stok ve fire sayımı başarıyla kaydedildi! (Günün Toplam Fire Zararı: {total_waste_value:,.2f} ₺)"

        except Exception as e:
            logger.error(f"save_daily_closing hatası: {e}")
            return False, f"Gün sonu kaydedilemedi: {str(e)}"


# Singleton Instance
stock_count_service = StockCountService()
