# Copyright (c) 2026 Phillip Chin
"""Provide compatibility types for supported Python versions."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """Provide the explicit-value string enum behavior used by tui-wifi."""

    def __str__(self) -> str:
        """Return the enum value as its user-facing string."""
        return str.__str__(self)

    def __format__(self, format_spec: str) -> str:
        """Format the enum value exactly like a normal string."""
        return str.__format__(self, format_spec)
