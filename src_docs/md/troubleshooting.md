# Troubleshooting

When a run fails, start with `report.json` in the newest run folder. Its
`status` is `failed` and `error` holds the message. The log files next to it
contain the output of each external process; see
[Run folders and reports](outputs.md#receipts-and-logs).

## `Output exists: ...; use --force`

The output file is already there. Add `--force` to replace it, or choose another
name with `--output_path` or `--suffix`.

## `Input, output file and work directory must be distinct`

Two of the input, the output and the work folder resolve to the same path.
Choose a different `--work_dir` or `--output_path`.

## `Video preview needs a pretrimmed video`

`--start` and `--duration` work only for audio input. Either trim the video
first, or process its audio:

```bash
vexy-speakup run meeting.mp4 --output_path=speech.wav --start=120 --duration=45
```

## `Set VEXY_SPEAKUP_TTS_ROOT ...`

A diarizer, DeepFilterNet or scoring needs the local adapters and the variable is
not set, or does not point to a folder. Set it as described in
[Local models](local-models.md), or run without the adapters:

```bash
vexy-speakup run meeting.m4a --diarization_json=turns.json --evaluate=False
```

## `diarizer must be mlx or sortformer, or supply --diarization_json`

`--diarizer` has an unsupported value. Use `mlx`, `sortformer`, or supply turns.

## Errors about turns

| Message | Fix |
| --- | --- |
| `Diarization requires a turns/segments array` | the JSON must be a list, or an object with `turns` or `segments` |
| `Turn timestamps must be finite numbers` | `start` and `end` must be numbers, not strings or booleans |
| `Turn outside audio duration` | each turn needs `0 <= start < end`, ending within the audio |
| `Speaker must be a safe nonempty identifier` | use only letters, digits, `_` and `-` in speaker IDs |

## `Unknown parameter ... use inspect`

A chain sets a parameter that the loaded plugin does not have. Names depend on
the plugin and its version. Print the real names:

```bash
vexy-speakup inspect "/Library/Audio/Plug-Ins/VST3/Ozone 12 Maximizer.vst3"
```

Then correct the chain file.

## `Unknown profile ...`

`--profile_name` must be `dx35`, `dx65`, `rx6-dx35`, `rx6` or `bypass`.

## `VST unexpectedly silenced input; check license and settings`

A plugin returned silence for a non-silent fragment. This usually means the
plugin is not licensed or activated on this machine, or a setting such as a mix
of 0 mutes it. Open the plugin once in a host to check its licence, and check the
values in `speakers/<ID>/vst-receipt.json`.

## `Not an effect`

The chain loads an instrument or another non-effect plugin. Use an effect
plugin, or name the right one in a multi-plugin bundle with `plugin_name`.

## A plugin fails to load or times out

Each plugin gets 15 seconds to initialise. Each worker process is limited by
`--timeout` (default 1800 seconds). The worker's log, `speakers/<ID>/jobs.log` or
`master.log`, holds the plugin's output. Raise `--timeout` for very long
recordings.

## `Encoded true-peak limit could not be satisfied`

After three encodes with decreasing gain, the encoded file still exceeded
`--true_peak`. Use a lossless output such as `.wav` or `.flac`, or set a lower
`--true_peak`.

## `AI enhancement changed duration`, `Assembly changed timeline length`, `Mastering changed timeline length`

A processing step returned a different number of samples from its input. The run
stops rather than publishing audio that is out of sync. Check the corresponding
log in the run folder.

## The run folder uses too much disk space

Every run keeps all its intermediate float WAV files. A long recording can need
tens of gigabytes. Delete run folders you no longer need; `latest.json` names the
most recent successful run.
