# 🐝 Arı Fırın - Uçtan Uca Geliştirici, Derleme ve OTA Dağıtım Rehberi

Bu el kitabı; kod geliştirmeden Git kullanımına, PyInstaller ile `.exe` derlemeden Raspberry Pi üzerinden sahadaki fırınlara uzaktan güncelleme (OTA) göndermeye kadar tüm süreci adım adım anlatır. Bir sonraki sürümü tek başına yayınlarken bu sırayı takip edebilirsin.

---

## 📑 İçindekiler
1. [Soru & Cevap: Müşteri Bilgisayarında Nasıl Çalışır?](#1-soru--cevap-müşteri-bilgisayarında-nasıl-çalışır)
2. [Adım 1: Git ve GitHub ile Kodları Yedekleme](#adım-1-git-ve-github-ile-kodları-yedekleme)
3. [Adım 2: Yeni Sürüm Numarasını Belirleme (Version Bump)](#adım-2-yeni-sürüm-numarasını-belirleme-version-bump)
4. [Adım 3: PyInstaller ile Windows .EXE Derleme](#adım-3-pyinstaller-ile-windows-exe-derleme)
5. [Adım 4: OTA Dağıtım Paketini (.ZIP) Oluşturma](#adım-4-ota-dağıtım-paketini-zip-oluşturma)
6. [Adım 5: Raspberry Pi Sunucusuna Yükleme ve Canlıya Alma](#adım-5-raspberry-pi-sunucusuna-yükleme-ve-canlıya-alma)
7. [Adım 6: Sıfırdan Yeni Bir Müşteri Bilgisayarına Kurulum](#adım-6-sıfırdan-yeni-bir-müşteri-bilgisayarına-kurulum)
8. [Adım 7: Hata Giderme ve Pratik İpuçları (Cheat Sheet)](#adım-7-hata-giderme-ve-pratik-ipuçları-cheat-sheet)

---

## 1. Soru & Cevap: Müşteri Bilgisayarında Nasıl Çalışır?

**Soru:** *Bende açılan gibi müşterimde de bu şekilde sorunsuz ve güzel açılacak mı?*

**Cevap: EVET, kesinlikle ve birebir aynı şekilde açılacaktır!**

### Neden?
1. **Bağımsız Çalışma (Zero Dependency):** Müşterinin bilgisayarında Python, VS Code, Git veya herhangi bir yazılımcı aracının kurulu olmasına gerek **yoktur**.
2. **Kendi Kendine Yeten Paket:** PyInstaller ile derlediğimiz `dist/AriFirin` klasörünün içindeki `_internal` dizininde:
   - Python 3.12 çalışma motoru,
   - Tüm arayüz kütüphaneleri (`PyQt5`),
   - Veritabanı sürücüleri (`psycopg2`),
   - İkonlar, grafikler ve stiller paketlenmiştir.
3. **Müşterinin Yapacağı Tek Şey:** Masaüstündeki altın sarısı arı logolu **"Arı Fırın"** kısayoluna çift tıklamak. Program doğrudan şifre ekranıyla açılır.

---

## Adım 1: Git ve GitHub ile Kodları Yedekleme

Kodlarında bir geliştirme veya hata düzeltmesi yaptığında, GitHub'a göndermek için terminalde şu komutları sırasıyla çalıştır:

```powershell
# 1. Hangi dosyaların değiştiğini gör
git status

# 2. Değişiklikleri Git sahnesine ekle
git add .

# 3. Yaptığın işi anlatan kısa bir notla kaydet
git commit -m "özellik: yeni sürüm hazırlandı"

# 4. Kodları güvenle GitHub'a gönder
git push origin main
```

> [!CAUTION]
> **Güvenlik Kuralı:** `config.json` dosyasında veritabanı şifren ve Gmail şifren olduğu için bu dosya `.gitignore` listesindedir ve asla GitHub'a gitmez. GitHub'a sadece temiz şablon olan `config.example.json` gider.

---

## Adım 2: Yeni Sürüm Numarasını Belirleme (Version Bump)

Diyelim ki `1.0.3`tesin ve yeni bir güncelleme yapıp `1.0.4` çıkaracaksın. Derlemeden önce şu dosyaları güncelle:

1. **`src/core/version.py`:**
   - 100. satır civarındaki hardcoded fallback sürümünü `"1.0.4"` yap.
2. **`config.json`:**
   - `"version": "1.0.4"`
   - `"download_url": "http://100.125.79.19:8001/AriFirin_v1.0.4.zip"`
3. **`.env`:**
   - `APP_VERSION=1.0.4`

---

## Adım 3: PyInstaller ile Windows .EXE Derleme

Terminalinde (PowerShell) `D:\Desktop\Arı_Fırın` dizinindeyken derleme komutunu çalıştır:

```powershell
pyinstaller --noconfirm --clean ari_firin.spec
```

- **Bu Komut Ne Yapar?**
  - `--noconfirm`: Eski `dist/AriFirin` klasörünün üzerine soru sormadan yazar.
  - `--clean`: Önbelleği temizler, sıfır ve temiz bir derleme yapar.
  - `ari_firin.spec`: İkonları, pencereleri ve kütüphaneleri toplayan tarif dosyasını okur.
- **Sonuç:** `dist/AriFirin/` klasörü içinde yeni `AriFirin.exe` ve `_internal/` klasörü üretilir.

---

## Adım 4: OTA Dağıtım Paketini (.ZIP) Oluşturma

Müşterilerin internetten indirebilmesi için derlenen `dist/AriFirin` klasörünü ZIP arşivine dönüştür:

```powershell
# 1. ZIP dosyasını oluştur (PowerShell)
Compress-Archive -Path "dist\AriFirin\*" -DestinationPath "dist\AriFirin_v1.0.4.zip" -Force

# 2. Sunucuya atılacak version.txt dosyasını oluştur
Set-Content -Path "version.txt" -Value "1.0.4"
```

---

## Adım 5: Raspberry Pi Sunucusuna Yükleme ve Canlıya Alma

### A. Dosyaları Pi'ye Kopyala (PowerShell'den):
```powershell
scp dist\AriFirin_v1.0.4.zip version.txt suna_slmz142@100.125.79.19:/home/suna_slmz142/update_server/
```
*(Pi şifreni girdiğinde iki dosya da sunucuya aktarılır).*

### B. Pi Terminalinde Eski Müşteriler İçin Link Eşitleme (Önemli!):
Eğer sahadaki bazı müşterilerin ayarlarında eski linkler kalmışsa, onların da anında yeni paketi alabilmesi için Pi'ye bağlan (`ssh suna_slmz142@100.125.79.19`):

```bash
cd /home/suna_slmz142/update_server
cp -f AriFirin_v1.0.4.zip AriFirin_v1.0.1.zip
cp -f AriFirin_v1.0.4.zip AriFirin_v1.0.3.zip
```

🎉 **Tebrikler!** Bu adımı tamamladığın anda sahadaki tüm fırınlar uygulamayı açtıklarında otomatik olarak yeni sürüme geçecektir.

---

## Adım 6: Sıfırdan Yeni Bir Müşteri Bilgisayarına Kurulum

Yeni bir fırına gittin ve programı ilk kez sıfırdan kuracaksın:

1. `dist/AriFirin` klasörünü (veya ZIP halini) bir USB belleğe at.
2. Müşterinin bilgisayarında `C:\AriFirin` klasörüne yapıştır.
3. İçine müşteriye özel `config.json` dosyasını koy:
   - `database.host`: Raspberry Pi'nin Tailscale IP'si (`100.125.79.19`) veya sabit IP.
   - `update.license_key`: O müşteriye tahsis ettiğin lisans anahtarı.
4. Klasördeki **`Kurulum_Yap_ve_Kisayol_Olustur.bat`** dosyasına çift tıkla.
   - Masaüstüne ve Başlat Menüsüne altın sarısı logolu **"Arı Fırın"** kısayolları otomatik eklenir.
5. Kısayola tıkla ve giriş yap. Kurulum tamamlandı!

---

## Adım 7: Hata Giderme ve Pratik İpuçları (Cheat Sheet)

| Yaşanan Durum | Olası Sebep | Çözüm Komutu / Adımı |
| :--- | :--- | :--- |
| **"Permission denied (publickey,password)"** | Yanlış SSH kullanıcı adı girildi | `ssh suna_slmz142@100.125.79.19` kullan. Şifre yazarken ekranda karakter görünmez, yazıp Enter'a bas. |
| **Pi dosya sunucusu hangi klasörde çalışıyor?** | Klasör yolu unutuldu | Pi terminalinde: `ps aux \| grep 8001` ardından `pwdx <PID>` çalıştır. |
| **Sonsuz güncelleme uyarısı geliyor** | `download_url` eski kalmış veya `.env` eski sürümde | `updater_service.py` düzeltildi. Pi'de `cp AriFirin_vX.zip AriFirin_v1.0.1.zip` çalıştır. |
| **Güncelleme indirildi ama kurulmadı** | Uygulama arkada kilitli kaldı | Güncelleme loguna bak: `%TEMP%\ari_firin_update.log` |
| **Git: "not a git repository" hatası** | Yanlış klasördesin | `cd "D:\Desktop\Arı_Fırın"` komutuyla proje dizinine geç. |

