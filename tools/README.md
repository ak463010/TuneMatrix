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
