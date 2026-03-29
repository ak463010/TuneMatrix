# Architecture Notes

## High-Level Structure

TuneMatrix is split into a small set of focused modules:

- [main.py](../main.py): starts the Qt application
- [main_window.py](../main_window.py): owns the UI, user interactions, and thread lifecycle
- [workers.py](../workers.py): background worker objects used from `QThread`
- [audio_processing.py](../audio_processing.py): audio analysis, transforms, export, and dependency checks
- [analysis_helper.py](../analysis_helper.py): Python bridge for the future native analysis helper contract
- [models.py](../models.py): shared dataclasses and constants
- [utils.py](../utils.py): utility helpers

There is also an early native helper scaffold under:

- [native/analysis_helper](../native/analysis_helper): C++ CLI contract for future native BPM/key analysis

## Data Model

The central model is `SongRecord` in [models.py](../models.py).

Each record stores:

- original file path and file name
- analyzed metadata such as duration, BPM, detected key, relative key, and compatible keys
- per-song processing settings such as target BPM, target key, processing mode, and selected stems
- per-song stem source stored with the song and edited from the `Separate Stems` workflow card settings
- current UI status
- generated stems directory
- processed output path
- last error text

`ProcessingOptions` now carries the global export settings plus the currently enabled ordered workflow steps.

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
- maintain the fixed workflow pipeline state for `Match Key -> Match Tempo -> Separate Stems`
- update the workflow visualization based on the current song selection and each song's configured targets
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

The repo now also includes a native helper scaffold, but it is not active yet:

- [analysis_helper.py](../analysis_helper.py) can locate and invoke a future `tm-analysis-helper` binary
- [native/analysis_helper](../native/analysis_helper) defines the CLI and JSON contract
- the live app still uses the existing Python `librosa` analysis path until that helper is implemented and wired in

`MainWindow` now also has an automatic analysis queue:

- newly imported songs start analysis automatically when the app is idle
- if another task is running, those songs move to `Queued for analysis`
- changing a song's `BPM Range` or `Key Hint` also queues re-analysis for that specific song
- if a hint change affects a song in the active analysis batch, the current analysis run is canceled and restarted with the latest values

### Workflow Execution

1. `MainWindow` builds the fixed workflow from the enabled sidebar steps
2. `ProcessingWorker` executes those enabled steps in order for each selected song
3. key/tempo steps operate on the current mix until stem separation runs
4. each song's `Processing Mode` maps to real Rubber Band argument presets for tempo and key processing
5. `Separate Stems` can use either the original track or the latest available workflow audio for each song
6. after stem separation, later key/tempo steps operate on each generated stem file
7. final artifacts are auto-exported to the chosen output folder

### Match Tempo and Match Key

1. worker ensures analysis metadata is present
2. processing uses the original file or latest processed file
3. new audio is written to the cache area
4. `SongRecord.processed_path` is updated
5. successful results are then auto-exported to the chosen output folder

### Export

1. primary processing actions export automatically after a successful run
2. the manual `File > Export Cached Results` action copies the processed file and stem directory if present
3. if no processed artifacts exist for the manual export action, the original file is copied instead

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
