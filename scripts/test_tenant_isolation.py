# scripts/test_tenant_isolation.py
"""
Multi-Tenant Veri İzolasyonu Doğrulama Testi
Senaryo:
1. Kullanıcı A (suna14270 - tenant_usr_1) ile giriş yap -> Müşteri ekle -> Çıkış yap
2. Kullanıcı B (admin - tenant_usr_2) ile giriş yap -> Müşteri listesini kontrol et -> A'nın müşterisi GÖRÜNMEMELİ!
3. Kullanıcı B ile müşteri ekle -> Çıkış yap
4. Kullanıcı A ile tekrar giriş yap -> Sadece kendi müşterisini görmeli, B'nin müşterisi GÖRÜNMEMELİ!
5. Test verilerini temizle ve sonucu raporla.
"""

import sys
import os

# UTF-8 konsol çıktısı (Windows cp1254 desteği)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.database import db
from src.models.user import User
from src.models.customer import Customer
from src.services.customer_service import CustomerService


def run_isolation_test():
    print("=" * 70)
    print("🚀 MULTI-TENANT VERİ İZOLASYONU TESTİ BAŞLIYOR")
    print("=" * 70)

    customer_service = CustomerService()

    # Kullanıcı A ve B'yi belirle
    user_a = User.get_by_username('suna14270')
    user_b = User.get_by_username('admin')

    if not user_a or not user_b:
        print("❌ HATA: Test kullanıcıları (suna14270 veya admin) bulunamadı!")
        return False

    schema_a = user_a.get_tenant_schema()
    schema_b = user_b.get_tenant_schema()

    print(f"👤 Kullanıcı A: {user_a.username} -> Şema: {schema_a}")
    print(f"👤 Kullanıcı B: {user_b.username} -> Şema: {schema_b}")

    title_a = "TEST_IZOLASYON_MUSTERI_A_8899"
    title_b = "TEST_IZOLASYON_MUSTERI_B_7766"

    # -------------------------------------------------------------
    # ADIM 1: Kullanıcı A Giriş Yapar, Müşteri Ekler, Çıkış Yapar
    # -------------------------------------------------------------
    print("\n--- [ADIM 1] Kullanıcı A Giriş Yapıyor ---")
    db.set_tenant(schema_a)
    db.ensure_tenant_schema(schema_a)
    
    # Mevcut test kaydı varsa önce temizle
    db.execute_query("DELETE FROM Customers WHERE title IN (%s, %s)", (title_a, title_b))

    # A kullanıcısına müşteri ekle
    cust_a = Customer({
        'branch_id': 1,
        'title': title_a,
        'phone': '05551112233',
        'balance': 1500.00,
        'credit_limit': 5000.00,
        'is_active': True
    })
    saved_a = cust_a.save()
    assert saved_a, "Kullanıcı A için müşteri kaydedilemedi!"
    print(f"✅ Kullanıcı A ({schema_a}) için '{title_a}' eklendi (ID: {cust_a.id})")

    # A müşterisini A oturumunda teyit et
    a_customers = db.fetch_all("SELECT title FROM Customers WHERE is_active = TRUE")
    a_titles = [c['title'] for c in a_customers]
    assert title_a in a_titles, "Kullanıcı A kendi eklediği müşteriyi göremiyor!"
    print(f"✅ Kullanıcı A kendi müşterisini başarıyla görüyor. Toplam cari: {len(a_titles)}")

    # Çıkış yap
    db.clear_tenant()
    print("👋 Kullanıcı A çıkış yaptı (tenant temizlendi).")

    # -------------------------------------------------------------
    # ADIM 2: Kullanıcı B Giriş Yapar, A'nın Müşterisini KESİNLİKLE Görmemeli
    # -------------------------------------------------------------
    print("\n--- [ADIM 2] Kullanıcı B Giriş Yapıyor ---")
    db.set_tenant(schema_b)
    db.ensure_tenant_schema(schema_b)

    # Mevcut test kaydı varsa önce temizle
    db.execute_query("DELETE FROM Customers WHERE title IN (%s, %s)", (title_a, title_b))

    b_customers = db.fetch_all("SELECT title FROM Customers WHERE is_active = TRUE")
    b_titles = [c['title'] for c in b_customers]
    print(f"ℹ️ Kullanıcı B ({schema_b}) müşteri sayısı: {len(b_titles)}")

    if title_a in b_titles:
        print(f"🚨 KRİTİK GÜVENLİK AÇIĞI: Kullanıcı B, Kullanıcı A'nın müşterisini ({title_a}) GÖREBİLİYOR!")
        assert False, "Multi-tenant izolasyon BAŞARISIZ! Kullanıcı B Kullanıcı A'nın verisini gördü!"
    else:
        print(f"🔒 İZOLASYON BAŞARILI: Kullanıcı B, Kullanıcı A'nın müşterisini ({title_a}) GÖRMÜYOR!")

    # -------------------------------------------------------------
    # ADIM 3: Kullanıcı B Müşteri Ekler, Çıkış Yapar
    # -------------------------------------------------------------
    print("\n--- [ADIM 3] Kullanıcı B Müşteri Ekliyor ---")
    cust_b = Customer({
        'branch_id': 1,
        'title': title_b,
        'phone': '05559998877',
        'balance': 3500.00,
        'credit_limit': 10000.00,
        'is_active': True
    })
    saved_b = cust_b.save()
    assert saved_b, "Kullanıcı B için müşteri kaydedilemedi!"
    print(f"✅ Kullanıcı B ({schema_b}) için '{title_b}' eklendi (ID: {cust_b.id})")

    b_customers_new = db.fetch_all("SELECT title FROM Customers WHERE is_active = TRUE")
    b_titles_new = [c['title'] for c in b_customers_new]
    assert title_b in b_titles_new, "Kullanıcı B kendi eklediği müşteriyi göremiyor!"
    assert title_a not in b_titles_new, "Kullanıcı B hâlâ A'nın verisini görüyor!"
    print(f"✅ Kullanıcı B kendi müşterisini görüyor, A'nın müşterisini görmüyor.")

    # Çıkış yap
    db.clear_tenant()
    print("👋 Kullanıcı B çıkış yaptı (tenant temizlendi).")

    # -------------------------------------------------------------
    # ADIM 4: Kullanıcı A Yeniden Giriş Yapar
    # -------------------------------------------------------------
    print("\n--- [ADIM 4] Kullanıcı A Yeniden Giriş Yapıyor ---")
    db.set_tenant(schema_a)
    db.ensure_tenant_schema(schema_a)

    a_customers_final = db.fetch_all("SELECT title FROM Customers WHERE is_active = TRUE")
    a_titles_final = [c['title'] for c in a_customers_final]

    assert title_a in a_titles_final, f"Kullanıcı A kendi müşterisini ({title_a}) göremedi!"
    print(f"✅ Kullanıcı A kendi müşterisini ({title_a}) görüyor.")

    if title_b in a_titles_final:
        print(f"🚨 KRİTİK GÜVENLİK AÇIĞI: Kullanıcı A, Kullanıcı B'nin müşterisini ({title_b}) GÖREBİLİYOR!")
        assert False, "Multi-tenant izolasyon BAŞARISIZ! Kullanıcı A Kullanıcı B'nin verisini gördü!"
    else:
        print(f"🔒 İZOLASYON BAŞARILI: Kullanıcı A, Kullanıcı B'nin müşterisini ({title_b}) GÖRMÜYOR!")

    # -------------------------------------------------------------
    # ADIM 5: Temizlik
    # -------------------------------------------------------------
    print("\n--- [ADIM 5] Test Verileri Temizleniyor ---")
    db.execute_query("DELETE FROM Customers WHERE title = %s", (title_a,))
    db.set_tenant(schema_b)
    db.execute_query("DELETE FROM Customers WHERE title = %s", (title_b,))
    db.clear_tenant()
    print("🧹 Test verileri her iki şemadan da temizlendi.")

    print("\n" + "=" * 70)
    print("🎉 TÜM MULTI-TENANT İZOLASYON TESTLERİ EKSİKSİZ VE BAŞARIYLA GEÇTİ!")
    print("=" * 70)
    return True


if __name__ == '__main__':
    success = run_isolation_test()
    sys.exit(0 if success else 1)
