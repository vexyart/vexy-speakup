<!-- this_file: WORK.md -->
# Work record

Ported the `speech-polish` scripts (media, models, pipeline, vst, audit, turns,
levels, CLI and plugin probe) into `src/vexy_speakup`. Behaviour is unchanged
except for packaging needs: relative imports, `python -m vexy_speakup` plugin
workers instead of a sibling script path, lazy configurable plugin/model roots,
and the probe script folded into `vexy-speakup probe`. Recorded evidence,
measurements and private recording paths stayed in the original folder.

Tests: 33 passed (26 ported functional tests with real FFmpeg encoding, video
remux, latency compensation and full CLI runs, plus location/version/inventory
tests). Coverage 73% with subprocess measurement; the remainder needs licensed
plugins or the local model adapters. Ruff passed.

## Issue 101 — 2026-10-13

The full issue is active; the seven-story ledger lives in
`.omc/ultragoal/goals.json`. Migration is complete; research, usable open-source
chains/brightness, batch jobs, GUI, speaker choices and full acceptance remain.

- Baseline: `./test.sh`, 33 passed, ruff clean, 73% coverage.
- After source retirement: `./test.sh`, 59 passed, ruff clean, 76% coverage.
  `./build.sh package` built wheel/sdist; both passed twine. Direct CLI
  config path/init/show smoke checks passed using an isolated config folder.
  Wheel inspection confirmed settings code and both dependencies are included
  and private media/history are excluded.
- Added `settings.py`: platformdirs config path, TOML read/write, defaults,
  settings validation, candidate aliases/custom chains, plugin-root-relative
  paths. `config path/init/show` exposes settings. CLI options override the
  configured processing defaults; root environment variables override TOML.
- Native rendering now shards each speaker's chunks across bounded worker
  processes; every shard retains that speaker's chosen chain, log and receipt.
  Tests cover concurrent execution limits, exact fragment coverage and failure
  propagation. The existing FFmpeg CLI/timeline tests exercise real workers.
- Migration audit checked every legacy function, original test function and
  custom example. Differences reviewed: package imports/worker entry points,
  configurable installation roots, probe command integration, new app settings
  and concurrent rendering. All nine duplicate scripts were retired after the
  56-test suite passed. Original source was archived and byte-verified;
  historical docs and 889 MB of recording evidence remain under
  `_private/speech-polish-history/`. Receipts with source/target hashes are in
  `.omc/ultragoal/migration-receipt.json` and that historical folder.
- Pluginary's native scanner discovered 1,073 entries (931 scan attempts):
  terminal summary was 467 successful, 463 failed, one timeout. This is not a
  usable full inventory yet: paths containing spaces were passed with literal
  quotes, some worker JSON output was truncated, and AppleAES3Audio remained
  alive for over two minutes despite a 30s timeout. Terminating that worker
  allowed the host to finish. No scan process remains live. The scanner clears
  its journal on completion, so the empty journal is not evidence of coverage.
  Exported database contains 854 records including prior cached entries at
  `.omc/ultragoal/plugin-catalog-20261013.json`.

## Issue 101 — plugin research follow-up

- Fixed Pluginary worker argv fidelity and blocking/truncated pipe results.
  Rebuilt the native host and console worker against pinned JUCE 8.0.12 outside
  the source tree. CTest: 23 passed, including silent-worker timeout/cancellation
  and 1 MB result handling. Original external source/builds were preserved.
- Full rescan terminated normally: 1,020 successful attempts, 31 failures,
  22 timeouts across 1,073 entries. Export contains 933 named plugin records.
  Log and exports are in `.omc/ultragoal/`; failures remain explicit.
- Added native metadata namespaces, exact-ID `annotate`, rescan preservation,
  metadata export/presets and atomic Python research import/list. Python preset
  descriptions and shared schema retain plugin metadata. Filter baseline:
  22 passed/3 skipped; current: 34 passed/3 skipped, ruff/mypy clean.
- Researched the nine supplied repositories, local tts adapters and 16 installed
  plugin candidates against primary sources. All nine README files match their
  recorded source commits. The 26-record collection is in Pluginary's
  `shared/research/speech-20261013.json`. Imported and verified all 26 live DB
  records and annotations on 16 scanned plugins; parameter arrays are intact.
  Native annotation/info and native-to-Python preset roundtrip checks passed.
