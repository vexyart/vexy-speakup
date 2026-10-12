---
name: vexy-speakup
description: Restore, level and master speech in local meeting recordings with installed VST3 plugins, keeping the video timeline.
---
<!-- this_file: skills/vexy-speakup/SKILL.md -->

# vexy-speakup

Check `command -v vexy-speakup` and FFmpeg/ffprobe. Plugins come from
`/Library/Audio/Plug-Ins/VST3` unless `VEXY_SPEAKUP_PLUGIN_ROOT` is set. Model
diarization and scoring need `VEXY_SPEAKUP_TTS_ROOT`; otherwise supply
`--diarization_json` and `--evaluate=False`.

```bash
vexy-speakup attempts meeting.m4a --start=120 --duration=45
vexy-speakup run meeting.mp4 --profile_name=dx65 --verbose
vexy-speakup inspect /Library/Audio/Plug-Ins/VST3/Accentize-dxRevivePro.vst3
```

Listen to the preview attempts before a full run; predictor scores guide but do
not prove quality. Read `report.json` in the run folder for levels, receipts and
errors. Keep recordings and run folders outside the public source tree, and
never publish the package without explicit authorization.
