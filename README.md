# Arı Fırın ERP - Dağıtık Çok Şubeli Fırın ve Muhasebe Yönetim Sistemi
**Enterprise Multi-Branch Bakery Management, Production Dispatch and Accounting ERP System**

## 1. Proje Özeti (Executive Summary)
Arı Fırın ERP, unlu mamul üreticileri, fırın zincirleri ve çok şubeli perakende işletmeleri için geliştirilmiş, üretim bandından kasa noktasına kadar tüm operasyonları yöneten kurumsal masaüstü ERP ve muhasebe sistemidir. 

Sistem; yüksek işlem hacmi, günlük fire hesaplamaları, imalathane-şube sevkiyat koordinasyonu, çevrimdışı çalışma toleransı ve finansal kuruş hassasiyeti gereksinimlerini karşılamak üzere dağıtık ve modüler bir mimariyle tasarlanmıştır.

## 2. Temel Teknik Yetkinlikler ve Anahtar Kelimeler (Core Competencies & Keywords)
- **Programlama Dilleri ve Kütüphaneler:** Python 3.12, PyQt5, Qt Framework, FastAPI, Uvicorn, SQL, HTML/CSS.
- **Veritabanı Mimarisi ve Veri Kalıcılığı:** PostgreSQL 14+, Dinamik Multi-Tenant Şema Bölümleme (Dynamic Schema-per-Tenant), Bağlantı Havuzu (Connection Pooling via psycopg2), SQLite (Merkezi lisans/OTA kaydı), ACID Uyumluluğu, Hareket Bütünlüğü (Transaction Management).
- **Sistem Tasarımı ve Mimari:** Dağıtık İstemci-Sunucu Ekosistemi (Distributed Client-Server), Çevrimdışı Çalışabilirlik (Offline-First Architecture), Çok İş Parçacıklı Arka Plan Servisleri (Multithreaded Background Daemons), RESTful API Entegrasyonu.
- **Finansal Hesaplama ve Hassasiyet:** Python Decimal Aritmetiği, Banker Yuvarlaması (ROUND_HALF_EVEN), Kuruş Farkı ve Kayan Nokta (Float Drift) Önleme, KDV Tevkifatı ve Cari Yaşlandırma.
- **Kriptografi ve Kurumsal Güvenlik:** PBKDF2-HMAC-SHA256 (100.000 İterasyon) Tuzlu Parola Özetleme, Zamanlama Saldırısı Koruması (hmac.compare_digest), Donanım Parmak İzi (Hardware Fingerprinting - UUID/MAC/Anakart Hash), AES Şifreli Veritabanı Yedekleme, Parametrik Sorgular (SQL Enjeksiyon Koruması).
- **Yazılım Dağıtımı ve DevOps:** PyInstaller (Bağımsız Windows PE Derlemesi), Inno Setup 6 (Kurulum Paketi Üretimi), OTA (Over-The-Air) Otomatik Güncelleme Hattı, Docker, Docker Compose, Git Sürüm Kontrolü.
- **Veri Analitiği ve Raporlama:** Pandas, OpenPyXL (Excel Çift Yönlü Entegrasyon), ReportLab (PDF Ekstre ve Fatura Raporlama).

## 3. Sistem Mimarisi ve Tasarım İlkeleri (System Architecture)
Sistem 3 temel katmandan meydana gelir:

### 3.1. Masaüstü İstemcisi Katmanı (Desktop Client - PyQt5)
- Windows işletim sistemlerinde bağımsız (standalone) PE olarak çalışır; Python kurulumu gerektirmez.
- Qt Fusion motoru ve kurumsal QSS tasarım sistemiyle donatılmış, yüksek çözünürlük (High-DPI) uyumlu kullanıcı arayüzü sunar.
- Kullanıcı yetkilendirme, veri doğrulama ve finansal hesaplama işlemlerini istemci tarafında düşük gecikme ile yürütür.

### 3.2. Veritabanı Katmanı (PostgreSQL Multi-Tenant Dynamic Schemas)
- **Genel Şema (public):** Kullanıcı oturum kayıtları, yetki tanımları, merkezi şube indeksleri ve kiracı kayıtlarını barındırır.
- **Kiracı Şemaları (tenant_usr_<id>):** Her kullanıcı / müşteri grubu için dinamik olarak üretilen izole şemalardır. Müşteri carileri, stok kartları, faturalar, kasa hareketleri ve yevmiye kayıtları bu şemalarda tamamen ayrıştırılmış olarak saklanır.
- **Bağlantı Optimizasyonu:** psycopg2 threaded connection pool ile eşzamanlı sorgular optimize edilir ve bağlantı sızıntıları önlenir.

