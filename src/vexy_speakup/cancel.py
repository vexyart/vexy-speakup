# this_file: src/vexy_speakup/cancel.py
"""Cooperative cancellation shared by a GUI job and its isolated subprocess groups."""

from contextlib import contextmanager
from contextvars import ContextVar
from threading import Event

TOKEN = ContextVar("speakup_cancellation", default=None)


def check() -> None:
    token = TOKEN.get()
    if token is not None and token.is_set():
        raise InterruptedError("Processing cancelled; saved work remains available")


@contextmanager
def scope(event: Event | None):
    previous = TOKEN.set(event)
    try:
        yield
    finally:
        TOKEN.reset(previous)
