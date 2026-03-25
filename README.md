# TuneMatrix

TuneMatrix is a desktop music-processing application built with Python and PySide6.

The current codebase focuses on:

- importing multiple songs
- saving and loading project sessions
- analyzing duration, BPM, and rough key
- separating stems with Demucs
- matching tempo
- matching key tonic with pitch shifting
- exporting processed outputs without changing the original files
- keeping the UI responsive with worker threads

## Project Status

This repository is currently an MVP with tests and documentation.

What works now:

- `wav` and `flac` import and analysis
- worker-threaded analyze, tempo match, key shift, and export flows
- project save/load with song state and control settings persisted to JSON
- dependency-aware UI gating for unsupported actions
- local test suite and CI workflow

What still depends on external tools:

- `mp3` and `m4a` processing requires `ffmpeg`
- higher-quality tempo and key processing prefers `rubberband`
- stem separation requires the Demucs and PyTorch runtime to be installed
- exact major/minor mode conversion is not implemented; key matching currently pitch-shifts tonic and keeps the existing mode

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
