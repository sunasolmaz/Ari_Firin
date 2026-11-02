# src/utils/backup_scheduler.py
import os
import time
import threading
from datetime import datetime, timedelta
from typing import Optional
from ..core.database import db
from ..core.logger import logger
from ..core.config import config

class BackupScheduler:
    """Otomatik yedekleme planlayıcısı"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.backup_interval = config.get('application.backup_interval', 7)
        self.backup_dir = config.get('application.backup_dir', 'backups')
        
        # Backup dizinini oluştur
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
    
    def start(self):
        """Yedekleme servisini başlat"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("✅ Yedekleme servisi başlatıldı")
    
    def stop(self):
        """Yedekleme servisini durdur"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Yedekleme servisi durduruldu")
    
    def _run(self):
        """Ana döngü"""
        while self.running:
            try:
                self._check_and_backup()
                time.sleep(3600)  # Her saat kontrol et
            except Exception as e:
                logger.error(f"Yedekleme hatası: {e}")
                time.sleep(3600)
    
    def _check_and_backup(self):
        """Yedekleme kontrolü"""
        # Son yedekleme zamanını kontrol et
        last_backup = self._get_last_backup_time()
        
        if not last_backup:
            self._perform_backup()
            return
        
        days_since = (datetime.now() - last_backup).days
        
        if days_since >= self.backup_interval:
            logger.info(f"Otomatik yedekleme başlatılıyor... (Son: {days_since} gün önce)")
            self._perform_backup()
    
    def _perform_backup(self):
        """Yedekleme yap"""
        try:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            db.backup_database(backup_path)
            encrypted_path = self._encrypt_backup(backup_path) or backup_path
            
            # Bulut sunucusuna yedek yükle
            try:
                self.upload_to_cloud(encrypted_path)
            except Exception as e:
                logger.error(f"Bulut yedekleme çağrı hatası: {e}")
            
            # Eski yedekleri temizle (30 günden eski)
            self._clean_old_backups()
            
            # Son yedekleme zamanını kaydet
            self._save_backup_time()
            
        except Exception as e:
            logger.error(f"Otomatik yedekleme hatası: {e}")
    
    def _encrypt_backup(self, sql_path: str) -> Optional[str]:
        """SQL yedeğini sıkıştırır ve korumalı zip oluşturur"""
        import zipfile
        try:
            if not os.path.exists(sql_path):
                return None
            
            zip_path = sql_path.replace('.sql', '.zip')
            backup_secret = config.get('security.backup_secret', 'AriFirinSecureBackupKey2026').encode('utf-8')
            
            with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                zf.setpassword(backup_secret)
                zf.write(sql_path, arcname=os.path.basename(sql_path))
            
            if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0:
                os.remove(sql_path)
                logger.info(f"🔒 Şifreli yedek oluşturuldu: {zip_path}")
                return zip_path
            return sql_path
        except Exception as e:
            logger.error(f"Yedek şifreleme hatası: {e}")
            return sql_path
    
    def _get_last_backup_time(self) -> Optional[datetime]:
        """Son yedekleme zamanını al"""
        try:
            backup_file = os.path.join(self.backup_dir, "last_backup.txt")
            if os.path.exists(backup_file):
                with open(backup_file, 'r') as f:
                    timestamp = f.read().strip()
                    return datetime.fromisoformat(timestamp)
        except:
            pass
        return None
    
    def _save_backup_time(self):
        """Son yedekleme zamanını kaydet"""
        try:
            backup_file = os.path.join(self.backup_dir, "last_backup.txt")
            with open(backup_file, 'w') as f:
                f.write(datetime.now().isoformat())
        except Exception as e:
            logger.error(f"Yedekleme zamanı kaydetme hatası: {e}")
    
    def _clean_old_backups(self, days: int = 30):
        """Eski yedekleri temizle"""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            
            for filename in os.listdir(self.backup_dir):
                if (filename.startswith("backup_") or filename.startswith("manual_")) and (filename.endswith(".sql") or filename.endswith(".zip")):
                    file_path = os.path.join(self.backup_dir, filename)
                    mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if mtime < cutoff:
                        os.remove(file_path)
                        logger.debug(f"Eski yedek silindi: {filename}")
                        
        except Exception as e:
            logger.error(f"Yedek temizleme hatası: {e}")
    
    def manual_backup(self) -> Optional[str]:
        """Manuel yedekleme"""
        try:
            backup_name = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            db.backup_database(backup_path)
            encrypted_path = self._encrypt_backup(backup_path) or backup_path
            logger.info(f"✅ Manuel yedekleme tamamlandı: {encrypted_path}")
            
            # Bulut sunucusuna yedek yükle
            try:
                self.upload_to_cloud(encrypted_path)
            except Exception as e:
                logger.error(f"Bulut yedekleme çağrı hatası: {e}")
            
            return encrypted_path
            
        except Exception as e:
            logger.error(f"Manuel yedekleme hatası: {e}")
            return None

    def upload_to_cloud(self, backup_path: str) -> bool:
        """Veritabanı yedeğini merkezi kontrol sunucusuna yükler"""
        import requests
        try:
            if not backup_path or not os.path.exists(backup_path):
                logger.warning(f"Bulut yedekleme için dosya bulunamadı: {backup_path}")
                return False

            server_url = (config.get("update.server_url") or config.get("update.cloud_hub_url") or os.environ.get("CLOUD_HUB_URL", "http://100.125.79.19:8000")).rstrip("/")
            if ":8001" in server_url:
                server_url = server_url.replace(":8001", ":8000")
            project_id = config.get("update.project_id", "ari_firin")
            client_name = config.get("update.client_name", "Tekirdağ Müşterisi")
            license_key = config.get("update.license_key", "ARI-FIRIN-TEKIRDAG-2026")

            endpoint = f"{server_url}/api/v1/projects/{project_id}/backups/upload"
            filename = os.path.basename(backup_path)

            with open(backup_path, "rb") as f:
                data = {
                    "client_name": client_name,
                    "license_key": license_key
                }
                files = {
                    "backup_file": (filename, f, "application/octet-stream")
                }
                r = requests.post(endpoint, data=data, files=files, timeout=60)

            if r.status_code == 200:
                resp_json = r.json()
                logger.info(f"☁️ Bulut yedekleme başarılı: {resp_json.get('filename')} ({resp_json.get('size')} bayt) -> {server_url}")
                return True
            else:
                logger.warning(f"⚠️ Bulut yedekleme başarısız: HTTP {r.status_code} - {r.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Bulut yedekleme bağlantı hatası: {e}")
            return False
    
    def get_backup_list(self) -> list:
        """Yedek listesini getir"""
        backups = []
        try:
            for filename in os.listdir(self.backup_dir):
                if filename.endswith(".sql") or filename.endswith(".zip"):
                    file_path = os.path.join(self.backup_dir, filename)
                    backups.append({
                        'name': filename,
                        'path': file_path,
                        'size': os.path.getsize(file_path),
                        'date': datetime.fromtimestamp(os.path.getmtime(file_path))
                    })
            return sorted(backups, key=lambda x: x['date'], reverse=True)
        except Exception as e:
            logger.error(f"Yedek listesi hatası: {e}")
            return []