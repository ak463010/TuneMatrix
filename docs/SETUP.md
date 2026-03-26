# Setup Guide

## Requirements

- Python 3.11 or 3.12
- Windows, macOS, or Linux with Qt widget support
- Optional but recommended system tools on `PATH`:
  - `ffmpeg`
  - `rubberband`

## Python Dependencies

Install the application dependencies from [requirements.txt](../requirements.txt):

```powershell
python -m venv .venv
.\.venv\Scripts\activate
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
- `torch`

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

## Output Locations

- Processed temporary files are written under the system temp directory in a `TuneMatrix` folder
- Exported files are written to the selected export directory
- Originals are never modified

## Next Checks

After setup:

1. Launch the app.
2. Import a `wav` file first.
3. Leave each song row's `BPM Range` and `Key Hint` columns on `Auto` unless you want to guide analysis.
4. Run `Analyze` and confirm the table fills detected key, relative key, and compatible keys.
5. Run `Match Tempo` or `Match Key`.
6. Export the result.

Then use [Testing Guide](TESTING.md) to verify the installation.
