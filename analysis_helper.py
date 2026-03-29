from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class AnalysisHelperError(Exception):
    pass


@dataclass(frozen=True)
class AnalysisCandidate:
    key: str
    score: float


@dataclass(frozen=True)
class NativeAnalysisResult:
    backend: str
    duration: Optional[float]
    bpm: Optional[float]
    key: Optional[str]
    scale: Optional[str]
    confidence: Optional[float]
    candidates: list[AnalysisCandidate]
    error: Optional[str]


def helper_binary_name() -> str:
    return "tm-analysis-helper.exe" if os.name == "nt" else "tm-analysis-helper"


def helper_search_paths(root: Optional[Path] = None) -> list[Path]:
    repo_root = Path(root or Path(__file__).resolve().parent)
    binary_name = helper_binary_name()
    env_path = os.environ.get("TUNEMATRIX_ANALYSIS_HELPER", "").strip()

    paths: list[Path] = []
    if env_path:
        paths.append(Path(env_path))

    paths.extend(
        [
            repo_root / "tools" / "analysis-helper" / binary_name,
            repo_root / "native" / "analysis_helper" / "build" / "Release" / binary_name,
            repo_root / "native" / "analysis_helper" / "build" / binary_name,
            repo_root / "build" / "analysis_helper_nmake" / binary_name,
            repo_root / "build" / "analysis_helper_msvc" / binary_name,
            repo_root / "build" / "analysis_helper" / "Release" / binary_name,
            repo_root / "build" / "analysis_helper" / binary_name,
        ]
    )
    return paths


def find_native_analysis_helper(root: Optional[Path] = None) -> Optional[Path]:
    for candidate in helper_search_paths(root):
        if candidate.is_file():
            return candidate
    return None


def build_helper_command(helper_path: Path | str, input_path: Path | str) -> list[str]:
    return [str(helper_path), "analyze", "--input", str(input_path), "--output-json"]


def parse_native_analysis_result(payload: dict[str, object]) -> NativeAnalysisResult:
    backend = str(payload.get("backend") or "").strip() or "unknown"
    candidates_payload = payload.get("candidates") or []
    candidates: list[AnalysisCandidate] = []
    if isinstance(candidates_payload, list):
        for item in candidates_payload:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            score_value = item.get("score")
            try:
                score = float(score_value)
            except (TypeError, ValueError):
                continue
            if key:
                candidates.append(AnalysisCandidate(key=key, score=score))

    def _optional_float(value: object) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _optional_string(value: object) -> Optional[str]:
        text = str(value).strip() if value is not None else ""
        return text or None

    return NativeAnalysisResult(
        backend=backend,
        duration=_optional_float(payload.get("duration")),
        bpm=_optional_float(payload.get("bpm")),
        key=_optional_string(payload.get("key")),
        scale=_optional_string(payload.get("scale")),
        confidence=_optional_float(payload.get("confidence")),
        candidates=candidates,
        error=_optional_string(payload.get("error")),
    )


def run_native_analysis_helper(
    input_path: str | Path,
    *,
    helper_path: Optional[str | Path] = None,
    timeout_seconds: float = 30.0,
    root: Optional[Path] = None,
) -> NativeAnalysisResult:
    resolved_helper = Path(helper_path) if helper_path else find_native_analysis_helper(root=root)
    if resolved_helper is None:
        raise AnalysisHelperError("Native analysis helper was not found.")

    command = build_helper_command(resolved_helper, input_path)
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except OSError as exc:
        raise AnalysisHelperError(f"Failed to start native analysis helper: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AnalysisHelperError("Native analysis helper timed out.") from exc

    stdout = completed.stdout.strip()
    if not stdout:
        stderr = completed.stderr.strip()
        raise AnalysisHelperError(stderr or "Native analysis helper returned no JSON output.")

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AnalysisHelperError(f"Native analysis helper returned invalid JSON: {exc}") from exc

    result = parse_native_analysis_result(payload)
    if completed.returncode != 0 and result.error:
        raise AnalysisHelperError(result.error)
    if completed.returncode != 0:
        raise AnalysisHelperError(f"Native analysis helper failed with exit code {completed.returncode}.")
    return result
