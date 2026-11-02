# src/models/customer.py
from typing import Optional, List, Dict
from decimal import Decimal
from ..core.database import db
from ..core.logger import logger
from ..core.decimal_utils import to_decimal, round_currency

class Customer:
    """Cari hesap modeli"""
    
    def __init__(self, data: Dict = None):
        if data:
            self.id = data.get('id')
            self.branch_id = data.get('branch_id')
            self.customer_code = data.get('customer_code')
            self.title = data.get('title')
            self.tax_no = data.get('tax_no')
            self.tax_office = data.get('tax_office')
            self.phone = data.get('phone')
            self.email = data.get('email')
            self.address = data.get('address')
            self.balance = to_decimal(data.get('balance', 0))
            self.credit_limit = to_decimal(data.get('credit_limit', 0))
            self.is_supplier = data.get('is_supplier', False)
            self.is_active = data.get('is_active', True)
            self.notes = data.get('notes')
            self.created_at = data.get('created_at')
            self.updated_at = data.get('updated_at')
    
    def save(self) -> bool:
        """Cari hesabı kaydet"""
        try:
            if self.id:
                # Güncelle
                db.execute_query("""
                    UPDATE Customers 
                    SET branch_id = %s, title = %s, tax_no = %s, tax_office = %s,
                        phone = %s, email = %s, address = %s, balance = %s,
                        credit_limit = %s, is_supplier = %s, is_active = %s,
                        notes = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (self.branch_id, self.title, self.tax_no, self.tax_office,
                      self.phone, self.email, self.address, self.balance,
                      self.credit_limit, self.is_supplier, self.is_active,
                      self.notes, self.id))
            else:
                # Yeni ekle
                result = db.execute_query("""
                    INSERT INTO Customers (branch_id, title, tax_no, tax_office,
                                          phone, email, address, balance,
                                          credit_limit, is_supplier, is_active, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (self.branch_id, self.title, self.tax_no, self.tax_office,
                      self.phone, self.email, self.address, self.balance,
                      self.credit_limit, self.is_supplier, self.is_active,
                      self.notes))
                self.id = result
            
            logger.info(f"✅ Cari hesap kaydedildi: {self.title}")
            return True
        except Exception as e:
            logger.error(f"❌ Cari hesap kaydetme hatası: {e}")
            return False
    
    def delete(self) -> bool:
        """Cari hesabı sil"""
        try:
            db.execute_query("UPDATE Customers SET is_active = FALSE WHERE id = %s", (self.id,))
            logger.info(f"✅ Cari hesap silindi: {self.title}")
            return True
        except Exception as e:
            logger.error(f"❌ Cari hesap silme hatası: {e}")
            return False
    
    def update_balance(self, amount) -> bool:
        """Cari bakiyeyi güncelle"""
        try:
            amount_dec = round_currency(amount)
            db.execute_query("""
                UPDATE Customers 
                SET balance = balance + %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (amount_dec, self.id))
            
            # Yeniden yükle
            data = db.fetch_one("SELECT balance FROM Customers WHERE id = %s", (self.id,))
            if data:
                self.balance = to_decimal(data['balance'])
            return True
        except Exception as e:
            logger.error(f"❌ Cari bakiye güncelleme hatası: {e}")
            return False
    
    @classmethod
    def get_by_id(cls, customer_id: int) -> Optional['Customer']:
        """ID'ye göre cari hesap getir"""
        data = db.fetch_one("SELECT * FROM Customers WHERE id = %s", (customer_id,))
        return cls(data) if data else None
    
    @classmethod
    def get_by_tax_no(cls, tax_no: str, branch_id: int) -> Optional['Customer']:
        """Vergi numarasına göre cari hesap getir"""
        data = db.fetch_one(
            "SELECT * FROM Customers WHERE tax_no = %s AND branch_id = %s",
            (tax_no, branch_id)
        )
        return cls(data) if data else None
    
    @classmethod
    def get_by_branch(cls, branch_id: int, page: int = 1, 
                     page_size: int = None) -> tuple:
        """Şubeye göre cari hesapları getir (sayfalı)"""
        query = "SELECT * FROM Customers WHERE branch_id = %s AND is_active = TRUE"
        return db.fetch_paginated(query, page, page_size, (branch_id,))
    
    @classmethod
    def search(cls, branch_id: int, search_term: str, page: int = 1) -> tuple:
        """Cari hesap ara"""
        query = """
            SELECT * FROM Customers 
            WHERE branch_id = %s 
            AND is_active = TRUE
            AND (title ILIKE %s OR tax_no ILIKE %s OR phone ILIKE %s)
        """
        search_pattern = f"%{search_term}%"
        params = (branch_id, search_pattern, search_pattern, search_pattern)
        return db.fetch_paginated(query, page, None, params)
    
    def get_invoices(self, limit: int = 50) -> List[Dict]:
        """Cari hesapla ilgili faturaları getir"""
        return db.fetch_all("""
            SELECT * FROM Invoices 
            WHERE customer_id = %s 
            ORDER BY invoice_date DESC
            LIMIT %s
        """, (self.id, limit))
    
    def get_balance_history(self, start_date: str, end_date: str) -> List[Dict]:
        """Bakiye geçmişini getir"""
        return db.fetch_all("""
            SELECT 
                invoice_date as date,
                invoice_no,
                grand_total as amount,
                payment_status,
                status
            FROM Invoices 
            WHERE customer_id = %s 
            AND invoice_date BETWEEN %s AND %s
            ORDER BY invoice_date DESC
        """, (self.id, start_date, end_date))
    
    def __str__(self):
        return self.title