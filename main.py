# main.py
"""
Muhasebe Uygulaması - Ana Giriş Noktası
Akış: Register → Login → Branch Select → Main
"""

import sys
import os

# Windows cp1254 UnicodeEncodeError koruması
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from PyQt5.QtWidgets import QApplication, QMessageBox, QSplashScreen, QStyleFactory
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QIcon

from src.core.database import db
from src.core.config import config
from src.core.logger import logger
from src.core.version import APP_VERSION
from src.models.user import User
from src.utils.error_handler import error_handler
from src.utils.backup_scheduler import BackupScheduler
from src.services.updater_service import updater
from src.ui.styles import AppStyles

sys.excepthook = error_handler.handle_exception


class Application:
    """Ana uygulama sınıfı"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        if "Fusion" in QStyleFactory.keys():
            self.app.setStyle(QStyleFactory.create("Fusion"))
        self.app.setApplicationName(config.get('application.name', 'Muhasebe Uygulaması'))
        self.app.setApplicationVersion(APP_VERSION)
        self.app.setStyleSheet(AppStyles.get_main_style())
        
        icon_path = "resources/icons/app.ico"
        if os.path.exists(icon_path):
            self.app.setWindowIcon(QIcon(icon_path))
        
        self.splash = None
        splash_path = "resources/images/splash.png"
        if os.path.exists(splash_path):
            self.splash = QSplashScreen(QPixmap(splash_path))
            self.splash.show()
            self.splash.showMessage("Başlatılıyor...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        
        self.backup_scheduler = BackupScheduler()
        self.setup_window = None
        self.login_window = None
        self.branch_window = None
        self.main_window = None
    
    def run(self):
        try:
            # Komut satırı parametresi denetimi (--setup / --config)
            if any(arg in sys.argv for arg in ("--setup", "--config", "-s")):
                self._close_splash()
                from src.ui.setup_wizard import SetupWizardDialog
                wizard = SetupWizardDialog()
                if wizard.exec_() != SetupWizardDialog.Accepted:
                    logger.info("Kurulum sihirbazı kullanıcı tarafından kapatıldı.")
                    return 0

            self._show_splash_message("📊 Veritabanı kontrol ediliyor...")
            if not self._initialize_database():
                self._close_splash()
                logger.warning("Veritabanına bağlanılamadı, kurulum sihirbazı seçeneği sunuluyor.")
                msg_box = QMessageBox()
                msg_box.setWindowTitle("Veritabanı Bağlantı Sorunu")
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setText(
                    "PostgreSQL veritabanına bağlanılamadı!\n\n"
                    "Sunucu adresi (IP) veya şifreniz değişmiş olabilir.\n"
                    "Ayarları düzenlemek için sihirbazı açabilirsiniz."
                )
                btn_wizard = msg_box.addButton("🛠️ Kurulum Sihirbazını Aç", QMessageBox.ActionRole)
                btn_exit = msg_box.addButton("Çıkış", QMessageBox.RejectRole)
                msg_box.exec_()

                if msg_box.clickedButton() == btn_wizard:
                    from src.ui.setup_wizard import SetupWizardDialog
                    wizard = SetupWizardDialog(autotest=True)
                    if wizard.exec_() == SetupWizardDialog.Accepted:
                        # Yeniden bağlanmayı dene
                        if not self._initialize_database():
                            QMessageBox.critical(None, "Bağlantı Hatası", "Yeni ayarlarla da veritabanına bağlanılamadı!")
                            return 1
                    else:
                        return 1
                else:
                    return 1

            self._show_splash_message("🔑 Lisans ve güvenlik kontrol ediliyor...")
            from src.utils.license_manager import LicenseManager
            self.license_manager = LicenseManager()
            is_valid, lic_msg = self.license_manager.verify_remote_license()
            if not is_valid:
                self._close_splash()
                logger.error(f"❌ Lisans doğrulama başarısız: {lic_msg}")
                msg_box = QMessageBox()
                msg_box.setWindowTitle("Lisans Hatası / Askıya Alındı")
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.setText(
                    f"Uygulama erişimi kısıtlandı:\n\n{lic_msg}\n\n"
                    f"Lisans anahtarınızı veya sunucu adresini güncellemek ister misiniz?"
                )
                btn_wizard = msg_box.addButton("🔑 Lisans Ayarlarını Aç", QMessageBox.ActionRole)
                btn_exit = msg_box.addButton("Kapat", QMessageBox.RejectRole)
                msg_box.exec_()

                if msg_box.clickedButton() == btn_wizard:
                    from src.ui.setup_wizard import SetupWizardDialog
                    wizard = SetupWizardDialog()
                    wizard.tabs.setCurrentIndex(1)  # Lisans sekmesine odaklan
                    if wizard.exec_() == SetupWizardDialog.Accepted:
                        is_valid, lic_msg = self.license_manager.verify_remote_license()
                        if not is_valid:
                            QMessageBox.critical(None, "Lisans Hatası", f"Lisans hâlâ geçersiz:\n{lic_msg}")
                            return 1
                    else:
                        return 1
                else:
                    return 1

            self._show_splash_message("💾 Yedekleme servisi başlatılıyor...")
            self.backup_scheduler.start()

            self._show_splash_message("🌐 Bulut bağlantısı ve güncellemeler kontrol ediliyor...")
            updater.start_background_services()

            self._show_splash_message("👤 Kullanıcı kontrol ediliyor...")
            
            # Kullanıcı var mı kontrol et
            first_user_exists = self._check_first_user()
            
            if not first_user_exists:
                # İlk kurulum - Kayıt ekranı
                logger.info("ℹ️ İlk kurulum - Kayıt ekranı açılıyor...")
                self._show_splash_message("🎉 İlk kurulum başlatılıyor...")
                QTimer.singleShot(50, self._show_register_window)
            else:
                # Giriş ekranı
                logger.info("ℹ️ Giriş ekranı açılıyor...")
                self._show_splash_message("🚀 Giriş ekranı yükleniyor...")
                QTimer.singleShot(50, self._show_login_window)
            
            exit_code = self.app.exec_()
            self._on_shutdown()
            return exit_code
            
        except Exception as e:
            logger.error(f"❌ Uygulama başlatma hatası: {e}")
            self._close_splash()
            QMessageBox.critical(None, "Başlatma Hatası", f"Uygulama başlatılamadı:\n{str(e)}")
            return 1
    
    def _show_splash_message(self, message: str):
        if self.splash:
            self.splash.showMessage(message, Qt.AlignBottom | Qt.AlignCenter, Qt.white)
            self.app.processEvents()
    
    def _close_splash(self):
        if self.splash:
            self.splash.close()
            self.splash = None
    
    def _initialize_database(self) -> bool:
        try:
            return db.initialize_database()
        except Exception as e:
            logger.error(f"❌ Veritabanı başlatma hatası: {e}")
            return False
    
    def _check_first_user(self) -> bool:
        try:
            from src.models.user import User
            # Başlangıçta önceki beklenmedik oturumları sıfırla
            User.reset_all_online_status()
            
            member_count = User.get_member_count()
            active_online_count = User.get_active_online_count()
            logger.info(f"👥 Uygulama Üye Sayısı: {member_count} | 🟢 Aktif Kullanıcı Sayısı: {active_online_count}")
            return member_count > 0
        except Exception as e:
            logger.error(f"❌ Kullanıcı kontrol hatası: {e}")
            return False
    
    def _show_register_window(self):
        """Kayıt ekranını göster"""
        self._close_splash()
        try:
            from src.ui.register_window import RegisterWindow
            self.setup_window = RegisterWindow()
            self.setup_window.register_successful.connect(self._on_register_completed)
            self.setup_window.show()
        except Exception as e:
            logger.error(f"❌ Kayıt penceresi açılamadı: {e}")
            QMessageBox.critical(None, "Hata", f"Kayıt penceresi açılamadı:\n{str(e)}")
            self.app.quit()
    
    def _on_register_completed(self):
        """Kayıt tamamlandığında giriş ekranını aç"""
        logger.info("✅ Kayıt tamamlandı, giriş ekranı açılıyor...")
        self.setup_window = None
        self._show_login_window()
    
    def _show_login_window(self):
        """Giriş ekranını göster"""
        self._close_splash()
        try:
            from src.ui.login_window import LoginWindow
            self.login_window = LoginWindow()
            self.login_window.login_successful.connect(self._on_login_successful)
            self.login_window.show()
        except Exception as e:
            logger.error(f"❌ Login penceresi açılamadı: {e}")
            QMessageBox.critical(None, "Hata", f"Giriş penceresi açılamadı:\n{str(e)}")
            self.app.quit()
    
    def _on_login_successful(self, user):
        """Giriş başarılı olduğunda ana pencereyi aç"""
        logger.info(f"✅ Giriş başarılı: {user.username}")
        
        try:
            # Multi-Tenant İzolasyon: Giriş yapan kullanıcının özel şemasını aktif et ve hazırla
            schema = user.get_tenant_schema() if hasattr(user, 'get_tenant_schema') else db.get_tenant_schema_for_user(user.id)
            db.set_tenant(schema)
            db.ensure_tenant_schema(schema)

            if user.has_permission('view_central'):
                from src.ui.central_window import CentralWindow
                self.central_window = CentralWindow(user)
                self.central_window.show()
            else:
                branch_id = getattr(user, 'branch_id', None)
                if not branch_id:
                    row = db.fetch_one("SELECT id FROM Branches WHERE is_active = TRUE ORDER BY id LIMIT 1")
                    if row:
                        branch_id = row['id']
                        user.branch_id = branch_id

                if branch_id:
                    from src.ui.main_window import MainWindow
                    self.main_window = MainWindow(user, branch_id)
                    self.main_window.show()
                else:
                    from src.ui.branch_select import BranchSelectWindow
                    self.branch_window = BranchSelectWindow(user)
                    self.branch_window.show()
            # Ana pencere başarıyla açıldıktan SONRA login penceresini gizle ve kapat
            if self.login_window:
                self.login_window.hide()
                self.login_window.close()
                self.login_window = None

            # Kullanıcı oturumu açtıktan 1.5 saniye sonra güncellemeleri kontrol et
            QTimer.singleShot(1500, lambda: updater.check_for_updates(silent=True))
        except Exception as e:

            logger.error(f"❌ Ana pencere açılamadı: {e}")
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Traceback:\n{tb}")
            QMessageBox.critical(
                None, "Hata",
                f"Ana uygulama penceresi açılamadı:\n\n{str(e)}\n\n"
                f"Lütfen log dosyasını kontrol edin.\n"
                f"Log: logs/muhasebe.log"
            )
            # Hata durumunda login penceresini tekrar göster
            if self.login_window:
                self.login_window.show()
    
    def _on_shutdown(self):
        try:
            logger.info("🔄 Uygulama kapatılıyor...")
            if hasattr(self, 'backup_scheduler'):
                self.backup_scheduler.stop()
            if hasattr(db, '_pool') and db._pool:
                try:
                    db._pool.closeall()
                except:
                    pass
            logger.info("✅ Uygulama başarıyla kapatıldı")
        except Exception as e:
            logger.error(f"❌ Kapanış hatası: {e}")


def main():
    print("=" * 60)
    print("ARI FIRIN MUHASEBE UYGULAMASI BASLATILIYOR")
    print("=" * 60)
    print(f"Tarih: {__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {sys.platform}")
    print("=" * 60)
    
    try:
        application = Application()
        exit_code = application.run()
        print("=" * 60)
        print(f"Uygulama kapatildi (Cikis kodu: {exit_code})")
        print("=" * 60)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nKullanici tarafindan iptal edildi")
        sys.exit(0)
    except Exception as e:
        print(f"\nBeklenmeyen hata: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()