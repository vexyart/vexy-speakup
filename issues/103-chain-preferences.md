---
this_file: issues/103-chain-preferences.md
---

# Chain preferences for "FontLab 9 rough magic", and the `<!DOCTYPE` error

Recording: `/Volumes/Falstaff4T/TypoVideo6/fonttechai26/fonttechai26--twardoch--fontlab-9-rough-magic.work3`
Listening session: `~/Library/Caches/vexy-speakup/previews/111bc1d8dfc04fb0b19638f90e508d6a/preview.json`
(one 10-second clip from 2273.6 s; 14 chains × 3 tone variants, all rendered without errors).

## What was liked

Sensible results: `rx6-dx35` and `auto-gate`, both at **Brighter +3 dB**.
Acceptable: `dx35` and `dx65`, also only at **Brighter +3 dB**.

## What those chains have in common

All four contain **Accentize dxRevive Pro**. All four end in the same master,
Ozone 12 Maximizer (output −2 dBTP, no input gain, no upward compression, no soft clip).

| Chain | Speech chain |
|---|---|
| `dx35` | dxRevive Pro, mix 35 % |
| `dx65` | dxRevive Pro, mix 65 % |
| `rx6-dx35` | RX 12 Voice De-noise (reduction 6, adaptive), then dxRevive Pro 35 % |
| `auto-gate` | Accentize VoiceGate2 (sensitivity 50, reduction 15), then dxRevive Pro 35 % |

The preference is for dxRevive restoration. The two favourites add a light
denoise or speech-aware gate in front of it.

Duplicates in the session: `dx35` at +3 dB is the same chain as `dx35-bright` at
preset tone (a 3 kHz +3 dB shelf after dxRevive). `auto-restore` is identical to `dx35`.

## Why only the "Brighter +3 dB" variants work

"Brighter +3 dB" appends a high shelf at 3 kHz, +3 dB, Q 0.707, after the speech
chain and before the master. On this recording dxRevive darkens the voice, and
the shelf puts the lost top end back.

Band energy of each clip, in dB relative to the 80 Hz–16 kHz total:

| Clip | RMS dBFS | 2–5 kHz | 5–10 kHz | >10 kHz |
|---|---|---|---|---|
| original | −19.5 | −15.1 | −21.0 | −37.3 |
| dx35, preset tone | −19.4 | −16.6 | −24.7 | −38.8 |
| **dx35 +3** | −19.5 | **−15.0** | **−21.9** | −35.7 |
| dx65, preset tone | −19.3 | −15.8 | −22.7 | −34.6 |
| **dx65 +3** | −19.4 | −14.3 | −20.0 | −31.8 |
| **rx6-dx35 +3** | −19.7 | −14.7 | −21.6 | −35.2 |
| **auto-gate +3** | −19.5 | −14.9 | −21.6 | −35.0 |
| rx6, preset tone | −19.5 | −15.0 | −20.8 | −37.4 |
| clear, preset tone | −19.5 | −15.1 | −21.0 | −37.3 |
| podcast, preset tone | −19.5 | −14.8 | −19.6 | −31.4 |
| auto-free-denoise, preset tone | −19.1 | −14.7 | −18.6 | −30.2 |

- **dxRevive Pro at 35 %** removes about 3.7 dB at 5–10 kHz. With +3 dB, the
  tonal balance is back to roughly the original's, but the voice keeps
  dxRevive's cleaning and restoration. At 65 % it darkens less, so +3 dB
  lands slightly brighter than the original.
- **The rejected chains** were already brighter than the original
  (`podcast`, `auto-free-*`: 6–7 dB more above 10 kHz), or they changed the
  tone without restoring anything (`clear`, `rx6` alone).
- **Loudness did not drive the choice.** Every clip sits within 0.7 dB of
  −19.5 dBFS RMS.

In short: this recording wants dxRevive Pro for restoration, plus a small
3 kHz lift to undo its darkening. A gate or light RX denoise in front helps.

## The error after "Clips ready"

```
Unexpected token '<', "<!DOCTYPE "... is not valid JSON
```

### Cause

- An old `python -m http.server 8765` (PID 79511, running since 7 Oct 2026)
  was listening on every address on port 8765.
- `vexy-speakup gui` binds `127.0.0.1:8765`. macOS allowed that bind next to
  the wildcard listener, so the GUI started normally.
- After "Clips ready", the vexy-speakup process stopped. There is no crash
  report for it, so it was probably closed with Ctrl-C or with its terminal.
  The exact reason is unknown.
- The page polls `/api/state` once a second. Those requests then reached
  `http.server`, which answered with an HTML 404 page (`501` for POST). The
  page tried to parse that HTML as JSON.

Verified with:

```
$ curl -s -i http://127.0.0.1:8765/api/state
HTTP/1.0 404 File not found
Server: SimpleHTTP/0.6 Python/3.13.10
Content-Type: text/html;charset=utf-8
```

### Consequences

- The choices were **not** saved. No job for this recording exists in
  `~/Library/Application Support/vexy-speakup/jobs/`.
- The rendered clips and `preview.json` are intact and can be reloaded.

### Recovery

1. `kill 79511`
2. Start `vexy-speakup gui` again.
3. Use "Load listening session" with the `preview.json` path above.
4. Tick `rx6-dx35`, `auto-gate`, `dx35` and `dx65` at Brighter +3 dB, then save the batch job.

### Fix in the code

