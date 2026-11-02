# src/services/payment_plan_service.py
"""
Ödeme Planı ve Vadeli Ödeme Takibi Servisi
- Personel maaşı, şube kirası, araç taksiti, diğer ödemeler
- Otomatik avans mahsubu (tam kesinti veya taksitli)
- Yaklaşan / gecikmiş ödeme bildirimleri (bildirim paneli için)
- Ödeme yapıldığında kasa/banka hareketi oluşturma
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Tuple, Optional, Any

from ..core.database import db
from ..core.logger import logger
from ..core.decimal_utils import to_decimal, round_currency
from .employee_service import employee_service


# ==================== SABİTLER ====================

PLAN_TYPES = {
    'personel':   'Personel Maaşı',
    'avans':      'Personel Avansı',
    'kira':       'Şube Kirası',
    'taksit':     'Taksit / Kredi',
    'diger':      'Diğer Ödeme',
}

PAYMENT_METHODS = ['Nakit', 'Havale / EFT', 'Kredi Kartı / POS', 'Çek', 'Senet']

STATUS = {
    'bekliyor':  'Bekliyor',
    'odendi':    'Ödendi',
    'gecikti':   'Gecikti',
    'iptal':     'İptal',
}


class PaymentPlanService:
    """Ödeme Planı Servisi"""

    def __init__(self):
        try:
            db.ensure_payment_plan_tables()
        except Exception as e:
            logger.warning(f"PaymentPlanService tablo denetim uyarısı: {e}")

    # ==================== OTOMATİK DURUM GÜNCELLEMESİ ====================

    def refresh_overdue_status(self) -> int:
        """
        Vadesi geçmiş 'bekliyor' durumundaki planları 'gecikti' yapar.
        Uygulama başlangıcında bir kez çağrılmalıdır.
        Döndürülen sayı: güncellenen kayıt sayısı.
        """
        try:
            today = datetime.now().date().strftime('%Y-%m-%d')
            with db.transaction():
                rowcount = db.execute_query("""
                    UPDATE PaymentPlans 
                    SET status = 'gecikti', updated_at = CURRENT_TIMESTAMP
                    WHERE status = 'bekliyor' 
                      AND due_date < %s
                """, (today,))
            if rowcount and rowcount > 0:
                logger.info(f"⏰ {rowcount} adet ödeme planı 'gecikti' olarak işaretlendi")
            return int(rowcount or 0)
        except Exception as e:
            logger.error(f"refresh_overdue_status hatası: {e}")
            return 0

    # ==================== PLAN CRUD ====================

    def get_plans(
        self,
        plan_type: Optional[str] = None,
        status: Optional[str] = None,
        branch_id: Optional[int] = None,
        payee_type: Optional[str] = None,
        payee_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: str = "",
        limit: int = 1000
    ) -> List[Dict]:
        """Ödeme planlarını filtreli listeler"""
        try:
            sql = """
                SELECT 
                    pp.id,
                    pp.branch_id,
                    pp.plan_type,
                    pp.title,
                    pp.payee_type,
                    pp.payee_id,
                    pp.payee_name,
                    pp.total_amount,
                    pp.installment_count,
                    pp.installment_no,
                    pp.gross_amount,
                    pp.advance_deduction,
                    pp.amount,
                    pp.due_date,
                    pp.payment_method,
                    pp.account_id,
                    pp.status,
                    pp.paid_date,
                    pp.paid_amount,
                    pp.reminder_days,
                    pp.notes,
                    pp.reference_type,
                    pp.reference_id,
                    pp.created_at,
                    pp.updated_at,
                    b.name AS branch_name,
                    ba.account_name AS account_display_name
                FROM PaymentPlans pp
                LEFT JOIN Branches b ON b.id = pp.branch_id
                LEFT JOIN BankAccounts ba ON ba.id = pp.account_id
                WHERE 1=1
            """
            params = []

            if plan_type and plan_type != 'Tümü':
                sql += " AND pp.plan_type = %s"
                params.append(plan_type)

            if status and status != 'Tümü':
                sql += " AND pp.status = %s"
                params.append(status)

            if branch_id:
                sql += " AND pp.branch_id = %s"
                params.append(branch_id)

            if payee_type:
                sql += " AND pp.payee_type = %s"
                params.append(payee_type)

            if payee_id:
                sql += " AND pp.payee_id = %s"
                params.append(payee_id)

            if start_date:
                sql += " AND pp.due_date >= %s"
                params.append(start_date)

            if end_date:
                sql += " AND pp.due_date <= %s"
                params.append(end_date)

            if search:
                sql += " AND (LOWER(pp.title) LIKE LOWER(%s) OR LOWER(pp.payee_name) LIKE LOWER(%s))"
                like = f"%{search.strip()}%"
                params.extend([like, like])

            sql += " ORDER BY pp.due_date ASC, pp.id DESC LIMIT %s"
            params.append(limit)

            return db.fetch_all(sql, tuple(params)) if params else db.fetch_all(sql)
        except Exception as e:
            logger.error(f"get_plans hatası: {e}")
            return []

    def get_plan(self, plan_id: int) -> Optional[Dict]:
        """Tek plan detayı"""
        try:
            return db.fetch_one("""
                SELECT pp.*, b.name AS branch_name
                FROM PaymentPlans pp
                LEFT JOIN Branches b ON b.id = pp.branch_id
                WHERE pp.id = %s
            """, (plan_id,))
        except Exception as e:
            logger.error(f"get_plan hatası: {e}")
            return None

    def create_plan(self, data: Dict, user_id: Optional[int] = None) -> Tuple[bool, str, Optional[int]]:
        """
        Yeni ödeme planı oluşturur.
        Eğer taksitli ise (installment_count > 1) otomatik olarak her taksit için
        ayrı bir plan satırı oluşturur.
        """
        try:
            title = (data.get('title') or '').strip()
            if not title:
                return False, "Başlık boş bırakılamaz!", None

            amount = to_decimal(data.get('amount', 0))
            if amount <= Decimal('0.00'):
                return False, "Tutar 0'dan büyük olmalıdır!", None

            due_date = data.get('due_date')
            if not due_date:
                return False, "Vade tarihi zorunludur!", None

            plan_type = data.get('plan_type', 'diger')
            installment_count = int(data.get('installment_count', 1) or 1)
            if installment_count < 1:
                installment_count = 1

            # Toplam tutar belirleme ve kuruş küsürat dengelemesi
            total_amount_val = to_decimal(data.get('total_amount', 0))
            if total_amount_val <= Decimal('0.00'):
                total_amount_val = amount * Decimal(installment_count) if installment_count > 1 else amount

            if installment_count > 1:
                base_installment = round_currency(total_amount_val / Decimal(installment_count))
                sum_previous = base_installment * Decimal(installment_count - 1)
                last_installment = total_amount_val - sum_previous
            else:
                base_installment = total_amount_val
                last_installment = total_amount_val

            plan_base = {
                'branch_id': data.get('branch_id'),
                'plan_type': plan_type,
                'title': title,
                'payee_type': data.get('payee_type', 'diger'),
                'payee_id': data.get('payee_id'),
                'payee_name': data.get('payee_name', ''),
                'total_amount': float(total_amount_val),
                'installment_count': installment_count,
                'payment_method': data.get('payment_method', 'Havale / EFT'),
                'account_id': data.get('account_id'),
                'notes': data.get('notes', ''),
                'reminder_days': int(data.get('reminder_days', 3) or 3),
                'reference_type': data.get('reference_type'),
                'reference_id': data.get('reference_id'),
            }

            first_id = None
            due_dt = datetime.strptime(due_date, '%Y-%m-%d').date()

            with db.transaction():
                for i in range(installment_count):
                    # Kuruş dengeli taksit tutarı (son taksite küsürat farkı eklenir)
                    current_inst_amount = float(last_installment if i == installment_count - 1 else base_installment)

                    # Vade tarihi her taksit için 1 ay ileri
                    if installment_count > 1:
                        try:
                            y = due_dt.year
                            m = due_dt.month + i
                            while m > 12:
                                m -= 12
                                y += 1
                            inst_date = due_dt.replace(year=y, month=m).strftime('%Y-%m-%d')
                        except Exception:
                            inst_date = due_dt.strftime('%Y-%m-%d')
                    else:
                        inst_date = due_dt.strftime('%Y-%m-%d')

                    inst_title = title if installment_count == 1 else f"{title} ({i+1}/{installment_count})"

                    new_id = db.execute_query("""
                        INSERT INTO PaymentPlans (
                            branch_id, plan_type, title, payee_type, payee_id, payee_name,
                            total_amount, installment_count, installment_no,
                            gross_amount, advance_deduction, amount, due_date,
                            payment_method, account_id, status, reminder_days,
                            notes, reference_type, reference_id, created_by
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s,
                            0, 0, %s, %s,
                            %s, %s, 'bekliyor', %s,
                            %s, %s, %s, %s
                        )
                        RETURNING id
                    """, (
                        plan_base['branch_id'], plan_base['plan_type'], inst_title,
                        plan_base['payee_type'], plan_base['payee_id'], plan_base['payee_name'],
                        plan_base['total_amount'], installment_count, i + 1,
                        current_inst_amount, inst_date,
                        plan_base['payment_method'], plan_base['account_id'],
                        plan_base['reminder_days'],
                        plan_base['notes'], plan_base['reference_type'], plan_base['reference_id'],
                        user_id
                    ))

                    if first_id is None:
                        first_id = new_id

            msg = f"Ödeme planı oluşturuldu." if installment_count == 1 else f"{installment_count} taksitli ödeme planı oluşturuldu."
            logger.info(f"✅ {msg} (İlk ID={first_id}, Tip={plan_type})")
            return True, msg, first_id
        except Exception as e:
            logger.error(f"create_plan hatası: {e}")
            return False, f"Plan oluşturulamadı: {str(e)}", None

    def update_plan(self, plan_id: int, data: Dict) -> Tuple[bool, str]:
        """Var olan planı günceller (yalnızca 'bekliyor' veya 'gecikti' durumunda tam güncelleme, ödenmişse bilgi güncelleme)"""
        try:
            plan = self.get_plan(plan_id)
            if not plan:
                return False, "Plan bulunamadı!"

            if plan['status'] == 'odendi':
                # Ödenmiş kayıtta sadece başlık, muhatap ve notlar güncellenebilir
                db.execute_query("""
                    UPDATE PaymentPlans SET
                        title = %s,
                        payee_name = %s,
                        notes = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    data.get('title', plan['title']),
                    data.get('payee_name', plan['payee_name']),
                    data.get('notes', plan['notes']),
                    plan_id
                ))
                return True, "Ödenmiş planın başlık ve not bilgileri güncellendi."

            amount = to_decimal(data.get('amount', plan['amount']))
            if amount <= Decimal('0.00'):
                return False, "Tutar 0'dan büyük olmalıdır!"

            total_amt = data.get('total_amount')
            total_amt_val = float(to_decimal(total_amt)) if total_amt is not None else float(plan.get('total_amount') or amount)

            db.execute_query("""
                UPDATE PaymentPlans SET
                    branch_id = %s,
                    plan_type = %s,
                    title = %s,
                    payee_type = %s,
                    payee_id = %s,
                    payee_name = %s,
                    amount = %s,
                    total_amount = %s,
                    due_date = %s,
                    payment_method = %s,
                    account_id = %s,
                    reminder_days = %s,
                    notes = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                data.get('branch_id', plan['branch_id']),
                data.get('plan_type', plan['plan_type']),
                data.get('title', plan['title']),
                data.get('payee_type', plan['payee_type']),
                data.get('payee_id', plan['payee_id']),
                data.get('payee_name', plan['payee_name']),
                float(amount),
                total_amt_val,
                data.get('due_date', plan['due_date']),
                data.get('payment_method', plan['payment_method']),
                data.get('account_id', plan['account_id']),
                int(data.get('reminder_days', plan['reminder_days']) or 3),
                data.get('notes', plan['notes']),
                plan_id
            ))
            return True, "Plan güncellendi."
        except Exception as e:
            logger.error(f"update_plan hatası: {e}")
            return False, f"Güncelleme hatası: {str(e)}"

    def update_plan_series(self, plan_ids: List[int], data: Dict) -> Tuple[bool, str]:
        """Taksit serisinin ortak alanlarını (başlık, muhatap, şube, ödeme yöntemi, notlar) toplu günceller."""
        try:
            with db.transaction():
                for pid in plan_ids:
                    plan = self.get_plan(pid)
                    if not plan:
                        continue
                    base_title = data.get('title', plan['title'])
                    inst_no = plan.get('installment_no') or 1
                    inst_cnt = plan.get('installment_count') or 1
                    full_title = f"{base_title} ({inst_no}/{inst_cnt})" if inst_cnt > 1 else base_title

                    if plan['status'] != 'odendi':
                        db.execute_query("""
                            UPDATE PaymentPlans SET
                                branch_id = %s,
                                plan_type = %s,
                                title = %s,
                                payee_name = %s,
                                payment_method = %s,
                                account_id = %s,
                                reminder_days = %s,
                                notes = %s,
                                total_amount = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (
                            data.get('branch_id', plan['branch_id']),
                            data.get('plan_type', plan['plan_type']),
                            full_title,
                            data.get('payee_name', plan['payee_name']),
                            data.get('payment_method', plan['payment_method']),
                            data.get('account_id', plan['account_id']),
                            int(data.get('reminder_days', plan['reminder_days']) or 3),
                            data.get('notes', plan['notes']),
                            float(data.get('total_amount', plan['total_amount'] or 0)),
                            pid
                        ))
                    else:
                        db.execute_query("""
                            UPDATE PaymentPlans SET
                                title = %s,
                                payee_name = %s,
                                notes = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (
                            full_title,
                            data.get('payee_name', plan['payee_name']),
                            data.get('notes', plan['notes']),
                            pid
                        ))
            return True, "Ödeme planı serisi güncellendi."
        except Exception as e:
            logger.error(f"update_plan_series hatası: {e}")
            return False, f"Güncelleme hatası: {str(e)}"

    def delete_plan(self, plan_id: int) -> Tuple[bool, str]:
        """Planı siler (yalnızca 'bekliyor' veya 'iptal' durumunda)"""
        try:
            plan = self.get_plan(plan_id)
            if not plan:
                return False, "Plan bulunamadı!"

            if plan['status'] == 'odendi':
                return False, "Ödenmiş plan silinemez!"

            # Personele bağlıysa ve avans mahsubu varsa engelle
            if plan.get('reference_type') == 'salary':
                offset_count = db.fetch_one(
                    "SELECT COUNT(*) AS c FROM AdvanceOffsets WHERE salary_plan_id = %s",
                    (plan_id,)
                )
                if offset_count and offset_count['c'] > 0:
                    return False, "Bu maaşa bağlı avans mahsupları var, plan silinemez."

            db.execute_query("DELETE FROM PaymentPlans WHERE id = %s", (plan_id,))
            return True, "Plan silindi."
        except Exception as e:
            logger.error(f"delete_plan hatası: {e}")
            return False, f"Silme hatası: {str(e)}"

    def delete_plans(self, plan_ids: List[int]) -> Tuple[bool, str, int]:
        """Birden çok plan kaydını siler (ödenmiş olanlar korunur, silinmez)."""
        deleted_count = 0
        try:
            with db.transaction():
                for pid in plan_ids:
                    plan = self.get_plan(pid)
                    if not plan or plan['status'] == 'odendi':
                        continue
                    if plan.get('reference_type') == 'salary':
                        offset = db.fetch_one(
                            "SELECT COUNT(*) AS c FROM AdvanceOffsets WHERE salary_plan_id = %s",
                            (pid,)
                        )
                        if offset and offset['c'] > 0:
                            continue
                    db.execute_query("DELETE FROM PaymentPlans WHERE id = %s", (pid,))
                    deleted_count += 1
            if deleted_count > 0:
                return True, f"{deleted_count} adet plan kaydı silindi.", deleted_count
            return False, "Silinebilecek uygun kayıt bulunamadı (ödenmiş planlar silinemez).", 0
        except Exception as e:
            logger.error(f"delete_plans hatası: {e}")
            return False, f"Silme hatası: {str(e)}", deleted_count

    # ==================== ÖDEME YAPMA ====================

    def mark_as_paid(
        self,
        plan_id: int,
        paid_date: Optional[str] = None,
        account_id: Optional[int] = None,
        description: str = "",
        user_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Planı 'ödendi' olarak işaretler.
        Eğer hesap (kasa/banka) seçildiyse otomatik BankTransactions kaydı oluşturur
        ve hesap bakiyesini düşürür.
        """
        try:
            plan = self.get_plan(plan_id)
            if not plan:
                return False, "Plan bulunamadı!"

            if plan['status'] == 'odendi':
                return False, "Bu plan zaten ödenmiş!"

            if not paid_date:
                paid_date = datetime.now().date().strftime('%Y-%m-%d')

            paid_amount = float(to_decimal(plan['amount']))

            with db.transaction():
                # 1. Planı ödendi işaretle
                db.execute_query("""
                    UPDATE PaymentPlans 
                    SET status = 'odendi', 
                        paid_date = %s, 
                        paid_amount = %s,
                        account_id = COALESCE(%s, account_id),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (paid_date, paid_amount, account_id, plan_id))

                # 2. Kasa/banka hesabı seçildiyse hareket oluştur
                final_account_id = account_id or plan.get('account_id')
                if final_account_id:
                    ref_no = f"PLN-{plan_id}"

                    db.execute_query("""
                        INSERT INTO BankTransactions (
                            branch_id, bank_account_id, transaction_date,
                            transaction_type, amount, description, reference_no, created_by
                        ) VALUES (%s, %s, %s, 'Withdrawal', %s, %s, %s, %s)
                    """, (
                        plan.get('branch_id'),
                        final_account_id,
                        paid_date,
                        paid_amount,
                        description or f"Ödeme: {plan['title']}",
                        ref_no,
                        user_id
                    ))

                    # 3. Hesap bakiyesini düşür
                    db.execute_query("""
                        UPDATE BankAccounts 
                        SET balance = balance - %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (paid_amount, final_account_id))

                # 4. Personel maaşı ise ve reference_type = 'salary' ise ledger'a kayıt
                if plan.get('reference_type') == 'salary' and plan.get('payee_id'):
                    db.execute_query("""
                        INSERT INTO EmployeeLedger (
                            employee_id, entry_type, amount, entry_date, description,
                            payment_plan_id, account_id, remaining_amount, is_closed, created_by
                        ) VALUES (%s, 'maas_odeme', %s, %s, %s, %s, %s, 0, 1, %s)
                    """, (
                        plan['payee_id'],
                        paid_amount,
                        paid_date,
                        f"Maaş ödemesi: {plan['title']}",
                        plan_id,
                        final_account_id,
                        user_id
                    ))

            logger.info(f"✅ Ödeme yapıldı: Plan ID={plan_id}, Tutar={paid_amount}, Hesap={final_account_id}")
            return True, f"Ödeme başarıyla kaydedildi ({paid_amount:,.2f} ₺)."
        except Exception as e:
            logger.error(f"mark_as_paid hatası: {e}")
            return False, f"Ödeme kaydedilemedi: {str(e)}"

    # ==================== BİLDİRİM SORGULARI ====================

    def get_upcoming_payments(self, days: int = 7, branch_id: Optional[int] = None) -> List[Dict]:
        """
        Yaklaşan ödemeler: Bugünden itibaren `days` gün içinde vadesi olan,
        durumu 'bekliyor' olan planları getirir.
        """
        try:
            today = datetime.now().date().strftime('%Y-%m-%d')
            future = (datetime.now().date() + timedelta(days=days)).strftime('%Y-%m-%d')

            sql = """
                SELECT 
                    pp.*,
                    b.name AS branch_name,
                    (pp.due_date - CURRENT_DATE) AS days_left
                FROM PaymentPlans pp
                LEFT JOIN Branches b ON b.id = pp.branch_id
                WHERE pp.status = 'bekliyor'
                  AND pp.due_date BETWEEN %s AND %s
            """
            params = [today, future]

            if branch_id:
                sql += " AND pp.branch_id = %s"
                params.append(branch_id)

            sql += " ORDER BY pp.due_date ASC"

            return db.fetch_all(sql, tuple(params))
        except Exception as e:
            logger.error(f"get_upcoming_payments hatası: {e}")
            return []

    def get_overdue_payments(self, branch_id: Optional[int] = None) -> List[Dict]:
        """Vadesi geçmiş (gecikti durumunda) ödemeleri getirir"""
        try:
            sql = """
                SELECT 
                    pp.*,
                    b.name AS branch_name,
                    (CURRENT_DATE - pp.due_date) AS days_overdue
                FROM PaymentPlans pp
                LEFT JOIN Branches b ON b.id = pp.branch_id
                WHERE pp.status = 'gecikti'
            """
            params = []

            if branch_id:
                sql += " AND pp.branch_id = %s"
                params.append(branch_id)

            sql += " ORDER BY pp.due_date ASC"

            return db.fetch_all(sql, tuple(params)) if params else db.fetch_all(sql)
        except Exception as e:
            logger.error(f"get_overdue_payments hatası: {e}")
            return []

    def get_today_payments(self, branch_id: Optional[int] = None) -> List[Dict]:
        """Bugün vadesi olan ödemeler"""
        try:
            today = datetime.now().date().strftime('%Y-%m-%d')

            sql = """
                SELECT 
                    pp.*,
                    b.name AS branch_name
                FROM PaymentPlans pp
                LEFT JOIN Branches b ON b.id = pp.branch_id
                WHERE pp.status = 'bekliyor'
                  AND pp.due_date = %s
            """
            params = [today]

            if branch_id:
                sql += " AND pp.branch_id = %s"
                params.append(branch_id)

            sql += " ORDER BY pp.title ASC"

            return db.fetch_all(sql, tuple(params))
        except Exception as e:
            logger.error(f"get_today_payments hatası: {e}")
            return []

    # ==================== İSTATİSTİKLER ====================

    def get_plan_stats(self, branch_id: Optional[int] = None) -> Dict:
        """Ödeme planı genel istatistikleri"""
        try:
            today = datetime.now().date().strftime('%Y-%m-%d')
            month_start = datetime.now().replace(day=1).date().strftime('%Y-%m-%d')

            params = []
            filter_sql = ""
            if branch_id:
                filter_sql = " AND branch_id = %s"
                params.append(branch_id)

            # Toplam bekleyen
            waiting = db.fetch_one(f"""
                SELECT 
                    COUNT(*) AS cnt,
                    COALESCE(SUM(amount), 0) AS total
                FROM PaymentPlans
                WHERE status = 'bekliyor' {filter_sql}
            """, tuple(params) if params else None)

            # Yaklaşan (7 gün)
            upcoming = db.fetch_one(f"""
                SELECT 
                    COUNT(*) AS cnt,
                    COALESCE(SUM(amount), 0) AS total
                FROM PaymentPlans
                WHERE status = 'bekliyor' 
                  AND due_date >= %s
                  AND due_date <= (CURRENT_DATE + INTERVAL '7 days')
                  {filter_sql}
            """, tuple([today] + params))

            # Gecikmiş
            overdue = db.fetch_one(f"""
                SELECT 
                    COUNT(*) AS cnt,
                    COALESCE(SUM(amount), 0) AS total
                FROM PaymentPlans
                WHERE status = 'gecikti' {filter_sql}
            """, tuple(params) if params else None)

            # Bu ay ödenen
            paid_this_month = db.fetch_one(f"""
                SELECT 
                    COUNT(*) AS cnt,
                    COALESCE(SUM(paid_amount), 0) AS total
                FROM PaymentPlans
                WHERE status = 'odendi' 
                  AND paid_date >= %s
                  {filter_sql}
            """, tuple([month_start] + params))

            # Bu ay ödenecek (vadesi bu ay olan bekleyen)
            month_end = (datetime.now().replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            month_end_str = month_end.strftime('%Y-%m-%d')
            upcoming_this_month = db.fetch_one(f"""
                SELECT 
                    COUNT(*) AS cnt,
                    COALESCE(SUM(amount), 0) AS total
                FROM PaymentPlans
                WHERE status IN ('bekliyor', 'gecikti') 
                  AND due_date >= %s
                  AND due_date <= %s
                  {filter_sql}
            """, tuple([month_start, month_end_str] + params))

            return {
                'waiting_count': int(waiting['cnt'] or 0) if waiting else 0,
                'waiting_total': float(waiting['total'] or 0) if waiting else 0.0,
                'upcoming_count': int(upcoming['cnt'] or 0) if upcoming else 0,
                'upcoming_total': float(upcoming['total'] or 0) if upcoming else 0.0,
                'overdue_count': int(overdue['cnt'] or 0) if overdue else 0,
                'overdue_total': float(overdue['total'] or 0) if overdue else 0.0,
                'paid_this_month_count': int(paid_this_month['cnt'] or 0) if paid_this_month else 0,
                'paid_this_month_total': float(paid_this_month['total'] or 0) if paid_this_month else 0.0,
                'month_pending_count': int(upcoming_this_month['cnt'] or 0) if upcoming_this_month else 0,
                'month_pending_total': float(upcoming_this_month['total'] or 0) if upcoming_this_month else 0.0,
            }
        except Exception as e:
            logger.error(f"get_plan_stats hatası: {e}")
            return {
                'waiting_count': 0, 'waiting_total': 0.0,
                'upcoming_count': 0, 'upcoming_total': 0.0,
                'overdue_count': 0, 'overdue_total': 0.0,
                'paid_this_month_count': 0, 'paid_this_month_total': 0.0,
                'month_pending_count': 0, 'month_pending_total': 0.0,
            }

    # ==================== AVANS İŞLEMLERİ ====================

    def give_advance(
        self,
        employee_id: int,
        amount: float,
        advance_date: Optional[str] = None,
        deduction_mode: str = 'full',
        installment_months: int = 1,
        account_id: Optional[int] = None,
        description: str = "",
        user_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Personele avans verir.
        - deduction_mode='full' → tam kesinti (bu ayki maaştan düşer)
        - deduction_mode='installment' → taksitli (installment_months ay boyunca)
        Avans, EmployeeLedger'a 'avans' tipiyle kaydedilir.
        """
        try:
            amt = round_currency(amount)
            if amt <= Decimal('0.00'):
                return False, "Avans tutarı 0'dan büyük olmalıdır!", None

            employee = employee_service.get_employee(employee_id)
            if not employee:
                return False, "Personel bulunamadı!", None

            if not advance_date:
                advance_date = datetime.now().date().strftime('%Y-%m-%d')

            if deduction_mode not in ('full', 'installment'):
                deduction_mode = 'full'

            installment_months = max(1, int(installment_months or 1))
            monthly_deduction = float(amt) if deduction_mode == 'full' else float(amt) / installment_months

            with db.transaction():
                # 1. Ledger'a avans kaydı
                ledger_id = db.execute_query("""
                    INSERT INTO EmployeeLedger (
                        employee_id, entry_type, amount, entry_date, description,
                        account_id, remaining_amount, is_closed, created_by
                    ) VALUES (%s, 'avans', %s, %s, %s, %s, %s, 0, %s)
                    RETURNING id
                """, (
                    employee_id, float(amt), advance_date,
                    (description or f"Avans ({'tam kesinti' if deduction_mode == 'full' else f'{installment_months} ay taksitli'})").strip(),
                    account_id, float(amt), user_id
                ))

                # 2. Hesap seçildiyse kasadan/bankadan çıkış
                if account_id:
                    ref_no = f"AVN-{ledger_id}"
                    db.execute_query("""
                        INSERT INTO BankTransactions (
                            branch_id, bank_account_id, transaction_date,
                            transaction_type, amount, description, reference_no, created_by
                        ) VALUES (%s, %s, %s, 'Withdrawal', %s, %s, %s, %s)
                    """, (
                        employee.get('branch_id'),
                        account_id,
                        advance_date,
                        float(amt),
                        f"Personel avansı: {employee['full_name']}",
                        ref_no,
                        user_id
                    ))
                    db.execute_query("""
                        UPDATE BankAccounts 
                        SET balance = balance - %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (float(amt), account_id))

            mode_text = "tam kesinti" if deduction_mode == 'full' else f"{installment_months} ay taksitli"
            logger.info(f"✅ Avans verildi: {employee['full_name']} - {amt} ₺ ({mode_text})")
            return True, f"{amt:,.2f} ₺ avans kaydedildi ({mode_text}).", ledger_id
        except Exception as e:
            logger.error(f"give_advance hatası: {e}")
            return False, f"Avans kaydedilemedi: {str(e)}", None

    def get_open_advances(self, employee_id: int) -> List[Dict]:
        """Personelin açık (kapatılmamış) avanslarını getirir"""
        try:
            return db.fetch_all("""
                SELECT 
                    id, employee_id, entry_type, amount, entry_date,
                    description, remaining_amount, is_closed, created_at
                FROM EmployeeLedger
                WHERE employee_id = %s 
                  AND entry_type = 'avans' 
                  AND is_closed = 0 
                  AND remaining_amount > 0
                ORDER BY entry_date ASC, id ASC
            """, (employee_id,))
        except Exception as e:
            logger.error(f"get_open_advances hatası: {e}")
            return []

    def get_total_open_advance(self, employee_id: int) -> float:
        """Personelin toplam açık avansını getirir"""
        try:
            row = db.fetch_one("""
                SELECT COALESCE(SUM(remaining_amount), 0) AS total
                FROM EmployeeLedger
                WHERE employee_id = %s AND entry_type = 'avans' AND is_closed = 0
            """, (employee_id,))
            return float(row['total'] or 0) if row else 0.0
        except Exception as e:
            logger.error(f"get_total_open_advance hatası: {e}")
            return 0.0

    def apply_advance_offsets(
        self,
        employee_id: int,
        salary_plan_id: int,
        gross_salary: float,
        max_deduction_ratio: float = 0.25,
        user_id: Optional[int] = None
    ) -> Tuple[float, List[Dict]]:
        """
        Personelin açık avanslarını maaştan keser (FIFO: en eski önce).
        max_deduction_ratio: brüt maaşın maksimum kesinti oranı (varsayılan %25).

        Returns:
            (toplam_kesinti, offset_detayları_listesi)
        """
        offsets_applied = []
        total_deduction = Decimal('0.00')

        try:
            open_advances = self.get_open_advances(employee_id)
            if not open_advances:
                return 0.0, []

            max_deduction = round_currency(gross_salary * max_deduction_ratio)
            remaining_budget = max_deduction

            with db.transaction():
                for adv in open_advances:
                    if remaining_budget <= Decimal('0.00'):
                        break

                    adv_remaining = round_currency(adv['remaining_amount'] or 0)
                    if adv_remaining <= Decimal('0.00'):
                        continue

                    deduct = min(adv_remaining, remaining_budget)

                    # 1. Avansın kalan tutarını düşür
                    new_remaining = round_currency(adv_remaining - deduct)
                    is_closed = 1 if new_remaining <= Decimal('0.00') else 0

                    db.execute_query("""
                        UPDATE EmployeeLedger 
                        SET remaining_amount = %s, is_closed = %s
                        WHERE id = %s
                    """, (float(new_remaining), is_closed, adv['id']))

                    # 2. Mahsup kaydı
                    db.execute_query("""
                        INSERT INTO AdvanceOffsets (
                            advance_ledger_id, salary_plan_id, offset_amount, offset_date
                        ) VALUES (%s, %s, %s, CURRENT_DATE)
                    """, (adv['id'], salary_plan_id, float(deduct)))

                    # 3. Ledger'a mahsup hareketi (bakiye düşümü için)
                    db.execute_query("""
                        INSERT INTO EmployeeLedger (
                            employee_id, entry_type, amount, entry_date, description,
                            payment_plan_id, remaining_amount, is_closed, created_by
                        ) VALUES (%s, 'mahsup', %s, CURRENT_DATE, %s, %s, 0, 1, %s)
                    """, (
                        employee_id, float(deduct),
                        f"Maaş mahsubu (Plan #{salary_plan_id})",
                        salary_plan_id, user_id
                    ))

                    offsets_applied.append({
                        'advance_id': adv['id'],
                        'advance_date': adv['entry_date'],
                        'advance_amount': float(adv['amount']),
                        'deducted': float(deduct),
                        'remaining_after': float(new_remaining),
                        'closed': bool(is_closed)
                    })

                    total_deduction += deduct
                    remaining_budget -= deduct

            if total_deduction > Decimal('0.00'):
                logger.info(f"💰 Avans mahsubu uygulandı: EmpID={employee_id}, Plan={salary_plan_id}, Toplam Kesinti={total_deduction}")

            return float(total_deduction), offsets_applied
        except Exception as e:
            logger.error(f"apply_advance_offsets hatası: {e}")
            return 0.0, []

    # ==================== MAAŞ PLANI OLUŞTURMA (AVANS MAHSUPLU) ====================

    def create_salary_plan(
        self,
        employee_id: int,
        period_month: int,
        period_year: int,
        due_date: str,
        gross_salary: Optional[float] = None,
        account_id: Optional[int] = None,
        notes: str = "",
        user_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Personel için maaş planı oluşturur ve açık avansları otomatik mahsup eder.

        Args:
            employee_id: Personel ID
            period_month: 1-12
            period_year: Yıl (2026 gibi)
            due_date: Ödeme tarihi (YYYY-MM-DD)
            gross_salary: Brüt maaş. None ise Employees.monthly_salary kullanılır.
            account_id: Ödeme yapılacak kasa/banka hesabı
            notes: Not
            user_id: Oluşturan kullanıcı

        Returns:
            (başarı, mesaj, yeni_plan_id)
        """
        try:
            employee = employee_service.get_employee(employee_id)
            if not employee:
                return False, "Personel bulunamadı!", None

            if gross_salary is None:
                gross_salary = float(employee.get('monthly_salary') or 0)

            gross = round_currency(gross_salary)
            if gross <= Decimal('0.00'):
                return False, "Brüt maaş 0'dan büyük olmalıdır!", None

            month_names = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                           "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
            period_text = f"{month_names[period_month]} {period_year}"
            plan_title = f"{employee['full_name']} - {period_text} Maaşı"

            # Aynı dönem için zaten plan var mı?
            existing = db.fetch_one("""
                SELECT id FROM PaymentPlans 
                WHERE plan_type = 'personel' 
                  AND payee_id = %s 
                  AND reference_type = 'salary' 
                  AND title LIKE %s
                  AND status != 'iptal'
            """, (employee_id, f"%{period_text}%"))

            if existing:
                return False, f"{period_text} dönemi için zaten bir maaş planı mevcut (ID: {existing['id']})!", existing['id']

            # Avans mahsubu yap (henüz plan ID yok, önce plan oluşturup sonra mahsup yapacağız)
            max_deduction_ratio = 0.25

            with db.transaction():
                # 1. Önce planı geçici olarak brüt tutarla oluştur
                plan_id = db.execute_query("""
                    INSERT INTO PaymentPlans (
                        branch_id, plan_type, title, payee_type, payee_id, payee_name,
                        total_amount, installment_count, installment_no,
                        gross_amount, advance_deduction, amount, due_date,
                        payment_method, account_id, status, reminder_days,
                        notes, reference_type, reference_id, created_by
                    ) VALUES (
                        %s, 'personel', %s, 'personel', %s, %s,
                        %s, 1, 1,
                        %s, 0, %s, %s,
                        'Havale / EFT', %s, 'bekliyor', 3,
                        %s, 'salary', %s, %s
                    )
                    RETURNING id
                """, (
                    employee.get('branch_id'),
                    plan_title,
                    employee_id,
                    employee['full_name'],
                    float(gross),
                    float(gross),  # geçici net = brüt
                    float(gross),
                    due_date,
                    account_id,
                    notes or f"{period_text} maaşı",
                    employee_id,
                    user_id
                ))

            # 2. Avans mahsubu (ayrı transaction içinde güvenli)
            total_deduction, offsets = self.apply_advance_offsets(
                employee_id=employee_id,
                salary_plan_id=plan_id,
                gross_salary=float(gross),
                max_deduction_ratio=max_deduction_ratio,
                user_id=user_id
            )

            # 3. Planı net tutarla güncelle
            net_amount = float(gross) - total_deduction
            if net_amount < 0:
                net_amount = 0.0

            with db.transaction():
                db.execute_query("""
                    UPDATE PaymentPlans 
                    SET gross_amount = %s,
                        advance_deduction = %s,
                        amount = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (float(gross), float(total_deduction), net_amount, plan_id))

                # 4. Maaş tahakkuk kaydı (ledger)
                db.execute_query("""
                    INSERT INTO EmployeeLedger (
                        employee_id, entry_type, amount, entry_date, description,
                        payment_plan_id, remaining_amount, is_closed, created_by
                    ) VALUES (%s, 'maas_tahakkuk', %s, CURRENT_DATE, %s, %s, 0, 1, %s)
                """, (
                    employee_id, float(gross),
                    f"Maaş tahakkuku: {period_text}",
                    plan_id, user_id
                ))

            msg = f"Maaş planı oluşturuldu: Brüt {gross:,.2f} ₺"
            if total_deduction > 0:
                msg += f", Avans kesintisi {total_deduction:,.2f} ₺, Net {net_amount:,.2f} ₺"
            else:
                msg += f", Net {net_amount:,.2f} ₺"

            logger.info(f"✅ {msg} (EmpID={employee_id}, Plan={plan_id})")
            return True, msg, plan_id
        except Exception as e:
            logger.error(f"create_salary_plan hatası: {e}")
            return False, f"Maaş planı oluşturulamadı: {str(e)}", None

    # ==================== YARDIMCILAR ====================

    def get_plan_type_options(self) -> List[Tuple[str, str]]:
        """Arayüz için plan tipi seçenekleri"""
        return list(PLAN_TYPES.items())

    def get_status_options(self) -> List[Tuple[str, str]]:
        """Arayüz için durum seçenekleri"""
        return list(STATUS.items())


# Singleton instance
payment_plan_service = PaymentPlanService()