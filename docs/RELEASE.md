# Release Process

This checklist is for maintainers preparing a public TuneMatrix release.

## Versioning

TuneMatrix uses Semantic Versioning once public releases begin:

- MAJOR versions contain incompatible changes.
- MINOR versions add backward-compatible features.
- PATCH versions fix bugs.

During the MVP stage, prefer `0.x.y` versions and clearly label preview releases.

## Pre-release Checklist

1. Update [CHANGELOG.md](../CHANGELOG.md).
2. Confirm [README.md](../README.md), [docs/SETUP.md](SETUP.md), and [docs/FEATURE_STATUS.md](FEATURE_STATUS.md) describe the current behavior.
3. Run the unit test suite locally:

   ```powershell
   $env:QT_QPA_PLATFORM = "offscreen"
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   ```

4. Confirm GitHub Actions passes on the supported OS/Python matrix.
5. Manually launch TuneMatrix.
6. Import a small `wav` file, confirm analysis runs, and export a result.
7. Check optional dependency behavior for `ffmpeg`, `rubberband`, and the Demucs/PyTorch runtime if the release notes mention those paths.
8. Confirm generated audio, `exports/`, temporary files, local environments, and personal editor settings are not committed.
9. Review third-party license obligations before distributing packaged binaries.

## Tagging a Release

1. Make sure the main branch is green in CI.
2. Create an annotated Git tag, for example `v0.1.0`.
3. Publish a GitHub release using the relevant [CHANGELOG.md](../CHANGELOG.md) section.
4. Include known limitations and optional dependency requirements in the release notes.

## Binary Distribution Notes

Open-sourcing TuneMatrix source code under the MIT License does not replace the licenses of bundled or invoked dependencies.

Before publishing packaged binaries, review and include required notices for dependencies and external tools such as PySide6/Qt, FFmpeg, Rubber Band, Demucs, Torch, `librosa`, `soundfile`, `pyrubberband`, and any bundled native helper/runtime tools.
