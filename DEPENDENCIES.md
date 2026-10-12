<!-- this_file: DEPENDENCIES.md -->
# Dependencies

Fire (CLI, matching vexy-subs), NumPy (sample buffers, gains and fades),
Pedalboard 0.9.26 (VST3 hosting with latency compensation; pinned because the
plugin rendering was verified with this exact wheel), SoundFile (float/RF64 WAV
streaming), pyloudnorm (BS.1770 speaker and fragment loudness).

FFmpeg/ffprobe are external executables for decoding, R128 levelling, encoding
and video remuxing. Diarization, DeepFilterNet and DNSMOS/UTMOS scoring use
existing local adapters in their own uv environments; they are not package
dependencies. Commercial VST3 plugins are user-installed and not distributed.

Build: hatchling with hatch-vcs (version from git tags).
Tests/build: pytest, pytest-cov, ruff, build and twine.
