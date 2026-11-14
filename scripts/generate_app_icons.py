#!/usr/bin/env python3
# scripts/generate_app_icons.py
"""
Arı Fırın & Universal Admin Çok Çözünürlüklü Windows ICO Simge Üreteci.
Pillow kullanarak modern, kurumsal ve çok çözünürlüklü (16x16 - 256x256) .ico dosyaları üretir.
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw

# Windows cp1254 terminal desteği
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARI_ICON_DIR = PROJECT_ROOT / "resources" / "icons"
ADMIN_ICON_DIR = PROJECT_ROOT / "resources" / "icons" / "admin"

SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def create_ari_firin_icon() -> Image.Image:
    """Arı Fırın için modern altın sarısı / fırın / petek temalı 256x256 RGBA ikon çizer."""
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Yuvarlatılmış Köşeli Altın Sarısı / Kehribar Arka Plan (#F59E0B -> #D97706)
    margin = 12
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=48,
        fill=(245, 158, 11, 255),  # Kehribar Sarısı
        outline=(217, 119, 6, 255),  # Koyu Kehribar Kontur
        width=4
    )

    # 2. İç Yumuşak Işık Halkası
    draw.rounded_rectangle(
        [margin + 8, margin + 8, size - margin - 8, size - margin - 8],
        radius=40,
        outline=(254, 240, 138, 120),  # Açık sarı parlama
        width=2
    )

    # 3. Sıcak Fırın Ekmeği / Hilal Geometrisi (Koyu Fırın Kahverengisi #78350F)
    # Ekmek tabanı
    draw.chord([48, 90, 208, 200], start=0, end=180, fill=(120, 53, 15, 255), outline=(69, 26, 3, 255), width=3)
    # Ekmek üst kubbesi
    draw.chord([48, 70, 208, 180], start=180, end=360, fill=(180, 83, 9, 255), outline=(120, 53, 15, 255), width=3)

    # 4. Geleneksel Fırıncı Ekmek Çizgileri (Kesikler)
    cut_color = (254, 243, 199, 230)  # Krem rengi ekmek içi yarıkları
    draw.line([88, 95, 100, 135], fill=cut_color, width=5)
    draw.line([128, 85, 128, 130], fill=cut_color, width=5)
    draw.line([168, 95, 156, 135], fill=cut_color, width=5)

    # 5. Petek / Arı Motifi Simgesi (Üst Merkez)
    hex_pts = [(128, 38), (146, 48), (146, 68), (128, 78), (110, 68), (110, 48)]
    draw.polygon(hex_pts, fill=(255, 255, 255, 240), outline=(217, 119, 6, 255))

    return img


def create_universal_admin_icon() -> Image.Image:
    """Universal Admin için kurumsal lacivert / yönetim kalkanı temalı 256x256 RGBA ikon çizer."""
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Koyu Lacivert / Grafit Arka Plan (#0F172A)
    margin = 12
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=48,
        fill=(15, 23, 42, 255),
        outline=(51, 65, 85, 255),
        width=4
    )

    # 2. Güvenlik ve Yönetim Kalkanı (Shield Motif: #3B82F6 / #1D4ED8)
    shield_pts = [
        (128, 48),   # Tepe nokta
        (190, 75),   # Sağ üst köşe
        (185, 145),  # Sağ kenar
        (128, 205),  # Alt sivri uç
        (71, 145),   # Sol kenar
        (66, 75),    # Sol üst köşe
    ]
    draw.polygon(shield_pts, fill=(29, 78, 216, 255), outline=(96, 165, 250, 255))

    # Kalkanın sol yarısını hafif açık mavi yap (3D Hacim etkisi)
    shield_left_pts = [
        (128, 48),
        (66, 75),
        (71, 145),
        (128, 205),
    ]
    draw.polygon(shield_left_pts, fill=(59, 130, 246, 255))

    # 3. Kalkan Merkezinde Yetkili Yönetici Rozeti / Anahtar Deseni
    # Beyaz kilit gövdesi
    draw.rounded_rectangle([108, 115, 148, 155], radius=6, fill=(255, 255, 255, 255))
    # Kilit kemeri (halka)
    draw.arc([114, 92, 142, 125], start=180, end=360, fill=(255, 255, 255, 255), width=5)
    # Anahtar deliği
    draw.ellipse([124, 126, 132, 134], fill=(15, 23, 42, 255))
    draw.rectangle([126, 132, 130, 144], fill=(15, 23, 42, 255))

    return img


def generate_all_icons():
    print("=" * 60)
    print("🎨 ÇOK ÇÖZÜNÜRLÜKLÜ ICO SİMGE ÜRETİCİSİ")
    print("=" * 60)

    # Dizinleri oluştur
    ARI_ICON_DIR.mkdir(parents=True, exist_ok=True)
    ADMIN_ICON_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Arı Fırın İkonu
    ari_img = create_ari_firin_icon()
    ari_ico_path = ARI_ICON_DIR / "app.ico"
    ari_png_path = ARI_ICON_DIR / "app.png"
    ari_img.save(ari_png_path, format="PNG")
    ari_img.save(ari_ico_path, format="ICO", sizes=SIZES)
    print(f"✅ Arı Fırın İkonu Üretildi: {ari_ico_path} ({ari_ico_path.stat().st_size / 1024:.1f} KB)")
    print(f"   PNG Önizleme: {ari_png_path}")

    # 2. Universal Admin İkonu
    admin_img = create_universal_admin_icon()
    admin_ico_path = ADMIN_ICON_DIR / "admin.ico"
    admin_png_path = ADMIN_ICON_DIR / "admin.png"
    admin_img.save(admin_png_path, format="PNG")
    admin_img.save(admin_ico_path, format="ICO", sizes=SIZES)
    print(f"✅ Universal Admin İkonu Üretildi: {admin_ico_path} ({admin_ico_path.stat().st_size / 1024:.1f} KB)")
    print(f"   PNG Önizleme: {admin_png_path}")

    print("=" * 60)


if __name__ == "__main__":
    generate_all_icons()
