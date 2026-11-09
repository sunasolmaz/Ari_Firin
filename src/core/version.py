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
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
            return str(data.get("application", {}).get("version", "")).strip()
    except Exception:
        pass
    return ""


def _parse_v(v_str: str) -> tuple:
    """Sürüm stringini sayı demetine dönüştürür (örn: '1.0.4' -> (1, 0, 4))"""
    try:
        clean = v_str.strip().lstrip("v")
        parts = tuple(int(x) for x in clean.split(".") if x.isdigit())
        return parts if parts else (0, 0, 0)
    except Exception:
        return (0, 0, 0)


def _detect_version() -> str:
    """Sürümü tespit et - tüm geçerli kaynaklar arasından en güncel sürümü seçer"""
    base_dir = _get_base_dir()
    candidates = []

    # 1. version.txt (kök dizin veya _internal)
    for v_path in [base_dir / "version.txt", base_dir / "_internal" / "version.txt", Path.cwd() / "version.txt"]:
        if v_path.exists():
            try:
                v = v_path.read_text(encoding="utf-8").strip()
                if v:
                    candidates.append(v)
            except Exception:
                pass

    # 2. .env dosyası (exe'nin yanında veya çalışma dizininde)
    for env_path in [base_dir / ".env", Path.cwd() / ".env"]:
        ver = _read_from_env_file(env_path)
        if ver:
            candidates.append(ver)

    # 3. config.json (exe'nin yanında veya _internal içinde)
    for cfg_path in [base_dir / "config.json", Path.cwd() / "config.json", base_dir / "_internal" / "config.json"]:
        ver = _read_from_config_json(cfg_path)
        if ver:
            candidates.append(ver)

    # 4. Ortam değişkeni (en son çare)
    env_ver = os.environ.get("APP_VERSION", "").strip()
    if env_ver:
        candidates.append(env_ver)

    # 5. Hardcoded derleme taban sürümü (bu kod derlenirken v1.0.5 idi, asla bundan eski olamaz)
    HARDCODED_FALLBACK = "1.0.5"
    candidates.append(HARDCODED_FALLBACK)

    # Tüm bulunan sürümler arasından en yüksek geçerli olanı seç
    best_ver = max(candidates, key=_parse_v)
    return best_ver


# Modül import edildiğinde bir kez hesaplanır
APP_VERSION = _detect_version()


def get_version() -> str:
    """
    Sürümü dinamik olarak yeniden okur.
    .env dosyası çalışma sırasında değişirse bu fonksiyon güncel değeri döndürür.
    """
    return _detect_version()