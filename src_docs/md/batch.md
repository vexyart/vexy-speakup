<!-- this_file: src_docs/md/batch.md -->
# Folder jobs and saved choices

```bash
vexy-speakup batch recordings --workers=8 --file_workers=2
vexy-speakup schedule recordings --candidates=podcast,dx35-bright
vexy-speakup job /path/to/saved-job.json --workers=8 --file_workers=2
```

`batch` schedules and immediately runs the folder. `schedule` saves the job and
prints its path; `job` runs or resumes it. `--job_path` chooses a particular JSON
file. Otherwise jobs are stored in the platformdirs user data folder under
`vexy-speakup/jobs/`. Existing job files are not overwritten.

The default candidates are PodcastPlugins, dxRevive, brighter dxRevive and Clear.
Their suffixes are `_podcast`, `_dx35`, `_dx35-bright` and `_clear`.
Outputs keep the input extension in `recordings/speakup-output/`, or in
`--output_dir`. Audio and video can share one batch. `--recursive=True` retains
the relative input subfolders, preventing equal basenames in different folders
from colliding. The output subtree is excluded from discovery.

## Speed and speaker preparation

The total native worker budget is split across `file_workers` concurrent variant
tasks. Chunk workers load their chains once per shard and reset between chunks.
Decoding and diarization happen once per input and are shared by its variants.
Continuous mastering runs after assembly; it is not split into independent
chunks. MOS evaluation defaults off in batch jobs.

Global processing defaults to `--diarizer=none`: one uniform speech chain across
the complete recording, without requiring a diarization model. Use
`--diarizer=mlx` or `sortformer` when you need identified speaker intervals;
configure the local model root first. This processes the full original audio,
not separately restarted speaker detection in each processing chunk.

`--diarization_dir` supplies annotations at matching relative filenames with
`.json` extensions. For `recordings/session/call.mp4`, use
`annotations/session/call.json`. Their contents are copied into the job, so
moving or editing the sidecars later does not change scheduled choices.

## Resume and failures

A job snapshots input hashes, processing settings, resolved plugin chains and
per-file speaker overrides. Each task records its output hash and successful
run report. Completed tasks are skipped only after the current source/output
hashes, chain choices and processing settings match. An interrupted runner can
recover a render from its complete, matching report and output hash.

Changed inputs fail explicitly. Changed outputs or changed processing choices
require a deliberate retry; `job --force=True` allows replacing output files.
Failures remain on individual tasks while other tasks continue. A failed batch
or job exits the CLI with status 1. The job JSON and work logs retain the errors.
A kernel lock prevents simultaneous execution of one job and releases if its
runner dies; the lock file's presence alone does not mean a runner is alive.

Speaker choices are keyed by the explicit input path and speaker ID in
`variants[].file_speakers`. The same anonymous ID in two files can therefore
receive different chains. Unknown speaker choices fail instead of silently
using a default. These choices affect speech processing; mastering remains one
continuous chain for that output variant.
