# Copyright (c) 2026 Phillip Chin
"""Provide nmcli profiles functionality."""

from __future__ import annotations

from collections import defaultdict

from tui_wifi.backends.nmcli_core import NmcliCore
from tui_wifi.backends.parsing import parse_bool, split_escaped, validate_uuid
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import (
    ActiveWifiConnection,
    DeviceState,
    IPConfiguration,
    SavedProfile,
    SecurityClass,
)

_COMPARISON_VALUE_2 = 2
_COMPARISON_VALUE_3 = 3


class NmcliProfilesMixin(NmcliCore):
    """Represent NmcliProfilesMixin."""

    async def list_saved_wifi_profiles(self) -> tuple[SavedProfile, ...]:
        """Perform list saved wifi profiles."""
        output = await self._run(
            (
                "-t",
                "-e",
                "yes",
                "-f",
                "NAME,UUID,TYPE,DEVICE,AUTOCONNECT",
                "connection",
                "show",
            ),
            timeout_seconds=self.QUERY_TIMEOUT,
        )
        rows = tuple(line for line in output.splitlines() if line)
        if len(rows) > self.PROFILE_DETAIL_LIMIT:
            raise WifiError(
                ErrorCategory.COMMAND_FAILURE,
                summary="Too many saved connection profiles were returned.",
                technical_details=(
                    f"profile count {len(rows)} exceeds bounded detail-query limit "
                    f"{self.PROFILE_DETAIL_LIMIT}"
                ),
            )
        profiles: list[SavedProfile] = []
        for line in rows:
            name, uuid, connection_type, device, autoconnect = split_escaped(line, 5)
            if connection_type not in {"wifi", "802-11-wireless"}:
                continue
            valid_uuid = validate_uuid(uuid)
            detail = await self._run(
                (
                    "-t",
                    "-e",
                    "yes",
                    "-g",
                    (
                        "802-11-wireless.ssid,802-11-wireless-security.key-mgmt,"
                        "connection.interface-name,connection.autoconnect"
                    ),
                    "connection",
                    "show",
                    "uuid",
                    valid_uuid,
                ),
                timeout_seconds=self.QUERY_TIMEOUT,
            )
            detail_lines = detail.splitlines()
            ssid = detail_lines[0] if detail_lines and detail_lines[0] else None
            key_mgmt = detail_lines[1] if len(detail_lines) > 1 else ""
            interface_name = detail_lines[2] if len(detail_lines) > _COMPARISON_VALUE_2 else ""
            detail_autoconnect = (
                detail_lines[3] if len(detail_lines) > _COMPARISON_VALUE_3 else autoconnect
            )
            profiles.append(
                SavedProfile(
                    name=name,
                    uuid=valid_uuid,
                    ssid=ssid,
                    interface_name=interface_name or None,
                    autoconnect=parse_bool(detail_autoconnect),
                    security=self.profile_security(key_mgmt),
                    active=device not in {"", "--"},
                ),
            )
        return tuple(profiles)

    @staticmethod
    def profile_security(key_mgmt: str) -> SecurityClass:
        """Perform profile security."""
        normalized = key_mgmt.strip().lower()
        if not normalized or normalized == "none":
            return SecurityClass.OPEN
        if "wpa-eap" in normalized or "ieee8021x" in normalized:
            return SecurityClass.ENTERPRISE
        if "sae" in normalized and "wpa-psk" in normalized:
            return SecurityClass.MIXED_PERSONAL
        if "sae" in normalized:
            return SecurityClass.WPA3_PERSONAL
        if "wpa-psk" in normalized:
            return SecurityClass.WPA2_PERSONAL
        return SecurityClass.UNKNOWN

    async def get_active_wifi_connection(self) -> ActiveWifiConnection | None:
        """Perform get active wifi connection."""
        devices = await self.list_wifi_devices()
        active_device = next(
            (device for device in devices if device.state == DeviceState.ACTIVATED),
            None,
        )
        if active_device is None:
            return None
        detail_output = await self._run(
            (
                "-t",
                "-e",
                "yes",
                "-f",
                (
                    "GENERAL.CONNECTION,GENERAL.CON-UUID,GENERAL.STATE,"
                    "IP4.ADDRESS,IP4.GATEWAY,IP4.DNS,"
                    "IP6.ADDRESS,IP6.GATEWAY,IP6.DNS"
                ),
                "device",
                "show",
                active_device.interface,
            ),
            timeout_seconds=self.QUERY_TIMEOUT,
        )
        values: dict[str, list[str]] = defaultdict(list)
        for line in detail_output.splitlines():
            if not line:
                continue
            key, value = split_escaped(line, 2)
            values[key].append(value)
        profile_name = (
            self._first(values, "GENERAL.CONNECTION") or active_device.active_connection or ""
        )
        uuid = self._first(values, "GENERAL.CON-UUID") or ""
        if not uuid:
            raise WifiError(
                ErrorCategory.PARSE_FAILURE,
                technical_details="active Wi-Fi device did not expose GENERAL.CON-UUID",
            )
        valid_uuid = validate_uuid(uuid)
        ssid_output = await self._run(
            (
                "-t",
                "-e",
                "yes",
                "-g",
                "802-11-wireless.ssid",
                "connection",
                "show",
                "uuid",
                valid_uuid,
            ),
            timeout_seconds=self.QUERY_TIMEOUT,
        )
        return ActiveWifiConnection(
            profile_name=profile_name,
            uuid=valid_uuid,
            ssid=ssid_output.strip() or None,
            device=active_device.interface,
            state=active_device.state,
            bssid=None,
            ipv4=IPConfiguration(
                addresses=tuple(values.get("IP4.ADDRESS", ())),
                gateway=self._first(values, "IP4.GATEWAY"),
                dns=tuple(values.get("IP4.DNS", ())),
            ),
            ipv6=IPConfiguration(
                addresses=tuple(values.get("IP6.ADDRESS", ())),
                gateway=self._first(values, "IP6.GATEWAY"),
                dns=tuple(values.get("IP6.DNS", ())),
            ),
        )

    @staticmethod
    def _first(values: dict[str, list[str]], key: str) -> str | None:
        """Perform first."""
        entries = values.get(key, [])
        return entries[0] if entries and entries[0] else None
