# Setup Guide

## Requirements

- Python 3.11 or 3.12
- Windows, macOS, or Linux with Qt widget support
- Optional but recommended system tools on `PATH`:
  - `ffmpeg`
  - `rubberband`

For contribution workflow expectations, see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Python Dependencies

Install the application dependencies from [requirements.txt](../requirements.txt):

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The current dependency list includes:

- `PySide6`
- `numpy`
- `librosa`
- `soundfile`
- `pyrubberband`
- `demucs`
- `torch` through the Demucs runtime stack

For lightweight test-only environments, install [requirements-test.txt](../requirements-test.txt) instead of the full runtime stack.

## External Tools

### ffmpeg

`ffmpeg` is required for decoding compressed formats such as `mp3` and `m4a`.

If `ffmpeg` is missing:

- those formats can still be imported into the table
- analyze and processing actions will be blocked for those files
- `wav` and `flac` still work

### rubberband

`rubberband` is recommended for better time stretching and pitch shifting.

If `rubberband` is missing:

- the app can still fall back to `librosa` for tempo and key processing
- quality and behavior may differ from Rubber Band

### Demucs Runtime

Stem separation uses Demucs in-process.

If the Demucs runtime is incomplete:

- `Separate Stems` is disabled
- `Process All` is disabled because it includes stem separation

At minimum, make sure these Python packages are installed:

- `demucs`
- `torch`
- `numpy`
- `librosa`
- `soundfile`

## Start the Application

Run:

```powershell
python main.py
```

On first launch, check the bottom log panel. TuneMatrix logs the detected dependency state at startup.

The startup log intentionally reports only the dependencies used by the current implementation:

- `librosa`
- `numpy`
- `soundfile`
- `pyrubberband`
- `rubberband`
- `ffmpeg`
- `torch`
- `demucs`

## Developer Setup

For local development:

1. Install runtime dependencies from [requirements.txt](../requirements.txt).
2. Install test dependencies from [requirements-test.txt](../requirements-test.txt) if you are using a lightweight CI-style environment.
3. Run the tests from [docs/TESTING.md](TESTING.md).
4. Launch the app with `python main.py` and manually verify UI changes.

Headless test runs should set `QT_QPA_PLATFORM=offscreen` as described in [docs/TESTING.md](TESTING.md).

## Output Locations

- On Windows, processed temporary files are written under:

```text
C:\Users\<you>\AppData\Local\Temp\TuneMatrix\
```

- Inside that cache root, TuneMatrix creates per-song folders under:
  - `processed\`
  - `stems\`
- Exported files are written to the selected export directory
- Originals are never modified

## Next Checks

After setup:

1. Launch the app.
2. Import a `wav` file first.
3. Leave each song row's `BPM Range` and `Key Hint` columns on `Auto` unless you want to guide analysis.
   `BPM Range` keeps preset dropdown choices and also includes `Enter BPM...` for manual exact BPM input such as `102.474` or manual ranges such as `102.474-110.2`.
4. Run `Analyze` and confirm the table fills detected key, relative key, and compatible keys.
5. In the right sidebar, choose a per-song `Processing Mode` if you want to tune tempo/key quality:
   `Balanced`, `High Quality Mix`, `Vocal`, `Percussive`, or `Fast Preview`.
   `High Quality Mix` is the better choice for wide full-song mixes and now uses Rubber Band's slower high-quality pitch path, while `Vocal` keeps lead vocals more centered and stable with formant preservation.
6. Run `Match Tempo` or `Match Key`.
7. Export the result.

Then use [Testing Guide](TESTING.md) to verify the installation.

If setup fails, check [Troubleshooting](TROUBLESHOOTING.md) before opening an issue.
