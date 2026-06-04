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
2. Confirm [README.md](../README.md), [docs/SETUP.md](SETUP.md), [docs/FEATURE_STATUS.md](FEATURE_STATUS.md), and [docs/PACKAGING.md](PACKAGING.md) describe the current behavior.
3. Run the unit test suite locally:

   ```powershell
   $env:QT_QPA_PLATFORM = "offscreen"
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   ```

4. Run source smoke mode locally:

   ```powershell
   $env:QT_QPA_PLATFORM = "offscreen"
   .\.venv\Scripts\python.exe main.py --smoke-test
   ```

5. Confirm GitHub Actions passes on the supported OS/Python matrix.
6. Run the release-artifact workflow manually and confirm Windows, macOS, and Linux artifacts upload successfully.
7. Download generated artifacts and manually launch them where possible.
8. Manually launch TuneMatrix from source.
9. Import a small `wav` file, confirm analysis runs, and export a result.
10. Check optional dependency behavior for `ffmpeg`, `rubberband`, and the Demucs/PyTorch runtime if the release notes mention those paths.
11. Confirm generated audio, `exports/`, temporary files, local environments, and personal editor settings are not committed.
12. Review third-party license obligations before distributing packaged binaries.

## Tagging a Release

1. Make sure the main branch is green in CI.
2. Create an annotated Git tag, for example `v0.1.0`.
3. Push the tag to GitHub. The release-artifact workflow creates or updates the matching GitHub Release and attaches artifacts.
4. Confirm the Release contains the Windows zip/setup executable, macOS zip/DMG, and Linux tarball/Debian package.
5. Publish release notes using the relevant [CHANGELOG.md](../CHANGELOG.md) section.
6. Include known limitations, unsigned-build warnings, and optional dependency requirements in the release notes.

## Binary Distribution Notes

Open-sourcing TuneMatrix source code under the MIT License does not replace the licenses of bundled or invoked dependencies.

The first GitHub release artifacts are unsigned preview packages:

- Windows setup files may trigger Microsoft Defender SmartScreen.
- macOS DMG/app artifacts are not notarized and may trigger Gatekeeper warnings.
- Linux `.deb` packages are Debian/Ubuntu-oriented and are not universal Linux installers.
- Demucs stem separation in packaged builds is experimental until separately hardened and verified.

Before publishing packaged binaries, review and include required notices for dependencies and external tools such as PySide6/Qt, FFmpeg, Rubber Band, Demucs, Torch, `librosa`, `soundfile`, `pyrubberband`, and any bundled native helper/runtime tools.

See [docs/PACKAGING.md](PACKAGING.md) for artifact names, local build commands, and packaged-app limitations.