- `gui()` in `src/vexy_speakup/web.py` now checks whether something already
  answers on the port and refuses to start:
  `OSError: Another program already answers on port 8765; stop it or pass --port`.
- `api()` in `src/vexy_speakup/web_assets/app.js` now reports a stopped
  server in plain words instead of a JSON parse error.
- New test: `test_gui_when_port_answers_then_refuses_before_serving` in
  `tests/test_web.py`. Full suite: 108 passed.

## Follow-up: spatial experiments after the Accentize chain

Accentize makes both dxRevive Pro and VoiceGate2, so `auto-gate`
(VoiceGate2, then dxRevive Pro 35 %) stays as the base. Two experiments add a
spatial plugin after it, before the Ozone master:

| Chain | Added after dxRevive | Settings |
|---|---|---|
| `auto-gate-wider` | Polyverse Wider 2 | amount 50 %, low bypass 161 Hz |
| `auto-gate-stageone` | Leapwing StageOne 2 | Mono Spread 100 on mid and high bands, 0 on low; Depth 0 |

### Why these settings

The recording is dual-mono: left and right are identical (correlation 1.00).

- **StageOne 2 Width** stretches off-centre content only, so it does nothing
  here. **Mono Spread** is the control that works on mono. **Depth** adds
  reflections, which work against dxRevive's dereverberation, so it stays at 0.
- **Wider** is built for mono sources. At 50 % it is clearly wide but not
  extreme. Low bypass at 161 Hz keeps the chest of the voice centred.
- Both plugins are mono-compatible: summing to mono gives back the input
  (difference below −58 dB).

### Measured on the same 10-second clip, Brighter +3 dB

| Chain | Side/mid | L/R correlation | RMS dBFS | Timing vs `auto-gate` |
|---|---|---|---|---|
| `auto-gate` | none (mono) | 1.00 | −19.5 | — |
| `auto-gate-wider` | −6.7 dB | 0.65 | −19.6 | 0 samples |
| `auto-gate-stageone` | −17.0 dB | 0.96 | −19.6 | 0 samples |
| `rx6-dx35` | none (mono) | 1.00 | −19.7 | 0 samples |

StageOne 2 reports 2048 samples of latency. The chain compensates for it, so
the clips line up exactly. Loudness stays matched, so a preference will not
come from one clip being louder.

New listening session (load it with "Load listening session"):
`~/Library/Caches/vexy-speakup/previews/b195beafa0e74846a95b2d9197dfa1a9/preview.json`

### Wider as a free offering

Wider costs nothing, but it is not open source. The Polyverse EULA (§1 and
§4.1) only covers copies obtained from Polyverse or an authorised reseller,
and forbids distributing the software "beyond what is needed for normal
installation and use". So it cannot go into `vexy-speakup-assets` the way the
GPL plugins do. Instead, the catalog marks it as a free vendor download: when
it is not installed, the GUI plugin list shows "not installed · free download
from the vendor" with a link to <https://polyversemusic.com/products/wider/>.
Once installed, `auto-gate-wider` appears automatically.

## Follow-up: a little StageOne Depth, and a mono source for StageOne

StageOne 2 stays optional: it is only in `auto-gate-stageone`, so you use it
by ticking that chain and skip it by leaving it out. `auto-gate` and every
other chain are unchanged.

### Changes

- **Depth 10** on the mid and high bands (low stays 0), on top of Mono Spread 100.
- **Mono fold before StageOne.** When the two channels are near-identical
  (side 60 dB or more below mid), the new built-in step `builtin:mono-fold`
  replaces them with exact mono, L = R = (L + R) / 2. StageOne then turns
  that mono signal into stereo with its own Mono Spread and Depth. Real
  stereo passes through unchanged.

### Why it is "exact L = R" and not a 1-channel signal

pedalboard 0.9.26 refuses to give StageOne 2 a 1-channel input:

```
Plugin 'StageOne2' does not support 1-channel output.
(Main bus currently expects 2 input channels and 2 output channels.)
```

On a 2-in/2-out bus, a mono source is L = R, and that is what a DAW sends
when you put a stereo plugin on a mono track. The fold guarantees StageOne
sees exactly that, even if earlier processing had left tiny differences
between the channels.

On this recording the channels were already bit-identical after dxRevive,
so the fold changes nothing here. It matters for recordings whose channels
differ very slightly, such as dual-mono files through a lossy codec.

### Measured, Brighter +3 dB, same 10-second clip

| Chain | Side/mid | L/R correlation | Mono sum vs `auto-gate` | RMS dBFS | Timing |
|---|---|---|---|---|---|
| `auto-gate` | none (mono) | 1.00 | — | −19.5 | — |
| `auto-gate-stageone` (Depth 10) | −17.1 dB | 0.96 | −31.4 dB | −19.5 | 0 samples |
| `auto-gate-wider` | −6.7 dB | 0.65 | −19.7 dB | −19.6 | 0 samples |

The −31 dB difference in the mono sum is the Depth reflections: quiet, but
present even in mono. Wider's own mono sum is unchanged; its −19.7 dB comes from the Ozone master
and loudness matching reacting to the wider signal. Per-plugin latencies (VoiceGate2 5120, dxRevive Pro
3993, StageOne2 2048 samples) are all compensated.

New listening session:
`~/Library/Caches/vexy-speakup/previews/9417653d33974441bbf007752a80f2c9/preview.json`
