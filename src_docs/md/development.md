# Development

## Set up

1. Clone the repository:

    ```bash
    git clone https://github.com/vexyart/vexy-speakup.git
    cd vexy-speakup
    ```

2. Run the tests. uv creates the environment with the `test` extra:

    ```bash
    ./test.sh
    ```

    `test.sh` runs `pytest` with coverage of `vexy_speakup`, then `ruff check` on
    `src` and `tests`.

The functional tests encode real audio and video with FFmpeg, so `ffmpeg` and
`ffprobe` must be on `PATH`. Tests that need licensed plugins or the local model
adapters cannot run without them.

## Source layout

| Module | Responsibility |
| --- | --- |
| `cli.py` | the Fire commands, argument checks and the `run` pipeline |
| `media.py` | FFmpeg decoding, loudness measurement, encoding and atomic publication |
| `models.py` | diarization, DeepFilterNet and scoring through local adapters |
| `turns.py` | turn validation and timeline partitioning |
| `levels.py` | BS.1770 loudness and bounded gain |
| `pipeline.py` | fragment extraction, speaker rendering, levelling, assembly and mastering |
| `vst.py` | built-in profiles, chain loading and VST rendering |
| `audit.py` | `inspect`, `probe`, `inventory`, `attempts` and evaluation windows |
| `locations.py` | plugin and adapter folders from environment variables |

Plugin rendering runs in child processes started as
`python -m vexy_speakup _render` and `python -m vexy_speakup _master`. These
internal commands read a job JSON file and are not meant to be called by hand.

## Build

```bash
./build.sh            # documentation and package
./build.sh docs       # documentation only
./build.sh package    # package only
```

The package step removes `dist/`, runs `uv build` and checks the result with
`twine check`. The version comes from the git tag through hatch-vcs and is
written to `src/vexy_speakup/__version__.py`, which git ignores. An untagged
commit builds a development version, which PyPI does not accept.

## Documentation

The documentation source is in `src_docs/md/`, and `src_docs/mkdocs.yml`
configures ProperDocs with the MaterialX theme. Build it with:

```bash
src_docs/build.sh          # strict build into docs/
src_docs/build.sh serve    # live preview on http://127.0.0.1:8000
```

The site is built into `docs/`, which GitHub Pages serves at
<https://vexy.dev/vexy-speakup/>. A push to `main` that changes `src_docs/`
rebuilds `docs/` through the `Docs` workflow.

## Release

```bash
./publish.sh
```

`publish.sh` runs `uvx gitnextver`, which commits pending changes, creates the
next `vX.Y.Z` tag and pushes. It stops if `HEAD` then carries no such tag. It
then builds the package from that tag and uploads it with `uv publish`. A
credential such as `UV_PUBLISH_TOKEN` must be set.

Run `./test.sh` before you publish; `publish.sh` does not run the tests.
