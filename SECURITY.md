# Security Policy

## Supported Versions

TuneMatrix is currently an MVP/alpha project. Security fixes are handled on the active `main` branch unless a release states otherwise.

| Version | Supported |
| ------- | --------- |
| `main` | Yes |
| Preview releases | Best effort |
| Older releases | No, unless otherwise stated |

## Reporting a Vulnerability

Please do not open public GitHub issues for security vulnerabilities.

Report security concerns through GitHub private vulnerability reporting or a private GitHub security advisory for this repository. If private vulnerability reporting is not enabled, contact the maintainer through GitHub and avoid posting exploit details publicly.

Include as much of the following as possible:

- Affected TuneMatrix version, release, branch, or commit.
- Operating system and Python version.
- Reproduction steps.
- Impact and likely affected users.
- Relevant logs, screenshots, or sample paths that do not contain sensitive data.
- Whether third-party tools such as `ffmpeg`, `rubberband`, Demucs, or bundled native helpers are involved.

## Response Expectations

Maintainers will triage reports on a best-effort basis and coordinate disclosure when a fix is needed. Public disclosure should wait until a fix or mitigation is available, unless there is an urgent user-safety reason to disclose sooner.

## Scope

Examples of in-scope security issues include:

- Unsafe file handling or path traversal.
- Unexpected command execution behavior.
- Processing untrusted audio files in a way that can overwrite files outside TuneMatrix-managed locations.
- Dependency or bundled-tool issues that directly affect TuneMatrix users.
- Disclosure of local file paths or sensitive information through logs or project files.

Examples of out-of-scope issues include:

- Vulnerabilities only present in unsupported forks.
- Issues in third-party tools that TuneMatrix merely documents but does not bundle or invoke.
- Denial-of-service reports based only on very large or malformed media files without a realistic user impact.
