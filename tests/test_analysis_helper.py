from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis_helper import (
    AnalysisHelperError,
    build_helper_command,
    find_native_analysis_helper,
    helper_binary_name,
    parse_native_analysis_result,
    run_native_analysis_helper,
)


class AnalysisHelperTests(unittest.TestCase):
    def test_build_helper_command_matches_cli_contract(self) -> None:
        command = build_helper_command(Path("helper.exe"), Path("song.wav"))
        self.assertEqual(
            command,
            ["helper.exe", "analyze", "--input", "song.wav", "--output-json"],
        )

    def test_parse_native_analysis_result_keeps_expected_fields(self) -> None:
        result = parse_native_analysis_result(
            {
                "backend": "essentia-cpp",
                "duration": 191.0,
                "bpm": 110.02,
                "key": "F# Major",
                "scale": "major",
                "confidence": 0.91,
                "candidates": [
                    {"key": "F# Major", "score": 0.91},
                    {"key": "D# Minor", "score": 0.07},
                ],
            }
        )

        self.assertEqual(result.backend, "essentia-cpp")
        self.assertEqual(result.key, "F# Major")
        self.assertEqual(result.scale, "major")
        self.assertAlmostEqual(result.bpm or 0.0, 110.02)
        self.assertEqual(len(result.candidates), 2)
        self.assertEqual(result.candidates[0].key, "F# Major")

    def test_find_native_analysis_helper_prefers_explicit_env_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            helper_path = Path(temp_dir) / helper_binary_name()
            helper_path.write_text("stub", encoding="utf-8")
            with patch.dict(os.environ, {"TUNEMATRIX_ANALYSIS_HELPER": str(helper_path)}, clear=False):
                self.assertEqual(find_native_analysis_helper(), helper_path)

    def test_run_native_analysis_helper_parses_json_from_subprocess(self) -> None:
        payload = (
            '{'
            '"backend":"essentia-cpp",'
            '"duration":191.0,'
            '"bpm":110.02,'
            '"key":"F# Major",'
            '"scale":"major",'
            '"confidence":0.91,'
            '"candidates":[{"key":"F# Major","score":0.91}],'
            '"error":null'
            '}'
        )

        completed = type(
            "Completed",
            (),
            {
                "returncode": 0,
                "stdout": payload,
                "stderr": "",
            },
        )()

        with patch("analysis_helper.subprocess.run", return_value=completed):
            result = run_native_analysis_helper(
                "song.wav",
                helper_path="tm-analysis-helper.exe",
            )

        self.assertEqual(result.backend, "essentia-cpp")
        self.assertEqual(result.key, "F# Major")

    def test_run_native_analysis_helper_raises_when_helper_missing(self) -> None:
        with self.assertRaises(AnalysisHelperError):
            run_native_analysis_helper("song.wav", root=Path("missing-root"))


if __name__ == "__main__":
    unittest.main()
