import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from src.core.database import db
from src.core.logger import logger

def run_migration():
    print("=" * 60)
    print("KULLANICI VERİ ALANI (TENANT SCHEMA) MİGRASYONU BAŞLATILIYOR")
    print("=" * 60)

    # 1. Şemaları oluştur
    print("\n1. Şemalar oluşturuluyor...")
    db.ensure_tenant_schema("tenant_usr_1", default_branch_name="Armada Şubesi")
    db.ensure_tenant_schema("tenant_usr_2", default_branch_name="Admin Şubesi")
    db.ensure_tenant_schema("tenant_usr_3", default_branch_name="Çobançeşme Şubesi")
    print("✅ tenant_usr_1, tenant_usr_2, tenant_usr_3 şemaları hazırlandı.")

    # 2. ArifirinMuhasebe1976 (user_id = 3 / Diyar Cabek) verilerini aktar
    print("\n2. Diyar Cabek (tenant_usr_3) verileri aktarılıyor...")
    with db.get_cursor(commit=True) as cur:
        # Şubeler
        cur.execute("""
            INSERT INTO tenant_usr_3.Branches (id, name, city, phone, address, tax_no, is_active, created_at, updated_at)
            SELECT id, name, city, phone, address, tax_no, is_active, created_at, updated_at
            FROM public.Branches
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;
            SELECT setval(pg_get_serial_sequence('tenant_usr_3.Branches', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_3.Branches;
        """)

        # Cariler (Diyar Cabek'in kullandığı tüm cariler: branch_id 2, 3 veya Diyar'ın faturalarındaki cariler)
        cur.execute("""
            INSERT INTO tenant_usr_3.Customers (
                id, branch_id, customer_code, title, tax_no, tax_office, phone, email,
                address, balance, credit_limit, is_supplier, is_active, notes, created_at, updated_at
            )
            SELECT 
                c.id, c.branch_id, c.customer_code, c.title, c.tax_no, c.tax_office, c.phone, c.email,
                c.address, c.balance, c.credit_limit, c.is_supplier, c.is_active, c.notes, c.created_at, c.updated_at
            FROM public.Customers c
            WHERE c.branch_id IN (2, 3) 
               OR c.id IN (SELECT customer_id FROM public.Invoices WHERE created_by = 3 AND customer_id IS NOT NULL)
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_3.Customers', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_3.Customers;
        """)

        # Ürünler
        cur.execute("""
            INSERT INTO tenant_usr_3.Products (
                id, branch_id, product_code, barcode, name, category, unit,
                purchase_price, sale_price, stock_quantity, critical_stock, vat_rate,
                is_active, notes, created_at, updated_at
            )
            SELECT 
                id, branch_id, product_code, barcode, name, category, unit,
                purchase_price, sale_price, stock_quantity, critical_stock, vat_rate,
                is_active, notes, created_at, updated_at
            FROM public.Products
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_3.Products', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_3.Products;
        """)

        # Faturalar (created_by = 3 olan 16 fatura)
        cur.execute("""
            INSERT INTO tenant_usr_3.Invoices (
                id, branch_id, invoice_no, invoice_date, invoice_type, customer_id,
                total, vat_total, discount_total, grand_total, paid_amount, remaining_amount,
                currency, exchange_rate, status, payment_status, payment_method, notes,
                created_by, created_at, updated_at
            )
            SELECT 
                id, branch_id, invoice_no, invoice_date, invoice_type, customer_id,
                total, vat_total, discount_total, grand_total, paid_amount, remaining_amount,
                currency, exchange_rate, status, payment_status, payment_method, notes,
                created_by, created_at, updated_at
            FROM public.Invoices
            WHERE created_by = 3
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_3.Invoices', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_3.Invoices;
        """)

        # Fatura Kalemleri
        cur.execute("""
            INSERT INTO tenant_usr_3.InvoiceItems (
                id, invoice_id, product_id, product_name, quantity, unit,
                unit_price, discount_rate, discount_amount, vat_rate, vat_amount, line_total, notes, created_at
            )
            SELECT 
                ii.id, ii.invoice_id, ii.product_id, ii.product_name, ii.quantity, ii.unit,
                ii.unit_price, ii.discount_rate, ii.discount_amount, ii.vat_rate, ii.vat_amount, ii.line_total, ii.notes, ii.created_at
            FROM public.InvoiceItems ii
            WHERE ii.invoice_id IN (SELECT id FROM tenant_usr_3.Invoices)
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_3.InvoiceItems', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_3.InvoiceItems;
        """)

        # Banka Hesapları
        cur.execute("""
            INSERT INTO tenant_usr_3.BankAccounts (
                id, branch_id, account_name, bank_name, branch_name, account_no, iban,
                balance, currency, is_active, notes, created_at, updated_at
            )
            SELECT 
                id, branch_id, account_name, bank_name, branch_name, account_no, iban,
                balance, currency, is_active, notes, created_at, updated_at
            FROM public.BankAccounts
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_3.BankAccounts', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_3.BankAccounts;
        """)

        # Depo Ürünleri
        cur.execute("""
            INSERT INTO tenant_usr_3.WarehouseProducts (
                id, product_code, barcode, name, category, unit, purchase_price,
                sale_price, stock_quantity, critical_stock, is_active, notes, created_at, updated_at
            )
            SELECT 
                id, product_code, barcode, name, category, unit, purchase_price,
                sale_price, stock_quantity, critical_stock, is_active, notes, created_at, updated_at
            FROM public.WarehouseProducts
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_3.WarehouseProducts', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_3.WarehouseProducts;
        """)

    print("✅ Diyar Cabek (tenant_usr_3) verileri başarıyla aktarıldı.")

    # 3. Suna Solmaz (user_id = 1 / suna14270) verilerini aktar
    print("\n3. Suna Solmaz (tenant_usr_1) verileri aktarılıyor...")
    with db.get_cursor(commit=True) as cur:
        # Şubeler
        cur.execute("""
            INSERT INTO tenant_usr_1.Branches (id, name, city, phone, address, tax_no, is_active, created_at, updated_at)
            SELECT id, name, city, phone, address, tax_no, is_active, created_at, updated_at
            FROM public.Branches WHERE id = 1
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_1.Branches', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_1.Branches;
        """)

        # Cariler (branch_id = 1 veya Suna Hanım'ın faturasındaki cari)
        cur.execute("""
            INSERT INTO tenant_usr_1.Customers (
                id, branch_id, customer_code, title, tax_no, tax_office, phone, email,
                address, balance, credit_limit, is_supplier, is_active, notes, created_at, updated_at
            )
            SELECT 
                c.id, c.branch_id, c.customer_code, c.title, c.tax_no, c.tax_office, c.phone, c.email,
                c.address, c.balance, c.credit_limit, c.is_supplier, c.is_active, c.notes, c.created_at, c.updated_at
            FROM public.Customers c
            WHERE c.branch_id = 1
               OR c.id IN (SELECT customer_id FROM public.Invoices WHERE created_by = 1 AND customer_id IS NOT NULL)
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_1.Customers', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_1.Customers;
        """)

        # Ürünler
        cur.execute("""
            INSERT INTO tenant_usr_1.Products (
                id, branch_id, product_code, barcode, name, category, unit,
                purchase_price, sale_price, stock_quantity, critical_stock, vat_rate,
                is_active, notes, created_at, updated_at
            )
            SELECT 
                id, branch_id, product_code, barcode, name, category, unit,
                purchase_price, sale_price, stock_quantity, critical_stock, vat_rate,
                is_active, notes, created_at, updated_at
            FROM public.Products
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_1.Products', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_1.Products;
        """)

        # Faturalar (created_by = 1)
        cur.execute("""
            INSERT INTO tenant_usr_1.Invoices (
                id, branch_id, invoice_no, invoice_date, invoice_type, customer_id,
                total, vat_total, discount_total, grand_total, paid_amount, remaining_amount,
                currency, exchange_rate, status, payment_status, payment_method, notes,
                created_by, created_at, updated_at
            )
            SELECT 
                id, branch_id, invoice_no, invoice_date, invoice_type, customer_id,
                total, vat_total, discount_total, grand_total, paid_amount, remaining_amount,
                currency, exchange_rate, status, payment_status, payment_method, notes,
                created_by, created_at, updated_at
            FROM public.Invoices
            WHERE created_by = 1
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_1.Invoices', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_1.Invoices;
        """)

        # Fatura Kalemleri
        cur.execute("""
            INSERT INTO tenant_usr_1.InvoiceItems (
                id, invoice_id, product_id, product_name, quantity, unit,
                unit_price, discount_rate, discount_amount, vat_rate, vat_amount, line_total, notes, created_at
            )
            SELECT 
                ii.id, ii.invoice_id, ii.product_id, ii.product_name, ii.quantity, ii.unit,
                ii.unit_price, ii.discount_rate, ii.discount_amount, ii.vat_rate, ii.vat_amount, ii.line_total, ii.notes, ii.created_at
            FROM public.InvoiceItems ii
            WHERE ii.invoice_id IN (SELECT id FROM tenant_usr_1.Invoices)
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_1.InvoiceItems', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_1.InvoiceItems;
        """)

        # Günlük Ciro (created_by = 1)
        cur.execute("""
            INSERT INTO tenant_usr_1.DailyTurnovers (
                id, branch_id, entry_date, entry_type, category, amount,
                payment_method, description, created_by, created_at, updated_at
            )
            SELECT 
                id, branch_id, entry_date, entry_type, category, amount,
                payment_method, description, created_by, created_at, updated_at
            FROM public.DailyTurnovers
            WHERE created_by = 1
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_1.DailyTurnovers', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_1.DailyTurnovers;
        """)

        # Depo Ürünleri
        cur.execute("""
            INSERT INTO tenant_usr_1.WarehouseProducts (
                id, product_code, barcode, name, category, unit, purchase_price,
                sale_price, stock_quantity, critical_stock, is_active, notes, created_at, updated_at
            )
            SELECT 
                id, product_code, barcode, name, category, unit, purchase_price,
                sale_price, stock_quantity, critical_stock, is_active, notes, created_at, updated_at
            FROM public.WarehouseProducts
            ON CONFLICT (id) DO NOTHING;
            SELECT setval(pg_get_serial_sequence('tenant_usr_1.WarehouseProducts', 'id'), COALESCE(MAX(id), 1)) FROM tenant_usr_1.WarehouseProducts;
        """)

    print("✅ Suna Solmaz (tenant_usr_1) verileri başarıyla aktarıldı.")

    # 4. Doğrulama ve Raporlama
    print("\n4. İzolasyon Testi ve Rapor:")
    for uid, schema, uname in [(1, 'tenant_usr_1', 'suna14270'), (3, 'tenant_usr_3', 'ArifirinMuhasebe1976')]:
        db.set_tenant(schema)
        inv_count = db.fetch_one("SELECT COUNT(*) as c FROM Invoices")['c']
        cust_count = db.fetch_one("SELECT COUNT(*) as c FROM Customers")['c']
        branch_count = db.fetch_one("SELECT COUNT(*) as c FROM Branches")['c']
        print(f"👉 Kullanıcı: {uname} ({schema}) -> Şubeler: {branch_count} | Cariler: {cust_count} | Faturalar: {inv_count}")

    db.set_tenant(None)
    print("\n🎉 TEBRİKLER! Veritabanı multi-tenancy izolasyon migrasyonu başarıyla tamamlandı!")

if __name__ == '__main__':
    run_migration()
