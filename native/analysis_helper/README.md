# TuneMatrix Native Analysis Helper

This directory contains the native C++ helper scaffold for future Essentia-based
key and BPM analysis.

Current state:

- defines the CLI contract
- defines the JSON result schema
- builds without Essentia as a stub helper
- does not replace TuneMatrix's live Python analysis path yet
- Windows MSVC builds are verified with `NMake Makefiles`
- the helper itself currently analyzes WAV input, while the Python app can prepare non-WAV files through `ffmpeg` before calling it
- non-WAV helper analysis therefore depends on `ffmpeg` being available to TuneMatrix

Relevant repo folders:

- `native/analysis_helper/`
  helper source code and build files
- `third_party/essentia-src/`
  current vendored Essentia source used for the Windows/MSVC build
- `third_party/eigen-src/`
  current vendored Eigen headers used by Essentia
- `build/analysis_helper_nmake/`
  generated helper build output

Planned role:

- `tm-analysis-helper analyze --input <file> --output-json`
- return BPM/key analysis as JSON
- be bundled beside the packaged desktop app on Windows, macOS, and Linux

Recommended Windows build:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\native\analysis_helper\build_windows_msvc.ps1
```

Build with the vendored Essentia source already present in this repo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\native\analysis_helper\build_windows_msvc.ps1 -EnableEssentia
```

Use an external Essentia tree instead:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\native\analysis_helper\build_windows_msvc.ps1 -EnableEssentia -EssentiaRoot C:\path\to\essentia
```

Output:

- the helper binary is written to `build/analysis_helper_nmake/tm-analysis-helper.exe`

Quick verification:

```powershell
.\build\analysis_helper_nmake\tm-analysis-helper.exe --print-contract
.\build\analysis_helper_nmake\tm-analysis-helper.exe analyze --input .\tmp\key_reference_tracks\01_c_major_bright_loop.wav --output-json
```

For now, a build without Essentia returns a structured runtime error instead of
fake analysis data.
