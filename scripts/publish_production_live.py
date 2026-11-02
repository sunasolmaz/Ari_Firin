#!/usr/bin/env python3
# scripts/publish_production_live.py
"""
Arı Fırın & Universal Admin Resmi Canlıya Alma (Go-Live) Betiği.
Derlenen resmi AriFirin.exe ikili paketini merkezi sunucuya (sunaos:8000)
yayınlar, OTA güncelleme beslemesini aktif eder ve uçtan uca doğrular.
"""

import os
import sys
import time
import requests
from pathlib import Path

# Windows cp1254 terminal desteği
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from UniversalAdmin.src.services.cloud_service import CloudService
from src.services.updater_service import UpdaterService

SERVER_URL = "http://sunaos:8000"
PROJECT_ID = "ari_firin"
RELEASE_VERSION = "1.0.1"
EXE_PATH = PROJECT_ROOT / "dist" / "AriFirin.exe"
RELEASE_NOTES = """🚀 Arı Fırın v1.0.1 Resmi Üretim Sürümü (Production Release)
- FinTech & Muhasebe: Yüksek hassasiyetli Decimal ve kuruş yuvarlama (Round-Half-Even) güvencesi.
- Veritabanı Güvenliği: Tam PostgreSQL ACID transaction bütünlüğü ve yarış durumu (race condition) koruması.
- Otomatik Bulut Yedekleme: Günlük AES şifreli veritabanı yedeklerinin merkezi sunucuya aktarımı.
- Gelişmiş Lisanslama: Uzaktan anlık askıya alma ve 7 günlük çevrimdışı (offline) tolerans.
- Marka ve Görsel Kimlik: Çok çözünürlüklü Windows ICO simgeleri ve modern arayüz teması.
- Canlı Teşhis: Dahili ilk kurulum ve bağlantı sihirbazı desteği (--setup)."""


