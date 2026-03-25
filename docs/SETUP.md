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
- `torchcodec`

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

### torchcodec

The current Demucs runtime in this environment requires `torchcodec`.

If `torchcodec` is missing:

- `Separate Stems` is disabled
- `Process All` is disabled because it includes stem separation

## Start the Application

Run:

```powershell
python main.py
```

On first launch, check the bottom log panel. TuneMatrix logs the detected dependency state at startup.

## Output Locations

- Processed temporary files are written under the system temp directory in a `TuneMatrix` folder
- Exported files are written to the selected export directory
- Originals are never modified

## Next Checks

After setup:

1. Launch the app.
2. Import a `wav` file first.
3. Run `Analyze`.
4. Run `Match Tempo` or `Match Key`.
5. Export the result.

Then use [Testing Guide](TESTING.md) to verify the installation.
