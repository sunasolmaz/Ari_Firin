# src/utils/shortcut_utils.py
"""
Windows Masaüstü ve Başlat Menüsü Kısayol Yardımcısı
PowerShell WScript.Shell COM nesnesi üzerinden masaüstü ve başlat menüsü
kısayolları (.lnk) oluşturur ve yönetir.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_desktop_dir() -> Path:
    """Kullanıcının masaüstü dizinini döner"""
    # Windows ortamında USERPROFILE / Desktop önceliklidir
    desktop_env = os.environ.get("USERPROFILE")
    if desktop_env:
        desktop_path = Path(desktop_env) / "Desktop"
        if desktop_path.exists():
            return desktop_path
    return Path.home() / "Desktop"


def get_start_menu_dir() -> Path:
    """Kullanıcının Başlat Menüsü Programlar dizinini döner"""
    appdata = os.environ.get("APPDATA")
    if appdata:
        programs_path = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if programs_path.exists():
            return programs_path
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def create_windows_shortcut(
    target_path: str,
    shortcut_path: str,
    working_dir: Optional[str] = None,
    icon_path: Optional[str] = None,
    description: str = "Arı Fırın Muhasebe Sistemi"
) -> bool:
    """
    Belirtilen hedef dosya için Windows .lnk kısayolu oluşturur.
    
    Args:
        target_path: Kısayolun işaret edeceği çalıştırılabilir dosya yolu (.exe)
        shortcut_path: Oluşturulacak .lnk dosyasının tam yolu
        working_dir: Uygulamanın çalışma dizini (None ise target_path'in dizini)
        icon_path: Kısayol simgesi (.ico)
        description: Kısayol açıklaması
    """
    if sys.platform != "win32":
        logger.info(f"Windows harici işletim sistemi ({sys.platform}), kısayol oluşturma atlandı.")
        return False

    target = Path(target_path).resolve()
    if not target.exists():
        logger.warning(f"Kısayol hedefi diskte bulunamadı: {target}")

    shortcut = Path(shortcut_path).resolve()
    shortcut.parent.mkdir(parents=True, exist_ok=True)

    if not working_dir:
        working_dir = str(target.parent)

    # 1. Öncelikli Yöntem: win32com.client (Hızlı, güvenli, doğrudan COM)
    try:
        import win32com.client
        wscript = win32com.client.Dispatch("WScript.Shell")
        shortcut_obj = wscript.CreateShortcut(str(shortcut))
        shortcut_obj.TargetPath = str(target)
        shortcut_obj.WorkingDirectory = working_dir
        shortcut_obj.Description = description

        if icon_path and os.path.exists(icon_path):
            shortcut_obj.IconLocation = str(Path(icon_path).resolve())
        elif target.suffix.lower() == ".exe":
            shortcut_obj.IconLocation = f"{str(target)},0"

        shortcut_obj.Save()
        if shortcut.exists():
            logger.info(f"✅ Kısayol başarıyla oluşturuldu (COM): {shortcut}")
            return True
    except Exception as com_err:
        logger.debug(f"win32com ile kısayol denemesi: {com_err}, PowerShell fallback deneniyor...")

    # 2. İkinci Yöntem: PowerShell WScript.Shell
    try:
        target_clean = str(target).replace("'", "''")
        shortcut_clean = str(shortcut).replace("'", "''")
        work_clean = working_dir.replace("'", "''")
        desc_clean = description.replace("'", "''")

        ps_script = (
            f"$w = New-Object -ComObject WScript.Shell; "
            f"$s = $w.CreateShortcut('{shortcut_clean}'); "
            f"$s.TargetPath = '{target_clean}'; "
            f"$s.WorkingDirectory = '{work_clean}'; "
            f"$s.Description = '{desc_clean}'; "
        )
        if icon_path and os.path.exists(icon_path):
            icon_clean = str(Path(icon_path).resolve()).replace("'", "''")
            ps_script += f"$s.IconLocation = '{icon_clean}'; "
        elif target.suffix.lower() == ".exe":
            ps_script += f"$s.IconLocation = '{target_clean},0'; "

        ps_script += "$s.Save()"

        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            ps_script
        ]
        res = subprocess.run(cmd, capture_output=True, text=False, timeout=10)
        if shortcut.exists():
            logger.info(f"✅ Kısayol başarıyla oluşturuldu (PowerShell): {shortcut}")
            return True
        else:
            err_msg = res.stderr.decode("utf-8", errors="replace") if res.stderr else ""
            logger.warning(f"⚠️ Kısayol oluşturulamadı (Kod {res.returncode}): {err_msg.strip()}")
            return False
    except Exception as e:
        logger.error(f"❌ Kısayol oluşturma hatası: {e}")
        return False


def create_desktop_shortcut(
    target_path: str,
    shortcut_name: str = "Arı Fırın",
    icon_path: Optional[str] = None,
    description: str = "Arı Fırın Muhasebe Sistemi"
) -> bool:
    """Masaüstünde kısayol oluşturur"""
    desktop = get_desktop_dir()
    shortcut_file = desktop / f"{shortcut_name}.lnk"
    return create_windows_shortcut(target_path, str(shortcut_file), icon_path=icon_path, description=description)


def create_start_menu_shortcut(
    target_path: str,
    shortcut_name: str = "Arı Fırın",
    icon_path: Optional[str] = None,
    description: str = "Arı Fırın Muhasebe Sistemi"
) -> bool:
    """Başlat Menüsünde kısayol oluşturur"""
    start_menu = get_start_menu_dir()
    shortcut_file = start_menu / f"{shortcut_name}.lnk"
    return create_windows_shortcut(target_path, str(shortcut_file), icon_path=icon_path, description=description)
