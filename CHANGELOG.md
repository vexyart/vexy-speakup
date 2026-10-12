<!-- this_file: CHANGELOG.md -->
# Changelog

## Unreleased
- Added `build.sh` (test, build, twine check) and `publish.sh` (test,
  gitnextver tag, build, `uv publish` with retry on rate limits).
- Ported the `speech-polish` script collection into the installable
  `vexy_speakup` src-layout package with a `vexy-speakup` Fire CLI.
- Versions now come from git tags through hatch-vcs; the generated
  `__version__.py` is ignored by git. Added a `version` command.
- Plugin workers run as `python -m vexy_speakup`, so the installed package
  needs no adjacent script.
- Replaced machine-specific paths: plugins default to
  `/Library/Audio/Plug-Ins/VST3` (`VEXY_SPEAKUP_PLUGIN_ROOT`), and local model
  adapters come from `VEXY_SPEAKUP_TTS_ROOT`, resolved only when used.
- Folded the standalone plugin probe script into the `probe` command.
