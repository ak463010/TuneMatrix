# TuneMatrix

[![Tests](https://github.com/ak463010/TuneMatrix/actions/workflows/tests.yml/badge.svg)](https://github.com/ak463010/TuneMatrix/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

TuneMatrix is a desktop music-processing application built with Python and PySide6.

> **Project status:** TuneMatrix is an MVP/alpha project. Core workflows are implemented and tested, but setup, packaging, and audio-processing behavior may still change before a stable release.

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
- analysis now prefers the native Essentia helper automatically when it is available, with `librosa` fallback if the helper is unavailable or fails in `auto` mode
- analysis populates detected key plus derived relative and compatible keys
- analysis supports per-song `BPM Range` and `Key Hint` table columns, both defaulting to `Auto`
- `BPM Range` keeps preset dropdown choices and includes an explicit `Enter BPM...` manual option for exact values such as `102.474` or ranges such as `102.474-110.2`
- newly imported songs are auto-analyzed in the background
- changing a song's `BPM Range` or `Key Hint` triggers automatic re-analysis for that song
- `BPM Range` and `Key Hint` stay editable during running tasks; active analysis is restarted with the latest values, while non-analysis tasks queue the updated song for re-analysis next
- a global `Key Display` preference switches visible key names between `Auto`, `Prefer Sharps`, and `Prefer Flats`
- the right sidebar edits the currently selected song or selected songs directly for target BPM, target key, and stem selection
- the right sidebar now also exposes a per-song `Processing Mode` for tempo/key quality tuning
- the right sidebar shows a fixed workflow visualization for `Match Key -> Match Tempo -> Separate Stems`
- the `Separate Stems` workflow card now has a settings button for per-song `Stem Source`
- stem separation can use either the `Original Track` or the `Latest Available Audio`, per song, with `Latest Available Audio` as the default
- each workflow step can be enabled or disabled without changing the execution order
- the workflow visualization is selection-aware and shows when a step will run, partially run, or be skipped
- `Output Folder` remains a single global export setting and is persisted separately from per-song processing settings
- exported processed filenames that include key names follow the current global key-display preference
- worker-threaded analyze, tempo match, key shift, and export flows
- separate stems, match tempo, match key, and workflow runs now auto-export on success
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

Processing modes:

- `Balanced`: solid general-purpose option
- `High Quality Mix`: quality-first setting for full stereo mixes with less center bias, more width, and slower high-quality pitch shifting; this is the default for new songs
- `Vocal`: favors vocal timbre preservation, center stability, and formant-preserving high-quality pitch shifting
- `Percussive`: favors drum/transient material
- `Fast Preview`: fastest preview-oriented Rubber Band mode

Planned later:

- further `High Quality Mix` stereo-width tuning to push full-song results closer to high-end DAW pitch-shifting workflows

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

To stage local runtime binaries into the bundled `tools/` layout used by TuneMatrix:

```powershell
python .\scripts\stage_runtime_tools.py
```

On Windows, TuneMatrix stores temporary processed and stem cache files under:

```text
C:\Users\<you>\AppData\Local\Temp\TuneMatrix\
```

The default export folder is:

```text
<project>\exports\
```

For packaged builds, TuneMatrix now prefers bundled executables before `PATH`. The intended cross-platform runtime layout is:

```text
tools/
  analysis-helper/
    tm-analysis-helper(.exe)
  ffmpeg/
    ffmpeg(.exe)
  rubberband/
    rubberband(.exe)
```

On Windows the bundled binaries use `.exe`. On macOS and Linux the same folders are used, but the executables keep their normal names without `.exe`.

## Run Tests

Use the provided batch file:

```bat
run_tests.bat
```

Or directly:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

See [docs/TESTING.md](docs/TESTING.md) for cross-platform commands and CI details.

## Documentation

- [Setup Guide](docs/SETUP.md)
- [Testing Guide](docs/TESTING.md)
- [Architecture Notes](docs/ARCHITECTURE.md)
- [Native Analysis Helper](docs/NATIVE_ANALYSIS_HELPER.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Feature Status](docs/FEATURE_STATUS.md)
- [Release Process](docs/RELEASE.md)

## Project Layout

- [main.py](main.py): application entry point
- [main_window.py](main_window.py): Qt main window and UI wiring
- [workers.py](workers.py): threaded workers and task orchestration
- [audio_processing.py](audio_processing.py): analysis, processing, export, and dependency checks
- [analysis_helper.py](analysis_helper.py): Python bridge for the native Essentia analysis helper
- [models.py](models.py): shared data models and constants
- [utils.py](utils.py): formatting, file validation, and helper utilities
- [native/analysis_helper](native/analysis_helper): C++ helper for native Essentia BPM/key analysis
- [tests/](tests): automated tests

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [docs/TESTING.md](docs/TESTING.md) before opening a pull request.

Good first contributions include documentation fixes, setup notes for different operating systems, worker-level tests, export-naming tests, and improvements to dependency diagnostics.

## Support

For setup help and troubleshooting, see [SUPPORT.md](SUPPORT.md), [docs/SETUP.md](docs/SETUP.md), and [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

Please do not upload copyrighted audio unless you have permission to share it. When possible, reproduce issues with a short generated or public-domain test file.

## Security

Please do not report security vulnerabilities in public issues. See [SECURITY.md](SECURITY.md) for private reporting guidance.

## Releases

See [CHANGELOG.md](CHANGELOG.md) for release notes and [docs/RELEASE.md](docs/RELEASE.md) for the maintainer release checklist.

## License

TuneMatrix is licensed under the MIT License. See [LICENSE](LICENSE).

Third-party dependencies and external tools are licensed separately. If you distribute packaged builds, review the license obligations for PySide6/Qt, FFmpeg, Rubber Band, Demucs, Torch, `librosa`, `soundfile`, `pyrubberband`, and any bundled helper/runtime tools.
