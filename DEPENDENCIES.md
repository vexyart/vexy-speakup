<!-- this_file: DEPENDENCIES.md -->
# Dependencies

Fire (CLI, matching vexy-subs), NumPy (sample buffers, gains and fades),
Pedalboard 0.9.26 (VST3 hosting with latency compensation; pinned because the
plugin rendering was verified with this exact wheel), SoundFile (float/RF64 WAV
streaming), pyloudnorm (BS.1770 speaker and fragment loudness).
platformdirs (OS user config location), tomli-w (editable TOML serialization).
Pydantic (versioned batch job boundary types and destination/chain invariants).
Optional `gui` extra: FastAPI (local browser API and static/audio responses),
Uvicorn (localhost server). The interface uses native browser audio controls
and plain HTML/CSS/JavaScript; it has no Qt dependency.
TOML reading uses Python's standard-library tomllib. Parallel orchestration
uses ThreadPoolExecutor; DSP stays in isolated native plugin subprocesses.

Optional `models` extra (macOS Apple Silicon): mlx-audio 0.5.7 (MLX Nemotron and
Sortformer diarization, DeepFilterNet3; pinned because outputs were verified with
it), huggingface-hub (pinned weight snapshots in the standard HF cache),
speechonnxmetrics 0.0.2a3 + onnxruntime (DNSMOS/UTMOS ONNX predictors, the same
library the earlier adapter used), sentencepiece (imported by mlx-audio's STS
package). Free GPL plugins download from the vexy-speakup-assets LFS repo with
the standard library (urllib, zipfile, hashlib); no extra dependency.

FFmpeg/ffprobe are external executables for decoding, R128 levelling, encoding
and video remuxing. Commercial VST3 plugins are user-installed and not distributed.

Build: hatchling with hatch-vcs (version from git tags).
Tests/build: pytest, pytest-cov, ruff, build, twine and HTTPX (browser API tests).
