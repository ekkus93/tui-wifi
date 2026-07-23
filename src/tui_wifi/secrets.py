# Copyright (c) 2026 Phillip Chin
"""Provide secrets functionality."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

_REDACTED = "<redacted>"


@dataclass(slots=True)
class SecretValue:
    """Represent SecretValue."""

    _value: str

    def reveal(self) -> str:
        """Perform reveal."""
        return self._value

    def clear(self) -> None:
        """Perform clear."""
        self._value = ""

    def __str__(self) -> str:
        """Return the user-facing string representation."""
        return _REDACTED

    def __repr__(self) -> str:
        """Return the diagnostic representation."""
        return "SecretValue(<redacted>)"


def redact_arguments(args: Iterable[str], sensitive_indexes: frozenset[int]) -> tuple[str, ...]:
    """Perform redact arguments."""
    return tuple(
        _REDACTED if index in sensitive_indexes else value for index, value in enumerate(args)
    )


def redact_text(text: str, secrets: Iterable[str] = ()) -> str:
    """Perform redact text."""
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, _REDACTED)
    return re.sub(
        r"(?i)(password|psk|passwd)(\s*[:=]\s*|\s+)([^\s,;]+)",
        rf"\1\2{_REDACTED}",
        redacted,
    )
