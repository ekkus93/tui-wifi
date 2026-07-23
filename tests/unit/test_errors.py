from __future__ import annotations

from tui_wifi.errors import ErrorCategory, WifiError


def test_every_error_has_friendly_summary() -> None:
    for category in ErrorCategory:
        error = WifiError(category)
        assert error.summary
        assert str(error) == error.summary
        assert category.value in error.diagnostic_text()


def test_diagnostics_include_structured_context() -> None:
    error = WifiError(
        ErrorCategory.COMMAND_FAILURE,
        technical_details="redacted stderr",
        exit_code=4,
        backend_reason="reason",
        operation="connect",
    )
    text = error.diagnostic_text()
    assert "operation=connect" in text
    assert "exit_code=4" in text
    assert "redacted stderr" in text
