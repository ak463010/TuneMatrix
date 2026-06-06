# Packaging and Release Artifacts

TuneMatrix release artifacts are built by GitHub Actions from version tags such as `v0.1.0`.

The first packaging pipeline is intended to make the app easier to try on Windows, macOS, and Linux. These artifacts are preview-quality distribution packages, not signed production installers.

## Artifact Types

For each release tag, the release workflow creates portable archives and installer-style artifacts where practical.

### Windows

Expected artifacts:

- `TuneMatrix-<version>-windows-x64.zip`
- `TuneMatrix-<version>-windows-x64-setup.exe`

The zip is the primary MVP distribution format. Extract it and run `TuneMatrix.exe` from the extracted `TuneMatrix` folder.

The setup executable is an unsigned NSIS installer that installs under the current user's local application data folder and creates shortcuts.

### macOS

Expected artifacts:

- `TuneMatrix-<version>-macos.zip`
- `TuneMatrix-<version>-macos.dmg`

The macOS artifacts are unsigned and not notarized. macOS Gatekeeper may block or warn about them until the project adds Developer ID signing and notarization.

### Linux

Expected artifacts:

- `TuneMatrix-<version>-linux-x64.tar.gz`
- `TuneMatrix-<version>-linux-x64.deb`

The tarball is the primary MVP Linux distribution format. Extract it and run the `TuneMatrix` executable from the extracted folder.

The `.deb` package installs the app under `/opt/tunematrix` and adds a desktop entry. It is intended for Debian/Ubuntu-style systems and is not universal Linux packaging.

## GitHub Actions Workflow

Release artifacts are built by [.github/workflows/release.yml](../.github/workflows/release.yml).

The workflow runs when:

- it is started manually with `workflow_dispatch`
- a Git tag matching `v*` is pushed

Manual runs upload artifacts to the workflow run. Tag runs also upload artifacts to the matching GitHub Release.

## Local Build

Install runtime and build dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

Build the PyInstaller output:

```powershell
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean packaging\pyinstaller\TuneMatrix.spec
```

Run the packaged smoke test:

```powershell
.\dist\TuneMatrix\TuneMatrix.exe --smoke-test
```

On macOS/Linux, use the platform executable path created under `dist/`.

## Smoke Test Mode

TuneMatrix supports a packaging smoke mode:

```powershell
python main.py --smoke-test
```

This mode starts Qt, constructs the main window, then exits automatically. It is used by the release workflow to catch packaging failures without opening an interactive session.

You can also set:

```text
TUNEMATRIX_SMOKE_TEST=1
```

## External Tools

Release artifacts stage vetted third-party runtime tools during GitHub Actions builds without committing those binaries to Git.

Current bundled-tool coverage:

- Windows: bundled `ffmpeg` and Rubber Band.
- macOS: bundled Rubber Band; `ffmpeg` is still expected from `PATH` or local staging until a pinned macOS provider is selected.
- Linux: bundled `ffmpeg`; Rubber Band is still expected from `PATH` or local staging until Linux source-build bundling is added.

TuneMatrix can find tools from:

- explicit environment variables such as `TUNEMATRIX_FFMPEG` or `TUNEMATRIX_RUBBERBAND`
- the bundled `tools/<tool>/` layout inside release artifacts or local staging
- the system `PATH`

Bundled third-party tools are separately licensed and include `NOTICE.txt` / `PROVENANCE.txt` files in the artifact. See [tools/README.md](../tools/README.md) for the expected layout.

## Packaged Feature Limitations

- `mp3` and `m4a` import/processing requires `ffmpeg`; Windows and Linux release artifacts currently bundle it, while macOS still needs a system or locally staged `ffmpeg`.
- Higher-quality tempo/key processing prefers `rubberband`; Windows and macOS release artifacts currently bundle it, while Linux still needs a system or locally staged Rubber Band.
- Standard packaged binaries intentionally exclude the heavy Demucs/Torch/TorchCodec stack to stay under GitHub release asset limits. Users who need stem separation should run TuneMatrix from source until a separate full/stems build is added and verified.

## Unsigned Build Warnings

The first release artifacts are unsigned:

- Windows may show Microsoft Defender SmartScreen warnings.
- macOS may show Gatekeeper warnings or block launch until manually approved.
- Linux desktops may require marking extracted executables as executable depending on archive tooling and filesystem behavior.

Signing, notarization, AppImage/Flatpak, MSI, Homebrew, and auto-update support are future packaging improvements.

## Release Checklist

Before publishing a release with binaries:

1. Run the normal unit tests.
2. Run `python main.py --smoke-test` locally.
3. Run the release workflow manually.
4. Download and manually launch the workflow artifacts where possible.
5. Push a release candidate tag such as `v0.1.0-rc1`.
6. Confirm artifacts attach to the GitHub Release.
7. Update release notes with known limitations and optional dependency requirements.
