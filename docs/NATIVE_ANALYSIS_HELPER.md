# Native Analysis Helper

TuneMatrix now includes a scaffold for a future cross-platform native helper at:

- [native/analysis_helper](../native/analysis_helper)

The intent is:

- keep the main desktop app in Python
- move future high-accuracy BPM/key analysis into a small native helper
- call that helper from Python through a stable CLI + JSON contract

Current state:

- the helper project is scaffolded with CMake
- the helper binary name is `tm-analysis-helper`
- the CLI contract is defined
- the Python bridge lives in [analysis_helper.py](../analysis_helper.py)
- live app analysis still uses the existing Python `librosa` path

CLI shape:

```text
tm-analysis-helper analyze --input <audio-file> --output-json
tm-analysis-helper --print-contract
```

Planned JSON shape:

```json
{
  "backend": "essentia-cpp",
  "duration": 191.0,
  "bpm": 110.02,
  "key": "F# Major",
  "scale": "major",
  "confidence": 0.91,
  "candidates": [
    {"key": "F# Major", "score": 0.91},
    {"key": "D# Minor", "score": 0.07},
    {"key": "A# Minor", "score": 0.02}
  ],
  "error": null
}
```

Recommended rollout:

1. keep the current Python analysis path as the default
2. wire the Python bridge into an optional helper-backed analysis path
3. integrate Essentia in the native helper
4. compare the helper against the current hard reference packs
5. only then consider switching the default backend