- PodcastPlugins TRACK and MASTER are installed as `pp-track.vst3` and
  `pp-master.vst3`; both produced finite stereo output on a real 12-second
  excerpt. Their actual TIMBRE range is [-5,5], neutral 0. These are the first
  open-source chain components to integrate. Probes are in `.omc/ultragoal/`.

Research report: `issues/101-research.md`. Next: complete open-source and brighter
candidate chains, test full chain/latency behavior, then implement saved batch
jobs, listening GUI and per-file speaker choices from PLAN.md. Native scanner
GUI-worker compilation and an actual argv/file-result smoke check also passed;
it is not the requested listening GUI. No publishing or tagging is requested.

## Issue 101 — chains and durable batch jobs

- Integrated four default candidates: GPL PodcastPlugins TRACK/MASTER,
  conservative dxRevive, dxRevive plus a 3 dB shelf, and Supertone Clear before
  Ozone mastering. The open-source `podcast-bright` profile uses verified TIMBRE
  +2. Built-in `builtin:high-shelf` supports TOML/JSON recipes. Global brightness
  applies to shared and overridden speaker chains and is snapshotted in jobs.
- Actual PodcastPlugins delay changed after preparation (TRACK 5,279 samples
  and MASTER 479 samples at 48 kHz); receipts now capture operational delay.
  A real noise-burst probe showed compensated onset at the expected frame.
- Four full CLI renders on real 12-second speech all completed with 576,000
  finite stereo frames at 48 kHz and measured final publication checks. Evidence:
  `.omc/ultragoal/four-chains/acceptance.json`, reports and worker receipts.
- Added versioned Pydantic job models and `schedule`, `job`, `batch` commands.
  Source hashes, resolved recipes, distinct suffixes, settings and per-file
  speaker choices are saved. Whole-recording mode avoids a diarization model;
  speaker detection and supplied annotations remain available explicitly.
- Decode/diarize once per input; split the native worker budget across concurrent
  variant tasks. Kernel locks prevent duplicate runners; atomic JSON writes and
  report/output hashes support verified resume and interrupted-state recovery.
  Failure details persist per task and the CLI exits with status 1 on failure.
- Tests exercise real batch encoding, changed sources/outputs, recovery, lock
  exclusion and global processing without models. A two-file spectral test gives
  the same anonymous speaker ID different brightness settings and confirms
  more than 5 dB difference in upper/lower-band ratios in the actual outputs.
- Real saved CLI job: audio plus video, four variants each, all eight completed
  and output hashes verified. Every video packet hash and timestamp in all four
  video outputs matches the original. Resume skipped all eight verified outputs.
  Evidence: `.omc/ultragoal/batch-real/acceptance.json` and `job.json`.
- Fresh `./test.sh`: 74 passed, ruff clean, 82% coverage. Wheel/sdist build and
  twine checks passed. README kept below 200 lines; detailed processing facts
  retained in documentation. Batch/config/processing docs updated.

Next: implement the actual listening GUI, representative previews and saved
preferences, then per-file speaker preview rows with diarization. The queue
already supports separate speaker recipes for each explicit source file; reuse
that schema rather than assuming IDs identify the same person across recordings.
Then run GUI/runtime/model acceptance, update docs and perform the full issue
completion audit. The full goal remains active.

## Issue 101 — local browser listening and speaker choices

- User preferred a web UI; replaced the provisional Qt modules with a local
  FastAPI/Uvicorn interface and removed PySide6 from dependencies and lockfile.
  `vexy-speakup gui` opens the browser; the same command accepts a custom port.
- Added representative energy-window and exclusive-speaker previews, three
  brightness variants per configured chain, level-matched original playback,
  folder browsing, per-file groups, explicit selections and job scheduling.
  Preview rendering reuses the existing full pipeline; failures remain visible.
- Added settings editing that retains custom candidates, preserves the original
  TOML backup and respects environment roots without replacing saved paths.
- Shared cancellable operation scopes propagate to native subprocess groups,
  which are stopped and reaped on cancellation/deadline. Saved jobs distinguish
  cancellation from failure and keep verified completed outputs for resume.
