from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime_tools import (
    discover_stageable_tools,
    helper_stage_name,
    stage_analysis_helper,
    stage_ffmpeg_runtime,
    stage_rubberband_runtime,
)
from utils import tool_binary_name


class RuntimeToolsTests(unittest.TestCase):
    def test_stage_analysis_helper_copies_binary_into_tools_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            source = repo_root / "build" / helper_stage_name()
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("helper", encoding="utf-8")

            destination = stage_analysis_helper(source, root=repo_root)

            self.assertEqual(destination, repo_root / "tools" / "analysis-helper" / helper_stage_name())
            self.assertTrue(destination.exists())

    def test_stage_ffmpeg_runtime_copies_ffmpeg_and_ffprobe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            ffmpeg = repo_root / tool_binary_name("ffmpeg")
            ffprobe = repo_root / tool_binary_name("ffprobe")
            ffmpeg.write_text("ffmpeg", encoding="utf-8")
            ffprobe.write_text("ffprobe", encoding="utf-8")

            staged = stage_ffmpeg_runtime(ffmpeg, ffprobe_path=ffprobe, root=repo_root)

            self.assertEqual(
                staged,
                [
                    repo_root / "tools" / "ffmpeg" / tool_binary_name("ffmpeg"),
                    repo_root / "tools" / "ffmpeg" / tool_binary_name("ffprobe"),
                ],
            )
            self.assertTrue(all(path.exists() for path in staged))

    def test_stage_rubberband_runtime_copies_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            source = repo_root / tool_binary_name("rubberband")
            source.write_text("rubberband", encoding="utf-8")

            destination = stage_rubberband_runtime(source, root=repo_root)

            self.assertEqual(destination, repo_root / "tools" / "rubberband" / tool_binary_name("rubberband"))
            self.assertTrue(destination.exists())

    def test_discover_stageable_tools_uses_current_lookup_stack(self) -> None:
        helper_path = Path("C:/app/tools/analysis-helper") / helper_stage_name()
        with patch("runtime_tools.find_native_analysis_helper", return_value=helper_path), patch(
            "runtime_tools.find_executable",
            side_effect=lambda name, root=None: {
                "ffmpeg": "C:/app/tools/ffmpeg/ffmpeg.exe",
                "ffprobe": "C:/app/tools/ffmpeg/ffprobe.exe",
                "rubberband": "C:/app/tools/rubberband/rubberband.exe",
            }.get(name),
        ):
            discovered = discover_stageable_tools(Path("repo-root"))

        self.assertEqual(discovered["analysis_helper"], str(helper_path))
        self.assertEqual(discovered["ffmpeg"], "C:/app/tools/ffmpeg/ffmpeg.exe")
        self.assertEqual(discovered["ffprobe"], "C:/app/tools/ffmpeg/ffprobe.exe")
        self.assertEqual(discovered["rubberband"], "C:/app/tools/rubberband/rubberband.exe")


if __name__ == "__main__":
    unittest.main()
