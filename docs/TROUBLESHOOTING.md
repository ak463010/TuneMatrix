# Troubleshooting

## Buttons Are Disabled

TuneMatrix disables some actions when required runtime support is missing.

Check the bottom log panel at startup for dependency status and disabled-feature messages.

The startup diagnostics show only the dependencies used by the current implementation. Older optional libraries that are not part of the active pipeline are intentionally omitted.

Common examples:

- `Separate Stems` disabled: Demucs or PyTorch runtime missing
- `Process All` disabled: stem separation dependency missing
- analyze blocked for `mp3` or `m4a`: `ffmpeg` missing

## mp3 or m4a Files Import but Do Not Analyze

Cause:

- `ffmpeg` is not available on `PATH`

Effect:

- the files can appear in the table
- analyze and processing actions are blocked for those files

Fix:

- install `ffmpeg`
- ensure the executable is on `PATH`
- restart the app

## Stem Separation Fails or Is Disabled

Cause:

- missing `demucs`
- missing Torch runtime pieces
- missing `librosa`, `numpy`, or `soundfile` required by the in-process stem path

Fix:

```powershell
pip install -r requirements.txt
```

Then restart the application.

If the problem continues, verify in the app log that `demucs`, `torch`, `librosa`, `numpy`, and `soundfile` are all available.

## Tempo or Key Matching Quality Is Poor

Cause:

- `rubberband` is missing, so the app falls back to `librosa`

Effect:

- lower-quality or different-sounding time stretch and pitch shift results

Fix:

- install Rubber Band
- ensure `rubberband` is available on `PATH`

## Key Matching Did Not Change Major to Minor

This is a current limitation.

The app currently:

- shifts the tonic
- keeps the existing mode

So a request like `A Major -> C Minor` will move the tonic toward `C`, but it will not perform full reharmonization into a real minor mode.

## Relative or Compatible Keys Look Wrong

Cause:

- the app first performs rough key detection
- relative and compatible keys are then derived from that detected key

Effect:

- if the detected key is wrong, the relative and compatible suggestions will also be wrong

Notes:

- the relative key is the strict major/minor pair for the detected key
- compatible keys are generated from a circle-of-fifths style heuristic, not full musical analysis

## Tests Fail on Headless Machines

Set:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
```

Or use:

```bat
run_tests.bat
```

The batch file already sets that environment variable.

## The UI Looks Wrong at Fullscreen

Recent fixes:

- right controls panel is scrollable
- bottom log area is compact
- left table area gets more width

If layout still looks wrong, restart after pulling the latest code and retest.

## Where Temporary Files Are Stored

On Windows, TuneMatrix keeps temporary processed audio and stem cache files under:

```text
C:\Users\<you>\AppData\Local\Temp\TuneMatrix\
```

Typical cache subfolders:

- `processed\`
- `stems\`

These are cache files, not exported deliverables.
