# Copyright (c) 2026 Phillip Chin
"""Provide fake functionality."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from tui_wifi.backends.base import (
    DisconnectRequest,
    HiddenConnectRequest,
    SavedProfileRequest,
    VisibleConnectRequest,
)
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import (
    AccessPoint,
    ActiveWifiConnection,
    BackendAvailability,
    BackendStatus,
    DeviceState,
    IPConfiguration,
    SavedProfile,
    WifiDevice,
    WifiRadioState,
)


class FakeWifiBackend:
    """Represent FakeWifiBackend."""

    def __init__(self) -> None:
        """Initialize the instance."""
        self.status = BackendStatus(
            BackendAvailability.AVAILABLE,
            wifi_radio=WifiRadioState.ENABLED,
        )
        self.radio = WifiRadioState.ENABLED
        self.devices: tuple[WifiDevice, ...] = (
            WifiDevice(
                interface="wlan0",
                state=DeviceState.DISCONNECTED,
                managed=True,
            ),
        )
        self.access_points: dict[str, tuple[AccessPoint, ...]] = defaultdict(tuple)
        self.profiles: tuple[SavedProfile, ...] = ()
        self.active: ActiveWifiConnection | None = None
        self.failures: dict[str, WifiError] = {}
        self.delays: dict[str, float] = {}
        self.calls: list[tuple[str, object | None]] = []

    async def _before(self, operation: str, payload: object | None = None) -> None:
        """Perform before."""
        self.calls.append((operation, payload))
        if delay := self.delays.get(operation):
            await asyncio.sleep(delay)
        if failure := self.failures.get(operation):
            raise failure

    async def check_status(self) -> BackendStatus:
        """Perform check status."""
        await self._before("check_status")
        return self.status

    async def get_wifi_radio_state(self) -> WifiRadioState:
        """Perform get wifi radio state."""
        await self._before("get_wifi_radio_state")
        return self.radio

    async def set_wifi_radio_state(self, *, enabled: bool) -> WifiRadioState:
        """Perform set wifi radio state."""
        await self._before("set_wifi_radio_state", enabled)
        self.radio = WifiRadioState.ENABLED if enabled else WifiRadioState.DISABLED
        self.status = BackendStatus(self.status.availability, wifi_radio=self.radio)
        if not enabled:
            self.active = None
        return self.radio

    async def list_wifi_devices(self) -> tuple[WifiDevice, ...]:
        """Perform list wifi devices."""
        await self._before("list_wifi_devices")
        return self.devices

    async def request_scan(self, interface: str) -> None:
        """Perform request scan."""
        await self._before("request_scan", interface)

    async def list_access_points(self, interface: str) -> tuple[AccessPoint, ...]:
        """Perform list access points."""
        await self._before("list_access_points", interface)
        return self.access_points[interface]

    async def get_active_wifi_connection(self) -> ActiveWifiConnection | None:
        """Perform get active wifi connection."""
        await self._before("get_active_wifi_connection")
        return self.active

    async def list_saved_wifi_profiles(self) -> tuple[SavedProfile, ...]:
        """Perform list saved wifi profiles."""
        await self._before("list_saved_wifi_profiles")
        return self.profiles

    async def activate_saved_profile(self, request: SavedProfileRequest) -> ActiveWifiConnection:
        """Perform activate saved profile."""
        await self._before("activate_saved_profile", request)
        profile = next((item for item in self.profiles if item.uuid == request.uuid), None)
        if profile is None:
            raise WifiError(ErrorCategory.NETWORK_UNAVAILABLE)
        self.active = ActiveWifiConnection(
            profile.name,
            profile.uuid,
            profile.ssid,
            request.interface,
            DeviceState.ACTIVATED,
            ipv4=IPConfiguration(("192.0.2.10/24",), "192.0.2.1", ("192.0.2.53",)),
        )
        return self.active

    async def connect_visible_network(self, request: VisibleConnectRequest) -> ActiveWifiConnection:
        """Perform connect visible network."""
        await self._before("connect_visible_network", request)
        if not request.security.supported:
            raise WifiError(ErrorCategory.UNSUPPORTED_SECURITY)
        uuid = "00000000-0000-0000-0000-000000000001"
        self.active = ActiveWifiConnection(
            request.ssid,
            uuid,
            request.ssid,
            request.interface,
            DeviceState.ACTIVATED,
            bssid=request.bssid,
            ipv4=IPConfiguration(("192.0.2.10/24",), "192.0.2.1", ("192.0.2.53",)),
        )
        return self.active

    async def connect_hidden_network(self, request: HiddenConnectRequest) -> ActiveWifiConnection:
        """Perform connect hidden network."""
        await self._before("connect_hidden_network", request)
        return await self.connect_visible_network(
            VisibleConnectRequest(
                request.ssid,
                request.interface,
                request.security,
                request.password,
                autoconnect=request.autoconnect,
            ),
        )

    async def disconnect(self, request: DisconnectRequest) -> None:
        """Perform disconnect."""
        await self._before("disconnect", request)
        if self.active is not None and self.active.device == request.interface:
            self.active = None

    async def delete_saved_profile(self, uuid: str) -> None:
        """Perform delete saved profile."""
        await self._before("delete_saved_profile", uuid)
        self.profiles = tuple(profile for profile in self.profiles if profile.uuid != uuid)

    async def set_profile_autoconnect(self, uuid: str, *, enabled: bool) -> SavedProfile:
        """Perform set profile autoconnect."""
        await self._before("set_profile_autoconnect", (uuid, enabled))
        updated: list[SavedProfile] = []
        result: SavedProfile | None = None
        for profile in self.profiles:
            if profile.uuid == uuid:
                result = SavedProfile(
                    profile.name,
                    profile.uuid,
                    profile.ssid,
                    profile.interface_name,
                    enabled,
                    profile.security,
                    profile.active,
                )
                updated.append(result)
            else:
                updated.append(profile)
        if result is None:
            raise WifiError(ErrorCategory.NETWORK_UNAVAILABLE)
        self.profiles = tuple(updated)
        return result

    async def get_connection_details(self) -> ActiveWifiConnection | None:
        """Perform get connection details."""
        await self._before("get_connection_details")
        return self.active
