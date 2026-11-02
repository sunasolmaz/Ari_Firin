# build.py
import os
import shutil
import PyInstaller.__main__
from src.core.config import config

def clean_build():
    """Eski build dosyalarını temizle"""
    dirs = ['build', 'dist', '__pycache__']
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d)
    
    # .spec dosyasını temizle
    for f in os.listdir('.'):
        if f.endswith('.spec'):
            os.remove(f)

def build_exe():
    """EXE oluştur"""
    
    # Temizlik
    clean_build()
    
    # PyInstaller argümanları
    args = [
        'main.py',
        '--onefile',                    # Tek EXE
        '--noconsole',                  # Konsol yok
        '--name=MuhasebeUygulamasi',    # EXE adı
        '--icon=resources/icons/app.ico', # İkon
        '--add-data=src;src',           # Kaynak dosyalar
        '--add-data=resources;resources',
        '--hidden-import=psycopg2',     # Gizli importlar
        '--hidden-import=PyQt5',
        '--hidden-import=pandas',
        '--hidden-import=openpyxl',
        '--hidden-import=psutil',
        '--hidden-import=requests',
        '--collect-all=psycopg2',       # Tüm modülleri topla
        '--collect-all=PyQt5',
        '--clean',                      # Temiz build
        '--strip',                      # Boyut küçült
        '--noconfirm'                   # Onay isteme
    ]
    
    # UPX ile sıkıştır (varsa)
    if shutil.which('upx'):
        args.append('--upx-dir')
        args.append(os.path.dirname(shutil.which('upx')))
    
    # Build
    PyInstaller.__main__.run(args)
    
    # Çıktıyı kontrol et
    exe_path = 'dist/MuhasebeUygulamasi.exe'
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"✅ EXE oluşturuldu: {exe_path}")
        print(f"   Boyut: {size_mb:.1f} MB")
        return True
    else:
        print("❌ EXE oluşturulamadı!")
        return False

def create_portable_package():
    """Portable paket oluştur"""
    import zipfile
    
    # Portable klasörü
    portable_dir = 'MuhasebePortable'
    if os.path.exists(portable_dir):
        shutil.rmtree(portable_dir)
    os.makedirs(portable_dir)
    
    # EXE'yi kopyala
    shutil.copy('dist/MuhasebeUygulamasi.exe', f'{portable_dir}/Muhasebe.exe')
    
    # Config dosyası
    shutil.copy('config.json', f'{portable_dir}/config.json')
    
    # PostgreSQL Portable (varsa)
    if os.path.exists('postgresql'):
        shutil.copytree('postgresql', f'{portable_dir}/postgresql')
    
    # Kurulum talimatları
    with open(f'{portable_dir}/KURULUM_TALIMATI.txt', 'w', encoding='utf-8') as f:
        f.write("""
        MUHASEBE UYGULAMASI - KURULUM TALİMATI
        
        1. PostgreSQL kurun:
           - postgresql klasöründeki init_db.bat'ı çalıştırın
           
        2. Uygulamayı başlatın:
           - Muhasebe.exe'ye çift tıklayın
           
        3. Giriş bilgileri:
           - Kullanıcı: admin_1, admin_2, admin_3
           - Şifre: admin123
           - Şube: Merkez Şube / Ankara / İzmir
        
        4. İlk girişte şifrenizi değiştirin!
        """)
    
    # ZIP oluştur
    zip_name = f"Muhasebe_Uygulamasi_{config.get('application.version')}.zip"
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(portable_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, portable_dir)
                zipf.write(file_path, arcname)
    
    # Temizlik
    shutil.rmtree(portable_dir)
    
    print(f"✅ Portable paket oluşturuldu: {zip_name}")
    print(f"   Boyut: {os.path.getsize(zip_name) / (1024 * 1024):.1f} MB")

if __name__ == "__main__":
    print("🚀 EXE Oluşturma Başlatılıyor...")
    
    if build_exe():
        create_portable_package()
        
    print("\n✅ İşlem tamamlandı!")