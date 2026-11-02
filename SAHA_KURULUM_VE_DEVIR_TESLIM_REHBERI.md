# Arı Fırın Muhasebe Sistemi & Universal Admin Hub
# Saha Kurulum, Canlı Devir Teslim ve İşletim El Kitabı

**Sürüm:** 1.0.0 (Production Release)  
**Tarih:** 19 Eylül 2026  
**Hedef Kitle:** Saha Mühendisleri, Sistem Yöneticileri, Muhasebe Personeli ve İstemci Şubeleri  
**Mimari:** Python Desktop Standalone PE Executable + PostgreSQL + Docker Raspberry Pi Central Server (`sunaos:8000`)

---

## 📑 İçindekiler
1. [Genel Mimari ve Dağıtım Bileşenleri](#1-genel-mimari-ve-dağıtım-bileşenleri)
2. [Adım 1: İstemci Bilgisayarına Sıfırdan Kurulum (Arı Fırın)](#2-adım-1-istemci-bilgisayarına-sıfırdan-kurulum-arı-fırın)
3. [Adım 2: İlk Bağlantı ve Ağ Yapılandırma Sihirbazı](#3-adım-2-ilk-bağlantı-ve-ağ-yapılandırma-sihirbazı)
4. [Adım 3: Uzaktan Lisans Yönetimi ve Askıya Alma (Kill-Switch)](#4-adım-3-uzaktan-lisans-yönetimi-ve-askıya-alma-kill-switch)
5. [Adım 4: Otomatik Bulut Yedekleme ve Felaket Kurtarma (Disaster Recovery)](#5-adım-4-otomatik-bulut-yedekleme-ve-felaket-kurtarma-disaster-recovery)
6. [Adım 5: Canlı OTA Güncelleme Yayınlama ve İstemciye İtme](#6-adım-5-canlı-ota-güncelleme-yayınlama-ve-istemciye-itme)
7. [Adım 6: Universal Admin Yönetici Paneli Kurulum ve Kullanımı](#7-adım-6-universal-admin-yönetici-paneli-kurulum-ve-kullanımı)
8. [Adım 7: Sorun Giderme (Troubleshooting) ve Saha Kontrol Listesi](#8-adım-7-sorun-giderme-troubleshooting-ve-saha-kontrol-listesi)

---

## 1. Genel Mimari ve Dağıtım Bileşenleri

Arı Fırın ekosistemi 3 temel katmandan oluşur:

```
+-------------------------------------------------------------+
|               UNIVERSAL ADMIN HUB (YÖNETİCİ)               |
|  - Lisans Kilitleme / Askıya Alma   - Canlı OTA Paketleme   |
|  - Bulut Yedekleri İndirme          - İstemci Durum İzleme  |
+-------------------------------------------------------------+
                              | (HTTP REST + Admin Session)
                              v
+-------------------------------------------------------------+
|             MERKEZİ SUNUCU (RASPBERRY PI / SUNAOS:8000)      |
|  - FastAPI & SQLite                 - /api/v1/projects/...  |
|  - OTA Paket Dağıtım Deposu         - Bulut Yedek Deposu    |
+-------------------------------------------------------------+
                              ^ (Heartbeat / License / Backup)
                              |
+-------------------------------------------------------------+
|             ARI FIRIN MASAÜSTÜ İSTEMCİSİ (ŞUBE / KASA)      |
|  - Standalone AriFirin.exe          - PostgreSQL 5432       |
|  - 7 Gün Çevrimdışı Lisans          - Otomatik OTA Banner   |
+-------------------------------------------------------------+
```

### Dağıtım Paketleri (`dist/` dizini):
- **`AriFirin_Musteri_Dagitim_Paketi_v1.0.0.zip` (138 MB)**: Müşteri kasasına/şubesine gönderilecek tam bağımsız kurulum paketi. Python kurulumu gerektirmez.
- **`UniversalAdmin_Yonetici_Paketi_v1.0.0.zip` (46 MB)**: Firma yöneticisinin/sistem mimarının bilgisayarına kurulacak yönetim paneli paketi.

---

## 2. Adım 1: İstemci Bilgisayarına Sıfırdan Kurulum (Arı Fırın)

### Hazırlık:
1. Müşteri bilgisayarında (Windows 10 / 11 64-bit) `AriFirin_Musteri_Dagitim_Paketi_v1.0.0.zip` dosyasını sağ tıklayıp bir klasöre çıkartın:
   - Önerilen yol: `C:\AriFirin` veya `D:\AriFirin`.
2. Klasörün içinde şu dosyaların yer aldığını doğrulayın:
   - `AriFirin.exe` (Ana uygulama)
   - `config.json` (Yapılandırma ayarları)
   - `Kurulum_Yap_ve_Kısayol_Olustur.bat` (Tek tıkla kurulum)
   - `resources/` (İkonlar, tema ve stiller)
   - `KURULUM_VE_KULLANIM_KILAVUZU.txt`

### Tek Tıkla Kurulum:
- `Kurulum_Yap_ve_Kısayol_Olustur.bat` dosyasına çift tıklayın (Yönetici izni gerektirmez).
- Betik otomatik olarak:
  1. Masaüstünüze altın sarısı logolu **"Arı Fırın"** kısayolunu ekler.
  2. Başlat Menünüze **"Arı Fırın"** ve **"Arı Fırın - Kurulum Sihirbazı"** kısayollarını ekler.
  3. "Uygulama şimdi başlatılsın mı? (E/H)" sorusunu sorar.

---

## 3. Adım 2: İlk Bağlantı ve Ağ Yapılandırma Sihirbazı

Uygulama ilk kez açıldığında yerel veritabanına bağlanmayı dener. Eğer veritabanı başka bir sunucuda veya farklı bir şifrede ise sistem otomatik olarak **Kurulum Sihirbazı (Setup Wizard)** penceresini açar.

### Sihirbazı Doğrudan Açmak İçin:
- Başlat Menüsünden **"Arı Fırın - Kurulum Sihirbazı"** simgesine tıklayın, VEYA
- Komut satırından çalıştırın:
  ```powershell
  C:\AriFirin\AriFirin.exe --setup
  ```

### Sihirbaz Ayarları:
1. **Veritabanı Ayarları**:
   - **Sunucu IP (Host):** Yerel makine için `localhost` veya `127.0.0.1`, yerel ağdaki sunucu için `192.168.1.xxx`.
   - **Port:** Varsayılan `5432`.
   - **Veritabanı Adı:** `accounting_db`.
   - **Kullanıcı:** `postgres`.
   - **Şifre:** Veritabanı şifreniz.
   - **⚡ Bağlantıyı Canlı Test Et:** Butona basarak yeşil "✅ Veritabanı bağlantısı başarılı!" onayını alın.
2. **Merkezi Sunucu & Lisans**:
   - **Merkezi Sunucu URL:** `http://sunaos:8000`.
   - **Lisans Anahtarı:** Size tahsis edilen anahtar (Örn: `ARI-FIRIN-TEKIRDAG-2026`).
3. **Kaydet ve Başlat**:
   - "💾 Ayarları Kaydet ve Başlat" butonuna tıkladığınızda yapılandırma kaydedilir ve muhasebe arayüzü doğrudan açılır.

---

## 4. Adım 3: Uzaktan Lisans Yönetimi ve Askıya Alma (Kill-Switch)

Arı Fırın, uzaktan lisans doğrulama ve anti-tamper güvenlik protokolüne sahiptir.

### Lisans Durumları:
- **Aktif Lisans:** Uygulama tam fonksiyonel çalışır. Her açılışta ve periyodik olarak merkezi sunucuya heartbeat (nabız) gönderir.
- **7 Günlük Çevrimdışı Tolerans (Offline Grace Period):** Müşterinin interneti kesilirse veya merkezi sunucuya ulaşılamazsa, sistem en son doğrulandığı tarihten itibaren tam 7 gün boyunca fırın işlemlerinin aksamaması için çalışmayı sürdürür. 7 gün dolduğunda bağlantı kurulana kadar bloke olur.
- **Askıya Alınmış / İptal Lisans (Remote Kill-Switch):**
  - Yönetici UniversalAdmin üzerinden lisansı kilitlediğinde (`toggle_client`), Arı Fırın açılışta veya ilk doğrulamada anında:
    `"❌ Lisansınız Yönetici Tarafından Askıya Alınmıştır!"`
    uyarısı verir ve uygulamayı derhal kapatır.
- **Tahrifat Koruması (Anti-Tamper):** `license_cache.dat` dosyası SHA-256 HMAC ile imzalanır. Dosya metin editörüyle değiştirilirse sistem bunu geçersiz sayar.

### Donanım / Bilgisayar Değişikliği:
- Müşteri yeni bir bilgisayara geçtiğinde eski donanım kilidi nedeniyle lisans uyarısı alabilir.
- Çözüm: UniversalAdmin panelinde **"Lisanslar"** sekmesine gidin, müşteriyi seçin ve **"🔓 Makine Kilidini Sıfırla"** butonuna basın. Müşteri yeni bilgisayarında Arı Fırın'ı açtığı anda yeni donanım kimliği sunucuya otomatik kaydedilir.

---

## 5. Adım 4: Otomatik Bulut Yedekleme ve Felaket Kurtarma (Disaster Recovery)

### Otomatik Bulut Yedekleme:
- Arı Fırın, her gün mesai bitiminde veya yönetici "Yedek Al" butonuna bastığında:
  1. PostgreSQL'in `pg_dump` aracını çalıştırır.
  2. Yedeği güçlü parola ile AES şifreli `.zip` haline getirir (`C:\AriFirin\backups\backup_YYYYMMDD_HHMMSS.zip`).
  3. Arka planda sessizce bu yedeği merkezi sunucuya (`POST /api/v1/projects/ari_firin/backups/upload`) yükler.

### Felaket Kurtarma (Disaster Recovery Prosedürü):
Müşteri bilgisayarı bozulursa, çalınırsa veya disk hasar görürse:
1. Yeni bilgisayara `AriFirin_Musteri_Dagitim_Paketi_v1.0.0.zip` paketini kurun.
2. PostgreSQL 14+ kurun ve boş bir `accounting_db` veritabanı oluşturun.
3. Universal Admin paneline girin, **"☁️ Bulut Yedekleri"** sekmesinden ilgili müşterinin en son tarihli yedeğini indirin.
4. İndirilen `.zip` yedeğini açın ve SQL dökümünü veritabanına geri yükleyin:
   ```powershell
   psql -U postgres -d accounting_db -f C:\AriFirin\backups\recovered.sql
   ```
5. Kurulum Sihirbazından (`AriFirin.exe --setup`) bağlantıyı test edin. Sistem tüm geçmiş faturalar, cariler ve bakiyelerle anında ayağa kalkacaktır.

---

## 6. Adım 5: Canlı OTA Güncelleme Yayınlama ve İstemciye İtme

Yazılımda bir güncelleme yapıldığında veya yeni özellik eklendiğinde istemci bilgisayarlarına gidip manuel işlem yapmaya gerek yoktur.

### Güncelleme Yayınlama Adımları (Yönetici):
1. Geliştirme ortamında derleme komutunu çalıştırın:
   ```powershell
   python scripts/build_executables.py --build-ari-firin
   ```
   Bu komut `dist/AriFirin.exe` dosyasını üretir.
2. Universal Admin Hub'ı açın ve **"☁️ Bulut & Güncelleme" -> "Yeni Güncelleme Yayınla"** sekmesine gelin.
3. Alanları doldurun:
   - **Proje:** `ari_firin`
   - **Yeni Sürüm:** Örn. `1.0.4`
   - **Kurulum Dosyası (.exe):** `D:\Desktop\Arı_Fırın\dist\AriFirin.exe` dosyasını seçin.
   - **Yenilikler / Değişiklik Notları:** Yapılan iyileştirmeleri yazın.
   - **Zorunlu Güncelleme:** Kritik güvenlik yamaları için işaretleyin.
4. **"🚀 Güncellemeyi Yayınla"** butonuna basın. Binary sunucuya yüklenir ve HTTP indirme linki oluşturulur.

### İstemci Deneyimi:
- İstemci bilgisayarındaki Arı Fırın, en geç 15 dakika içinde (veya kullanıcı giriş yaptığı anda) yeni sürümü algılar.
- Ekranın üst kısmında turuncu **"🚀 Arı Fırın v1.0.4 Güncellemesi Hazır!"** şeridi belirir.
- Kullanıcı **"📥 Şimdi İndir ve Güncelle"** butonuna tıklar.
- İlerleme çubuğuyla dosya indirilir, dosya bütünlüğü (MD5 ve PE MZ imzası) denetlenir ve tek tıkla yeni sürüme geçilir.

---

## 7. Adım 6: Universal Admin Yönetici Paneli Kurulum ve Kullanımı

Universal Admin Hub, birden fazla işletmeyi ve merkezi sunucuyu yönetmek için kullanılır.

### Kurulum:
1. `UniversalAdmin_Yonetici_Paketi_v1.0.0.zip` dosyasını yönetici bilgisayarında açın.
2. `Yonetici_Paneli_Kurulum_ve_Kisayol.bat` çalıştırarak masaüstüne lacivert logolu **"Universal Admin Hub"** simgesini ekleyin.
3. Uygulamayı çalıştırın. Açılışta Master Şifre ile giriş yapın.

### Yetenekler:
- **Uygulamalar Tablosu:** Kayıtlı masaüstü uygulamalarını ve durumlarını listeler.
- **Bulut & Güncelleme:** Raspberry Pi sunucusunun disk doluluğunu, CPU/RAM durumunu ve OTA servislerini canlı izler.
- **Müşteri & Lisans Paneli:** Müşteri lisans anahtarlarını üretir, dondurur veya donanım kilidini çözer.
- **Bulut Yedekleri:** Sahadaki tüm şubelerin günlük veritabanı yedeklerini listeler ve tek tıkla güvenli indirme sağlar.

---

## 8. Adım 7: Sorun Giderme (Troubleshooting) ve Saha Kontrol Listesi

| Sorun Belirtisi | Olası Kök Neden | Saha Çözüm Adımı |
| :--- | :--- | :--- |
| **"Veritabanına bağlanılamadı" hatası** | PostgreSQL servisi durmuş veya güvenlik duvarı 5432 portunu engelliyor. | Sunucu makinesinde `services.msc` altından `postgresql-x64-14` servisinin çalıştığını doğrulayın. Windows Güvenlik Duvarında 5432 TCP portuna izin verin. `AriFirin.exe --setup` ile testi tekrarlayın. |
| **"Lisansınız Askıya Alınmıştır" uyarısı** | UniversalAdmin üzerinden lisans dondurulmuş veya ödeme gecikmiş. | UniversalAdmin panelinde Müşteri Lisansları sekmesine gidin, lisansı bularak `Durumu Değiştir` butonuna basıp tekrar aktif edin. |
| **"Lisans Doğrulanamadı (7 Gün Aşıldı)"** | İstemci bilgisayar 7 günden uzun süredir internete/merkezi sunucuya bağlanmamış. | Bilgisayarın ağ bağlantısını kontrol edin. `http://sunaos:8000/api/health` adresine tarayıcıdan erişilebildiğini doğrulayın. |
| **"Donanım Değişikliği Algılandı"** | Müşteri anakart, işlemci veya bilgisayar değiştirmiş. | UniversalAdmin panelinde `🔓 Makine Kilidini Sıfırla` butonuna basın, ardından Arı Fırın'ı yeniden başlatın. |
| **Güncelleme indirilirken takılıyor** | Ağ zaman aşımı veya proxy kısıtlaması. | Ağ bağlantısını kontrol edin. İstemcide sol menüden `🔄 Güncellemeleri Denetle` butonuna basarak indirmeyi baştan başlatın. |
| **Kısayol simgesi beyaz/boş görünüyor** | Windows ikon önbelleği yenilenmemiş. | `resources\icons\app.ico` dosyasının mevcut olduğunu doğrulayın. `Kurulum_Yap_ve_Kısayol_Olustur.bat` dosyasını bir kez daha çalıştırın. |

---

## 📞 Destek ve İletişim

- **Geliştirici & Mimari:** Arı Fırın Bilişim Sistemleri
- **Merkezi Sunucu API:** `http://sunaos:8000`
- **Yedekleme ve Lisans Desteği:** Universal Admin Hub v1.0.0
