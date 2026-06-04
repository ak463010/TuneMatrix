# Contributing to TuneMatrix

Thank you for your interest in improving TuneMatrix. This project is an MVP/alpha desktop music-processing app, so focused issues, small pull requests, and clear test notes are especially helpful.

## Ways to Contribute

Good contribution areas include:

- Bug reports with reproducible steps.
- Documentation fixes and setup notes for Windows, macOS, and Linux.
- Tests for utilities, audio-processing behavior, workers, and UI state.
- Dependency detection and troubleshooting improvements.
- UI/UX improvements that keep the app responsive.
- Audio-processing improvements that preserve original files.

## Before You Start

- Read [README.md](README.md), [docs/SETUP.md](docs/SETUP.md), and [docs/FEATURE_STATUS.md](docs/FEATURE_STATUS.md).
- Search existing issues and pull requests.
- Open an issue before starting large features, dependency changes, packaging work, or architecture changes.
- Keep pull requests focused. Smaller changes are easier to review and test.

## Development Setup

TuneMatrix supports Python 3.11 and 3.12.

Install runtime dependencies from [requirements.txt](requirements.txt):

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

For full setup details and optional tools such as `ffmpeg` and `rubberband`, see [docs/SETUP.md](docs/SETUP.md).

## Running Tests

The default test runner is Python's standard `unittest` discovery.

Windows PowerShell:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

macOS/Linux:

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

The Windows convenience script is also available:

```bat
run_tests.bat
```

See [docs/TESTING.md](docs/TESTING.md) for details about CI and known test warnings.

## Coding Guidelines

- Match the style and naming of nearby code.
- Prefer clear, small functions over clever abstractions.
- Keep Qt UI updates on the main thread.
- Keep long-running audio work inside worker objects and `QThread` flows.
- Do not modify original audio files. Write generated artifacts to cache/export locations only.
- Preserve dependency-aware behavior: missing optional tools should produce clear user-facing messages rather than crashes.
- Avoid adding heavy dependencies without opening an issue first.
- Update docs and tests when behavior changes.

## Commit and Pull Request Guidelines

Use short, imperative commit subjects when possible, for example:

- `fix export naming for target keys`
- `document ffmpeg setup on Windows`
- `test duplicate song import handling`

Before opening a pull request:

- Run the unit tests.
- Manually launch the app if UI behavior changed.
- Update [CHANGELOG.md](CHANGELOG.md) for user-facing changes.
- Update docs when setup, behavior, dependencies, or limitations change.
- Confirm generated audio files, `exports/`, temp files, local environments, and personal editor settings are not committed.

## Dependency Policy

TuneMatrix uses a lightweight test dependency set in [requirements-test.txt](requirements-test.txt) so CI does not need the full Demucs/Torch runtime. If you add or change dependencies:

- Explain why the dependency is needed.
- Update [requirements.txt](requirements.txt) or [requirements-test.txt](requirements-test.txt) as appropriate.
- Update [docs/SETUP.md](docs/SETUP.md) and [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) if setup changes.
- Consider license and binary distribution implications.

## Code of Conduct

All participation is covered by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security

Please do not report security vulnerabilities in public issues. Follow [SECURITY.md](SECURITY.md).
