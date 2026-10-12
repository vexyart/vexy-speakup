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
