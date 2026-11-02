# -*- mode: python ; coding: utf-8 -*-
# AriFirin_Final.spec - Kesin çalışan derleme dosyası
import os
from PyInstaller.utils.hooks import collect_submodules

HERE = os.path.abspath(os.path.dirname('main.py'))

# Veri dosyaları (exe'nin yanına kopyalanacaklar)
datas = []
if os.path.exists('resources'):
    datas.append(('resources', 'resources'))
if os.path.exists('src'):
    datas.append(('src', 'src'))          # ✅ TÜM src klasörünü ekle

# Gizli import'lar (exe'nin içine gömülecek Python modülleri)
hidden_imports = [
    'psycopg2',
    'psycopg2.extras',
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'openpyxl',
    'pandas',
    'requests',
    'bcrypt',
    'dotenv',
    'decimal',
    'hashlib',
    'hmac',
    'uuid',
    'zipfile',
    'json',
    'datetime',
    # ✅ src modüllerini AÇIKÇA listele
    'src',
    'src.core',
    'src.core.version',
    'src.core.config',
    'src.core.database',
    'src.core.logger',
    'src.models',
    'src.models.user',
    'src.models.branch',
    'src.services',
    'src.services.updater_service',
    'src.ui',
] + collect_submodules('src')

a = Analysis(
    ['main.py'],
    pathex=[HERE],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest', 'botocore', 'boto3', 'sqlalchemy', 'scipy', 'matplotlib',
        'torch', 'IPython', 'jupyter', 'tkinter', 'pygame',
        'tensorflow', 'sklearn', 'transformers', 'cv2', 'nltk',
        'onnxruntime', 'fastapi', 'django', 'Cython', 'numba', 'llvmlite'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AriFirin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icons/app.ico' if os.path.exists('resources/icons/app.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AriFirin',
)