### 3.3. Merkezi Kontrol ve Dağıtım Sunucusu (Central Server - FastAPI & Docker)
- OTA yazılım güncellemelerinin SHA-256 doğrulamasını ve ikili dosya (binary) dağıtımını yönetir.
- Müşteri lisans doğrulaması (heartbeat) ve uzaktan yönetim mekanizmalarını yürütür.
- İstemcilerden gelen AES şifreli veritabanı yedeklerini depolar ve saklama politikası (retention policy) doğrultusunda rotasyona tabi tutar.

## 4. Öne Çıkan Mühendislik Çözümleri (Key Engineering Highlights)

### 4.1. PostgreSQL Multi-Tenant Dinamik Şema İzolasyonu
Geleneksel tek şemalı yapılarda sorgulara WHERE tenant_id = X filtresi eklemek yazılımcı hatasına açık ve performans darboğazı yaratan bir yöntemdir. Arı Fırın mimarisinde, her kiracı için fiziksel olarak ayrılmış bağımsız PostgreSQL şemaları (CREATE SCHEMA IF NOT EXISTS tenant_usr_X) kullanılır. Bu sayede:
- Tam veri gizliliği ve KVKK/GDPR uyumu sağlanır.
- İndeksler ve tablolar küçük kalarak sorgu süreleri milisaniye seviyesinde tutulur.
- Şema adı dinamik çözümlenirken beyaz liste (whitelist) ve regex denetimleri uygulanarak SQL enjeksiyonu riski tamamen bertaraf edilir.

### 4.2. Yüksek Hassasiyetli Finansal Hesaplama Motoru
Finans ve muhasebe uygulamalarında kayan nokta (IEEE 754 floating point) aritmetiği kullanıldığında kuruş düzeyinde sapmalar meydana gelir (0.1 + 0.2 != 0.3). Sistem genelinde:
- Tüm parasal değerler Python Decimal tipi ile işlenir.
- Yuvarlama işlemlerinde uluslararası bankacılık standardı olan Banker Yuvarlaması (ROUND_HALF_EVEN) kullanılır.
- KDV hesaplamaları, iskonto matrahları ve yevmiye denklemleri kuruş farkı oluşturmaksızın %100 doğrulukla kapatılır.

### 4.3. OTA (Over-The-Air) Otomatik Güncelleme Hattı
Sahada çalışan masaüstü istemcilerinin yerinde müdahale gerektirmeksizin güncellenebilmesi amacıyla özel bir OTA motoru geliştirilmiştir:
- Uygulama arka plan iş parçacığında merkezi sunucu ile sürüm kontrolü yapar.
- Yeni sürüm tespit edildiğinde paket arka planda indirilir ve SHA-256 sağlama toplamı (checksum) ile doğrulanır.
- Kullanıcı uygulamayı kapattığında güncelleme betiği devreye girerek yeni ikili dosyaları atomik olarak değiştirir ve sistemi yeniden başlatır.

### 4.4. Donanım Tabanlı Lisanslama ve Çevrimdışı Çalışma Toleransı
- İstemci makinenin anakart seri numarası, CPU kimliği ve MAC adresinden benzersiz bir donanım özeti (Machine ID) üretilir.
- Sunucu ile iletişim kurulamayan ağ kesintilerinde iş akışının durmaması adına 7 günlük çevrimdışı çalışma toleransı (offline grace period) tanınır.
- Kriptografik zaman damgası kontrolleri sayesinde sistem saatinin manipüle edilmesi engellenir.
- Sözleşme feshi veya güvenlik ihlallerinde sunucu üzerinden tek komutla uzaktan dondurma (remote kill-switch) uygulanabilir.

### 4.5. Otomatik Şifreli Bulut Yedekleme ve Felaket Kurtarma
- Arka planda çalışan bağımsız zamanlayıcı (backup_scheduler), yapılandırılan aralıklarla veritabanı dökümünü alır.
- Alınan SQL dökümleri yerel diskte AES algoritması ile şifrelenir ve merkezi depolama sunucusuna güvenli HTTP POST ile aktarılır.
- Disk doluluğunu önlemek için yerel ve uzak depolama alanlarında zaman aşımına uğrayan eski yedekler otomatik temizlenir.

