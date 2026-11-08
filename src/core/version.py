# src/core/version.py
"""
Uygulama sürüm bilgisi.

Öncelik sırası:
1. .env dosyasındaki APP_VERSION (exe'nin yanında)
2. config.json içindeki application.version
3. Hardcoded default "1.0.0"

Bu dosya, uygulama .exe olarak çalışırken CWD'nin neresi olduğundan
bağımsız olarak doğru .env dosyasını bulacak şekilde tasarlandı.
"""

import os
import sys
import json
from pathlib import Path


def _get_base_dir() -> Path:
    """
    Uygulamanın kök dizinini döndürür.
    - Frozen (.exe): .exe'nin bulunduğu klasör
    - Geliştirme: proje kökü
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    # src/core/version.py -> proje kökü
    return Path(__file__).resolve().parent.parent.parent


def _read_from_env_file(env_path: Path) -> str:
    """Belirtilen .env dosyasından APP_VERSION'ı oku"""
    if not env_path.exists():
        return ""
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('APP_VERSION'):
                    # APP_VERSION=1.0.0 veya APP_VERSION="1.0.0"
                    _, _, value = line.partition('=')
                    value = value.strip().strip('"').strip("'")
                    return value
    except Exception:
        pass
    return ""


def _read_from_config_json(config_path: Path) -> str:
    """config.json içindeki application.version değerini oku"""
    if not config_path.exists():
        return ""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return str(data.get("application", {}).get("version", "")).strip()
    except Exception:
        pass
    return ""


def _detect_version() -> str:
    """Sürümü tespit et - öncelik sırasına göre"""
    base_dir = _get_base_dir()

    # 0. Derlenmiş (.exe / frozen) ise, paketle gelen _internal/config.json resmi sürümdür
    if getattr(sys, 'frozen', False):
        internal_cfg = base_dir / "_internal" / "config.json"
        if internal_cfg.exists():
            ver = _read_from_config_json(internal_cfg)
            if ver:
                return ver

    # 1. .env dosyası (exe'nin yanında)
    env_candidates = [
        base_dir / ".env",
        Path.cwd() / ".env",
    ]
    for env_path in env_candidates:
        ver = _read_from_env_file(env_path)
        if ver:
            return ver

    # 2. config.json (exe'nin yanında)
    config_candidates = [
        base_dir / "config.json",
        Path.cwd() / "config.json",
    ]
    for cfg_path in config_candidates:
        ver = _read_from_config_json(cfg_path)
        if ver:
            return ver

    # 3. Ortam değişkeni (en son çare)
    env_ver = os.environ.get("APP_VERSION", "").strip()
    if env_ver:
        return env_ver

    # 4. Hardcoded fallback
    return "1.0.4"


# Modül import edildiğinde bir kez hesaplanır
APP_VERSION = _detect_version()


def get_version() -> str:
    """
    Sürümü dinamik olarak yeniden okur.
    .env dosyası çalışma sırasında değişirse bu fonksiyon güncel değeri döndürür.
    """
    return _detect_version()