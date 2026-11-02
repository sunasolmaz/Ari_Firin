# src/services/employee_service.py
"""
Personel (Çalışan) Yönetimi Servisi
- Çalışan CRUD işlemleri (ekle, güncelle, sil, listele)
- Cari hareketler (avans / maaş / mahsup / prim / kesinti)
- Cari ekstre ve bakiye hesaplama
- İstatistikler
"""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Tuple, Optional, Any

from ..core.database import db
from ..core.logger import logger
from ..core.decimal_utils import to_decimal, round_currency


class EmployeeService:
    """Personel / Çalışan servisi"""

    def __init__(self):
        try:
            db.ensure_payment_plan_tables()
        except Exception as e:
            logger.warning(f"EmployeeService tablo denetim uyarısı: {e}")

    # ==================== ÇALIŞAN CRUD ====================

    def get_employees(
        self,
        search: str = "",
        branch_id: Optional[int] = None,
        active_only: bool = True
    ) -> List[Dict]:
        """Çalışanları listeler ve filtreler"""
        try:
            sql = """
                SELECT 
                    e.id,
                    e.branch_id,
                    e.employee_code,
                    e.full_name,
                    e.national_id,
                    e.phone,
                    e.email,
                    e.address,
                    e.position,
                    e.department,
                    e.hire_date,
                    e.birth_date,
                    e.iban,
                    e.monthly_salary,
                    e.salary_day,
                    e.notes,
                    e.is_active,
                    e.created_at,
                    e.updated_at,
                    b.name AS branch_name
                FROM Employees e
                LEFT JOIN Branches b ON b.id = e.branch_id
                WHERE 1=1
            """
            params = []

            if active_only:
                sql += " AND e.is_active = TRUE"

            if branch_id:
                sql += " AND e.branch_id = %s"
                params.append(branch_id)

            if search:
                sql += " AND (LOWER(e.full_name) LIKE LOWER(%s) OR LOWER(e.employee_code) LIKE LOWER(%s) OR e.phone LIKE %s)"
                like = f"%{search.strip()}%"
                params.extend([like, like, like])

            sql += " ORDER BY e.full_name ASC"

            return db.fetch_all(sql, tuple(params)) if params else db.fetch_all(sql)
        except Exception as e:
            logger.error(f"get_employees hatası: {e}")
            return []

    def get_employee(self, employee_id: int) -> Optional[Dict]:
        """Tek çalışan detayı"""
        try:
            return db.fetch_one(
                "SELECT * FROM Employees WHERE id = %s",
                (employee_id,)
            )
        except Exception as e:
            logger.error(f"get_employee hatası: {e}")
            return None

    def generate_employee_code(self) -> str:
        """Otomatik çalışan kodu üret: EMP-XXXX"""
        try:
            row = db.fetch_one("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM Employees")
            next_id = row['next_id'] if row else 1

            for _ in range(20):
                code = f"EMP-{next_id:04d}"
                exists = db.fetch_one(
                    "SELECT id FROM Employees WHERE employee_code = %s LIMIT 1",
                    (code,)
                )
                if not exists:
                    return code
                next_id += 1

            return f"EMP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        except Exception as e:
            logger.error(f"generate_employee_code hatası: {e}")
            return f"EMP-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def add_employee(self, data: Dict, user_id: Optional[int] = None) -> Tuple[bool, str, Optional[int]]:
        """Yeni çalışan ekler"""
        try:
            full_name = (data.get('full_name') or '').strip()
            if not full_name:
                return False, "Ad Soyad boş bırakılamaz!", None

            code = (data.get('employee_code') or '').strip()
            if not code:
                code = self.generate_employee_code()

            # Kod benzersizlik kontrolü
            existing = db.fetch_one(
                "SELECT id FROM Employees WHERE employee_code = %s LIMIT 1",
                (code,)
            )
            if existing:
                return False, f"'{code}' kodlu personel zaten mevcut!", None

            monthly_salary = float(to_decimal(data.get('monthly_salary', 0)))
            salary_day = int(data.get('salary_day', 1) or 1)
            if salary_day < 1 or salary_day > 28:
                salary_day = 1

            new_id = db.execute_query("""
                INSERT INTO Employees (
                    branch_id, employee_code, full_name, national_id, phone, email,
                    address, position, department, hire_date, birth_date, iban,
                    monthly_salary, salary_day, notes, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
            """, (
                data.get('branch_id'),
                code,
                full_name,
                data.get('national_id', '') or None,
                data.get('phone', '') or None,
                data.get('email', '') or None,
                data.get('address', '') or None,
                data.get('position', '') or None,
                data.get('department', '') or None,
                data.get('hire_date') or None,
                data.get('birth_date') or None,
                data.get('iban', '') or None,
                monthly_salary,
                salary_day,
                data.get('notes', '') or None,
            ))

            logger.info(f"✅ Yeni personel eklendi: ID={new_id}, Kod={code}, Ad={full_name}")
            return True, "Personel başarıyla eklendi.", new_id
        except Exception as e:
            logger.error(f"add_employee hatası: {e}")
            return False, f"Personel eklenirken hata: {str(e)}", None

    def update_employee(self, employee_id: int, data: Dict) -> Tuple[bool, str]:
        """Çalışan bilgilerini günceller"""
        try:
            full_name = (data.get('full_name') or '').strip()
            if not full_name:
                return False, "Ad Soyad boş bırakılamaz!"

            monthly_salary = float(to_decimal(data.get('monthly_salary', 0)))
            salary_day = int(data.get('salary_day', 1) or 1)
            if salary_day < 1 or salary_day > 28:
                salary_day = 1

            # Kod değişmişse benzersizlik kontrolü
            new_code = (data.get('employee_code') or '').strip()
            if new_code:
                existing = db.fetch_one(
                    "SELECT id FROM Employees WHERE employee_code = %s AND id != %s LIMIT 1",
                    (new_code, employee_id)
                )
                if existing:
                    return False, f"'{new_code}' kodlu personel zaten mevcut!"

            db.execute_query("""
                UPDATE Employees SET
                    branch_id = %s,
                    employee_code = COALESCE(NULLIF(%s, ''), employee_code),
                    full_name = %s,
                    national_id = %s,
                    phone = %s,
                    email = %s,
                    address = %s,
                    position = %s,
                    department = %s,
                    hire_date = %s,
                    birth_date = %s,
                    iban = %s,
                    monthly_salary = %s,
                    salary_day = %s,
                    notes = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                data.get('branch_id'),
                new_code,
                full_name,
                data.get('national_id', '') or None,
                data.get('phone', '') or None,
                data.get('email', '') or None,
                data.get('address', '') or None,
                data.get('position', '') or None,
                data.get('department', '') or None,
                data.get('hire_date') or None,
                data.get('birth_date') or None,
                data.get('iban', '') or None,
                monthly_salary,
                salary_day,
                data.get('notes', '') or None,
                employee_id
            ))
            return True, "Personel güncellendi."
        except Exception as e:
            logger.error(f"update_employee hatası: {e}")
            return False, f"Güncelleme hatası: {str(e)}"

    def delete_employee(self, employee_id: int) -> Tuple[bool, str]:
        """Çalışanı pasife alır (soft delete)"""
        try:
            # Açık avansı olan personel silinemesin
            open_advance = db.fetch_one("""
                SELECT COALESCE(SUM(remaining_amount), 0) AS total
                FROM EmployeeLedger
                WHERE employee_id = %s AND entry_type = 'avans' AND is_closed = 0
            """, (employee_id,))

            if open_advance and float(open_advance['total'] or 0) > 0.001:
                return False, f"Personelin açık avansı var ({float(open_advance['total']):,.2f} ₺). Önce mahsup edilmeli."

            db.execute_query(
                "UPDATE Employees SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (employee_id,)
            )
            return True, "Personel silindi."
        except Exception as e:
            logger.error(f"delete_employee hatası: {e}")
            return False, f"Silme hatası: {str(e)}"

    def toggle_active(self, employee_id: int, is_active: bool) -> Tuple[bool, str]:
        """Personel aktiflik durumunu değiştirir"""
        try:
            db.execute_query(
                "UPDATE Employees SET is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (is_active, employee_id)
            )
            return True, "Personel durumu güncellendi."
        except Exception as e:
            logger.error(f"toggle_active hatası: {e}")
            return False, f"Durum güncellenemedi: {str(e)}"

    # ==================== CARİ HAREKETLER (LEDGER) ====================

    def add_ledger_entry(
        self,
        employee_id: int,
        entry_type: str,
        amount: float,
        entry_date: Optional[str] = None,
        description: str = "",
        account_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Personel cari hareketi ekler.
        entry_type: 'avans', 'maas_tahakkuk', 'maas_odeme', 'mahsup', 'prim', 'kesinti', 'iade'
        amount: pozitif değer; servis içinde işaretlenir (avans = bize borç, maaş = biz borçluyuz).
        """
        try:
            amt = round_currency(amount)
            if amt <= Decimal('0.00'):
                return False, "Tutar 0'dan büyük olmalıdır!", None

            if not entry_date:
                entry_date = datetime.now().date().strftime('%Y-%m-%d')

            # Avans ve prim pozitif bakiyeyi artırır (bize borç)
            # Maaş tahakkuk/ödeme bakiye borcumuzu artırır (alacak)
            # Bu ayrım ekstre hesabında yapılır, ledger'da sadece tutar saklanır.
            remaining = float(amt) if entry_type == 'avans' else 0.0
            is_closed = 0 if entry_type == 'avans' else 1

            new_id = db.execute_query("""
                INSERT INTO EmployeeLedger (
                    employee_id, entry_type, amount, entry_date, description,
                    account_id, remaining_amount, is_closed, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                employee_id, entry_type, float(amt), entry_date,
                (description or '').strip() or None,
                account_id, remaining, is_closed, user_id
            ))

            logger.info(f"✅ Personel cari hareketi eklendi: EmpID={employee_id}, Tip={entry_type}, Tutar={amt}")
            return True, "Cari hareket eklendi.", new_id
        except Exception as e:
            logger.error(f"add_ledger_entry hatası: {e}")
            return False, f"Cari hareket eklenemedi: {str(e)}", None

    def get_ledger_entries(
        self,
        employee_id: int,
        entry_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 500
    ) -> List[Dict]:
        """Personel cari hareketlerini listeler"""
        try:
            sql = """
                SELECT 
                    el.id,
                    el.employee_id,
                    el.entry_type,
                    el.amount,
                    el.entry_date,
                    el.description,
                    el.payment_plan_id,
                    el.account_id,
                    el.remaining_amount,
                    el.is_closed,
                    el.created_at,
                    u.full_name AS created_by_name
                FROM EmployeeLedger el
                LEFT JOIN public.Users u ON u.id = el.created_by
                WHERE el.employee_id = %s
            """
            params = [employee_id]

            if entry_type:
                sql += " AND el.entry_type = %s"
                params.append(entry_type)

            if start_date:
                sql += " AND el.entry_date >= %s"
                params.append(start_date)

            if end_date:
                sql += " AND el.entry_date <= %s"
                params.append(end_date)

            sql += " ORDER BY el.entry_date DESC, el.id DESC LIMIT %s"
            params.append(limit)

            return db.fetch_all(sql, tuple(params))
        except Exception as e:
            logger.error(f"get_ledger_entries hatası: {e}")
            return []

    def get_employee_balance(self, employee_id: int) -> Dict:
        """
        Personel bakiyesi:
        - total_advance: Açık avanslar toplamı (personel bize borçlu)
        - total_salary_paid: Toplam ödenen maaşlar
        - net_balance: + ise personel bize borçlu, - ise biz personele borçluyuz
        """
        try:
            row = db.fetch_one("""
                SELECT 
                    COALESCE(SUM(CASE WHEN entry_type = 'avans' AND is_closed = 0 THEN remaining_amount ELSE 0 END), 0) AS open_advance,
                    COALESCE(SUM(CASE WHEN entry_type = 'avans' THEN amount ELSE 0 END), 0) AS total_advance,
                    COALESCE(SUM(CASE WHEN entry_type = 'maas_odeme' THEN amount ELSE 0 END), 0) AS total_salary_paid,
                    COALESCE(SUM(CASE WHEN entry_type = 'maas_tahakkuk' THEN amount ELSE 0 END), 0) AS total_salary_accrued,
                    COALESCE(SUM(CASE WHEN entry_type = 'prim' THEN amount ELSE 0 END), 0) AS total_bonus,
                    COALESCE(SUM(CASE WHEN entry_type = 'kesinti' THEN amount ELSE 0 END), 0) AS total_deduction
                FROM EmployeeLedger
                WHERE employee_id = %s
            """, (employee_id,))

            if not row:
                return {
                    'open_advance': 0.0,
                    'total_advance': 0.0,
                    'total_salary_paid': 0.0,
                    'total_salary_accrued': 0.0,
                    'total_bonus': 0.0,
                    'total_deduction': 0.0,
                    'net_balance': 0.0
                }

            open_adv = float(row['open_advance'] or 0)
            net = open_adv  # + ise personel bize borçlu

            return {
                'open_advance': open_adv,
                'total_advance': float(row['total_advance'] or 0),
                'total_salary_paid': float(row['total_salary_paid'] or 0),
                'total_salary_accrued': float(row['total_salary_accrued'] or 0),
                'total_bonus': float(row['total_bonus'] or 0),
                'total_deduction': float(row['total_deduction'] or 0),
                'net_balance': net
            }
        except Exception as e:
            logger.error(f"get_employee_balance hatası: {e}")
            return {
                'open_advance': 0.0,
                'total_advance': 0.0,
                'total_salary_paid': 0.0,
                'total_salary_accrued': 0.0,
                'total_bonus': 0.0,
                'total_deduction': 0.0,
                'net_balance': 0.0
            }

    def get_employee_ledger_statement(self, employee_id: int) -> List[Dict]:
        """
        Kronolojik cari ekstre (her satırda bakiye sütunu ile).
        + bakiye: personel bize borçlu
        - bakiye: biz personele borçluyuz
        """
        try:
            rows = db.fetch_all("""
                SELECT 
                    id, entry_type, amount, entry_date, description,
                    remaining_amount, is_closed, created_at
                FROM EmployeeLedger
                WHERE employee_id = %s
                ORDER BY entry_date ASC, id ASC
            """, (employee_id,))

            statement = []
            running_balance = Decimal('0.00')

            for r in rows:
                amt = to_decimal(r['amount'])
                etype = r['entry_type']

                # Bakiye etkisi:
                # + avans, prim → bize borç artar
                # - maas_odeme, iade → bize olan borcu azaltır (biz ödedik)
                # - mahsup → avans bakiyesini azaltır (biz kapatıyoruz)
                # - kesinti → bakiye değişmez, sadece brütten düşer (bilgi amaçlı)
                if etype in ('avans', 'prim'):
                    running_balance += amt
                elif etype in ('maas_odeme', 'mahsup', 'iade'):
                    running_balance -= amt

                statement.append({
                    'id': r['id'],
                    'entry_date': r['entry_date'],
                    'entry_type': etype,
                    'description': r['description'],
                    'amount': float(amt),
                    'balance': float(running_balance),
                    'remaining_amount': float(r['remaining_amount'] or 0),
                    'is_closed': r['is_closed'],
                    'created_at': r['created_at']
                })

            return statement
        except Exception as e:
            logger.error(f"get_employee_ledger_statement hatası: {e}")
            return []

    # ==================== İSTATİSTİKLER ====================

    def get_employee_stats(self, branch_id: Optional[int] = None) -> Dict:
        """Personel genel istatistikleri"""
        try:
            sql = """
                SELECT 
                    COUNT(*) AS total_employees,
                    COUNT(CASE WHEN is_active = TRUE THEN 1 END) AS active_employees,
                    COUNT(CASE WHEN is_active = FALSE THEN 1 END) AS inactive_employees,
                    COALESCE(SUM(CASE WHEN is_active = TRUE THEN monthly_salary ELSE 0 END), 0) AS total_monthly_salary,
                    COALESCE(AVG(CASE WHEN is_active = TRUE THEN monthly_salary END), 0) AS avg_monthly_salary
                FROM Employees
            """
            params = []
            if branch_id:
                sql = sql.replace("FROM Employees", "FROM Employees WHERE branch_id = %s")
                params.append(branch_id)

            row = db.fetch_one(sql, tuple(params)) if params else db.fetch_one(sql)

            open_adv = 0.0
            try:
                adv_sql = """
                    SELECT COALESCE(SUM(el.remaining_amount), 0) AS total
                    FROM EmployeeLedger el
                    JOIN Employees e ON e.id = el.employee_id
                    WHERE el.entry_type = 'avans' AND el.is_closed = 0
                """
                adv_params = []
                if branch_id:
                    adv_sql += " AND e.branch_id = %s"
                    adv_params.append(branch_id)
                adv_row = db.fetch_one(adv_sql, tuple(adv_params)) if adv_params else db.fetch_one(adv_sql)
                open_adv = float(adv_row['total'] or 0) if adv_row else 0.0
            except Exception:
                pass

            return {
                'total_employees': int(row['total_employees'] or 0) if row else 0,
                'active_employees': int(row['active_employees'] or 0) if row else 0,
                'inactive_employees': int(row['inactive_employees'] or 0) if row else 0,
                'total_monthly_salary': float(row['total_monthly_salary'] or 0) if row else 0.0,
                'avg_monthly_salary': float(row['avg_monthly_salary'] or 0) if row else 0.0,
                'total_open_advance': open_adv
            }
        except Exception as e:
            logger.error(f"get_employee_stats hatası: {e}")
            return {
                'total_employees': 0,
                'active_employees': 0,
                'inactive_employees': 0,
                'total_monthly_salary': 0.0,
                'avg_monthly_salary': 0.0,
                'total_open_advance': 0.0
            }


# Singleton instance
employee_service = EmployeeService()