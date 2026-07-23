# Copyright (c) 2026 Phillip Chin
"""Provide typed factories for deterministic tests."""

from __future__ import annotations

from typing import TypedDict, Unpack

from tui_wifi.models import (
    AccessPoint,
    ActiveWifiConnection,
    ApplicationSnapshot,
    BackendAvailability,
    BackendStatus,
    DeviceState,
    IPConfiguration,
    NetworkGroup,
    NetworkManagerState,
    OperationStatus,
    SavedProfile,
    SecurityClass,
    WifiDevice,
    WifiRadioState,
)

DEFAULT_UUID = "00000000-0000-0000-0000-000000000001"
DEFAULT_BSSID = "00:11:22:33:44:55"


class AccessPointOptions(TypedDict, total=False):
    """Describe optional access-point factory values."""

    ssid: str
    bssid: str
    signal: int | None
    frequency: int | None
    channel: int | None
    security: SecurityClass
    active: bool
    device: str


class SavedProfileOptions(TypedDict, total=False):
    """Describe optional saved-profile factory values."""

    name: str
    uuid: str
    ssid: str | None
    interface_name: str | None
    autoconnect: bool
    security: SecurityClass
    active: bool


class ActiveConnectionOptions(TypedDict, total=False):
    """Describe optional active-connection factory values."""

    profile_name: str
    uuid: str
    ssid: str | None
    device: str
    state: DeviceState
    bssid: str | None
    ipv4: IPConfiguration | None
    ipv6: IPConfiguration | None


class NetworkGroupOptions(TypedDict, total=False):
    """Describe optional network-group factory values."""

    identity: str
    display_ssid: str
    security: SecurityClass
    signal: int | None
    connected: bool
    saved_profile_uuids: tuple[str, ...]
    supported: bool
    member_bssids: tuple[str, ...]


class ApplicationSnapshotOptions(TypedDict, total=False):
    """Describe optional application-snapshot factory values."""

    status: BackendStatus | None
    devices: tuple[WifiDevice, ...]
    selected_device: str | None
    networks: tuple[NetworkGroup, ...]
    profiles: tuple[SavedProfile, ...]
    active: ActiveWifiConnection | None
    operation: OperationStatus | None
    warning: str | None
    error: str | None
    stale: bool
    generation: int


def access_point(**options: Unpack[AccessPointOptions]) -> AccessPoint:
    """Build an access point with explicit overridable fields."""
    ssid = options.get("ssid", "Home")
    return AccessPoint(
        ssid=ssid.encode(),
        display_ssid=ssid,
        bssid=options.get("bssid", DEFAULT_BSSID),
        signal=options.get("signal", 80),
        frequency=options.get("frequency", 2412),
        channel=options.get("channel", 1),
        security=options.get("security", SecurityClass.WPA2_PERSONAL),
        active=options.get("active", False),
        device=options.get("device", "wlan0"),
    )


def wifi_device(
    *,
    interface: str = "wlan0",
    state: DeviceState = DeviceState.DISCONNECTED,
    managed: bool = True,
    active_connection: str | None = None,
) -> WifiDevice:
    """Build a Wi-Fi device."""
    return WifiDevice(
        interface=interface,
        state=state,
        managed=managed,
        active_connection=active_connection,
    )


def saved_profile(**options: Unpack[SavedProfileOptions]) -> SavedProfile:
    """Build a saved Wi-Fi profile."""
    return SavedProfile(
        name=options.get("name", "Home profile"),
        uuid=options.get("uuid", DEFAULT_UUID),
        ssid=options.get("ssid", "Home"),
        interface_name=options.get("interface_name", "wlan0"),
        autoconnect=options.get("autoconnect", True),
        security=options.get("security", SecurityClass.WPA2_PERSONAL),
        active=options.get("active", False),
    )


def active_connection(**options: Unpack[ActiveConnectionOptions]) -> ActiveWifiConnection:
    """Build an active Wi-Fi connection."""
    ipv4 = options.get("ipv4")
    ipv6 = options.get("ipv6")
    return ActiveWifiConnection(
        profile_name=options.get("profile_name", "Home profile"),
        uuid=options.get("uuid", DEFAULT_UUID),
        ssid=options.get("ssid", "Home"),
        device=options.get("device", "wlan0"),
        state=options.get("state", DeviceState.ACTIVATED),
        bssid=options.get("bssid", DEFAULT_BSSID),
        ipv4=(
            ipv4
            if ipv4 is not None
            else IPConfiguration(("192.0.2.10/24",), "192.0.2.1", ("192.0.2.53",))
        ),
        ipv6=ipv6 if ipv6 is not None else IPConfiguration(),
    )


def network_group(**options: Unpack[NetworkGroupOptions]) -> NetworkGroup:
    """Build a logical network group."""
    return NetworkGroup(
        identity=options.get("identity", "Home\0wpa2_personal"),
        display_ssid=options.get("display_ssid", "Home"),
        security=options.get("security", SecurityClass.WPA2_PERSONAL),
        signal=options.get("signal", 80),
        connected=options.get("connected", False),
        saved_profile_uuids=options.get("saved_profile_uuids", ()),
        supported=options.get("supported", True),
        member_bssids=options.get("member_bssids", (DEFAULT_BSSID,)),
    )


def backend_status(
    *,
    availability: BackendAvailability = BackendAvailability.AVAILABLE,
    network_manager_state: NetworkManagerState = NetworkManagerState.CONNECTED_GLOBAL,
    wifi_radio: WifiRadioState = WifiRadioState.ENABLED,
    nmcli_version: str | None = "nmcli tool, version 1.50",
) -> BackendStatus:
    """Build a backend status value."""
    return BackendStatus(
        availability=availability,
        network_manager_state=network_manager_state,
        wifi_radio=wifi_radio,
        nmcli_version=nmcli_version,
    )


def application_snapshot(**options: Unpack[ApplicationSnapshotOptions]) -> ApplicationSnapshot:
    """Build a coherent application snapshot for UI tests."""
    status = options.get("status")
    operation = options.get("operation")
    return ApplicationSnapshot(
        status=status if status is not None else backend_status(),
        devices=options.get("devices", ()),
        selected_device=options.get("selected_device", "wlan0"),
        networks=options.get("networks", ()),
        profiles=options.get("profiles", ()),
        active_connection=options.get("active"),
        operation=operation if operation is not None else OperationStatus(),
        warning=options.get("warning"),
        error=options.get("error"),
        stale=options.get("stale", False),
        generation=options.get("generation", 1),
    )
