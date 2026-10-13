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

## Local models

Automatic diarization, the optional DeepFilterNet pass and quality scoring need
the optional `models` extra (macOS Apple Silicon):

```bash
uv pip install 'vexy-speakup[models]'
```

It adds `mlx-audio`, `huggingface-hub`, `onnxruntime`, `sentencepiece` and
`speechonnxmetrics`. Weights download on first use into the Hugging Face cache.
[Local models](local-models.md) lists them. You can process recordings without
the extra by supplying speaker turns and turning scoring off:

```bash
vexy-speakup run meeting.m4a --diarization_json=turns.json --evaluate=False
```

## Free plugins

Four GPL-3.0 plugins are available without installing them yourself:
PodcastPlugins (TRACK, MASTER), master_me, Noise Repellent and Vocal Gate. They
are stored with Git LFS in
[vexy-speakup-assets](https://github.com/vexyart/vexy-speakup-assets), with
builds for macOS and Windows x64. The package pins the
repository commit and each file's SHA-256.

When a chain names a plugin that is not in your VST3 folder, the bundled copy is
downloaded on first use. To download everything up front, or to see what is
installed:

```bash
vexy-speakup assets fetch
vexy-speakup assets list
```

Bundles go to the user data folder (`~/Library/Application Support/vexy-speakup/plugins/`
on macOS). Set `VEXY_SPEAKUP_ASSETS_DIR` to use another folder.

On Windows, Vocal Gate exists only as its vendor installer. `assets fetch` (or
the first chain that uses it) runs that installer silently. Windows asks for
administrator rights; the plugin goes to
`C:\Program Files\Common Files\VST3\Vocal Gate.vst3` together with the Visual C++
runtime it needs. Remove it from Settings > Apps. If you decline the prompt, the
plugin is reported as not installed and the installer log is kept beside the
other assets. `assets list` shows each plugin's install method.
