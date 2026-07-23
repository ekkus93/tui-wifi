"""Provide explicit test verification helpers."""

from __future__ import annotations


class VerificationError(AssertionError):
    """Represent a failed explicit test verification."""


def verify(value: object, *, message: object | None = None) -> None:
    """Raise a test failure when value is false."""
    if value:
        return
    raise VerificationError(message)
