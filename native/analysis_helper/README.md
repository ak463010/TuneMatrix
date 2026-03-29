# TuneMatrix Native Analysis Helper

This directory contains the native C++ helper scaffold for future Essentia-based
key and BPM analysis.

Current state:

- defines the CLI contract
- defines the JSON result schema
- builds without Essentia as a stub helper
- does not replace TuneMatrix's live Python analysis path yet

Planned role:

- `tm-analysis-helper analyze --input <file> --output-json`
- return BPM/key analysis as JSON
- be bundled beside the packaged desktop app on Windows, macOS, and Linux

Example configure/build:

```powershell
cmake -S native/analysis_helper -B build/analysis_helper
cmake --build build/analysis_helper --config Release
```

For now, a build without Essentia returns a structured runtime error instead of
fake analysis data.
