from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from ..models.invoice import Invoice, InvoiceItem
from ..models.customer import Customer
from ..models.journal import JournalEntry
from ..core.database import db
from ..core.logger import logger
from ..core.decimal_utils import to_decimal, round_currency, round_quantity

class InvoiceService:
    """Fatura servisi"""
    
    def __init__(self):
        self.cache = {}
    
    def get_invoices(self, branch_id: int, page: int = 1, 
                    page_size: int = None) -> Tuple[List[Invoice], int]:
        """Faturaları getir"""
        try:
            data, total = Invoice.get_by_branch(branch_id, page, page_size)
            invoices = [Invoice(d) for d in data]
            return invoices, total
        except Exception as e:
            logger.error(f"Fatura listeleme hatası: {e}")
            return [], 0
    
    def get_invoice(self, invoice_id: int) -> Optional[Invoice]:
        """Fatura detayını getir"""
        try:
            return Invoice.get_by_id(invoice_id)
        except Exception as e:
            logger.error(f"Fatura detay hatası: {e}")
            return None
    
    def create_invoice(self, data: Dict, items: List[Dict], user_id: int) -> Tuple[bool, str, Optional[Invoice]]:
        """Yeni fatura oluştur (ACID Transaction garantili & Otomatik Cari Senkronizasyonlu)"""
        try:
            # 1. Müşteri Çözümleme / Otomatik Cari Kayıt
            customer_id = data.get('customer_id')
            customer_title = (data.get('customer_title') or '').strip()

            if not customer_id and customer_title:
                # İsim kontrolü: Bu şubede veya şubesiz bu isimde aktif bir cari var mı? (Case-insensitive)
                branch_id = data.get('branch_id')
                existing = db.fetch_one("""
                    SELECT id FROM Customers 
                    WHERE (branch_id = %s OR branch_id IS NULL) AND LOWER(TRIM(title)) = LOWER(TRIM(%s)) AND is_active = TRUE
                    ORDER BY (CASE WHEN branch_id = %s THEN 0 ELSE 1 END) ASC
                    LIMIT 1
                """, (branch_id, customer_title, branch_id))
                if existing:
                    customer_id = existing['id']
                    if branch_id:
                        db.execute_query("UPDATE Customers SET branch_id = %s WHERE id = %s AND branch_id IS NULL", (branch_id, customer_id))
                else:
                    # Yoksa bu şubeye özel yeni cari oluştur
                    inv_type = data.get('invoice_type', 'Sales')
                    is_supplier = True if inv_type in ('Purchase', 'Alış') else False
                    tax_no = (data.get('customer_tax_no') or data.get('tax_no') or '').strip()
                    phone = (data.get('customer_phone') or data.get('phone') or '').strip()
                    address = (data.get('customer_address') or data.get('address') or '').strip()
                    
                    customer_id = db.execute_query("""
                        INSERT INTO Customers (branch_id, title, tax_no, phone, address, is_supplier, is_active, balance)
                        VALUES (%s, %s, %s, %s, %s, %s, TRUE, 0)
                        RETURNING id
                    """, (branch_id, customer_title, tax_no, phone, address, is_supplier))

            # Validasyon
            if not customer_id:
                return False, "Müşteri veya firma seçilmeli / adı girilmelidir!", None

            data['customer_id'] = customer_id

            if not items:
                return False, "En az bir fatura kalemi olmalıdır!", None

            # Customer kontrolü
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return False, "Geçersiz müşteri!", None

            with db.transaction():
                # Fatura oluştur
                invoice = Invoice({
                    'branch_id': data['branch_id'],
                    'invoice_date': data.get('invoice_date', datetime.now().date()),
                    'invoice_type': data.get('invoice_type', 'Sales'),
                    'customer_id': customer_id,
                    'currency': data.get('currency', 'TRY'),
                    'exchange_rate': data.get('exchange_rate', 1),
                    'payment_method': data.get('payment_method', 'Nakit'),
                    'payment_status': data.get('payment_status', 'Unpaid'),
                    'notes': data.get('notes', ''),
                    'created_by': user_id
                })
                
                # Invoice numarasını manuel belirle
                if data.get('invoice_no'):
                    invoice.invoice_no = data['invoice_no']
                
                if not invoice.save():
                    raise ValueError("Fatura oluşturulamadı!")
                
                # Kalemleri ekle
                for item_data in items:
                    p_id = item_data.get('product_id')
                    if not p_id:
                        p_row = db.fetch_one("SELECT id FROM Products WHERE branch_id = %s AND LOWER(name) = LOWER(%s) AND is_active = TRUE", (data['branch_id'], item_data['product_name'].strip()))
                        if p_row:
                            p_id = p_row['id']
                    
                    item = InvoiceItem({
                        'invoice_id': invoice.id,
                        'product_id': p_id,
                        'product_name': item_data['product_name'],
                        'quantity': item_data.get('quantity', 1),
                        'unit': item_data.get('unit', 'Adet'),
                        'unit_price': item_data.get('unit_price', 0),
                        'discount_rate': item_data.get('discount_rate', 0),
                        'vat_rate': item_data.get('vat_rate', 18),
                        'notes': item_data.get('notes', '')
                    })
                    item.calculate_totals() # Geçersiz miktar veya fiyat durumunda ValueError fırlatır
                    if not item.save():
                        raise ValueError(f"Kalem kaydedilemedi: {item_data['product_name']}")
                
                # Fatura toplamlarını güncelle
                invoice.calculate_totals()
                invoice.save()
                
                # Cari bakiyesini kesin olarak senkronize et
                from .customer_service import CustomerService
                CustomerService().sync_customer_balance(customer_id)

                # Muhasebe kaydı oluştur (Opsiyonel)
                if data.get('auto_journal', True):
                    self._create_journal_entries(invoice, customer, user_id)

            # Transaction sonrası cari bakiyeyi tekrar güvenceye al
            try:
                from .customer_service import CustomerService
                CustomerService().sync_customer_balance(customer_id)
            except Exception:
                pass

            logger.info(f"✅ Fatura oluşturuldu: {invoice.invoice_no}")
            return True, f"Fatura başarıyla oluşturuldu! No: {invoice.invoice_no}", invoice
            
        except ValueError as ve:
            logger.warning(f"Fatura doğrulama hatası: {ve}")
            return False, str(ve), None
        except Exception as e:
            logger.error(f"Fatura oluşturma hatası: {e}")
            return False, f"Sistem hatası: {str(e)}", None
    
    def update_invoice(self, invoice_id: int, data: Dict) -> Tuple[bool, str]:
        """Fatura güncelle"""
        try:
            invoice = Invoice.get_by_id(invoice_id)
            if not invoice:
                return False, "Fatura bulunamadı!"
            
            # Onaylanmış faturalar güncellenemez
            if invoice.status == 'Approved':
                return False, "Onaylanmış faturalar güncellenemez!"
            
            # Verileri güncelle
            for key, value in data.items():
                if hasattr(invoice, key) and key not in ['id', 'invoice_no', 'status']:
                    setattr(invoice, key, value)
            
            if invoice.save():
                self.cache.pop(invoice_id, None)
                if invoice.customer_id:
                    from .customer_service import CustomerService
                    CustomerService().sync_customer_balance(invoice.customer_id)
                logger.info(f"✅ Fatura güncellendi: {invoice.invoice_no}")
                return True, "Fatura başarıyla güncellendi!"
            else:
                return False, "Fatura güncellenemedi!"
                
        except Exception as e:
            logger.error(f"Fatura güncelleme hatası: {e}")
            return False, f"Sistem hatası: {str(e)}"
    
    def approve_invoice(self, invoice_id: int) -> Tuple[bool, str]:
        """Faturayı onayla"""
        try:
            invoice = Invoice.get_by_id(invoice_id)
            if not invoice:
                return False, "Fatura bulunamadı!"
            
            if invoice.status == 'Approved':
                return False, "Fatura zaten onaylanmış!"
            
            if to_decimal(invoice.grand_total or 0) <= Decimal('0.00'):
                return False, "Toplam tutarı 0 olan veya kalemi bulunmayan fatura onaylanamaz!"
            
            if invoice.approve():
                # Cari bakiyesini kesin olarak senkronize et
                if invoice.customer_id:
                    from .customer_service import CustomerService
                    CustomerService().sync_customer_balance(invoice.customer_id)

                # Muhasebe (yevmiye) kaydı oluştur
                try:
                    customer = Customer.get_by_id(invoice.customer_id) if invoice.customer_id else None
                    if customer:
                        self._create_journal_entries(invoice, customer, invoice.created_by or 1)
                except Exception as je_err:
                    logger.warning(f"Onaylanan fatura için yevmiye kaydı oluşturulurken uyarı: {je_err}")

                self.cache.pop(invoice_id, None)
                logger.info(f"✅ Fatura onaylandı: {invoice.invoice_no}")
                return True, "Fatura başarıyla onaylandı!"
            else:
                return False, "Fatura onaylanamadı! Lütfen kalemleri ve verileri kontrol ediniz."
                
        except Exception as e:
            logger.error(f"Fatura onaylama hatası: {e}")
            return False, f"Sistem hatası: {str(e)}"
    
    def delete_invoice(self, invoice_id: int) -> Tuple[bool, str]:
        """Fatura sil (Onaylı veya Taslak - ACID Transaction garantili)"""
        try:
            with db.transaction():
                invoice = Invoice.get_by_id(invoice_id)
                if not invoice:
                    return False, "Fatura bulunamadı!"
                
                # Onaylanmış faturanın stok etkisini geri al
                if invoice.status == 'Approved':
                    for item in invoice.items:
                        p_id = item.product_id
                        if not p_id:
                            prod_name = (item.product_name or '').strip()
                            if prod_name:
                                prod = db.fetch_one("SELECT id FROM Products WHERE branch_id = %s AND LOWER(name) = LOWER(%s) AND is_active = TRUE", (invoice.branch_id, prod_name))
                                p_id = prod['id'] if prod else None
                        if p_id:
                            qty = round_quantity(item.quantity or 0)
                            if invoice.invoice_type == 'Sales':
                                db.execute_query("UPDATE Products SET stock_quantity = stock_quantity + %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (qty, p_id))
                            elif invoice.invoice_type in ['Purchase', 'Return']:
                                db.execute_query("UPDATE Products SET stock_quantity = stock_quantity - %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (qty, p_id))
                
                # Varsa ilişkili sevkiyat veya tedarik kayıtlarındaki referansı temizle
                try:
                    db.execute_query("UPDATE BakerySupplies SET invoice_id = NULL WHERE invoice_id = %s", (invoice_id,))
                except Exception:
                    pass
                try:
                    db.execute_query("UPDATE bakery_supplies SET invoice_id = NULL WHERE invoice_id = %s", (invoice_id,))
                except Exception:
                    pass

                # Varsa muhasebe (yevmiye) kayıtlarını sil
                db.execute_query("DELETE FROM JournalEntries WHERE invoice_id = %s", (invoice_id,))

                # Kalemleri sil
                db.execute_query("DELETE FROM InvoiceItems WHERE invoice_id = %s", (invoice_id,))
                
                # Faturayı sil
                db.execute_query("DELETE FROM Invoices WHERE id = %s", (invoice_id,))

                # Cari bakiyesini kesin olarak senkronize et
                if invoice.customer_id:
                    from .customer_service import CustomerService
                    CustomerService().sync_customer_balance(invoice.customer_id)

            self.cache.pop(invoice_id, None)
            logger.info(f"✅ Fatura silindi: {invoice.invoice_no}")
            return True, "Fatura başarıyla silindi!"
            
        except Exception as e:
            logger.error(f"Fatura silme hatası: {e}")
            return False, f"Sistem hatası: {str(e)}"
    
    def add_item(self, invoice_id: int, item_data: Dict) -> Tuple[bool, str]:
        """Fatura kalemi ekle"""
        try:
            invoice = Invoice.get_by_id(invoice_id)
            if not invoice:
                return False, "Fatura bulunamadı!"
            
            if invoice.status == 'Approved':
                return False, "Onaylanmış faturalara kalem eklenemez!"
            
            item = InvoiceItem({
                'invoice_id': invoice_id,
                'product_id': item_data.get('product_id'),
                'product_name': item_data['product_name'],
                'quantity': item_data.get('quantity', 1),
                'unit': item_data.get('unit', 'Adet'),
                'unit_price': item_data.get('unit_price', 0),
                'discount_rate': item_data.get('discount_rate', 0),
                'vat_rate': item_data.get('vat_rate', 18),
                'notes': item_data.get('notes', '')
            })
            item.calculate_totals()
            
            if item.save():
                invoice.calculate_totals()
                invoice.save()
                logger.info(f"✅ Kalem eklendi: {item.product_name}")
                return True, "Kalem başarıyla eklendi!"
            else:
                return False, "Kalem eklenemedi!"
                
        except Exception as e:
            logger.error(f"Kalem ekleme hatası: {e}")
            return False, f"Sistem hatası: {str(e)}"
    
    def remove_item(self, invoice_id: int, item_id: int) -> Tuple[bool, str]:
        """Fatura kalemi sil"""
        try:
            invoice = Invoice.get_by_id(invoice_id)
            if not invoice:
                return False, "Fatura bulunamadı!"
            
            if invoice.status == 'Approved':
                return False, "Onaylanmış faturalardan kalem silinemez!"
            
            if invoice.remove_item(item_id):
                logger.info(f"✅ Kalem silindi: {item_id}")
                return True, "Kalem başarıyla silindi!"
            else:
                return False, "Kalem silinemedi!"
                
        except Exception as e:
            logger.error(f"Kalem silme hatası: {e}")
            return False, f"Sistem hatası: {str(e)}"
    
    def make_payment(self, invoice_id: int, amount: float) -> Tuple[bool, str]:
        """Fatura ödemesi yap"""
        try:
            invoice = Invoice.get_by_id(invoice_id)
            if not invoice:
                return False, "Fatura bulunamadı!"
            
            if invoice.status != 'Approved':
                return False, "Önce faturayı onaylayın!"
            
            if invoice.payment_status == 'Paid':
                return False, "Fatura zaten ödenmiş!"
            
            amt = float(amount)
            if amt <= 0:
                return False, "Geçerli bir miktar girin!"
            
            rem = float(invoice.remaining_amount or 0)
            tot = float(invoice.grand_total or 0)
            if tot <= 0:
                return False, "Fatura tutarı 0 olduğu için ödeme alınamaz!"
            paid = float(invoice.paid_amount or 0)
            if invoice.payment_status != 'Paid' and rem <= 0.001 and tot > paid:
                rem = max(0.0, tot - paid)
                invoice.remaining_amount = rem

            if amt > rem + 0.001:
                return False, f"Girilen tutar kalan borçtan fazla olamaz! Kalan: {rem:,.2f} TL"
            
            if invoice.make_payment(amt):
                # Cari bakiyesini kesin olarak senkronize et (ödenen tutar borçtan düşülür)
                if invoice.customer_id:
                    from .customer_service import CustomerService
                    CustomerService().sync_customer_balance(invoice.customer_id)

                logger.info(f"✅ Ödeme yapıldı: {invoice.invoice_no} - {amt} TL")
                rem_after = float(invoice.remaining_amount or 0)
                status_info = "Fatura tamamen kapatıldı (Ödendi)!" if rem_after <= 0 else f"Kısmi ödeme yapıldı! Kalan: {rem_after:,.2f} TL"
                return True, f"Ödeme başarıyla işlendi! {status_info}"
            else:
                return False, "Ödeme yapılamadı!"
                
        except Exception as e:
            logger.error(f"Ödeme hatası: {e}")
            return False, f"Sistem hatası: {str(e)}"
    
    def _create_journal_entries(self, invoice: Invoice, customer: Customer, user_id: int):
        """Muhasebe kayıtlarını oluştur"""
        try:
            # Fatura numarası boşsa veritabanından çek veya yedek üret
            if not invoice.invoice_no and invoice.id:
                row = db.fetch_one("SELECT invoice_no FROM Invoices WHERE id = %s", (invoice.id,))
                if row and row.get('invoice_no'):
                    invoice.invoice_no = row['invoice_no']
            inv_no = invoice.invoice_no or f"FAT-{invoice.id}"
            cust_name = customer.title if (customer and customer.title) else "Müşteri"

            entries = []
            
            if invoice.invoice_type == 'Sales':
                # Satış faturası
                # 120 - Alıcılar (Borç)
                entries.append({
                    'account_code': '120',
                    'account_name': 'ALICILAR',
                    'debit': invoice.grand_total,
                    'credit': 0,
                    'explanation': f"{inv_no} - {cust_name}",
                    'invoice_id': invoice.id
                })
                
                # 600 - Yurtiçi Satışlar (Alacak)
                entries.append({
                    'account_code': '600',
                    'account_name': 'YURTİÇİ SATIŞLAR',
                    'debit': 0,
                    'credit': invoice.total,
                    'explanation': f"{inv_no} - {cust_name}",
                    'invoice_id': invoice.id
                })
                
                # 391 - Hesaplanan KDV (Alacak)
                if invoice.vat_total > 0:
                    entries.append({
                        'account_code': '391',
                        'account_name': 'HESAPLANAN KDV',
                        'debit': 0,
                        'credit': invoice.vat_total,
                        'explanation': f"{inv_no} - KDV",
                        'invoice_id': invoice.id
                    })
                
            elif invoice.invoice_type == 'Purchase':
                # Alış faturası
                # 320 - Satıcılar (Alacak)
                entries.append({
                    'account_code': '320',
                    'account_name': 'SATICILAR',
                    'debit': 0,
                    'credit': invoice.grand_total,
                    'explanation': f"{inv_no} - {cust_name}",
                    'invoice_id': invoice.id
                })
                
                # 150 - İlk Madde ve Malzeme (Borç)
                entries.append({
                    'account_code': '150',
                    'account_name': 'İLK MADDE VE MALZEME',
                    'debit': invoice.total,
                    'credit': 0,
                    'explanation': f"{inv_no} - {cust_name}",
                    'invoice_id': invoice.id
                })
                
                # 191 - İndirilecek KDV (Borç)
                if invoice.vat_total > 0:
                    entries.append({
                        'account_code': '191',
                        'account_name': 'İNDİRİLECEK KDV',
                        'debit': invoice.vat_total,
                        'credit': 0,
                        'explanation': f"{inv_no} - KDV",
                        'invoice_id': invoice.id
                    })
            
            # Kaydet
            if entries:
                JournalEntry.save_double_entry(invoice.branch_id, entries, user_id)
                
        except Exception as e:
            logger.error(f"Muhasebe kaydı oluşturma hatası: {e}")
    
    def get_invoice_report(self, branch_id: int, start_date: str, 
                          end_date: str) -> List[Dict]:
        """Fatura raporu"""
        try:
            return Invoice.get_report(branch_id, start_date, end_date)
        except Exception as e:
            logger.error(f"Rapor hatası: {e}")
            return []
    
    def get_invoice_stats(self, branch_id: int, start_date: str, 
                         end_date: str) -> Dict:
        """Fatura istatistikleri (Nakit vs Kart/POS ayrımı ile)"""
        try:
            stats = db.fetch_one("""
                SELECT 
                    COUNT(*) as total_invoices,
                    COALESCE(SUM(CASE WHEN invoice_type = 'Sales' THEN grand_total ELSE 0 END), 0) as total_sales,
                    COALESCE(SUM(CASE WHEN invoice_type = 'Sales' AND (payment_method = 'Nakit' OR payment_method IS NULL) THEN grand_total ELSE 0 END), 0) as total_cash_sales,
                    COALESCE(SUM(CASE WHEN invoice_type = 'Sales' AND payment_method != 'Nakit' THEN grand_total ELSE 0 END), 0) as total_card_sales,
                    COALESCE(SUM(CASE WHEN invoice_type = 'Purchase' THEN grand_total ELSE 0 END), 0) as total_purchases,
                    COUNT(CASE WHEN payment_status = 'Paid' THEN 1 END) as paid_invoices,
                    COUNT(CASE WHEN payment_status = 'Unpaid' THEN 1 END) as unpaid_invoices,
                    COALESCE(SUM(CASE WHEN invoice_type = 'Sales' AND payment_status != 'Paid' THEN remaining_amount ELSE 0 END), 0) as total_receivables,
                    COALESCE(SUM(CASE WHEN invoice_type = 'Purchase' AND payment_status != 'Paid' THEN remaining_amount ELSE 0 END), 0) as total_payables
                FROM Invoices
                WHERE branch_id = %s 
                AND status = 'Approved'
                AND invoice_date BETWEEN %s AND %s
            """, (branch_id, start_date, end_date))
            
            if stats:
                return {k: (v if v is not None else 0) for k, v in stats.items()}
            return {
                'total_invoices': 0,
                'total_sales': 0,
                'total_cash_sales': 0,
                'total_card_sales': 0,
                'total_purchases': 0,
                'paid_invoices': 0,
                'unpaid_invoices': 0,
                'total_receivables': 0,
                'total_payables': 0
            }
            
        except Exception as e:
            logger.error(f"İstatistik hatası: {e}")
            return {}