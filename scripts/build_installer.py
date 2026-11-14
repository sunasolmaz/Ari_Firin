#!/usr/bin/env python3
# scripts/build_installer.py
"""
Arı Fırın & Universal Admin Kurulum Paketi & Dağıtım Derleyicisi.
Inno Setup (varsa) ve İstemci/Yönetici Taşınabilir Dağıtım Paketleri
(ZIP + Otomatik İkonlu Kısayol Kurucuları) üretir.
"""

import os
import sys
import shutil
import zipfile
import subprocess
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
ARI_FIRIN_EXE = DIST_DIR / "AriFirin.exe"
UNIVERSAL_ADMIN_EXE = DIST_DIR / "UniversalAdmin.exe"
CONFIG_JSON = PROJECT_ROOT / "config.json"
RESOURCES_DIR = PROJECT_ROOT / "resources"
SETUP_ISS = PROJECT_ROOT / "setup.iss"

ADMIN_ROOT = PROJECT_ROOT / "UniversalAdmin"
ADMIN_SECURITY_JSON = ADMIN_ROOT / "admin_security.json"
ADMIN_APPS_REGISTRY_JSON = ADMIN_ROOT / "apps_registry.json"
ADMIN_RESOURCES_DIR = ADMIN_ROOT / "resources"


def check_prerequisites() -> bool:
    """Dağıtım paketleri için gerekli temel dosyaları kontrol eder."""
    print("=" * 60)
    print("🔍 KURULUM VE DAĞITIM PAKETİ ÖN GEREKSİNİM KONTROLÜ")
    print("=" * 60)

    # 1. İkonları kontrol et / yoksa üret
    ari_icon = RESOURCES_DIR / "icons" / "app.ico"
    if not ari_icon.exists():
        print("ℹ️ İkon dosyası eksik, otomatik üretiliyor...")
        try:
            from scripts.generate_app_icons import generate_all_icons
            generate_all_icons()
        except Exception as e:
            print(f"⚠️ İkon üretimi sırasında uyarı: {e}")

    # 2. AriFirin.exe / AriFirin klasörü kontrolü
    ari_onedir = DIST_DIR / "AriFirin"
    ari_exe = (ari_onedir / "AriFirin.exe") if (ari_onedir / "AriFirin.exe").exists() else ARI_FIRIN_EXE
    if not ari_exe.exists():
        print(f"❌ HATA: AriFirin.exe bulunamadı!")
        print("   Lütfen önce 'python scripts/build_executables.py --build-ari-firin' çalıştırın.")
        return False
    exe_size_mb = ari_exe.stat().st_size / (1024 * 1024)
    print(f"✅ AriFirin.exe Mevcut ({exe_size_mb:.2f} MB)")

    # 3. UniversalAdmin.exe kontrolü
    if not UNIVERSAL_ADMIN_EXE.exists():
        print(f"⚠️ UYARI: {UNIVERSAL_ADMIN_EXE} bulunamadı! (Yalnızca Arı Fırın paketi üretilebilir)")
    else:
        admin_size_mb = UNIVERSAL_ADMIN_EXE.stat().st_size / (1024 * 1024)
        print(f"✅ UniversalAdmin.exe Mevcut ({admin_size_mb:.2f} MB)")

    # 4. config.json ve setup.iss kontrolü
    if not CONFIG_JSON.exists():
        print(f"❌ HATA: {CONFIG_JSON} bulunamadı!")
        return False
    print(f"✅ config.json Mevcut")

    if not SETUP_ISS.exists():
        print(f"❌ HATA: {SETUP_ISS} bulunamadı!")
        return False
    print(f"✅ setup.iss Inno Setup betiği Mevcut")

    return True


