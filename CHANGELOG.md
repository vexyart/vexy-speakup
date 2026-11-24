<!-- this_file: CHANGELOG.md -->
# Changelog

## Unreleased

- PyPI releases use GitHub Actions Trusted Publishing. The PyPI project owner must configure the publisher for `vexyart/vexy-speakup`, workflow `release.yml`, environment `pypi`.
- Built and twine-checked the wheel and sdist, inspected their contents and verified each clean install by running `vexy-speakup version` from outside the checkout.
- Site now uses the fly-january 0.2.1 theme (chrome: none).
- Default chain is now `auto-gate-stageone` with `brightness_db = 3` (was `dx35`,
  0), the result of listening on dual-mono speech. It needs VoiceGate2,
  dxRevive Pro, StageOne 2 and Ozone 12; without them `run` stops with "needs
  plugins that are not installed" — pass `--profile_name` to choose another.
  The +3 dB default also applies to `schedule` candidates; set
  `brightness_db = 0` in the TOML to keep the old tone.
- `auto-gate-stageone` now adds a little StageOne 2 Depth (10 on the mid and
  high bands) and folds near-identical channels (side 60 dB or more below mid)
  to exact mono (`builtin:mono-fold`) directly before StageOne. Pedalboard
  0.9.26 offers StageOne only a 2-in/2-out bus, so it cannot receive a
  1-channel signal; exact L = R is the closest equivalent. Real stereo and
  single-channel audio pass unchanged. Chains with a fold run as Pedalboard
  segments, each compensating its own latency; streaming (master) chains
  reject a fold. Other chains, including `auto-gate`, are unchanged.
- Spatial stage after Accentize restoration: `auto-gate-wider` (VoiceGate2,
  dxRevive Pro 35 %, Polyverse Wider 50 % with low bypass at 161 Hz) and
  `auto-gate-stageone` (same, then Leapwing StageOne 2 Mono Spread 100 on the
  mid and high bands, Depth 0). Both appear only when the plugin is installed;
  `auto-gate` is unchanged. Wider is free but its EULA forbids redistribution,
  so it is not bundled: the GUI plugin list links to the vendor download when
  it is missing. On dual-mono speech Wider gives side/mid −6.7 dB and StageOne
  −17 dB, with an unchanged mono sum and no timing offset.
- Fixed: `gui` started alongside a wildcard listener on the same port (a stale
  `python -m http.server 8765`) and, once it exited, the page's API calls hit
  that server and failed with `Unexpected token '<', "<!DOCTYPE "...`. `gui`
  now refuses a port that already answers, and the page reports a stopped
  server in plain words instead of a JSON parse error.
- Fixed: continuous mastering delayed everything after the first 10 s block by
  the master chain's latency and left that much silence at the 10 s boundary
  (pedalboard pads a reset=True block). Measured before the fix: 810 samples
  (16.9 ms) with Ozone 12 Maximizer, 479 (10 ms) with PodcastPlugins MASTER.
  `render_master` now resets once and streams every block with reset=False;
  outputs align within 3 samples. Outputs mastered with a latent plugin up to
  1.0.2 carry this offset.
- Speech plugin detection: `plugin_catalog.json` snapshots the Pluginary speech
  research (role, caveat, source SHA-256) with settings verified on installed
  versions. The VST3 folder is scanned by file name only (vendor subfolders,
  never inside bundles); bundled free plugins always count. The GUI lists
  "Detected speech plugins" (`/api/plugins`).
- Automatic chains (`auto-free-denoise`, `auto-free-gate`, `auto-restore`,
  `auto-clean`, `auto-gate`, `auto-dialogue`): one plugin per stage (gate,
  denoise, dereverb, restore, integrated, tone; limiters only in master), built
  from what is detected. The two open-source chains always exist. Usable
  anywhere a profile name is (`--profile_name=auto-clean`, candidates, GUI).

## 1.0.2
- GUI: choose which chains to compare (configured candidates plus built-in
  profiles); chains whose plugins are neither installed nor bundled are greyed
  out with the missing names (`/api/chains`, `profiles.chain_options`).
- GUI speaker mode no longer forces a shared mastering chain. Speaker clips use
  the speech chain plus loudness/peak levelling; an optional final master is
  chosen after listening (default none). Overlaps use the dominant speaker's
  chain.
- Assembly crossfades adjacent fragments into each other over 40 ms using both
  renders' context, replacing the 10 ms fades through unprocessed audio.
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

## Issue 101 verification (v1.0.2)

- Retired nine duplicate scripts after auditing every legacy function and running 56 tests.
- Fixed scanner paths, output and timeouts. Pluginary passed 23 native tests and completed the rescan of 1,073 entries.
- Verified 26 research records in the Pluginary database and annotations on 16 scanned plugins (`issues/101-research.md`).
- Verified TOML settings and candidate definitions with isolated `config path/init/show` runs.
- Checked bounded chunk workers for concurrency, per-speaker overrides, fragment coverage and failure propagation in the 59-test suite.
- Rendered four comparison chains on real speech, including the GPL and brighter variants. Each produced 576,000 finite stereo frames.
- Verified eight saved batch outputs with distinct suffixes. Resume skipped all eight after checking their hashes.
- Verified folder selection, playback, scheduling and reload with 24 real preview clips in the browser.
- Verified per-file speaker choices in two full renders. Identical speaker IDs retained different brightness settings across files.
- Checked the shared vexy-subs turns format against offline MLX diarization with two speaker IDs and 11 intervals.
- Verified commercial and GPL plugin renders, output hashes, video packet hashes and timestamps on real recordings.
- Completed the issue review after 80 tests passed, Ruff passed, and strict documentation and package builds succeeded.

## 1.0.0

- Published the first release as 1.0.0 (tag `v1.0.0`, commit `62bf2de`, wheel and sdist on PyPI).
- Added `build.sh` (test, build, twine check) and `publish.sh` (test,
  gitnextver tag, build, `uv publish` with retry on rate limits).
- Ported the `speech-polish` script collection into the installable
  `vexy_speakup` src-layout package with a `vexy-speakup` Fire CLI (commit `5980dc4`, 33 tests passed).
- Versions now come from git tags through hatch-vcs; the generated
  `__version__.py` is ignored by git. Added a `version` command (commit `5980dc4`).
- Plugin workers run as `python -m vexy_speakup`, so the installed package
  needs no adjacent script.
- Replaced machine-specific paths: plugins default to
  `/Library/Audio/Plug-Ins/VST3` (`VEXY_SPEAKUP_PLUGIN_ROOT`), and local model
  adapters come from `VEXY_SPEAKUP_TTS_ROOT`, resolved only when used (commit `5980dc4`, `tests/test_locations.py`).
- Folded the standalone plugin probe script into the `probe` command.

## 2026-10-18: documentation plugins

- Use MaterialX search, inherited metadata and a topic index; keep ordered navigation in awesome-nav.
- The documentation wrapper installs the plugins required by this site.
- Strict documentation build and rendered output checks passed.
