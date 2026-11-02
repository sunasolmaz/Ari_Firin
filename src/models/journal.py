# src/models/journal.py
from datetime import datetime
from typing import Optional, List, Dict
from decimal import Decimal
from ..core.database import db
from ..core.logger import logger
from ..core.decimal_utils import to_decimal, round_currency

class JournalEntry:
    """Muhasebe kaydı modeli"""
    
    def __init__(self, data: Dict = None):
        if data:
            self.id = data.get('id')
            self.branch_id = data.get('branch_id')
            self.entry_date = data.get('entry_date')
            self.account_code = data.get('account_code')
            self.account_name = data.get('account_name')
            self.explanation = data.get('explanation')
            self.debit = round_currency(to_decimal(data.get('debit', 0)))
            self.credit = round_currency(to_decimal(data.get('credit', 0)))
            self.invoice_id = data.get('invoice_id')
            self.reference_no = data.get('reference_no')
            self.currency = data.get('currency', 'TRY')
            self.created_by = data.get('created_by')
            self.created_at = data.get('created_at')
    
    def is_balanced(self) -> bool:
        """Kayıt denk mi kontrol et"""
        return self.debit == self.credit
    
    def save(self) -> bool:
        """Muhasebe kaydını kaydet"""
        try:
            if self.id:
                # Güncelle
                db.execute_query("""
                    UPDATE JournalEntries 
                    SET entry_date = %s, account_code = %s, account_name = %s,
                        explanation = %s, debit = %s, credit = %s,
                        invoice_id = %s, reference_no = %s, currency = %s
                    WHERE id = %s
                """, (self.entry_date, self.account_code, self.account_name,
                      self.explanation, self.debit, self.credit,
                      self.invoice_id, self.reference_no, self.currency,
                      self.id))
            else:
                # Yeni ekle
                result = db.execute_query("""
                    INSERT INTO JournalEntries 
                    (branch_id, entry_date, account_code, account_name,
                     explanation, debit, credit, invoice_id,
                     reference_no, currency, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (self.branch_id, self.entry_date, self.account_code,
                      self.account_name, self.explanation, self.debit,
                      self.credit, self.invoice_id, self.reference_no,
                      self.currency, self.created_by))
                self.id = result
            
            logger.info(f"✅ Muhasebe kaydı kaydedildi: {self.account_code}")
            return True
        except Exception as e:
            logger.error(f"❌ Muhasebe kaydı kaydetme hatası: {e}")
            return False
    
    @classmethod
    def save_double_entry(cls, branch_id: int, entries: List[Dict], 
                          created_by: int) -> bool:
        """Çift taraflı muhasebe kaydı yap"""
        total_debit = sum((round_currency(to_decimal(e.get('debit', 0))) for e in entries), Decimal('0.00'))
        total_credit = sum((round_currency(to_decimal(e.get('credit', 0))) for e in entries), Decimal('0.00'))
        
        if total_debit != total_credit:
            logger.error(f"❌ Borç ({total_debit}) ve alacak ({total_credit}) eşit değil!")
            return False
        
        try:
            with db.transaction():
                for entry in entries:
                    journal = cls({
                        'branch_id': branch_id,
                        'entry_date': entry.get('entry_date', datetime.now().date()),
                        'account_code': entry['account_code'],
                        'account_name': entry['account_name'],
                        'explanation': entry.get('explanation', ''),
                        'debit': round_currency(to_decimal(entry.get('debit', 0))),
                        'credit': round_currency(to_decimal(entry.get('credit', 0))),
                        'invoice_id': entry.get('invoice_id'),
                        'reference_no': entry.get('reference_no'),
                        'currency': entry.get('currency', 'TRY'),
                        'created_by': created_by
                    })
                    if not journal.save():
                        raise Exception("Muhasebe kaydı kaydedilemedi")
            
            logger.info(f"✅ Çift taraflı kayıt başarılı: {len(entries)} kayıt")
            return True
        except Exception as e:
            logger.error(f"❌ Çift taraflı kayıt hatası: {e}")
            return False
    
    @classmethod
    def get_by_id(cls, entry_id: int) -> Optional['JournalEntry']:
        """ID'ye göre muhasebe kaydı getir"""
        data = db.fetch_one("SELECT * FROM JournalEntries WHERE id = %s", (entry_id,))
        return cls(data) if data else None
    
    @classmethod
    def get_by_branch(cls, branch_id: int, page: int = 1) -> tuple:
        """Şubeye göre muhasebe kayıtlarını getir"""
        query = "SELECT * FROM JournalEntries WHERE branch_id = %s ORDER BY entry_date DESC"
        return db.fetch_paginated(query, page, None, (branch_id,))
    
    @classmethod
    def get_by_account(cls, account_code: str, start_date: str, 
                      end_date: str) -> List[Dict]:
        """Hesap koduna göre kayıtları getir"""
        return db.fetch_all("""
            SELECT * FROM JournalEntries 
            WHERE account_code = %s 
            AND entry_date BETWEEN %s AND %s
            ORDER BY entry_date DESC
        """, (account_code, start_date, end_date))
    
    @classmethod
    def get_balance(cls, account_code: str, branch_id: int = None) -> Decimal:
        """Hesap bakiyesini hesapla"""
        query = """
            SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as balance
            FROM JournalEntries 
            WHERE account_code = %s
        """
        params = [account_code]
        
        if branch_id:
            query += " AND branch_id = %s"
            params.append(branch_id)
        
        result = db.fetch_one(query, tuple(params))
        return to_decimal(result['balance']) if result else Decimal('0.00')
    
    @classmethod
    def get_trial_balance(cls, branch_id: int, end_date: str) -> List[Dict]:
        """Deneme bilançosu getir"""
        return db.fetch_all("""
            SELECT 
                account_code,
                account_name,
                COALESCE(SUM(debit), 0) as total_debit,
                COALESCE(SUM(credit), 0) as total_credit,
                COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as balance
            FROM JournalEntries 
            WHERE branch_id = %s 
            AND entry_date <= %s
            GROUP BY account_code, account_name
            ORDER BY account_code
        """, (branch_id, end_date))