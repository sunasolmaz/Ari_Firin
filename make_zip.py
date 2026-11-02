import zipfile
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

src = r'D:\Desktop\Arı_Fırın\dist\AriFirin_Musteri_Dagitim_Paketi_v1.0.0'
dst = r'D:\Desktop\Arı_Fırın\dist\AriFirin_Musteri_Dagitim_Paketi_v1.0.0.zip'

if os.path.exists(dst):
    os.remove(dst)
    print(f"Eski ZIP silindi.")

skipped = []
added = []

with zipfile.ZipFile(dst, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src):
        # skip __pycache__
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fname in files:
            if fname in ['license.dat', 'license_cache.dat', 'machine_id.dat']:
                continue
            fpath = os.path.join(root, fname)
            arcname = os.path.relpath(fpath, src)
            try:
                zf.write(fpath, arcname)
                added.append(arcname)
            except Exception as e:
                skipped.append((arcname, str(e)))

print(f"\nEklenen: {len(added)} dosya")
if skipped:
    print(f"Atlanan: {len(skipped)} dosya (kilitli/hata)")
    for arc, err in skipped:
        print(f"  ATLANDI: {arc}: {err[:60]}")

size_mb = os.path.getsize(dst) / 1024 / 1024
print(f"\nZIP hazir: {dst}")
print(f"Boyut: {size_mb:.1f} MB")
