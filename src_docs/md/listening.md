<!-- this_file: src_docs/md/listening.md -->
# Listen and choose in your browser

```bash
# From this checkout, including the optional browser dependencies:
uv tool install '.[gui]'
vexy-speakup gui /path/to/recordings
# Another port, without opening a browser automatically:
vexy-speakup gui --port=8766 --open_browser=False
```

The interface runs at `http://127.0.0.1:8765`. It processes files directly on
this computer; browsing folders does not upload recordings. Keep the terminal
running while you use the interface. Ctrl-C stops the server and its workers.
Closing a browser tab leaves the server and active job running.

1. Choose an audio/video folder using **Browse** or enter its path. Set your
   VST3 folder in **Settings**.
2. Tick the **Chains to compare**. The list holds your configured candidates and
   the built-in profiles. A chain is greyed out when a plugin it needs is neither
   in your VST3 folder nor one of the bundled free plugins (hover for the missing
   names); "open source" marks chains made only of bundled free plugins. The
   list refreshes after you save Settings.
3. Choose **Prepare listening clips**. The app decodes each recording once and
   chooses an energy-rich excerpt. This is a sampling heuristic, so review
   difficult sections of the full outputs too.
4. Compare the level-matched original and three tone variants for each chain:
   preset, +3 dB brightness, and −3 dB brightness. Playback pauses other clips.
   Failed plugins display errors on their clips; other chains still render.
5. Select the tone for every chain you want to keep, or **Skip this chain**.
   Global choices apply to every recording in the folder. Select an optional
   output folder, then **Save batch job**. Saving verifies the preview and
   source hashes and snapshots the selected recipes.
6. Choose **Run / resume job**. Each selected chain produces its own suffix.
   **Stop processing** cancels native workers; completed outputs are retained.
   Resume verifies outputs and reports before skipping them. **Replace existing
   outputs** permits replacement when retrying a failed or changed output.

Saved job paths appear in the interface and can be opened in another session,
including jobs made with the CLI. Run the same saved job without the browser:
`vexy-speakup job /path/to/job.json`. Earlier previews can be opened using their
`preview.json` path; previews live in the OS user-cache folder under
`vexy-speakup/previews/`. Opening previews requires choosing preferences again.

## Individual speakers

Enable **Choose separately for each speaker** before preparing clips. Choose
MLX or Sortformer (needs the `models` extra), or provide an existing
annotations folder. Speaker mode generates one listening group for each speaker
in each recording; IDs are scoped to that recording. Select one chain and tone
for **every** group. The count shows which groups still need choices.

Speaker clips use only the speech chain, then loudness and peak levelling, so
chains are compared on the speaker alone. After choosing, **Final mastering
(optional)** applies one chosen chain's master to the whole recording; the
default, **None**, keeps loudness and peak levelling only. Overlapping speech
uses the chain chosen for the speaker who talks most in that recording.
A speaker's longest exclusive interval supplies their clip; when no exclusive
interval exists the interface labels the excerpt as overlapping voices.
Overlapping audio cannot be independently separated by these processing chains.

Matching annotation files can contain a list of `{start, end, speaker}` turns,
or `{"turns": [...]}` as produced by vexy-subs in `work/diarization.json`.
Place them in the annotations folder with the corresponding media basename
(and relative folders). Times must use the same audio timebase as the source.
The full turns are saved in the batch job, so execution reuses those choices
and does not identify speakers again.

Settings edits retain custom candidate chains and back up the original TOML
once as `config.toml.bak`. Environment root overrides remain authoritative.
