# vexy-speakup

`vexy-speakup` restores a recorded conversation with the VST3 speech plugins you
already have installed. It works one speaker at a time, levels each speaker,
masters the whole recording, and gives you back the same file type. If the input
is a video, the original video packets are copied unchanged and only the audio
track is replaced, so the timeline stays exactly as it was.

```bash
vexy-speakup run meeting.mp4 --profile_name=dx65 --verbose
```

For `meeting.mp4`, this writes `meeting_improved.mp4` beside the input and keeps
every intermediate file in a new run folder under `meeting/`.

## What happens to a recording

1. FFmpeg decodes the first audio stream to 48 kHz stereo 32-bit float WAV.
2. A local diarizer labels who speaks when. You can also supply your own speaker
   turns as JSON.
3. The timeline is split into disjoint intervals: one speaker, several speakers
   at once (overlap), or nobody (background).
4. Each speaker's fragments go through that speaker's VST3 chain in an isolated
   worker process.
5. Each speaker gets a loudness baseline, and each fragment is corrected within
   3 dB of it.
6. The fragments are written back onto the original timeline, sample for sample.
7. The whole recording is levelled to EBU R128, sent through the master chain,
   and levelled again to the target loudness and true peak.
8. The result is encoded and checked for true peak. For video, the new audio is
   remuxed with the original video.

[How processing works](processing.md) follows a single recording through these
steps in detail.

## Requirements at a glance

- macOS, Python 3.12 or later, and `ffmpeg`/`ffprobe` on `PATH`.
- Installed VST3 plugins. The built-in profiles expect Accentize dxRevive Pro,
  iZotope RX 12 Voice De-noise and iZotope Ozone 12 Maximizer.
- For automatic diarization, optional DeepFilterNet restoration and quality
  scoring: the local model adapters described in [Local models](local-models.md).
  Without them, supply speaker turns with `--diarization_json` and turn scoring
  off with `--evaluate=False`.

No plugin, model or recording is distributed with the package, and nothing is
uploaded anywhere.

## Where to go next

| Page | Read it when you want to |
| --- | --- |
| [Installation](installation.md) | install the tool and check prerequisites |
| [Quickstart](quickstart.md) | process a first recording |
| [Command reference](cli.md) | look up every command and flag |
| [Profiles and custom chains](configuration.md) | choose or write plugin chains |
| [How processing works](processing.md) | understand levels, overlap and timing |
| [Run folders and reports](outputs.md) | find and read the files a run leaves behind |
| [Local models](local-models.md) | set up diarization, DeepFilterNet and scoring |
| [Troubleshooting](troubleshooting.md) | fix a failed run |
| [Development](development.md) | test, build and release the package |
