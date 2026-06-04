from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
from pathlib import Path


def copy_tree_contents(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def build_package(dist_dir: Path, output_dir: Path, version: str, arch: str) -> Path:
    package_root = output_dir / "deb-root"
    if package_root.exists():
        shutil.rmtree(package_root)

    app_root = package_root / "opt" / "tunematrix"
    desktop_root = package_root / "usr" / "share" / "applications"
    debian_root = package_root / "DEBIAN"

    copy_tree_contents(dist_dir, app_root)
    desktop_root.mkdir(parents=True, exist_ok=True)
    debian_root.mkdir(parents=True, exist_ok=True)

    executable = app_root / "TuneMatrix"
    if executable.exists():
        make_executable(executable)

    shutil.copy2(Path(__file__).with_name("tunematrix.desktop"), desktop_root / "tunematrix.desktop")

    installed_size_kb = 0
    for path in app_root.rglob("*"):
        if path.is_file():
            installed_size_kb += max(1, path.stat().st_size // 1024)

    control = f"""Package: tunematrix
Version: {version.lstrip('v')}
Section: sound
Priority: optional
Architecture: {arch}
Maintainer: Avinash Kumar
Installed-Size: {installed_size_kb}
Description: Desktop music-processing application built with Python and PySide6.
 TuneMatrix imports, analyzes, processes, and exports music files.
"""
    (debian_root / "control").write_text(control, encoding="utf-8")

    output_dir.mkdir(parents=True, exist_ok=True)
    package_path = output_dir / f"TuneMatrix-{version}-linux-x64.deb"
    if package_path.exists():
        package_path.unlink()
    subprocess.run(["dpkg-deb", "--build", str(package_root), str(package_path)], check=True)
    return package_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a simple TuneMatrix Debian package.")
    parser.add_argument("--dist-dir", default="dist/TuneMatrix")
    parser.add_argument("--output-dir", default="release-artifacts")
    parser.add_argument("--version", default=os.environ.get("RELEASE_VERSION", "0.1.0"))
    parser.add_argument("--arch", default="amd64")
    args = parser.parse_args()

    package_path = build_package(
        dist_dir=Path(args.dist_dir).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        version=args.version,
        arch=args.arch,
    )
    print(package_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
