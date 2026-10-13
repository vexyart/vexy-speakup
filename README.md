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
`/Library/Audio/Plug-Ins/VST3`. Set the folder in the TOML app settings or use
`VEXY_SPEAKUP_PLUGIN_ROOT`. Plugins and their licences are yours; none are
distributed here.

## App settings

```bash
vexy-speakup config path       # OS config folder, located with platformdirs
vexy-speakup config init       # creates config.toml; refuses to overwrite
vexy-speakup config show       # effective settings with defaults
vexy-speakup run meeting.mp4 --workers=8 --max_chunk=15
```

On macOS the file is `~/Library/Application Support/vexy-speakup/config.toml`.
`VEXY_SPEAKUP_CONFIG` selects another app settings file. `[paths]` configures
`plugin_root`; the environment variable takes precedence. An old `tts_root` key
is ignored. `[processing]` configures `profile`, `workers`, `max_chunk`,
`target_lufs` and `true_peak`. Explicit `run` options override these. Unknown
settings and invalid ranges fail before processing.
`brightness_db` adds a 3 kHz high shelf to shared/per-speaker speech chains
(range -12 to +12 dB); zero is neutral. Set it in TOML or pass
`--brightness_db=3`. The master remains continuous after assembly.

`[candidates.NAME]` defines a `profile` alias and a distinct `suffix`, or
explicit `speech`, `master` and optional `speakers` chains. Relative plugin
paths in TOML candidates resolve under `plugin_root`. Use the candidate's name
with `--profile_name=NAME`. See [example TOML](examples/config.example.toml).
The existing `--config_path` option still accepts a JSON chain for one run.

## Folder jobs

For browser listening, install `uv tool install '.[gui]'` from this checkout,
then run `vexy-speakup gui recordings`, or use `./run-gui.sh recordings` from
the checkout. It opens `http://127.0.0.1:8765` with
folder selection, level-matched previews, brightness and per-speaker choices,
saved jobs and stop/resume controls. Audio stays local. See the
[listening workflow](src_docs/md/listening.md).

```bash
# All configured candidate chains; global processing needs no diarization model
vexy-speakup batch recordings --workers=8 --file_workers=2

# Schedule now, run later (prints the saved job path)
vexy-speakup schedule recordings --candidates=podcast,dx35-bright
vexy-speakup job /path/to/job.json --workers=8

# Optional individual speaker preparation; needs the models extra
vexy-speakup batch recordings --diarizer=mlx
```

Jobs default to the platformdirs data folder under `jobs/`; select a file with
`--job_path`. Outputs default to `recordings/speakup-output/`, retaining input
extensions with each candidate's suffix. `--recursive=True` retains subfolders.
The total worker budget is split across `file_workers`; decoding and diarization
are shared across variants of one recording. MOS evaluation defaults off for
batch speed. `--diarizer=none` means one uniform chain over the whole recording;
individual speaker mode requires actual diarization or supplied annotations.

Each job snapshots source hashes, chains and optional per-file speaker choices.
Resume verifies completed outputs, reports and settings before skipping work,
and recovers a completed render after an interrupted state update. Changed
inputs/outputs fail explicitly. Use `job --force=True` to replace outputs when
retrying. Failures persist per task and make the CLI exit with status 1.
`--diarization_dir` accepts matching relative `.json` annotation files, whose
contents are saved in the job. Speaker IDs are scoped to each input file.

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

# Optional local DeepFilterNet3 (MLX) before VST processing
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

Diarization, DeepFilterNet and scoring need the `models` extra (Apple Silicon):
`uv pip install 'vexy-speakup[models]'`. Pinned weights download on first use into
the Hugging Face cache, then work offline: `mlx-community/Nemotron-3-Diarization-8bit`
(default), `mlx-community/diar_streaming_sortformer_4spk-v2.1-fp16` (`sortformer`),
`iky1e/DeepFilterNet3-MLX` (`--ai=deepfilter`). Without the extra, use
`--diarizer=none` or `--diarization_json=turns.json --evaluate=False`. Evaluation
scores three 30-second windows with DNSMOS and UTMOS; failures are report errors,
never synthetic scores.

## Free plugins

PodcastPlugins, master_me, Noise Repellent and Vocal Gate (GPL-3.0, macOS and
Windows x64) ship from [vexy-speakup-assets](https://github.com/vexyart/vexy-speakup-assets),
pinned by commit and SHA-256. A chain plugin missing from `plugin_root` is fetched
on first use; `vexy-speakup assets fetch` downloads all, `assets list` shows them.

## Profiles and custom chains

`dx35` is the conservative default: dxRevive at 35%, followed by Ozone Maximizer.
`dx65` raises restoration to 65%; it led DNSMOS on the tested Zoom excerpt.
`rx6-dx35` adds RX Voice De-noise at 6 dB before dxRevive.
`rx6` uses RX alone. `bypass` skips VSTs but keeps the level passes.
`podcast` uses the GPL PodcastPlugins TRACK and MASTER (`pp-track.vst3` and
`pp-master.vst3`); `podcast-bright` raises TRACK's TIMBRE to +2. `clear` uses
Supertone Clear for voice/ambience/reverb balance before Ozone mastering.
`dx35-bright` adds a 3 dB high shelf to dx35. The four default candidates are
`podcast`, `dx35`, `dx35-bright` and `clear`. Missing plugins produce errors.
All controls were checked against installed versions; choices still need
listening comparisons for your speakers.

Use `--config_path=custom-chain.json` to replace the chains. The bundled
[example](examples/custom-chain.example.json) gives speaker `0` a lighter
dxRevive setting and mouth de-clicking. `speech` is the shared default chain,
`speakers` overrides individual speaker IDs, and `master` runs continuously after
assembly. Each plugin entry accepts `path`, `parameters`, optional `plugin_name`
for a multi-plugin bundle, and optional `preset` for a saved `.vstpreset` file.
Parameter names are validated against the installed plugin; unknown names fail.
Saved presets should come from your own host and installed plugin version.
Use `path = "builtin:high-shelf"` for Pedalboard's open-source shelf, with
`cutoff_frequency_hz`, `gain_db` and `q` parameters, in TOML or JSON speech chains.

## Processing and files

The pipeline preserves the original timeline, processes overlaps as mixed
fragments, levels individual voices and masters the assembled recording
continuously. Video packets are copied. Receipts, source hashes and intermediate
files remain in each run folder; original recordings are never overwritten.
See [processing details and limits](src_docs/md/processing-details.md) for
chunk context, gains, file outputs, disk use and model-score limitations.

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
