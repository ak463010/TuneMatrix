TuneMatrix looks for bundled runtime tools here before it falls back to `PATH`.

Recommended layout:

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
  rubberband/
    rubberband(.exe)
    bin/
      rubberband(.exe)
```

Platform notes:

- Windows uses `.exe` binaries.
- macOS and Linux use the same folders, but the executables do not have a `.exe` suffix.
- You can also override individual tool paths with environment variables such as:
  - `TUNEMATRIX_ANALYSIS_HELPER`
  - `TUNEMATRIX_FFMPEG`
  - `TUNEMATRIX_RUBBERBAND`

Staging command:

```powershell
python .\scripts\stage_runtime_tools.py
```

That command tries to discover:

- `tm-analysis-helper`
- `ffmpeg`
- `ffprobe`
- `rubberband`

and copies any it finds into this `tools/` layout.

Windows helper build shortcut:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\native\analysis_helper\build_windows_msvc.ps1 -EnableEssentia -StageToTools
```

That builds the helper and immediately stages `tm-analysis-helper.exe` into `tools/analysis-helper/`.