def try_compile_inno_setup() -> bool:
    """Eğer sistemde Inno Setup derleyicisi (iscc) varsa setup.exe üretir."""
    print("\n📦 Inno Setup Derleme Girişimi...")
    iscc_path = shutil.which("iscc")
    if not iscc_path:
        candidate_paths = [
            Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
            Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
            Path(r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"),
            Path(r"C:\Program Files\Inno Setup 5\ISCC.exe"),
        ]
        for p in candidate_paths:
            if p.exists():
                iscc_path = str(p)
                break

    if not iscc_path:
        print("ℹ️ Inno Setup (ISCC.exe) sistemde bulunamadı.")
        print("   (setup.iss dosyası hazır; Inno Setup 6 kurulu bir sistemde 'iscc setup.iss' ile doğrudan derlenebilir).")
        return False

    print(f"✅ Inno Setup Bulundu: {iscc_path}")
    cmd = [iscc_path, str(SETUP_ISS)]
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if res.returncode == 0:
        print("🎉 Inno Setup ile 'AriFirin_Setup.exe' başarıyla üretildi!")
        return True
    else:
        print(f"⚠️ Inno Setup derleme uyarısı (Kod: {res.returncode})")
        return False


def create_ari_firin_package() -> Path:
    """Müşteri için tek tıkla kurulan, ikonlu kısayol oluşturan Arı Fırın dağıtım paketi üretir."""
    print("\n📦 1. Arı Fırın Müşteri Dağıtım Paketi Üretiliyor...")

    package_dir = DIST_DIR / "AriFirin_Kurulum_Paketi"
    package_dir.mkdir(parents=True, exist_ok=True)

    # 1. Ana EXE veya onedir klasörünü kopyala
    ari_onedir = DIST_DIR / "AriFirin"
    if ari_onedir.exists() and (ari_onedir / "AriFirin.exe").exists():
        for item in ari_onedir.iterdir():
            dest = package_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
    else:
        dest_exe = package_dir / "AriFirin.exe"
        try:
            shutil.copy2(ARI_FIRIN_EXE, dest_exe)
        except Exception as e:
            print(f"   AriFirin.exe kopyalama notu: {e}")

    # 2. config.json kopyala
    shutil.copy2(CONFIG_JSON, package_dir / "config.json")

    # 3. resources klasörünü kopyala (İkonlar ve stiller dahil)
    if RESOURCES_DIR.exists():
        shutil.copytree(RESOURCES_DIR, package_dir / "resources", dirs_exist_ok=True)

    # 4. Tek tıkla Masaüstü ve Başlat Menüsü Kısayolu Oluşturan Kurulum Betiği (.bat)
    install_bat = package_dir / "Kurulum_Yap_ve_Kısayol_Olustur.bat"
    with open(install_bat, "w", encoding="utf-8") as f:
        f.write("""@echo off
chcp 65001 >nul
echo ============================================================
echo   ARI FIRIN MUHASEBE SISTEMI - OTOMATIK KURULUM VE KISAYOL
echo ============================================================
echo.
set "CURRENT_DIR=%~dp0"
set "TARGET_EXE=%CURRENT_DIR%AriFirin.exe"
set "ICON_PATH=%CURRENT_DIR%resources\\icons\\app.ico"

echo [1/3] Masaustune 'Arı Fırın' lisansli kisayolu olusturuluyor...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desk = [Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut((Join-Path $desk 'Arı Fırın.lnk')); $s.TargetPath = '%TARGET_EXE%'; $s.WorkingDirectory = '%CURRENT_DIR%'; $s.Description = 'Arı Fırın Masaüstü Muhasebe Sistemi'; if (Test-Path '%ICON_PATH%') { $s.IconLocation = '%ICON_PATH%' }; $s.Save()"

echo [2/3] Baslat Menusune kisayol ekleniyor...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $prog = [Environment]::GetFolderPath('Programs'); $s = $ws.CreateShortcut((Join-Path $prog 'Arı Fırın.lnk')); $s.TargetPath = '%TARGET_EXE%'; $s.WorkingDirectory = '%CURRENT_DIR%'; $s.Description = 'Arı Fırın Masaüstü Muhasebe Sistemi'; if (Test-Path '%ICON_PATH%') { $s.IconLocation = '%ICON_PATH%' }; $s.Save()"

echo [3/3] Baslat Menusune 'Kurulum ve Baglanti Sihirbazi' ekleniyor...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $prog = [Environment]::GetFolderPath('Programs'); $s = $ws.CreateShortcut((Join-Path $prog 'Arı Fırın - Kurulum Sihirbazı.lnk')); $s.TargetPath = '%TARGET_EXE%'; $s.Arguments = '--setup'; $s.WorkingDirectory = '%CURRENT_DIR%'; $s.Description = 'Arı Fırın Bağlantı ve Yapılandırma Sihirbazı'; if (Test-Path '%ICON_PATH%') { $s.IconLocation = '%ICON_PATH%' }; $s.Save()"

echo.
echo ============================================================
echo ✅ Kurulum ve Kisayollar Basariyla Tamamlandi!
echo ============================================================
echo.
set /p START_NOW="Uygulama simdi baslatilsin mi? (E/H): "
if /i "%START_NOW%"=="E" (
    start "" "%TARGET_EXE%"
)
""")

    # 5. Kurulum ve Kullanım Talimatı (README)
    readme_file = package_dir / "KURULUM_VE_KULLANIM_KILAVUZU.txt"
    with open(readme_file, "w", encoding="utf-8") as f:
        f.write("""============================================================
ARI FIRIN MUHASEBE SİSTEMİ - MÜŞTERİ HIZLI KURULUM KILAVUZU
============================================================

1. KURULUM (TEK TIKLA):
   - Bu klasörü bilgisayarınızda sabit bir konuma kopyalayın
     (Önerilen: C:\\AriFirin veya D:\\AriFirin).
   - "Kurulum_Yap_ve_Kısayol_Olustur.bat" dosyasına çift tıklayın.
   - Masaüstünüze ve Başlat Menünüze logolu "Arı Fırın" simgesi eklenecektir.

2. İLK ÇALIŞTIRMA VE BAĞLANTI SİHİRBAZI:
   - Masaüstündeki "Arı Fırın" simgesine çift tıklayın.
   - Eğer PostgreSQL sunucunuz başka bir bilgisayardaysa veya şifreniz farklıysa:
     * Başlat Menüsündeki "Arı Fırın - Kurulum Sihirbazı" kısayoluna tıklayın, veya
     * Komut satırından "AriFirin.exe --setup" yazın.
     * Yeni sunucu IP adresini, portunu ve şifresini yazıp "⚡ Bağlantıyı Canlı Test Et"
       butonuna basın. Bağlantı başarılı olduğunda "Kaydet ve Başlat" diyerek girin.

3. LİSANS VE ÇEVRİMDIŞI ÇALIŞMA:
   - Lisans anahtarınız merkezi sunucu üzerinden otomatik doğrulanır.
   - İnternetiniz veya yerel sunucu kesilse dahi sistem 7 gün boyunca kesintisiz
     çevrimdışı (offline) çalışmaya devam eder.

4. CANLI GÜNCELLEMELER (OTA):
   - Merkezi sunucuya yeni bir sürüm yüklendiğinde ekranın üst kısmında turuncu
     güncelleme şeridi belirecektir. "Şimdi İndir ve Güncelle" butonuna basarak
     tek tıkla en güncel sürüme geçebilirsiniz.

Teknik Destek: Arı Fırın Bilişim
============================================================
""")

    # 6. ZIP Arşivi Haline Getir
    zip_path = DIST_DIR / "AriFirin_Musteri_Dagitim_Paketi_v1.0.0.zip"
    print(f"📦 Arı Fırın ZIP arşivi sıkıştırılıyor: {zip_path.name}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_p = Path(root) / file
                arcname = file_p.relative_to(package_dir)
                zipf.write(file_p, arcname)

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"✅ Arı Fırın Dağıtım Paketi Hazırlandı: {zip_path} ({zip_size_mb:.2f} MB)")
    return zip_path


def create_universal_admin_package() -> Path:
    """Yönetici için Universal Admin Hub bağımsız dağıtım paketi üretir."""
    if not UNIVERSAL_ADMIN_EXE.exists():
        print("⚠️ UniversalAdmin.exe bulunmadığı için yönetici paketi atlanıyor.")
        return None

    print("\n📦 2. Universal Admin Yönetici Dağıtım Paketi Üretiliyor...")

    package_dir = DIST_DIR / "UniversalAdmin_Yonetici_Paketi"
    package_dir.mkdir(parents=True, exist_ok=True)

    # 1. Ana EXE'yi kopyala
    dest_exe = package_dir / "UniversalAdmin.exe"
    try:
        shutil.copy2(UNIVERSAL_ADMIN_EXE, dest_exe)
    except Exception as e:
        print(f"   UniversalAdmin.exe kopyalama notu: {e}")

    # 2. Güvenlik ve uygulama kayıt dosyalarını kopyala
    if ADMIN_SECURITY_JSON.exists():
        shutil.copy2(ADMIN_SECURITY_JSON, package_dir / "admin_security.json")
    if ADMIN_APPS_REGISTRY_JSON.exists():
        shutil.copy2(ADMIN_APPS_REGISTRY_JSON, package_dir / "apps_registry.json")

    # 3. resources klasörünü kopyala (İkonlar dahil)
    if ADMIN_RESOURCES_DIR.exists():
        shutil.copytree(ADMIN_RESOURCES_DIR, package_dir / "resources", dirs_exist_ok=True)

    # 4. Yönetici Kısayol Kurulum Betiği (.bat)
    install_bat = package_dir / "Yonetici_Paneli_Kurulum_ve_Kisayol.bat"
    with open(install_bat, "w", encoding="utf-8") as f:
        f.write("""@echo off
chcp 65001 >nul
echo ============================================================
echo   UNIVERSAL ADMIN HUB - YONETICI PANELI KISAYOL KURUCU
echo ============================================================
echo.
set "CURRENT_DIR=%~dp0"
set "TARGET_EXE=%CURRENT_DIR%UniversalAdmin.exe"
set "ICON_PATH=%CURRENT_DIR%resources\\icons\\admin.ico"

echo [1/2] Masaustune 'Universal Admin Hub' yonetici kisayolu ekleniyor...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desk = [Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut((Join-Path $desk 'Universal Admin Hub.lnk')); $s.TargetPath = '%TARGET_EXE%'; $s.WorkingDirectory = '%CURRENT_DIR%'; $s.Description = 'Universal Admin - Merkezi Sistem Yönetim Paneli'; if (Test-Path '%ICON_PATH%') { $s.IconLocation = '%ICON_PATH%' }; $s.Save()"

echo [2/2] Baslat Menusune yonetici kisayolu ekleniyor...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $prog = [Environment]::GetFolderPath('Programs'); $s = $ws.CreateShortcut((Join-Path $prog 'Universal Admin Hub.lnk')); $s.TargetPath = '%TARGET_EXE%'; $s.WorkingDirectory = '%CURRENT_DIR%'; $s.Description = 'Universal Admin - Merkezi Sistem Yönetim Paneli'; if (Test-Path '%ICON_PATH%') { $s.IconLocation = '%ICON_PATH%' }; $s.Save()"

echo.
echo ============================================================
echo ✅ Yonetici Kisayollari Basariyla Olusturuldu!
echo ============================================================
echo.
set /p START_NOW="Yonetici Paneli simdi baslatilsin mi? (E/H): "
if /i "%START_NOW%"=="E" (
    start "" "%TARGET_EXE%"
)
""")

    # 5. Yönetici Kılavuzu (README)
    readme_file = package_dir / "YONETICI_KILAVUZU.txt"
    with open(readme_file, "w", encoding="utf-8") as f:
        f.write("""============================================================
UNIVERSAL ADMIN HUB - MERKEZİ YÖNETİM PANELİ KULLANIM KILAVUZU
============================================================

1. BAŞLATMA VE GİRİŞ:
   - "Yonetici_Paneli_Kurulum_ve_Kisayol.bat" çalıştırılarak masaüstüne
     yönetici kısayolu eklenir.
   - Açılışta Master Şifre istenir. Varsayılan güvenli şifre ile giriş yapılır.

2. MERKEZİ SUNUCU BULUT BAĞLANTISI:
   - Sol taraftaki "☁️ Bulut & Güncelleme" sekmesinden Raspberry Pi sunucusu
     (http://sunaos:8000) yönetilir.
   - Oturum Çerezi güvenliği ve anlık durum kontrolleri devrededir.

3. MÜŞTERİ LİSANS YÖNETİMİ:
   - Lisanslar sekmesinde kayıtlı müşteriler listelenir.
   - "🔒/🔓 Durumu Değiştir" butonuyla ödeme yapmayan müşterinin lisansı
     uzaktan anında askıya alınabilir (Arı Fırın anında kilitlenir).
   - "🔓 Makine Kilidini Sıfırla" butonuyla bilgisayar değiştiren müşterinin
     donanım bağı çözülür ve yeni bilgisayarına bağlanması sağlanır.

4. BULUT YEDEKLERİNİ YÖNETME:
   - "☁️ Bulut Yedekleri" sekmesinde müşterilerin otomatik yüklenen veritabanı
     yedekleri listelenir.
   - İstenilen yedeğe tıklanarak doğrudan güvenle indirilebilir (Path Traversal
     ve oturum korumalı).

5. OTA GÜNCELLEME DAĞITIMI:
   - Yeni bir AriFirin.exe üretildiğinde "Yeni Güncelleme Yayınla" sekmesinden
     dosya seçilip sürüm notları girilerek tek tıkla sunucuya yüklenir.
   - Tüm sahadaki Arı Fırın istemcilerine saniyeler içinde güncelleme bildirimi ulaşır.

Geliştirici & Sistem Mimarı: Arı Fırın Bilişim
============================================================
""")

    # 6. ZIP Arşivi Haline Getir
    zip_path = DIST_DIR / "UniversalAdmin_Yonetici_Paketi_v1.0.0.zip"
    print(f"📦 Universal Admin ZIP arşivi sıkıştırılıyor: {zip_path.name}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_p = Path(root) / file
                arcname = file_p.relative_to(package_dir)
                zipf.write(file_p, arcname)

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"✅ Universal Admin Dağıtım Paketi Hazırlandı: {zip_path} ({zip_size_mb:.2f} MB)")
    return zip_path


def main():
    if not check_prerequisites():
        sys.exit(1)

    try_compile_inno_setup()
    create_ari_firin_package()
    create_universal_admin_package()

    print("\n" + "=" * 60)
    print("🏆 TÜM DAĞITIM VE KURULUM PAKETLERİ BAŞARIYLA OLUŞTURULDU!")
    print(f"📁 Çıktı Dizini: {DIST_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
