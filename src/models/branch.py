# src/models/branch.py
from typing import Optional, List, Dict
from ..core.database import db
from ..core.logger import logger


class Branch:
    """Şube modeli"""

    def __init__(self, data: Dict = None):
        if data:
            self.id = data.get('id')
            self.name = data.get('name')
            self.city = data.get('city')
            self.phone = data.get('phone')
            self.address = data.get('address')
            self.tax_no = data.get('tax_no')
            self.branch_type = data.get('branch_type', 'retail')
            self.is_active = data.get('is_active', True)
            self.created_at = data.get('created_at')
            self.updated_at = data.get('updated_at')
        else:
            self.id = None
            self.name = ""
            self.city = None
            self.phone = None
            self.address = None
            self.tax_no = None
            self.branch_type = 'retail'
            self.is_active = True
            self.created_at = None
            self.updated_at = None

    def save(self) -> bool:
        """Şubeyi kaydet (is_active ve phone dahil)"""
        try:
            if self.id:
                # Güncelle
                db.execute_query("""
                    UPDATE Branches 
                    SET name = %s, city = %s, phone = %s, address = %s, 
                        tax_no = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (self.name, self.city, self.phone, self.address,
                      self.tax_no, self.is_active, self.id))
            else:
                # Yeni ekle
                result = db.execute_query("""
                    INSERT INTO Branches (name, city, phone, address, tax_no, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (self.name, self.city, self.phone, self.address,
                      self.tax_no, self.is_active))
                if result and isinstance(result, int):
                    self.id = result

            logger.info(f"✅ Şube kaydedildi: {self.name}")
            return True
        except Exception as e:
            logger.error(f"❌ Şube kaydetme hatası: {e}")
            return False

    def delete(self) -> bool:
        """Şubeyi sil (soft delete - is_active = False)"""
        try:
            db.execute_query(
                "UPDATE Branches SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (self.id,)
            )
            logger.info(f"✅ Şube silindi: {self.name}")
            return True
        except Exception as e:
            logger.error(f"❌ Şube silme hatası: {e}")
            return False

    @classmethod
    def get_by_id(cls, branch_id: int) -> Optional['Branch']:
        """ID'ye göre şube getir"""
        data = db.fetch_one("SELECT * FROM Branches WHERE id = %s", (branch_id,))
        return cls(data) if data else None

    @classmethod
    def get_all(cls, active_only: bool = True) -> List['Branch']:
        """Tüm şubeleri getir"""
        query = "SELECT * FROM Branches"
        if active_only:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY id"

        results = db.fetch_all(query)
        return [cls(data) for data in results]

    @classmethod
    def get_by_name(cls, name: str) -> Optional['Branch']:
        """İsme göre şube getir"""
        data = db.fetch_one("SELECT * FROM Branches WHERE name = %s", (name,))
        return cls(data) if data else None

    def get_stats(self) -> Dict:
        """Şube istatistiklerini getir"""
        stats = db.fetch_one("""
            SELECT 
                COUNT(DISTINCT c.id) as customer_count,
                COUNT(DISTINCT i.id) as invoice_count,
                COALESCE(SUM(i.grand_total), 0) as total_revenue,
                COALESCE(SUM(CASE WHEN i.invoice_type = 'Purchase' THEN i.grand_total END), 0) as total_expense,
                COALESCE(SUM(CASE WHEN i.invoice_type = 'Sales' THEN i.grand_total END), 0) as total_sales
            FROM Branches b
            LEFT JOIN Customers c ON c.branch_id = b.id
            LEFT JOIN Invoices i ON i.branch_id = b.id AND (i.status IS NULL OR i.status != 'Cancelled')
            WHERE b.id = %s
            GROUP BY b.id
        """, (self.id,))

        return stats if stats else {}

    def __str__(self):
        return self.name