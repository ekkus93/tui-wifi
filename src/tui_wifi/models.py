from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class BackendAvailability(StrEnum):
    AVAILABLE = "available"
    MISSING_EXECUTABLE = "missing_executable"
    UNAVAILABLE = "unavailable"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN = "unknown"


class NetworkManagerState(StrEnum):
    CONNECTED_GLOBAL = "connected_global"
    CONNECTED_SITE = "connected_site"
    CONNECTED_LOCAL = "connected_local"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    ASLEEP = "asleep"
    UNKNOWN = "unknown"


class WifiRadioState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    HARDWARE_BLOCKED = "hardware_blocked"
    UNKNOWN = "unknown"


class DeviceState(StrEnum):
    UNKNOWN = "unknown"
    UNMANAGED = "unmanaged"
    UNAVAILABLE = "unavailable"
    DISCONNECTED = "disconnected"
    PREPARE = "prepare"
    CONFIG = "config"
    NEED_AUTH = "need_auth"
    IP_CONFIG = "ip_config"
    IP_CHECK = "ip_check"
    SECONDARIES = "secondaries"
    ACTIVATED = "activated"
    DEACTIVATING = "deactivating"
    FAILED = "failed"


class OperationKind(StrEnum):
    NONE = "none"
    REFRESH = "refresh"
    SCAN = "scan"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    RADIO = "radio"
    DELETE_PROFILE = "delete_profile"
    AUTOCONNECT = "autoconnect"


class OperationPhase(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SecurityClass(StrEnum):
    OPEN = "open"
    WEP = "wep"
    WPA_PERSONAL = "wpa_personal"
    WPA2_PERSONAL = "wpa2_personal"
    WPA3_PERSONAL = "wpa3_personal"
    MIXED_PERSONAL = "mixed_personal"
    ENTERPRISE = "enterprise"
    UNKNOWN = "unknown"

    @property
    def supported(self) -> bool:
        return self in {
            SecurityClass.OPEN,
            SecurityClass.WPA_PERSONAL,
            SecurityClass.WPA2_PERSONAL,
            SecurityClass.WPA3_PERSONAL,
            SecurityClass.MIXED_PERSONAL,
        }

    @property
    def requires_password(self) -> bool:
        return self not in {SecurityClass.OPEN, SecurityClass.UNKNOWN}


class SignalQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    WEAK = "weak"
    UNKNOWN = "unknown"

    @classmethod
    def from_percent(cls, value: int | None) -> SignalQuality:
        if value is None:
            return cls.UNKNOWN
        if value >= 75:
            return cls.EXCELLENT
        if value >= 50:
            return cls.GOOD
        if value >= 25:
            return cls.FAIR
        return cls.WEAK


@dataclass(frozen=True, slots=True)
class WifiDevice:
    interface: str
    state: DeviceState
    managed: bool
    hardware_address: str | None = None
    active_connection: str | None = None


@dataclass(frozen=True, slots=True)
class AccessPoint:
    ssid: bytes
    display_ssid: str
    bssid: str
    signal: int | None
    frequency: int | None
    channel: int | None
    security: SecurityClass
    active: bool
    device: str


@dataclass(frozen=True, slots=True)
class NetworkGroup:
    identity: str
    display_ssid: str
    security: SecurityClass
    signal: int | None
    connected: bool
    saved_profile_uuids: tuple[str, ...] = ()
    supported: bool = True
    member_bssids: tuple[str, ...] = ()

    @property
    def quality(self) -> SignalQuality:
        return SignalQuality.from_percent(self.signal)


@dataclass(frozen=True, slots=True)
class SavedProfile:
    name: str
    uuid: str
    ssid: str | None
    interface_name: str | None
    autoconnect: bool
    security: SecurityClass
    active: bool = False


@dataclass(frozen=True, slots=True)
class IPConfiguration:
    addresses: tuple[str, ...] = ()
    gateway: str | None = None
    dns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ActiveWifiConnection:
    profile_name: str
    uuid: str
    ssid: str | None
    device: str
    state: DeviceState
    bssid: str | None = None
    ipv4: IPConfiguration = field(default_factory=IPConfiguration)
    ipv6: IPConfiguration = field(default_factory=IPConfiguration)


@dataclass(frozen=True, slots=True)
class BackendStatus:
    availability: BackendAvailability
    network_manager_state: NetworkManagerState = NetworkManagerState.UNKNOWN
    wifi_radio: WifiRadioState = WifiRadioState.UNKNOWN
    nmcli_version: str | None = None
    network_manager_version: str | None = None
    technical_details: str | None = None


@dataclass(frozen=True, slots=True)
class OperationStatus:
    kind: OperationKind = OperationKind.NONE
    phase: OperationPhase = OperationPhase.IDLE
    target: str | None = None
    message: str | None = None
    operation_id: int = 0


@dataclass(frozen=True, slots=True)
class ApplicationSnapshot:
    status: BackendStatus
    devices: tuple[WifiDevice, ...] = ()
    selected_device: str | None = None
    networks: tuple[NetworkGroup, ...] = ()
    profiles: tuple[SavedProfile, ...] = ()
    active_connection: ActiveWifiConnection | None = None
    operation: OperationStatus = field(default_factory=OperationStatus)
    last_refresh: datetime = field(default_factory=lambda: datetime.now(UTC))
    warning: str | None = None
    error: str | None = None
    stale: bool = False
    generation: int = 0
