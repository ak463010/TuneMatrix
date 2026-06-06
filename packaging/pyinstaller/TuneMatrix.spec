# -*- mode: python ; coding: utf-8 -*-

import sys
from importlib.util import find_spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

SPEC_DIR = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_DIR.parents[1]
MAIN_SCRIPT = REPO_ROOT / "main.py"


def collect_if_available(package_name, collector):
    if find_spec(package_name) is None:
        return []
    try:
        return collector(package_name)
    except Exception:
        return []


def collect_staged_tool_files():
    tool_root = REPO_ROOT / "tools"
    if not tool_root.exists():
        return []
    collected = []
    for path in tool_root.rglob("*"):
        if path.is_file() and path.name != ".gitkeep":
            collected.append((str(path), str(path.parent.relative_to(REPO_ROOT))))
    return collected


hiddenimports = []
for package_name in (
    "librosa",
    "soundfile",
    "pyrubberband",
):
    hiddenimports += collect_if_available(package_name, collect_submodules)

datas = []
for package_name in (
    "librosa",
    "soundfile",
):
    datas += collect_if_available(package_name, collect_data_files)

datas += collect_staged_tool_files()

binaries = []
for package_name in (
    "soundfile",
):
    binaries += collect_if_available(package_name, collect_dynamic_libs)

analysis = Analysis(
    [str(MAIN_SCRIPT)],
    pathex=[str(REPO_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "demucs",
        "torch",
        "torchaudio",
        "torchcodec",
    ],
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