### 4.6. Kurumsal Seviye Bilgi Güvenliği
- **Parola Güvenliği:** Parolalar veritabanında asla açık metin olarak saklanmaz. 100.000 iterasyonlu PBKDF2-HMAC-SHA256 ve rastgele 16 baytlık tuz (salt) ile özetlenir.
- **Zamanlama Saldırısı Engelleme:** Parola doğrulamalarında hmac.compare_digest kullanılarak zaman analizi tabanlı sızma girişimleri önlenir.
- **Sır Yönetimi:** Kod tabanında hiçbir sabit IP, kullanıcı adı veya veritabanı şifresi yer almaz. Tüm kimlik bilgileri ortam değişkenleri (.env) üzerinden yönetilir.

## 5. Fonksiyonel Modüller (Functional Modules)

- **Merkezi İmalathane ve Sevkiyat Yönetimi:** Günlük üretim reçetelerinin işlenmesi, un ve hammadde sarfiyatının kaydı, mamul ürünlerin şubelere irsaliye bağlantılı otomatik transferi ve stok senkronizasyonu.
- **Günlük Kasa ve Ciro Analizi:** Nakit, kredi kartı, banka havalesi ve açık hesap (veresiye) tahsilatlarının ayrıştırılması; günlük masrafların düşülmesi ve Z-raporu kasa mutabakatı.
- **Stok Sayımı ve Fire Yönetimi:** Tarih bazlı dinamik stok sayım formları, teorik stok ile fiili sayım arasındaki açık/fazla tespiti, otomatik fire maliyeti analizi ve Excel aktarımı.
- **Fatura ve Cari Hesap Yönetimi:** Alış ve satış faturalarının düzenlenmesi, KDV tevkifatı hesaplaması, cari hesap ekstreleri ve bakiye yaşlandırma raporları.
- **Banka ve Şirket Giderleri:** Çoklu banka hesap bakiyelerinin takibi, gider kategorizasyonu, çek/senet vade takibi ve nakit akış projeksiyonu.
- **Personel ve Maaş Yönetimi:** Personel avans, maaş hakedişleri, mesai takibi ve şube bazlı iş gücü maliyet analizleri.
- **Merkez Şube ve Konsolidasyon:** Tüm bağlı şubelerin anlık ciro, fatura, stok ve cari hareketlerinin tek ekranda konsolide izlenmesi ve şubeler arası virman/transfer yönetimi.

## 6. Proje Dizin Yapısı (Directory Structure)

```text
Ari_Firin/
|-- main.py                     # Masaüstü uygulaması ana giriş noktası
|-- ari_firin.spec              # PyInstaller derleme konfigürasyonu
|-- build_app.py                # Windows PE derleme aracı
|-- setup.iss                   # Inno Setup 6 kurulum paketi betiği
|-- version.txt                 # Üretim sürüm bilgisi (1.0.5)
|-- config.example.json         # Yapılandırma şablonu (şifresiz/güvenli)
|-- .env.example                # Çevre değişkenleri şablonu
|-- requirements.txt            # Python kütüphane bağımlılıkları
|
|-- central_server/             # Merkezi OTA, Lisans ve Bulut Yedekleme Sunucusu
|   |-- main.py                 # FastAPI REST uç noktaları ve yönetim arayüzü
|   |-- database.py             # SQLite lisans ve proje kayıt katmanı
|   |-- Dockerfile              # Docker container konfigürasyonu
|   |-- docker-compose.yml      # Canlı sunucu orkestrasyonu
|   `-- templates/              # Sunucu yönetim HTML şablonları
|
|-- src/                        # İstemci Uygulama Çekirdeği
|   |-- core/                   # Yapılandırma, veritabanı havuzu, logger, versiyon
|   |   |-- config.py           # Güvenli konfigürasyon yöneticisi
|   |   |-- database.py         # PostgreSQL multi-tenant havuz ve şema yönetimi
|   |   |-- decimal_utils.py    # Finansal Decimal ve Banker yuvarlama motoru
|   |   `-- version.py          # Dinamik sürüm çözümleme katmanı
|   |
|   |-- models/                 # Veritabanı domain modelleri
|   |   |-- branch.py           # Şube veri modeli
|   |   |-- customer.py         # Cari hesap modeli
|   |   |-- invoice.py          # Fatura ve fatura kalemi modeli
|   |   |-- journal.py          # Muhasebe yevmiye kayıtları modeli
|   |   `-- user.py             # PBKDF2 oturum ve kullanıcı modeli
|   |
|   |-- services/               # İş mantığı servis katmanı (Business Logic)
|   |   |-- turnover_service.py # Günlük ciro ve kasa servisi
|   |   |-- production_service.py# İmalat ve sevkiyat transfer servisi
|   |   |-- stock_count_service.py# Stok sayım ve fire analiz servisi
|   |   |-- invoice_service.py  # Fatura kesim ve bakiye takip servisi
|   |   `-- updater_service.py  # OTA arka plan indirme servisi
|   |
|   |-- ui/                     # PyQt5 Grafiksel Kullanıcı Arayüzü
|   |   |-- main_window.py      # Ana uygulama kabuğu ve modül yönlendirici
|   |   |-- central_window.py   # Merkez şube ve konsolidasyon penceresi
|   |   |-- branch_select.py    # Şube seçim diyaloğu
|   |   |-- pages/              # Şube modül sayfaları (Ciro, İmalat, Stok vb.)
|   |   |-- central_pages/      # Merkez modül sayfaları (Konsolide Ciro, Raporlar)
|   |   `-- styles.py           # Modern QSS tema ve arayüz stilleri
|   |
|   `-- utils/                  # Yardımcı sistem servisleri
|       |-- auto_updater.py     # Binary takas ve OTA yürütücüsü
|       |-- backup_scheduler.py # Şifreli yedekleme arka plan iş parçacığı
|       `-- license_manager.py  # Makine parmak izi ve lisans yöneticisi
|
|-- resources/                  # Uygulama ikonları, logolar ve statik varlıklar
|   `-- icons/                  # Çok çözünürlüklü Windows ICO ve PNG simgeleri
|
|-- docs/                       # Teknik Belgeler ve Canlıya Alma Rehberleri
|   |-- CANLIYA_ALMA_VE_DAGITIM_REHBERI.md
|   `-- GELISTIRICI_VE_SURUM_YONETIMI_REHBERI.md
|
`-- scripts/                    # Operasyonel ve derleme yardımcı betikleri
    |-- build_executables.py    # Otomatik PyInstaller derleyici
    |-- build_installer.py      # Inno Setup ve ZIP dağıtım paketleyici
    `-- generate_app_icons.py   # Çok çözünürlüklü ICO simge üreteci
