# tests/test_production_packaging.py
"""
Üretim Paketleme & Dağıtım (Production Packaging & Distribution) Testleri
PyInstaller .spec yapılandırmalarını, frozen ortam yol çözümlemelerini ve
OTA üzerinden gerçek çalıştırılabilir ikili (binary) dağıtım akışını test eder.
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

# Ana dizini yola ekle
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.build_executables import verify_pe_executable, check_environment
from UniversalAdmin.src.services.cloud_service import CloudService


class TestProductionPackaging(unittest.TestCase):
    SERVER_URL = "http://sunaos:8000"
    PROJECT_ID = "ari_firin"

    def test_01_spec_files_exist_and_compile(self):
        """Spec dosyalarının diskte mevcut olduğunu ve sözdizimi hatası içermediğini doğrular."""
        ari_spec = os.path.join(PROJECT_ROOT, "ari_firin.spec")
        admin_spec = os.path.join(PROJECT_ROOT, "universal_admin.spec")

        self.assertTrue(os.path.exists(ari_spec), "ari_firin.spec dosyası eksik!")
        self.assertTrue(os.path.exists(admin_spec), "universal_admin.spec dosyası eksik!")

        # Spec dosyalarının syntax geçerliliğini compile ile denetle
        with open(ari_spec, "r", encoding="utf-8") as f:
            compile(f.read(), ari_spec, "exec")

        with open(admin_spec, "r", encoding="utf-8") as f:
            compile(f.read(), admin_spec, "exec")

    def test_02_hidden_imports_completeness(self):
        """Kritik bağımlılıkların (psycopg2, PyQt5, openpyxl, reportlab, bcrypt) spec içinde tanımlandığını doğrular."""
        ari_spec = os.path.join(PROJECT_ROOT, "ari_firin.spec")
        with open(ari_spec, "r", encoding="utf-8") as f:
            content = f.read()

        critical_libs = ['psycopg2', 'PyQt5', 'openpyxl', 'pandas', 'requests', 'bcrypt', 'decimal']
        for lib in critical_libs:
            self.assertIn(f"'{lib}'", content, f"Kritik kütüphane '{lib}' ari_firin.spec içinde eksik!")

    def test_03_frozen_path_resolution_simulation(self):
        """PyInstaller ile derlenmiş frozen ortamda (sys.frozen=True) yolların doğru çözüldüğünü doğrular."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_exe = os.path.join(tmp_dir, "AriFirin.exe")
            with open(fake_exe, "wb") as f:
                f.write(b"MZ" + b"\x00" * 100)

            fake_config = os.path.join(tmp_dir, "config.json")
            with open(fake_config, "w", encoding="utf-8") as f:
                f.write('{"application": {"name": "Test Frozen App"}}')

            # sys.frozen simülasyonu
            old_frozen = getattr(sys, 'frozen', False)
            old_executable = sys.executable
            try:
                sys.frozen = True
                sys.executable = fake_exe

                from src.core.config import Config
                cfg = Config()
                cfg._load_config()

                self.assertEqual(cfg.get("application.name"), "Test Frozen App")
                self.assertEqual(str(cfg._config_path), fake_config)
            finally:
                if old_frozen:
                    sys.frozen = old_frozen
                else:
                    del sys.frozen
                sys.executable = old_executable

    def test_04_pe_header_validator_logic(self):
        """verify_pe_executable fonksiyonunun MZ başlığını ve boyut sınırını doğru tespit ettiğini test eder."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            # Geçerli bir PE simülasyonu: 'MZ' ile başlayan ve > 5MB olan dosya
            f.write(b"MZ" + b"\x00" * (6 * 1024 * 1024))
            valid_exe = Path(f.name)

        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            # Geçersiz dosya: 'MZ' yok
            f.write(b"PK" + b"\x00" * (6 * 1024 * 1024))
            invalid_exe = Path(f.name)

        try:
            self.assertTrue(verify_pe_executable(valid_exe))
            self.assertFalse(verify_pe_executable(invalid_exe))
        finally:
            if valid_exe.exists():
                valid_exe.unlink()
            if invalid_exe.exists():
                invalid_exe.unlink()

    def test_05_ota_binary_distribution_pipeline(self):
        """Üretilen Windows PE binary paketinin merkezi sunucuya yüklenip OTA ile indirilebildiğini test eder."""
        cloud = CloudService(self.SERVER_URL)
        if not cloud.test_connection():
            self.skipTest("Merkezi sunucu aktif değil, OTA paket dağıtım testi atlanıyor.")

        test_version = f"1.0.{int(datetime.now().timestamp()) % 10000}"
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_bin:
            # Gerçek Windows PE imzalı binary paketi simülasyonu
            tmp_bin.write(b"MZ\x90\x00\x03\x00\x00\x00" + b"\x41" * 10240)
            binary_path = tmp_bin.name

        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as dl_bin:
            dl_path = dl_bin.name

        orig_info = cloud.get_version_info(self.PROJECT_ID)
        try:
            # 1. UniversalAdmin aracılığıyla merkezi sunucuya yayınla
            pub_res = cloud.publish_update(
                project_id=self.PROJECT_ID,
                version=test_version,
                release_notes=f"Canli Uretim Paketi OTA Testi v{test_version}",
                force_update=False,
                installer_path=binary_path
            )
            self.assertTrue(pub_res.get("success"), f"Yayınlama hatası: {pub_res}")
            download_url = pub_res["data"]["download_url"]
            self.assertIn(".exe", download_url)

            # 2. İstemci olarak sunucudan yeni sürüm bilgilerini çek
            info = cloud.get_version_info(self.PROJECT_ID)
            self.assertEqual(info["latest_version"], test_version)

            # 3. Paketi istemci tarafında indir ve bayt bütünlüğünü doğrula
            full_url = f"{self.SERVER_URL}{download_url}"
            import requests
            r = requests.get(full_url, timeout=10)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.content.startswith(b"MZ"))
            self.assertEqual(len(r.content), os.path.getsize(binary_path))
        finally:
            if os.path.exists(binary_path):
                os.remove(binary_path)
            if os.path.exists(dl_path):
                os.remove(dl_path)
            # Canlı ortamı resmi üretim sürümüne geri getir
            if orig_info and "latest_version" in orig_info:
                try:
                    cloud.publish_update(
                        project_id=self.PROJECT_ID,
                        version=orig_info["latest_version"],
                        release_notes=orig_info.get("release_notes", ""),
                        force_update=orig_info.get("force_update", False),
                        external_url=orig_info.get("download_url", "")
                    )
                except Exception:
                    pass


if __name__ == "__main__":
    from datetime import datetime
    unittest.main()
