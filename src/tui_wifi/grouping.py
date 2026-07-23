"""Provide grouping functionality."""

from __future__ import annotations

from collections import defaultdict

from tui_wifi.models import AccessPoint, ActiveWifiConnection, NetworkGroup, SavedProfile


def group_networks(
    access_points: tuple[AccessPoint, ...],
    profiles: tuple[SavedProfile, ...],
    active: ActiveWifiConnection | None,
) -> tuple[NetworkGroup, ...]:
    """Perform group networks."""
    buckets: dict[tuple[str, str], list[AccessPoint]] = defaultdict(list)
    for ap in access_points:
        if ap.display_ssid:
            buckets[(ap.display_ssid, ap.security.value)].append(ap)

    groups: list[NetworkGroup] = []
    for (ssid, _security_key), members in buckets.items():
        strongest = max(members, key=lambda ap: ap.signal if ap.signal is not None else -1)
        compatible_profiles = tuple(
            profile.uuid
            for profile in profiles
            if profile.ssid == ssid and profile.security == strongest.security
        )
        connected = any(ap.active for ap in members) or (active is not None and active.ssid == ssid)
        groups.append(
            NetworkGroup(
                identity=f"{ssid}\0{strongest.security.value}",
                display_ssid=ssid,
                security=strongest.security,
                signal=strongest.signal,
                connected=connected,
                saved_profile_uuids=compatible_profiles,
                supported=strongest.security.supported,
                member_bssids=tuple(sorted(ap.bssid for ap in members)),
            ),
        )

    def sort_key(group: NetworkGroup) -> tuple[int, int, str]:
        """Perform sort key."""
        if group.connected:
            bucket = 0
        elif group.saved_profile_uuids and group.supported:
            bucket = 1
        elif group.supported:
            bucket = 2
        else:
            bucket = 3
        signal = group.signal if group.signal is not None else -1
        return (bucket, -signal, group.display_ssid.casefold())

    return tuple(sorted(groups, key=sort_key))
