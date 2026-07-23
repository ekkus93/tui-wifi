# Copyright (c) 2026 Phillip Chin
"""Verify the remaining Wi-Fi service decision branches."""

from __future__ import annotations

import asyncio
import sys

import pytest

from tests.assertions import verify
from tests.factories import (
    DEFAULT_BSSID,
    DEFAULT_UUID,
    access_point,
    network_group,
    saved_profile,
    wifi_device,
)
from tui_wifi.backends.fake import FakeWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import (
    BackendAvailability,
    BackendStatus,
    DeviceState,
    OperationPhase,
    SecurityClass,
)
from tui_wifi.services.wifi import WifiService


@pytest.mark.parametrize(
    ("availability", "expected_error"),
    [
        (BackendAvailability.MISSING_EXECUTABLE, "nmcli utility"),
        (BackendAvailability.UNAUTHORIZED, "denied"),
        (BackendAvailability.UNAVAILABLE, "NetworkManager is not available"),
    ],
)
def test_backend_status_translation_is_explicit(
    availability: BackendAvailability,
    expected_error: str,
) -> None:
    """Verify each unavailable backend status maps to its stable service error."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        backend.status = BackendStatus(availability)
        snapshot = await WifiService(backend).refresh()
        verify(snapshot.error is not None)
        verify(expected_error in snapshot.error)
        verify(snapshot.operation.phase == OperationPhase.FAILED)

    asyncio.run(scenario())


def test_non_linux_startup_stops_before_backend_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the platform guard is visible and avoids backend access."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        service = WifiService(backend)
        monkeypatch.setattr(sys, "platform", "darwin")
        snapshot = await service.startup()
        verify(snapshot.error == "tui-wifi currently supports Linux only.")
        verify(backend.calls == [])

    asyncio.run(scenario())


def test_subscription_snapshot_and_idempotent_unsubscribe() -> None:
    """Verify listeners use a stable publication snapshot and unsubscribe safely."""
    backend = FakeWifiBackend()
    service = WifiService(backend)
    first: list[int] = []
    second: list[int] = []

    def no_op_unsubscribe() -> None:
        """Provide the initial unsubscribe placeholder."""

    unsubscribe_first = no_op_unsubscribe

    def first_listener(_snapshot: object) -> None:
        first.append(service.snapshot.generation)
        unsubscribe_first()

    unsubscribe_first = service.subscribe(first_listener)
    unsubscribe_second = service.subscribe(
        lambda _snapshot: second.append(service.snapshot.generation)
    )
    service.publish(service.snapshot)
    service.publish(service.snapshot)
    unsubscribe_first()
    unsubscribe_second()
    unsubscribe_second()
    verify(first == [0])
    verify(second == [0, 0])


def test_scan_request_failure_is_warning_and_listing_continues() -> None:
    """Verify scan request failure remains a warning when listing succeeds."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        backend.access_points["wlan0"] = (access_point(),)
        backend.failures["request_scan"] = WifiError(
            ErrorCategory.COMMAND_FAILURE,
            summary="Synthetic scan failure.",
        )
        snapshot = await WifiService(backend).refresh(request_scan=True)
        verify(snapshot.warning == "Scan request failed: Synthetic scan failure.")
        verify(snapshot.operation.phase == OperationPhase.SUCCEEDED)
        verify(len(snapshot.networks) == 1)
        verify(any(name == "list_access_points" for name, _payload in backend.calls))

    asyncio.run(scenario())


def test_adapter_selection_prefers_requested_and_active_devices() -> None:
    """Verify explicit and activated adapters win without arbitrary fallback."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        backend.devices = (
            wifi_device(interface="wlan0"),
            wifi_device(interface="wlan1", state=DeviceState.ACTIVATED),
        )
        automatic = await WifiService(backend).refresh()
        verify(automatic.selected_device == "wlan1")

        preferred = await WifiService(backend, preferred_interface="wlan0").refresh()
        verify(preferred.selected_device == "wlan0")

    asyncio.run(scenario())


def test_no_managed_adapter_skips_access_point_listing() -> None:
    """Verify unmanaged-only device lists do not invent a selected adapter."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        backend.devices = (wifi_device(managed=False, state=DeviceState.UNMANAGED),)
        snapshot = await WifiService(backend).refresh(request_scan=True)
        verify(snapshot.selected_device is None)
        verify(not any(name == "request_scan" for name, _payload in backend.calls))
        verify(not any(name == "list_access_points" for name, _payload in backend.calls))

    asyncio.run(scenario())


def test_saved_profile_connection_uses_activation_path() -> None:
    """Verify one unambiguous saved UUID is activated without creating a profile."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        profile = saved_profile()
        backend.profiles = (profile,)
        service = WifiService(backend)
        await service.refresh()
        backend.calls.clear()
        group = network_group(saved_profile_uuids=(profile.uuid,))
        await service.connect_network(group)
        names = [name for name, _payload in backend.calls]
        verify("activate_saved_profile" in names)
        verify("connect_visible_network" not in names)

    asyncio.run(scenario())


@pytest.mark.parametrize("bssid_mode", ["single", "multiple", "missing"])
def test_visible_connection_bssid_policy_is_conservative(bssid_mode: str) -> None:
    """Verify only one unambiguous BSSID is forwarded to the backend."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        service = WifiService(backend)
        await service.refresh()
        backend.calls.clear()
        members = {
            "single": (DEFAULT_BSSID,),
            "multiple": (DEFAULT_BSSID, "00:11:22:33:44:66"),
            "missing": (),
        }[bssid_mode]
        await service.connect_network(
            network_group(member_bssids=members),
            password=None,
        )
        request = next(
            payload for name, payload in backend.calls if name == "connect_visible_network"
        )
        expected = DEFAULT_BSSID if bssid_mode == "single" else None
        verify(request.bssid == expected)

    asyncio.run(scenario())


def test_disconnect_without_active_connection_is_noop() -> None:
    """Verify an already-disconnected service does not call the backend."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        service = WifiService(backend)
        await service.refresh()
        backend.calls.clear()
        before = service.snapshot
        after = await service.disconnect()
        verify(after is before)
        verify(not any(name == "disconnect" for name, _payload in backend.calls))

    asyncio.run(scenario())


def test_missing_interface_blocks_hidden_connection_before_backend() -> None:
    """Verify hidden connections require an explicitly selected adapter."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        service = WifiService(backend)
        with pytest.raises(WifiError) as caught:
            await service.connect_hidden(
                "Hidden",
                SecurityClass.OPEN,
                None,
                autoconnect=True,
            )
        verify(caught.value.category == ErrorCategory.NO_ADAPTER)
        verify(not any(name == "connect_hidden_network" for name, _payload in backend.calls))

    asyncio.run(scenario())


def test_profile_lookup_returns_match_or_none() -> None:
    """Verify saved-profile lookup covers matching and missing UUIDs."""
    service = WifiService(FakeWifiBackend())
    profile = saved_profile(uuid=DEFAULT_UUID)
    service.publish(service.snapshot.__class__(service.snapshot.status, profiles=(profile,)))
    verify(service.profile_by_uuid(DEFAULT_UUID) is profile)
    verify(service.profile_by_uuid("00000000-0000-0000-0000-000000000099") is None)
