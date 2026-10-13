# Run folders and reports

Each `run` creates a new run folder inside the work folder. Earlier runs and the
original file are never overwritten, so you can compare attempts or inspect a
failure later.

```text
meeting/                              work folder (default: input name without extension)
├── latest.json                       points to the last successful run
└── run-20260101-101500-123456/       one folder per run
    ├── report.json
    ├── input.wav
    ├── turns.json
    ├── fragments.json
    ├── speaker-gains.json
    ├── assembled.wav
    ├── premaster.wav
    ├── master-vst.wav
    ├── master.wav
    ├── evaluation.json
    ├── speakers/
    │   ├── 0/
    │   │   ├── jobs.json
    │   │   ├── jobs.log
    │   │   ├── vst-receipt.json
    │   │   ├── 000001-context.wav
    │   │   ├── 000001-render.wav
    │   │   ├── 000001.wav
    │   │   └── 000001-mastered.wav
    │   ├── _overlap/
    │   └── _background/
    └── evaluation/
```

The run folder name is the local start time with microseconds:
`run-YYYYMMDD-HHMMSS-ffffff`.

A long recording can need tens of gigabytes of work files. Delete run folders you
no longer need.

## Reports

| File | Contents |
| --- | --- |
| `report.json` | inputs, settings, status, levels, evaluation and publication details |
| `turns.json` | the validated speaker turns used for the run |
| `fragments.json` | every interval with original times, sample offsets, speakers, owner and gain |
| `speaker-gains.json` | the baseline gain of each speaker, in dB |
| `evaluation.json` | before/after scores for each evaluation window |
| `../latest.json` | path of the last successful run folder and its `report.json` |

`report.json` is written when the run starts with `"status": "running"`. It is
updated to `"complete"` with the results, or to `"failed"` with an `error`
message. A failed run keeps all its work files.

Fields of `report.json`:

| Field | Meaning |
| --- | --- |
| `input`, `input_sha256` | input path and its SHA-256 |
| `output` | output path |
| `video`, `output_video` | whether the input has video, and whether the output keeps it |
| `profile`, `config` | profile name and the full chain configuration used |
| `ai` | `none` or `deepfilter` |
| `preview_start` | the `--start` value |
| `target_lufs`, `true_peak` | level targets |
| `status`, `error` | run state, and the error message of a failed run |
| `duration_s` | decoded duration in seconds |
| `fragments` | number of intervals |
| `speakers` | sorted speaker IDs |
| `overlap_s` | total seconds with more than one speaker |
| `levels` | `loudnorm` measurements before and after the premaster and final passes |
| `evaluation` | the evaluation rows, when `--evaluate=True` |
| `publication` | codec, encoded loudness, extra codec gain and output SHA-256 |

## Receipts and logs

| File | Contents |
| --- | --- |
| `speakers/<ID>/vst-receipt.json` | each plugin's path, name, reported latency and every parameter value used |
| `master-receipt.json` | the same for the master chain, plus the rendered frame count |
| `speakers/<ID>/jobs.json`, `master-job.json` | the job description passed to each worker |
| `speakers/<ID>/jobs.log`, `master.log` | worker output |
| `diarization.log` | diarizer output |
| `diarization-native/` or `diarization-native.json` | raw diarizer result (`mlx` or `sortformer`) |
| `deepfilter.log`, `deepfilter-receipt.json` | DeepFilterNet output and model checks, with `--ai=deepfilter` |

## Audio files

| File | Format | Contents |
| --- | --- | --- |
| `input.wav` | float | decoded input |
| `deepfilter.wav` | float | DeepFilterNet output, with `--ai=deepfilter` |
| `speakers/<ID>/NNNNNN-context.wav` | float | fragment with up to 0.5 s of context on each side |
| `speakers/<ID>/NNNNNN-render.wav` | float | the context file after the speech chain |
| `speakers/<ID>/NNNNNN.wav` | float | levelled fragment, exactly as placed on the timeline |
| `speakers/<ID>/NNNNNN-mastered.wav` | 24-bit PCM | the same interval cut from the final master |
| `assembled.wav` | float | all fragments on the original timeline |
| `premaster.wav` | float | assembled audio after the first loudness pass |
| `master-vst.wav` | float | after the master chain |
| `master.wav` | float | final levelled master |

`NNNNNN` is the interval index in `fragments.json`. Background intervals get only
`-context.wav` and the timeline `.wav` file.

Intermediate float files may exceed 0 dBFS. Only `master.wav`, the
`-mastered.wav` cuts and the published output are peak-controlled.

## Privacy

Recordings, turn files and run folders contain your private data. Keep them
outside any public source tree. They are excluded from the package's source and
wheel builds, and the tool uploads nothing.
