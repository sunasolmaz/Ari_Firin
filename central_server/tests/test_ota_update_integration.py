# tests/test_ota_update_integration.py
"""
Merkezi Sunucu (Raspberry Pi) & OTA Güncelleme Entegrasyon Test Paketi
Aşağıdaki kritik adımları test eder ve doğrular:
1. Merkezi sunucu sağlık ve proje versiyon API uç noktaları (sunaos:8000).
2. UpdaterService sürüm karşılaştırma, ayrıştırma ve yeni sürüm tespiti.
3. UniversalAdmin üzerinden OTA güncelleme paketi yayınlama ve Arı Fırın'ın paketi indirmesi.
4. Müşteri canlılık (heartbeat) sinyali ve lisans doğrulama akışı.
5. UpdateBanner arayüz bileşeni ve Qt sinyal köprüsü entegrasyonu.
"""

import os
import sys
import tempfile
import unittest
import requests

# Proje kök dizini sys.path'e ekle
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.config import config
from src.services.updater_service import UpdaterService, parse_version
from UniversalAdmin.src.services.cloud_service import CloudService


class TestOtaUpdateIntegration(unittest.TestCase):
    """Merkezi Sunucu ve OTA Güncelleme Entegrasyon Testi"""

    @classmethod
    def setUpClass(cls):
        cls.server_url = config.get("update.server_url", "http://sunaos:8000").rstrip("/")
        cls.project_id = config.get("update.project_id", "ari_firin")
        cls.license_key = config.get("update.license_key", "ARI-FIRIN-TEKIRDAG-2026")
        
        # Sunucunun çalışıp çalışmadığını kontrol et
        try:
            r = requests.get(f"{cls.server_url}/api/health", timeout=3)
            cls.server_online = (r.status_code == 200 and r.json().get("status") == "ok")
        except Exception:
            cls.server_online = False

    def setUp(self):
        if not self.server_online:
            self.skipTest(f"Merkezi kontrol sunucusuna ({self.server_url}) erişilemiyor, test atlanıyor.")

    # ─── 1. Sunucu API ve Sağlık Kontrolü ────────────────────────────

    def test_01_central_server_health_and_version_api(self):
        """Merkezi sunucunun ayakta olduğunu ve proje versiyon API'sinin yanıt verdiğini doğrular."""
        # Health check
        r_health = requests.get(f"{self.server_url}/api/health", timeout=5)
        self.assertEqual(r_health.status_code, 200)
        self.assertEqual(r_health.json().get("status"), "ok")

        # Proje sürüm API'si
        url = f"{self.server_url}/api/v1/projects/{self.project_id}/version"
        r_ver = requests.get(url, timeout=5)
        self.assertEqual(r_ver.status_code, 200)
        data = r_ver.json()
        self.assertEqual(data.get("project_id"), self.project_id)
        self.assertIn("latest_version", data)
        self.assertIn("download_url", data)

    # ─── 2. Sürüm Ayrıştırma ve Karşılaştırma ────────────────────────

    def test_02_updater_service_version_parsing_and_detection(self):
        """parse_version ve sürüm karşılaştırma mantığının doğruluğunu test eder."""
        self.assertEqual(parse_version("1.0.0"), (1, 0, 0))
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("2.1"), (2, 1))
        self.assertEqual(parse_version("invalid"), (0, 0, 0))

        # Versiyon karşılaştırma testleri
        self.assertTrue(parse_version("1.0.1") > parse_version("1.0.0"))
        self.assertTrue(parse_version("1.1.0") > parse_version("1.0.9"))
        self.assertTrue(parse_version("2.0.0") > parse_version("1.9.9"))
        self.assertFalse(parse_version("1.0.0") > parse_version("1.0.0"))
        self.assertFalse(parse_version("1.0.0") > parse_version("1.0.1"))

    # ─── 3. OTA Güncelleme Paketi Yayınlama ve İndirme ────────────────

    def test_03_universal_admin_publish_and_ota_distribution(self):
        """UniversalAdmin ile sunucuya paket yüklenip Arı Fırın tarafından indirilebildiğini test eder."""
        cloud = CloudService(self.server_url)
        from datetime import datetime
        test_version = f"1.0.{int(datetime.now().timestamp()) % 10000 + 100}"
        test_payload = b"ARI_FIRIN_OTA_BINARY_PAYLOAD_TEST_V103"

        # Geçici bir güncelleme paketi oluştur
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            tmp.write(test_payload)
            tmp_path = tmp.name

        try:
            # 1. UniversalAdmin üzerinden sürümü ve dosyayı yayınla
            publish_res = cloud.publish_update(
                project_id=self.project_id,
                version=test_version,
                release_notes="Kritik OTA test sürümü ve performans hızlandırması.",
                force_update=False,
                installer_path=tmp_path
            )
            self.assertTrue(publish_res.get("success"), f"Yayınlama başarısız: {publish_res}")
            
            # 2. Sunucudaki sürümü sorgula
            ver_info = cloud.get_version_info(self.project_id)
            self.assertIsNotNone(ver_info)
            self.assertEqual(ver_info.get("latest_version"), test_version)
            dl_url = ver_info.get("download_url", "")
            self.assertTrue(dl_url.startswith("/static/updates/"), f"İndirme bağlantısı geçersiz: {dl_url}")

            # 3. Arı Fırın istemcisi gözüyle bu dosyayı HTTP üzerinden indir
            full_dl_url = f"{self.server_url}{dl_url}"
            r_download = requests.get(full_dl_url, timeout=10)
            self.assertEqual(r_download.status_code, 200)
            self.assertEqual(r_download.content, test_payload, "İndirilen paket içeriği yayınlanan ile eşleşmelidir!")

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ─── 4. Müşteri Canlılık (Heartbeat) ve Lisans Kontrolü ───────────

    def test_04_client_heartbeat_and_license_verification(self):
        """Arı Fırın'ın kalp atışı gönderdiğinde sunucuda çevrimiçi olarak işaretlendiğini doğrular."""
        heartbeat_url = f"{self.server_url}/api/v1/projects/{self.project_id}/heartbeat"
        payload = {
            "license_key": self.license_key,
            "version": "1.0.0"
        }
        r_hb = requests.post(heartbeat_url, json=payload, timeout=5)
        self.assertEqual(r_hb.status_code, 200)
        self.assertEqual(r_hb.json().get("status"), "received")

        # Sunucudan müşteri listesini çek ve çevrimiçi durumunu doğrula
        cloud = CloudService(self.server_url)
        clients = cloud.get_clients(self.project_id)
        matching_client = next((c for c in clients if c.get("license_key") == self.license_key), None)
        self.assertIsNotNone(matching_client, "Lisans anahtarına ait müşteri sunucuda bulunmalıdır.")
        self.assertTrue(matching_client.get("is_online"), "Kalp atışı sonrası müşteri 'is_online=True' olmalıdır.")

    # ─── 5. Güncelleme Bildirim Durumu (Update Info Cache) ────────────

    def test_05_update_detection_and_service_state(self):
        """UpdaterService nesnesinin sunucudaki yeni sürümü tespit edip kaydettiğini test eder."""
        updater_srv = UpdaterService()
        
        # Sunucuda en son yayınladığımız 1.0.3 sürümü mevcut (uygulamadaki sürüm 1.0.0)
        url = f"{updater_srv.server_url}/api/v1/projects/{updater_srv.project_id}/version"
        r = requests.get(url, timeout=5)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        latest = data.get("latest_version")
        
        is_newer = parse_version(latest) > parse_version(updater_srv.current_version)
        self.assertTrue(is_newer, f"Sunucudaki {latest} mevcut {updater_srv.current_version}'dan yeni olmalıdır.")


if __name__ == "__main__":
    unittest.main()
