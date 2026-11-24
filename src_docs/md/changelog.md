# Changelog

## Unreleased

- Site now uses fly-january 0.3.0 or later (chrome: none).
- Fixed a mastering bug: with a latent master plugin (Ozone 12 Maximizer,
  PodcastPlugins MASTER), audio after the first 10 seconds was delayed by the
  plugin latency (10–17 ms) with a short silence at the 10-second mark. Outputs
  now align within 3 samples. Re-render files mastered with those plugins.
- Detects the researched speech plugins in your VST3 folder and lists them in
  the browser interface with their role.
- Adds automatic `auto-*` chains built from the detected plugins; two fully
  open-source ones are always available.

## 1.0.2

- Local models are bundled (optional `models` extra) and use the standard
  Hugging Face cache; `VEXY_SPEAKUP_TTS_ROOT` is gone.
- Free GPL plugins download on demand from the vexy-speakup-assets repository
  (`assets fetch`, `assets list`); on Windows, Vocal Gate runs its installer.
- The browser interface lets you choose which chains to compare, no longer
  forces a shared master in speaker mode, and offers an optional final master.
- Neighbouring fragments crossfade into each other over 40 ms.

## 1.0.0

- Ported the `speech-polish` script collection into the installable
  `vexy_speakup` package with a `vexy-speakup` command-line tool.
- Versions come from git tags through hatch-vcs. Added a `version` command.
- Plugin workers run as `python -m vexy_speakup`, so the installed package needs
  no script beside it.
- Replaced machine-specific paths: plugins default to
  `/Library/Audio/Plug-Ins/VST3` (`VEXY_SPEAKUP_PLUGIN_ROOT`), and local model
  adapters come from `VEXY_SPEAKUP_TTS_ROOT`, looked up only when used.
- Folded the standalone plugin probe script into the `probe` command.
- Added `build.sh` and `publish.sh`.

The full history is in
[CHANGELOG.md](https://github.com/vexyart/vexy-speakup/blob/main/CHANGELOG.md).
