# Installation

## Prerequisites

- macOS. The package metadata lists macOS as its operating system, and the
  default plugin folder is the macOS system VST3 folder.
- Python 3.12 or later.
- [uv](https://docs.astral.sh/uv/) to install the command-line tool.
- FFmpeg with `ffprobe`, both on `PATH`. FFmpeg decodes, measures loudness,
  encodes and remuxes video.
- The VST3 plugins your chain uses, installed and licensed on this machine.

## Install the tool

1. Install the package as a uv tool:

    ```bash
    uv tool install vexy-speakup
    ```

    To install from a source checkout instead, run this in the repository folder:

    ```bash
    uv tool install .
    ```

2. Check that the command is available:

    ```bash
    vexy-speakup version
    ```

    The command prints the installed package version.

3. Check that FFmpeg is available:

    ```bash
    ffmpeg -version
    ffprobe -version
    ```

## Python dependencies

The package installs these libraries:

| Library | Used for |
| --- | --- |
| `fire` | the command-line interface |
| `numpy` | sample buffers, gains and fades |
| `pedalboard==0.9.26` | hosting VST3 plugins, with latency compensation |
| `soundfile` | streaming float and RF64 WAV files |
| `pyloudnorm` | BS.1770 loudness of speakers and fragments |

Pedalboard is pinned to 0.9.26 because plugin rendering was verified with that
exact wheel.

## Plugin folder

The built-in profiles load plugins from `/Library/Audio/Plug-Ins/VST3`. To use
another folder, set `VEXY_SPEAKUP_PLUGIN_ROOT`:

```bash
export VEXY_SPEAKUP_PLUGIN_ROOT="$HOME/Library/Audio/Plug-Ins/VST3"
vexy-speakup inventory --output_path=inventory.json
```

`inventory` lists every `.vst3` bundle under that folder without loading any
plugin, so it is a quick way to check the folder setting.

The variable affects the built-in profiles and `inventory`. A custom chain file
uses the full `path` written in each plugin entry.

## Local model adapters

Automatic diarization, the optional DeepFilterNet pass and quality scoring call
local adapters that live outside this package. Point `VEXY_SPEAKUP_TTS_ROOT` at
the folder that holds them:

```bash
export VEXY_SPEAKUP_TTS_ROOT=/path/to/tts
```

[Local models](local-models.md) lists what the folder must contain. You can
process recordings without it by supplying speaker turns and turning scoring off:

```bash
vexy-speakup run meeting.m4a --diarization_json=turns.json --evaluate=False
```
