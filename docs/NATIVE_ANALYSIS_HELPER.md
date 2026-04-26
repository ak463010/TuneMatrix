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
- live app analysis now prefers the native Essentia helper by default when it is available
- if the helper is unavailable or fails in `auto` mode, TuneMatrix falls back to the existing Python `librosa` path
- the `TUNEMATRIX_ANALYSIS_BACKEND` environment variable can still force `librosa`, `auto`, or `native_helper`
- Windows MSVC builds are currently verified through `NMake Makefiles`
- the native Essentia helper still analyzes WAV internally, and the Python app now uses `ffmpeg` to prepare a temporary WAV automatically for non-WAV inputs
- non-WAV helper analysis therefore requires `ffmpeg` to be available to the app

Folder roles:

- [native/analysis_helper](../native/analysis_helper)
  the real C++ helper source code, CMake files, and Windows build script
- `third_party/essentia-src`
  the vendored Essentia source tree currently used for local Windows/MSVC builds
- `third_party/eigen-src`
  the vendored Eigen headers required by Essentia
- `third_party/eigen-pkgconfig/eigen3.pc`
  local pkg-config helper file used while building Essentia from source on Windows
- `build/analysis_helper_nmake`
  generated helper build output; this is not source and can be regenerated

Current repo assumption:

- if `third_party/essentia-src` and `third_party/eigen-src` exist, the helper can be rebuilt from this repo without downloading more source code
- if those folders are missing, you need to provide an external Essentia build and pass `-EssentiaRoot`

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
- bundled release layout is now expected to prefer:
  - `tools/analysis-helper/tm-analysis-helper.exe` on Windows
  - `tools/analysis-helper/tm-analysis-helper` on macOS and Linux
  - `tools/analysis-helper/bin/<binary-name>` as a secondary bundled location on every platform
- if no bundled helper is found, TuneMatrix falls back to the helper name on `PATH`

Bundled tool layout:

```text
tools/
  analysis-helper/
    tm-analysis-helper(.exe)
    bin/
      tm-analysis-helper(.exe)
  ffmpeg/
    ffmpeg(.exe)
    ffprobe(.exe)
    bin/
      ffmpeg(.exe)
      ffprobe(.exe)
```

Cross-platform note:

- TuneMatrix now resolves helper and tool names with platform-aware binary names
- Windows expects `.exe`
- macOS and Linux expect the plain executable name with no `.exe` suffix
- the same bundled folder structure can therefore be used on all three platforms

Windows build:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\native\analysis_helper\build_windows_msvc.ps1
```

That script currently builds the helper into:

```text
build/analysis_helper_nmake/
```

Build with the vendored Essentia source already in this repo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\native\analysis_helper\build_windows_msvc.ps1 -EnableEssentia
```

Build and stage the helper straight into the bundled runtime layout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\native\analysis_helper\build_windows_msvc.ps1 -EnableEssentia -StageToTools
```

That command automatically uses:

- `third_party/essentia-src`
- `third_party/eigen-src`

If you want to use an external Essentia tree instead, build the helper with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\native\analysis_helper\build_windows_msvc.ps1 -EnableEssentia -EssentiaRoot C:\path\to\essentia
```

The CMake helper build looks for:

- `include\essentia\algorithmfactory.h`
- an Essentia library such as `essentia.lib` or `libessentia.lib`

Note:

- the helper stub has been verified with the `NMake Makefiles` generator on this Windows setup
- the `Ninja` generator was stalling during CMake compiler-probe steps here, so `NMake` is the current known-good path
- the helper build script deletes and recreates `build/analysis_helper_nmake` each time

Verify the built helper:

```powershell
.\build\analysis_helper_nmake\tm-analysis-helper.exe --print-contract
.\build\analysis_helper_nmake\tm-analysis-helper.exe analyze --input .\tmp\key_reference_tracks\01_c_major_bright_loop.wav --output-json
```

Stage bundled runtime tools:

```powershell
python .\scripts\stage_runtime_tools.py
```

That script stages any discovered helper, `ffmpeg`, `ffprobe`, and `rubberband` binaries into the `tools/` layout used by TuneMatrix at runtime.

Use the helper in TuneMatrix:

- default app behavior already prefers the helper automatically when it is available
- to force strict helper-only analysis:

```powershell
$env:TUNEMATRIX_ANALYSIS_BACKEND = "native_helper"
python main.py
```

- to force the fallback path instead:

```powershell
$env:TUNEMATRIX_ANALYSIS_BACKEND = "librosa"
python main.py
```

Cleanup expectations:

- `build/` is generated output and should not be treated as permanent source
- `third_party/essentia-src/build` is generated by the Essentia build and can be rebuilt
- `native/analysis_helper` is real project source and should stay in the repo

Current rollout:

1. TuneMatrix prefers the native helper automatically in `auto` mode
2. `librosa` remains the safe fallback path
3. `native_helper` mode can be forced for strict testing
4. non-WAV helper analysis is prepared through `ffmpeg`
5. bundled helper and tool locations are searched before `PATH`, which keeps future packaged builds aligned across Windows, macOS, and Linux
