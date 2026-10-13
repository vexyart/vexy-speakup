<!-- this_file: issues/101-research.md -->
# Issue 101: plugin research and catalog evidence

Checked 2026-10-13. Structured findings are stored in Pluginary at
`shared/research/speech-20261013.json`, imported into the live scanner database
at `~/Library/org.pluginary.scanner/plugins.db`. There are 26 research entries:
16 real VST3 plugin descriptions and ten non-plugin components, including `tts`.
Each separates primary-source facts, suitability inferences, caveats and runtime
scan evidence. Nine source README files match their pinned commits byte-for-byte.

## Inventory and reliability

The first native scan found 1,073 entries but returned many false failures for
paths containing spaces. Worker argument reparsing kept literal quote characters;
blocking pipe reads also prevented timeouts on silent workers and truncated
large output. These defects were fixed in the sibling Pluginary scanner.

The full corrected rescan finished normally:

- 1,073 discovered entries, including system and requested external VST3 folders.
- 1,020 successful attempts; 31 failures; 22 enforced timeouts.
- 933 exported catalog records; duplicate installed copies share named IDs.
- Full log: `.omc/ultragoal/plugin-rescan-20261013.log`.
- Export: `.omc/ultragoal/plugin-catalog-researched-20261013.json`.
- Native tests: 23 passed. Python filter tests: 34 passed, three existing skips;
  ruff and mypy passed. Metadata survives native rescans and native/Python preset
  export roundtrips. Imports are atomic and exact-ID based.

A successful metadata scan is not evidence of activation, usable audio output,
operational latency, model readiness or listening quality. Those are separate
acceptance checks. Failed/unsupported plugins remain recorded as failures.

## Comparison shortlist

- **dxRevive Pro:** compare conservative and stronger restoration. Its
  [manual](https://www.accentize.com/products/dxReviveProManual.pdf) distinguishes
  Studio/Natural/Retain/EQ Restore processing. Natural changes tone less; EQ
  Restore addresses spectral issues without doing noise/reverb suppression.
  These are promising comparisons for muffled speakers, rather than assuming
  a stronger broadband mix always helps.
- **RX Voice De-noise / Acon DeNoise:** conventional adaptive-noise comparisons
  before restoration. Reduction must remain conservative enough to preserve
  speech detail; learned profiles need a real noise-only section.
- **Clear / DeRoom Pro / Acon DeVerberate:** dedicated alternatives for noisy or
  reverberant speakers. Clear offers separate voice/ambience/reverb gains; its
  trial injects noise, so scanning alone cannot establish deliverable readiness.
- **Pro-Q 4:** a modest upper-frequency shelf is a direct brightness control;
  dynamic/spectral bands can restrain harshness. Use the installed plugin's
  actual parameter names and verify the chosen latency mode.
- **SpectralBalance:** reference EQ for a speaker with a suitable clean speech
  reference. It is not a substitute for denoising or reconstruction of absent
  content. Avoid forcing different speakers into one person's spectral shape.
- **Ozone Clarity:** an optional adaptive tone comparison. Its music-mastering
  origin makes a listening test on speech necessary.
- **Ozone Maximizer:** continuous final peak/dynamics processing, with measured
  loudness and encoded-output peak checks retained. It does not fix muffling.
- **Mouth De-click:** optional speaker-specific click repair before restoration;
  monitor consonants and keep clicks-only audition modes out of final output.
- **DialogueEnhance:** compare its integrated speech processing against a
  modular chain, avoiding duplicated tone/dynamics stages.
- **VoiceGate2:** installed and scanned; the vendor's original VoiceGate page
  is retired. Successor/licence status is deliberately left uncertain rather
  than inferred from the bundle name.

Full source links and version/control-count evidence are in the database records.

## Open-source components

- **PodcastPlugins TRACK / MASTER:** both are installed and scanned. TRACK
  shapes individual speaker tone/dynamics, with TIMBRE moving warmer/brighter.
  MASTER belongs on the continuous assembled recording. Both loaded and
  produced finite stereo output from a real 12-second source excerpt; complete
  chain, edge/latency and listening checks still remain. This is the first
  planned fully GPL open-source comparison chain.
- **noise-repellent / libspecbleach:** spectral-noise reduction. Prefer the
  existing VST3 wrapper to another C binding. NLM has its own worker pool;
  external chunk workers must account for it. These are researched but not
  installed in the current inventory.
- **master_me:** continuous automatic mastering, with VST3 available upstream.
  Use an installed/build-qualified plugin before calling this an integration.
- **vocal-gate:** optional speech-aware microphone-event gate. Its documented
  750 ms lookahead requires context and verified delay compensation. Cough
  suppression is distinct from broadband denoising or diarization.
- **dereverb-vst3:** inspected JenyaDereverb2 requires 48 kHz and documents
  960 samples delay. Other sample rates bypass; intermediate mix can cancel
  phase. No root plugin licence was found, so model/runtime licences alone
  cannot establish a redistributable fully open-source plugin licence.
- **Matchering:** reference-based final spectral/level matching. A clean
  same-speaker speech reference is an optional control; music-reference
  matching can impose an unwanted tone/stereo character.
- **Resemble Enhance:** isolated model/executable comparison for denoising and
  bandwidth enhancement. Assets, Torch/backend compatibility and exact frame
  restoration must be verified before enabling it.
- **Audio_Enhanced:** AudioForge offers useful local A/B orchestration patterns.
  It is an application, not a VST. Silence trimming should not be imported into
  this project's timeline-preserving video workflow.
- **tts:** existing local adapters supply diarization, optional DeepFilterNet
  and metrics. Assets and licences belong to individual tools/models; speaker
  identities do not become stable across files merely because IDs match.

## Remaining acceptance

Implement and render at least four useful comparison chains, including the
open-source chain and brighter variants. Save batch listening choices and
per-file speaker mappings in the shared job format. Verify actual chain audio,
preview/full processing consistency, full timeline preservation, GUI playback
and speaker selection on the private recordings named in issue 101.
