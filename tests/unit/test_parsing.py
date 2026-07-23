"""Verify test parsing behavior."""

from __future__ import annotations

import pytest

from tests.assertions import verify
from tui_wifi.backends.parsing import (
    frequency_to_channel,
    parse_bool,
    parse_security,
    parse_signal,
    split_escaped,
    validate_uuid,
)
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import SecurityClass

_COMPARISON_VALUE_14 = 14
_COMPARISON_VALUE_36 = 36
_COMPARISON_VALUE_75 = 75
_COMPARISON_VALUE_5180 = 5180


def test_split_escaped_colon_and_backslash() -> None:
    """Verify test split escaped colon and backslash."""
    verify(
        split_escaped(r"Cafe\:West:path\\name::", 4)
        == [
            "Cafe:West",
            r"path\name",
            "",
            "",
        ],
    )


def test_split_escaped_rejects_dangling_escape() -> None:
    """Verify test split escaped rejects dangling escape."""
    with pytest.raises(WifiError) as caught:
        split_escaped("bad\\")
    verify(caught.value.category == ErrorCategory.PARSE_FAILURE)


def test_split_escaped_rejects_wrong_field_count() -> None:
    """Verify test split escaped rejects wrong field count."""
    with pytest.raises(WifiError):
        split_escaped("one:two", 3)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("yes", True), ("disabled", False), ("1", True), ("0", False)],
)
def test_parse_bool(raw: str, *, expected: bool) -> None:
    """Verify test parse bool."""
    verify(parse_bool(raw) is expected)


def test_parse_signal_validates_range() -> None:
    """Verify test parse signal validates range."""
    verify(parse_signal("") is None)
    verify(parse_signal("75") == _COMPARISON_VALUE_75)
    with pytest.raises(WifiError):
        parse_signal("101")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("--", SecurityClass.OPEN),
        ("WEP", SecurityClass.WEP),
        ("WPA1", SecurityClass.WPA_PERSONAL),
        ("WPA2", SecurityClass.WPA2_PERSONAL),
        ("WPA3 SAE", SecurityClass.WPA3_PERSONAL),
        ("WPA2 WPA3 SAE", SecurityClass.MIXED_PERSONAL),
        ("WPA2 802.1X", SecurityClass.ENTERPRISE),
        ("mystery", SecurityClass.UNKNOWN),
    ],
)
def test_security_classification(raw: str, expected: SecurityClass) -> None:
    """Verify test security classification."""
    verify(parse_security(raw) == expected)


def test_frequency_to_channel() -> None:
    """Verify test frequency to channel."""
    verify(frequency_to_channel(2412) == 1)
    verify(frequency_to_channel(2484) == _COMPARISON_VALUE_14)
    verify(frequency_to_channel(5180) == _COMPARISON_VALUE_36)
    verify(frequency_to_channel(5955) == 1)
    verify(frequency_to_channel(1234) is None)


def test_validate_uuid() -> None:
    """Verify test validate uuid."""
    value = "00000000-0000-0000-0000-000000000001"
    verify(validate_uuid(value) == value)
    with pytest.raises(WifiError):
        validate_uuid("not-a-uuid")


def test_additional_scalar_and_state_parsers() -> None:
    """Verify test additional scalar and state parsers."""
    from tui_wifi.backends.parsing import (
        parse_device_state,
        parse_ip_values,
        parse_nm_state,
        parse_optional_int,
    )
    from tui_wifi.models import DeviceState, NetworkManagerState

    verify(parse_optional_int("") is None)
    verify(parse_optional_int("5180") == _COMPARISON_VALUE_5180)
    verify(parse_device_state("connected") == DeviceState.ACTIVATED)
    verify(parse_device_state("future-state") == DeviceState.UNKNOWN)
    verify(parse_nm_state("connected (global)") == NetworkManagerState.CONNECTED_GLOBAL)
    verify(parse_nm_state("future-state") == NetworkManagerState.UNKNOWN)
    verify(
        parse_ip_values(["192.0.2.1/24", "", "2001:db8::1/64"])
        == (
            "192.0.2.1/24",
            "2001:db8::1/64",
        ),
    )
    with pytest.raises(WifiError):
        parse_optional_int("not-int")
    with pytest.raises(WifiError):
        parse_ip_values(["not-an-address"])
