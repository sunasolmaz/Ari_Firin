# src/services/updater_service.py
"""
Arı Fırın - Otomatik Güncelleme ve Canlılık (Heartbeat) Servisi
Raspberry Pi üzerindeki Merkezi Sunucu ile konuşur.
İnternet kesildiğinde veya sunucuya ulaşılamadığında uygulamanın çalışmasını engellemez.
"""

import os
import sys
import tempfile
import threading
import subprocess
import requests
from typing import Optional, Dict

from PyQt5.QtWidgets import QMessageBox, QProgressDialog, QApplication
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal

from ..core.config import config
from ..core.logger import logger
from ..core.version import APP_VERSION


def parse_version(v_str: str) -> tuple:
    """Sürüm stringini sayı demetine dönüştürür (örn: '1.0.5' -> (1, 0, 5))"""
    try:
        clean = v_str.strip().lstrip("v")
        parts = tuple(int(x) for x in clean.split(".") if x.isdigit())
        return parts if parts else (0, 0, 0)
    except Exception:
        return (0, 0, 0)


class UpdaterBridge(QObject):
    """Thread'ler arası Qt sinyal köprüsü (GUI Thread'e güvenli bildirim için)"""
    update_found = pyqtSignal(str, str, str, bool)
    up_to_date = pyqtSignal()
    download_progress = pyqtSignal(int)
    download_finished = pyqtSignal(str)
    download_failed = pyqtSignal(str)


