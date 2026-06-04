# Support

Thanks for using TuneMatrix. This project is an MVP/alpha desktop music-processing app, so clear environment details make support much easier.

## Where to Get Help

- Setup and usage problems: open a GitHub issue using the bug report template.
- Feature ideas: open a GitHub issue using the feature request template.
- Documentation problems: open a GitHub issue using the documentation template.
- Security concerns: do not open a public issue; see [SECURITY.md](SECURITY.md).

## Before Opening an Issue

Please check these pages first:

- [README.md](README.md)
- [docs/SETUP.md](docs/SETUP.md)
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- [docs/FEATURE_STATUS.md](docs/FEATURE_STATUS.md)
- [docs/TESTING.md](docs/TESTING.md)

Also search existing GitHub issues to see whether the problem is already known.

## What to Include

For setup, import, analysis, processing, or export issues, include:

- Operating system and version.
- Python version.
- TuneMatrix version, release, branch, or commit.
- How you installed dependencies.
- Audio file type, such as `wav`, `flac`, `mp3`, or `m4a`.
- Whether `ffmpeg` is installed and available on `PATH`.
- Whether `rubberband` is installed and available on `PATH`.
- Whether the Demucs/PyTorch runtime is installed, if stem separation is involved.
- Steps to reproduce the issue.
- Expected behavior and actual behavior.
- Relevant messages from the TuneMatrix bottom log panel.

Do not upload copyrighted audio unless you have permission to share it. When possible, reproduce the issue with a short generated or public-domain test file.

## What Is Not Supported

- Private debugging without reproduction steps.
- Unsupported Python versions.
- Unofficial modified builds unless the issue also reproduces on this repository.
- Requests to process or share audio in ways that violate copyright or license terms.
- Vulnerability reports in public GitHub issues; use [SECURITY.md](SECURITY.md) instead.
