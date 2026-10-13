# Command reference

`vexy-speakup` is a [Fire](https://github.com/google/python-fire) command-line
tool. Flags use underscores, as in `--profile_name`, and Boolean flags take an
explicit value, as in `--evaluate=False`. Add `--help` after a command to print
its flags:

```bash
vexy-speakup run --help
```

| Command | Purpose |
| --- | --- |
| `run` | process an audio or video file |
| `attempts` | process one excerpt with several profiles for comparison |
| `inspect` | list a plugin's controls and their ranges |
| `probe` | load one plugin, record its controls and render a test signal |
| `inventory` | list the VST3 bundles in the plugin folder |
| `version` | print the installed package version |

## `run`

```bash
vexy-speakup run INPUT_PATH [flags]
```

Processes an audio or video file and prints the output path.

| Flag | Default | Meaning |
| --- | --- | --- |
| `--work_dir` | input path without its extension | folder that receives a new run folder |
| `--output_path` | input name plus `--suffix` | output file; its extension selects the format |
| `--suffix` | `_improved` | added to the input name when `--output_path` is empty |
| `--profile_name` | `dx35` | built-in plugin profile: `dx35`, `dx65`, `rx6-dx35`, `rx6` or `bypass` |
| `--config_path` | empty | JSON file with custom chains; replaces the profile |
| `--diarizer` | `mlx` | `mlx` or `sortformer` |
| `--diarization_json` | empty | speaker turns to use instead of a diarizer |
| `--target_lufs` | `-16` | integrated loudness target, from -70 to -5 LUFS |
| `--true_peak` | `-2` | true-peak ceiling, from -9 to 0 dBTP |
| `--max_chunk` | `30` | longest processed interval, in seconds |
| `--start` | `0` | excerpt start, in seconds (audio input only) |
| `--duration` | `0` | excerpt length, in seconds; `0` means to the end (audio input only) |
| `--evaluate` | `True` | score matching before/after windows |
| `--metrics_python` | empty | Python interpreter of the scoring environment |
| `--ai` | `none` | `none`, or `deepfilter` to run DeepFilterNet3 before the VSTs |
| `--timeout` | `1800` | time limit, in seconds, for each external process |
| `--force` | `False` | replace an existing output file |
| `--verbose` | `False` | print each stage |

The command checks its arguments before it starts work:

- All numbers must be finite; `--start` and `--duration` must not be negative;
  `--max_chunk` and `--timeout` must be positive.
- The input file, the output file and the work folder must all be different.
- An existing output is refused unless `--force` is given.
- A video input cannot be combined with `--start` or `--duration`.
- A `--config_path` file must contain `speech` and `master` arrays.

### Output names

With no `--output_path`, the output goes beside the input:

| Input | Output | Work folder |
| --- | --- | --- |
| `talk.mp4` | `talk_improved.mp4` | `talk/` |
| `talk.m4a` | `talk_improved.m4a` | `talk/` |
| `talk.m4a` with `--start` or `--duration` | `talk_improved_preview.m4a` | `talk/` |

### Output formats

The output extension selects the audio codec:

| Extension | Codec |
| --- | --- |
| `.wav` | 24-bit PCM, little-endian |
| `.aif`, `.aiff` | 24-bit PCM, big-endian |
| `.flac` | FLAC |
| `.mp3` | MP3 (LAME), 192 kb/s |
| `.ogg`, `.opus`, `.webm` | Opus, 192 kb/s |
| anything else | AAC, 192 kb/s |

### Export audio from a video

If the input has a video stream and the output extension is an audio-only
format (`.wav`, `.mp3`, `.m4a`, `.aac`, `.flac`, `.ogg`, `.opus`, `.aif`,
`.aiff`, `.caf`, `.wma` or `.ac3`), the result is audio only:

```bash
vexy-speakup run meeting.mp4 --output_path=speech.wav
```

An embedded cover image does not count as a video stream.

### Examples

```bash
# Explicit paths and loudness
vexy-speakup run meeting.mp4 \
  --work_dir=work --output_path=result.mp4 \
  --target_lufs=-16 --true_peak=-2 --verbose

# Local DeepFilterNet3 CoreML pass before the VST chain
vexy-speakup run meeting.m4a --ai=deepfilter

# Reuse earlier or corrected speaker turns instead of running a diarizer
vexy-speakup run meeting.m4a --diarization_json=turns.json

# Sortformer diarizer (up to four speakers)
vexy-speakup run meeting.m4a --diarizer=sortformer

# Custom chains
vexy-speakup run meeting.m4a --config_path=custom-chain.json
```

## `attempts`

```bash
vexy-speakup attempts INPUT_PATH [flags]
```

Processes one excerpt with several profiles and keeps every result for
listening. It prints the path of `comparison.json`.

| Flag | Default | Meaning |
| --- | --- | --- |
| `--work_dir` | `<input name>_attempts` beside the input | folder for all attempts |
| `--start` | `120` | excerpt start, in seconds |
| `--duration` | `45` | excerpt length, in seconds |
| `--profiles` | `dx35,dx65,rx6-dx35` | comma-separated profile names |
| `--metrics_python` | empty | Python interpreter of the scoring environment |
| `--verbose` | `True` | print each stage |

The command extracts the excerpt to `sample.wav`, diarizes it once with the
`mlx` diarizer, and writes `turns.json`. It then runs `run` once per profile with
those turns, writing `<profile>.wav` and a `<profile>/` work folder. Finally it
collects every run's report into `comparison.json`.

`attempts` always uses the `mlx` diarizer, so it needs
`VEXY_SPEAKUP_TTS_ROOT`.

## `inspect`

```bash
vexy-speakup inspect PLUGIN_PATH [--output_path=FILE]
```

Loads a plugin the same way a chain does and prints JSON with its name, reported
latency, current parameter values and the range of each parameter. Use it to
find the exact parameter names before you write a custom chain. With
`--output_path`, the JSON is also saved to that file. A licence or loading
problem appears as an error.

```bash
vexy-speakup inspect /Library/Audio/Plug-Ins/VST3/Accentize-dxRevivePro.vst3
```

## `probe`

```bash
vexy-speakup probe PLUGIN_PATH OUTPUT_PATH [--audio_path=FILE]
```

Loads one plugin directly and writes `OUTPUT_PATH` as JSON with:

- each control's value, raw value, range and valid values,
- the number of input and output frames of a test render,
- whether every output sample is finite, and the output peak.

Without `--audio_path`, the test signal is one second of stereo silence at
48 kHz. With it, the file is read instead. Two seconds of silence are added to
the end in both cases. The command prints the plugin name, the number of
parameters and the output shape.

```bash
vexy-speakup probe /Library/Audio/Plug-Ins/VST3/Accentize-dxRevivePro.vst3 probe.json
```

## `inventory`

```bash
vexy-speakup inventory [--output_path=inventory.json]
```

Finds every `.vst3` bundle under the plugin folder without loading any plugin.
It writes the folder, the count and the sorted bundle paths to
`--output_path` (default `inventory.json`) and prints the count. The plugin
folder is `/Library/Audio/Plug-Ins/VST3` unless `VEXY_SPEAKUP_PLUGIN_ROOT` is
set.

## `version`

```bash
vexy-speakup version
```

Prints the installed package version.

## Environment variables

| Variable | Effect |
| --- | --- |
| `VEXY_SPEAKUP_PLUGIN_ROOT` | plugin folder for built-in profiles and `inventory` |
| `VEXY_SPEAKUP_TTS_ROOT` | folder with the local model adapters |

`run` also sets `HF_HUB_OFFLINE=1` for itself and its child processes, so model
access never reaches the network.
