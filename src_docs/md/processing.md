# How processing works

This page follows one recording through `vexy-speakup run`. The example is a
60-second video, `call.mp4`, with two speakers, `A` and `B`:

| Time (s) | Who speaks |
| --- | --- |
| 0.0 – 2.0 | nobody |
| 2.0 – 40.0 | `A` |
| 38.0 – 40.0 | `A` and `B` |
| 40.0 – 58.0 | `B` |
| 58.0 – 60.0 | nobody |

## 1. Decode

FFmpeg decodes the first audio stream to `input.wav`: 48 kHz, stereo, 32-bit
float, RF64 when the file is large. For video, FFmpeg resamples against the
container timestamps, so audio that starts late in the video becomes leading
silence. Without that, the processed audio would drift against the picture.

## 2. Diarize

The diarizer reads the complete `input.wav`, so speaker IDs stay consistent
across the whole recording. The result is a list of turns, each with `start`,
`end` and `speaker`, saved as `turns.json`. Diarization always sees the original
signal, even when `--ai=deepfilter` is used.

The turns are checked before use. Each start and end must be a finite number,
`0 <= start < end`, and the end must lie within the audio. Each speaker ID must
contain only letters, digits, `_` and `-`.

## 3. Optional AI restoration

With `--ai=deepfilter`, DeepFilterNet3 runs through its local CoreML host on the
decoded audio. Its output is converted back to the same format and must have
exactly the same number of samples; if not, the run stops.

## 4. Partition the timeline

The timeline is cut wherever a turn starts or ends. Each piece is labelled with
the speakers active in it, and neighbouring pieces with the same speakers are
merged. Pieces longer than `--max_chunk` seconds (default 30) are split. For the
example, this gives:

| Interval (s) | Speakers | Owner |
| --- | --- | --- |
| 0 – 2 | none | `_background` |
| 2 – 32 | `A` | `A` |
| 32 – 38 | `A` | `A` |
| 38 – 40 | `A`, `B` | `_overlap` |
| 40 – 58 | `B` | `B` |
| 58 – 60 | none | `_background` |

The `A` interval from 2 to 38 seconds is longer than 30 seconds, so it is split
at 32. Every sample belongs to exactly one interval, so nothing is processed
twice.

For each interval, half a second of context is cut on each side, where
available, and saved as `speakers/<owner>/NNNNNN-context.wav`. The context gives
plugins a run-up and is removed again later.

## 5. Render each speaker

Each owner with speech (`A`, `B` and `_overlap`) has its chunks distributed to
isolated workers, up to the configured worker budget. Each worker loads its
chain once: the owner's chain from `speakers` in a custom chain file, or the
shared `speech` chain. Background intervals are not rendered. Whole-recording
mode (`--diarizer=none`) explicitly uses one uniform chain over the full signal.

For each fragment, the worker:

1. resets the plugin state,
2. adds two seconds of silence so plugin buffers drain,
3. renders the fragment in stereo, with plugin latency compensated by Pedalboard,
4. crops the result to the original length and saves it as `NNNNNN-render.wav`.

A render fails if it returns the wrong shape or non-finite samples, or if a
non-silent input comes back silent. A silent output usually means an unlicensed
plugin or a wrong setting.

Running each owner in its own process means that a plugin crash or hang stops
only that worker, and `--timeout` limits how long it may take.

## 6. Level the speakers

Each rendered fragment is measured with BS.1770 integrated loudness. Fragments
shorter than 400 ms are padded with silence for the measurement only.

1. **Speaker baseline.** For each owner, the median loudness of its fragments,
   weighted by fragment length, sets a gain that brings that speaker to two LU
   below `--target_lufs`. Short turns therefore do not dominate. The baseline
   gain is limited to ±12 dB.
2. **Fragment correction.** Each fragment may then differ from its speaker's
   baseline by at most 3 dB, and the total gain is limited to ±12 dB.
3. **Silence.** A fragment whose RMS level is below 10⁻⁶ gets no gain, so room
   tone and silence are never amplified.

The gains are saved in `speaker-gains.json` and per fragment in
`fragments.json`.

## 7. Assemble

The fragments are written in timeline order to `assembled.wav`. The context
margins are cropped away. Neighbouring fragments crossfade into each other over
40 ms centred on each cut, using both fragments' own audio (renders keep half a
second of context), so two speakers' chains meet directly rather than through
unprocessed audio. Background intervals are copied from the source and crossfade
the same way. The first and last samples are never faded. If the assembled file has a different number of
samples from the input, the run stops.

## 8. Master

1. The assembled audio gets a two-pass EBU R128 `loudnorm` to `--target_lufs`
   and `--true_peak` (`premaster.wav`).
2. The master chain processes the whole file in 10-second blocks without
   resetting between blocks, then drains the plugin tail (`master-vst.wav`).
3. A second two-pass `loudnorm` sets the final loudness and true peak
   (`master.wav`).

A silent file skips `loudnorm`, because its loudness is undefined.

From `master.wav`, each speech interval is cut again as a 24-bit
`NNNNNN-mastered.wav`, so the fragments carry the final levels.

## 9. Evaluate

With `--evaluate=True`, up to three windows of up to 30 seconds are chosen,
starting at the first, middle and last turn. Each window is cut from the original and from the
master, and both are scored with DNSMOS and UTMOS. Missing predictors are
recorded as errors in the report; they never produce invented scores. See
[Local models](local-models.md).

## 10. Encode and publish

The master is encoded to the output format. For a video, the original video and
subtitle streams are copied without re-encoding, and the new audio replaces the
old. Metadata is copied from the input.

Lossy encoders can push the true peak above the limit, so the encoded file is
measured. If its true peak exceeds `--true_peak` by more than 0.1 dB, the
volume is lowered by the excess plus 0.15 dB and the file is encoded again.
The file is encoded at most three times. The output is first written to a hidden temporary file beside the
destination and then renamed, so an interrupted run never leaves a half-written
output.

## Limits

- During overlap, the speakers are processed together as one mixed fragment.
  Separating simultaneous voices would need separate microphone tracks or a
  tested separation model.
- Predictor scores guide comparisons. They do not establish speaker accuracy,
  transcript preservation or perceived quality across a whole meeting.
- Speaker IDs are anonymous until you label them.
