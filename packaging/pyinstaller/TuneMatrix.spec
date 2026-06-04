# -*- mode: python ; coding: utf-8 -*-

import sys
from importlib.util import find_spec

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


def collect_if_available(package_name, collector):
    if find_spec(package_name) is None:
        return []
    try:
        return collector(package_name)
    except Exception:
        return []


hiddenimports = []
for package_name in (
    "librosa",
    "soundfile",
    "pyrubberband",
    "demucs",
    "torch",
    "torchaudio",
    "torchcodec",
):
    hiddenimports += collect_if_available(package_name, collect_submodules)

datas = []
for package_name in (
    "librosa",
    "soundfile",
    "demucs",
    "torch",
    "torchaudio",
    "torchcodec",
):
    datas += collect_if_available(package_name, collect_data_files)

binaries = []
for package_name in (
    "soundfile",
    "torch",
    "torchaudio",
    "torchcodec",
):
    binaries += collect_if_available(package_name, collect_dynamic_libs)

analysis = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="TuneMatrix",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TuneMatrix",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="TuneMatrix.app",
        icon=None,
        bundle_identifier="com.tunematrix.app",
        info_plist={
            "CFBundleName": "TuneMatrix",
            "CFBundleDisplayName": "TuneMatrix",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "NSHighResolutionCapable": "True",
        },
    )
