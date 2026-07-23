"""Verify access-point grouping behavior."""

from __future__ import annotations

from tests.assertions import verify
from tui_wifi.grouping import group_networks
from tui_wifi.models import (
    AccessPoint,
    ActiveWifiConnection,
    DeviceState,
    SavedProfile,
    SecurityClass,
)

_EXPECTED_BSSID_COUNT = 2
_EXPECTED_STRONGEST_SIGNAL = 90


def ap(
    ssid: str,
    bssid: str,
    signal: int,
    security: SecurityClass,
    *,
    active: bool = False,
) -> AccessPoint:
    """Build one access point for grouping tests."""
    return AccessPoint(
        ssid=ssid.encode(),
        display_ssid=ssid,
        bssid=bssid,
        signal=signal,
        frequency=2412,
        channel=1,
        security=security,
        active=active,
        device="wlan0",
    )


def test_grouping_preserves_security_boundaries_and_sorting() -> None:
    """Verify grouping keeps security classes separate and sorts deterministically."""
    profile = SavedProfile(
        name="Home profile",
        uuid="00000000-0000-0000-0000-000000000001",
        ssid="Home",
        interface_name=None,
        autoconnect=True,
        security=SecurityClass.WPA2_PERSONAL,
    )
    active = ActiveWifiConnection(
        "Guest",
        "00000000-0000-0000-0000-000000000002",
        "Guest",
        "wlan0",
        DeviceState.ACTIVATED,
    )
    groups = group_networks(
        (
            ap("Home", "00:00:00:00:00:01", 40, SecurityClass.WPA2_PERSONAL),
            ap("Home", "00:00:00:00:00:02", 90, SecurityClass.WPA2_PERSONAL),
            ap("Home", "00:00:00:00:00:03", 80, SecurityClass.OPEN),
            ap("Guest", "00:00:00:00:00:04", 20, SecurityClass.OPEN, active=True),
            ap("Corp", "00:00:00:00:00:05", 99, SecurityClass.ENTERPRISE),
        ),
        (profile,),
        active,
    )
    verify([group.display_ssid for group in groups] == ["Guest", "Home", "Home", "Corp"])
    secured_home = next(
        group
        for group in groups
        if group.display_ssid == "Home"
        and group.security.supported
        and group.security != SecurityClass.OPEN
    )
    verify(secured_home.signal == _EXPECTED_STRONGEST_SIGNAL)
    verify(len(secured_home.member_bssids) == _EXPECTED_BSSID_COUNT)
    verify(secured_home.saved_profile_uuids == (profile.uuid,))
    verify(groups[-1].supported is False)
