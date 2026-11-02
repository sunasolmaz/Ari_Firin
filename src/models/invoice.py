# src/models/invoice.py
from decimal import Decimal
from typing import Optional, List, Dict
from ..core.database import db
from ..core.logger import logger
from ..core.decimal_utils import to_decimal, round_currency, round_quantity, round_rate

class InvoiceItem:
    """Fatura kalemi modeli"""
    
    def __init__(self, data: Dict = None):
        if data:
            self.id = data.get('id')
            self.invoice_id = data.get('invoice_id')
            self.product_id = data.get('product_id')
            self.product_name = data.get('product_name')
            self.quantity = round_quantity(data.get('quantity', 1))
            self.unit = data.get('unit')
            self.unit_price = round_currency(data.get('unit_price', 0))
            self.discount_rate = round_rate(data.get('discount_rate', 0))
            self.discount_amount = round_currency(data.get('discount_amount', 0))
            self.vat_rate = round_rate(data.get('vat_rate', 18))
            self.vat_amount = round_currency(data.get('vat_amount', 0))
            self.line_total = round_currency(data.get('line_total', 0))
            self.notes = data.get('notes')
            self.created_at = data.get('created_at')
    
    def calculate_totals(self) -> Decimal:
        """Kalem toplamlarını kuruş hassasiyetinde ve kontrollerle hesapla"""
        self.quantity = round_quantity(self.quantity)
        self.unit_price = round_currency(self.unit_price)
        self.discount_rate = round_rate(self.discount_rate)
        self.vat_rate = round_rate(self.vat_rate)

        if self.quantity <= Decimal('0.000'):
            raise ValueError("Miktar 0'dan büyük olmalıdır!")
        if self.unit_price < Decimal('0.00'):
            raise ValueError("Birim fiyat negatif olamaz!")
        if self.discount_rate < Decimal('0.00') or self.discount_rate > Decimal('100.00'):
            raise ValueError("İskonto oranı %0 ile %100 arasında olmalıdır!")
        if self.vat_rate < Decimal('0.00') or self.vat_rate > Decimal('100.00'):
            raise ValueError("KDV oranı %0 ile %100 arasında olmalıdır!")

        # Brüt Tutar
        gross = round_currency(self.unit_price * self.quantity)

        # İskonto
        self.discount_amount = round_currency(gross * (self.discount_rate / Decimal('100')))

        # Ara toplam (Matrah)
        subtotal = gross - self.discount_amount

        # KDV Tutarı
        self.vat_amount = round_currency(subtotal * (self.vat_rate / Decimal('100')))

        # Satır toplamı
        self.line_total = subtotal + self.vat_amount

        return self.line_total
    
    def save(self) -> bool:
        """Fatura kalemini kaydet"""
        try:
            if self.id:
                # Güncelle
                db.execute_query("""
                    UPDATE InvoiceItems 
                    SET product_name = %s, quantity = %s, unit = %s,
                        unit_price = %s, discount_rate = %s, discount_amount = %s,
                        vat_rate = %s, vat_amount = %s, line_total = %s,
                        notes = %s
                    WHERE id = %s
                """, (self.product_name, self.quantity, self.unit,
                      self.unit_price, self.discount_rate, self.discount_amount,
                      self.vat_rate, self.vat_amount, self.line_total,
                      self.notes, self.id))
            else:
                # Yeni ekle
                result = db.execute_query("""
                    INSERT INTO InvoiceItems 
                    (invoice_id, product_id, product_name, quantity, unit,
                     unit_price, discount_rate, discount_amount,
                     vat_rate, vat_amount, line_total, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (self.invoice_id, self.product_id, self.product_name,
                      self.quantity, self.unit, self.unit_price,
                      self.discount_rate, self.discount_amount,
                      self.vat_rate, self.vat_amount, self.line_total,
                      self.notes))
                self.id = result
            
            # Fatura toplamlarını güncelle
            Invoice.update_totals(self.invoice_id)
            
            logger.debug(f"✅ Fatura kalemi kaydedildi: {self.product_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Fatura kalemi kaydetme hatası: {e}")
            return False
    
    def delete(self) -> bool:
        """Fatura kalemini sil"""
        try:
            invoice_id = self.invoice_id
            db.execute_query("DELETE FROM InvoiceItems WHERE id = %s", (self.id,))
            
            # Fatura toplamlarını güncelle
            Invoice.update_totals(invoice_id)
            
            logger.debug(f"✅ Fatura kalemi silindi: {self.product_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Fatura kalemi silme hatası: {e}")
            return False

class Invoice:
    """Fatura modeli"""
    
    def __init__(self, data: Dict = None):
        if data:
            self.id = data.get('id')
            self.branch_id = data.get('branch_id')
            self.invoice_no = data.get('invoice_no')
            self.invoice_date = data.get('invoice_date')
            self.invoice_type = data.get('invoice_type')
            self.customer_id = data.get('customer_id')
            self.total = data.get('total', 0)
            self.vat_total = data.get('vat_total', 0)
            self.discount_total = data.get('discount_total', 0)
            self.grand_total = data.get('grand_total', 0)
            self.paid_amount = data.get('paid_amount', 0)
            self.remaining_amount = data.get('remaining_amount', 0)
            self.currency = data.get('currency', 'TRY')
            self.exchange_rate = data.get('exchange_rate', 1)
            self.status = data.get('status', 'Draft')
            self.payment_status = data.get('payment_status', 'Unpaid')
            self.payment_method = data.get('payment_method', 'Nakit')
            self.notes = data.get('notes')
            self.created_by = data.get('created_by')
            self.created_at = data.get('created_at')
            self.updated_at = data.get('updated_at')
            self._items = None
    
    @property
    def items(self) -> List[InvoiceItem]:
        """Fatura kalemlerini getir"""
        if self._items is None:
            results = db.fetch_all(
                "SELECT * FROM InvoiceItems WHERE invoice_id = %s ORDER BY id",
                (self.id,)
            )
            self._items = [InvoiceItem(data) for data in results]
        return self._items
    
    def add_item(self, item: InvoiceItem) -> bool:
        """Fatura kalemi ekle"""
        item.invoice_id = self.id
        item.calculate_totals()
        if item.save():
            self._items = None  # Cache'i temizle
            self.calculate_totals()
            return True
        return False
    
    def remove_item(self, item_id: int) -> bool:
        """Fatura kalemi sil"""
        item = InvoiceItem({'invoice_id': self.id, 'id': item_id})
        if item.delete():
            self._items = None
            self.calculate_totals()
            return True
        return False
    
    def calculate_totals(self):
        """Fatura toplamlarını kuruş hassasiyetinde hesapla"""
        items = self.items
        
        self.total = round_currency(sum((to_decimal(item.line_total) - to_decimal(item.vat_amount)) for item in items))
        self.vat_total = round_currency(sum(to_decimal(item.vat_amount) for item in items))
        self.discount_total = round_currency(sum(to_decimal(item.discount_amount) for item in items))
        self.grand_total = self.total + self.vat_total
        
        if self.payment_status == 'Paid':
            self.paid_amount = self.grand_total
            self.remaining_amount = Decimal('0.00')
        else:
            paid = round_currency(self.paid_amount or 0)
            self.remaining_amount = max(Decimal('0.00'), self.grand_total - paid)
    
    def save(self) -> bool:
        """Faturayı kaydet"""
        try:
            if self.id:
                # Güncelle
                db.execute_query("""
                    UPDATE Invoices 
                    SET branch_id = %s, invoice_date = %s, invoice_type = %s,
                        customer_id = %s, total = %s, vat_total = %s,
                        discount_total = %s, grand_total = %s,
                        paid_amount = %s, remaining_amount = %s,
                        currency = %s, exchange_rate = %s,
                        status = %s, payment_status = %s, payment_method = %s,
                        notes = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (self.branch_id, self.invoice_date, self.invoice_type,
                      self.customer_id, self.total, self.vat_total,
                      self.discount_total, self.grand_total,
                      self.paid_amount, self.remaining_amount,
                      self.currency, self.exchange_rate,
                      self.status, self.payment_status, self.payment_method,
                      self.notes, self.id))
            else:
                # Yeni ekle
                result = db.execute_query("""
                    INSERT INTO Invoices 
                    (branch_id, invoice_date, invoice_type, customer_id,
                     total, vat_total, discount_total, grand_total,
                     paid_amount, remaining_amount, currency, exchange_rate,
                     status, payment_status, payment_method, notes, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (self.branch_id, self.invoice_date, self.invoice_type,
                      self.customer_id, self.total, self.vat_total,
                      self.discount_total, self.grand_total,
                      self.paid_amount, self.remaining_amount,
                      self.currency, self.exchange_rate,
                      self.status, self.payment_status, self.payment_method,
                      self.notes, self.created_by))
                self.id = result
                inv_row = db.fetch_one("SELECT invoice_no FROM Invoices WHERE id = %s", (self.id,))
                if inv_row and inv_row.get('invoice_no'):
                    self.invoice_no = inv_row['invoice_no']
            
            logger.info(f"✅ Fatura kaydedildi: {self.invoice_no}")
            return True
        except Exception as e:
            logger.error(f"❌ Fatura kaydetme hatası: {e}")
            return False
    
    def approve(self) -> bool:
        """Faturayı onayla (ACID transaction ve Concurrency kilitli)"""
        try:
            with db.transaction():
                # Fatura kilitli sorgu
                inv_row = db.fetch_one("SELECT status, grand_total, remaining_amount, payment_status FROM Invoices WHERE id = %s FOR UPDATE", (self.id,))
                if not inv_row:
                    raise ValueError("Fatura bulunamadı!")
                if inv_row['status'] == 'Approved':
                    raise ValueError("Fatura zaten onaylanmış!")
                
                grand_tot = round_currency(inv_row['grand_total'])
                if grand_tot <= Decimal('0.00'):
                    raise ValueError("Toplam tutarı 0 olan veya kalemi bulunmayan fatura onaylanamaz!")

                # 1. Stok miktarlarını kontrol et ve güncelle (Pessimistic locking)
                for item in self.items:
                    p_id = item.product_id
                    if not p_id:
                        prod_name = (item.product_name or '').strip()
                        if prod_name:
                            prod = db.fetch_one(
                                "SELECT id FROM Products WHERE branch_id = %s AND LOWER(name) = LOWER(%s) AND is_active = TRUE",
                                (self.branch_id, prod_name)
                            )
                            p_id = prod['id'] if prod else None
                    
                    if p_id:
                        qty = round_quantity(item.quantity)
                        if self.invoice_type == 'Sales':
                            # FOR UPDATE ile satır seviyesinde kilit
                            p_row = db.fetch_one("SELECT id, name, stock_quantity FROM Products WHERE id = %s FOR UPDATE", (p_id,))
                            if p_row:
                                cur_stock = to_decimal(p_row['stock_quantity'])
                                if cur_stock < qty:
                                    logger.warning(f"⚠️ Yetersiz stok uyarısı: '{p_row['name']}' için mevcut stok {cur_stock}, talep edilen {qty}. Stok eksiye düşürüldü.")
                                db.execute_query("UPDATE Products SET stock_quantity = stock_quantity - %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (qty, p_id))
                        elif self.invoice_type in ['Purchase', 'Return']:
                            db.execute_query("UPDATE Products SET stock_quantity = stock_quantity + %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (qty, p_id))

                # 2. Fatura durumunu onayla
                db.execute_query("""
                    UPDATE Invoices SET status = 'Approved', updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (self.id,))
                self.status = 'Approved'

                # 3. Cari bakiyesini kesin olarak senkronize et
                if self.customer_id:
                    from ..services.customer_service import CustomerService
                    CustomerService().sync_customer_balance(self.customer_id)

            logger.info(f"✅ Fatura onaylandı: {self.invoice_no}")
            return True
        except Exception as e:
            logger.error(f"❌ Fatura onaylama hatası: {e}")
            return False
    
    def make_payment(self, amount) -> bool:
        """Ödeme yap (ACID transaction ve Decimal kontrollü)"""
        try:
            amt = round_currency(amount)
            if amt <= Decimal('0.00'):
                logger.warning(f"Geçersiz ödeme tutarı: {amt}")
                return False

            with db.transaction():
                # Faturayı kilitle
                inv_row = db.fetch_one("SELECT grand_total, paid_amount, remaining_amount, payment_status FROM Invoices WHERE id = %s FOR UPDATE", (self.id,))
                if not inv_row:
                    return False
                
                curr_paid = round_currency(inv_row['paid_amount'])
                curr_rem = round_currency(inv_row['remaining_amount'])
                
                if amt > curr_rem:
                    logger.warning(f"Ödeme tutarı ({amt}) kalan tutardan ({curr_rem}) büyük olamaz!")
                    return False

                self.paid_amount = curr_paid + amt
                self.remaining_amount = curr_rem - amt
                self.payment_status = 'Paid' if self.remaining_amount == Decimal('0.00') else 'Partial'

                db.execute_query("""
                    UPDATE Invoices 
                    SET paid_amount = %s, remaining_amount = %s, payment_status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (self.paid_amount, self.remaining_amount, self.payment_status, self.id))

                # Cari bakiyesini güncelle
                from .customer import Customer
                customer = Customer.get_by_id(self.customer_id)
                if customer:
                    customer.update_balance(-amt)

            logger.info(f"✅ Ödeme yapıldı: {self.invoice_no} - {amt} TL")
            return True
        except Exception as e:
            logger.error(f"❌ Ödeme hatası: {e}")
            return False
    
    @classmethod
    def update_totals(cls, invoice_id: int):
        """Fatura toplamlarını güncelle (trigger ile yapılıyor, yedek)"""
        try:
            db.execute_query("""
                UPDATE Invoices 
                SET 
                    total = COALESCE((SELECT SUM(line_total - vat_amount) 
                                     FROM InvoiceItems WHERE invoice_id = %s), 0),
                    vat_total = COALESCE((SELECT SUM(vat_amount) 
                                         FROM InvoiceItems WHERE invoice_id = %s), 0),
                    discount_total = COALESCE((SELECT SUM(discount_amount) 
                                              FROM InvoiceItems WHERE invoice_id = %s), 0)
                WHERE id = %s
            """, (invoice_id, invoice_id, invoice_id, invoice_id))
        except Exception as e:
            logger.error(f"❌ Fatura toplam güncelleme hatası: {e}")
    
    @classmethod
    def get_by_id(cls, invoice_id: int) -> Optional['Invoice']:
        """ID'ye göre fatura getir"""
        data = db.fetch_one("SELECT * FROM Invoices WHERE id = %s", (invoice_id,))
        return cls(data) if data else None
    
    @classmethod
    def get_by_no(cls, invoice_no: str) -> Optional['Invoice']:
        """Fatura numarasına göre getir"""
        data = db.fetch_one("SELECT * FROM Invoices WHERE invoice_no = %s", (invoice_no,))
        return cls(data) if data else None
    
    @classmethod
    def get_by_branch(cls, branch_id: int, page: int = 1, 
                     page_size: int = None) -> tuple:
        """Şubeye göre faturaları getir"""
        query = "SELECT * FROM Invoices WHERE branch_id = %s ORDER BY invoice_date DESC"
        return db.fetch_paginated(query, page, page_size, (branch_id,))
    
    @classmethod
    def get_by_customer(cls, customer_id: int, page: int = 1) -> tuple:
        """Cari hesaba göre faturaları getir"""
        query = "SELECT * FROM Invoices WHERE customer_id = %s ORDER BY invoice_date DESC"
        return db.fetch_paginated(query, page, None, (customer_id,))
    
    @classmethod
    def get_report(cls, branch_id: int, start_date: str, end_date: str) -> List[Dict]:
        """Fatura raporu getir"""
        return db.fetch_all("""
            SELECT 
                i.*,
                c.title as customer_name,
                u.full_name as created_by_name
            FROM Invoices i
            LEFT JOIN Customers c ON c.id = i.customer_id
            LEFT JOIN Users u ON u.id = i.created_by
            WHERE i.branch_id = %s
            AND i.invoice_date BETWEEN %s AND %s
            AND i.status = 'Approved'
            ORDER BY i.invoice_date DESC
        """, (branch_id, start_date, end_date))