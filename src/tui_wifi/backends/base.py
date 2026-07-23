from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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
    ssid: str
    interface: str
    security: SecurityClass
    password: SecretValue | None = None
    bssid: str | None = None
    autoconnect: bool = True


@dataclass(frozen=True, slots=True)
class HiddenConnectRequest:
    ssid: str
    interface: str
    security: SecurityClass
    password: SecretValue | None = None
    autoconnect: bool = True


@dataclass(frozen=True, slots=True)
class SavedProfileRequest:
    uuid: str
    interface: str


@dataclass(frozen=True, slots=True)
class DisconnectRequest:
    interface: str
    active_uuid: str | None = None


class WifiBackend(Protocol):
    async def check_status(self) -> BackendStatus: ...
    async def get_wifi_radio_state(self) -> WifiRadioState: ...
    async def set_wifi_radio_state(self, enabled: bool) -> WifiRadioState: ...
    async def list_wifi_devices(self) -> tuple[WifiDevice, ...]: ...
    async def request_scan(self, interface: str) -> None: ...
    async def list_access_points(self, interface: str) -> tuple[AccessPoint, ...]: ...
    async def get_active_wifi_connection(self) -> ActiveWifiConnection | None: ...
    async def list_saved_wifi_profiles(self) -> tuple[SavedProfile, ...]: ...
    async def activate_saved_profile(
        self, request: SavedProfileRequest
    ) -> ActiveWifiConnection: ...
    async def connect_visible_network(
        self, request: VisibleConnectRequest
    ) -> ActiveWifiConnection: ...
    async def connect_hidden_network(
        self, request: HiddenConnectRequest
    ) -> ActiveWifiConnection: ...
    async def disconnect(self, request: DisconnectRequest) -> None: ...
    async def delete_saved_profile(self, uuid: str) -> None: ...
    async def set_profile_autoconnect(self, uuid: str, enabled: bool) -> SavedProfile: ...
    async def get_connection_details(self) -> ActiveWifiConnection | None: ...