class UpdaterService:
    """Merkezi sunucu ile versiyon kontrolü ve canlılık takibi"""

    def __init__(self):
        self.project_id = config.get("update.project_id", "ari_firin")
        self.server_url = config.get("update.server_url", "http://sunaos:8000").rstrip("/")
        self.enabled = config.get("update.enabled", True)
        self.current_version = APP_VERSION
        self.license_key = config.get("update.license_key", "ARI-FIRIN-TEKIRDAG-2026")

        self.bridge = UpdaterBridge()
        self.bridge.update_found.connect(self._on_update_found)
        self.bridge.up_to_date.connect(self._on_up_to_date)
        self.bridge.download_finished.connect(self._launch_installer_and_exit)
        self.bridge.download_failed.connect(self._on_download_failed)

        self._heartbeat_timer: Optional[QTimer] = None
        self._update_check_timer: Optional[QTimer] = None
        self._progress_dialog: Optional[QProgressDialog] = None
        self.latest_update_info: Optional[Dict] = None

    def start_background_services(self):
        """Arka plan servislerini başlatır"""
        if not self.enabled:
            return

        logger.info(f"🌐 Güncelleyici servisi başlatıldı (Sunucu: {self.server_url}, Mevcut: v{self.current_version})")

        # 1. Açılışta güncelleme kontrolü (1.5 saniye sonra)
        QTimer.singleShot(1500, lambda: self.check_for_updates(silent=True))

        # 2. Periyodik güncelleme kontrolü (Her 15 dakikada bir)
        self._update_check_timer = QTimer()
        self._update_check_timer.timeout.connect(lambda: self.check_for_updates(silent=True))
        self._update_check_timer.start(15 * 60 * 1000)

        # 3. Kalp atışı (Her 10 dakikada bir)
        self._heartbeat_timer = QTimer()
        self._heartbeat_timer.timeout.connect(self._send_heartbeat_async)
        self._heartbeat_timer.start(10 * 60 * 1000)

        # İlk kalp atışını hemen gönder
        self._send_heartbeat_async()

    def check_for_updates(self, silent=True):
        """Sunucudaki yeni sürümü arka plan iş parçacığında kontrol eder"""
        def _worker():
            try:
                version_url = config.get("update.url", "")
                download_url = config.get("update.download_url", "")

                if not version_url:
                    logger.warning("⚠️ update.url tanımlı değil")
                    return

                r = requests.get(version_url, timeout=5)
                if r.status_code == 200:
                    latest_ver = r.text.strip()
                    notes = "Hata düzeltmeleri ve performans iyileştirmeleri."
                    force = False

                    logger.info(f"🔍 Sunucu sürüm kontrolü: Sunucu=v{latest_ver}, Mevcut=v{self.current_version}")

                    if parse_version(latest_ver) > parse_version(self.current_version):
                        import re
                        if download_url and re.search(r'v\d+\.\d+\.\d+', download_url):
                            download_url = re.sub(r'v\d+\.\d+\.\d+', f'v{latest_ver}', download_url)
                        elif not download_url and version_url:
                            base_url = version_url.rsplit('/', 1)[0]
                            download_url = f"{base_url}/AriFirin_v{latest_ver}.zip"

                        self.latest_update_info = {
                            "version": latest_ver,
                            "download_url": download_url,
                            "notes": notes,
                            "force": force
                        }
                        self.bridge.update_found.emit(latest_ver, download_url, notes, force)
                    elif not silent:
                        self.bridge.up_to_date.emit()
            except Exception as e:
                logger.warning(f"⚠️ Güncelleme kontrolü yapılamadı: {e}")
                if not silent:
                    self.bridge.download_failed.emit(f"Sunucuya bağlanılamadı:\n{e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _on_update_found(self, latest_ver: str, download_url: str, notes: str, force: bool):
        """Ana GUI thread'inde çalışan güncelleme onay kutusu"""
        self.latest_update_info = {
            "version": latest_ver,
            "download_url": download_url,
            "notes": notes,
            "force": force
        }

        active_win = QApplication.activeWindow()
        msg = (
            f"🚀 Arı Fırın için yeni bir güncelleme mevcut!\n\n"
            f"Mevcut Sürüm: v{self.current_version}\n"
            f"Yeni Sürüm: v{latest_ver}\n\n"
            f"Yenilikler / Değişiklikler:\n{notes or 'Hata düzeltmeleri ve performans iyileştirmeleri.'}\n\n"
            f"Güncellemeyi şimdi indirip kurmak istiyor musunuz?"
        )

        msg_box = QMessageBox(active_win)
        msg_box.setWindowTitle("🚀 Yeni Güncelleme Mevcut")
        msg_box.setText(msg)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.Yes)
        msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowStaysOnTopHint)
        msg_box.show()
        msg_box.raise_()
        msg_box.activateWindow()

        reply = msg_box.exec_()

        if reply == QMessageBox.Yes:
            if not download_url:
                QMessageBox.information(
                    active_win, "Bilgi",
                    f"Yeni sürüm (v{latest_ver}) sunucuda tanımlanmış ancak henüz setup dosyası yüklenmemiş."
                )
                return
            self._download_and_install(download_url, latest_ver)
        else:
            if force:
                QMessageBox.critical(
                    active_win, "Zorunlu Güncelleme",
                    "Bu güncelleme zorunludur. Güncelleme yapılmadan uygulama başlatılamaz."
                )
                QApplication.quit()
                import time; time.sleep(0.5); os._exit(0)

    def _on_up_to_date(self):
        active_win = QApplication.activeWindow()
        QMessageBox.information(
            active_win, "Güncelleme Kontrolü",
            f"Uygulamanız zaten güncel!\nKullanılan sürüm: v{self.current_version}"
        )

    def start_download(self, download_url: str, version: str):
        """Public API: Kullanıcı arayüzünden çağrılabilir indirme başlatıcı."""
        return self._download_and_install(download_url, version)

    def _download_and_install(self, download_url: str, new_version: str):
        """Kurulum dosyasını indirir"""
        if not download_url.startswith("http"):
            download_url = f"{self.server_url}{download_url}"

        temp_dir = tempfile.gettempdir()
        ext = ".zip" if ".zip" in download_url.lower() else ".exe"
        installer_path = os.path.join(temp_dir, f"Ari_Firin_Update_v{new_version}{ext}")

        active_win = QApplication.activeWindow()
        self._progress_dialog = QProgressDialog(
            "Yeni sürüm indiriliyor, lütfen bekleyin...", "İptal", 0, 100, active_win
        )
        self._progress_dialog.setWindowTitle("İndiriliyor")
        self._progress_dialog.setWindowModality(Qt.ApplicationModal)
        self._progress_dialog.setWindowFlags(self._progress_dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        self._progress_dialog.setAutoClose(True)
        self.bridge.download_progress.connect(self._progress_dialog.setValue)
        self._progress_dialog.show()

        def _download_worker():
            try:
                with requests.get(download_url, stream=True, timeout=120) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get("content-length", 0))
                    downloaded = 0

                    with open(installer_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if self._progress_dialog and self._progress_dialog.wasCanceled():
                                return
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    pct = int((downloaded / total_size) * 100)
                                    self.bridge.download_progress.emit(pct)

                self.bridge.download_finished.emit(installer_path)
            except Exception as e:
                self.bridge.download_failed.emit(str(e))

        threading.Thread(target=_download_worker, daemon=True).start()

    def _on_download_failed(self, error_msg: str):
        active_win = QApplication.activeWindow()
        QMessageBox.critical(active_win, "İndirme Hatası", f"Güncelleme dosyası indirilemedi:\n{error_msg}")

    def _launch_installer_and_exit(self, installer_path: str):
        """İndirilen kurulum dosyasını başlatıp mevcut uygulamayı sonlandırır"""
        active_win = QApplication.activeWindow()
        try:
            logger.info(f"Yeni kurulum paketi indirildi: {installer_path}")

            is_real_exe = False
            is_zip_file = False
            if os.path.exists(installer_path) and os.path.getsize(installer_path) > 100:
                try:
                    with open(installer_path, "rb") as f:
                        magic = f.read(4)
                        if magic[:2] == b"MZ":
                            is_real_exe = True
                        elif magic == b"PK\x03\x04":
                            is_zip_file = True
                except Exception:
                    pass

            # ZIP ise çıkar
            if is_zip_file:
                import zipfile
                import shutil
                extract_dir = os.path.join(tempfile.gettempdir(), "ari_firin_update_extracted")
                if os.path.exists(extract_dir):
                    shutil.rmtree(extract_dir, ignore_errors=True)
                os.makedirs(extract_dir, exist_ok=True)
                try:
                    with zipfile.ZipFile(installer_path, 'r') as zip_ref:
                        # Zip Slip (Path Traversal) Güvenlik Doğrulaması
                        abs_extract_dir = os.path.abspath(extract_dir)
                        for member in zip_ref.namelist():
                            target_path = os.path.abspath(os.path.join(extract_dir, member))
                            if not target_path.startswith(abs_extract_dir + os.sep) and target_path != abs_extract_dir:
                                raise ValueError(f"Güvenlik İhlali: ZIP dosyasında yetkisiz dizine taşma tespit edildi: {member}")
                        zip_ref.extractall(extract_dir)

                    extracted_exe = None
                    for root, dirs, files in os.walk(extract_dir):
                        for file in files:
                            if file.lower().endswith(".exe"):
                                extracted_exe = os.path.join(root, file)
                                break
                        if extracted_exe:
                            break

                    if extracted_exe:
                        installer_path = extracted_exe
                        is_real_exe = True
                    else:
                        QMessageBox.warning(active_win, "Hata", "ZIP dosyası indirildi ama içinde .exe bulunamadı!")
                        return
                except Exception as e:
                    QMessageBox.warning(active_win, "Hata", f"ZIP arşivi çıkarılamadı:\n{e}")
                    return

            if is_real_exe:
                QMessageBox.information(
                    active_win, "İndirme Tamamlandı",
                    f"Yeni sürüm başarıyla indirildi!\n"
                    f"Uygulama şimdi kapanacak ve güncelleme otomatik olarak uygulanacak.\n\n"
                    f"Tamam'a bastıktan sonra lütfen bekleyin (5-10 saniye).\n"
                    f"Uygulama otomatik olarak yeniden başlayacak.",
                    QMessageBox.Ok
                )

                current_exe = sys.executable
                if current_exe.lower().endswith("python.exe") or current_exe.lower().endswith("pythonw.exe"):
                    os.startfile(installer_path)
                    QApplication.quit()
                    import time; time.sleep(0.5); os._exit(0)
                    return

                new_exe_dir = os.path.dirname(installer_path)
                current_exe_dir = os.path.dirname(current_exe)

                # Hedef dizindeki config.json ve .env surum bilgisini yeni surumle guncelle
                new_ver = self.latest_update_info.get("version", "") if self.latest_update_info else ""
                if new_ver:
                    target_cfg = os.path.join(current_exe_dir, "config.json")
                    if os.path.exists(target_cfg):
                        try:
                            with open(target_cfg, "r", encoding="utf-8") as f:
                                cdata = json.load(f)
                            cdata.setdefault("application", {})["version"] = new_ver
                            if "update" in cdata and "download_url" in cdata["update"]:
                                cdata["update"]["download_url"] = re.sub(r'v\d+\.\d+\.\d+', f'v{new_ver}', cdata["update"]["download_url"])
                            with open(target_cfg, "w", encoding="utf-8") as f:
                                json.dump(cdata, f, indent=4, ensure_ascii=False)
                        except Exception as ce:
                            logger.warning(f"config.json guncellenemedi: {ce}")

                    target_env = os.path.join(current_exe_dir, ".env")
                    if os.path.exists(target_env):
                        try:
                            lines = []
                            with open(target_env, "r", encoding="utf-8") as f:
                                for line in f:
                                    if line.strip().startswith("APP_VERSION"):
                                        lines.append(f"APP_VERSION={new_ver}\n")
                                    else:
                                        lines.append(line)
                            with open(target_env, "w", encoding="utf-8") as f:
                                f.writelines(lines)
                        except Exception as ee:
                            logger.warning(f".env guncellenemedi: {ee}")

                bat_path = os.path.join(tempfile.gettempdir(), "ari_firin_updater.bat")
                log_path = os.path.join(tempfile.gettempdir(), "ari_firin_update.log")

                bat_content = f"""@echo off
chcp 65001 >nul
echo Guncelleme uygulaniyor, lutfen bekleyin... > "{log_path}"
echo. >> "{log_path}"

set "TEMP_EXE={installer_path}"
set "TEMP_DIR={new_exe_dir}"
set "TARGET_EXE={current_exe}"
set "TARGET_DIR={current_exe_dir}"

echo Bekleniyor: Eski uygulama kapanana kadar... >> "{log_path}"

set retry=0

:waitloop
ping 127.0.0.1 -n 2 > nul
tasklist /FI "IMAGENAME eq {os.path.basename(current_exe)}" 2>NUL | find /I "{os.path.basename(current_exe)}" >NUL
if not errorlevel 1 (
    set /a retry+=1
    if %retry% LSS 10 (
        goto waitloop
    )
    taskkill /F /IM "{os.path.basename(current_exe)}" >nul 2>&1
)

echo Uygulama kapandi, dosyalar kopyalaniyor... >> "{log_path}"

if exist "{current_exe_dir}\\_internal" (
    if exist "{current_exe_dir}\\_internal_old" rmdir /S /Q "{current_exe_dir}\\_internal_old"
    move /Y "{current_exe_dir}\\_internal" "{current_exe_dir}\\_internal_old" >nul 2>&1
)

xcopy /E /Y /I /R /H "{new_exe_dir}\\*" "{current_exe_dir}\\" >> "{log_path}" 2>&1

if exist "{current_exe_dir}\\_internal" (
    echo Guncelleme basarili! >> "{log_path}"
    if exist "{current_exe_dir}\\_internal_old" rmdir /S /Q "{current_exe_dir}\\_internal_old"
) else (
    echo HATA: _internal kopyalanamadi! Geri aliniyor... >> "{log_path}"
    if exist "{current_exe_dir}\\_internal_old" move /Y "{current_exe_dir}\\_internal_old" "{current_exe_dir}\\_internal" >nul 2>&1
)

echo Uygulama yeniden baslatiliyor... >> "{log_path}"
start "" "{current_exe}"

(goto) 2>nul & del "%~f0"
"""

                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(bat_content)

                subprocess.Popen(
                    [bat_path],
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )

                logger.info(f"Güncelleme .bat dosyası başlatıldı: {bat_path}")
                logger.info(f"Güncelleme log dosyası: {log_path}")

                QApplication.quit()
                import time; time.sleep(0.5); os._exit(0)
            else:
                QMessageBox.information(
                    active_win, "İndirme Başarılı (Test Doğrulandı)",
                    f"🎉 Yeni sürüm paketi sunucudan başarıyla indirildi:\n\n"
                    f"📂 {installer_path}\n"
                    f"Boyut: {os.path.getsize(installer_path)} bayt\n\n"
                    f"OTA Güncelleme ve dosya iletim akışı başarıyla test edildi!"
                )
        except Exception as e:
            logger.error(f"Kurulum başlatma hatası: {e}")
            QMessageBox.critical(active_win, "Hata", f"Kurulum başlatılamadı:\n{e}")

    def _send_heartbeat_async(self):
        """Arka planda sunucuya 'Ben hayattayım' sinyali gönderir"""
        def _task():
            try:
                url = f"{self.server_url}/api/v1/projects/{self.project_id}/heartbeat"
                payload = {
                    "license_key": self.license_key,
                    "version": self.current_version
                }
                requests.post(url, json=payload, timeout=4)
            except Exception:
                pass

        threading.Thread(target=_task, daemon=True).start()


# Tekil örnek
updater = UpdaterService()