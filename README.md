<!-- this_file: README.md -->
# vexy-speakup

**Documentation:** https://vexy.dev/vexy-speakup/

Restore a meeting recording with your installed VST3 speech plugins, one speaker
at a time, and get back the same file with the original video timeline intact.

```bash
uv tool install vexy-speakup
# From a checkout before the first release:
uv tool install .
vexy-speakup run meeting.mp4 --profile_name=dx65 --verbose
```

It requires macOS, Python 3.12+ and FFmpeg/ffprobe on PATH. Rendering uses the
tested Pedalboard 0.9.26 wheel. The built-in profiles expect Accentize dxRevive
Pro, iZotope RX 12 Voice De-noise and Ozone 12 Maximizer. Plugins are read from
`/Library/Audio/Plug-Ins/VST3`. Set `VEXY_SPEAKUP_PLUGIN_ROOT` to use another
folder. Plugins and their licences are yours; none are distributed here.

## Commands

```bash
# Full audio or video, default work and output paths
vexy-speakup run meeting.m4a --profile_name=dx65

# Explicit paths and loudness
vexy-speakup run meeting.mp4 \
  --work_dir=work --output_path=result.mp4 \
  --target_lufs=-16 --true_peak=-2 --verbose

# Compare three processing attempts on one excerpt and retain model scores
vexy-speakup attempts meeting.m4a --work_dir=comparison --start=120 --duration=45

# Audio-only preview (video previews need a pretrimmed video)
vexy-speakup run meeting.m4a --start=120 --duration=45

# Export audio only from a video
vexy-speakup run meeting.mp4 --output_path=speech.wav

# Optional local DeepFilterNet3 CoreML before VST processing
vexy-speakup run meeting.m4a --ai=deepfilter

# Reuse or correct speaker annotations instead of rerunning a model
vexy-speakup run meeting.m4a --diarization_json=turns.json

# Alternate local diarizer; four speaker slots
vexy-speakup run meeting.m4a --diarizer=sortformer

# Inspect actual plugin controls before writing a custom chain
vexy-speakup inspect /Library/Audio/Plug-Ins/VST3/Accentize-dxRevivePro.vst3
vexy-speakup probe /Library/Audio/Plug-Ins/VST3/Accentize-dxRevivePro.vst3 probe.json
vexy-speakup inventory --output_path=inventory.json
vexy-speakup version
```

For `meeting.mp4`, the defaults are a work folder `meeting/` and an output file
`meeting_improved.mp4`, beside the input. Audio follows the same naming rule and
keeps its extension. Audio previews add `_preview`. An existing output is
refused unless `--force` is supplied. Every run gets a new directory inside the
work folder, so previous attempts and originals stay available.

## Local models

Diarization, DeepFilterNet and quality scoring call existing local adapters and
native hosts in isolated uv environments. Set `VEXY_SPEAKUP_TTS_ROOT` to the
folder holding `myasr/`, `myaud/` and `.external/`. Without it, you can still
process a recording with `--diarization_json=turns.json --evaluate=False`.

The default diarizer is the cached `mlx-community/Nemotron-3-Diarization-8bit`
conversion via `myasr/tools/diarize-mlx.py`. Sortformer uses the pinned Q8 GGUF
from the Hugging Face cache and the native `nemo-speech` host. No paid service is
used, and model access runs with `HF_HUB_OFFLINE=1`.

Evaluation invokes the cached `aud-metrics` environment and its DNSMOS/UTMOS
ONNX predictors. Override its Python with `--metrics_python=...` or disable
scoring with `--evaluate=False`. Missing predictors appear as errors in reports;
they never become synthetic scores. Normal runs score up to three matching
30-second speech windows.

## Profiles and custom chains

`dx35` is the conservative default: dxRevive at 35%, followed by Ozone Maximizer.
`dx65` raises restoration to 65%; it led DNSMOS on the tested Zoom excerpt.
`rx6-dx35` adds RX Voice De-noise at 6 dB before dxRevive.
`rx6` uses RX alone. `bypass` skips VSTs but keeps the level passes.

