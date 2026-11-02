# create_license.py
"""
Arı Fırın - Lisans Yönetim ve Oluşturma Aracı
Merkezi Kontrol Sunucusu (Raspberry Pi) & Çevrimdışı Lisans Desteği
"""

import sys
import requests
from datetime import datetime, timedelta
from src.utils.license_manager import LicenseManager

PI_SERVER_URL = "http://100.125.79.19:8000"
PROJECT_ID = "ari_firin"


def get_pi_clients():
    try:
        url = f"{PI_SERVER_URL}/api/v1/projects/{PROJECT_ID}/clients"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            return r.json().get("clients", [])
    except Exception as e:
        print(f"[!] Pi sunucusuna erisilemedi: {e}")
    return None


def print_pi_licenses():
    print(f"\n[+] Raspberry Pi Lisans Sunucusu ({PI_SERVER_URL}):")
    clients = get_pi_clients()
    if clients is None:
        print("[-] Pi sunucusuna baglanilamadi. Tailscale acik mi kontrol edin.")
        return
    print(f"{'ID':<4} {'Musteri / Cihaz':<35} {'Lisans Anahtari':<28} {'Kilitli Makine ID'}")
    print("-" * 105)
    for c in clients:
        mid = c.get("machine_id") or "KILITLI DEGIL (Ilk baglanan cihaz alir)"
        print(f"{c.get('id'):<4} {c.get('client_name', ''):<35} {c.get('license_key', ''):<28} {mid}")
    print("-" * 105)


def add_license_to_pi(client_name: str, license_key: str):
    url = f"{PI_SERVER_URL}/api/v1/projects/{PROJECT_ID}/clients"
    payload = {
        "client_name": client_name,
        "license_key": license_key,
        "expires_at": None,
        "machine_id": None
    }
    try:
        r = requests.post(url, json=payload, timeout=4)
        if r.status_code == 200:
            print(f"\n[+] Lisans Pi sunucusuna basariyla kaydedildi!")
            print(f"   Musteri: {client_name}")
            print(f"   Lisans Anahtari: {license_key}")
            print("   (Ilk calistirildiginda musterinin bilgisayari bu lisansa otomatik kilitlenecektir.)")
            return True
        else:
            print(f"[-] Hata: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"[-] Baglanti hatasi: {e}")
    return False


def reset_machine_lock(client_id: int):
    url = f"{PI_SERVER_URL}/api/v1/clients/{client_id}/reset-machine"
    try:
        r = requests.post(url, timeout=4)
        if r.status_code == 200:
            print(f"\n[+] Makine kilidi basariyla sifirlandi! (Cihaz degisikligine izin verildi)")
            return True
        else:
            print(f"[-] Hata: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"[-] Baglanti hatasi: {e}")
    return False


def main():
    print("=" * 60)
    print("      ARI FIRIN - LISANS VE CIHAZ YONETIM MERKEZI")
    print("=" * 60)

    # Eger komut satirindan hizlica cagrildiysa
    if len(sys.argv) >= 2:
        arg = sys.argv[1].strip()
        if arg.startswith("ARI-FIRIN-"):
            print(f"\n[*] Belirtilen lisans anahtari: {arg}")
            print("Bu anahtar dogrudan Pi sunucusuna kaydediliyor...")
            add_license_to_pi(f"Musteri Bilgisayari ({arg})", arg)
            return

    while True:
        print("\nIslem Seciniz:")
        print("1. Pi Sunucusundaki Lisanslari ve Kilitli Cihazlari Listele")
        print("2. Yeni Bilgisayar Icin Lisans Tanimla (Pi'ye Kaydet)")
        print("3. Cihaz Degisikligi / Makine Kilidini Sifirla (Reset)")
        print("4. Cevrimdisi / Yerel Lisans Dosyasi (license.dat) Olustur")
        print("5. Cikis")

        secim = input("\nSeciminiz (1-5): ").strip()

        if secim == "1":
            print_pi_licenses()

        elif secim == "2":
            name = input("\nBilgisayar Aciklamasi (Orn: Tekirdag Musterisi 3. Bilgisayar): ").strip()
            if not name:
                name = "Yeni Musteri Bilgisayari"
            key = input("Lisans Anahtari (Orn: ARI-FIRIN-TEKIRDAG-2026-C): ").strip()
            if not key:
                print("[-] Lisans anahtari bos olamaz!")
                continue
            add_license_to_pi(name, key)

        elif secim == "3":
            print_pi_licenses()
            cid_str = input("\nKilidi sifirlanacak Musteri ID'sini girin: ").strip()
            if cid_str.isdigit():
                reset_machine_lock(int(cid_str))
            else:
                print("[-] Gecersiz ID!")

        elif secim == "4":
            manager = LicenseManager()
            mid = input("\nHedef Makine ID (Bos birakilirsa bu PC'nin ID'si kullanilir): ").strip() or None
            print("\nLisans Suresi:")
            print("1. Suresiz")
            print("2. 1 Yil")
            print("3. 30 Gun")
            sub = input("Secim (1/2/3): ").strip()
            expiry = None
            if sub == "2":
                expiry = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
            elif sub == "3":
                expiry = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

            data = manager.create_license(expiry_date=expiry, features=['all'], custom_machine_id=mid)
            if manager.save_license(data):
                print(f"\n[+] Yerel license.dat olusturuldu (Makine ID: {data['machine_id']})")
            else:
                print("[-] Kaydedilemedi!")

        elif secim == "5":
            break
        else:
            print("[-] Gecersiz secim!")


if __name__ == "__main__":
    main()