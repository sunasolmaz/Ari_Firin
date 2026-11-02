#!/usr/bin/env python3
# scripts/build_executables.py
"""
Arı Fırın ve UniversalAdmin Otomatik PyInstaller Derleme Aracı
Tüm bağımlılıkları, Qt eklentilerini ve PostgreSQL sürücülerini
bağımsız çalışan Windows .exe dosyaları haline getirir.
"""

import os
import sys
import shutil
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# Windows cp1254 UnicodeEncodeError koruması
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"


def check_environment():
    """Derleme öncesi ortam ve bağımlılık kontrolleri"""
    print("=" * 60)
    print("🔍 DERLEME ÖNCESİ ORTAM KONTROLÜ")
    print("=" * 60)
    print(f"🐍 Python Sürümü: {sys.version.split()[0]}")
    print(f"💻 Platform: {sys.platform}")
    print(f"📁 Proje Dizini: {PROJECT_ROOT}")

    # PyInstaller kontrolü
    try:
        import PyInstaller
        print(f"✅ PyInstaller Kurulu: v{PyInstaller.__version__}")
    except ImportError:
        print("❌ HATA: PyInstaller bulunamadı! 'pip install pyinstaller' çalıştırın.")
        return False

    # Spec dosyaları kontrolü
    ari_spec = PROJECT_ROOT / "ari_firin.spec"
    admin_spec = PROJECT_ROOT / "universal_admin.spec"

    if not ari_spec.exists():
        print(f"❌ HATA: {ari_spec} bulunamadı!")
        return False
    if not admin_spec.exists():
        print(f"❌ HATA: {admin_spec} bulunamadı!")
        return False

    print(f"✅ Spec Dosyaları Mevcut: {ari_spec.name}, {admin_spec.name}")

    # Ana giriş dosyaları kontrolü
    main_py = PROJECT_ROOT / "main.py"
    admin_py = PROJECT_ROOT / "UniversalAdmin" / "universal_admin.py"
    if not main_py.exists():
        print(f"❌ HATA: {main_py} bulunamadı!")
        return False
    if not admin_py.exists():
        print(f"❌ HATA: {admin_py} bulunamadı!")
        return False

    print("✅ Tüm kaynak dosyaları ve spec tanımları eksiksiz.")
    print("=" * 60)
    return True


def verify_pe_executable(exe_path: Path) -> bool:
    """Üretilen dosyanın geçerli bir Windows PE çalıştırılabilir dosyası olduğunu doğrular"""
    if not exe_path.exists():
        print(f"❌ HATA: {exe_path} bulunamadı!")
        return False

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"📦 Dosya Boyutu: {size_mb:.2f} MB")

    if size_mb < 5.0:
        print("❌ UYARI: Dosya boyutu beklenenden küçük (< 5MB), eksik paketleme olabilir!")
        return False

    # Windows PE 'MZ' başlığı kontrolü
    with open(exe_path, "rb") as f:
        magic = f.read(2)
        if magic != b"MZ":
            print(f"❌ HATA: Dosya geçerli bir Windows PE imzası ('MZ') taşımıyor: {magic}")
            return False

    print("✅ Windows PE ('MZ') imzası ve dosya boyutu doğrulandı.")
    return True


def build_target(spec_name: str, output_name: str):
    """Belirtilen spec dosyası ile PyInstaller derlemesini çalıştırır"""
    spec_path = PROJECT_ROOT / spec_name
    print(f"\n🔨 DERLEME BAŞLATILIYOR: {spec_name} -> {output_name}.exe")
    start_time = datetime.now()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(spec_path)
    ]

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    duration = (datetime.now() - start_time).total_seconds()

    if result.returncode != 0:
        print(f"❌ {spec_name} derleme hatası (Çıkış kodu: {result.returncode})!")
        return False

    print(f"⏱️ Derleme Tamamlandı ({duration:.1f} saniye).")

    # Çıktıyı doğrula (onedir veya onefile)
    target_exe = DIST_DIR / output_name / f"{output_name}.exe"
    if not target_exe.exists():
        target_exe = DIST_DIR / f"{output_name}.exe"
    is_valid = verify_pe_executable(target_exe)
    if is_valid:
        print(f"🎉 BAŞARILI: {target_exe} bağımsız olarak çalışmaya hazır!")
    return is_valid


def clean_artifacts():
    """Önceki derleme artıklarını temizler"""
    print("🧹 Derleme dizinleri temizleniyor...")
    for d in [BUILD_DIR, DIST_DIR]:
        if d.exists():
            try:
                shutil.rmtree(d)
                print(f"   Silindi: {d.name}/")
            except Exception as e:
                print(f"   Temizleme uyarısı ({d.name}): {e}")


def main():
    parser = argparse.ArgumentParser(description="Arı Fırın ve UniversalAdmin PyInstaller Derleme Aracı")
    parser.add_argument("--check-only", action="store_true", help="Yalnızca ortam ve gereksinimleri denetle")
    parser.add_argument("--clean", action="store_true", help="Önceki derleme çıktılarını temizle")
    parser.add_argument("--build-ari-firin", action="store_true", help="Yalnızca Arı Fırın'ı derle")
    parser.add_argument("--build-admin", action="store_true", help="Yalnızca UniversalAdmin'i derle")
    parser.add_argument("--all", action="store_true", help="Tüm uygulamaları derle")

    args = parser.parse_args()

    if not check_environment():
        sys.exit(1)

    if args.check_only:
        print("✅ Ortam kontrolü başarılı. Derlemeye hazır.")
        sys.exit(0)

    if args.clean:
        clean_artifacts()

    # Varsayılan olarak eğer parametre verilmediyse ikisini birden derle
    build_all = args.all or (not args.build_ari_firin and not args.build_admin)

    success = True
    if build_all or args.build_ari_firin:
        ok = build_target("ari_firin.spec", "AriFirin")
        success = success and ok

    if build_all or args.build_admin:
        ok = build_target("universal_admin.spec", "UniversalAdmin")
        success = success and ok

    if success:
        print("\n" + "=" * 60)
        print("🏆 TÜM ÇALIŞTIRILABİLİR DOSYALAR (.EXE) BAŞARIYLA ÜRETİLDİ!")
        print(f"📁 Çıktı Dizini: {DIST_DIR}")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n❌ Bazı hedeflerin derlenmesinde hata oluştu!")
        sys.exit(1)


if __name__ == "__main__":
    main()
