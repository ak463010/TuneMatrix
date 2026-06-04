from __future__ import annotations

from pathlib import Path

from stage_common import (
    copy_executable,
    download_file,
    extract_archive,
    find_first,
    parse_args,
    skip_or_fail,
    stage_notice,
    temporary_download_dir,
    tool_binary_name,
    tools_root,
)

RUBBERBAND_VERSION = "4.0.0"
RUBBERBAND_BASE_URL = "https://breakfastquay.com/files/releases"
RUBBERBAND_ASSETS = {
    "windows": "rubberband-4.0.0-gpl-executable-windows.zip",
    "macos": "rubberband-4.0.0-gpl-executable-macos.tar.bz2",
}

# The official release index provides Windows and macOS executable archives but
# no Linux executable archive. Linux source-build bundling can be added later.
SUPPORTED_PLATFORMS = set(RUBBERBAND_ASSETS)


def stage_rubberband(platform: str, tools_dir: Path, downloads_dir: Path, skip_unsupported: bool) -> int:
    if platform not in SUPPORTED_PLATFORMS:
        return skip_or_fail(
            f"Rubber Band bundling is not configured for {platform}; using system/staged rubberband fallback.",
            skip_unsupported,
        )

    asset_name = RUBBERBAND_ASSETS[platform]
    # Breakfast Quay's release index does not publish a checksums file alongside
    # these assets. Pin the exact upstream URL and record the observed SHA256 in
    # PROVENANCE.txt for auditability.
    archive = download_file(f"{RUBBERBAND_BASE_URL}/{asset_name}", downloads_dir / asset_name)
    extracted = extract_archive(archive.path, downloads_dir / "extracted")

    tool_root = tools_dir / "rubberband"
    bin_root = tool_root / "bin"
    rubberband_source = find_first(extracted, [tool_binary_name("rubberband", platform)])
    copy_executable(rubberband_source, bin_root / tool_binary_name("rubberband", platform))

    notice = """
Rubber Band is bundled in TuneMatrix release artifacts as a separately licensed third-party runtime tool.
The official executable packages used here are GPL builds. Review Rubber Band licensing terms before redistributing modified artifacts.
TuneMatrix source code remains licensed separately under the project license.
"""
    provenance = f"""
Tool: Rubber Band command-line executable
Provider: Breakfast Quay / Rubber Band Library official release files
Version: {RUBBERBAND_VERSION}
Asset: {asset_name}
Source URL: {RUBBERBAND_BASE_URL}/{asset_name}
SHA256: {archive.sha256}
License notes: Official executable packages are GPL builds. Source release is available from the same release index and upstream project.
"""
    stage_notice(tool_root, notice, provenance)
    return 0


def main() -> int:
    args = parse_args("Stage Rubber Band into TuneMatrix's release tools layout.")
    downloads_dir = temporary_download_dir("tunematrix_rubberband_", args.downloads_dir)
    return stage_rubberband(
        platform=args.platform,
        tools_dir=tools_root(args.tools_dir),
        downloads_dir=downloads_dir,
        skip_unsupported=args.skip_unsupported,
    )


if __name__ == "__main__":
    raise SystemExit(main())
