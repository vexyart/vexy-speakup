<!-- this_file: CHANGELOG.md -->
# Changelog

## 1.0.2
- Free plugins (PodcastPlugins 1.0.0, master_me 1.3.1, Noise Repellent 0.4.1,
  Vocal Gate 1.0.5; macOS + Windows x64) now live in the
  Git LFS repo `vexyart/vexy-speakup-assets`. The package ships a pinned
  manifest (`assets_manifest.json`, commit + SHA-256) and downloads bundles on
  demand into the user data folder (`VEXY_SPEAKUP_ASSETS_DIR` overrides). A chain
  plugin missing from `plugin_root` resolves to the bundled copy. New commands:
  `assets fetch`, `assets list`. Parallel workers installing the same bundle no
  longer clobber each other.
- Vocal Gate for Windows is the vendor's Inno Setup installer (stored in LFS
  unmodified). On Windows, `assets fetch` or first use runs it silently; it asks
  for administrator rights (UAC), installs into Common Files\VST3 plus the VC++
  runtime, and logs next to the assets. One install runs at a time.
- `run` and batch rendering no longer force `HF_HUB_OFFLINE=1`, so first-use
  weight downloads work; cached pinned weights load without network.
- Removed `VEXY_SPEAKUP_TTS_ROOT` and the `paths.tts_root` setting; no external
  myasr/myaud/.external folder is needed. Old config files with `tts_root`
  still load and the key is ignored. The GUI settings dialog drops the adapters
  folder field.
- Bundled model code as `vexy_speakup.model_worker`, run as a child process
  (`diarize|score|deepfilter`) so cancellation and timeouts still kill it. Logs
  go to the run folder: `diarization.log`, `metrics.log`, `deepfilter.log`.
- Added the optional `models` extra (macOS Apple Silicon): `mlx-audio`,
  `huggingface-hub`, `onnxruntime`, `sentencepiece`, `speechonnxmetrics`.
  `run-gui.sh` installs it. A missing extra raises `ModuleNotFoundError` naming
  the install command; evaluation records it per window.
- Weights now download on first use into the standard Hugging Face cache,
  pinned by commit. The `mlx` diarizer output is unchanged; its raw report is
  now `diarization-native.json`.
- `sortformer` now runs Sortformer v2.1 fp16 on MLX in 30 s chunks (was the
  native `nemo-speech` host with a Q8 GGUF of v2).
- `--ai=deepfilter` now runs DeepFilterNet3 on MLX (`iky1e/DeepFilterNet3-MLX`),
  the same `model.safetensors` as the former CoreML package; outputs differ
  slightly. Writes `deepfilter-receipt.json` with weight hashes; the binary and
  catalog hash check is gone.
- Scoring uses `speechonnxmetrics` DNSMOS/UTMOS with the same scores as before.
  `--metrics_python` is now an optional alternative interpreter.
- Added executable `run-gui.sh` to launch the browser UI with its optional
  dependencies and forward folder/port/browser options.
- Added a local browser listening interface (`gui`) with folder browsing,
  level-matched representative clips, tone variants, per-file speaker choices,
  saved batch jobs, playback and stop/resume controls. The optional `gui` extra
  uses FastAPI/Uvicorn; Qt is not required.
- Cancel native subprocess groups on stop, shutdown or interrupted runners;
  preserve completed work and resume cancelled jobs through verified reports.
- Added four useful comparison candidates: GPL PodcastPlugins TRACK/MASTER,
  dxRevive, brighter dxRevive and Clear. Added standalone and per-speaker voice
  brightness, plus a brighter PodcastPlugins profile.
- Added `schedule`, `job` and `batch` CLI commands with persisted choices,
  distinct variant suffixes, shared decode/diarization, bounded concurrency,
  hash/report-verified resume, interrupted-state recovery and per-task failures.
- Added explicit whole-recording processing (`--diarizer=none`) for workflows
  that do not need individual speaker choices or local models.
- Record operational plugin latency after rendering and final output hashes.
- Added platformdirs-located TOML app settings and `config path/init/show`.
  Settings configure plugin/model folders, processing defaults and candidate
  plugin chains; environment and explicit CLI options take precedence.
- Render chunk shards in isolated processes with configurable `--workers`,
  retaining per-speaker overrides and independent receipts.
- Verified the legacy speech-polish source and test coverage before retiring
  duplicate scripts; preserve historical recording evidence privately.

## 1.0.0
- Added `build.sh` (test, build, twine check) and `publish.sh` (test,
  gitnextver tag, build, `uv publish` with retry on rate limits).
- Ported the `speech-polish` script collection into the installable
  `vexy_speakup` src-layout package with a `vexy-speakup` Fire CLI.
- Versions now come from git tags through hatch-vcs; the generated
  `__version__.py` is ignored by git. Added a `version` command.
- Plugin workers run as `python -m vexy_speakup`, so the installed package
  needs no adjacent script.
- Replaced machine-specific paths: plugins default to
  `/Library/Audio/Plug-Ins/VST3` (`VEXY_SPEAKUP_PLUGIN_ROOT`), and local model
  adapters come from `VEXY_SPEAKUP_TTS_ROOT`, resolved only when used.
- Folded the standalone plugin probe script into the `probe` command.
