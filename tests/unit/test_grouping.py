"""Verify test grouping behavior."""

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


def ap(
    ssid: str,
    bssid: str,
    signal: int,
    security: SecurityClass,
    *,
    active: bool = False,
) -> AccessPoint:
    """Perform ap."""
    return AccessPoint(ssid.encode(), ssid, bssid, signal, 2412, 1, security, active, "wlan0")


def test_grouping_preserves_security_boundaries_and_sorting() -> None:
    """Verify test grouping preserves security boundaries and sorting."""
    profile = SavedProfile(
        "Home profile",
        "00000000-0000-0000-0000-000000000001",
        "Home",
        None,
        True,
        SecurityClass.WPA2_PERSONAL,
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
    verify(secured_home.signal == 90)
    verify(len(secured_home.member_bssids) == 2)
    verify(secured_home.saved_profile_uuids == (profile.uuid,))
    verify(groups[-1].supported is False)
