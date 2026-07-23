"""Provide typed factories for deterministic tests."""

from __future__ import annotations

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


def access_point(
    *,
    ssid: str = "Home",
    bssid: str = DEFAULT_BSSID,
    signal: int | None = 80,
    frequency: int | None = 2412,
    channel: int | None = 1,
    security: SecurityClass = SecurityClass.WPA2_PERSONAL,
    active: bool = False,
    device: str = "wlan0",
) -> AccessPoint:
    """Build an access point with explicit overridable fields."""
    return AccessPoint(
        ssid=ssid.encode(),
        display_ssid=ssid,
        bssid=bssid,
        signal=signal,
        frequency=frequency,
        channel=channel,
        security=security,
        active=active,
        device=device,
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


def saved_profile(
    *,
    name: str = "Home profile",
    uuid: str = DEFAULT_UUID,
    ssid: str | None = "Home",
    interface_name: str | None = "wlan0",
    autoconnect: bool = True,
    security: SecurityClass = SecurityClass.WPA2_PERSONAL,
    active: bool = False,
) -> SavedProfile:
    """Build a saved Wi-Fi profile."""
    return SavedProfile(
        name=name,
        uuid=uuid,
        ssid=ssid,
        interface_name=interface_name,
        autoconnect=autoconnect,
        security=security,
        active=active,
    )


def active_connection(
    *,
    profile_name: str = "Home profile",
    uuid: str = DEFAULT_UUID,
    ssid: str | None = "Home",
    device: str = "wlan0",
    state: DeviceState = DeviceState.ACTIVATED,
    bssid: str | None = DEFAULT_BSSID,
    ipv4: IPConfiguration | None = None,
    ipv6: IPConfiguration | None = None,
) -> ActiveWifiConnection:
    """Build an active Wi-Fi connection."""
    return ActiveWifiConnection(
        profile_name=profile_name,
        uuid=uuid,
        ssid=ssid,
        device=device,
        state=state,
        bssid=bssid,
        ipv4=ipv4 or IPConfiguration(("192.0.2.10/24",), "192.0.2.1", ("192.0.2.53",)),
        ipv6=ipv6 or IPConfiguration(),
    )


def network_group(
    *,
    identity: str = "Home\0wpa2_personal",
    display_ssid: str = "Home",
    security: SecurityClass = SecurityClass.WPA2_PERSONAL,
    signal: int | None = 80,
    connected: bool = False,
    saved_profile_uuids: tuple[str, ...] = (),
    supported: bool = True,
    member_bssids: tuple[str, ...] = (DEFAULT_BSSID,),
) -> NetworkGroup:
    """Build a logical network group."""
    return NetworkGroup(
        identity=identity,
        display_ssid=display_ssid,
        security=security,
        signal=signal,
        connected=connected,
        saved_profile_uuids=saved_profile_uuids,
        supported=supported,
        member_bssids=member_bssids,
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


def application_snapshot(
    *,
    status: BackendStatus | None = None,
    devices: tuple[WifiDevice, ...] = (),
    selected_device: str | None = "wlan0",
    networks: tuple[NetworkGroup, ...] = (),
    profiles: tuple[SavedProfile, ...] = (),
    active: ActiveWifiConnection | None = None,
    operation: OperationStatus | None = None,
    warning: str | None = None,
    error: str | None = None,
    stale: bool = False,
    generation: int = 1,
) -> ApplicationSnapshot:
    """Build a coherent application snapshot for UI tests."""
    return ApplicationSnapshot(
        status=status or backend_status(),
        devices=devices,
        selected_device=selected_device,
        networks=networks,
        profiles=profiles,
        active_connection=active,
        operation=operation or OperationStatus(),
        warning=warning,
        error=error,
        stale=stale,
        generation=generation,
    )