- Offline MLX diarization on actual speech produced two IDs and 11 intervals,
  including overlap. Two real recordings produced four browser speaker groups;
  different brightness choices for identical IDs stayed scoped to each source.
  Both full speaker outputs completed with verified hashes. The supplied
  `{"model": ..., "turns": [...]}` annotations match vexy-subs' existing contract,
  so no incompatible sibling format or unnecessary source change was introduced.
- Browser acceptance: 24 real four-family clips, playback advanced, cross-file
  selection persisted, saved job produced two full audio/video outputs, hashes
  matched receipts and every video packet hash/time was retained. Desktop/mobile
  screenshots and receipts live in `.omc/ultragoal/web-acceptance.json` and
  `web-speakers/acceptance.json`; no browser page errors or horizontal overflow.
- Direct cleanup plan: delete unused Qt code; separate preview-window selection
  and request boundary models; combine duplicate HTTP error handling; preserve
  cancelled-task recovery; verify package assets and settings backup behavior.
  Cleanup retained the backend schema and processing behavior.
- Initial full web suite: 80 passed, ruff clean, 83% coverage. A final rerun,
  fresh browser check, rebuilt package/docs and issue audit follow the cleanup.

Final acceptance after cleanup: `./test.sh` passed all 80 tests with 83% coverage
and ruff clean. Strict docs and wheel/sdist builds passed; both archives passed
twine. Direct wheel inspection found all four static assets and optional web
dependencies, with no Qt/private payload. A clean installed wheel served its
CLI/browser/assets/API from outside the checkout and exited 0 on shutdown.
Fresh browser checks passed folder selection, duration metadata, playback with
exclusive pause, saved-job resume and mobile layout without page errors.
All browser-created full outputs were independently hash-verified; video packet
data hashes and timestamps remained identical. `git diff --check` passed.
Direct post-cleanup review found no blocking findings; verdict and requirement
audit are in `.omc/ultragoal/final-review.md`. Issue 101 is complete. Publication
and tagging remain separate, unauthorized release follow-up work.

## Browser launcher

Added executable `run-gui.sh`, which locates the checkout, installs/enables the
optional web dependencies through `uv run --extra gui`, and forwards arguments
to `vexy-speakup gui`. README and changelog updated. `bash -n` passed; launching
from `/tmp` with a custom port and browser opening disabled served the actual
web UI, and SIGINT completed server shutdown cleanly.

## Bundled models and free-plugin assets — 2026-10-13

- Model adapters now ship as `vexy_speakup.model_worker` (child process) and use
  the standard HF cache; `tts_root` is gone. Parity on a 60 s excerpt: MLX
  Nemotron turns identical (23/23) to the old myasr adapter; DNSMOS/UTMOS
  identical to the old aud-metrics adapter; DeepFilterNet3 (MLX, same weights as
  the CoreML package) keeps the sample count. All ran with `HF_HUB_OFFLINE=1`.
- Free GPL plugins live in `vexyart/vexy-speakup-assets` (Git LFS, commit
  942277f) with complete corresponding source. `assets fetch|list`; on-demand
  fallback in `vst.load_chain`. Verified: 4-worker `run --profile_name=podcast`
  and GUI `prepare_preview(speaker_mode=True)` with an empty VST3 folder.
- Gaps: Vocal Gate has no Windows build (Inno Setup 6.7 > innoextract 1.9);
  Windows bundles are hash-verified but not load-tested; dereverb-vst3 has no
  licence and is excluded.
- Tests: 89 passed, coverage 82%, ruff clean. Docs site rebuilt.
- Not started: multi-chain listening workflow (per recording / per speaker,
  no forced shared mastering), crossfade between adjacent processed speakers,
  Pluginary-based plugin detection, auto-built chains.


## Release 1.0.2

User authorised commit, push and publication. Fresh release checks: 100 tests
passed, 84% coverage, Ruff clean; strict documentation build passed. Preflight
wheel/sdist contain the model worker, asset manifest and web application, with
private recordings, model weights and local paths excluded. The pinned asset
manifest matches the companion repository; ten binaries match hashes and sizes,
four corresponding source archives are present, and LFS integrity passed.
