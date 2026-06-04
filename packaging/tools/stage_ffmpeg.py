from __future__ import annotations

from pathlib import Path

from stage_common import (
    copy_executable,
    copy_runtime_siblings,
    download_file,
    extract_archive,
    find_first,
    parse_args,
    read_checksum_from_file,
    skip_or_fail,
    stage_notice,
    temporary_download_dir,
    tool_binary_name,
    tools_root,
)

BTBN_BASE_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"
BTBN_CHECKSUMS_URL = f"{BTBN_BASE_URL}/checksums.sha256"
BTBN_ASSETS = {
    "windows": "ffmpeg-master-latest-win64-lgpl.zip",
    "linux": "ffmpeg-master-latest-linux64-lgpl.tar.xz",
}

# macOS is intentionally skipped until the project chooses a provider with pinned
# provenance/checksum suitable for redistribution.
SUPPORTED_PLATFORMS = set(BTBN_ASSETS)


def stage_ffmpeg(platform: str, tools_dir: Path, downloads_dir: Path, skip_unsupported: bool) -> int:
    if platform not in SUPPORTED_PLATFORMS:
        return skip_or_fail(
            f"ffmpeg bundling is not configured for {platform}; using system/staged ffmpeg fallback.",
            skip_unsupported,
        )

    asset_name = BTBN_ASSETS[platform]
    checksum_file = download_file(BTBN_CHECKSUMS_URL, downloads_dir / "checksums.sha256").path
    expected_sha256 = read_checksum_from_file(checksum_file, asset_name)
    archive = download_file(
        f"{BTBN_BASE_URL}/{asset_name}",
        downloads_dir / asset_name,
        expected_sha256=expected_sha256,
    )
    extracted = extract_archive(archive.path, downloads_dir / "extracted")

    tool_root = tools_dir / "ffmpeg"
    bin_root = tool_root / "bin"
    ffmpeg_source = find_first(extracted, [tool_binary_name("ffmpeg", platform)])
    copy_runtime_siblings(ffmpeg_source, bin_root)

    # Ensure the primary executables have the expected normalized names even if
    # the upstream archive layout changes.
    copy_executable(ffmpeg_source, bin_root / tool_binary_name("ffmpeg", platform))

    try:
        ffprobe_source = find_first(extracted, [tool_binary_name("ffprobe", platform)])
    except RuntimeError:
        ffprobe_source = None
    if ffprobe_source is not None:
        copy_executable(ffprobe_source, bin_root / tool_binary_name("ffprobe", platform))

    notice = """
FFmpeg is bundled in TuneMatrix release artifacts as a separately licensed third-party runtime tool.
TuneMatrix source code remains licensed separately under the project license.
Review FFmpeg licensing terms before redistributing modified artifacts.
"""
    provenance = f"""
Tool: FFmpeg
Provider: BtbN/FFmpeg-Builds
Variant: LGPL autobuild
Asset: {asset_name}
Source URL: {BTBN_BASE_URL}/{asset_name}
Checksum URL: {BTBN_CHECKSUMS_URL}
SHA256: {archive.sha256}
License notes: FFmpeg is primarily LGPL, with optional GPL components depending on build variant. This workflow uses the BtbN lgpl variant.
"""
    stage_notice(tool_root, notice, provenance)
    return 0


def main() -> int:
    args = parse_args("Stage FFmpeg into TuneMatrix's release tools layout.")
    downloads_dir = temporary_download_dir("tunematrix_ffmpeg_", args.downloads_dir)
    return stage_ffmpeg(
        platform=args.platform,
        tools_dir=tools_root(args.tools_dir),
        downloads_dir=downloads_dir,
        skip_unsupported=args.skip_unsupported,
    )


if __name__ == "__main__":
    raise SystemExit(main())
