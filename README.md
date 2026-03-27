# TuneMatrix

TuneMatrix is a desktop music-processing application built with Python and PySide6.

The current codebase focuses on:

- importing multiple songs
- saving and loading project sessions
- automatically analyzing newly imported songs
- automatically re-analyzing songs when their BPM Range or Key Hint changes
- analyzing duration, BPM, rough key, relative key, and compatible keys
- separating stems with Demucs
- matching tempo
- matching key tonic with pitch shifting
- automatically exporting processed outputs to the chosen output folder without changing the original files
- keeping the UI responsive with worker threads

## Project Status

This repository is currently an MVP with tests and documentation.

What works now:

- `wav` and `flac` import and analysis
- analysis populates detected key plus derived relative and compatible keys
- analysis supports per-song `BPM Range` and `Key Hint` table columns, both defaulting to `Auto`
- `BPM Range` keeps preset dropdown choices and includes an explicit `Enter BPM...` manual option for values such as `128` or `120-130`
- newly imported songs are auto-analyzed in the background
- changing a song's `BPM Range` or `Key Hint` triggers automatic re-analysis for that song
- a global `Key Display` preference switches visible key names between `Auto`, `Prefer Sharps`, and `Prefer Flats`
- the right sidebar edits the currently selected song or selected songs directly for target BPM, target key, stem selection, and reference song
- `Output Folder` remains a single global export setting and is persisted separately from per-song processing settings
- exported processed filenames that include key names follow the current global key-display preference
- worker-threaded analyze, tempo match, key shift, and export flows
- separate stems, match tempo, match key, and process all now auto-export on success
- manual export remains available from the `File` menu as `Export Cached Results`
- project save/load with song state, global output settings, and key-display preference persisted to JSON
- dependency-aware UI gating for unsupported actions
- startup diagnostics limited to the dependencies the current runtime path actually uses
- local test suite and CI workflow

Planned later:

- user-defined export folder and export filename templates with variable placeholders

What still depends on external tools:

- `mp3` and `m4a` processing requires `ffmpeg`
- higher-quality tempo and key processing prefers `rubberband`
- stem separation requires the Demucs and PyTorch runtime to be installed
- exact major/minor mode conversion is not implemented; key matching currently pitch-shifts tonic and keeps the existing mode
- compatible keys are derived from the detected key using a circle-of-fifths style heuristic, not deep harmonic analysis

See [docs/FEATURE_STATUS.md](docs/FEATURE_STATUS.md) for more detail.

## Quick Start

1. Create and activate a virtual environment.
2. Install Python dependencies from `requirements.txt`.
3. Install required system tools such as `ffmpeg` and `rubberband`.
4. Run the app with `python main.py`.

Windows example:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

On Windows, TuneMatrix stores temporary processed and stem cache files under:

```text
C:\Users\<you>\AppData\Local\Temp\TuneMatrix\
```

The default export folder is:

```text
<project>\exports\
```

## Run Tests

Use the provided batch file:

```bat
run_tests.bat
```

Or directly:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Documentation

- [Setup Guide](docs/SETUP.md)
- [Testing Guide](docs/TESTING.md)
- [Architecture Notes](docs/ARCHITECTURE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Feature Status](docs/FEATURE_STATUS.md)

## Project Layout

- [main.py](main.py): application entry point
- [main_window.py](main_window.py): Qt main window and UI wiring
- [workers.py](workers.py): threaded workers and task orchestration
- [audio_processing.py](audio_processing.py): analysis, processing, export, and dependency checks
- [models.py](models.py): shared data models and constants
- [utils.py](utils.py): formatting, file validation, and helper utilities
- [tests/](tests): automated tests
