# tests/test_security_audit.py
"""
Siber Güvenlik Denetim (Security Audit) Test Paketi
Denetlenen Zafiyetler:
1. RBAC Yetki Aşımı (Privilege Escalation) Kontrolleri
2. SQL Injection Sanitizasyonu & Whitelist Doğrulaması (ArchiverService)
3. Zayıf / Hardcoded Sabit "123456" Şifresinin Engellenmesi & Kriptografik Üretim
4. Şifre Karmaşıklığı (Password Strength Policy) Doğrulaması
5. Kimlik Bilgilerinde Ortam Değişkeni (Environment Variable Precedence) Önceliği
"""

import os
import sys
import unittest
import secrets

test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if test_dir not in sys.path:
    sys.path.insert(0, test_dir)

from src.models.user import User
from src.services.archiver_service import ArchiverService
from src.core.config import Config
from src.core.database import db


class TestSecurityAudit(unittest.TestCase):
    """Siber Güvenlik Denetim Test Senaryoları"""

    def test_01_rbac_permission_matrix_and_privilege_escalation_defense(self):
        """
        Kullanıcı rolleri için RBAC matrisini ve yetki aşımı korumasını test eder.
        User rolü genel merkeze erişememeli ve fatura silememelidir.
        """
        cashier = User({'username': 'kasiyer1', 'role': 'User'})
        accountant = User({'username': 'muhasebe1', 'role': 'Accountant'})
        manager = User({'username': 'mudur1', 'role': 'Manager'})
        admin = User({'username': 'admin1', 'role': 'Admin'})

        # 1. Genel merkez konsolide verilerini görme yetkisi
        self.assertFalse(cashier.has_permission('view_central'), "User rolü Genel Merkez'e erişememelidir!")
        self.assertFalse(accountant.has_permission('view_central'), "Accountant rolü Genel Merkez'e erişememelidir!")
        self.assertTrue(manager.has_permission('view_central'), "Manager Genel Merkez'e erişebilmelidir.")
        self.assertTrue(admin.has_permission('view_central'), "Admin Genel Merkez'e erişebilmelidir.")

        # 2. Fatura ve hareket silme yetkisi
        self.assertFalse(cashier.has_permission('delete'), "User rolü silme işlemi yapamamalıdır!")
        self.assertFalse(accountant.has_permission('delete'), "Accountant silme işlemi yapamamalıdır!")
        self.assertTrue(manager.has_permission('delete'), "Manager silme işlemi yapabilmelidir.")
        self.assertTrue(admin.has_permission('delete'), "Admin silme işlemi yapabilmelidir.")

        # 3. Kullanıcı ve sistem yönetimi yetkisi
        self.assertFalse(cashier.has_permission('manage_users'))
        self.assertFalse(manager.has_permission('manage_users'))
        self.assertTrue(admin.has_permission('manage_users'))

    def test_02_sql_injection_defense_in_archiver_service(self):
        """
        ArchiverService dinamik tablo sorgularında SQL enjeksiyonu ve
        whitelist dışı tablo erişim girişimlerinin engellendiğini denetler.
        """
        archiver = ArchiverService()
        malicious_tables = [
            "Invoices; DROP TABLE Users; --",
            "Invoices' OR '1'='1",
            "Users",  # Arşivlenemez, ana tablo
            "../../etc/passwd",
            "non_existent_table_99"
        ]

        for bad_table in malicious_tables:
            # restore_from_archive whitelist kontrolünden geçmeli ve False dönmelidir
            ok = archiver.restore_from_archive(bad_table, 1)
            self.assertFalse(
                ok,
                f"Kötü niyetli/geçersiz tablo '{bad_table}' için restore_from_archive False dönmelidir!"
            )

    def test_03_elimination_of_hardcoded_default_password(self):
        """
        Yeni bir kullanıcı oluşturulurken şifre verilmediğinde tahmin edilebilir
        sabit '123456' şifresinin atanmadığını, kriptografik rastgele güvenli
        bir geçici şifre üretildiğini veya '123456' ile oturum açılamadığını test eder.
        """
        uname = f"sec_user_{secrets.token_hex(4)}"
        new_user = User({
            'username': uname,
            'full_name': 'Test Security User',
            'role': 'User',
            'is_active': True
        })
        
        saved = new_user.save()
        self.assertTrue(saved, "Kullanıcı kaydedilebilmelidir.")

        try:
            # Yeni kullanıcı '123456' sabit şifresiyle ASLA giriş yapamamalıdır
            authenticated = new_user.authenticate("123456")
            self.assertFalse(
                authenticated,
                "Yeni kullanıcı '123456' varsayılan şifresiyle giriş yapamamalıdır! Sabit şifre zaafiyeti giderilmelidir."
            )
        finally:
            # Temizlik
            if new_user.id:
                db.execute_query("DELETE FROM Users WHERE id = %s", (new_user.id,))

    def test_04_password_strength_validation(self):
        """
        Şifre karmaşıklık politikasını (en az 8 karakter, büyük-küçük harf ve rakam) denetler.
        """
        self.assertFalse(User.validate_password_strength("12345")[0], "Kısa şifre reddedilmelidir.")
        self.assertFalse(User.validate_password_strength("sadeceharf")[0], "Rakam içermeyen şifre reddedilmelidir.")
        self.assertFalse(User.validate_password_strength("123456789")[0], "Harf içermeyen şifre reddedilmelidir.")
        self.assertFalse(User.validate_password_strength("hepsikucuk123")[0], "Büyük harf içermeyen şifre reddedilmelidir.")
        
        # Geçerli güçlü şifre
        is_valid, msg = User.validate_password_strength("GucluSifre2026!")
        self.assertTrue(is_valid, f"Güçlü şifre kabul edilmelidir: {msg}")

    def test_05_environment_variable_precedence(self):
        """
        Hassas veritabanı kimlik bilgilerinde ortam değişkenlerinin (DB_PASSWORD, DB_HOST)
        config.json içeriğine önceliklendirilerek ezildiğini doğrular.
        """
        os.environ["DB_HOST"] = "custom-secure-host"
        os.environ["DB_PASSWORD"] = "SuperSecretEnvPass123!"

        try:
            cfg = Config()
            db_cfg = cfg.get("database")
            self.assertEqual(
                db_cfg.get("host"), "custom-secure-host",
                "DB_HOST ortam değişkeni config değerine önceliklendirilmelidir."
            )
            self.assertEqual(
                db_cfg.get("password"), "SuperSecretEnvPass123!",
                "DB_PASSWORD ortam değişkeni config değerine önceliklendirilmelidir."
            )
        finally:
            del os.environ["DB_HOST"]
            del os.environ["DB_PASSWORD"]
            # Config'i orijinal haline döndürmek için tekrar yükle
            cfg._load_config()


if __name__ == '__main__':
    unittest.main(verbosity=2)
