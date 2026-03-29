from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from analysis_helper import find_native_analysis_helper
from utils import ensure_directory, find_executable, tool_binary_name


def repo_root(root: Optional[str | Path] = None) -> Path:
    return Path(root or Path(__file__).resolve().parent)


def tool_stage_dir(tool_name: str, root: Optional[str | Path] = None) -> Path:
    return repo_root(root) / "tools" / tool_name


def stage_runtime_binary(
    tool_name: str,
    source_path: str | Path,
    *,
    root: Optional[str | Path] = None,
    target_name: Optional[str] = None,
) -> Path:
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(f"Runtime binary was not found: {source}")

    destination_dir = Path(ensure_directory(tool_stage_dir(tool_name, root=root)))
    destination = destination_dir / (target_name or source.name)
    shutil.copy2(source, destination)
    return destination


def helper_stage_name() -> str:
    return tool_binary_name("tm-analysis-helper")


def stage_analysis_helper(
    helper_path: str | Path,
    *,
    root: Optional[str | Path] = None,
) -> Path:
    return stage_runtime_binary(
        "analysis-helper",
        helper_path,
        root=root,
        target_name=helper_stage_name(),
    )


def stage_ffmpeg_runtime(
    ffmpeg_path: str | Path,
    *,
    ffprobe_path: Optional[str | Path] = None,
    root: Optional[str | Path] = None,
) -> list[Path]:
    staged = [
        stage_runtime_binary(
            "ffmpeg",
            ffmpeg_path,
            root=root,
            target_name=tool_binary_name("ffmpeg"),
        )
    ]
    if ffprobe_path:
        staged.append(
            stage_runtime_binary(
                "ffmpeg",
                ffprobe_path,
                root=root,
                target_name=tool_binary_name("ffprobe"),
            )
        )
    return staged


def stage_rubberband_runtime(
    rubberband_path: str | Path,
    *,
    root: Optional[str | Path] = None,
) -> Path:
    return stage_runtime_binary(
        "rubberband",
        rubberband_path,
        root=root,
        target_name=tool_binary_name("rubberband"),
    )


def discover_stageable_tools(root: Optional[str | Path] = None) -> dict[str, Optional[str]]:
    repo = repo_root(root)
    ffmpeg = find_executable("ffmpeg", root=repo)
    ffprobe = find_executable("ffprobe", root=repo)
    rubberband = find_executable("rubberband", root=repo)
    helper = find_native_analysis_helper(root=repo)
    return {
        "analysis_helper": str(helper) if helper else None,
        "ffmpeg": ffmpeg,
        "ffprobe": ffprobe,
        "rubberband": rubberband,
    }

