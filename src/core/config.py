# src/core/config.py
"""
Konfigürasyon Yönetimi
"""

import os
import sys
import json
from pathlib import Path


class Config:
    """Uygulama konfigürasyon yönetimi"""
    
    _instance = None
    _config = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Konfigürasyon dosyasını yükle"""
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).resolve().parent
        else:
            base_dir = Path(__file__).resolve().parent.parent.parent
            
        config_path = base_dir / "config.json"
        if not config_path.exists():
            config_path = Path("config.json")
        self._config_path = config_path
        
        default_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "database": "accounting_db",
                "user": "postgres",
                "password": "postgres123"
            },
            "application": {
                "name": "Muhasebe Uygulaması",
                "version": "1.0.0",
                "theme": "professional",
                "language": "tr",
                "auto_backup": True,
                "backup_interval": 7,
                "backup_dir": "backups",
                "demo_mode": False
            },
            # ✅ DÜZELTİLDİ: Tüm anahtarlar burada, enabled=True
            "update": {
                "enabled": True,
                "server_url": "http://100.125.79.19:8000",
                "url": "http://100.125.79.19:8001/version.txt",
                "download_url": "http://100.125.79.19:8001/AriFirin_v1.0.1.zip",
                "project_id": "ari_firin",
                "license_key": "ARI-FIRIN-TEKIRDAG-2026",
                "check_interval": 7
            },
            "performance": {
                "cache_size": 100,
                "page_size": 50,
                "connection_pool": 5
            },
            "archive": {
                "days_to_archive": 730,
                "auto_archive": True,
                "archive_path": "archive"
            },
            "logging": {
                "level": "INFO",
                "file": "logs/muhasebe.log",
                "max_size_mb": 10,
                "backup_count": 5
            },
            "error_report": {
                "enabled": False,
                "url": ""
            },
            "email": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "sender_email": "sunasolmaz00@gmail.com",
                "sender_password": "",
                "use_tls": True,
                "use_ssl": False
            }
        }
        
        # ✅ DÜZELTİLDİ: "config varsa üzerine yazma" mantığı
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8-sig') as f:
                    loaded_config = json.load(f)
                    # Deep merge: loaded önceliklidir
                    self._config = self._merge_configs(default_config, loaded_config)
                # ⚠️ KRİTİK: Burada save() ÇAĞRILMIYOR!
                # Kullanıcının manuel değişiklikleri korunur.
            except Exception as e:
                print(f"⚠️ Config okuma hatası: {e}, varsayılan kullanılıyor")
                self._config = default_config
                self.save()
        else:
            self._config = default_config
            self.save()
            print(f"ℹ️ Yeni config.json oluşturuldu: {config_path}")

        # Ortam değişkenleri önceliği (Security & 12-Factor App)
        self._apply_env_overrides()
    
    def _apply_env_overrides(self):
        """Ortam değişkenlerini config üzerine uygula"""
        if "database" not in self._config:
            self._config["database"] = {}
        env_db_map = {
            "DB_HOST": ("host", str),
            "DB_PORT": ("port", int),
            "DB_NAME": ("database", str),
            "DB_DATABASE": ("database", str),
            "DB_USER": ("user", str),
            "DB_PASSWORD": ("password", str),
            "DB_SSLMODE": ("sslmode", str),
        }
        for env_key, (cfg_key, cast) in env_db_map.items():
            if os.environ.get(env_key):
                try:
                    self._config["database"][cfg_key] = cast(os.environ[env_key])
                except (ValueError, TypeError):
                    pass

        if "email" not in self._config:
            self._config["email"] = {}
        if os.environ.get("SMTP_SERVER"):
            self._config["email"]["smtp_server"] = os.environ["SMTP_SERVER"]
        if os.environ.get("SMTP_PORT"):
            try:
                self._config["email"]["smtp_port"] = int(os.environ["SMTP_PORT"])
            except ValueError:
                pass
        if os.environ.get("SMTP_USER") or os.environ.get("SENDER_EMAIL"):
            self._config["email"]["sender_email"] = os.environ.get("SMTP_USER") or os.environ.get("SENDER_EMAIL")
        if os.environ.get("SMTP_PASSWORD") or os.environ.get("SENDER_PASSWORD"):
            self._config["email"]["sender_password"] = os.environ.get("SMTP_PASSWORD") or os.environ.get("SENDER_PASSWORD")

        # Update ortam değişkenleri
        if "update" not in self._config:
            self._config["update"] = {}
        if os.environ.get("UPDATE_SERVER_URL"):
            self._config["update"]["server_url"] = os.environ["UPDATE_SERVER_URL"]
        if os.environ.get("UPDATE_VERSION_URL"):
            self._config["update"]["url"] = os.environ["UPDATE_VERSION_URL"]
        if os.environ.get("UPDATE_DOWNLOAD_URL"):
            self._config["update"]["download_url"] = os.environ["UPDATE_DOWNLOAD_URL"]
    
    def _merge_configs(self, default: dict, loaded: dict) -> dict:
        """İki config'i birleştir (loaded önceliklidir)"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
    
    def save(self):
        """Konfigürasyonu kaydet (atomik yazma)"""
        try:
            target_path = getattr(self, '_config_path', Path("config.json"))
            tmp_path = target_path.with_suffix('.json.tmp')
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            os.replace(tmp_path, target_path)
        except Exception as e:
            print(f"⚠️ Config kaydetme hatası: {e}")
    
    def get(self, key, default=None):
        """Konfigürasyon değerini al - Ortam değişkenleri önceliklidir"""
        env_map = {
            "database.host": "DB_HOST",
            "database.port": "DB_PORT",
            "database.database": "DB_NAME",
            "database.user": "DB_USER",
            "database.password": "DB_PASSWORD",
            "database.sslmode": "DB_SSLMODE",
            "email.smtp_server": "SMTP_SERVER",
            "email.sender_email": "SMTP_USER",
            "email.sender_password": "SMTP_PASSWORD",
            "update.server_url": "UPDATE_SERVER_URL",
            "update.url": "UPDATE_VERSION_URL",
            "update.download_url": "UPDATE_DOWNLOAD_URL",
        }
        if key in env_map and os.environ.get(env_map[key]):
            val = os.environ.get(env_map[key])
            if key == "database.port":
                try:
                    return int(val)
                except ValueError:
                    pass
            return val

        if key == "database":
            db_copy = dict(self._config.get("database", {}))
            for env_key, cfg_key in [("DB_HOST", "host"), ("DB_PORT", "port"),
                                      ("DB_NAME", "database"), ("DB_DATABASE", "database"),
                                      ("DB_USER", "user"), ("DB_PASSWORD", "password"),
                                      ("DB_SSLMODE", "sslmode")]:
                if os.environ.get(env_key):
                    try:
                        db_copy[cfg_key] = int(os.environ[env_key]) if cfg_key == "port" else os.environ[env_key]
                    except ValueError:
                        pass
            return db_copy

        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        
        return value if value is not None else default
    
    def set(self, key, value):
        """Konfigürasyon değerini ata (diske YAZMAZ, save() ayrı çağrılmalı)"""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        # ✅ save() artık otomatik çağrılmıyor. Çağıran taraf save() demeli.


# Global config instance
config = Config()