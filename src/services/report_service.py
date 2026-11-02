# src/services/report_service.py
from typing import Dict, List
from ..core.database import db
from ..core.logger import logger
from ..models.journal import JournalEntry

class ReportService:
    """Rapor servisi"""
    
    def __init__(self):
        self.cache = {}
    
    def get_balance_sheet(self, branch_id: int, end_date: str) -> Dict:
        """Bilanço raporu"""
        try:
            # Aktif hesaplar (100-599)
            assets = db.fetch_all("""
                SELECT 
                    account_code,
                    account_name,
                    SUM(debit) - SUM(credit) as balance
                FROM JournalEntries
                WHERE branch_id = %s 
                AND entry_date <= %s
                AND account_code BETWEEN '100' AND '599'
                GROUP BY account_code, account_name
                HAVING SUM(debit) - SUM(credit) != 0
                ORDER BY account_code
            """, (branch_id, end_date))
            
            # Pasif hesaplar (600-999)
            liabilities = db.fetch_all("""
                SELECT 
                    account_code,
                    account_name,
                    SUM(credit) - SUM(debit) as balance
                FROM JournalEntries
                WHERE branch_id = %s 
                AND entry_date <= %s
                AND account_code BETWEEN '600' AND '999'
                GROUP BY account_code, account_name
                HAVING SUM(credit) - SUM(debit) != 0
                ORDER BY account_code
            """, (branch_id, end_date))
            
            total_assets = sum(a['balance'] for a in assets)
            total_liabilities = sum(l['balance'] for l in liabilities)
            
            return {
                'assets': assets,
                'liabilities': liabilities,
                'total_assets': total_assets,
                'total_liabilities': total_liabilities,
                'equity': total_assets - total_liabilities
            }
            
        except Exception as e:
            logger.error(f"Bilanço hatası: {e}")
            return {}
    
    def get_income_statement(self, branch_id: int, start_date: str, 
                            end_date: str) -> Dict:
        """Gelir tablosu"""
        try:
            # Gelir hesapları (600-699)
            revenues = db.fetch_all("""
                SELECT 
                    account_code,
                    account_name,
                    SUM(credit) as total_credit,
                    SUM(debit) as total_debit,
                    SUM(credit) - SUM(debit) as net_amount
                FROM JournalEntries
                WHERE branch_id = %s 
                AND entry_date BETWEEN %s AND %s
                AND account_code BETWEEN '600' AND '699'
                GROUP BY account_code, account_name
                ORDER BY account_code
            """, (branch_id, start_date, end_date))
            
            # Gider hesapları (700-799)
            expenses = db.fetch_all("""
                SELECT 
                    account_code,
                    account_name,
                    SUM(debit) as total_debit,
                    SUM(credit) as total_credit,
                    SUM(debit) - SUM(credit) as net_amount
                FROM JournalEntries
                WHERE branch_id = %s 
                AND entry_date BETWEEN %s AND %s
                AND account_code BETWEEN '700' AND '799'
                GROUP BY account_code, account_name
                ORDER BY account_code
            """, (branch_id, start_date, end_date))
            
            total_revenue = sum(r['net_amount'] for r in revenues)
            total_expenses = sum(e['net_amount'] for e in expenses)
            net_profit = total_revenue - total_expenses
            
            return {
                'revenues': revenues,
                'expenses': expenses,
                'total_revenue': total_revenue,
                'total_expenses': total_expenses,
                'net_profit': net_profit
            }
            
        except Exception as e:
            logger.error(f"Gelir tablosu hatası: {e}")
            return {}
    
    def get_trial_balance(self, branch_id: int, end_date: str) -> Dict:
        """Deneme bilançosu"""
        try:
            return JournalEntry.get_trial_balance(branch_id, end_date)
        except Exception as e:
            logger.error(f"Deneme bilançosu hatası: {e}")
            return {}
    
    def get_customer_aging(self, branch_id: int, as_of_date: str) -> List[Dict]:
        """Cari yaşlandırma raporu"""
        try:
            # 0-30 gün, 31-60 gün, 61-90 gün, 90+ gün
            aging = db.fetch_all("""
                SELECT 
                    c.id as customer_id,
                    c.title as customer_name,
                    c.tax_no,
                    c.phone,
                    c.balance,
                    COALESCE(SUM(CASE 
                        WHEN i.invoice_date >= (%s::date - INTERVAL '30 days') 
                        THEN i.remaining_amount ELSE 0 END), 0) as day_1_30,
                    COALESCE(SUM(CASE 
                        WHEN i.invoice_date BETWEEN (%s::date - INTERVAL '60 days') AND (%s::date - INTERVAL '31 days')
                        THEN i.remaining_amount ELSE 0 END), 0) as day_31_60,
                    COALESCE(SUM(CASE 
                        WHEN i.invoice_date BETWEEN (%s::date - INTERVAL '90 days') AND (%s::date - INTERVAL '61 days')
                        THEN i.remaining_amount ELSE 0 END), 0) as day_61_90,
                    COALESCE(SUM(CASE 
                        WHEN i.invoice_date < (%s::date - INTERVAL '90 days')
                        THEN i.remaining_amount ELSE 0 END), 0) as day_90_plus
                FROM Customers c
                LEFT JOIN Invoices i ON i.customer_id = c.id 
                    AND (i.status IS NULL OR i.status != 'Cancelled') 
                    AND i.payment_status != 'Paid'
                    AND i.invoice_type = 'Sales'
                WHERE c.branch_id = %s AND c.is_active = TRUE
                GROUP BY c.id, c.title, c.tax_no, c.phone, c.balance
                HAVING c.balance != 0 OR SUM(i.remaining_amount) != 0
                ORDER BY c.balance DESC
            """, (
                as_of_date, as_of_date, as_of_date,
                as_of_date, as_of_date, as_of_date,
                branch_id
            ))
            
            return aging if aging else []
            
        except Exception as e:
            logger.error(f"Yaşlandırma hatası: {e}")
            return []
    
    def get_daily_summary(self, branch_id: int, date: str) -> Dict:
        """Günlük özet raporu (Nakit vs Kart ayrımı ile)"""
        try:
            summary = db.fetch_one("""
                SELECT 
                    COUNT(DISTINCT i.id) as total_invoices,
                    COUNT(DISTINCT c.id) as unique_customers,
                    COALESCE(SUM(CASE WHEN i.invoice_type = 'Sales' THEN i.grand_total END), 0) as daily_sales,
                    COALESCE(SUM(CASE WHEN i.invoice_type = 'Sales' AND (i.payment_method = 'Nakit' OR i.payment_method IS NULL) THEN i.grand_total END), 0) as daily_cash_sales,
                    COALESCE(SUM(CASE WHEN i.invoice_type = 'Sales' AND i.payment_method != 'Nakit' THEN i.grand_total END), 0) as daily_card_sales,
                    COALESCE(SUM(CASE WHEN i.invoice_type = 'Purchase' THEN i.grand_total END), 0) as daily_purchases,
                    COALESCE(SUM(CASE WHEN i.invoice_type = 'Sales' AND i.payment_status = 'Paid' THEN i.grand_total END), 0) as daily_collections
                FROM Invoices i
                LEFT JOIN Customers c ON c.id = i.customer_id
                WHERE i.branch_id = %s 
                AND i.invoice_date = %s
                AND (i.status IS NULL OR i.status != 'Cancelled')
            """, (branch_id, date))
            
            if summary:
                return {k: (v if v is not None else 0) for k, v in summary.items()}
            return {
                'total_invoices': 0,
                'unique_customers': 0,
                'daily_sales': 0,
                'daily_cash_sales': 0,
                'daily_card_sales': 0,
                'daily_purchases': 0,
                'daily_collections': 0
            }
            
        except Exception as e:
            logger.error(f"Günlük özet hatası: {e}")
            return {}
    
    def get_monthly_summary(self, branch_id: int, year: int, month: int) -> Dict:
        """Aylık özet raporu"""
        try:
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{31 if month in [1,3,5,7,8,10,12] else 30}"
            
            summary = db.fetch_one("""
                SELECT 
                    COUNT(*) as total_invoices,
                    COALESCE(SUM(CASE WHEN invoice_type = 'Sales' THEN grand_total END), 0) as monthly_sales,
                    COALESCE(SUM(CASE WHEN invoice_type = 'Purchase' THEN grand_total END), 0) as monthly_purchases,
                    AVG(grand_total) as avg_invoice_amount,
                    COUNT(DISTINCT customer_id) as active_customers
                FROM Invoices
                WHERE branch_id = %s 
                AND invoice_date BETWEEN %s AND %s
                AND (status IS NULL OR status != 'Cancelled')
            """, (branch_id, start_date, end_date))
            
            if summary:
                return {k: (v if v is not None else 0) for k, v in summary.items()}
            return {
                'total_invoices': 0,
                'monthly_sales': 0,
                'monthly_purchases': 0,
                'avg_invoice_amount': 0,
                'active_customers': 0
            }
            
        except Exception as e:
            logger.error(f"Aylık özet hatası: {e}")
            return {}

    def get_invoice_stats(self, branch_id: int, start_date: str, end_date: str) -> Dict:
        """Fatura istatistikleri ve Nakit vs Kart kırılımı"""
        from .invoice_service import InvoiceService
        return InvoiceService().get_invoice_stats(branch_id, start_date, end_date)

    def get_invoice_report(self, branch_id: int, start_date: str, end_date: str) -> List[Dict]:
        """Fatura raporu"""
        from .invoice_service import InvoiceService
        return InvoiceService().get_invoice_report(branch_id, start_date, end_date)
    
    def export_report_to_excel(self, report_type: str, branch_id: int, 
                              start_date: str, end_date: str, file_path: str) -> bool:
        """Raporu Excel'e aktar"""
        try:
            import pandas as pd
            data = {}
            
            if report_type == 'balance_sheet':
                data = self.get_balance_sheet(branch_id, end_date)
                df_assets = pd.DataFrame(data.get('assets', []))
                df_liabilities = pd.DataFrame(data.get('liabilities', []))
                
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    df_assets.to_excel(writer, sheet_name='Aktifler', index=False)
                    df_liabilities.to_excel(writer, sheet_name='Pasifler', index=False)
                    
                    # Özet
                    summary_df = pd.DataFrame({
                        'Toplam Aktif': [data.get('total_assets', 0)],
                        'Toplam Pasif': [data.get('total_liabilities', 0)],
                        'Öz Sermaye': [data.get('equity', 0)]
                    })
                    summary_df.to_excel(writer, sheet_name='Özet', index=False)
                    
            elif report_type == 'income_statement':
                data = self.get_income_statement(branch_id, start_date, end_date)
                df_revenues = pd.DataFrame(data.get('revenues', []))
                df_expenses = pd.DataFrame(data.get('expenses', []))
                
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    df_revenues.to_excel(writer, sheet_name='Gelirler', index=False)
                    df_expenses.to_excel(writer, sheet_name='Giderler', index=False)
                    
                    summary_df = pd.DataFrame({
                        'Toplam Gelir': [data.get('total_revenue', 0)],
                        'Toplam Gider': [data.get('total_expenses', 0)],
                        'Net Kar': [data.get('net_profit', 0)]
                    })
                    summary_df.to_excel(writer, sheet_name='Özet', index=False)
                    
            elif report_type == 'customer_aging':
                data = self.get_customer_aging(branch_id, end_date)
                df = pd.DataFrame(data)
                df.to_excel(file_path, sheet_name='Yaşlandırma', index=False)
            
            logger.info(f"✅ Rapor oluşturuldu: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Rapor oluşturma hatası: {e}")
            return False