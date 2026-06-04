# Packaging

This folder contains release packaging helpers used by GitHub Actions.

The first release pipeline builds PyInstaller one-folder outputs, then turns them into:

- portable archives for Windows, macOS, and Linux
- an unsigned NSIS installer for Windows
- an unsigned DMG for macOS
- a simple Debian package for Linux

These helpers intentionally do not perform code signing, notarization, AppImage/Flatpak generation, auto-updates, or third-party runtime binary downloads.
