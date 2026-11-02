# tests/test_setup_wizard.py
"""
İlk Kurulum Sihirbazı & Kısayol Yardımcısı Testleri
Masaüstü/Başlat menüsü kısayol yöneticisini, SetupWizardDialog yapılandırma ve
bağlantı teşhis mekanizmasını, Inno Setup betiğini test eder.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt5.QtWidgets import QApplication
from src.core.config import Config
from src.utils.shortcut_utils import (
    get_desktop_dir, get_start_menu_dir, create_windows_shortcut
)

# Testler için QApplication nesnesi
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestSetupWizardAndInstaller(unittest.TestCase):

    def test_01_shortcut_utils_directory_resolution(self):
        """Masaüstü ve Başlat Menüsü dizinlerinin doğru çözümlendiğini doğrular."""
        desktop = get_desktop_dir()
        self.assertIsNotNone(desktop)
        self.assertTrue(str(desktop).endswith("Desktop") or "Desktop" in str(desktop))

        start_menu = get_start_menu_dir()
        self.assertIsNotNone(start_menu)
        self.assertTrue("Programs" in str(start_menu) or "Start Menu" in str(start_menu))

    def test_02_shortcut_creation_with_temp_files(self):
        """Geçici dizinde Windows .lnk kısayolu oluşturmayı test eder."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_lnk = os.path.join(tmp_dir, "TestApp.lnk")
            ok = create_windows_shortcut(
                target_path=sys.executable,
                shortcut_path=tmp_lnk,
                description="Test Shortcut"
            )
            # Windows üzerinde PowerShell / COM ile lnk oluşmalıdır
            if sys.platform == "win32":
                self.assertTrue(ok, "Windows üzerinde kısayol oluşturma başarısız oldu!")
                self.assertTrue(os.path.exists(tmp_lnk), ".lnk kısayol dosyası oluşturulamadı!")

    def test_03_setup_wizard_instantiation_and_defaults(self):
        """SetupWizardDialog arayüzünün hatasız başlatıldığını ve alanların yüklendiğini test eder."""
        from src.ui.setup_wizard import SetupWizardDialog
        wizard = SetupWizardDialog()

        self.assertIsNotNone(wizard.txt_db_host.text())
        self.assertIsNotNone(wizard.txt_db_port.text())
        self.assertIsNotNone(wizard.txt_db_name.text())
        self.assertIsNotNone(wizard.txt_server_url.text())

        # Varsayılan portun integer dönüşümü
        db_cfg = wizard._get_form_db_config()
        self.assertIsInstance(db_cfg["port"], int)
        self.assertEqual(wizard.tabs.count(), 3)
        wizard.close()

    def test_04_setup_wizard_db_test_failure_handling(self):
        """Geçersiz bir host verildiğinde _on_test_db fonksiyonunun hatayı yakaladığını test eder."""
        from src.ui.setup_wizard import SetupWizardDialog
        wizard = SetupWizardDialog()

        # Geçersiz bağlantı bilgileri ver
        wizard.txt_db_host.setText("192.168.254.253")
        wizard.txt_db_port.setText("9999")
        wizard.txt_db_password.setText("yanlis_sifre")

        wizard._on_test_db()
        self.assertFalse(wizard.db_tested_success)
        self.assertIn("❌", wizard.db_status_lbl.text())
        wizard.close()

    def test_05_setup_wizard_save_and_config_update(self):
        """Sihirbazın ayarları config nesnesine ve diskteki config.json'a doğru yazdığını test eder."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_config_path = Path(tmp_dir) / "config.json"

            cfg = Config()
            old_path = getattr(cfg, '_config_path', None)
            cfg._config_path = fake_config_path

            try:
                from src.ui.setup_wizard import SetupWizardDialog
                wizard = SetupWizardDialog()
                wizard.chk_desktop_shortcut.setChecked(False)
                wizard.chk_start_menu_shortcut.setChecked(False)

                wizard.txt_db_host.setText("127.0.0.1")
                wizard.txt_db_port.setText("5433")
                wizard.txt_db_name.setText("test_wizard_db")
                wizard.txt_server_url.setText("http://testserver:8000")

                wizard._on_save_and_launch()

                # config.json diske yazıldı mı?
                self.assertTrue(fake_config_path.exists())
                with open(fake_config_path, "r", encoding="utf-8") as f:
                    import json
                    saved = json.load(f)

                self.assertEqual(saved["database"]["host"], "127.0.0.1")
                self.assertEqual(saved["database"]["port"], 5433)
                self.assertEqual(saved["database"]["database"], "test_wizard_db")
                self.assertEqual(saved["update"]["server_url"], "http://testserver:8000")
            finally:
                if old_path:
                    cfg._config_path = old_path

    def test_06_inno_setup_script_validation(self):
        """setup.iss dosyasının Inno Setup yönergelerini ve geçerli kaynakları içerdiğini doğrular."""
        setup_iss = os.path.join(PROJECT_ROOT, "setup.iss")
        self.assertTrue(os.path.exists(setup_iss), "setup.iss dosyası eksik!")

        with open(setup_iss, "r", encoding="utf-8") as f:
            content = f.read()

        # Temel Inno Setup bölümleri kontrolü
        self.assertIn("[Setup]", content)
        self.assertIn("[Files]", content)
        self.assertIn("[Icons]", content)
        self.assertIn("[Run]", content)
        self.assertIn("AriFirin.exe", content)
        self.assertIn("config.json", content)
        self.assertIn("--setup", content)


if __name__ == "__main__":
    unittest.main()
