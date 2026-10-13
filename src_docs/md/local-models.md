# Local models

Diarization, DeepFilterNet restoration and quality scoring run local models. The
code ships inside `vexy-speakup` as `vexy_speakup.model_worker`; the model
libraries come from the optional `models` extra (macOS, Apple Silicon). No paid
service is used and no external adapter folder is needed.

## Install the extra

```bash
uv pip install 'vexy-speakup[models]'
```

The extra installs `mlx-audio==0.5.7`, `huggingface-hub`, `onnxruntime`,
`sentencepiece` and `speechonnxmetrics[audio]==0.0.2a3`. If it is missing, the
feature stops with `ModuleNotFoundError` naming this command; evaluation records
the error per window instead of failing the run.

Each model step runs as a child process, `python -m vexy_speakup.model_worker
diarize|score|deepfilter`, so cancellation and `--timeout` still kill it. Its log
is written to the run folder: `diarization.log`, `metrics.log` or
`deepfilter.log`.

## Weights

All weights download on first use into the standard Hugging Face cache
(`HF_HOME` / `HF_HUB_CACHE`, default `~/.cache/huggingface/hub`) and are pinned
by commit. The first use needs network access; afterwards runs work with
`HF_HUB_OFFLINE=1`.

| Feature | Hugging Face repository @ revision |
| --- | --- |
| `mlx` diarizer (default) | `mlx-community/Nemotron-3-Diarization-8bit` @ `dd8b8ce3d69a80540a7e50150e2beed1c34fee37` |
| `sortformer` diarizer | `mlx-community/diar_streaming_sortformer_4spk-v2.1-fp16` @ `e23e6404bd9859e93edbf94a740eb1c7fc58f12e` |
| `--ai=deepfilter` | `iky1e/DeepFilterNet3-MLX` @ `2439328cfebafb28099d9feff6890e29dbae2241` |
| evaluation (DNSMOS, UTMOS) | `TigreGotico/*-onnx`, revisions pinned by `speechonnxmetrics` |

## Diarization

### `mlx` (default)

Runs Nemotron-3-Diarization 8-bit with the offline AOSC preset on the whole
file, so speaker IDs are not restarted per fragment. The raw result goes to
`diarization-native.json` in the run folder.

### `sortformer`

```bash
vexy-speakup run meeting.m4a --diarizer=sortformer
```

Runs Streaming Sortformer 4spk v2.1 (fp16) on MLX, streamed in 30 s chunks. The
model has four speaker slots.

Both diarizers report their last 80 ms frame as extending past the end of the
file. Only that last frame is clipped to the audio duration, and the original end
time is kept as `end_before_eof_clip` in `diarization-native.json`.

### Supplied turns

`--diarization_json` skips the diarizer. The file may be:

- a list of `{"start", "end", "speaker"}` objects,
- an object with a `turns` array, such as a `turns.json` from an earlier run, or
- an object with a `segments` array, such as a native diarizer report.

Use this to reuse a diarization, or to correct one by editing its `turns.json`.

## DeepFilterNet3

`--ai=deepfilter` runs DeepFilterNet3 on MLX through `mlx-audio` before the VST
chains. The input is downmixed to 48 kHz mono, and the output sample count must
match the input exactly. `deepfilter-receipt.json` in the run folder lists the
SHA-256 of every weight file.

The weights are the same `model.safetensors` (SHA-256 `fca0af2f...`) as the
CoreML package used before; outputs differ slightly from that host.

## Quality scoring

Evaluation scores matching windows with DNSMOS and UTMOS, two no-reference ONNX
predictors from `speechonnxmetrics`, with weights redirected to the standard
Hugging Face cache.

`--metrics_python` is optional: an alternative interpreter that has
`vexy-speakup[models]` installed. By default scoring uses the current
interpreter.

If a predictor fails or the extra is missing, the error is stored for that window
in `evaluation.json` and the run continues. A missing predictor never becomes a
synthetic score. To skip scoring, use `--evaluate=False`.

## Working without the extra

Without the `models` extra you can still run with `--diarizer=none` (whole
recording, no per-speaker choices), or with your own turns:

```bash
vexy-speakup run meeting.m4a --diarization_json=turns.json --evaluate=False
```

`attempts` always runs the `mlx` diarizer, so it needs the extra.
