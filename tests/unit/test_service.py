from __future__ import annotations

import asyncio

import pytest

from tui_wifi.backends.fake import FakeWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import AccessPoint, SecurityClass
from tui_wifi.secrets import SecretValue
from tui_wifi.services.wifi import WifiService


def sample_ap() -> AccessPoint:
    return AccessPoint(
        b"Home",
        "Home",
        "00:11:22:33:44:55",
        88,
        2412,
        1,
        SecurityClass.WPA2_PERSONAL,
        False,
        "wlan0",
    )


def test_startup_connect_disconnect_and_radio() -> None:
    async def scenario() -> None:
        backend = FakeWifiBackend()
        backend.access_points["wlan0"] = (sample_ap(),)
        service = WifiService(backend)
        snapshot = await service.startup()
        assert snapshot.selected_device == "wlan0"
        assert snapshot.networks[0].display_ssid == "Home"
        password = SecretValue("test-only-password")
        connected = await service.connect_network(snapshot.networks[0], password=password)
        assert connected.active_connection is not None
        assert password.reveal() == ""
        disconnected = await service.disconnect()
        assert disconnected.active_connection is None
        disabled = await service.set_wifi_enabled(False)
        assert disabled.status.wifi_radio.value == "disabled"

    asyncio.run(scenario())


def test_refresh_failure_preserves_last_valid_state() -> None:
    async def scenario() -> None:
        backend = FakeWifiBackend()
        backend.access_points["wlan0"] = (sample_ap(),)
        service = WifiService(backend)
        first = await service.startup()
        backend.failures["list_access_points"] = WifiError(ErrorCategory.COMMAND_FAILURE)
        second = await service.refresh()
        assert second.networks == first.networks
        assert second.stale is True
        assert second.error

    asyncio.run(scenario())


def test_explicit_missing_interface_is_visible() -> None:
    async def scenario() -> None:
        service = WifiService(FakeWifiBackend(), preferred_interface="missing0")
        snapshot = await service.startup()
        assert snapshot.error == "Wi-Fi interface 'missing0' is unavailable."

    asyncio.run(scenario())


def test_unsupported_connection_is_rejected_before_backend() -> None:
    async def scenario() -> None:
        backend = FakeWifiBackend()
        service = WifiService(backend)
        await service.startup()
        from tui_wifi.models import NetworkGroup

        group = NetworkGroup("corp", "Corp", SecurityClass.ENTERPRISE, 80, False, supported=False)
        with pytest.raises(WifiError) as caught:
            await service.connect_network(group)
        assert caught.value.category == ErrorCategory.UNSUPPORTED_SECURITY
        assert not any(call[0] == "connect_visible_network" for call in backend.calls)

    asyncio.run(scenario())


def test_fake_backend_saved_profile_workflows() -> None:
    async def scenario() -> None:
        from tui_wifi.backends.base import SavedProfileRequest
        from tui_wifi.models import SavedProfile

        backend = FakeWifiBackend()
        profile = SavedProfile(
            "Home",
            "00000000-0000-0000-0000-000000000099",
            "Home",
            None,
            True,
            SecurityClass.WPA2_PERSONAL,
        )
        backend.profiles = (profile,)
        active = await backend.activate_saved_profile(SavedProfileRequest(profile.uuid, "wlan0"))
        assert active.uuid == profile.uuid
        changed = await backend.set_profile_autoconnect(profile.uuid, False)
        assert changed.autoconnect is False
        await backend.delete_saved_profile(profile.uuid)
        assert backend.profiles == ()
        await backend.disconnect(
            __import__("tui_wifi.backends.base", fromlist=["DisconnectRequest"]).DisconnectRequest(
                "wlan0", active.uuid
            )
        )
        assert await backend.get_connection_details() is None

    asyncio.run(scenario())


def test_multiple_idle_adapters_require_explicit_selection() -> None:
    async def scenario() -> None:
        from tui_wifi.models import DeviceState, WifiDevice

        backend = FakeWifiBackend()
        backend.devices = (
            WifiDevice("wlan0", DeviceState.DISCONNECTED, True),
            WifiDevice("wlan1", DeviceState.DISCONNECTED, True),
        )
        snapshot = await WifiService(backend).startup()
        assert snapshot.error is not None
        assert "Multiple Wi-Fi adapters" in snapshot.error

    asyncio.run(scenario())
