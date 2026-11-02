# src/models/user.py
"""
User modeli - Kullanıcı işlemleri
PostgreSQL Multi-Tenant mimarisi ile uyumlu.
"""

import hashlib
from datetime import datetime
from typing import Optional, List, Dict

from ..core.database import db
from ..core.logger import logger


class User:
    """Kullanıcı modeli"""

    def __init__(self, data: Dict = None):
        if data:
            self.id = data.get('id')
            self.branch_id = data.get('branch_id')
            self.username = data.get('username')
            self.password_hash = data.get('password_hash')
            self.full_name = data.get('full_name')
            self.email = data.get('email')
            self.phone = data.get('phone')
            self.role = data.get('role', 'User')
            self.is_active = data.get('is_active', True)
            self.is_online = data.get('is_online', False)
            self.last_login = data.get('last_login')
            self.created_at = data.get('created_at')
            self.updated_at = data.get('updated_at')

    # ══════════════════════════════════════════════════════════════
    # ŞİFRE İŞLEMLERİ
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def hash_password(password: str) -> str:
        """Şifreyi PBKDF2-HMAC-SHA256 ile tuzlu (salted) hash'le"""
        import secrets
        salt = secrets.token_bytes(16)
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return f"pbkdf2:sha256:100000${salt.hex()}${key.hex()}"

    def authenticate(self, password: str) -> bool:
        """Şifreyi doğrula (Geriye dönük SHA256 desteği ve otomatik yükseltme ile)"""
        import hmac
        try:
            if not self.password_hash:
                return False

            if self.password_hash.startswith("pbkdf2:sha256:"):
                parts = self.password_hash.split('$')
                if len(parts) != 3:
                    return False
                iterations = int(parts[0].split(':')[2])
                salt = bytes.fromhex(parts[1])
                expected_key = bytes.fromhex(parts[2])
                candidate_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
                return hmac.compare_digest(candidate_key, expected_key)
            else:
                # Eski SHA256 kontrolü
                legacy_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
                if hmac.compare_digest(legacy_hash, self.password_hash):
                    # Başarılı girişte şifre hash'ini otomatik PBKDF2'ye yükselt
                    try:
                        new_hash = self.hash_password(password)
                        if self.id:
                            db.execute_query(
                                "UPDATE public.Users SET password_hash = %s WHERE id = %s",
                                (new_hash, self.id)
                            )
                            self.password_hash = new_hash
                            logger.info(f"🔒 Kullanıcı {self.username} şifre hash'i otomatik PBKDF2 seviyesine yükseltildi")
                    except Exception as e:
                        logger.error(f"Şifre hash yükseltme hatası: {e}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Şifre doğrulama hatası: {e}")
            return False

    @staticmethod
    def validate_password_strength(password: str) -> tuple:
        """
        Şifre karmaşıklık politikasını denetler (TEK KAYNAK):
        - En az 8 karakter
        - En az bir büyük harf (A-Z)
        - En az bir küçük harf (a-z)
        - En az bir rakam (0-9)
        """
        if not password or len(password) < 8:
            return False, "Şifre en az 8 karakter uzunluğunda olmalıdır."
        if not any(c.isupper() for c in password):
            return False, "Şifre en az bir büyük harf (A-Z) içermelidir."
        if not any(c.islower() for c in password):
            return False, "Şifre en az bir küçük harf (a-z) içermelidir."
        if not any(c.isdigit() for c in password):
            return False, "Şifre en az bir rakam (0-9) içermelidir."
        return True, "Şifre güvenlik kriterlerini karşılıyor."

    # ══════════════════════════════════════════════════════════════
    # TENANT (Kullanıcıya Özel Şema)
    # ══════════════════════════════════════════════════════════════

    def get_tenant_schema(self) -> str:
        """Kullanıcının özel izole PostgreSQL şema adını döndürür"""
        if not self.id:
            return "public"
        return f"tenant_usr_{self.id}"

    # ══════════════════════════════════════════════════════════════
    # KAYIT / GÜNCELLEME
    # ══════════════════════════════════════════════════════════════

    def save(self, branch_name: str = None) -> bool:
        """
        Kullanıcıyı kaydet.

        Args:
            branch_name: Yeni kullanıcı için tenant şemasında oluşturulacak
                         varsayılan şube adı. Verilmezse kullanıcı adından türetilir.

        Returns:
            Başarılı ise True
        """
        try:
            if self.id:
                # Güncelle
                db.execute_query("""
                    UPDATE public.Users 
                    SET branch_id = %s, username = %s, full_name = %s, 
                        email = %s, phone = %s, role = %s, 
                        is_active = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (self.branch_id, self.username, self.full_name,
                      self.email, self.phone, self.role,
                      self.is_active, self.id))
            else:
                # Yeni ekle
                if not self.password_hash:
                    import secrets
                    temp_random_pwd = secrets.token_urlsafe(16)
                    self.password_hash = self.hash_password(temp_random_pwd)

                result = db.execute_query("""
                    INSERT INTO public.Users 
                    (branch_id, username, password_hash, full_name, 
                     email, phone, role, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (self.branch_id, self.username, self.password_hash,
                      self.full_name, self.email, self.phone,
                      self.role, self.is_active))

                if result and isinstance(result, int):
                    self.id = result
                    # Yeni kullanıcıya özel izole veritabanı alanını (şemasını) oluştur
                    schema = self.get_tenant_schema()
                    final_branch_name = branch_name or f"{self.full_name or self.username} Şubesi"
                    try:
                        db.ensure_tenant_schema(schema, default_branch_name=final_branch_name)
                    except Exception as schema_err:
                        # Şeması kurulamayan yarım hesap bırakma: kaydı geri al
                        logger.error(f"❌ Yeni kullanıcı şeması kurulamadı, kayıt geri alınıyor: {schema_err}")
                        try:
                            db.execute_query(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                            db.execute_query("DELETE FROM public.Users WHERE id = %s", (self.id,))
                        except Exception as cleanup_err:
                            logger.error(f"❌ Yarım kayıt temizlenemedi: {cleanup_err}")
                        self.id = None
                        raise
                    logger.info(f"🏢 Tenant şeması oluşturuldu: {schema} (varsayılan şube: {final_branch_name})")
                    # Kullanıcının branch_id'sini kendi tenant şemasındaki ilk şubeyle eşle
                    try:
                        b_row = db.fetch_one(f'SELECT id FROM "{schema}".Branches LIMIT 1')
                        if b_row and b_row.get('id'):
                            self.branch_id = b_row['id']
                            db.execute_query("UPDATE public.Users SET branch_id = %s WHERE id = %s", (self.branch_id, self.id))
                    except Exception:
                        pass

            logger.info(f"✅ Kullanıcı kaydedildi: {self.username}")
            return True

        except Exception as e:
            logger.error(f"❌ Kullanıcı kaydetme hatası: {e}")
            return False

    def change_password(self, old_password: str, new_password: str) -> bool:
        """Şifre değiştir"""
        if not self.authenticate(old_password):
            logger.warning(f"❌ Şifre değiştirme başarısız: {self.username}")
            return False

        is_strong, msg = self.validate_password_strength(new_password)
        if not is_strong:
            logger.warning(f"❌ Zayıf şifre reddedildi ({self.username}): {msg}")
            return False

        try:
            self.password_hash = self.hash_password(new_password)
            db.execute_query("""
                UPDATE public.Users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (self.password_hash, self.id))
            logger.info(f"✅ Şifre değiştirildi: {self.username}")
            return True
        except Exception as e:
            logger.error(f"❌ Şifre değiştirme hatası: {e}")
            return False

    def reset_password(self, new_password: str) -> bool:
        """Şifreyi direkt sıfırla (Doğrulama kodu onaylandıktan sonra)"""
        is_strong, msg = self.validate_password_strength(new_password)
        if not is_strong:
            logger.warning(f"❌ Zayıf şifre reddedildi ({self.username}): {msg}")
            return False
        try:
            self.password_hash = self.hash_password(new_password)
            db.execute_query("""
                UPDATE public.Users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (self.password_hash, self.id))
            logger.info(f"✅ Şifre sıfırlandı: {self.username}")
            return True
        except Exception as e:
            logger.error(f"❌ Şifre sıfırlama hatası: {e}")
            return False

    def update_last_login(self) -> bool:
        """Son giriş tarihini güncelle"""
        try:
            db.execute_query("""
                UPDATE public.Users SET last_login = CURRENT_TIMESTAMP WHERE id = %s
            """, (self.id,))
            return True
        except Exception as e:
            logger.error(f"❌ Son giriş güncelleme hatası: {e}")
            return False

    def set_online(self, is_online: bool = True) -> bool:
        """Kullanıcının çevrimiçi (aktif) durumunu güncelle"""
        try:
            if not self.id:
                return False
            db.execute_query("""
                UPDATE public.Users 
                SET is_online = %s,
                    last_login = CASE WHEN %s = TRUE THEN CURRENT_TIMESTAMP ELSE last_login END
                WHERE id = %s
            """, (is_online, is_online, self.id))
            self.is_online = is_online
            logger.info(f"👤 Kullanıcı online durumu güncellendi: {self.username} -> {'🟢 Çevrimiçi' if is_online else '⚪ Çevrimdışı'}")
            return True
        except Exception as e:
            logger.error(f"❌ Online durumu güncelleme hatası: {e}")
            return False

    # ══════════════════════════════════════════════════════════════
    # SAYIM METOTLARI
    # ══════════════════════════════════════════════════════════════

    @classmethod
    def get_count(cls, active_only: bool = False) -> int:
        """
        Toplam kullanıcı sayısını döndürür.

        Args:
            active_only: True ise sadece aktif kullanıcıları sayar
        """
        try:
            if active_only:
                res = db.fetch_one("SELECT COUNT(*) as count FROM public.Users WHERE is_active = TRUE")
            else:
                res = db.fetch_one("SELECT COUNT(*) as count FROM public.Users")
            return res['count'] if res else 0
        except Exception as e:
            logger.error(f"Kullanıcı sayısı hatası: {e}")
            return 0

    @classmethod
    def get_member_count(cls) -> int:
        """Sistemde kayıtlı toplam aktif üye/kullanıcı sayısı"""
        return cls.get_count(active_only=True)

    @classmethod
    def get_active_online_count(cls) -> int:
        """O an sistemi aktif kullanan (çevrimiçi) kullanıcı sayısı"""
        try:
            res = db.fetch_one("SELECT COUNT(*) as count FROM public.Users WHERE is_active = TRUE AND is_online = TRUE")
            return res['count'] if res else 0
        except Exception as e:
            logger.error(f"Aktif online kullanıcı sayısı getirme hatası: {e}")
            return 0

    @classmethod
    def reset_all_online_status(cls) -> bool:
        """Sistem başlarken veya gerektiğinde tüm online durumlarını sıfırla"""
        try:
            db.execute_query("UPDATE public.Users SET is_online = FALSE")
            return True
        except Exception as e:
            logger.error(f"Online durumları sıfırlama hatası: {e}")
            return False

    # ══════════════════════════════════════════════════════════════
    # SORGU METOTLARI
    # ══════════════════════════════════════════════════════════════

    @classmethod
    def get_by_id(cls, user_id: int) -> Optional['User']:
        """ID'ye göre kullanıcı getir"""
        data = db.fetch_one("SELECT * FROM public.Users WHERE id = %s", (user_id,))
        return cls(data) if data else None

    @classmethod
    def get_by_username(cls, username: str) -> Optional['User']:
        """Kullanıcı adına göre getir"""
        data = db.fetch_one("SELECT * FROM public.Users WHERE username = %s", (username,))
        return cls(data) if data else None

    @classmethod
    def get_by_email(cls, email: str) -> Optional['User']:
        """E-posta adresine göre kullanıcı getir (büyük/küçük harf duyarsız)"""
        if not email:
            return None
        data = db.fetch_one("SELECT * FROM public.Users WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
        return cls(data) if data else None

    @classmethod
    def authenticate_user(cls, username: str, password: str, branch_id: int) -> Optional['User']:
        """Kullanıcıyı doğrula ve döndür"""
        user = cls.get_by_username(username)
        if user and user.authenticate(password) and user.is_active:
            user.update_last_login()
            logger.info(f"✅ Kullanıcı giriş yaptı: {username}")
            return user
        logger.warning(f"❌ Başarısız giriş denemesi: {username}")
        return None

    @classmethod
    def get_by_branch(cls, branch_id: int, active_only: bool = True) -> List['User']:
        """Şubeye göre kullanıcıları getir"""
        query = "SELECT * FROM public.Users WHERE branch_id = %s"
        if active_only:
            query += " AND is_active = TRUE"
        query += " ORDER BY full_name"

        results = db.fetch_all(query, (branch_id,))
        return [cls(data) for data in results]

    @classmethod
    def get_all(cls, active_only: bool = True) -> List['User']:
        """Tüm kullanıcıları getir"""
        query = "SELECT * FROM public.Users"
        if active_only:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY full_name"

        results = db.fetch_all(query)
        return [cls(data) for data in results]

    @classmethod
    def get_all_with_details(cls) -> List[Dict]:
        """Tüm kullanıcıları şube isimleri ve detaylarıyla birlikte getir"""
        try:
            query = """
                SELECT u.id, u.branch_id, u.username, u.full_name, u.email, u.phone, 
                       u.role, u.is_active, u.is_online, u.last_login, u.created_at, u.updated_at,
                       COALESCE(b.name, 'Atanmamış') as branch_name
                FROM public.Users u
                LEFT JOIN Branches b ON u.branch_id = b.id
                ORDER BY u.is_online DESC, u.is_active DESC, u.last_login DESC NULLS LAST, u.username ASC
            """
            return db.fetch_all(query)
        except Exception as e:
            logger.error(f"Kullanıcı detayları getirme hatası: {e}")
            return []

    @classmethod
    def get_active_online_users(cls) -> List[Dict]:
        """Şu anda aktif/çevrimiçi olan kullanıcıları getir"""
        try:
            query = """
                SELECT u.id, u.branch_id, u.username, u.full_name, u.email, u.role, 
                       u.last_login, COALESCE(b.name, 'Genel') as branch_name
                FROM public.Users u
                LEFT JOIN Branches b ON u.branch_id = b.id
                WHERE u.is_active = TRUE AND u.is_online = TRUE
                ORDER BY u.last_login DESC NULLS LAST, u.username ASC
            """
            return db.fetch_all(query)
        except Exception as e:
            logger.error(f"Aktif çevrimiçi kullanıcıları getirme hatası: {e}")
            return []

    # ══════════════════════════════════════════════════════════════
    # YÖNETİM METOTLARI
    # ══════════════════════════════════════════════════════════════

    @classmethod
    def force_logout(cls, user_id: int) -> bool:
        """Kullanıcının çevrimiçi oturumunu sonlandır"""
        try:
            db.execute_query("UPDATE public.Users SET is_online = FALSE WHERE id = %s", (user_id,))
            logger.info(f"🔒 Kullanıcı oturumu sonlandırıldı (ID: {user_id})")
            return True
        except Exception as e:
            logger.error(f"Oturum sonlandırma hatası: {e}")
            return False

    @classmethod
    def toggle_active_status(cls, user_id: int, is_active: bool) -> bool:
        """Kullanıcının aktiflik durumunu değiştir"""
        try:
            if not is_active:
                db.execute_query("""
                    UPDATE public.Users 
                    SET is_active = FALSE, is_online = FALSE, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """, (user_id,))
            else:
                db.execute_query("""
                    UPDATE public.Users 
                    SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """, (user_id,))
            logger.info(f"👤 Kullanıcı aktiflik durumu güncellendi: ID={user_id}, is_active={is_active}")
            return True
        except Exception as e:
            logger.error(f"Kullanıcı durumu değiştirme hatası: {e}")
            return False

    @classmethod
    def get_system_user_stats(cls) -> Dict:
        """Admin paneli için kullanıcı ve sistem istatistiklerini hesapla"""
        try:
            stats = {
                'total_users': 0,
                'online_users': 0,
                'active_users': 0,
                'inactive_users': 0,
                'admin_users': 0,
                'total_branches': 0,
                'total_invoices': 0,
                'total_customers': 0,
                'database_size_mb': 0.0
            }
            res_users = db.fetch_one("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN is_online = TRUE AND is_active = TRUE THEN 1 END) as online,
                    COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active,
                    COUNT(CASE WHEN is_active = FALSE THEN 1 END) as inactive,
                    COUNT(CASE WHEN role = 'Admin' THEN 1 END) as admins
                FROM public.Users
            """)
            if res_users:
                stats['total_users'] = res_users.get('total', 0)
                stats['online_users'] = res_users.get('online', 0)
                stats['active_users'] = res_users.get('active', 0)
                stats['inactive_users'] = res_users.get('inactive', 0)
                stats['admin_users'] = res_users.get('admins', 0)

            res_branch = db.fetch_one("SELECT COUNT(*) as count FROM Branches WHERE is_active = TRUE")
            if res_branch:
                stats['total_branches'] = res_branch.get('count', 0)

            res_inv = db.fetch_one("SELECT COUNT(*) as count FROM Invoices")
            if res_inv:
                stats['total_invoices'] = res_inv.get('count', 0)

            res_cust = db.fetch_one("SELECT COUNT(*) as count FROM Customers WHERE is_active = TRUE")
            if res_cust:
                stats['total_customers'] = res_cust.get('count', 0)

            stats['database_size_mb'] = db.get_database_size()
            return stats
        except Exception as e:
            logger.error(f"Sistem istatistikleri hatası: {e}")
            return {}

    # ══════════════════════════════════════════════════════════════
    # YETKİ KONTROLÜ
    # ══════════════════════════════════════════════════════════════

    def has_permission(self, permission: str) -> bool:
        """Kullanıcı yetki kontrolü (Granüler RBAC)"""
        permissions = {
            'Admin': ['*'],
            'Manager': ['view', 'create', 'edit', 'delete', 'report', 'view_central', 'branch_switch'],
            'Accountant': ['view', 'create', 'edit', 'report'],
            'User': ['view', 'create']
        }

        user_permissions = permissions.get(self.role, [])
        return '*' in user_permissions or permission in user_permissions

    def __str__(self):
        return self.full_name or self.username

    def __repr__(self):
        return f"<User: {self.username} ({self.role})>"