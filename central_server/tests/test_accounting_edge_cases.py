# tests/test_accounting_edge_cases.py
"""
Lead QA & FinTech Architecture Test Suite
Finansal hassasiyet, ACID transaction bütünlüğü, eşzamanlılık (concurrency) ve sınır değer testleri.
"""

import sys
import os
import unittest
import threading
from decimal import Decimal
from datetime import datetime

# Proje kök dizinini ekle
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.database import db
from src.core.decimal_utils import to_decimal, round_currency, round_quantity
from src.models.invoice import Invoice, InvoiceItem
from src.models.customer import Customer
from src.models.journal import JournalEntry
from src.services.invoice_service import InvoiceService


class TestAccountingEdgeCases(unittest.TestCase):
    """Finansal ve Mimari Sınır Değer Test Paketi"""

    @classmethod
    def setUpClass(cls):
        # Test için varsayılan bir şube ve kullanıcı bul
        branch = db.fetch_one("SELECT id FROM Branches WHERE is_active = TRUE LIMIT 1")
        cls.branch_id = branch['id'] if branch else 1

        user = db.fetch_one("SELECT id FROM Users WHERE is_active = TRUE LIMIT 1")
        cls.user_id = user['id'] if user else 1

        cls.service = InvoiceService()

    def setUp(self):
        # Her test öncesi temiz bir müşteri oluştur
        self.test_customer_code = f"TEST_C_{int(datetime.now().timestamp() * 1000)}"
        c_res = db.execute_query("""
            INSERT INTO Customers (branch_id, customer_code, title, balance, credit_limit, is_active)
            VALUES (%s, %s, %s, 0, 10000, TRUE)
            RETURNING id
        """, (self.branch_id, self.test_customer_code, f"Test Müşteri {self.test_customer_code}"))
        self.customer_id = c_res

        # Temiz bir test ürünü oluştur
        self.test_product_code = f"TEST_P_{int(datetime.now().timestamp() * 1000)}"
        p_res = db.execute_query("""
            INSERT INTO Products (branch_id, product_code, name, purchase_price, sale_price, stock_quantity, is_active)
            VALUES (%s, %s, %s, 10.00, 20.00, 50.000, TRUE)
            RETURNING id
        """, (self.branch_id, self.test_product_code, f"Test Ürün {self.test_product_code}"))
        self.product_id = p_res

    def tearDown(self):
        # Test kayıtlarını temizle
        try:
            # Müşteriye ve ürüne bağlı faturaları temizle
            db.execute_query("DELETE FROM JournalEntries WHERE invoice_id IN (SELECT id FROM Invoices WHERE customer_id = %s)", (self.customer_id,))
            db.execute_query("DELETE FROM InvoiceItems WHERE product_id = %s", (self.product_id,))
            db.execute_query("DELETE FROM Invoices WHERE customer_id = %s", (self.customer_id,))
            db.execute_query("DELETE FROM Customers WHERE id = %s", (self.customer_id,))
            db.execute_query("DELETE FROM Products WHERE id = %s", (self.product_id,))
        except Exception as e:
            print(f"Teardown cleanup error: {e}")

    # ─────────────────────────────────────────────────────────────────
    # 1. Finansal Hassasiyet ve Kuruş Yuvarlama Testi (Float vs Decimal)
    # ─────────────────────────────────────────────────────────────────
    def test_floating_point_rounding_precision(self):
        """
        Float aritmetiğindeki 0.000000000000006 sapmalarını ve kuruş yuvarlama kurallarını test eder.
        Örnek: 3 adet x 19.99 TL, %15 İskonto, %20 KDV
        Brüt = 59.97 TL
        İskonto = 59.97 * 0.15 = 8.9955 -> 9.00 TL (ROUND_HALF_UP)
        Matrah = 59.97 - 9.00 = 50.97 TL
        KDV (%20) = 50.97 * 0.20 = 10.194 -> 10.19 TL
        Satır Toplamı = 50.97 + 10.19 = 61.16 TL
        """
        item = InvoiceItem({
            'product_id': self.product_id,
            'product_name': 'Hassas Hesaplama Ürünü',
            'quantity': Decimal('3'),
            'unit_price': Decimal('19.99'),
            'discount_rate': Decimal('15.00'),
            'vat_rate': Decimal('20.00')
        })
        line_total = item.calculate_totals()

        self.assertEqual(round_currency(item.discount_amount), Decimal('9.00'))
        self.assertEqual(round_currency(item.vat_amount), Decimal('10.19'))
        self.assertEqual(round_currency(line_total), Decimal('61.16'))
        self.assertIsInstance(item.line_total, Decimal)

    # ─────────────────────────────────────────────────────────────────
    # 2. ACID Transaction Bütünlüğü: Kalem Hatasında Otomatik Rollback
    # ─────────────────────────────────────────────────────────────────
    def test_atomic_invoice_creation_rollback_on_item_failure(self):
        """
        Fatura kalemlerinden biri geçersiz olduğunda (örn: negatif miktar),
        fatura başlığı dahil TÜM işlemin geri alınmasını (Rollback) doğrular.
        Veritabanında öksüz/yarım fatura kalmamalıdır.
        """
        inv_no = f"INV_ERR_{int(datetime.now().timestamp() * 1000)}"
        invoice_data = {
            'branch_id': self.branch_id,
            'invoice_no': inv_no,
            'invoice_type': 'Sales',
            'customer_id': self.customer_id
        }
        # 1. kalem geçerli, 2. kalem negatif miktarlı (hatalı)
        items = [
            {'product_id': self.product_id, 'product_name': 'Geçerli Kalem', 'quantity': 2, 'unit_price': 20},
            {'product_id': self.product_id, 'product_name': 'Hatalı Kalem', 'quantity': -5, 'unit_price': 20}
        ]

        success, msg, inv = self.service.create_invoice(invoice_data, items, self.user_id)
        self.assertFalse(success, "Negatif miktarlı kalem içeren fatura oluşturulamamalıdır!")

        # Veritabanında faturanın ve kalemlerin olmadığını doğrula (Rollback kontrolü)
        check_inv = db.fetch_one("SELECT id FROM Invoices WHERE invoice_no = %s", (inv_no,))
        self.assertIsNone(check_inv, "Rollback başarısız: Fatura başlığı veritabanında öksüz kaldı!")

    # ─────────────────────────────────────────────────────────────────
    # 3. Yetersiz Stok Satış Engeli (Negatif Stok Oluşmasını Önleme)
    # ─────────────────────────────────────────────────────────────────
    def test_stock_depletion_insufficient_stock_prevention(self):
        """
        Mevcut stoktan fazla miktarda satış faturası onaylanmaya çalışıldığında,
        sistem işlemi reddetmeli, stok eksiye düşmemeli ve cari bakiye değişmemelidir.
        """
        # Stoğu 5 adede ayarla
        db.execute_query("UPDATE Products SET stock_quantity = 5.000 WHERE id = %s", (self.product_id,))

        inv_no = f"INV_STK_{int(datetime.now().timestamp() * 1000)}"
        invoice_data = {
            'branch_id': self.branch_id,
            'invoice_no': inv_no,
            'invoice_type': 'Sales',
            'customer_id': self.customer_id
        }
        # 10 adet satmaya çalış (Stok 5)
        items = [{'product_id': self.product_id, 'product_name': 'Stok Test Ürünü', 'quantity': 10, 'unit_price': 50}]

        success, _, invoice = self.service.create_invoice(invoice_data, items, self.user_id)
        self.assertTrue(success)

        # Onaylamayı dene
        approved, app_msg = self.service.approve_invoice(invoice.id)
        self.assertFalse(approved, "Stok yetersizken fatura onaylanmamalıdır!")

        # Stok miktarını kontrol et: Hala 5 olmalı, asla negatif olmamalı
        prod = db.fetch_one("SELECT stock_quantity FROM Products WHERE id = %s", (self.product_id,))
        self.assertEqual(to_decimal(prod['stock_quantity']), Decimal('5.000'))

        # Cari bakiye değişmemiş olmalı
        cust = Customer.get_by_id(self.customer_id)
        self.assertEqual(to_decimal(cust.balance), Decimal('0.00'))

    # ─────────────────────────────────────────────────────────────────
    # 4. Eşzamanlılık & Yarış Durumu (Concurrency / Race Condition Testi)
    # ─────────────────────────────────────────────────────────────────
    def test_concurrent_stock_sales_race_condition(self):
        """
        Stokta sadece 10 adet varken iki farklı oturumun aynı anda 7'şer adet satmaya çalışması.
        Biri başarılı olmalı, diğeri yetersiz stok hatası almalıdır. Stok asla eksiye düşmemelidir.
        """
        db.execute_query("UPDATE Products SET stock_quantity = 10.000 WHERE id = %s", (self.product_id,))

        # 2 ayrı fatura oluştur (Draft)
        inv1_no = f"INV_RACE1_{int(datetime.now().timestamp() * 1000)}"
        inv2_no = f"INV_RACE2_{int(datetime.now().timestamp() * 1000)}"

        _, _, invoice1 = self.service.create_invoice(
            {'branch_id': self.branch_id, 'invoice_no': inv1_no, 'invoice_type': 'Sales', 'customer_id': self.customer_id},
            [{'product_id': self.product_id, 'product_name': 'Yarış Ürünü', 'quantity': 7, 'unit_price': 10}],
            self.user_id
        )

        _, _, invoice2 = self.service.create_invoice(
            {'branch_id': self.branch_id, 'invoice_no': inv2_no, 'invoice_type': 'Sales', 'customer_id': self.customer_id},
            [{'product_id': self.product_id, 'product_name': 'Yarış Ürünü', 'quantity': 7, 'unit_price': 10}],
            self.user_id
        )

        results = []

        def approve_worker(inv_id):
            svc = InvoiceService()
            ok, msg = svc.approve_invoice(inv_id)
            results.append((ok, msg))

        t1 = threading.Thread(target=approve_worker, args=(invoice1.id,))
        t2 = threading.Thread(target=approve_worker, args=(invoice2.id,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if r[0] is True]
        fails = [r for r in results if r[0] is False]

        # Tam olarak biri başarılı olmalı, biri başarısız olmalı
        self.assertEqual(len(successes), 1, "Eşzamanlı satışta sadece 1 fatura onaylanabilmeli!")
        self.assertEqual(len(fails), 1, "Eşzamanlı satışta yetersiz kalan fatura reddedilmeli!")

        # Kalan stok tam olarak 10 - 7 = 3 olmalı
        prod = db.fetch_one("SELECT stock_quantity FROM Products WHERE id = %s", (self.product_id,))
        self.assertEqual(to_decimal(prod['stock_quantity']), Decimal('3.000'))

    # ─────────────────────────────────────────────────────────────────
    # 5. Sınır Değerler: Negatif Fiyat, Aşırı İskonto ve Negatif Ödeme
    # ─────────────────────────────────────────────────────────────────
    def test_negative_amounts_and_validation(self):
        """
        Negatif fiyat, 100'den büyük iskonto, negatif ödeme ve kalan tutardan fazla ödemeyi test eder.
        """
        # Negatif fiyat engeli
        with self.assertRaises((ValueError, AssertionError)):
            item_neg = InvoiceItem({'product_id': self.product_id, 'quantity': 1, 'unit_price': -50})
            item_neg.calculate_totals()

        # %100'den büyük iskonto engeli
        with self.assertRaises((ValueError, AssertionError)):
            item_disc = InvoiceItem({'product_id': self.product_id, 'quantity': 1, 'unit_price': 100, 'discount_rate': 120})
            item_disc.calculate_totals()

        # Fatura üzerinden ödeme testi
        inv_no = f"INV_PAY_{int(datetime.now().timestamp() * 1000)}"
        _, _, invoice = self.service.create_invoice(
            {'branch_id': self.branch_id, 'invoice_no': inv_no, 'invoice_type': 'Sales', 'customer_id': self.customer_id},
            [{'product_id': self.product_id, 'product_name': 'Ödeme Ürünü', 'quantity': 2, 'unit_price': 50}],
            self.user_id
        )

        # Negatif ödeme reddedilmeli
        pay_res = invoice.make_payment(-50)
        self.assertFalse(pay_res, "Negatif tutarlı ödeme kabul edilmemelidir!")

        # Fatura tutarından (100 + KDV) fazla ödeme reddedilmeli
        excessive_pay = invoice.make_payment(50000)
        self.assertFalse(excessive_pay, "Kalan tutardan fazla ödeme kabul edilmemelidir!")

    # ─────────────────────────────────────────────────────────────────
    # 6. Çift Taraflı Yevmiye Kaydı (Double-Entry) Kuruş Denkliği
    # ─────────────────────────────────────────────────────────────────
    def test_double_entry_journal_balance_strictness(self):
        """
        Borç ve Alacak toplamı 1 kuruş dahi farklı olduğunda kaydın reddedildiğini doğrular.
        """
        unbalanced_entries = [
            {'account_code': '120', 'account_name': 'ALICILAR', 'debit': Decimal('100.00'), 'credit': Decimal('0.00')},
            {'account_code': '600', 'account_name': 'YURTİÇİ SATIŞLAR', 'debit': Decimal('0.00'), 'credit': Decimal('99.99')} # 1 kuruş eksik
        ]

        saved = JournalEntry.save_double_entry(self.branch_id, unbalanced_entries, self.user_id)
        self.assertFalse(saved, "Borç ve alacak kuruşu kuruşuna eşit olmayan yevmiye kaydı engellenmelidir!")

    # ─────────────────────────────────────────────────────────────────
    # 7. Onay ve Silme Döngüsünde Tam Finansal Simetri
    # ─────────────────────────────────────────────────────────────────
    def test_invoice_approve_and_delete_transaction_symmetry(self):
        """
        Fatura onaylandığında stok düşer ve cari bakiye artar.
        Fatura silindiğinde stok tam olarak iade edilir ve cari bakiye sıfıra döner.
        """
        initial_stock = Decimal('30.000')
        db.execute_query("UPDATE Products SET stock_quantity = %s WHERE id = %s", (initial_stock, self.product_id))

        inv_no = f"INV_SYM_{int(datetime.now().timestamp() * 1000)}"
        _, _, invoice = self.service.create_invoice(
            {'branch_id': self.branch_id, 'invoice_no': inv_no, 'invoice_type': 'Sales', 'customer_id': self.customer_id},
            [{'product_id': self.product_id, 'product_name': 'Simetri Ürünü', 'quantity': 10, 'unit_price': 20, 'vat_rate': 20}],
            self.user_id
        )

        # Onayla
        self.service.approve_invoice(invoice.id)

        # Stok 30 - 10 = 20 olmalı
        prod_after = db.fetch_one("SELECT stock_quantity FROM Products WHERE id = %s", (self.product_id,))
        self.assertEqual(to_decimal(prod_after['stock_quantity']), Decimal('20.000'))

        # Cari bakiye grand_total kadar artmış olmalı
        cust_after = Customer.get_by_id(self.customer_id)
        expected_balance = round_currency(invoice.grand_total)
        self.assertEqual(to_decimal(cust_after.balance), expected_balance)

        # Faturayı sil
        del_ok, _ = self.service.delete_invoice(invoice.id)
        self.assertTrue(del_ok)

        # Stok 30'a geri dönmeli
        prod_restored = db.fetch_one("SELECT stock_quantity FROM Products WHERE id = %s", (self.product_id,))
        self.assertEqual(to_decimal(prod_restored['stock_quantity']), initial_stock)

        # Cari bakiye tam olarak 0.00'a geri dönmeli
        cust_restored = Customer.get_by_id(self.customer_id)
        self.assertEqual(to_decimal(cust_restored.balance), Decimal('0.00'))


if __name__ == '__main__':
    unittest.main()
