from __future__ import annotations

import ipaddress
import uuid as uuid_module

from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import DeviceState, NetworkManagerState, SecurityClass


def split_escaped(line: str, expected_fields: int | None = None, separator: str = ":") -> list[str]:
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line.rstrip("\n"):
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == separator:
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    if escaped:
        raise WifiError(
            ErrorCategory.PARSE_FAILURE,
            technical_details="dangling escape at end of nmcli output line",
        )
    fields.append("".join(current))
    if expected_fields is not None and len(fields) != expected_fields:
        raise WifiError(
            ErrorCategory.PARSE_FAILURE,
            technical_details=f"expected {expected_fields} fields, got {len(fields)}",
        )
    return fields


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"yes", "true", "on", "enabled", "1"}:
        return True
    if normalized in {"no", "false", "off", "disabled", "0"}:
        return False
    raise WifiError(ErrorCategory.PARSE_FAILURE, technical_details=f"invalid boolean: {value!r}")


def parse_signal(value: str) -> int | None:
    if not value.strip():
        return None
    try:
        signal = int(value)
    except ValueError as exc:
        raise WifiError(
            ErrorCategory.PARSE_FAILURE, technical_details=f"invalid signal value: {value!r}"
        ) from exc
    if not 0 <= signal <= 100:
        raise WifiError(
            ErrorCategory.PARSE_FAILURE, technical_details=f"signal outside 0..100: {signal}"
        )
    return signal


def parse_optional_int(value: str) -> int | None:
    if not value.strip():
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise WifiError(
            ErrorCategory.PARSE_FAILURE, technical_details=f"invalid integer: {value!r}"
        ) from exc


def frequency_to_channel(frequency: int | None) -> int | None:
    if frequency is None:
        return None
    if frequency == 2484:
        return 14
    if 2412 <= frequency <= 2472:
        return (frequency - 2407) // 5
    if 5000 <= frequency <= 5895:
        return (frequency - 5000) // 5
    if 5955 <= frequency <= 7115:
        return (frequency - 5950) // 5
    return None


def parse_security(value: str) -> SecurityClass:
    normalized = " ".join(value.upper().replace("_", "-").split())
    if normalized in {"", "--", "NONE", "OPEN"}:
        return SecurityClass.OPEN
    if "WEP" in normalized:
        return SecurityClass.WEP
    if any(marker in normalized for marker in ("802.1X", "EAP", "ENTERPRISE")):
        return SecurityClass.ENTERPRISE
    has_wpa1 = "WPA1" in normalized or normalized == "WPA"
    has_wpa2 = "WPA2" in normalized or "RSN" in normalized
    has_wpa3 = "WPA3" in normalized or "SAE" in normalized
    if has_wpa3 and (has_wpa2 or has_wpa1):
        return SecurityClass.MIXED_PERSONAL
    if has_wpa3:
        return SecurityClass.WPA3_PERSONAL
    if has_wpa2 and has_wpa1:
        return SecurityClass.MIXED_PERSONAL
    if has_wpa2:
        return SecurityClass.WPA2_PERSONAL
    if has_wpa1:
        return SecurityClass.WPA_PERSONAL
    return SecurityClass.UNKNOWN


def parse_device_state(value: str) -> DeviceState:
    normalized = value.strip().lower().replace(" ", "-")
    mapping = {
        "unmanaged": DeviceState.UNMANAGED,
        "unavailable": DeviceState.UNAVAILABLE,
        "disconnected": DeviceState.DISCONNECTED,
        "prepare": DeviceState.PREPARE,
        "connecting-(prepare)": DeviceState.PREPARE,
        "config": DeviceState.CONFIG,
        "connecting-(configuring)": DeviceState.CONFIG,
        "need-auth": DeviceState.NEED_AUTH,
        "connecting-(need-auth)": DeviceState.NEED_AUTH,
        "ip-config": DeviceState.IP_CONFIG,
        "connecting-(getting-ip-configuration)": DeviceState.IP_CONFIG,
        "ip-check": DeviceState.IP_CHECK,
        "secondaries": DeviceState.SECONDARIES,
        "activated": DeviceState.ACTIVATED,
        "connected": DeviceState.ACTIVATED,
        "deactivating": DeviceState.DEACTIVATING,
        "failed": DeviceState.FAILED,
    }
    return mapping.get(normalized, DeviceState.UNKNOWN)


def parse_nm_state(value: str) -> NetworkManagerState:
    normalized = value.strip().lower().replace(" ", "-")
    mapping = {
        "connected-(global)": NetworkManagerState.CONNECTED_GLOBAL,
        "connected-(site-only)": NetworkManagerState.CONNECTED_SITE,
        "connected-(local-only)": NetworkManagerState.CONNECTED_LOCAL,
        "connecting": NetworkManagerState.CONNECTING,
        "disconnected": NetworkManagerState.DISCONNECTED,
        "asleep": NetworkManagerState.ASLEEP,
    }
    return mapping.get(normalized, NetworkManagerState.UNKNOWN)


def validate_uuid(value: str) -> str:
    try:
        return str(uuid_module.UUID(value))
    except ValueError as exc:
        raise WifiError(
            ErrorCategory.PARSE_FAILURE,
            technical_details=f"invalid UUID: {value!r}",
        ) from exc


def parse_ip_values(values: list[str]) -> tuple[str, ...]:
    parsed: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        try:
            ipaddress.ip_interface(stripped)
        except ValueError as exc:
            raise WifiError(
                ErrorCategory.PARSE_FAILURE, technical_details=f"invalid IP address: {stripped!r}"
            ) from exc
        parsed.append(stripped)
    return tuple(parsed)