```

## 7. Kurulum ve Yerel Geliştirme (Setup and Local Development)

### 7.1. Ön Koşullar
- Python 3.10 veya üzeri (Önerilen: Python 3.12 64-bit)
- PostgreSQL 14 veya üzeri
- Windows 10 / 11 (Masaüstü istemcisi için)

### 7.2. Sanal Ortam Kurulumu ve Bağımlılıklar
```bash
git clone https://github.com/sunasolmaz/Ari_Firin.git
cd Ari_Firin

python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

pip install -r requirements.txt
```

### 7.3. Ortam Değişkenleri Yapılandırması
1. `.env.example` dosyasını `.env` olarak kopyalayınız:
   ```bash
   cp .env.example .env
   ```
2. Veritabanı bağlantı bilgilerinizi `.env` içerisine tanımlayınız:
   ```env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=accounting_db
   DB_USER=postgres
   DB_PASSWORD=veritabani_parolaniz
   APP_VERSION=1.0.5
   ```

### 7.4. Uygulamayı Başlatma
```bash
python main.py
```
Uygulama ilk açılışta gerekli PostgreSQL şemalarını ve temel tabloları otomatik olarak hazırlar.

### 7.5. Merkezi Dağıtım ve OTA Sunucusunu Başlatma (İsteğe Bağlı)
```bash
cd central_server
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 8. Üretim Derlemesi ve Paketleme (Production Build & Distribution)

### 8.1. PyInstaller ile Bağımsız Windows PE (.exe) Derleme
```powershell
pyinstaller --noconfirm --clean ari_firin.spec
```
Derleme çıktısı `dist/AriFirin/` dizininde üretilir ve istemci makinelerde Python kurulumu gerektirmeden çalışır.

### 8.2. Inno Setup ile Windows Kurulum Paketi Üretme
Inno Setup 6 derleyicisi ile:
```powershell
iscc setup.iss
```
Masaüstü simgesi, başlat menüsü girdileri ve kaldırma aracı içeren tek kurulum paketi (`dist/AriFirin_Setup_v1.0.5.exe`) oluşturulur.

## 9. Güvenlik Politikası (Security Policy)
- Bu depoda yer alan konfigürasyon dosyaları gerçek kimlik bilgileri, IP adresleri ve API parolalarından arındırılmıştır.
- Canlı dağıtımlarda çevre değişkenleri (`.env`) ve işletim sistemi gizli anahtar depoları kullanılmaktadır.

## 10. İletişim ve Geliştirici Bilgisi
- **Proje Sahibi ve Geliştirici:** Suna Solmaz
- **Rol:** Full Stack / Desktop & Backend Software Developer
- **Depo:** https://github.com/sunasolmaz/Ari_Firin
