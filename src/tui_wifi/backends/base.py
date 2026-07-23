# Copyright (c) 2026 Phillip Chin
"""Provide base functionality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from tui_wifi.models import (
        AccessPoint,
        ActiveWifiConnection,
        BackendStatus,
        SavedProfile,
        SecurityClass,
        WifiDevice,
        WifiRadioState,
    )
    from tui_wifi.secrets import SecretValue


@dataclass(frozen=True, slots=True)
class VisibleConnectRequest:
    """Represent VisibleConnectRequest."""

    ssid: str
    interface: str
    security: SecurityClass
    password: SecretValue | None = None
    bssid: str | None = None
    autoconnect: bool = True


@dataclass(frozen=True, slots=True)
class HiddenConnectRequest:
    """Represent HiddenConnectRequest."""

    ssid: str
    interface: str
    security: SecurityClass
    password: SecretValue | None = None
    autoconnect: bool = True


@dataclass(frozen=True, slots=True)
class SavedProfileRequest:
    """Represent SavedProfileRequest."""

    uuid: str
    interface: str


@dataclass(frozen=True, slots=True)
class DisconnectRequest:
    """Represent DisconnectRequest."""

    interface: str
    active_uuid: str | None = None


class WifiBackend(Protocol):
    """Represent WifiBackend."""

    async def check_status(self) -> BackendStatus:
        """Perform check status."""
        ...

    async def get_wifi_radio_state(self) -> WifiRadioState:
        """Perform get wifi radio state."""
        ...

    async def set_wifi_radio_state(self, *, enabled: bool) -> WifiRadioState:
        """Perform set wifi radio state."""
        ...

    async def list_wifi_devices(self) -> tuple[WifiDevice, ...]:
        """Perform list wifi devices."""
        ...

    async def request_scan(self, interface: str) -> None:
        """Perform request scan."""
        ...

    async def list_access_points(self, interface: str) -> tuple[AccessPoint, ...]:
        """Perform list access points."""
        ...

    async def get_active_wifi_connection(self) -> ActiveWifiConnection | None:
        """Perform get active wifi connection."""
        ...

    async def list_saved_wifi_profiles(self) -> tuple[SavedProfile, ...]:
        """Perform list saved wifi profiles."""
        ...

    async def activate_saved_profile(
        self,
        request: SavedProfileRequest,
    ) -> ActiveWifiConnection:
        """Perform activate saved profile."""
        ...

    async def connect_visible_network(
        self,
        request: VisibleConnectRequest,
    ) -> ActiveWifiConnection:
        """Perform connect visible network."""
        ...

    async def connect_hidden_network(
        self,
        request: HiddenConnectRequest,
    ) -> ActiveWifiConnection:
        """Perform connect hidden network."""
        ...

    async def disconnect(self, request: DisconnectRequest) -> None:
        """Perform disconnect."""
        ...

    async def delete_saved_profile(self, uuid: str) -> None:
        """Perform delete saved profile."""
        ...

    async def set_profile_autoconnect(self, uuid: str, *, enabled: bool) -> SavedProfile:
        """Perform set profile autoconnect."""
        ...

    async def get_connection_details(self) -> ActiveWifiConnection | None:
        """Perform get connection details."""
        ...
