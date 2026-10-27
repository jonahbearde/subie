"""Turning exceptions into the one line a user is allowed to see."""

from __future__ import annotations


class SubieError(Exception):
    """A failure whose message is meant for the user, with no stack trace."""


def one_line(exc: BaseException) -> str:
    """Collapse an exception's message to a single readable line."""
    message = " ".join(str(exc).split())
    return message or exc.__class__.__name__
