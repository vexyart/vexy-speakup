<!-- this_file: PLAN.md -->
# Plan

## Issue 101: completed listening-guided batch restoration

Deliver a configurable CLI and local browser UI that compare speech chains, save listening
choices and process folders with optional individual speaker choices.

1. Verify every legacy module, probe, CLI command, test and example against
   `src/` and `tests/`. Retire duplicate source after fresh regression tests;
   retain private original files and measurement evidence with hashes.
2. Scan `/Volumes/Falstaff4T/RomeoData2/audio/Plug-Ins/VST3` using Pluginary.
   Correct actual scan failures (quoted spaced paths, truncated worker output,
   timed-out worker termination), rebuild and rescan. Preserve scanner results
   and failures. Extend Pluginary's plugin metadata with source URL, retrieved
   date, verified capability, licence, suitability and caveats; populate it from
   vendor documentation and the source repositories listed in issue 101.
3. TOML app settings: OS config location, plugin/model roots, candidates,
   processing defaults, worker count and per-chain suffixes. Include four
   useful comparison chains, one entirely open source, and adjustable voice
   brightness. Support listed open-source components through installed VST3
   builds or documented executable adapters; distinguish working integrations
   from researched candidates requiring assets/builds. Do not silently fall
   back when a selected processor is missing.
4. Batch CLI: discover audio/video files, save explicit jobs, run selected
   variants with separate suffixes, resume completed tasks, report failures,
   and bound simultaneous native workers across file/chunk processing.
5. Local browser UI (FastAPI/Uvicorn, plain browser audio): pick folder, extract representative speech clips, listen to at least
   four chain variants, choose variants and save a batch job for later CLI or
   GUI execution. Show failed/missing plugins as errors. Keep preview processing
   off the UI thread and use the same render path as batch processing.
6. Speaker mode: diarize and preview each speaker; record listening choices
   per file and speaker, since anonymous IDs are not stable between files.
   Apply different speech chains per speaker, preserve the timeline and handle
   overlaps explicitly. Share relevant diarization contracts with vexy-subs
   rather than creating inconsistent annotation formats.
7. Acceptance: real private recording previews including brighter variants,
   actual plugin parameter/load/render checks, end-to-end folder and saved-job
   processing, GUI playback/selection/reload, per-speaker choice verification,
   and sample-exact audio/video preservation. Run full tests, build artifacts,
   review cleanup and code directly, document limits and actual integrations.

Current evidence and next actions are in WORK.md. The seven-story ledger is
private at `.omc/ultragoal/goals.json`. Every issue requirement above has
implementation and acceptance evidence; see WORK.md and the private final review.

## Release follow-up

1. First release: tag `v0.1.0` on a clean commit, `uv build`, `twine check`,
   upload only after explicit approval.
2. Keep packaging aligned with vexy-subs: hatch-vcs versions, src layout,
   Fire CLI, the same `test.sh` shape and privacy-focused `.gitignore`.
3. Speaker-separation or multitrack input would be needed before overlap can be
   processed per voice; until then overlap stays one mixed fragment.
