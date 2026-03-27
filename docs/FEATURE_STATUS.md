# Feature Status

This file describes the current implementation status against the requested feature set.

## Implemented

### Desktop GUI

- PySide6 Qt Widgets application
- main window with menu bar
- left song table
- right control panel
- bottom progress bar and log console
- drag and drop import
- dark styling

### Song Management

- import multiple files
- save and load project sessions
- remove selected
- clear list
- table columns for file name, full path, per-song BPM range hint, per-song key hint, duration, BPM, key, relative key, compatible keys, and status
- global key-display preference for `Auto`, `Prefer Sharps`, and `Prefer Flats`
- exported processed filenames that include key names respect the global key-display preference

### Analysis

- newly imported songs are auto-analyzed in the background
- changing a song's `BPM Range` or `Key Hint` queues automatic re-analysis for that song
- `BPM Range` and `Key Hint` remain editable while tasks are running; changing them restarts active analysis or queues fresh analysis after the current non-analysis task
- duration detection with `librosa`
- BPM estimation with `librosa`
- optional per-song BPM-range hint to reduce half-time/double-time BPM ambiguity
- BPM range cells accept presets plus manual entries such as `128` or `120-130`
- rough key detection using chroma features
- optional per-song key-hint dropdown used as a soft tie-breaker when detection is close
- relative key derived from the detected key
- compatible-key list derived from the detected key using circle-of-fifths neighbors and relative major/minor relationships
- background worker execution through `QThread`

### Processing

- stem separation entry point using Demucs
- tempo matching
- key pitch shifting
- per-song target BPM, target key, and stem selection through the right sidebar
- fixed workflow pipeline for `Match Key -> Match Tempo -> Separate Stems`
- per-selection workflow visualization showing when a step will run, partially run, or be skipped
- per-song stem-source choice for `Separate Stems` exposed from the workflow card settings button: `Latest Available Audio` or `Original Track`
- global output-folder selection
- ordered workflow worker pipeline for selected songs
- separate stems, match tempo, match key, and workflow actions auto-export processed files and stems to the selected output folder
- manual fallback export is still available from the `File` menu as `Export Cached Results`

### Reliability and Tooling

- dependency-aware UI gating
- readable log and message-box errors
- automated unittest suite
- GitHub Actions test workflow
- JSON project persistence with song metadata, global output settings, and key-display preference

## Partially Implemented

### Key and Scale Matching

Current behavior:

- tonic can be pitch-shifted
- relative key and compatible keys are shown after analysis
- current mode is preserved

Not fully implemented yet:

- exact scale conversion between major and minor
- harmonic analysis beyond rough key detection and derived key-relationship heuristics

### Stem Separation

The code path is implemented, but actual runtime success depends on the full Demucs stack being installed and working.

In the current environment:

- the old Demucs CLI path has been replaced with an in-process separation path
- `wav` and `flac` can now be separated through the in-process loader path used by the app
- stem actions still require the Demucs and PyTorch runtime to be installed

### mp3 and m4a Support

These formats are accepted by the UI, but actual analysis and processing requires `ffmpeg`.

So support is conditional rather than fully self-contained.

## Not Implemented Yet

- waveform preview
- packaged desktop installer
- integration tests against real Demucs output
- exact musical reharmonization or scale-aware mode conversion
- user-defined export folder templates
- user-defined export filename templates with placeholder variables

## Recommended Next Steps

1. Add an in-app diagnostics dialog that shows install commands for missing dependencies.
2. Add worker-level tests for cancel and multi-song flows.
3. Package the app for Windows once the runtime dependencies are stable.
4. Add configurable export naming templates with preview and validation.
5. Revisit key matching if exact harmonic mode conversion is a hard requirement.