Use `--config_path=custom-chain.json` to replace the chains. The bundled
[example](examples/custom-chain.example.json) gives speaker `0` a lighter
dxRevive setting and mouth de-clicking. `speech` is the shared default chain,
`speakers` overrides individual speaker IDs, and `master` runs continuously after
assembly. Each plugin entry accepts `path`, `parameters`, optional `plugin_name`
for a multi-plugin bundle, and optional `preset` for a saved `.vstpreset` file.
Parameter names are validated against the installed plugin; unknown names fail.
Saved presets should come from your own host and installed plugin version.

## Processing and files

1. FFmpeg extracts stereo float PCM at 48 kHz. A delayed video audio start
   becomes leading silence. Diarization receives the original signal; optional
   AI restoration happens afterwards.
2. The diarizer processes the complete audio with its own bounded context, so
   speaker IDs are not restarted for each fragment.
3. The timeline is partitioned into disjoint speech, overlap and background
   intervals of at most 30 seconds (`--max_chunk`). Each speech fragment
   carries half a second of context at each edge.
4. One isolated plugin worker (`python -m vexy_speakup _render`) processes each
   speaker and resets the chain between fragments. Stereo is retained. Two
   seconds of padding drain plugin buffering; Pedalboard compensates reported
   plugin latency.
5. A duration-weighted median calibrates each speaker. Turn adjustments stay
   within 3 dB of that baseline, and total gain within ±12 dB. Silence is never
   amplified. Processing transitions blend with the source over 10 ms.
6. Timeline assembly writes every sample exactly once. Background gaps remain.
   Overlap is processed once as a mixed fragment under `speakers/_overlap`.
7. Two-pass R128 levelling precedes continuous mastering; a measured pass then
   sets final loudness and true peak. Export checks the encoded true peak and
   attenuates and re-encodes if lossy encoding overshoots.
8. For video, FFmpeg copies the original video packets and replaces the audio.

`speakers/<ID>/*.wav` are levelled timeline fragments; `*-context.wav` and
`*-render.wav` keep their processing context. `*-mastered.wav` are 24-bit cuts
from the final master, with final levels and the full-recording limiter
behaviour. `fragments.json` records original times, sample offsets, active
speakers and gains. Intermediate WAVs are float PCM and may exceed 0 dBFS;
`master.wav` and the published output are the peak-controlled deliverables.
A long recording can consume tens of GB of work files.

`turns.json`, diarization receipts, `speaker-gains.json`, VST parameter
receipts, `report.json`, `evaluation.json`, subprocess logs and `latest.json`
make each run reviewable. A failed run records its error and keeps its work
files. A successful output is published through a temporary file and rename.

## Limits

Predictor scores guide comparisons. They do not establish speaker accuracy,
transcript preservation or perceptual quality across a whole meeting. Diarized
fragments are not isolated voices during simultaneous speech; that would need
separate microphone tracks or a tested separation model. Speaker IDs are
anonymous until you label them.

Recordings, turn files and run folders are your private data. They are excluded
from the source and wheel allowlists, and nothing is uploaded.

## Development

```bash
./test.sh                 # pytest with coverage, then ruff
./build.sh                # docs into docs/, then uv build and twine check
./build.sh docs           # documentation only (src_docs/build.sh)
./build.sh package        # package only
./publish.sh              # gitnextver tag, build, uv publish to PyPI
```

Tag releases with `uvx gitnextver`. Untagged commits build as development
versions with a local segment, which PyPI rejects. The generated
`src/vexy_speakup/__version__.py` is ignored by git.

`./publish.sh` runs `uvx gitnextver`, which commits all changes, creates the
next `vX.Y.Z` tag and pushes. It stops if HEAD carries no such tag, then builds
the package and runs `uv publish`. It does not run the tests, so run
`./test.sh` first.

The documentation source is in `src_docs/md/`; `src_docs/build.sh` builds it
into `docs/`, which GitHub Pages serves.
