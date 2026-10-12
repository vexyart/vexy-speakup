# this_file: src/vexy_speakup/__init__.py
"""Diarize, restore, level and master recorded speech, retaining the video timeline."""

try:
    from .__version__ import __version__
except ImportError:  # Source checkout without a build: ask installed metadata.
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("vexy-speakup")
    except PackageNotFoundError:
        __version__ = "0.0.0"
