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
- remove selected
- clear list
- table columns for file name, full path, duration, BPM, key, and status

### Analysis

- duration detection with `librosa`
- BPM estimation with `librosa`
- rough key detection using chroma features
- background worker execution through `QThread`

### Processing

- stem separation entry point using Demucs
- tempo matching
- key pitch shifting
- reference-song matching for BPM and key target selection
- process-all worker pipeline
- export processed files and stems while keeping originals unchanged

### Reliability and Tooling

- dependency-aware UI gating
- readable log and message-box errors
- automated unittest suite
- GitHub Actions test workflow

## Partially Implemented

### Key and Scale Matching

Current behavior:

- tonic can be pitch-shifted
- current mode is preserved

Not fully implemented yet:

- exact scale conversion between major and minor
- harmonic analysis beyond rough key detection

### Stem Separation

The code path is implemented, but actual runtime success depends on the full Demucs stack being installed and working.

In the current environment:

- `torchcodec` is required
- without it, stem actions are disabled

### mp3 and m4a Support

These formats are accepted by the UI, but actual analysis and processing requires `ffmpeg`.

So support is conditional rather than fully self-contained.

## Not Implemented Yet

- waveform preview
- project/session save and load
- packaged desktop installer
- integration tests against real Demucs output
- exact musical reharmonization or scale-aware mode conversion

## Recommended Next Steps

1. Add an in-app diagnostics dialog that shows install commands for missing dependencies.
2. Add worker-level tests for cancel and multi-song flows.
3. Add a project save/load feature if you want to manage larger sessions.
4. Revisit key matching if exact harmonic mode conversion is a hard requirement.
