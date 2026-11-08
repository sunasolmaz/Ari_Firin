# src/services/turnover_service.py
"""
Günlük Ciro, Gelir/Gider ve Akıllı Kayar Seçenek Servisi
+ Aylık ve Yıllık Ciro Raporlama Metotları
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Tuple, Optional, Any
from ..core.database import db
from ..core.logger import logger
from ..core.decimal_utils import to_decimal, round_currency


class TurnoverService:
    """Günlük Ciro, Gelir/Gider ve Akıllı Kayar Seçenek Servisi"""

    def __init__(self):
        try:
            db.ensure_turnover_tables()
        except Exception as e:
            logger.warning(f"TurnoverService tablo denetim uyarısı: {e}")

    # ==================== AKILLI KAYAR SEÇENEK (KATEGORİ HAVUZU) ====================

    def get_categories(self, branch_id: int, category_type: str) -> List[str]:
        """
        Şubenin ilgili türdeki (Income veya Expense) akıllı seçenek listesini döndürür.
        Hem kayıtlı kategorileri hem de geçmişte girilmiş benzersiz tanımları birleştirir.
        """
        try:
            # 1. Kategori tablosundan
            cat_rows = db.fetch_all("""
                SELECT DISTINCT name 
                FROM DailyTurnoverCategories 
                WHERE (branch_id = %s OR branch_id IS NULL) 
                AND category_type = %s
                ORDER BY name ASC
            """, (branch_id, category_type))

            # 2. Geçmiş hareketlerden varsa yeni eklenmiş olanları da çek
            entry_rows = db.fetch_all("""
                SELECT DISTINCT category as name
                FROM DailyTurnovers
                WHERE branch_id = %s 
                AND entry_type = %s
            """, (branch_id, category_type))

            names = set()
            for r in cat_rows:
                if r and r.get('name'):
                    names.add(r['name'].strip())
            for r in entry_rows:
                if r and r.get('name'):
                    names.add(r['name'].strip())

            # Boş olanları ele ve alfabetik sırala
            result = sorted([n for n in names if n])
            return result
        except Exception as e:
            logger.error(f"get_categories hatası ({category_type}): {e}")
            return []

    def add_category(self, branch_id: int, category_type: str, name: str) -> bool:
        """Yeni girilen bir tanımı akıllı seçenekler havuzuna ekler"""
        name_clean = (name or "").strip()
        if not name_clean:
            return False

        try:
            db.execute_query("""
                INSERT INTO DailyTurnoverCategories (branch_id, category_type, name)
                VALUES (%s, %s, %s)
                ON CONFLICT (branch_id, category_type, name) DO NOTHING
            """, (branch_id, category_type, name_clean))
            return True
        except Exception as e:
            logger.warning(f"add_category uyarısı: {e}")
            return False

    # ==================== HAREKET YÖNETİMİ (GELİR / GİDER) ====================

    def add_entry(
        self,
        branch_id: int,
        entry_date: str,
        entry_type: str,
        category: str,
        amount: float,
        payment_method: str = "Nakit",
        description: str = "",
        user_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Yeni bir gelir veya gider kaydı ekler.
        Girilen kategori/tanım daha önce yoksa otomatik olarak akıllı seçenekler havuzuna kaydeder.
        """
        try:
            cat_clean = (category or "").strip()
            if not cat_clean:
                return False, "Kategori / Tanım boş bırakılamaz!", None

            amt_dec = to_decimal(amount)
            if amt_dec <= Decimal('0'):
                return False, "Tutar 0'dan büyük olmalıdır!", None

            if entry_type not in ('Income', 'Expense'):
                return False, "Geçersiz işlem türü (Gelir veya Gider olmalıdır)!", None

            # Akıllı kayar seçeneği otomatik öğren / kaydet
            self.add_category(branch_id, entry_type, cat_clean)

            # Kaydı ekle
            new_id = db.execute_query("""
                INSERT INTO DailyTurnovers (
                    branch_id, entry_date, entry_type, category,
                    amount, payment_method, description, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                branch_id,
                entry_date,
                entry_type,
                cat_clean,
                float(amt_dec),
                payment_method or "Nakit",
                (description or "").strip(),
                user_id
            ))

            # Finansal entegrasyon: Kasa / Banka hareketini senkronize et
            self._sync_financial_transaction(
                branch_id, new_id, entry_date, entry_type,
                cat_clean, float(amt_dec), payment_method, description, user_id
            )

            logger.info(f"✅ Günlük ciro kaydı eklendi: ID={new_id}, Şube={branch_id}, Tip={entry_type}, Tutar={amt_dec}")
            return True, "Kayıt başarıyla eklendi.", new_id

        except Exception as e:
            logger.error(f"add_entry hatası: {e}")
            return False, f"Kayıt eklenirken hata oluştu: {str(e)}", None

    def _sync_financial_transaction(
        self,
        branch_id: int,
        entry_id: int,
        entry_date: str,
        entry_type: str,
        category: str,
        amount: float,
        payment_method: str,
        description: str,
        user_id: Optional[int]
    ):
        """Ciro gelir/gider hareketini Kasa/Banka hesaplarına otomatik yansıtır"""
        try:
            acc = db.fetch_one("""
                SELECT id, balance FROM BankAccounts 
                WHERE branch_id = %s AND is_active = TRUE 
                ORDER BY id ASC LIMIT 1
            """, (branch_id,))
            if not acc:
                acc_id = db.execute_query("""
                    INSERT INTO BankAccounts (branch_id, account_name, bank_name, balance, currency, is_active)
                    VALUES (%s, 'Şube Kasası / Ana Hesap', 'Kasa', 0.0, 'TRY', TRUE)
                    RETURNING id
                """, (branch_id,))
                cur_bal = 0.0
            else:
                acc_id = acc['id']
                cur_bal = float(acc['balance'] or 0)

            txn_type = 'Deposit' if entry_type == 'Income' else 'Withdrawal'
            delta = amount if entry_type == 'Income' else -amount
            new_bal = cur_bal + delta

            db.execute_query("""
                UPDATE BankAccounts SET balance = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s
            """, (new_bal, acc_id))

            ref = f"CIR-{entry_id}"
            desc = f"Ciro: {category} - {description or ''}".strip(" -")
            db.execute_query("""
                INSERT INTO BankTransactions (
                    branch_id, bank_account_id, transaction_date, transaction_type,
                    amount, description, reference_no, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                branch_id, acc_id, entry_date, txn_type,
                amount, desc[:200], ref, user_id
            ))
        except Exception as e:
            logger.warning(f"Ciro finansal entegrasyon uyarısı: {e}")

    def delete_entry(self, entry_id: Any) -> Tuple[bool, str]:
        """Kayıt sil (Serbest kasa/ciro hareketi)"""
        try:
            if isinstance(entry_id, str) and entry_id.startswith('inv_'):
                return False, "Faturalar ciro yönetiminden silinemez. Lütfen Faturalar sayfasını kullanın."

            rowcount = db.execute_query("DELETE FROM DailyTurnovers WHERE id = %s", (int(entry_id),))
            if rowcount and rowcount > 0:
                return True, "Kayıt silindi."
            return False, "Kayıt bulunamadı."
        except Exception as e:
            logger.error(f"delete_entry hatası: {e}")
            return False, f"Kayıt silinirken hata: {str(e)}"

    def _build_branch_filter(self, branch_id: Optional[int], table_prefix: str = "") -> Tuple[str, list]:
        """Şube filtre SQL parçası ve parametreleri"""
        prefix = f"{table_prefix}." if table_prefix else ""
        if branch_id and branch_id > 0:
            return f"{prefix}branch_id = %s", [branch_id]
        return "1=1", []

    def get_entries_by_date(self, branch_id: int, entry_date: str) -> List[Dict]:
        """
        Seçilen tarihe ait serbest kasa ve ciro hareketlerini listeler.
        Faturalar ile ciro tamamen ayrılmıştır (faturalar bu listede yer almaz).
        """
        try:
            b_cond_dt, b_params_dt = self._build_branch_filter(branch_id, "dt")

            # Sadece Serbest Kasa & Ciro Hareketleri
            dt_sql = f"""
                SELECT 
                    dt.id,
                    dt.branch_id,
                    dt.entry_date,
                    dt.entry_type,
                    dt.category,
                    dt.amount,
                    dt.payment_method,
                    dt.description,
                    dt.created_at,
                    u.full_name as created_by_name,
                    'turnover' as source
                FROM DailyTurnovers dt
                LEFT JOIN Users u ON dt.created_by = u.id
                WHERE {b_cond_dt} AND dt.entry_date = %s
                ORDER BY dt.created_at DESC, dt.id DESC
            """
            dt_rows = db.fetch_all(dt_sql, tuple(b_params_dt + [entry_date])) or []

            formatted_entries = []
            for r in dt_rows:
                formatted_entries.append(dict(r))

            return formatted_entries
        except Exception as e:
            logger.error(f"get_entries_by_date hatası: {e}")
            return []

    # ==================== ÖZET & CİRO HESAPLAMALARI ====================

    def get_daily_summary(self, branch_id: int, entry_date: str) -> Dict:
        """
        Belirtilen tarihin günlük ciro özetini hesaplar (Sadece Ciro / Kasa):
        - Toplam Gelir (Ciro = Kasa Geliri)
        - Nakit Gelir
        - Kart / POS Gelir
        - Toplam Gider (Kasa Gideri)
        - Net Günlük Ciro (Gelir - Gider)
        Faturalar cirodan tamamen ayrılmıştır.
        """
        try:
            b_cond_dt, b_params_dt = self._build_branch_filter(branch_id)

            dt_row = db.fetch_one(f"""
                SELECT 
                    COALESCE(SUM(CASE WHEN entry_type = 'Income' THEN amount ELSE 0 END), 0) as total_income,
                    COALESCE(SUM(CASE WHEN entry_type = 'Income' AND payment_method = 'Nakit' THEN amount ELSE 0 END), 0) as cash_income,
                    COALESCE(SUM(CASE WHEN entry_type = 'Income' AND payment_method != 'Nakit' THEN amount ELSE 0 END), 0) as card_income,
                    COALESCE(SUM(CASE WHEN entry_type = 'Expense' THEN amount ELSE 0 END), 0) as total_expense,
                    COUNT(*) as entry_count
                FROM DailyTurnovers
                WHERE {b_cond_dt} AND entry_date = %s
            """, tuple(b_params_dt + [entry_date]))

            dt_inc = float(dt_row['total_income']) if dt_row else 0.0
            dt_cash = float(dt_row['cash_income']) if dt_row else 0.0
            dt_card = float(dt_row['card_income']) if dt_row else 0.0
            dt_exp = float(dt_row['total_expense']) if dt_row else 0.0
            dt_cnt = int(dt_row['entry_count']) if dt_row else 0

            return {
                'total_income': dt_inc,
                'cash_income': dt_cash,
                'card_income': dt_card,
                'total_expense': dt_exp,
                'net_turnover': dt_inc - dt_exp,
                'entry_count': dt_cnt
            }
        except Exception as e:
            logger.error(f"get_daily_summary hatası: {e}")
            return {
                'total_income': 0.0,
                'cash_income': 0.0,
                'card_income': 0.0,
                'total_expense': 0.0,
                'net_turnover': 0.0,
                'entry_count': 0
            }

    def get_cumulative_turnover(self, branch_id: int, up_to_date: str) -> Dict:
        """
        O güne kadar olan kümülatif toplam ciroyu ve fireyi hesaplar (sadece kasa / ciro).
        Net Kümülatif = Toplam Gelir - Toplam Gider - Toplam Fire
        """
        try:
            b_cond_dt, b_params_dt = self._build_branch_filter(branch_id)

            dt_row = db.fetch_one(f"""
                SELECT 
                    COALESCE(SUM(CASE WHEN entry_type = 'Income' THEN amount ELSE 0 END), 0) as cumulative_income,
                    COALESCE(SUM(CASE WHEN entry_type = 'Expense' AND category != 'Fire / Zayiat Kaybı' THEN amount ELSE 0 END), 0) as cumulative_expense,
                    COALESCE(SUM(CASE WHEN entry_type = 'Expense' AND category = 'Fire / Zayiat Kaybı' THEN amount ELSE 0 END), 0) as cumulative_waste_dt
                FROM DailyTurnovers
                WHERE {b_cond_dt} AND entry_date <= %s
            """, tuple(b_params_dt + [up_to_date]))

            cum_inc = float(dt_row['cumulative_income']) if dt_row else 0.0
            cum_exp = float(dt_row['cumulative_expense']) if dt_row else 0.0
            cum_waste_dt = float(dt_row['cumulative_waste_dt']) if dt_row else 0.0

            # StockCountItems tablosundaki zayiatları da tara (eğer DailyTurnovers'a işlenmemişse kaçırmamak için)
            total_waste = cum_waste_dt
            try:
                sci_cond = "s.branch_id = %s" if branch_id > 0 else "1=1"
                sci_params = [branch_id, up_to_date] if branch_id > 0 else [up_to_date]
                sci_row = db.fetch_one(f"""
                    SELECT COALESCE(SUM(i.waste_value), 0) as total_sci_waste
                    FROM StockCountItems i
                    JOIN StockCountSessions s ON s.id = i.session_id
                    WHERE {sci_cond} AND s.created_at::date <= %s
                """, tuple(sci_params))
                sci_waste = float(sci_row['total_sci_waste']) if sci_row else 0.0
                if sci_waste > total_waste:
                    total_waste = sci_waste
            except Exception as we:
                logger.debug(f"get_cumulative_turnover stock waste check: {we}")

            cum_net = cum_inc - cum_exp - total_waste

            return {
                'cumulative_income': cum_inc,
                'cumulative_expense': cum_exp,
                'cumulative_waste': total_waste,
                'cumulative_net': cum_net
            }
        except Exception as e:
            logger.error(f"get_cumulative_turnover hatası: {e}")
            return {
                'cumulative_income': 0.0,
                'cumulative_expense': 0.0,
                'cumulative_waste': 0.0,
                'cumulative_net': 0.0
            }

    # ==================== 3 ŞUBE KONSOLİDE CİRO ÖZETİ ====================

    def get_three_branches_summary(self, target_date: Optional[str] = None) -> Dict:
        """
        Tüm aktif şubelerin (Armada, Çobançeşme, Rumeli, İmalathane vb.) hem günlük hem de
        o güne kadarki toplam kümülatif cirolarını, fire kayıplarını ve konsolide net kümülatifi döndürür.
        Net Kümülatif = Toplam Gelir - Toplam Gider - Toplam Fire
        """
        if not target_date:
            target_date = datetime.now().date().strftime('%Y-%m-%d')

        try:
            branches = db.fetch_all("""
                SELECT id, name, city 
                FROM Branches 
                WHERE is_active = TRUE 
                ORDER BY id ASC
                LIMIT 10
            """)

            branch_summaries = []
            grand_daily_income = 0.0
            grand_daily_expense = 0.0
            grand_cumulative_income = 0.0
            grand_cumulative_expense = 0.0
            grand_cumulative_waste = 0.0

            for b in branches:
                bid = b['id']
                bname = b['name']

                daily = self.get_daily_summary(bid, target_date)
                cum = self.get_cumulative_turnover(bid, target_date)

                b_data = {
                    'branch_id': bid,
                    'branch_name': bname,
                    'city': b.get('city', ''),
                    'daily_income': daily['total_income'],
                    'daily_cash': daily['cash_income'],
                    'daily_card': daily['card_income'],
                    'daily_expense': daily['total_expense'],
                    'daily_net': daily['net_turnover'],
                    'cumulative_income': cum['cumulative_income'],
                    'cumulative_expense': cum['cumulative_expense'],
                    'cumulative_waste': cum.get('cumulative_waste', 0.0),
                    'cumulative_net': cum['cumulative_net'],
                    'entry_count': daily['entry_count']
                }

                branch_summaries.append(b_data)

                grand_daily_income += daily['total_income']
                grand_daily_expense += daily['total_expense']
                grand_cumulative_income += cum['cumulative_income']
                grand_cumulative_expense += cum['cumulative_expense']
                grand_cumulative_waste += cum.get('cumulative_waste', 0.0)

            grand_cumulative_net = grand_cumulative_income - grand_cumulative_expense - grand_cumulative_waste

            return {
                'date': target_date,
                'branches': branch_summaries,
                'total_daily_income': grand_daily_income,
                'total_daily_expense': grand_daily_expense,
                'total_daily_net': grand_daily_income - grand_daily_expense,
                'grand_cumulative_income': grand_cumulative_income,
                'grand_cumulative_expense': grand_cumulative_expense,
                'grand_cumulative_waste': grand_cumulative_waste,
                'grand_cumulative_net': grand_cumulative_net,
            }
        except Exception as e:
            logger.error(f"get_three_branches_summary hatası: {e}")
            return {
                'date': target_date,
                'branches': [],
                'total_daily_income': 0.0,
                'total_daily_expense': 0.0,
                'total_daily_net': 0.0,
                'grand_cumulative_income': 0.0,
                'grand_cumulative_expense': 0.0,
                'grand_cumulative_waste': 0.0,
                'grand_cumulative_net': 0.0,
            }

    # ═══════════════════════════════════════════════════════════════════
    #  AYLIK / YILLIK RAPORLAMA METOTLARI (KASA + FATURA ENTEGRE)
    # ═══════════════════════════════════════════════════════════════════

    def get_monthly_summary(self, branch_id: int, year: int, month: int) -> Dict:
        """Belirtilen yıl ve ayın özetini döndürür"""
        start_date = f"{year:04d}-{month:02d}-01"
        if month == 12:
            next_m = datetime(year + 1, 1, 1)
        else:
            next_m = datetime(year, month + 1, 1)
        end_date = (next_m - timedelta(days=1)).strftime('%Y-%m-%d')
        return self.get_range_summary(branch_id, start_date, end_date)

    def get_yearly_summary(self, branch_id: int, year: int) -> Dict:
        """Belirtilen yılın özetini döndürür"""
        start_date = f"{year:04d}-01-01"
        end_date = f"{year:04d}-12-31"
        return self.get_range_summary(branch_id, start_date, end_date)

    def get_branch_financial_overview(self, branch_id: int, start_date: str, end_date: str) -> Dict:
        """
        Belirtilen şubenin verilen tarih aralığındaki tüm gelirlerini, faaliyet giderlerini,
        fire zararlarını ve net kazancını (Gelir - Gider - Fire) detaylı hesaplar.
        """
        try:
            b_cond_dt, b_params_dt = self._build_branch_filter(branch_id)

            sql = f"""
                SELECT 
                    COALESCE(SUM(CASE WHEN entry_type = 'Income' THEN amount ELSE 0 END), 0) as income,
                    COALESCE(SUM(CASE WHEN entry_type = 'Income' AND payment_method = 'Nakit' THEN amount ELSE 0 END), 0) as cash_income,
                    COALESCE(SUM(CASE WHEN entry_type = 'Income' AND payment_method != 'Nakit' THEN amount ELSE 0 END), 0) as card_income,
                    COALESCE(SUM(CASE WHEN entry_type = 'Expense' AND category != 'Fire / Zayiat Kaybı' THEN amount ELSE 0 END), 0) as expense,
                    COALESCE(SUM(CASE WHEN entry_type = 'Expense' AND category = 'Fire / Zayiat Kaybı' THEN amount ELSE 0 END), 0) as dt_waste,
                    COUNT(*) as entry_count
                FROM DailyTurnovers
                WHERE {b_cond_dt} AND entry_date BETWEEN %s AND %s
            """
            params = tuple(b_params_dt + [start_date, end_date])
            dt = db.fetch_one(sql, params)

            income = float(dt['income']) if dt else 0.0
            cash = float(dt['cash_income']) if dt else 0.0
            card = float(dt['card_income']) if dt else 0.0
            expense = float(dt['expense']) if dt else 0.0
            dt_waste = float(dt['dt_waste']) if dt else 0.0

            # StockCountItems tablosundaki zayiatları da dahil et
            sci_cond = "s.branch_id = %s" if branch_id > 0 else "1=1"
            sci_params = [branch_id, start_date, end_date] if branch_id > 0 else [start_date, end_date]
            sci = db.fetch_one(f"""
                SELECT COALESCE(SUM(i.waste_value), 0) as waste_val, COALESCE(SUM(i.waste_qty), 0) as waste_qty
                FROM StockCountItems i
                JOIN StockCountSessions s ON s.id = i.session_id
                WHERE {sci_cond} AND s.created_at::date BETWEEN %s AND %s
            """, tuple(sci_params))
            sci_waste = float(sci['waste_val']) if sci else 0.0
            sci_qty = float(sci['waste_qty']) if sci else 0.0

            total_waste = max(dt_waste, sci_waste)
            net_profit = income - expense - total_waste
            margin = (net_profit / income * 100.0) if income > 0 else 0.0

            return {
                'income': income,
                'cash_income': cash,
                'card_income': card,
                'expense': expense,
                'waste': total_waste,
                'waste_qty': sci_qty,
                'total_expense': expense + total_waste,
                'net_profit': net_profit,
                'profit_margin': margin,
                'entry_count': int(dt['entry_count']) if dt else 0
            }
        except Exception as e:
            logger.error(f"get_branch_financial_overview hatası: {e}")
            return {
                'income': 0.0,
                'cash_income': 0.0,
                'card_income': 0.0,
                'expense': 0.0,
                'waste': 0.0,
                'waste_qty': 0.0,
                'total_expense': 0.0,
                'net_profit': 0.0,
                'profit_margin': 0.0,
                'entry_count': 0
            }

    def get_range_summary(self, branch_id: int, start_date: str, end_date: str) -> Dict:
        """
        Belirli bir tarih aralığındaki toplam gelir/gider özeti (sadece kasa / ciro).
        Aylık veya yıllık raporlar için kullanılır.
        """
        try:
            b_cond_dt, b_params_dt = self._build_branch_filter(branch_id)

            dt_row = db.fetch_one(f"""
                SELECT 
                    COALESCE(SUM(CASE WHEN entry_type = 'Income' THEN amount ELSE 0 END), 0) as total_income,
                    COALESCE(SUM(CASE WHEN entry_type = 'Expense' THEN amount ELSE 0 END), 0) as total_expense,
                    COUNT(*) as entry_count
                FROM DailyTurnovers
                WHERE {b_cond_dt} AND entry_date BETWEEN %s AND %s
            """, tuple(b_params_dt + [start_date, end_date]))

            dt_inc = float(dt_row['total_income']) if dt_row else 0.0
            dt_exp = float(dt_row['total_expense']) if dt_row else 0.0
            dt_cnt = int(dt_row['entry_count']) if dt_row else 0

            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                days = (end_dt - start_dt).days + 1
            except Exception:
                days = 1

            return {
                'total_income': dt_inc,
                'total_expense': dt_exp,
                'net': dt_inc - dt_exp,
                'entry_count': dt_cnt,
                'avg_daily_income': dt_inc / days if days > 0 else 0.0,
                'avg_daily_expense': dt_exp / days if days > 0 else 0.0
            }
        except Exception as e:
            logger.error(f"get_range_summary hatası: {e}")
            return {
                'total_income': 0.0,
                'total_expense': 0.0,
                'net': 0.0,
                'entry_count': 0,
                'avg_daily_income': 0.0,
                'avg_daily_expense': 0.0
            }

    def get_daily_range(self, branch_id: int, start_date: str, end_date: str) -> List[Dict]:
        """
        Belirli bir tarih aralığındaki GÜNLÜK toplamları döndürür (sadece kasa / ciro).
        Aylık görünümde gün gün dağılım için kullanılır.
        """
        try:
            b_cond_dt, b_params_dt = self._build_branch_filter(branch_id)

            dt_rows = db.fetch_all(f"""
                SELECT 
                    entry_date as date,
                    COALESCE(SUM(CASE WHEN entry_type = 'Income' THEN amount ELSE 0 END), 0) as total_income,
                    COALESCE(SUM(CASE WHEN entry_type = 'Expense' THEN amount ELSE 0 END), 0) as total_expense,
                    COUNT(*) as entry_count
                FROM DailyTurnovers
                WHERE {b_cond_dt} AND entry_date BETWEEN %s AND %s
                GROUP BY entry_date
                ORDER BY entry_date ASC
            """, tuple(b_params_dt + [start_date, end_date])) or []

            result = []
            for r in dt_rows:
                d_str = str(r['date'])
                inc = float(r['total_income'])
                exp = float(r['total_expense'])
                result.append({
                    'date': d_str,
                    'total_income': inc,
                    'total_expense': exp,
                    'net': inc - exp,
                    'entry_count': int(r['entry_count'])
                })
            return result
        except Exception as e:
            logger.error(f"get_daily_range hatası: {e}")
            return []

    def get_monthly_range(self, branch_id: int, start_date: str, end_date: str) -> List[Dict]:
        """
        Belirli bir tarih aralığındaki AYLIK toplamları döndürür (sadece kasa / ciro).
        Yıllık görünümde ay ay dağılım için kullanılır.
        """
        try:
            b_cond_dt, b_params_dt = self._build_branch_filter(branch_id)

            dt_rows = db.fetch_all(f"""
                SELECT 
                    EXTRACT(MONTH FROM entry_date)::int as month,
                    EXTRACT(YEAR FROM entry_date)::int as year,
                    COALESCE(SUM(CASE WHEN entry_type = 'Income' THEN amount ELSE 0 END), 0) as total_income,
                    COALESCE(SUM(CASE WHEN entry_type = 'Expense' THEN amount ELSE 0 END), 0) as total_expense,
                    COUNT(*) as entry_count
                FROM DailyTurnovers
                WHERE {b_cond_dt} AND entry_date BETWEEN %s AND %s
                GROUP BY year, month
                ORDER BY year ASC, month ASC
            """, tuple(b_params_dt + [start_date, end_date])) or []

            result = []
            for r in dt_rows:
                inc = float(r['total_income'])
                exp = float(r['total_expense'])
                result.append({
                    'year': int(r['year']),
                    'month': int(r['month']),
                    'total_income': inc,
                    'total_expense': exp,
                    'net': inc - exp,
                    'entry_count': int(r['entry_count'])
                })
            return result
        except Exception as e:
            logger.error(f"get_monthly_range hatası: {e}")
            return []

    def get_category_summary(self, branch_id: int, start_date: str, end_date: str) -> List[Dict]:
        """
        Belirli bir tarih aralığındaki KATEGORİ bazlı toplamları döndürür (sadece kasa / ciro).
        Aylık ve yıllık raporlarda kategori dağılımı için kullanılır.
        """
        try:
            b_cond_dt, b_params_dt = self._build_branch_filter(branch_id)

            dt_rows = db.fetch_all(f"""
                SELECT 
                    entry_type,
                    category,
                    COALESCE(SUM(amount), 0) as total_amount,
                    COUNT(*) as entry_count
                FROM DailyTurnovers
                WHERE {b_cond_dt} AND entry_date BETWEEN %s AND %s
                GROUP BY entry_type, category
                ORDER BY entry_type, total_amount DESC
            """, tuple(b_params_dt + [start_date, end_date])) or []

            result = []
            for r in dt_rows:
                result.append({
                    'entry_type': r['entry_type'],
                    'category': r['category'],
                    'total_amount': float(r['total_amount']),
                    'entry_count': int(r['entry_count'])
                })
            return result
        except Exception as e:
            logger.error(f"get_category_summary hatası: {e}")
            return []

    # ═══════════════════════════════════════════════════════════════════
    #  YARDIMCI METOTLAR
    # ═══════════════════════════════════════════════════════════════════

    def get_best_day_in_range(self, branch_id: int, start_date: str, end_date: str) -> Dict:
        """
        Belirli tarih aralığındaki en yüksek gelirli günü döndürür (sadece kasa / ciro).
        Aylık görünümde "En İyi Gün" KPI kartı için kullanılır.
        """
        try:
            daily_data = self.get_daily_range(branch_id, start_date, end_date)
            if not daily_data:
                return {'date': None, 'total_income': 0.0}
            best = max(daily_data, key=lambda x: x.get('total_income', 0.0))
            return {
                'date': best.get('date'),
                'total_income': best.get('total_income', 0.0)
            }
        except Exception as e:
            logger.error(f"get_best_day_in_range hatası: {e}")
            return {'date': None, 'total_income': 0.0}

    def get_best_month_in_year(self, branch_id: int, year: int) -> Dict:
        """
        Belirtilen yıldaki en yüksek gelirli ayı döndürür (sadece kasa / ciro).
        Yıllık görünümde "En İyi Ay" KPI kartı için kullanılır.
        """
        try:
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
            monthly_data = self.get_monthly_range(branch_id, start_date, end_date)
            if not monthly_data:
                return {'month': None, 'total_income': 0.0}
            best = max(monthly_data, key=lambda x: x.get('total_income', 0.0))
            return {
                'month': best.get('month'),
                'total_income': best.get('total_income', 0.0)
            }
        except Exception as e:
            logger.error(f"get_best_month_in_year hatası: {e}")
            return {'month': None, 'total_income': 0.0}


# Singleton instance
turnover_service = TurnoverService()