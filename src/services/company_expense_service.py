# src/services/company_expense_service.py
"""
Genel Şirket & Ortak Giderleri Servisi
Şube ve imalathane işletme giderleri haricinde, şirket ortaklarının
şirketten aldıkları paralar, özel harcamalar, kurumsal temsil ve genel merkez
harcamalarını yönetir.
"""

from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime, date

from ..core.database import db
from ..core.logger import logger
from ..core.decimal_utils import to_decimal


class CompanyExpenseService:
    """Genel Şirket ve Ortak Harcamaları Servisi"""

    DEFAULT_CATEGORIES = [
        "Ortak Özel Harcama",
        "Ortak Avans / Kâr Payı Çekimi",
        "Şirket Temsil & Ağırlama",
        "Genel Merkez & Yönetim Gideri",
        "Resmi Harç, Noter & Hukuk",
        "Taşıt, Akaryakıt & Seyahat",
        "Finans & Bankacılık Masrafı",
        "Diğer Şirket Gideri"
    ]

    PAYMENT_METHODS = [
        "Nakit",
        "Şirket Kredi Kartı",
        "Banka Transferi / EFT",
        "Ortak Şahsi Kredi Kartı",
        "Diğer"
    ]

    def get_expenses(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        person_name: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 500
    ) -> List[Dict]:
        """Tüm şirket ve ortak harcamalarını filtreleyerek getirir"""
        try:
            sql = """
                SELECT 
                    ce.id,
                    ce.branch_id,
                    ce.expense_date,
                    ce.person_name,
                    ce.amount,
                    ce.category,
                    ce.location_destination,
                    ce.payment_method,
                    ce.document_no,
                    ce.description,
                    ce.created_by,
                    ce.created_at,
                    ce.updated_at,
                    u.full_name as created_by_name,
                    b.name as branch_name
                FROM CompanyExpenses ce
                LEFT JOIN Users u ON ce.created_by = u.id
                LEFT JOIN Branches b ON ce.branch_id = b.id
                WHERE 1=1
            """
            params = []

            if start_date:
                sql += " AND ce.expense_date >= %s"
                params.append(start_date)

            if end_date:
                sql += " AND ce.expense_date <= %s"
                params.append(end_date)

            if person_name and person_name != "Tümü":
                sql += " AND LOWER(TRIM(ce.person_name)) = LOWER(TRIM(%s))"
                params.append(person_name)

            if category and category != "Tümü":
                sql += " AND ce.category = %s"
                params.append(category)

            if search:
                s_param = f"%{search.strip().lower()}%"
                sql += """ AND (
                    LOWER(ce.person_name) LIKE %s OR 
                    LOWER(COALESCE(ce.location_destination, '')) LIKE %s OR 
                    LOWER(COALESCE(ce.description, '')) LIKE %s OR 
                    LOWER(COALESCE(ce.document_no, '')) LIKE %s
                )"""
                params.extend([s_param, s_param, s_param, s_param])

            sql += " ORDER BY ce.expense_date DESC, ce.id DESC LIMIT %s"
            params.append(limit)

            return db.fetch_all(sql, tuple(params))
        except Exception as e:
            logger.error(f"get_expenses hatası: {e}")
            return []

    def get_expense(self, expense_id: int) -> Optional[Dict]:
        """Tekil harcama detayını getirir"""
        try:
            return db.fetch_one("""
                SELECT 
                    ce.*,
                    u.full_name as created_by_name,
                    b.name as branch_name
                FROM CompanyExpenses ce
                LEFT JOIN Users u ON ce.created_by = u.id
                LEFT JOIN Branches b ON ce.branch_id = b.id
                WHERE ce.id = %s
            """, (expense_id,))
        except Exception as e:
            logger.error(f"get_expense hatası: {e}")
            return None

    def add_expense(self, data: Dict, user_id: Optional[int] = None) -> Tuple[bool, str, Optional[int]]:
        """Yeni genel şirket / ortak harcaması ekler"""
        try:
            person_name = (data.get('person_name') or '').strip()
            if not person_name:
                return False, "Kime / Harcayan Kişi adı boş bırakılamaz!", None

            amount = to_decimal(data.get('amount', 0))
            if amount <= Decimal('0'):
                return False, "Harcama tutarı 0'dan büyük olmalıdır!", None

            expense_date = data.get('expense_date') or datetime.now().date().strftime('%Y-%m-%d')
            category = data.get('category') or "Ortak Özel Harcama"
            location = (data.get('location_destination') or '').strip() or None
            payment_method = data.get('payment_method') or "Nakit"
            doc_no = (data.get('document_no') or '').strip() or None
            description = (data.get('description') or '').strip() or None
            branch_id = data.get('branch_id')

            new_id = db.execute_query("""
                INSERT INTO CompanyExpenses (
                    branch_id, expense_date, person_name, amount,
                    category, location_destination, payment_method,
                    document_no, description, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                branch_id, expense_date, person_name, float(amount),
                category, location, payment_method,
                doc_no, description, user_id
            ))
            logger.info(f"💼 Şirket/Ortak Harcaması Eklendi: ID={new_id}, Kişi={person_name}, Tutar={amount} ₺")
            return True, "Harcama kaydı başarıyla eklendi.", new_id
        except Exception as e:
            logger.error(f"add_expense hatası: {e}")
            return False, f"Harcama eklenirken hata: {str(e)}", None

    def update_expense(self, expense_id: int, data: Dict, user_id: Optional[int] = None) -> Tuple[bool, str]:
        """Mevcut şirket / ortak harcamasını günceller"""
        try:
            existing = self.get_expense(expense_id)
            if not existing:
                return False, "Harcama kaydı bulunamadı!"

            person_name = (data.get('person_name') or existing.get('person_name') or '').strip()
            if not person_name:
                return False, "Kişi/Ortak adı boş bırakılamaz!"

            amount = to_decimal(data.get('amount', existing.get('amount', 0)))
            if amount <= Decimal('0'):
                return False, "Harcama tutarı 0'dan büyük olmalıdır!"

            expense_date = data.get('expense_date') or existing.get('expense_date')
            category = data.get('category') or existing.get('category')
            location = data.get('location_destination') if 'location_destination' in data else existing.get('location_destination')
            payment_method = data.get('payment_method') or existing.get('payment_method')
            doc_no = data.get('document_no') if 'document_no' in data else existing.get('document_no')
            description = data.get('description') if 'description' in data else existing.get('description')
            branch_id = data.get('branch_id') if 'branch_id' in data else existing.get('branch_id')

            db.execute_query("""
                UPDATE CompanyExpenses 
                SET branch_id = %s,
                    expense_date = %s,
                    person_name = %s,
                    amount = %s,
                    category = %s,
                    location_destination = %s,
                    payment_method = %s,
                    document_no = %s,
                    description = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                branch_id, expense_date, person_name, float(amount),
                category, location, payment_method,
                doc_no, description, expense_id
            ))

            logger.info(f"💼 Şirket/Ortak Harcaması Güncellendi: ID={expense_id}, Kişi={person_name}, Tutar={amount} ₺")
            return True, "Harcama kaydı başarıyla güncellendi."
        except Exception as e:
            logger.error(f"update_expense hatası: {e}")
            return False, f"Güncelleme hatası: {str(e)}"

    def delete_expense(self, expense_id: int, user_id: Optional[int] = None) -> Tuple[bool, str]:
        """Harcama kaydını siler"""
        try:
            existing = self.get_expense(expense_id)
            if not existing:
                return False, "Harcama kaydı bulunamadı!"

            p_name = existing.get('person_name', 'Kayıt')
            amount = existing.get('amount', 0)

            db.execute_query("DELETE FROM CompanyExpenses WHERE id = %s", (expense_id,))
            logger.info(f"🗑️ Şirket/Ortak Harcaması Silindi: ID={expense_id}, Kişi={p_name}, Tutar={amount}")
            return True, f"'{p_name}' adına ait {amount:,.2f} ₺ tutarındaki harcama kaydı silindi."
        except Exception as e:
            logger.error(f"delete_expense hatası: {e}")
            return False, f"Silme hatası: {str(e)}"

    def get_summary_stats(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
        """Özet KPI ve istatistikleri hesaplar"""
        try:
            sql = """
                SELECT 
                    COUNT(*) as total_count,
                    COALESCE(SUM(amount), 0) as total_amount,
                    COALESCE(SUM(CASE WHEN category IN ('Ortak Özel Harcama', 'Ortak Avans / Kâr Payı Çekimi') THEN amount ELSE 0 END), 0) as partner_drawings,
                    COALESCE(SUM(CASE WHEN category NOT IN ('Ortak Özel Harcama', 'Ortak Avans / Kâr Payı Çekimi') THEN amount ELSE 0 END), 0) as company_expenses
                FROM CompanyExpenses
                WHERE 1=1
            """
            params = []
            if start_date:
                sql += " AND expense_date >= %s"
                params.append(start_date)
            if end_date:
                sql += " AND expense_date <= %s"
                params.append(end_date)

            row = db.fetch_one(sql, tuple(params)) or {}

            # Bu ayki toplam
            now = datetime.now()
            first_day = date(now.year, now.month, 1).strftime('%Y-%m-%d')
            month_row = db.fetch_one("""
                SELECT COALESCE(SUM(amount), 0) as month_total, COUNT(*) as month_count
                FROM CompanyExpenses
                WHERE expense_date >= %s
            """, (first_day,)) or {}

            return {
                'total_count': int(row.get('total_count', 0)),
                'total_amount': float(row.get('total_amount', 0.0)),
                'partner_drawings': float(row.get('partner_drawings', 0.0)),
                'company_expenses': float(row.get('company_expenses', 0.0)),
                'month_total': float(month_row.get('month_total', 0.0)),
                'month_count': int(month_row.get('month_count', 0))
            }
        except Exception as e:
            logger.error(f"get_summary_stats hatası: {e}")
            return {
                'total_count': 0,
                'total_amount': 0.0,
                'partner_drawings': 0.0,
                'company_expenses': 0.0,
                'month_total': 0.0,
                'month_count': 0
            }

    def get_distinct_persons(self) -> List[str]:
        """Kayıtlı kişi / ortak isimlerini listeler"""
        try:
            rows = db.fetch_all("SELECT DISTINCT person_name FROM CompanyExpenses WHERE person_name IS NOT NULL AND TRIM(person_name) != '' ORDER BY person_name")
            return [r['person_name'] for r in rows]
        except Exception as e:
            logger.error(f"get_distinct_persons hatası: {e}")
            return []

    def get_persons_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict]:
        """
        Kişi / Ortak bazında şirketten toplam ne kadar para alındığını,
        kaç adet harcama yapıldığını ve son harcama tarihini özetler.
        """
        try:
            sql = """
                SELECT 
                    ce.person_name,
                    COUNT(*) as expense_count,
                    COALESCE(SUM(ce.amount), 0) as total_amount,
                    COALESCE(SUM(CASE WHEN ce.category IN ('Ortak Özel Harcama', 'Ortak Avans / Kâr Payı Çekimi') THEN ce.amount ELSE 0 END), 0) as personal_amount,
                    COALESCE(SUM(CASE WHEN ce.category NOT IN ('Ortak Özel Harcama', 'Ortak Avans / Kâr Payı Çekimi') THEN ce.amount ELSE 0 END), 0) as company_amount,
                    MAX(ce.expense_date) as last_expense_date,
                    MIN(ce.expense_date) as first_expense_date
                FROM CompanyExpenses ce
                WHERE 1=1
            """
            params = []
            if start_date:
                sql += " AND ce.expense_date >= %s"
                params.append(start_date)
            if end_date:
                sql += " AND ce.expense_date <= %s"
                params.append(end_date)
            if search:
                sql += " AND LOWER(ce.person_name) LIKE %s"
                params.append(f"%{search.strip().lower()}%")

            sql += " GROUP BY ce.person_name ORDER BY total_amount DESC, expense_count DESC"
            return db.fetch_all(sql, tuple(params)) if params else db.fetch_all(sql)
        except Exception as e:
            logger.error(f"get_persons_summary hatası: {e}")
            return []

    def get_expenses_by_person(
        self,
        person_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """Belirli bir kişinin / ortağın tüm harcama ve para çekim detaylarını getirir"""
        return self.get_expenses(start_date=start_date, end_date=end_date, person_name=person_name, limit=1000)


company_expense_service = CompanyExpenseService()
