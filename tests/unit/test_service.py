"""Verify Wi-Fi service behavior."""

from __future__ import annotations

import asyncio

import pytest

from tests.assertions import verify
from tui_wifi.backends.base import DisconnectRequest, SavedProfileRequest
from tui_wifi.backends.fake import FakeWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import (
    AccessPoint,
    DeviceState,
    NetworkGroup,
    SavedProfile,
    SecurityClass,
    WifiDevice,
)
from tui_wifi.secrets import SecretValue
from tui_wifi.services.wifi import WifiService


def sample_ap() -> AccessPoint:
    """Return a representative secured access point."""
    return AccessPoint(
        ssid=b"Home",
        display_ssid="Home",
        bssid="00:11:22:33:44:55",
        signal=88,
        frequency=2412,
        channel=1,
        security=SecurityClass.WPA2_PERSONAL,
        active=False,
        device="wlan0",
    )


def test_startup_connect_disconnect_and_radio() -> None:
    """Verify the primary startup, connection, and radio workflow."""

    async def scenario() -> None:
        """Run the asynchronous service workflow."""
        backend = FakeWifiBackend()
        backend.access_points["wlan0"] = (sample_ap(),)
        service = WifiService(backend)
        snapshot = await service.startup()
        verify(snapshot.selected_device == "wlan0")
        verify(snapshot.networks[0].display_ssid == "Home")
        password = SecretValue("test-only-password")
        connected = await service.connect_network(snapshot.networks[0], password=password)
        verify(connected.active_connection is not None)
        verify(password.reveal() == "")
        disconnected = await service.disconnect()
        verify(disconnected.active_connection is None)
        disabled = await service.set_wifi_enabled(enabled=False)
        verify(disabled.status.wifi_radio.value == "disabled")

    asyncio.run(scenario())


def test_refresh_failure_preserves_last_valid_state() -> None:
    """Verify failed refreshes preserve the last coherent state."""

    async def scenario() -> None:
        """Run a refresh that fails after a valid startup."""
        backend = FakeWifiBackend()
        backend.access_points["wlan0"] = (sample_ap(),)
        service = WifiService(backend)
        first = await service.startup()
        backend.failures["list_access_points"] = WifiError(ErrorCategory.COMMAND_FAILURE)
        second = await service.refresh()
        verify(second.networks == first.networks)
        verify(second.stale is True)
        verify(second.error)

    asyncio.run(scenario())


def test_explicit_missing_interface_is_visible() -> None:
    """Verify a requested missing interface produces a visible error."""

    async def scenario() -> None:
        """Start a service with an unavailable preferred interface."""
        service = WifiService(FakeWifiBackend(), preferred_interface="missing0")
        snapshot = await service.startup()
        verify(snapshot.error == "Wi-Fi interface 'missing0' is unavailable.")

    asyncio.run(scenario())


def test_unsupported_connection_is_rejected_before_backend() -> None:
    """Verify unsupported security never reaches the backend."""

    async def scenario() -> None:
        """Attempt an unsupported enterprise connection."""
        backend = FakeWifiBackend()
        service = WifiService(backend)
        await service.startup()
        group = NetworkGroup(
            identity="corp",
            display_ssid="Corp",
            security=SecurityClass.ENTERPRISE,
            signal=80,
            connected=False,
            supported=False,
        )
        with pytest.raises(WifiError) as caught:
            await service.connect_network(group)
        verify(caught.value.category == ErrorCategory.UNSUPPORTED_SECURITY)
        verify(not any(call[0] == "connect_visible_network" for call in backend.calls))

    asyncio.run(scenario())


def test_fake_backend_saved_profile_workflows() -> None:
    """Verify saved-profile activation, update, deletion, and disconnect."""

    async def scenario() -> None:
        """Run saved-profile operations against the fake backend."""
        backend = FakeWifiBackend()
        profile = SavedProfile(
            name="Home",
            uuid="00000000-0000-0000-0000-000000000099",
            ssid="Home",
            interface_name=None,
            autoconnect=True,
            security=SecurityClass.WPA2_PERSONAL,
        )
        backend.profiles = (profile,)
        active = await backend.activate_saved_profile(
            SavedProfileRequest(profile.uuid, "wlan0"),
        )
        verify(active.uuid == profile.uuid)
        changed = await backend.set_profile_autoconnect(profile.uuid, enabled=False)
        verify(changed.autoconnect is False)
        await backend.delete_saved_profile(profile.uuid)
        verify(backend.profiles == ())
        await backend.disconnect(DisconnectRequest("wlan0", active.uuid))
        verify(await backend.get_connection_details() is None)

    asyncio.run(scenario())


def test_multiple_idle_adapters_require_explicit_selection() -> None:
    """Verify multiple idle adapters require an explicit interface choice."""

    async def scenario() -> None:
        """Start with two managed disconnected adapters."""
        backend = FakeWifiBackend()
        backend.devices = (
            WifiDevice(interface="wlan0", state=DeviceState.DISCONNECTED, managed=True),
            WifiDevice(interface="wlan1", state=DeviceState.DISCONNECTED, managed=True),
        )
        snapshot = await WifiService(backend).startup()
        verify(snapshot.error is not None)
        verify("Multiple Wi-Fi adapters" in snapshot.error)

    asyncio.run(scenario())
