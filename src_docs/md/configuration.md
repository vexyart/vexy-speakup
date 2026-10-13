# Profiles and custom chains

Application settings are TOML, stored at the platformdirs user config path:

```bash
vexy-speakup config path
vexy-speakup config init
vexy-speakup config show
```

`VEXY_SPEAKUP_CONFIG` selects another file. `[paths]` sets `plugin_root`; the root
environment variable takes precedence. An old `tts_root` key still loads and is
ignored. `[processing]` sets
profile, worker count, max chunk, loudness, peak and brightness defaults;
explicit CLI options take precedence. `[candidates.NAME]` sets a profile alias
and unique output suffix, or explicit speech/master/speaker chains. Relative
plugin paths in TOML candidates resolve under `plugin_root`.

The four default listening candidates are `podcast`, `dx35`, `dx35-bright` and
`clear`. `podcast` uses installed GPL PodcastPlugins TRACK/MASTER; `clear` uses
Supertone Clear before Ozone mastering. `podcast-bright` sets TRACK TIMBRE to +2.
`dx35-bright` adds a 3 dB shelf above 3 kHz. `--brightness_db` / TOML
`brightness_db` adds a shelf to shared and overridden speaker chains, in the
range [-12,12] dB. Zero is neutral. Missing plugins fail explicitly.

`path = "builtin:high-shelf"` selects Pedalboard's open-source high-shelf effect
with `cutoff_frequency_hz`, `gain_db` and `q` parameters; it works in TOML and
JSON chains. This reserved path is not resolved as a VST bundle filename.

A chain is an ordered list of VST3 plugins. `vexy-speakup` uses two kinds:

- **Speech chains** process each speaker's fragments separately. The plugin state
  is reset between fragments.
- **The master chain** processes the whole assembled recording continuously,
  after the speakers have been levelled and put back on the timeline.

You choose chains with a built-in profile (`--profile_name`) or a JSON file
(`--config_path`). A file replaces the profile completely.

## Built-in profiles

| Profile | Speech chain | Master chain |
| --- | --- | --- |
| `dx35` (default) | dxRevive Pro, mix 35% | Ozone 12 Maximizer |
| `dx65` | dxRevive Pro, mix 65% | Ozone 12 Maximizer |
| `rx6-dx35` | RX 12 Voice De-noise at 6 dB, then dxRevive Pro at 35% | Ozone 12 Maximizer |
| `rx6` | RX 12 Voice De-noise at 6 dB | Ozone 12 Maximizer |
| `bypass` | none | none |

`dx35` is the conservative choice. `dx65` led DNSMOS on the Zoom excerpt it was
tested on. `bypass` skips every plugin but still performs the level passes, which
makes it a useful reference when you compare attempts.

The profiles set these plugin parameters:

| Plugin bundle | Parameters |
| --- | --- |
| `Accentize-dxRevivePro.vst3` | `mix` = 35.0 or 65.0, `bypass` = false |
| `RX 12 Voice De-noise.vst3` | `reduction` = 6.0, `adaptive_mode` = true, `global_bypass` = false |
| `Ozone 12 Maximizer.vst3` | `max_output_level` = -2.0, `max_input_gain_db` = 0.0, `max_upward_compression_amt_db` = 0.0, `max_soft_clip_on_off` = false, `global_bypass` = false |

The bundles are loaded from `/Library/Audio/Plug-Ins/VST3`, or from
`VEXY_SPEAKUP_PLUGIN_ROOT` if it is set. The parameter names were verified
against the locally installed plugin versions; a different plugin version may
name its controls differently.

## Custom chain files

A chain file is a JSON object with three keys:

| Key | Type | Meaning |
| --- | --- | --- |
| `speech` | array of plugin entries | default chain for every speaker |
| `speakers` | object, optional | chains for individual speaker IDs; each replaces `speech` for that speaker |
| `master` | array of plugin entries | continuous chain after assembly |

`speech` and `master` are required. Either may be an empty array.

Each plugin entry accepts:

| Field | Required | Meaning |
| --- | --- | --- |
| `path` | yes | path to the `.vst3` bundle; `~` is expanded |
| `parameters` | no | object of parameter names and values |
| `plugin_name` | no | which plugin to load from a bundle that contains several |
| `preset` | no | path to a `.vstpreset` file loaded before `parameters` are applied |

Every parameter name is checked against the loaded plugin. An unknown name stops
the run with an error that suggests `inspect`. Every plugin must be an effect.
Saved presets should come from your own host and the installed plugin version.

## Example

The repository includes `examples/custom-chain.example.json`:

```json
{
  "speech": [
    {
      "path": "/Library/Audio/Plug-Ins/VST3/Accentize-dxRevivePro.vst3",
      "parameters": {"mix": 65.0, "bypass": false}
    }
  ],
  "speakers": {
    "0": [
      {
        "path": "/Library/Audio/Plug-Ins/VST3/RX 12 Mouth De-click.vst3",
        "parameters": {"sensitivity": 3.0, "output_clicks_only": false, "global_bypass": false}
      },
      {
        "path": "/Library/Audio/Plug-Ins/VST3/Accentize-dxRevivePro.vst3",
        "parameters": {"mix": 35.0, "bypass": false}
      }
    ]
  },
  "master": [
    {
      "path": "/Library/Audio/Plug-Ins/VST3/Ozone 12 Maximizer.vst3",
      "parameters": {"max_output_level": -2.0, "max_input_gain_db": 0.0, "global_bypass": false}
    }
  ]
}
```

With this file, speaker `0` gets mouth de-clicking and a lighter dxRevive mix of
35%. Every other speaker gets dxRevive at 65%. The master chain is the Ozone
Maximizer.

Speaker IDs are the labels in the speaker turns: whatever the diarizer produced,
or the `speaker` values in your `--diarization_json` file. Overlap intervals use
the shared `speech` chain, because they belong to no single speaker.

## Write a chain for your plugins

1. List the installed bundles:

    ```bash
    vexy-speakup inventory --output_path=inventory.json
    ```

2. Print the controls of the plugin you want to use:

    ```bash
    vexy-speakup inspect "/Library/Audio/Plug-Ins/VST3/RX 12 Mouth De-click.vst3"
    ```

    The `parameters` object shows each control's current value, and `ranges`
    shows its range.

3. Copy `examples/custom-chain.example.json` to `custom-chain.json` and edit the
   paths and parameter names to match the `inspect` output.

4. Test the chain on an audio excerpt:

    ```bash
    vexy-speakup run meeting.m4a --config_path=custom-chain.json \
      --start=120 --duration=45
    ```

5. Open the run folder and check `speakers/<ID>/vst-receipt.json`. It records the
   parameter values each plugin actually used.
