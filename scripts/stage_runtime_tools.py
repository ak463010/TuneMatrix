from __future__ import annotations

import argparse
from pathlib import Path

from runtime_tools import (
    discover_stageable_tools,
    helper_stage_name,
    stage_analysis_helper,
    stage_ffmpeg_runtime,
    stage_rubberband_runtime,
)
from utils import tool_binary_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage runtime binaries into TuneMatrix tools/ for local packaging tests."
    )
    parser.add_argument("--root", default=".", help="Repo root to stage into.")
    parser.add_argument("--helper", help="Explicit tm-analysis-helper binary path.")
    parser.add_argument("--ffmpeg", help="Explicit ffmpeg binary path.")
    parser.add_argument("--ffprobe", help="Explicit ffprobe binary path.")
    parser.add_argument("--rubberband", help="Explicit rubberband binary path.")
    parser.add_argument("--skip-helper", action="store_true", help="Do not stage the analysis helper.")
    parser.add_argument("--skip-ffmpeg", action="store_true", help="Do not stage ffmpeg/ffprobe.")
    parser.add_argument("--skip-rubberband", action="store_true", help="Do not stage rubberband.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.root).resolve()
    discovered = discover_stageable_tools(root)

    helper_path = args.helper or discovered["analysis_helper"]
    ffmpeg_path = args.ffmpeg or discovered["ffmpeg"]
    ffprobe_path = args.ffprobe or discovered["ffprobe"]
    rubberband_path = args.rubberband or discovered["rubberband"]

    staged_any = False

    if not args.skip_helper and helper_path:
        destination = stage_analysis_helper(helper_path, root=root)
        staged_any = True
        print(f"Staged analysis helper -> {destination}")
    elif not args.skip_helper:
        print(f"Skipped analysis helper: no {helper_stage_name()} binary was found.")

    if not args.skip_ffmpeg and ffmpeg_path:
        staged = stage_ffmpeg_runtime(ffmpeg_path, ffprobe_path=ffprobe_path, root=root)
        staged_any = True
        print(f"Staged ffmpeg runtime -> {', '.join(str(path) for path in staged)}")
    elif not args.skip_ffmpeg:
        print(f"Skipped ffmpeg runtime: no {tool_binary_name('ffmpeg')} binary was found.")

    if not args.skip_rubberband and rubberband_path:
        destination = stage_rubberband_runtime(rubberband_path, root=root)
        staged_any = True
        print(f"Staged rubberband runtime -> {destination}")
    elif not args.skip_rubberband:
        print(f"Skipped rubberband runtime: no {tool_binary_name('rubberband')} binary was found.")

    if not staged_any:
        print("No runtime tools were staged.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
