# Quickstart

This walk-through processes a meeting recording called `meeting.mp4`. It first
compares three profiles on a short excerpt, then processes the full file with the
one that sounds best.

## Before you start

- `vexy-speakup`, `ffmpeg` and `ffprobe` are installed. See
  [Installation](installation.md).
- The plugins used by the built-in profiles are installed: Accentize dxRevive
  Pro, iZotope RX 12 Voice De-noise and iZotope Ozone 12 Maximizer.
- `VEXY_SPEAKUP_TTS_ROOT` points to the local model adapters. If you do not have
  them, skip to [Process without local models](#process-without-local-models).

## Compare profiles on an excerpt

1. Run `attempts` on the recording:

    ```bash
    vexy-speakup attempts meeting.mp4
    ```

    By default this takes 45 seconds starting at 120 seconds, diarizes that
    excerpt once, and processes it with the `dx35`, `dx65` and `rx6-dx35`
    profiles. Everything goes into `meeting_attempts/` beside the input.

2. Listen to `meeting_attempts/dx35.wav`, `meeting_attempts/dx65.wav` and
   `meeting_attempts/rx6-dx35.wav`.

3. Optionally, read `meeting_attempts/comparison.json`. It holds the full report
   of each attempt, including the DNSMOS and UTMOS scores of matching windows
   before and after processing.

The scores help you compare attempts. They do not prove that one attempt sounds
better across the whole meeting, so let your ears decide.

## Process the full recording

1. Run the profile you chose on the whole file:

    ```bash
    vexy-speakup run meeting.mp4 --profile_name=dx65 --verbose
    ```

    `--verbose` prints each stage as it starts. The first line names the run
    folder:

    ```text
    Work: /path/to/meeting/run-20260101-101500-123456
    ```

2. Wait for the final line:

    ```text
    Output: /path/to/meeting_improved.mp4
    ```

    `meeting_improved.mp4` contains the original video packets and the improved
    audio track.

3. To read what was done, open `report.json` in the run folder. See
   [Run folders and reports](outputs.md).

If you run the same command again, it stops because `meeting_improved.mp4`
already exists. Add `--force` to replace it. Each run creates a new run folder,
so the earlier run stays available.

## Process without local models

Without `VEXY_SPEAKUP_TTS_ROOT`, give the tool your own speaker turns and turn off
scoring.

1. Write `turns.json` with one entry per turn. Times are in seconds from the start
   of the recording; speaker IDs may contain letters, digits, `_` and `-`:

    ```json
    [
      {"start": 0.0, "end": 12.4, "speaker": "anna"},
      {"start": 12.4, "end": 30.0, "speaker": "ben"},
      {"start": 28.5, "end": 41.0, "speaker": "anna"}
    ]
    ```

2. Run the tool with these turns:

    ```bash
    vexy-speakup run meeting.m4a --diarization_json=turns.json --evaluate=False
    ```

    The result is `meeting_improved.m4a`. Between 28.5 and 30.0 seconds both
    speakers talk at once, so that interval is processed once as a mixed
    fragment rather than twice.

## Preview an audio file

For an audio input, `--start` and `--duration` process only an excerpt:

```bash
vexy-speakup run meeting.m4a --start=120 --duration=45
```

The output gets a `_preview` suffix, `meeting_improved_preview.m4a`, so it does
not collide with a full-length output. Video input cannot be previewed this way;
trim the video first, or extract the audio as shown in
[Command reference](cli.md#export-audio-from-a-video).
