# src/services/customer_service.py
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from ..models.customer import Customer
from ..models.invoice import Invoice
from ..core.database import db
from ..core.logger import logger

class CustomerService:
    """Cari hesap servisi"""
    
    def __init__(self):
        self.cache = {}
        self.cache_size = 100
    
    def get_customers(self, branch_id: int, page: int = 1, 
                     page_size: int = None) -> Tuple[List[Customer], int]:
        """Cari hesapları getir (sayfalı)"""
        try:
            data, total = Customer.get_by_branch(branch_id, page, page_size)
            customers = [Customer(d) for d in data]
            return customers, total
        except Exception as e:
            logger.error(f"Cari listeleme hatası: {e}")
            return [], 0
    
    def get_customer(self, customer_id: int) -> Optional[Customer]:
        """Cari hesap detayını getir"""
        try:
            return Customer.get_by_id(customer_id)
        except Exception as e:
            logger.error(f"Cari detay hatası: {e}")
            return None
    
    def search_customers(self, branch_id: int, search_term: str, 
                        page: int = 1) -> Tuple[List[Customer], int]:
        """Cari hesap ara"""
        try:
            data, total = Customer.search(branch_id, search_term, page)
            customers = [Customer(d) for d in data]
            return customers, total
        except Exception as e:
            logger.error(f"Cari arama hatası: {e}")
            return [], 0
    
    def create_customer(self, data: Dict) -> Tuple[bool, str, Optional[Customer]]:
        """Yeni cari hesap oluştur"""
        try:
            # Validasyon
            if not data.get('title'):
                return False, "Ünvan alanı zorunludur!", None
            
            # Vergi no kontrolü
            if data.get('tax_no'):
                existing = Customer.get_by_tax_no(data['tax_no'], data['branch_id'])
                if existing:
                    return False, "Bu vergi numarası ile kayıtlı bir cari hesap zaten var!", None
            
            customer = Customer(data)
            if customer.save():
                return True, "Cari hesap başarıyla oluşturuldu!", customer
            else:
                return False, "Cari hesap oluşturulamadı!", None
                
        except Exception as e:
            logger.error(f"Cari oluşturma hatası: {e}")
            return False, f"Sistem hatası: {str(e)}", None
    
    def update_customer(self, customer_id: int, data: Dict) -> Tuple[bool, str]:
        """Cari hesap güncelle"""
        try:
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return False, "Cari hesap bulunamadı!"
            
            # Verileri güncelle
            for key, value in data.items():
                if hasattr(customer, key):
                    setattr(customer, key, value)
            
            if customer.save():
                # Cache'i temizle
                self.cache.pop(customer_id, None)
                return True, "Cari hesap başarıyla güncellendi!"
            else:
                return False, "Cari hesap güncellenemedi!"
                
        except Exception as e:
            logger.error(f"Cari güncelleme hatası: {e}")
            return False, f"Sistem hatası: {str(e)}"
    
    def delete_customer(self, customer_id: int) -> Tuple[bool, str]:
        """Cari hesap sil"""
        try:
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return False, "Cari hesap bulunamadı!"
            
            # Fatura kontrolü
            invoices, _ = Invoice.get_by_customer(customer_id, 1)
            if invoices:
                return False, "Bu cari hesaba ait faturalar var! Silinemez."
            
            if customer.delete():
                self.cache.pop(customer_id, None)
                return True, "Cari hesap başarıyla silindi!"
            else:
                return False, "Cari hesap silinemedi!"
                
        except Exception as e:
            logger.error(f"Cari silme hatası: {e}")
            return False, f"Sistem hatası: {str(e)}"
    
    def get_customer_balance(self, customer_id: int) -> float:
        """Cari bakiye getir"""
        try:
            customer = Customer.get_by_id(customer_id)
            return customer.balance if customer else 0
        except Exception as e:
            logger.error(f"Bakiye getirme hatası: {e}")
            return 0
    
    def get_customer_invoices(self, customer_id: int, limit: int = 50) -> List[Dict]:
        """Cari hesap faturalarını getir"""
        try:
            customer = Customer.get_by_id(customer_id)
            if customer:
                return customer.get_invoices(limit)
            return []
        except Exception as e:
            logger.error(f"Fatura getirme hatası: {e}")
            return []
    
    def get_customer_balance_history(self, customer_id: int, start_date: str, 
                                   end_date: str) -> List[Dict]:
        """Bakiye geçmişi getir"""
        try:
            customer = Customer.get_by_id(customer_id)
            if customer:
                return customer.get_balance_history(start_date, end_date)
            return []
        except Exception as e:
            logger.error(f"Bakiye geçmişi hatası: {e}")
            return []
    
    def export_customers(self, branch_id: int, file_path: str) -> bool:
        """Cari hesapları Excel'e aktar"""
        try:
            import pandas as pd
            customers, _ = self.get_customers(branch_id, 1, 9999)
            
            data = []
            for c in customers:
                data.append({
                    'Kod': c.customer_code,
                    'Ünvan': c.title,
                    'Vergi No': c.tax_no,
                    'Vergi Dairesi': c.tax_office,
                    'Telefon': c.phone,
                    'Email': c.email,
                    'Adres': c.address,
                    'Bakiye': c.balance,
                    'Kredi Limiti': c.credit_limit,
                    'Tür': 'Tedarikçi' if c.is_supplier else 'Müşteri',
                    'Durum': 'Aktif' if c.is_active else 'Pasif'
                })
            
            df = pd.DataFrame(data)
            df.to_excel(file_path, sheet_name='Cari Hesaplar', index=False)
            
            logger.info(f"Cari hesaplar Excel'e aktarıldı: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Excel aktarım hatası: {e}")
            return False
    
    def get_customer_stats(self, branch_id: int) -> Dict:
        """Cari istatistikler"""
        try:
            stats = db.fetch_one("""
                SELECT 
                    COUNT(*) as total_customers,
                    COUNT(CASE WHEN is_supplier = FALSE THEN 1 END) as total_customers_only,
                    COUNT(CASE WHEN is_supplier = TRUE THEN 1 END) as total_suppliers,
                    SUM(CASE 
                        WHEN is_supplier = FALSE AND balance > 0 THEN balance 
                        WHEN is_supplier = TRUE AND balance < 0 THEN -balance
                        ELSE 0 
                    END) as total_receivables,
                    SUM(CASE 
                        WHEN is_supplier = TRUE AND balance > 0 THEN balance 
                        WHEN is_supplier = FALSE AND balance < 0 THEN -balance
                        ELSE 0 
                    END) as total_payables,
                    AVG(balance) as avg_balance
                FROM Customers
                WHERE branch_id = %s AND is_active = TRUE
            """, (branch_id,))
            
            return stats if stats else {}
            
        except Exception as e:
            logger.error(f"İstatistik hatası: {e}")
            return {}

    def get_companies_balance_summary(self, branch_id: Optional[int] = None) -> Dict:
        """
        Tüm firmaların (müşteri ve tedarikçi) faturalaşma, alacak ve verecek dökümünü ve
        genel toplam KPI metriklerini getirir.
        """
        try:
            sql = """
                SELECT 
                    c.id, c.customer_code, c.title, c.phone, c.tax_no, c.tax_office, 
                    c.is_supplier, c.balance, c.branch_id,
                    b.name as branch_name,
                    COUNT(i.id) as invoice_count,
                    COUNT(CASE WHEN (i.remaining_amount > 0 OR i.payment_status != 'Paid') AND (i.status IS NULL OR i.status != 'Cancelled') THEN 1 END) as unpaid_invoice_count,
                    COALESCE(SUM(CASE WHEN i.status IS NULL OR i.status != 'Cancelled' THEN i.grand_total ELSE 0 END), 0) as total_invoiced,
                    COALESCE(SUM(CASE WHEN i.status IS NULL OR i.status != 'Cancelled' THEN i.paid_amount ELSE 0 END), 0) as total_paid,
                    COALESCE(SUM(CASE WHEN i.status IS NULL OR i.status != 'Cancelled' THEN 
                        CASE WHEN i.payment_status = 'Paid' THEN 0 
                             ELSE COALESCE(i.remaining_amount, i.grand_total - COALESCE(i.paid_amount, 0)) 
                        END ELSE 0 END), 0) as total_remaining,
                    COALESCE(SUM(CASE WHEN i.invoice_type IN ('Sales', 'Satış') AND (i.status IS NULL OR i.status != 'Cancelled') THEN 
                        CASE WHEN i.payment_status = 'Paid' THEN 0 
                             ELSE COALESCE(i.remaining_amount, i.grand_total - COALESCE(i.paid_amount, 0)) 
                        END ELSE 0 END), 0) as sales_unpaid,
                    COALESCE(SUM(CASE WHEN i.invoice_type IN ('Purchase', 'Alış') AND (i.status IS NULL OR i.status != 'Cancelled') THEN 
                        CASE WHEN i.payment_status = 'Paid' THEN 0 
                             ELSE COALESCE(i.remaining_amount, i.grand_total - COALESCE(i.paid_amount, 0)) 
                        END ELSE 0 END), 0) as purchase_unpaid,
                    COALESCE(SUM(CASE WHEN i.invoice_type IN ('Sales', 'Satış') AND (i.status IS NULL OR i.status != 'Cancelled') THEN i.grand_total ELSE 0 END), 0) as sales_total,
                    COALESCE(SUM(CASE WHEN i.invoice_type IN ('Purchase', 'Alış') AND (i.status IS NULL OR i.status != 'Cancelled') THEN i.grand_total ELSE 0 END), 0) as purchase_total
                FROM Customers c
                INNER JOIN Invoices i ON i.customer_id = c.id
                LEFT JOIN Branches b ON b.id = i.branch_id
                WHERE (c.is_active = TRUE OR c.is_active IS NULL)
                  AND (i.status IS NULL OR i.status != 'Cancelled')
            """
            params = []
            if branch_id:
                sql += " AND i.branch_id = %s AND (c.branch_id = %s OR c.branch_id IS NULL)"
                params.append(branch_id)
                params.append(branch_id)
            
            sql += """
                GROUP BY c.id, c.customer_code, c.title, c.phone, c.tax_no, c.tax_office, c.is_supplier, c.balance, c.branch_id, b.name
                ORDER BY c.title ASC
            """
            rows = db.fetch_all(sql, tuple(params) if params else ())
            
            companies = []
            total_receivables = Decimal('0.00')
            total_payables = Decimal('0.00')
            total_invoiced_sum = Decimal('0.00')
            total_sales_sum = Decimal('0.00')
            total_purchases_sum = Decimal('0.00')
            cust_debtor_count = 0
            supp_creditor_count = 0
            unpaid_invoices_count = 0
            unpaid_invoices_amount = Decimal('0.00')
            
            for r in rows:
                bal = Decimal(str(r.get('balance') or 0))
                s_unpaid = Decimal(str(r.get('sales_unpaid') or 0))
                p_unpaid = Decimal(str(r.get('purchase_unpaid') or 0))
                inv_cnt = int(r.get('invoice_count') or 0)
                unpaid_inv_cnt = int(r.get('unpaid_invoice_count') or 0)
                tot_inv = Decimal(str(r.get('total_invoiced') or 0))
                tot_paid = Decimal(str(r.get('total_paid') or 0))
                tot_rem = Decimal(str(r.get('total_remaining') or 0))
                sales_tot = Decimal(str(r.get('sales_total') or 0))
                purch_tot = Decimal(str(r.get('purchase_total') or 0))
                is_supp = bool(r.get('is_supplier'))
                
                total_invoiced_sum += tot_inv
                total_sales_sum += sales_tot
                total_purchases_sum += purch_tot
                
                # Alacak & Verecek Hesaplama:
                # Faturalı firmalarda borç/alacak faturaların gerçek kalan tutarıdır (remaining_amount).
                if inv_cnt > 0:
                    receivable = s_unpaid
                    payable = p_unpaid
                    if is_supp and payable == Decimal('0.00') and receivable == Decimal('0.00') and bal > Decimal('0.001'):
                        payable = bal
                    elif not is_supp and receivable == Decimal('0.00') and payable == Decimal('0.00') and bal > Decimal('0.001'):
                        receivable = bal
                else:
                    # Faturası olmayan sadece açılış bakiyesi ile çalışan firmalar
                    if is_supp:
                        if bal > Decimal('0.001'):
                            payable = bal
                            receivable = Decimal('0.00')
                        elif bal < Decimal('-0.001'):
                            payable = Decimal('0.00')
                            receivable = -bal
                        else:
                            payable = Decimal('0.00')
                            receivable = Decimal('0.00')
                    else:
                        if bal > Decimal('0.001'):
                            receivable = bal
                            payable = Decimal('0.00')
                        elif bal < Decimal('-0.001'):
                            receivable = Decimal('0.00')
                            payable = -bal
                        else:
                            receivable = Decimal('0.00')
                            payable = Decimal('0.00')

                net = receivable - payable
                
                if receivable > Decimal('0.001'):
                    total_receivables += receivable
                    cust_debtor_count += 1
                if payable > Decimal('0.001'):
                    total_payables += payable
                    supp_creditor_count += 1
                
                if tot_rem > Decimal('0.001'):
                    unpaid_invoices_amount += tot_rem
                unpaid_invoices_count += unpaid_inv_cnt
                
                effective_balance = payable if is_supp else receivable

                companies.append({
                    'id': r['id'],
                    'customer_code': r.get('customer_code') or f"C{r['id']:06d}",
                    'title': r.get('title') or 'İsimsiz Firma',
                    'phone': r.get('phone') or '-',
                    'tax_no': r.get('tax_no') or '-',
                    'tax_office': r.get('tax_office') or '-',
                    'is_supplier': is_supp,
                    'branch_id': r.get('branch_id'),
                    'branch_name': r.get('branch_name') or 'Merkez',
                    'invoice_count': inv_cnt,
                    'total_invoiced': float(tot_inv),
                    'total_paid': float(tot_paid),
                    'total_remaining': float(tot_rem),
                    'sales_total': float(sales_tot),
                    'purchase_total': float(purch_tot),
                    'receivable': float(receivable),
                    'payable': float(payable),
                    'net_balance': float(net),
                    'balance': float(effective_balance)
                })
            
            return {
                'companies': companies,
                'total_receivables': float(total_receivables),
                'total_payables': float(total_payables),
                'net_balance': float(total_receivables - total_payables),
                'total_companies': len(companies),
                'total_invoiced': float(total_invoiced_sum),
                'total_sales': float(total_sales_sum),
                'total_purchases': float(total_purchases_sum),
                'cust_debtor_count': cust_debtor_count,
                'supp_creditor_count': supp_creditor_count,
                'unpaid_invoices_count': unpaid_invoices_count,
                'unpaid_invoices_amount': float(unpaid_invoices_amount)
            }
        except Exception as e:
            logger.error(f"get_companies_balance_summary hatası: {e}")
            return {
                'companies': [], 'total_receivables': 0.0, 'total_payables': 0.0,
                'net_balance': 0.0, 'total_companies': 0, 'total_invoiced': 0.0,
                'total_sales': 0.0, 'total_purchases': 0.0,
                'cust_debtor_count': 0, 'supp_creditor_count': 0,
                'unpaid_invoices_count': 0, 'unpaid_invoices_amount': 0.0
            }

    def get_customer_all_invoices(self, customer_id: int, customer_title: Optional[str] = None, branch_id: Optional[int] = None) -> Tuple[Optional[Dict], List[Dict]]:
        """
        Belirtilen müşteri/firma için farklı tarihlerde kesilen tüm faturaları ve
        fatura kalem özetlerini getirir. branch_id verilirse yalnızca o şubenin faturalarını döndürür.
        """
        try:
            cust = Customer.get_by_id(customer_id)
            c_title = cust.title if cust else (customer_title or "")
            
            cust_conditions = ["i.customer_id = %s"]
            params = [customer_id]
            if c_title and c_title.strip():
                cust_conditions.append("(c.title IS NOT NULL AND LOWER(TRIM(c.title)) = LOWER(TRIM(%s)))")
                params.append(c_title.strip())
            
            where_clause = f"({' OR '.join(cust_conditions)})"
            if branch_id:
                where_clause += " AND i.branch_id = %s"
                params.append(branch_id)

            sql = f"""
                SELECT 
                    i.id, i.invoice_no, i.invoice_date, i.invoice_type, i.grand_total,
                    i.paid_amount, i.remaining_amount, i.payment_method, i.payment_status,
                    i.status, i.notes, i.branch_id,
                    b.name as branch_name,
                    (SELECT COUNT(*) FROM InvoiceItems WHERE invoice_id = i.id) as item_count,
                    (SELECT STRING_AGG(product_name || ' (' || quantity || ' ' || COALESCE(unit, 'Adet') || ')', ', ') 
                     FROM (SELECT product_name, quantity, unit FROM InvoiceItems WHERE invoice_id = i.id ORDER BY id ASC LIMIT 3) sub) as items_summary
                FROM Invoices i
                LEFT JOIN Branches b ON b.id = i.branch_id
                LEFT JOIN Customers c ON c.id = i.customer_id
                WHERE {where_clause}
                ORDER BY i.invoice_date DESC, i.id DESC
            """
            invoices = db.fetch_all(sql, tuple(params))
            
            cust_dict = None
            if cust:
                cust_dict = {
                    'id': cust.id,
                    'customer_code': cust.customer_code,
                    'title': cust.title,
                    'phone': cust.phone or '-',
                    'tax_no': cust.tax_no or '-',
                    'tax_office': cust.tax_office or '-',
                    'is_supplier': bool(cust.is_supplier),
                    'balance': float(cust.balance or 0)
                }
            elif invoices:
                cust_dict = {
                    'id': customer_id,
                    'customer_code': f"C{customer_id:06d}",
                    'title': c_title or "Müşteri",
                    'phone': '-',
                    'tax_no': '-',
                    'tax_office': '-',
                    'is_supplier': False,
                    'balance': 0.0
                }
            
            formatted_invoices = []
            for inv in (invoices or []):
                tot = float(inv.get('grand_total') or 0.0)
                paid = float(inv.get('paid_amount') or 0.0)
                rem_val = inv.get('remaining_amount')
                p_status = inv.get('payment_status', '')
                
                if p_status == 'Paid':
                    rem = 0.0
                    if paid == 0 and tot > 0:
                        paid = tot
                elif rem_val is not None:
                    rem = float(rem_val)
                else:
                    rem = max(0.0, tot - paid)
                
                formatted_invoices.append({
                    'id': inv['id'],
                    'invoice_no': inv.get('invoice_no') or f"FAT-{inv['id']}",
                    'invoice_date': inv.get('invoice_date'),
                    'invoice_type': inv.get('invoice_type', 'Sales'),
                    'branch_id': inv.get('branch_id'),
                    'branch_name': inv.get('branch_name') or 'Merkez',
                    'grand_total': tot,
                    'paid_amount': paid,
                    'remaining_amount': rem,
                    'payment_method': inv.get('payment_method') or 'Nakit',
                    'payment_status': p_status,
                    'status': inv.get('status', 'Approved'),
                    'notes': inv.get('notes') or '',
                    'item_count': int(inv.get('item_count') or 0),
                    'items_summary': inv.get('items_summary') or '-'
                })
            
            return cust_dict, formatted_invoices
        except Exception as e:
            logger.error(f"get_customer_all_invoices hatası: {e}")
            return None, []

    def sync_customer_balance(self, customer_id: int) -> Decimal:
        """
        Cari hesabın bakiyesini faturalarındaki gerçek kalan tutar (remaining_amount) ile senkronize eder.
        Ödenen tutarların borç olarak görünmesini kesinlikle engeller.
        """
        try:
            cust = Customer.get_by_id(customer_id)
            if not cust:
                return Decimal('0.00')

            inv_stats = db.fetch_one("""
                SELECT 
                    COUNT(id) as inv_cnt,
                    COALESCE(SUM(CASE WHEN invoice_type IN ('Purchase', 'Alış') AND (status IS NULL OR status != 'Cancelled') THEN 
                        CASE WHEN payment_status = 'Paid' THEN 0 
                             ELSE COALESCE(remaining_amount, grand_total - COALESCE(paid_amount, 0)) 
                        END ELSE 0 END), 0) as p_rem,
                    COALESCE(SUM(CASE WHEN invoice_type IN ('Sales', 'Satış') AND (status IS NULL OR status != 'Cancelled') THEN 
                        CASE WHEN payment_status = 'Paid' THEN 0 
                             ELSE COALESCE(remaining_amount, grand_total - COALESCE(paid_amount, 0)) 
                        END ELSE 0 END), 0) as s_rem
                FROM Invoices
                WHERE customer_id = %s
            """, (customer_id,))

            if not inv_stats or int(inv_stats['inv_cnt'] or 0) == 0:
                # Faturası yoksa açılış bakiyesini koru
                return Decimal(str(cust.balance or 0))

            is_supp = bool(cust.is_supplier)
            p_rem = Decimal(str(inv_stats['p_rem'] or 0))
            s_rem = Decimal(str(inv_stats['s_rem'] or 0))

            if is_supp:
                new_bal = p_rem - s_rem
            else:
                new_bal = s_rem - p_rem

            from ..core.decimal_utils import round_currency
            new_bal = round_currency(new_bal)

            db.execute_query("""
                UPDATE Customers 
                SET balance = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (new_bal, customer_id))

            cust.balance = new_bal
            self.cache.pop(customer_id, None)
            logger.info(f"✅ Cari bakiye faturalarla senkronize edildi: {cust.title} -> {new_bal} TL")
            return new_bal
        except Exception as e:
            logger.error(f"sync_customer_balance hatası: {e}")
            return Decimal('0.00')

    def sync_all_customers_balances(self) -> int:
        """
        Tüm cari hesapların bakiyelerini faturaların kalan tutarlarıyla senkronize eder.
        """
        try:
            custs = db.fetch_all("SELECT DISTINCT customer_id FROM Invoices WHERE customer_id IS NOT NULL")
            count = 0
            for c in custs:
                self.sync_customer_balance(c['customer_id'])
                count += 1
            return count
        except Exception as e:
            logger.error(f"sync_all_customers_balances hatası: {e}")
            return 0