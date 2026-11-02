# tests/test_cloud_backup_license_sync.py
"""
Bulut Yedekleme ve Uzaktan Lisans Senkronizasyonu Entegrasyon Testleri
Merkezi Kontrol Sunucusu (sunaos:8000), Arı Fırın ve UniversalAdmin bileşenleri
arasındaki yedek iletimini ve lisans askıya alma/açma mekanizmasını test eder.
"""

import os
import sys
import json
import tempfile
import unittest
from datetime import datetime, timedelta

# Ana dizini yola ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.backup_scheduler import BackupScheduler
from src.utils.license_manager import LicenseManager
from UniversalAdmin.src.services.cloud_service import CloudService


class TestCloudBackupLicenseSync(unittest.TestCase):
    SERVER_URL = "http://sunaos:8000"
    PROJECT_ID = "ari_firin"
    CLIENT_NAME = "Tekirdağ Müşterisi"
    LICENSE_KEY = "ARI-FIRIN-TEKIRDAG-2026"

    @classmethod
    def setUpClass(cls):
        cls.cloud_service = CloudService(cls.SERVER_URL)
        # Sunucu ayakta mı kontrol et
        cls.server_online = cls.cloud_service.test_connection()
        if not cls.server_online:
            print("⚠️ UYARI: Merkezi sunucuya (sunaos:8000) erişilemedi!")

    def setUp(self):
        if not self.server_online:
            self.skipTest("Merkezi sunucu (sunaos:8000) aktif değil, entegrasyon testi atlanıyor.")

    def test_01_backup_scheduler_cloud_upload(self):
        """Arı Fırın yedekleme planlayıcısının merkezi sunucuya başarıyla yedek yükleyebildiğini test eder."""
        scheduler = BackupScheduler()
        test_content = b"-- ARI FIRIN YEDEK TEST VERISI " + datetime.now().isoformat().encode()

        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp_file:
            tmp_file.write(test_content)
            tmp_path = tmp_file.name

        try:
            success = scheduler.upload_to_cloud(tmp_path)
            self.assertTrue(success, "Bulut kontrol sunucusuna yedek yükleme başarısız oldu!")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_02_universal_admin_list_and_download_backup(self):
        """Universal Admin'in sunucudaki yedekleri listeleyip sağlam olarak indirebildiğini test eder."""
        backups = self.cloud_service.get_backups(self.PROJECT_ID)
        self.assertIsInstance(backups, list)
        self.assertGreater(len(backups), 0, "Sunucuda en az bir yedek listelenmelidir!")

        latest_backup = backups[0]
        filename = latest_backup["filename"]
        client_name = latest_backup["client_name"]

        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp_dl:
            dl_path = tmp_dl.name

        try:
            dl_success = self.cloud_service.download_backup(
                self.PROJECT_ID, client_name, filename, dl_path
            )
            self.assertTrue(dl_success, f"Yedek dosyası ({filename}) indirilemedi!")
            self.assertTrue(os.path.exists(dl_path))
            self.assertGreater(os.path.getsize(dl_path), 0, "İndirilen yedek dosyası boş olamaz!")
        finally:
            if os.path.exists(dl_path):
                os.remove(dl_path)

    def test_03_remote_license_verification_active(self):
        """Aktif lisansın merkezi sunucu tarafından onaylandığını ve imzalı önbellek oluştuğunu test eder."""
        with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as tmp_cache:
            cache_path = tmp_cache.name

        try:
            mgr = LicenseManager(cache_file=cache_path)
            valid, msg = mgr.verify_remote_license(
                server_url=self.SERVER_URL,
                project_id=self.PROJECT_ID,
                license_key=self.LICENSE_KEY
            )
            self.assertTrue(valid, f"Lisans onaylanmalıydı, dönen mesaj: {msg}")
            self.assertIn("onaylandı", msg.lower())

            # İmzalı önbelleğin oluştuğunu doğrula
            self.assertTrue(os.path.exists(cache_path))
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            self.assertTrue(cached.get("valid"))
            self.assertIsNotNone(cached.get("signature"))
        finally:
            if os.path.exists(cache_path):
                os.remove(cache_path)

    def test_04_remote_license_suspension_and_enforcement(self):
        """Universal Admin lisansı dondurduğunda Arı Fırın'ın lisans sorgusunda anında kilitlendiğini doğrular."""
        clients = self.cloud_service.get_clients(self.PROJECT_ID)
        target_client = None
        for c in clients:
            if c["license_key"] == self.LICENSE_KEY:
                target_client = c
                break

        self.assertIsNotNone(target_client, "Test lisansı sunucuda bulunamadı!")
        client_id = target_client["id"]

        with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as tmp_cache:
            cache_path = tmp_cache.name

        try:
            # 1. Lisansı DONDUR (Askıya al)
            toggled = self.cloud_service.toggle_client(client_id)
            self.assertTrue(toggled, "Lisans dondurma isteği başarısız oldu!")

            # 2. Arı Fırın lisans kontrolü yapmalı ve REDDETMELİ
            mgr = LicenseManager(cache_file=cache_path)
            valid, msg = mgr.verify_remote_license(
                server_url=self.SERVER_URL,
                project_id=self.PROJECT_ID,
                license_key=self.LICENSE_KEY
            )
            self.assertFalse(valid, "Askıya alınan lisans reddedilmelidir!")
            self.assertIn("askıya alınmıştır", msg.lower())

            # 3. Lisansı TEKRAR AKTİF ET
            restored = self.cloud_service.toggle_client(client_id)
            self.assertTrue(restored, "Lisansı tekrar aktif etme isteği başarısız oldu!")

            # 4. Arı Fırın tekrar geçerli lisans almalı
            valid_restored, msg_restored = mgr.verify_remote_license(
                server_url=self.SERVER_URL,
                project_id=self.PROJECT_ID,
                license_key=self.LICENSE_KEY
            )
            self.assertTrue(valid_restored, f"Lisans tekrar onaylanmalıydı: {msg_restored}")
        finally:
            if os.path.exists(cache_path):
                os.remove(cache_path)

    def test_05_offline_grace_period_and_expiry(self):
        """Sunucu erişilemediğinde 7 günlük çevrimdışı toleransı ve süre aşımını test eder."""
        with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as tmp_cache:
            cache_path = tmp_cache.name

        try:
            mgr = LicenseManager(cache_file=cache_path)

            # Senaryo A: Son doğrulama 2 gün önce yapılmış -> 7 günlük tolerans devrede olmalı
            recent_time = (datetime.now() - timedelta(days=2)).isoformat()
            sig = mgr._get_cache_signature(True, recent_time, mgr._get_machine_id())
            cached_data = {
                "valid": True,
                "message": "Lisans onaylandı.",
                "last_verified": recent_time,
                "machine_id": mgr._get_machine_id(),
                "signature": sig
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cached_data, f)

            mgr._load_remote_cache()
            valid, msg = mgr.verify_remote_license(server_url="http://192.168.254.254:9999")
            self.assertTrue(valid, "7 günden az çevrimdışı sürede erişim verilmeliydi!")
            self.assertIn("çevrimdışı mod", msg.lower())

            # Senaryo B: Son doğrulama 10 gün önce yapılmış -> Tolerans dolmuş olmalı
            old_time = (datetime.now() - timedelta(days=10)).isoformat()
            sig_old = mgr._get_cache_signature(True, old_time, mgr._get_machine_id())
            cached_data["last_verified"] = old_time
            cached_data["signature"] = sig_old
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cached_data, f)

            mgr._load_remote_cache()
            valid_expired, msg_expired = mgr.verify_remote_license(server_url="http://192.168.254.254:9999")
            self.assertFalse(valid_expired, "10 gün çevrimdışı kaldıktan sonra lisans reddedilmeliydi!")
            self.assertIn("tolerans süresi", msg_expired.lower())
        finally:
            if os.path.exists(cache_path):
                os.remove(cache_path)

    def test_06_cache_tamper_defense(self):
        """Önbellek dosyasındaki verinin tahrif edilmesi durumunda imzanın reddedildiğini test eder."""
        with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as tmp_cache:
            cache_path = tmp_cache.name

        try:
            mgr = LicenseManager(cache_file=cache_path)
            # Sahte veri yaz ama imzayı uydurma
            tampered_data = {
                "valid": True,
                "message": "Sahte Lisans",
                "last_verified": datetime.now().isoformat(),
                "machine_id": mgr._get_machine_id(),
                "signature": "FAKESIGNATURE12345"
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(tampered_data, f)

            mgr._load_remote_cache()
            self.assertIsNone(mgr.cached_remote_status, "Tahrif edilmiş imza reddedilmelidir!")
        finally:
            if os.path.exists(cache_path):
                os.remove(cache_path)


if __name__ == "__main__":
    unittest.main()
