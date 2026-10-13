# Local models

Diarization, DeepFilterNet restoration and quality scoring are not Python
dependencies of `vexy-speakup`. They call local adapters and native hosts that
run in their own uv environments. All model access runs offline, with
`HF_HUB_OFFLINE=1`, and no paid service is used.

## The adapter folder

Set `VEXY_SPEAKUP_TTS_ROOT` to the folder that holds `myasr/`, `myaud/` and
`.external/`:

```bash
export VEXY_SPEAKUP_TTS_ROOT=/path/to/tts
```

The folder is only looked up when a feature needs it. If it is unset or is not a
folder, that feature stops with an error that names the variable.

| Feature | Files used under `VEXY_SPEAKUP_TTS_ROOT` |
| --- | --- |
| `mlx` diarizer | `myasr/tools/diarize-mlx.py` |
| `sortformer` diarizer | `.external/NeMo-Speech.cpp/build/metal-asr/bin/nemo-speech` |
| `--ai=deepfilter` | `myaud/catalogs/deepfilternet-coreml.json`, `.cache/issue201/deepfilternet-coreml-materialized/`, `.external/DeepFilterNet-mlx/` |
| evaluation | `myaud/tools/aud-metrics.py` |

## Diarization

### `mlx` (default)

Runs `myasr/tools/diarize-mlx.py` with `uv run --offline --script` in offline
mode. It uses the cached `mlx-community/Nemotron-3-Diarization-8bit`
conversion and processes the complete file with its own bounded context, so
speaker IDs are not restarted per fragment. The raw result goes to
`diarization-native/report.json` in the run folder.

### `sortformer`

```bash
vexy-speakup run meeting.m4a --diarizer=sortformer
```

Runs the native `nemo-speech diarize` host on Metal with the Q8 GGUF of
`nvidia/diar_streaming_sortformer_4spk-v2` from the Hugging Face cache in
`~/.cache/huggingface/hub`. This model has four speaker slots.

Sortformer reports its last 80 ms frame as extending past the end of the file.
Only that last frame is clipped to the audio duration, and the original end time
is kept as `end_before_eof_clip` in `diarization-native.json`.

### Supplied turns

`--diarization_json` skips the diarizer. The file may be:

- a list of `{"start", "end", "speaker"}` objects,
- an object with a `turns` array, such as a `turns.json` from an earlier run, or
- an object with a `segments` array, such as a native diarizer report.

Use this to reuse a diarization, or to correct one by editing its `turns.json`.

## DeepFilterNet3

`--ai=deepfilter` runs DeepFilterNet3 through its CoreML host on the CPU before
the VST chains. Before running, the tool checks the SHA-256 of the host binary and
of every model file against `myaud/catalogs/deepfilternet-coreml.json`. Any
mismatch stops the run. The host writes mono output, which is converted back to
48 kHz stereo float; the sample count must match the input exactly.

## Quality scoring

Evaluation runs `myaud/tools/aud-metrics.py score` with DNSMOS and UTMOS, two
no-reference ONNX predictors. The interpreter is taken from:

1. `--metrics_python`, if given, or
2. the first `aud-metrics-*` environment under `~/.cache/uv/environments-v2`.

If neither exists, or a predictor fails, the error is stored for that window in
`evaluation.json` and the run continues. A missing predictor never becomes a
synthetic score.

To skip scoring, use `--evaluate=False`.

## Working without the adapters

Everything except diarization, DeepFilterNet and scoring works without
`VEXY_SPEAKUP_TTS_ROOT`:

```bash
vexy-speakup run meeting.m4a --diarization_json=turns.json --evaluate=False
```

`attempts` always runs the `mlx` diarizer, so it needs the adapters.
