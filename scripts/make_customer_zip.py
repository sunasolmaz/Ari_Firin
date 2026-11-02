import os
import shutil
import zipfile
from pathlib import Path

pkg = Path('dist/AriFirin_Kurulum_Paketi')

# Copy TEK_TIKLA_KURULUM.bat if exists in dist/ or root
bat_candidates = [
    Path('TEK_TIKLA_KURULUM.bat'),
    Path('dist/TEK_TIKLA_KURULUM.bat'),
]
for bc in bat_candidates:
    if bc.exists():
        shutil.copy2(bc, pkg / 'TEK_TIKLA_KURULUM.bat')
        break

# Write KURULUM_VE_KULLANIM_KILAVUZU.txt
guide_content = """=====================================================================
                   ARI FIRIN MUHASEBE VE YÖNETİM SİSTEMİ
                     MÜŞTERİ KURULUM VE KULLANIM REHBERİ
=====================================================================

Değerli Müşterimiz,
Arı Fırın Masaüstü Muhasebe Sistemine hoş geldiniz.

---------------------------------------------------------------------
1. İLK KURULUM
---------------------------------------------------------------------
1. Size iletilen ZIP arşiv dosyasını bilgisayarınızda bir klasöre çıkartınız.
2. Klasör içerisindeki "TEK_TIKLA_KURULUM.bat" dosyasını çalıştırınız.
3. Masaüstünüze "Arı Fırın" kısayolu eklenecek ve uygulama otomatik açılacaktır.

---------------------------------------------------------------------
2. GİRİŞ BİLGİLERİ
---------------------------------------------------------------------
Sisteminiz için tanımlı yönetici hesapları:
- Kullanıcı Adı: admin        Şifre: Solmaz142
- Kullanıcı Adı: suna14270    Şifre: 123456

(Giriş yaptıktan sonra Ayarlar sayfasından şifrenizi dilediğiniz gibi güncelleyebilirsiniz.)

---------------------------------------------------------------------
3. GÜNLÜK KULLANIM
---------------------------------------------------------------------
Günlük kullanımda Masaüstünüzdeki "Arı Fırın" kısayoluna çift tıklayarak
doğrudan giriş yapabilirsiniz.
=====================================================================
"""
with open(pkg / 'KURULUM_VE_KULLANIM_KILAVUZU.txt', 'w', encoding='utf-8') as f:
    f.write(guide_content)

# Remove any cache or machine id or local license files from package
for bad in ['license_cache.dat', 'machine_id.dat', 'license.dat']:
    bf = pkg / bad
    if bf.exists():
        os.remove(bf)

# Clean log files in package
log_dir = pkg / 'logs'
if log_dir.exists():
    for f in log_dir.glob('*'):
        if f.is_file():
            os.remove(f)

# Create ZIP
zip_path = Path('dist/AriFirin_Musteri_Dagitim_Paketi_v1.0.0.zip')
if zip_path.exists():
    os.remove(zip_path)

print('Compressing customer package into ZIP...')
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for root, dirs, files in os.walk(pkg):
        for fl in files:
            full_f = Path(root) / fl
            rel_f = full_f.relative_to(pkg)
            if rel_f.name in ['license_cache.dat', 'machine_id.dat', 'license.dat']:
                continue
            zf.write(full_f, arcname=str(rel_f))

size_mb = zip_path.stat().st_size / (1024 * 1024)
print(f'Customer ZIP Created Successfully: {zip_path.name} ({size_mb:.2f} MB)')