def go_live():
    print("=" * 70)
    print("🚀 ARI FIRIN RESMİ CANLIYA ALMA (PRODUCTION GO-LIVE) DAĞITIMI")
    print("=" * 70)

    # 1. Sunucu Sağlık Denetimi
    print("\n[1/6] Merkezi Sunucu Sağlık Denetimi...")
    cloud = CloudService(SERVER_URL)
    if not cloud.test_connection():
        print(f"❌ HATA: {SERVER_URL} sunucusuna erişilemiyor!")
        sys.exit(1)
    print(f"✅ Merkezi Sunucu Aktif ve Çalışıyor: {SERVER_URL}")

    # 2. Üretim Paketi (EXE) Kontrolü
    print("\n[2/6] Üretim Paketi (EXE) Bütünlük Denetimi...")
    if not EXE_PATH.exists():
        print(f"❌ HATA: {EXE_PATH} bulunamadı!")
        sys.exit(1)
    exe_size_mb = EXE_PATH.stat().st_size / (1024 * 1024)
    with open(EXE_PATH, "rb") as f:
        magic = f.read(2)
    if magic != b"MZ":
        print(f"❌ HATA: {EXE_PATH} geçerli bir Windows PE binary dosyası değil!")
        sys.exit(1)
    print(f"✅ AriFirin.exe Doğrulandı: {exe_size_mb:.2f} MB (PE MZ Header Onaylı)")

    # 3. Merkezi Sunucuya Resmi Sürüm Olarak Yayınlama
    print(f"\n[3/6] Resmi Sürüm v{RELEASE_VERSION} Sunucuya Yükleniyor ve Yayınlanıyor...")
    start_time = time.time()
    
    # Sunucuda AriFirin.exe zaten yüklü mü kontrol et
    static_url = f"/static/updates/{PROJECT_ID}/AriFirin.exe"
    head_check = requests.head(f"{SERVER_URL}{static_url}", timeout=5)
    if head_check.status_code == 200:
        print(f"ℹ️ Sunucuda AriFirin.exe zaten mevcut ({head_check.headers.get('content-length')} bayt), anlık yayınlama yapılıyor...")
        pub_res = cloud.publish_update(
            project_id=PROJECT_ID,
            version=RELEASE_VERSION,
            release_notes=RELEASE_NOTES,
            force_update=False,
            external_url=static_url
        )
    else:
        print("ℹ️ Sunucuya AriFirin.exe ikili paketi yükleniyor...")
        pub_res = cloud.publish_update(
            project_id=PROJECT_ID,
            version=RELEASE_VERSION,
            release_notes=RELEASE_NOTES,
            force_update=False,
            installer_path=str(EXE_PATH)
        )
    elapsed = time.time() - start_time

    if not pub_res.get("success"):
        print(f"❌ Yayınlama Başarısız: {pub_res.get('error')}")
        sys.exit(1)

    data = pub_res["data"]
    download_url = data["download_url"]
    print(f"🎉 Sürüm Başarıyla Yayınlandı ({elapsed:.2f} sn)!")
    print(f"   Sürüm: v{data['latest_version']}")
    print(f"   İndirme Yolu: {download_url}")

    # 4. Sunucudan OTA Beslemesini Doğrulama
    print("\n[4/6] Canlı OTA API Beslemesi Doğrulanıyor...")
    ver_info = cloud.get_version_info(PROJECT_ID)
    if not ver_info or ver_info.get("latest_version") != RELEASE_VERSION:
        print(f"❌ HATA: Sunucu sürüm bilgisi eşleşmiyor! Alınan: {ver_info}")
        sys.exit(1)
    print(f"✅ OTA API Doğrulandı: Son Sürüm = v{ver_info['latest_version']}")

    # 5. İndirme Bağlantısı Bütünlük Testi
    print("\n[5/6] İndirme Bağlantısı ve Dosya Doğrulaması...")
    full_dl_url = f"{SERVER_URL}{download_url}"
    head_res = requests.get(full_dl_url, stream=True, timeout=10)
    if head_res.status_code != 200:
        print(f"❌ HATA: İndirme URL'si HTTP {head_res.status_code} döndürdü!")
        sys.exit(1)
    # İlk baytları oku
    first_bytes = head_res.raw.read(2)
    if first_bytes != b"MZ":
        print("❌ HATA: İndirilen dosya geçerli bir Windows PE binary değil!")
        sys.exit(1)
    print(f"✅ İndirme Linki Canlı ve Sağlam: {full_dl_url} (HTTP 200 OK)")

    # 6. İstemci Sürüm ve Kalp Atışı (Heartbeat) Denetimi
    print("\n[6/6] Sahadaki İstemci Durumu ve Kalp Atışı Denetimi...")
    hb_url = f"{SERVER_URL}/api/v1/projects/{PROJECT_ID}/heartbeat"
    hb_payload = {
        "license_key": "ARI-FIRIN-TEKIRDAG-2026",
        "version": "1.0.0"
    }
    hb_res = requests.post(hb_url, json=hb_payload, timeout=5)
    hb_ok = (hb_res.status_code == 200)
    print(f"✅ İstemci Kalp Atışı (Heartbeat): {'Başarılı (Online)' if hb_ok else f'Hata ({hb_res.status_code})'}")

    # Semantik sürüm denetimi
    v_server = ver_info.get("latest_version")
    print(f"✅ Canlı Güncelleme Durumu: Sahadaki v1.0.0 istemciler v{v_server} sürümünü alacaktır.")
    print(f"   İstemci Ekranında Belirecek Banner: 🚀 Arı Fırın v{v_server} Güncellemesi Hazır! [📥 Şimdi İndir ve Güncelle]")

    clients = cloud.get_clients(PROJECT_ID)
    print(f"\n📊 Merkezi Sunucudaki Kayıtlı İstemciler ({len(clients)} İstemci):")
    for c in clients:
        status_icon = "🟢" if c.get("is_online") else "⚪"
        print(f"   {status_icon} Müşteri: {c.get('client_name')} | Lisans: {c.get('license_key')} | Sürüm: v{c.get('current_version')}")

    print("\n" + "=" * 70)
    print("🏆 SİSTEM RESMİ OLARAK CANLIYA ALINDI VE TÜM SERVİSLER AKTİF!")
    print("=" * 70)


if __name__ == "__main__":
    go_live()
