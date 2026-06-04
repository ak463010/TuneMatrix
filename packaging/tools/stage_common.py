from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DownloadedFile:
    path: Path
    sha256: str


def parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--platform", required=True, choices=["windows", "macos", "linux"])
    parser.add_argument("--tools-dir", default="tools")
    parser.add_argument("--downloads-dir", default=None)
    parser.add_argument("--skip-unsupported", action="store_true", help="Exit successfully when this tool is unsupported on the platform.")
    return parser.parse_args()


def tool_binary_name(name: str, platform: str) -> str:
    if platform == "windows" and not name.lower().endswith(".exe"):
        return f"{name}.exe"
    return name


def ensure_clean_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path, expected_sha256: str | None = None) -> DownloadedFile:
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, destination)
    actual_sha256 = sha256_file(destination)
    if expected_sha256 and actual_sha256.lower() != expected_sha256.lower():
        raise RuntimeError(
            f"Checksum mismatch for {url}: expected {expected_sha256}, got {actual_sha256}"
        )
    print(f"Downloaded {destination.name} sha256={actual_sha256}")
    return DownloadedFile(destination, actual_sha256)


def read_checksum_from_file(checksum_file: Path, asset_name: str) -> str:
    for raw_line in checksum_file.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = raw_line.strip().split()
        if len(parts) < 2:
            continue
        checksum = parts[0]
        name = parts[-1].lstrip("*")
        if Path(name).name == asset_name:
            return checksum
    raise RuntimeError(f"Could not find checksum for {asset_name} in {checksum_file}")


def extract_archive(archive_path: Path, destination: Path) -> Path:
    ensure_clean_dir(destination)
    archive_name = archive_path.name.lower()
    if archive_name.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(destination)
        return destination
    if archive_name.endswith((".tar.xz", ".tar.gz", ".tgz", ".tar.bz2")):
        with tarfile.open(archive_path) as archive:
            archive.extractall(destination)
        return destination
    raise RuntimeError(f"Unsupported archive format: {archive_path}")


def find_first(root: Path, names: list[str]) -> Path:
    wanted = {name.lower() for name in names}
    for candidate in root.rglob("*"):
        if candidate.is_file() and candidate.name.lower() in wanted:
            return candidate
    raise RuntimeError(f"Could not find any of {names} under {root}")


def copy_executable(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    mode = target.stat().st_mode
    target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Staged {target}")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def temporary_download_dir(prefix: str, requested: str | None) -> Path:
    if requested:
        return ensure_clean_dir(Path(requested))
    return Path(tempfile.mkdtemp(prefix=prefix))


def tools_root(tools_dir: str | Path) -> Path:
    return Path(tools_dir).resolve()


def stage_notice(tool_root: Path, notice: str, provenance: str) -> None:
    write_text(tool_root / "NOTICE.txt", notice.strip() + "\n")
    write_text(tool_root / "PROVENANCE.txt", provenance.strip() + "\n")


def skip_or_fail(message: str, skip_unsupported: bool) -> int:
    if skip_unsupported:
        print(message)
        return 0
    raise RuntimeError(message)
