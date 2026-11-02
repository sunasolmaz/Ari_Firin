# Arı Fırın & Universal Admin - Canlıya Alma ve Dağıtım Rehberi

Bu rehber, geliştirilen sistemin sahada (müşteri fırınlarında) ve merkezde (Raspberry Pi / Yönetici bilgisayarı) adım adım canlıya alınması ve işletilmesi sürecini kapsar.

---

## 🏗️ Sistemin Canlı Mimarisi (3 Temel Ayak)

```
                       ┌──────────────────────────────────────┐
                       │      MERKEZİ SUNUCU (Raspberry Pi)   │
                       │             http://sunaos:8000       │
                       │   - Canlı OTA Güncelleme Dağıtımı    │
                       │   - Müşteri Lisans & Heartbeat       │
                       │   - Şifreli Bulut Yedek Havuzu       │
                       └──────────────────┬───────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
   ┌──────────────────────────────┐              ┌──────────────────────────────┐
   │     YÖNETİCİ BİLGİSAYARI     │              │     MÜŞTERİ FIRIN BİLGİSAYARI│
   │      (Universal Admin)       │              │         (Arı Fırın)          │
   │ - Müşteri Lisanslarını Yönet │              │ - Masaüstü Muhasebe & Stok   │
   │ - Tek Tıkla Canlıya Güncelle │              │ - Otomatik Bulut Yedekleme   │
   │ - Bulut Yedeklerini İndir    │              │ - 7 Gün Çevrimdışı Tolerans  │
   └──────────────────────────────┘              └──────────────────────────────┘
```

---

## 1. ADIM: Merkezi Sunucunun Canlıda Çalıştırılması (Raspberry Pi)

Merkezi sunucu (`central_server`), tüm fırınların lisans kontrolünü yapar, yedeklerini toplar ve yeni sürümleri dağıtır.

### A. Sunucuya Dosyaları Yükleme & Başlatma
1. Raspberry Pi'de terminali açın:
   ```bash
   cd /home/pi/Arı_Fırın/central_server
   pip install -r requirements.txt
   ```
2. Canlı sunucuyu arka planda (`systemd` servisi olarak veya `screen/tmux/pm2` ile) başlatın:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
3. **Servis Kontrolü:**
   Tarayıcınızdan veya komut satırından doğrulayın:
   `http://sunaos:8000/api/health` -> `{"status": "ok"}` yanıtı gelmelidir.

---

## 2. ADIM: Yönetici Paneli Kurulumu (Sizin Bilgisayarınız)

Yönetici olarak sahayı izlemek ve güncelleme göndermek için Universal Admin'i kurun:

1. `dist/UniversalAdmin_Yonetici_Paketi_v1.0.0.zip` dosyasını bilgisayarınızda bir klasöre çıkarın (Örn: `C:\UniversalAdmin`).
2. **`Yonetici_Paneli_Kurulum_ve_Kisayol.bat`** dosyasına çift tıklayın.
   - Masaüstünüze logolu **`Universal Admin Hub`** kısayolu otomatik yerleşecektir.
3. Uygulamayı açın:
   - **Giriş:** Yönetici şifreniz ile oturum açın.
   - **Bulut & Güncelleme Sekmesi:** `http://sunaos:8000` sunucunuza bağlı olduğunuzu ve yeşil "Çevrimiçi" durumunu görün.
   - **Müşteri Lisansları:** Arı Fırın için lisans anahtarının aktif olduğunu teyit edin.

---

## 3. ADIM: Müşteri / Fırın Kurulumu (İstemci Bilgisayarı)

Müşteriye veya yeni bir şube kasasına programı kurarken:

### A. Kurulum Dosyasını Aktarma
1. `dist/AriFirin_Musteri_Dagitim_Paketi_v1.0.0.zip` dosyasını USB bellek veya ağ üzerinden müşterinin bilgisayarına aktarın.
2. Klasöre çıkarın (Önerilen: `C:\AriFirin`).
3. Klasörün içindeki **`Kurulum_Yap_ve_Kısayol_Olustur.bat`** dosyasına çift tıklayın.
   - Masaüstüne **`Arı Fırın`** simgesi eklenir.
   - Başlat Menüsüne **`Arı Fırın`** ve **`Arı Fırın - Kurulum Sihirbazı`** eklenir.

### B. İlk Bağlantı & Canlı Teşhis
1. Masaüstündeki **`Arı Fırın`** simgesine çift tıklayın.
2. Eğer PostgreSQL sunucusu yerel değilse (örn. ana kasada kurulu ve bu bilgisayar terminal/şube ise):
   - Açılışta *"🛠️ Kurulum Sihirbazını Aç"* seçeneğine tıklayın.
   - **Sunucu IP:** Ana kasanın IP adresini yazın (Örn: `192.168.1.50`).
   - **Port:** `5432` | **Şifre:** PostgreSQL şifreniz.
   - **`⚡ Bağlantıyı Canlı Test Et`** butonuna basın. Yeşil onay aldığınızda **`💾 Ayarları Kaydet ve Başlat`** diyerek sistemi devreye alın.

---

## 4. ADIM: Canlıda Güncelleme Yayınlama (OTA Akışı)

Gelecekte kodda bir değişiklik yaptığınızda veya yeni özellik eklediğinizde müşterinin ayağına gitmeden uzaktan güncelleme yapmak için:

1. Kendi bilgisayarınızda yeni `.exe`yi derleyin:
   ```powershell
   python scripts/build_executables.py --build-ari-firin
   ```
2. **Universal Admin**'i açın -> **"Yeni Güncelleme Yayınla"** sekmesine gelin.
3. Yeni sürüm numarasını (Örn: `1.0.1`) ve yenilik notlarını yazın.
4. Dosya seçici ile derlediğiniz `dist/AriFirin.exe` dosyasını seçip **"Güncellemeyi Canlıya Yayınla"** butonuna basın.
5. **Sonuç:** Sahadaki tüm fırınların ekranının üstünde anında:
   `🚀 Arı Fırın v1.0.1 Güncellemesi Hazır! [📥 Şimdi İndir ve Güncelle]`
   şeridi çıkacak ve tek tıkla tüm müşterileriniz güncellenecektir!

---

## 5. ADIM: Otomatik Bulut Yedekleri İzleme

- Fırın her gün otomatik olarak veritabanı yedeğini alır ve şifreli olarak Raspberry Pi sunucusuna yükler.
- Universal Admin panelindeki **"Bulut Yedekleri"** sekmesinden tüm müşterilerin günlük yedeklerini dilediğiniz an listeleyebilir ve tek tıkla kendi bilgisayarınıza indirebilirsiniz.
