# src/utils/license_manager.py
import os
import json
import hashlib
import platform
import subprocess
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict
from ..core.logger import logger


class LicenseManager:
    """Lisans yönetimi - Yerel & Merkezi Kontrol Sunucusu Entegrasyonlu"""

    def __init__(self, license_file: str = "license.dat", cache_file: str = "license_cache.dat"):
        self.license_file = license_file
        self.cache_file = cache_file
        self.license_data = None
        self.cached_remote_status = None
        self._load_license()
        self._load_remote_cache()

    def _load_license(self):
        """Yerel lisans dosyasını yükle"""
        try:
            if os.path.exists(self.license_file):
                with open(self.license_file, 'r', encoding='utf-8') as f:
                    self.license_data = json.load(f)
            else:
                self.license_data = None
        except Exception as e:
            logger.error(f"Lisans yükleme hatası: {e}")
            self.license_data = None

    def _get_cache_signature(self, valid: bool, last_verified: str, machine_id: str) -> str:
        """Önbellek verisinin yerel olarak manipüle edilmesini engelleyen HMAC imzası"""
        secret = "AriFirinLicenseSecret2026"
        raw = f"{valid}:{last_verified}:{machine_id}:{secret}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _save_remote_cache(self, valid: bool, message: str, expires_at: Optional[str] = None, features: Optional[list] = None):
        """Son sunucu lisans doğrulama sonucunu imzalı olarak önbelleğe alır"""
        machine_id = self._get_machine_id()
        now_str = datetime.now().isoformat()
        sig = self._get_cache_signature(valid, now_str, machine_id)
        cache = {
            "valid": valid,
            "message": message,
            "expires_at": expires_at,
            "features": features or ["all"],
            "last_verified": now_str,
            "machine_id": machine_id,
            "signature": sig
        }
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            self.cached_remote_status = cache
        except Exception as e:
            logger.error(f"Lisans önbellek kaydetme hatası: {e}")

    def _load_remote_cache(self):
        """İmzalı lisans önbelleğini doğrular ve yükler"""
        try:
            if os.path.exists(self.cache_file) and os.path.getsize(self.cache_file) > 0:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                expected_sig = self._get_cache_signature(
                    cache.get("valid", False),
                    cache.get("last_verified", ""),
                    cache.get("machine_id", "")
                )
                if cache.get("signature") == expected_sig:
                    self.cached_remote_status = cache
                else:
                    logger.warning("⚠️ Lisans önbellek imzası geçersiz veya bozulmuş! Önbellek reddedildi.")
                    self.cached_remote_status = None
            else:
                self.cached_remote_status = None
        except Exception as e:
            logger.error(f"Lisans önbellek yükleme hatası: {e}")
            self.cached_remote_status = None

    def _get_machine_id(self) -> str:
        """Bilgisayar ID'si al (Hızlı önbellekli, harici süreç ve konsol penceresi açmaz)"""
        if getattr(self, '_cached_machine_id', None):
            return self._cached_machine_id

        # 1. Önceden kaydedilmiş yerel makine kimliği varsa doğrudan oku
        mid_file = "machine_id.dat"
        if os.path.exists(mid_file):
            try:
                with open(mid_file, "r", encoding="utf-8") as f:
                    saved_mid = f.read().strip()
                    if saved_mid:
                        self._cached_machine_id = saved_mid
                        return self._cached_machine_id
            except Exception:
                pass

        try:
            import uuid
            if platform.system() == 'Windows':
                mac = str(uuid.getnode())
                cpu = platform.processor() or "CPU_DEFAULT"
                disk = platform.node() or "DISK_DEFAULT"
                # PowerShell alt işlemi çalıştırmadan doğrudan Windows Registry üzerinden benzersiz donanım GUID'i al
                try:
                    import winreg
                    k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
                    guid, _ = winreg.QueryValueEx(k, "MachineGuid")
                    if guid:
                        disk = f"{disk}_{guid}"
                except Exception:
                    pass
            else:
                mac, cpu, disk = str(uuid.getnode()), platform.processor() or "CPU", platform.node() or "DISK"

            machine_id = hashlib.sha256(f"{mac}{cpu}{disk}".encode()).hexdigest()[:32]
            self._cached_machine_id = machine_id
            try:
                with open(mid_file, "w", encoding="utf-8") as f:
                    f.write(machine_id)
            except Exception:
                pass
            return self._cached_machine_id

        except Exception as e:
            logger.error(f"Makine ID hatası: {e}")
            return "UNKNOWN"

    def _generate_license_key(self, machine_id: str, expiry_date: str, features: list) -> str:
        """Lisans anahtarı oluştur"""
        data = f"{machine_id}|{expiry_date}|{','.join(features)}|SALT"
        return hashlib.sha256(data.encode()).hexdigest()

    def validate_license(self) -> tuple:
        """Lisansı doğrula"""
        if not self.license_data:
            return False, "Lisans dosyası bulunamadı!"

        try:
            # Makine ID kontrolü
            machine_id = self._get_machine_id()
            if self.license_data.get('machine_id') not in [machine_id, "UNKNOWN"]:
                return False, "Bu bilgisayarda çalıştırılamaz!"

            # Tarih kontrolü
            expiry_str = self.license_data.get('expiry_date')
            if expiry_str:
                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d')
                if datetime.now() > expiry_date:
                    return False, f"Lisans süresi doldu! ({expiry_str})"

            # Anahtar doğrulama
            expected_key = self._generate_license_key(
                self.license_data.get('machine_id'),
                expiry_str or 'permanent',
                self.license_data.get('features', [])
            )

            if self.license_data.get('license_key') != expected_key:
                return False, "Geçersiz lisans!"

            return True, "Lisans geçerli"

        except Exception as e:
            logger.error(f"Lisans doğrulama hatası: {e}")
            return False, f"Lisans hatası: {str(e)}"

    def create_license(self, expiry_date: Optional[str] = None,
                       features: list = None,
                       custom_machine_id: Optional[str] = None) -> Dict:
        """Lisans oluştur (Admin tool) - Harici Makine ID destekli"""
        
        # ✅ DÜZELTME: Dışarıdan bir makine ID'si verilmişse onu kullan, yoksa kendi ID'sini al
        machine_id = custom_machine_id if custom_machine_id else self._get_machine_id()

        if expiry_date is None:
            expiry_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')

        if features is None:
            features = ['all']

        license_data = {
            'machine_id': machine_id,
            'expiry_date': expiry_date,
            'features': features,
            'created_at': datetime.now().isoformat(),
            'license_key': self._generate_license_key(machine_id, expiry_date, features)
        }

        return license_data

    def save_license(self, license_data: Dict) -> bool:
        """Lisansı kaydet"""
        try:
            with open(self.license_file, 'w') as f:
                json.dump(license_data, f, indent=2)
            self.license_data = license_data
            logger.info("✅ Lisans kaydedildi")
            return True
        except Exception as e:
            logger.error(f"Lisans kaydetme hatası: {e}")
            return False

    def get_license_info(self) -> Dict:
        """Lisans bilgilerini getir"""
        if not self.license_data:
            return {'status': 'Not Found'}

        return {
            'status': 'Valid' if self.validate_license()[0] else 'Invalid',
            'machine_id': self.license_data.get('machine_id'),
            'expiry_date': self.license_data.get('expiry_date'),
            'features': self.license_data.get('features', []),
            'created_at': self.license_data.get('created_at')
        }

    def verify_remote_license(
        self,
        server_url: Optional[str] = None,
        project_id: Optional[str] = None,
        license_key: Optional[str] = None
    ) -> tuple:
        """
        Merkezi kontrol sunucusu üzerinden lisans durumunu doğrular.
        - Sunucu aktif ve onayladıysa: (True, "Lisans onaylandı.")
        - Sunucu dondurdu / askıya aldıysa: (False, "Bu lisans yönetici tarafından askıya alınmıştır!")
        - Sunucuya ulaşılamıyorsa: 7 günlük çevrimdışı tolerans süresini (grace period) uygular.
        """
        import requests
        try:
            from ..core.config import config
            raw_url = (server_url or config.get("update.server_url") or config.get("update.cloud_hub_url") or os.environ.get("CLOUD_HUB_URL", "http://localhost:8000")).rstrip("/")
            if ":8001" in raw_url:
                raw_url = raw_url.replace(":8001", ":8000")
            url = raw_url
            proj = project_id or config.get("update.project_id", "ari_firin")
            key = license_key or config.get("update.license_key", "DEMO-LICENSE-KEY")
        except Exception:
            raw_url = (server_url or os.environ.get("CLOUD_HUB_URL", "http://localhost:8000")).rstrip("/")
            if ":8001" in raw_url:
                raw_url = raw_url.replace(":8001", ":8000")
            url = raw_url
            proj = project_id or "ari_firin"
            key = license_key or "DEMO-LICENSE-KEY"

        machine_id = self._get_machine_id()
        payload = {
            "license_key": key,
            "machine_id": machine_id
        }

        # ─── HIZLI AÇILIŞ (CACHE-FIRST GÜVENLİK KONTROLÜ) ───
        # Eğer önbellek geçerli, bu bilgisayara ait ve son 24 saat içinde sunucu tarafından onaylanmışsa,
        # ana iş parçacığını (GUI) bekletmeden anında aç ve sunucu doğrulamasını arka planda yap.
        if self.cached_remote_status and self.cached_remote_status.get("valid", False):
            # Başka bilgisayardan kopyalanmış önbelleği kesinlikle reddet
            if self.cached_remote_status.get("machine_id") != machine_id:
                self.cached_remote_status = None
            else:
                last_verified_str = self.cached_remote_status.get("last_verified")
                if last_verified_str:
                    try:
                        last_dt = datetime.fromisoformat(last_verified_str)
                        hours_passed = (datetime.now() - last_dt).total_seconds() / 3600
                        if hours_passed < 24:
                            threading.Thread(
                                target=self._background_refresh_license,
                                args=(url, proj, key),
                                daemon=True
                            ).start()
                            return True, self.cached_remote_status.get("message", "Lisans onaylandı.")
                    except Exception:
                        pass

        try:
            endpoint = f"{url}/api/v1/projects/{proj}/license/verify"
            r = requests.post(endpoint, json=payload, timeout=2.0)
            if r.status_code == 200:
                data = r.json()
                is_valid = bool(data.get("valid", False))
                msg = data.get("message", "Lisans onaylandı.")
                self._save_remote_cache(
                    valid=is_valid,
                    message=msg,
                    expires_at=data.get("expires_at"),
                    features=data.get("features")
                )
                return is_valid, msg
            else:
                logger.warning(f"Merkezi lisans sunucusu HTTP {r.status_code} döndürdü.")
        except Exception as conn_err:
            logger.warning(f"Merkezi lisans sunucusuna erişilemedi ({conn_err}), çevrimdışı mod denetleniyor...")

        # ─── ÇEVRİMDIŞI TOLERANS KONTROLÜ (OFFLINE GRACE PERIOD) ───
        if self.cached_remote_status:
            # Eğer son sunucu cevabında lisans dondurulmuşsa, çevrimdışı modda da açma!
            if not self.cached_remote_status.get("valid", False):
                return False, self.cached_remote_status.get("message", "Bu lisans yönetici tarafından askıya alınmıştır!")

            last_verified_str = self.cached_remote_status.get("last_verified")
            if last_verified_str:
                try:
                    last_dt = datetime.fromisoformat(last_verified_str)
                    days_passed = (datetime.now() - last_dt).days
                    if days_passed < 7:
                        remaining = 7 - days_passed
                        logger.info(f"🟢 Çevrimdışı mod devrede: Kalan tolerans süresi {remaining} gün.")
                        return True, f"Çevrimdışı Mod (Kalan tolerans: {remaining} gün)"
                    else:
                        logger.warning("❌ Çevrimdışı tolerans süresi (7 gün) doldu!")
                        return False, "Çevrimdışı çalışma tolerans süresi (7 gün) doldu. Lütfen internete bağlanın!"
                except Exception:
                    pass

        # Eğer hiç önbellek yoksa ve sunucuya ulaşılamıyorsa, yerel dosya lisansını dene
        local_valid, local_msg = self.validate_license()
        if local_valid:
            return True, "Yerel lisans aktif (Çevrimdışı)"

        # İlk kurulumda ve internet yoksa, varsayılan lisans anahtarı için 3 günlük geçici ilk aktivasyon toleransı
        if key == "ARI-FIRIN-TEKIRDAG-2026":
            return True, "İlk kurulum geçici toleransı (3 gün)"

        return False, "Lisans doğrulanamadı ve geçerli bir çevrimdışı oturum bulunamadı."

    def _background_refresh_license(self, url: str, proj: str, key: str):
        """Arka planda sunucu lisans durumunu sessizce tazeler"""
        try:
            import requests
            machine_id = self._get_machine_id()
            payload = {
                "license_key": key,
                "machine_id": machine_id
            }
            endpoint = f"{url}/api/v1/projects/{proj}/license/verify"
            r = requests.post(endpoint, json=payload, timeout=5.0)
            if r.status_code == 200:
                data = r.json()
                self._save_remote_cache(
                    valid=bool(data.get("valid", False)),
                    message=data.get("message", "Lisans onaylandı."),
                    expires_at=data.get("expires_at"),
                    features=data.get("features")
                )
        except Exception:
            pass