<!-- this_file: src_docs/md/processing-details.md -->
# Processing details and limits


1. FFmpeg extracts stereo float PCM at 48 kHz. A delayed video audio start
   becomes leading silence. Diarization receives the original signal; optional
   AI restoration happens afterwards.
2. The diarizer processes the complete audio with its own bounded context, so
   speaker IDs are not restarted for each fragment.
3. The timeline is partitioned into disjoint speech, overlap and background
   intervals of at most 30 seconds (`--max_chunk`). Each speech fragment
   carries half a second of context at each edge.
4. Isolated plugin workers (`python -m vexy_speakup _render`) process chunk
   shards concurrently, up to `--workers` (default 4), and reset the chain
   between fragments. Speaker overrides apply to every shard. Stereo is retained. Two
   seconds of padding drain plugin buffering; Pedalboard compensates reported
   plugin latency.
5. A duration-weighted median calibrates each speaker. Turn adjustments stay
   within 3 dB of that baseline, and total gain within ±12 dB. Silence is never
   amplified. Adjacent fragments crossfade into each other over 40 ms.
6. Timeline assembly writes every sample exactly once. Background gaps remain.
   Overlap is processed once as a mixed fragment under `speakers/_overlap`.
7. Two-pass R128 levelling precedes continuous mastering; a measured pass then
   sets final loudness and true peak. Export checks the encoded true peak and
   attenuates and re-encodes if lossy encoding overshoots.
8. For video, FFmpeg copies the original video packets and replaces the audio.

`speakers/<ID>/*.wav` are levelled timeline fragments; `*-context.wav` and
`*-render.wav` keep their processing context. `*-mastered.wav` are 24-bit cuts
from the final master, with final levels and the full-recording limiter
behaviour. `fragments.json` records original times, sample offsets, active
speakers and gains. Intermediate WAVs are float PCM and may exceed 0 dBFS;
`master.wav` and the published output are the peak-controlled deliverables.
A long recording can consume tens of GB of work files.

`turns.json`, diarization receipts, `speaker-gains.json`, VST parameter
receipts, `report.json`, `evaluation.json`, subprocess logs and `latest.json`
make each run reviewable. A failed run records its error and keeps its work
files. A successful output is published through a temporary file and rename.
Parallel worker receipts and logs live in `speakers/<ID>/worker-NNN/`.

## Limits

Predictor scores guide comparisons. They do not establish speaker accuracy,
transcript preservation or perceptual quality across a whole meeting. Diarized
fragments are not isolated voices during simultaneous speech; that would need
separate microphone tracks or a tested separation model. Speaker IDs are
anonymous until you label them.

Recordings, turn files and run folders are your private data. They are excluded
from the source and wheel allowlists, and nothing is uploaded.

