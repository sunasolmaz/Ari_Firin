# tests/test_installer_and_distribution.py
"""
Üretim Dağıtım Paketleri & Kurulum Bütünlüğü Testleri.
İkon dosyalarını, taşınabilir ZIP dağıtım paketlerini, otomatik kısayol
kurucuları (.bat) ve saha devir teslim kılavuzunu doğrular.
"""

import os
import sys
import zipfile
import unittest
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
ARI_ZIP = DIST_DIR / "AriFirin_Musteri_Dagitim_Paketi_v1.0.0.zip"
ADMIN_ZIP = DIST_DIR / "UniversalAdmin_Yonetici_Paketi_v1.0.0.zip"
ARI_ICO = PROJECT_ROOT / "resources" / "icons" / "app.ico"
ADMIN_ICO = PROJECT_ROOT / "UniversalAdmin" / "resources" / "icons" / "admin.ico"
HANDOVER_GUIDE = PROJECT_ROOT / "SAHA_KURULUM_VE_DEVIR_TESLIM_REHBERI.md"


class TestInstallerAndDistribution(unittest.TestCase):

    def test_01_ico_header_and_resolutions(self):
        """ICO simge dosyalarının mevcut olduğunu, geçerli başlık ve çoklu boyut içerdiğini doğrular."""
        self.assertTrue(ARI_ICO.exists(), f"Arı Fırın ikonu eksik: {ARI_ICO}")
        self.assertTrue(ADMIN_ICO.exists(), f"Universal Admin ikonu eksik: {ADMIN_ICO}")

        # İkili başlık denetimi (ICO magic: 00 00 01 00)
        with open(ARI_ICO, "rb") as f:
            ari_magic = f.read(4)
        self.assertEqual(ari_magic, b"\x00\x00\x01\x00", "Arı Fırın ikonu geçerli bir ICO başlığı içermiyor!")

        with open(ADMIN_ICO, "rb") as f:
            admin_magic = f.read(4)
        self.assertEqual(admin_magic, b"\x00\x00\x01\x00", "Admin ikonu geçerli bir ICO başlığı içermiyor!")

        # PIL ile çözünürlük denetimi (Kaynak sızıntısını önlemek için context manager)
        with Image.open(ARI_ICO) as ari_img:
            self.assertEqual(ari_img.format, "ICO")
            self.assertGreaterEqual(ari_img.size[0], 128, "Arı Fırın ikonu en az 128px genişliğinde olmalıdır!")

        with Image.open(ADMIN_ICO) as admin_img:
            self.assertEqual(admin_img.format, "ICO")
            self.assertGreaterEqual(admin_img.size[0], 128, "Admin ikonu en az 128px genişliğinde olmalıdır!")

    def test_02_ari_firin_distribution_zip_completeness(self):
        """Arı Fırın müşteri dağıtım ZIP paketinin eksiksiz ve bütünlüğünün tam olduğunu doğrular."""
        self.assertTrue(ARI_ZIP.exists(), f"Arı Fırın ZIP paketi eksik: {ARI_ZIP}")
        zip_size_mb = ARI_ZIP.stat().st_size / (1024 * 1024)
        self.assertGreater(zip_size_mb, 50, f"Arı Fırın ZIP boyutu beklenenden küçük: {zip_size_mb:.2f} MB")

        with zipfile.ZipFile(ARI_ZIP, "r") as z:
            names = z.namelist()

            # Kritik dosyalar
            self.assertIn("AriFirin.exe", names, "ZIP içinde AriFirin.exe bulunamadı!")
            self.assertIn("config.json", names, "ZIP içinde config.json bulunamadı!")
            self.assertIn("KURULUM_VE_KULLANIM_KILAVUZU.txt", names, "ZIP içinde kılavuz dosyası bulunamadı!")

            bat_found = any("Kurulum_Yap" in name for name in names)
            self.assertTrue(bat_found, "ZIP içinde kısayol kurucu bat bulunamadı!")

            # İkon dosyası resources içinde var mı?
            ico_found = any("app.ico" in name for name in names)
            self.assertTrue(ico_found, "ZIP içinde resources/icons/app.ico bulunamadı!")

            # AriFirin.exe binary doğrulaması (İlk 2 bayt MZ olmalı)
            with z.open("AriFirin.exe") as exe_f:
                magic = exe_f.read(2)
                self.assertEqual(magic, b"MZ", "ZIP içindeki AriFirin.exe geçerli bir PE binary değil!")

    def test_03_universal_admin_distribution_zip_completeness(self):
        """Universal Admin yönetici dağıtım ZIP paketinin eksiksiz ve bütünlüğünün tam olduğunu doğrular."""
        self.assertTrue(ADMIN_ZIP.exists(), f"Universal Admin ZIP paketi eksik: {ADMIN_ZIP}")
        zip_size_mb = ADMIN_ZIP.stat().st_size / (1024 * 1024)
        self.assertGreater(zip_size_mb, 20, f"Universal Admin ZIP boyutu beklenenden küçük: {zip_size_mb:.2f} MB")

        with zipfile.ZipFile(ADMIN_ZIP, "r") as z:
            names = z.namelist()

            # Kritik dosyalar
            self.assertIn("UniversalAdmin.exe", names, "ZIP içinde UniversalAdmin.exe bulunamadı!")
            self.assertIn("admin_security.json", names, "ZIP içinde admin_security.json bulunamadı!")
            self.assertIn("apps_registry.json", names, "ZIP içinde apps_registry.json bulunamadı!")
            self.assertIn("YONETICI_KILAVUZU.txt", names, "ZIP içinde yönetici kılavuzu bulunamadı!")

            bat_found = any("Yonetici_Paneli" in name for name in names)
            self.assertTrue(bat_found, "ZIP içinde yönetici bat bulunamadı!")

            # İkon dosyası var mı?
            ico_found = any("admin.ico" in name for name in names)
            self.assertTrue(ico_found, "ZIP içinde resources/icons/admin.ico bulunamadı!")

            # UniversalAdmin.exe binary doğrulaması
            with z.open("UniversalAdmin.exe") as exe_f:
                magic = exe_f.read(2)
                self.assertEqual(magic, b"MZ", "ZIP içindeki UniversalAdmin.exe geçerli bir PE binary değil!")

    def test_04_batch_scripts_syntax_and_encoding(self):
        """Kısayol oluşturan bat dosyalarının UTF-8 desteği ve doğru PowerShell çağrıları içerdiğini doğrular."""
        ari_pkg = DIST_DIR / "AriFirin_Kurulum_Paketi"
        admin_pkg = DIST_DIR / "UniversalAdmin_Yonetici_Paketi"

        ari_bats = list(ari_pkg.glob("*.bat"))
        admin_bats = list(admin_pkg.glob("*.bat"))

        self.assertGreater(len(ari_bats), 0, "Arı Fırın klasöründe .bat dosyası bulunamadı!")
        self.assertGreater(len(admin_bats), 0, "Admin klasöründe .bat dosyası bulunamadı!")

        with open(ari_bats[0], "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("chcp 65001", content)
            self.assertIn("WScript.Shell", content)
            self.assertIn("CreateShortcut", content)
            self.assertIn("Desktop", content)
            self.assertIn("Programs", content)
            self.assertIn("ICON_PATH", content)
            self.assertIn("--setup", content)

        with open(admin_bats[0], "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("chcp 65001", content)
            self.assertIn("WScript.Shell", content)
            self.assertIn("CreateShortcut", content)
            self.assertIn("Universal Admin Hub", content)
            self.assertIn("ICON_PATH", content)

    def test_05_handover_guide_exists_and_covers_topics(self):
        """Saha devir teslim rehberinin mevcut olduğunu ve tüm operasyonel konuları kapsadığını doğrular."""
        self.assertTrue(HANDOVER_GUIDE.exists(), f"Rehber dosyası eksik: {HANDOVER_GUIDE}")

        with open(HANDOVER_GUIDE, "r", encoding="utf-8") as f:
            guide_text = f.read()

        topics = [
            "İstemci Bilgisayarına Sıfırdan Kurulum",
            "Kurulum Sihirbazı",
            "Uzaktan Lisans Yönetimi",
            "Otomatik Bulut Yedekleme",
            "Felaket Kurtarma",
            "Canlı OTA Güncelleme",
            "Universal Admin",
            "Sorun Giderme",
            "sunaos:8000"
        ]
        for topic in topics:
            self.assertIn(topic, guide_text, f"Rehberde '{topic}' konusu eksik!")


if __name__ == "__main__":
    unittest.main()
