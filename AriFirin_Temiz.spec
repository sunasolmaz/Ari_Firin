# -*- mode: python ; coding: utf-8 -*-
# AriFirin_Temiz.spec - Temiz ve güncel derleme dosyası
import os
from PyInstaller.utils.hooks import collect_submodules

HERE = os.path.abspath(os.path.dirname('main.py'))

# Derlemeye dahil edilecek veri dosyaları
datas = []
if os.path.exists('resources'):
    datas.append(('resources', 'resources'))
if os.path.exists('src/ui/assets'):
    datas.append(('src/ui/assets', 'src/ui/assets'))

# Gizli import'lar (PyInstaller'ın bulamadığı kütüphaneler)
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