# merge_duplicates.py
"""
Mükerrer cari kayıtlarını birleştirir.
Her mükerrer grup için en eski ID'yi ana kayıt seçer,
diğerlerinin faturalarını ana kayda taşır ve diğerlerini siler.
"""
import sys
from src.core.database import db
from src.core.logger import logger

# Multi-tenant şemayı ayarla
TENANT_SCHEMA = "tenant_usr_1"  # ← Kendi şemanı yaz

def find_duplicates():
    """Mükerrer grupları bul"""
    sql = f"""
        SELECT LOWER(TRIM(title)) as normalized_title, 
               COUNT(*) as cnt, 
               array_agg(id ORDER BY id) as ids
        FROM "{TENANT_SCHEMA}".Customers
        WHERE is_active = TRUE
        GROUP BY LOWER(TRIM(title))
        HAVING COUNT(*) > 1
    """
    return db.fetch_all(sql)

def merge_group(normalized_title, ids):
    """Bir mükerrer grubu birleştir"""
    if len(ids) < 2:
        return
    
    # Ana kayıt: en eski ID (en küçük)
    main_id = ids[0]
    other_ids = ids[1:]
    
    print(f"\nBirleştiriliyor: '{normalized_title}'")
    print(f"   Ana kayıt: ID {main_id}")
    print(f"   Diğerleri: {other_ids}")
    
    # Her diğer kayıt için faturaları ana kayda taşı
    for other_id in other_ids:
        # Fatura sayısını kontrol et
        count = db.fetch_one(
            f'SELECT COUNT(*) as cnt FROM "{TENANT_SCHEMA}".Invoices WHERE customer_id = %s',
            (other_id,)
        )
        inv_count = int(count['cnt']) if count else 0
        print(f"   ID {other_id} -> {inv_count} fatura taşınacak")
        
        # Faturaları taşı
        if inv_count > 0:
            db.execute_query(
                f'UPDATE "{TENANT_SCHEMA}".Invoices SET customer_id = %s WHERE customer_id = %s',
                (main_id, other_id)
            )
        
        # Diğer tablolarda da müşteri referansı varsa güncelle (ör: PaymentPlans, EmployeeLedger)
        # Bu tablolar varsa, onları da güncelle
        try:
            db.execute_query(
                f'UPDATE "{TENANT_SCHEMA}".PaymentPlans SET payee_id = %s WHERE payee_type = \'Customer\' AND payee_id = %s',
                (main_id, other_id)
            )
        except Exception:
            pass  # Tablo yoksa veya kolon yoksa geç
        
        # Diğer kaydı sil
        db.execute_query(
            f'DELETE FROM "{TENANT_SCHEMA}".Customers WHERE id = %s',
            (other_id,)
        )
        print(f" ID {other_id} silindi")
    
    # Ana kaydın bakiyesini güncelle
    from src.services.customer_service import CustomerService
    cs = CustomerService()
    new_balance = cs.sync_customer_balance(main_id)
    print(f"   Ana kayıt ID {main_id} yeni bakiye: {new_balance} TL")
    print(f"   Birleştirme tamamlandı")

def main():
    print(f"Şema: {TENANT_SCHEMA}")
    print("=" * 60)
    
    # Tenant şemayı ayarla
    db.set_tenant(TENANT_SCHEMA)
    
    # Mükerrerleri bul
    duplicates = find_duplicates()
    print(f"Toplam {len(duplicates)} mükerrer grup bulundu")
    print("=" * 60)
    
    if not duplicates:
        print("Mükerrer yok, işlem yapılmayacak.")
        return
    
    # Her grubu birleştir
    for dup in duplicates:
        merge_group(dup['normalized_title'], dup['ids'])
    
    print("\n" + "=" * 60)
    print("Tüm mükerrer kayıtlar birleştirildi!")

if __name__ == "__main__":
    main()