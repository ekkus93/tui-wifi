# Copyright (c) 2026 Phillip Chin
"""Verify compatibility types shared across supported Python versions."""

from __future__ import annotations

from tests.assertions import verify
from tui_wifi.compat import StrEnum


class ExampleValue(StrEnum):
    """Provide one explicit string-enum value for compatibility testing."""

    VALUE = "value"


def test_string_enum_matches_required_string_behavior() -> None:
    """Verify equality, conversion, and formatting match normal strings."""
    verify(ExampleValue.VALUE == "value")
    verify(str(ExampleValue.VALUE) == "value")
    verify(f"{ExampleValue.VALUE:>7}" == "  value")
