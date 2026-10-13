# Changelog

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
