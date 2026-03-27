# Architecture Notes

## High-Level Structure

TuneMatrix is split into a small set of focused modules:

- [main.py](../main.py): starts the Qt application
- [main_window.py](../main_window.py): owns the UI, user interactions, and thread lifecycle
- [workers.py](../workers.py): background worker objects used from `QThread`
- [audio_processing.py](../audio_processing.py): audio analysis, transforms, export, and dependency checks
- [models.py](../models.py): shared dataclasses and constants
- [utils.py](../utils.py): utility helpers

## Data Model

The central model is `SongRecord` in [models.py](../models.py).

Each record stores:

- original file path and file name
- analyzed metadata such as duration, BPM, detected key, relative key, and compatible keys
- per-song processing settings such as target BPM, target key, selected stems, and reference song
- current UI status
- generated stems directory
- processed output path
- last error text

`ProcessingOptions` now only carries the remaining global export settings needed by the workers.

Project sessions are stored as JSON with:

- a format version
- serialized `SongRecord` entries
- persisted global UI state such as the export folder and key display preference

## UI Flow

The main UI lives in `MainWindow`.

Key responsibilities:

- import and validate files
- save and restore project state
- maintain the in-memory song list
- mirror song data into the table
- apply the global key-display preference to visible key labels and tooltips
- bind the right sidebar to the current song selection
- create and manage worker threads
- log progress and errors
- gate actions based on missing dependencies

## Threading Model

Heavy work is not run on the UI thread.

The app uses:

- `QThread`
- worker `QObject` subclasses
- Qt signals for progress, logs, errors, and song updates

This keeps the Qt event loop responsive while audio operations run in the background.

## Processing Flow

### Analyze

1. `MainWindow` creates `AnalyzeWorker`
2. worker calls `analyze_audio`
3. duration, BPM, rough key, relative key, and compatible keys are written back to the `SongRecord`
4. UI updates the table row

### Separate Stems

1. `MainWindow` creates `ProcessingWorker` with action `separate`
2. worker calls `separate_song_stems`
3. `audio_processing.py` loads Demucs in-process and runs the model directly
4. generated stems are written into a cache folder for the song

### Match Tempo and Match Key

1. worker ensures analysis metadata is present
2. processing uses the original file or latest processed file
3. new audio is written to the cache area
4. `SongRecord.processed_path` is updated

### Export

1. export copies the processed file and stem directory if present
2. if no processed artifacts exist, the original file is copied instead

## Caching and Output

Temporary processing outputs are stored in a per-song cache folder under the Windows temp directory:

```text
C:\Users\<you>\AppData\Local\Temp\TuneMatrix\
```

Current subfolders:

- `processed\`
- `stems\`

Benefits:

- original media remains untouched
- repeated runs do not overwrite source files
- exported files can be produced from cached outputs

## Dependency Gating

`audio_processing.py` performs dependency inspection and reports issues per action.

The startup dependency summary is intentionally limited to the libraries and executables used by the current runtime path, so it does not include unrelated optional packages.

`main_window.py` uses that information to:

- disable unsupported actions
- show tooltips explaining why
- block invalid runs before worker startup

## Session Persistence

Project save/load is handled in `MainWindow`.

The window:

- collects current songs and global output settings into a JSON-safe dict
- writes the session to disk
- restores songs, table rows, and control state from a saved project
- marks missing source files as `Error` on restore instead of silently dropping them

## Current Limitation

Key matching is currently tonic-based pitch shifting. It does not perform true harmonic mode conversion between major and minor. Relative and compatible keys are derived from the detected key, so their quality is limited by the rough key detection step.
