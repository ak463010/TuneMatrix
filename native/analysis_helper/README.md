# TuneMatrix Native Analysis Helper

This directory contains the native C++ helper scaffold for future Essentia-based
key and BPM analysis.

Current state:

- defines the CLI contract
- defines the JSON result schema
- builds without Essentia as a stub helper
- does not replace TuneMatrix's live Python analysis path yet
- Windows MSVC builds are verified with `NMake Makefiles`
- first real Essentia version is intended to be WAV-only

Planned role:

- `tm-analysis-helper analyze --input <file> --output-json`
- return BPM/key analysis as JSON
- be bundled beside the packaged desktop app on Windows, macOS, and Linux

Recommended Windows build:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\native\analysis_helper\build_windows_msvc.ps1
```

Build with Essentia:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\native\analysis_helper\build_windows_msvc.ps1 -EnableEssentia -EssentiaRoot C:\path\to\essentia
```

For now, a build without Essentia returns a structured runtime error instead of
fake analysis data.
