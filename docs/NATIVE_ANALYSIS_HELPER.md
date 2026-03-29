# Native Analysis Helper

TuneMatrix now includes a scaffold for a future cross-platform native helper at:

- [native/analysis_helper](../native/analysis_helper)

The intent is:

- keep the main desktop app in Python
- move future high-accuracy BPM/key analysis into a small native helper
- call that helper from Python through a stable CLI + JSON contract

Current state:

- the helper project is scaffolded with CMake
- the helper binary name is `tm-analysis-helper`
- the CLI contract is defined
- the Python bridge lives in [analysis_helper.py](../analysis_helper.py)
- live app analysis still uses the existing Python `librosa` path by default
- the app can optionally try the helper through the `TUNEMATRIX_ANALYSIS_BACKEND` environment variable
- Windows MSVC builds are currently verified through `NMake Makefiles`
- the first native Essentia path is designed as WAV-only to keep decoding simple

CLI shape:

```text
tm-analysis-helper analyze --input <audio-file> --output-json
tm-analysis-helper --print-contract
```

Planned JSON shape:

```json
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
    {"key": "A# Minor", "score": 0.02}
  ],
  "error": null
}
```

Backend switching:

- `TUNEMATRIX_ANALYSIS_BACKEND=librosa`
  always use the current Python `librosa` path
- `TUNEMATRIX_ANALYSIS_BACKEND=auto`
  try the native helper first, then fall back to `librosa`
- `TUNEMATRIX_ANALYSIS_BACKEND=native_helper`
  require the native helper and fail if it is unavailable

Helper discovery:

- set `TUNEMATRIX_ANALYSIS_HELPER` to an explicit helper executable path
- otherwise TuneMatrix searches common bundled/build locations through [analysis_helper.py](../analysis_helper.py)

Windows build:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\native\analysis_helper\build_windows_msvc.ps1
```

That script currently builds the helper into:

```text
build/analysis_helper_nmake/
```

If Essentia is installed locally, build the helper with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\native\analysis_helper\build_windows_msvc.ps1 -EnableEssentia -EssentiaRoot C:\path\to\essentia
```

The CMake helper build looks for:

- `include\essentia\algorithmfactory.h`
- an Essentia library such as `essentia.lib` or `libessentia.lib`

Note:

- the helper stub has been verified with the `NMake Makefiles` generator on this Windows setup
- the `Ninja` generator was stalling during CMake compiler-probe steps here, so `NMake` is the current known-good path

Recommended rollout:

1. keep the current Python analysis path as the default
2. wire the Python bridge into an optional helper-backed analysis path
3. integrate Essentia in the native helper
4. compare the helper against the current hard reference packs
5. only then consider switching the default backend
