import os
import requests
from PyQt5.QtWidgets import QMessageBox, QProgressDialog, QApplication
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from ..core.config import config
from ..services.updater_service import updater, UpdaterService, parse_version

# Geriye dönük uyumluluk için alias
UpdateChecker = updater.bridge
AutoUpdater = UpdaterService


class AutoUpdater:
    """Otomatik güncelleme yöneticisi"""
    
    def __init__(self, parent_widget=None):
        self.parent = parent_widget
        self.checker = UpdateChecker()
        self.checker.update_available.connect(self._on_update_available)
        self.checker.update_not_available.connect(self._on_no_update)
        self.checker.error_occurred.connect(self._on_error)
        
        # Son kontrol zamanı
        self.last_check_file = "last_update_check.json"
        self.check_interval = 7  # Gün
    
    def check_for_updates(self, show_dialog: bool = True):
        """Güncelleme kontrolü"""
        # Periyodik kontrol
        if not show_dialog:
            last_check = self._get_last_check()
            if last_check and (datetime.now() - last_check).days < self.check_interval:
                return
        
        self.show_progress = show_dialog
        
        if show_dialog:
            self.progress = QProgressDialog("Güncelleme kontrol ediliyor...", "İptal", 0, 0, self.parent)
            self.progress.setWindowModality(Qt.WindowModal)
            self.progress.show()
        
        self.checker.start()
    
    def _on_update_available(self, data: dict):
        """Güncelleme mevcut"""
        if self.show_progress:
            self.progress.close()
        
        latest_version = data.get('version', '')
        changelog = data.get('changelog', '')
        download_url = data.get('download_url', '')
        
        message = "Yeni sürüm mevcut!\n\n"
        message += f"Mevcut: {config.get('application.version')}\n"
        message += f"Yeni: {latest_version}\n\n"
        
        if changelog:
            message += f"Değişiklikler:\n{changelog}\n\n"
        
        reply = QMessageBox.question(
            self.parent, "Güncelleme Mevcut",
            message + "Güncellemek ister misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes and download_url:
            self.download_update(download_url)
    
    def _on_no_update(self):
        """Güncelleme yok"""
        if self.show_progress:
            self.progress.close()
            QMessageBox.information(self.parent, "Güncelleme",
                                   "Uygulama güncel! Son sürüm kullanılıyor.")
        
        self._save_last_check()
    
    def _on_error(self, error: str):
        """Hata durumu"""
        if self.show_progress:
            self.progress.close()
            QMessageBox.warning(self.parent, "Güncelleme Hatası",
                              f"Güncelleme kontrol edilemedi:\n{error}")
    
    def download_update(self, url: str):
        """Güncellemeyi indir"""
        try:
            response = requests.get(url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            progress = QProgressDialog("Güncelleme indiriliyor...", "İptal", 0, total_size, self.parent)
            progress.setWindowModality(Qt.WindowModal)
            
            downloaded = 0
            chunk_size = 8192
            
            with open("update_temp.exe", "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress.setValue(downloaded)
                        
                        if progress.wasCanceled():
                            f.close()
                            os.remove("update_temp.exe")
                            return
            
            progress.setValue(total_size)
            progress.close()
            
            # Güncellemeyi uygula
            self._apply_update()
            
        except Exception as e:
            QMessageBox.critical(self.parent, "Hata", f"Güncelleme indirilemedi:\n{str(e)}")
    
    def _apply_update(self):
        """Güncellemeyi uygula"""
        reply = QMessageBox.question(
            self.parent, "Güncelleme",
            "Uygulama kapanacak ve güncelleme başlayacak.\nDevam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Update script'i oluştur
            update_script = """
            @echo off
            timeout /t 2 /nobreak > nul
            echo Güncelleme başlatılıyor...
            move /y update_temp.exe "%~dp0Muhasebe.exe"
            echo Güncelleme tamamlandı!
            start "" "%~dp0Muhasebe.exe"
            del "%~f0"
            """
            
            with open("update.bat", "w") as f:
                f.write(update_script)
            
            # Uygulamayı kapat
            QApplication.quit()
            
            # Update script'ini çalıştır
            subprocess.Popen("update.bat", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    
    def _get_last_check(self) -> datetime:
        """Son kontrol zamanını al"""
        try:
            if os.path.exists(self.last_check_file):
                with open(self.last_check_file, 'r') as f:
                    data = json.load(f)
                    return datetime.fromisoformat(data.get('last_check', ''))
        except:
            pass
        return None
    
    def _save_last_check(self):
        """Son kontrol zamanını kaydet"""
        try:
            with open(self.last_check_file, 'w') as f:
                json.dump({'last_check': datetime.now().isoformat()}, f)
        except:
            pass