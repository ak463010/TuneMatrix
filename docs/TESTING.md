# Testing Guide

## Current Test Runner

The repository uses the Python standard library `unittest` runner.

Primary command:

```bat
run_tests.bat
```

That script:

- prefers `.venv\Scripts\python.exe` if it exists
- sets `QT_QPA_PLATFORM=offscreen`
- runs all tests under `tests/`

Equivalent direct command:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Test Files

- [tests/test_utils.py](../tests/test_utils.py)
- [tests/test_audio_processing.py](../tests/test_audio_processing.py)
- [tests/test_main_window.py](../tests/test_main_window.py)

## What Is Covered

### Utility tests

- duration, BPM, and key formatting
- key-list formatting
- filename and path helpers
- supported-file validation

### Audio processing tests

- metadata analysis for a generated `wav`
- relative-key and compatible-key helper mapping
- dependency gating for `ffmpeg` and the active Demucs runtime stack
- tempo matching
- key shifting
- export behavior

### Main window tests

- action enable/disable state based on dependency messages
- processing option parsing
- duplicate import handling
- blocking an action when runtime issues exist
- project-state persistence of analyzed key-relationship columns

## CI

GitHub Actions workflow:

- [.github/workflows/tests.yml](../.github/workflows/tests.yml)

The workflow:

- uses Python 3.11
- installs `requirements-test.txt`
- runs the same unittest discovery command

## Test Dependencies

CI uses [requirements-test.txt](../requirements-test.txt) instead of the full runtime dependency list.

This keeps CI lightweight by avoiding the full Demucs/Torch install for tests that do not need it.

## Known Test Warnings

You may see warnings from `librosa` or `audioread` during the synthetic-audio tests.

These are currently expected and do not fail the suite.

## Adding More Tests

Recommended next additions:

1. worker-level tests for cancel behavior and status transitions
2. integration tests around export naming and multiple-song processing
3. optional Demucs integration tests guarded behind an environment flag
