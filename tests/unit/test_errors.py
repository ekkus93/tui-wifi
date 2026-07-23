"""Verify test errors behavior."""

from __future__ import annotations

from tests.assertions import verify
from tui_wifi.errors import ErrorCategory, WifiError


def test_every_error_has_friendly_summary() -> None:
    """Verify test every error has friendly summary."""
    for category in ErrorCategory:
        error = WifiError(category)
        verify(error.summary)
        verify(str(error) == error.summary)
        verify(category.value in error.diagnostic_text())


def test_diagnostics_include_structured_context() -> None:
    """Verify test diagnostics include structured context."""
    error = WifiError(
        ErrorCategory.COMMAND_FAILURE,
        technical_details="redacted stderr",
        exit_code=4,
        backend_reason="reason",
        operation="connect",
    )
    text = error.diagnostic_text()
    verify("operation=connect" in text)
    verify("exit_code=4" in text)
    verify("redacted stderr" in text)
