"""Verify saved-profile and active-connection parsing."""

from __future__ import annotations

import asyncio

import pytest

from tests.assertions import verify
from tests.factories import DEFAULT_UUID
from tests.nmcli_fixtures import (
    NMCLI_PATH,
    active_detail_command,
    device_status_command,
    process_result,
    profile_detail_command,
    profile_summary_command,
    ssid_query_command,
)
from tui_wifi.backends.nmcli import NmcliWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import DeviceState, SecurityClass
from tui_wifi.process.fake import FakeProcessRunner

OTHER_UUID = "00000000-0000-0000-0000-000000000002"
THIRD_UUID = "00000000-0000-0000-0000-000000000003"


def queue_profile(
    runner: FakeProcessRunner,
    *,
    name: str = "Home profile",
    uuid: str = DEFAULT_UUID,
    connection_type: str = "wifi",
    device: str = "--",
    summary_autoconnect: str = "yes",
    detail: str = "Home\nwpa-psk\nwlan0\nyes\n",
) -> None:
    """Queue a single profile summary and detail response."""
    runner.queue(
        NMCLI_PATH,
        profile_summary_command(),
        process_result(
            stdout=f"{name}:{uuid}:{connection_type}:{device}:{summary_autoconnect}\n",
        ),
    )
    if connection_type in {"wifi", "802-11-wireless"}:
        runner.queue(NMCLI_PATH, profile_detail_command(uuid), process_result(stdout=detail))


def test_saved_profile_list_filters_non_wifi_rows_and_preserves_order() -> None:
    """Verify only wireless summaries trigger detail queries in original order."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        summary = (
            f"Home:{DEFAULT_UUID}:wifi:--:yes\n"
            f"Wired:{OTHER_UUID}:ethernet:eth0:yes\n"
            f"Guest:{THIRD_UUID}:802-11-wireless:wlan0:no\n"
            "Bridge:00000000-0000-0000-0000-000000000004:bridge:br0:yes\n"
            "VPN:00000000-0000-0000-0000-000000000005:vpn:--:no\n"
        )
        runner.queue(NMCLI_PATH, profile_summary_command(), process_result(stdout=summary))
        runner.queue(
            NMCLI_PATH,
            profile_detail_command(DEFAULT_UUID),
            process_result(stdout="Home\nwpa-psk\nwlan0\nyes\n"),
        )
        runner.queue(
            NMCLI_PATH,
            profile_detail_command(THIRD_UUID),
            process_result(stdout="Guest\nnone\n\nno\n"),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        profiles = await backend.list_saved_wifi_profiles()

        verify([profile.name for profile in profiles] == ["Home", "Guest"])
        verify([profile.uuid for profile in profiles] == [DEFAULT_UUID, THIRD_UUID])
        verify(OTHER_UUID not in repr(runner.requests))
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    (
        "key_mgmt",
        "security",
        "device",
        "expected_active",
        "ssid",
        "interface_name",
    ),
    [
        ("wpa-psk", SecurityClass.WPA2_PERSONAL, "--", False, "Home", "wlan0"),
        ("sae", SecurityClass.WPA3_PERSONAL, "", False, "Home", "wlan0"),
        ("sae wpa-psk", SecurityClass.MIXED_PERSONAL, "wlan0", True, "Home", "wlan0"),
        ("none", SecurityClass.OPEN, "--", False, "Home", ""),
        ("wpa-eap", SecurityClass.ENTERPRISE, "wlan0", True, "Home", "wlan0"),
        ("future-mode", SecurityClass.UNKNOWN, "--", False, "", ""),
    ],
)
def test_profile_detail_parsing_matrix(
    key_mgmt: str,
    security: SecurityClass,
    device: str,
    expected_active: bool,
    ssid: str,
    interface_name: str,
) -> None:
    """Verify profile security, optional fields, and active-state parsing."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            profile_summary_command(),
            process_result(stdout=f"Profile:{DEFAULT_UUID}:wifi:{device}:yes\n"),
        )
        runner.queue(
            NMCLI_PATH,
            profile_detail_command(DEFAULT_UUID),
            process_result(stdout=f"{ssid}\n{key_mgmt}\n{interface_name}\nyes\n"),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        profile = (await backend.list_saved_wifi_profiles())[0]

        verify(profile.security == security)
        verify(profile.active is expected_active)
        verify(profile.ssid == (ssid or None))
        verify(profile.interface_name == (interface_name or None))
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("detail", "summary_value", "expected_autoconnect", "expected_interface"),
    [
        ("Home\n", "yes", True, None),
        ("Home\nwpa-psk\n", "no", False, None),
        ("Home\nwpa-psk\n\n", "yes", True, None),
        ("Home\nwpa-psk\nwlan1\n", "no", False, "wlan1"),
        ("Home\nwpa-psk\nwlan0\nyes\nignored\n", "no", True, "wlan0"),
    ],
)
def test_partial_profile_detail_fallbacks(
    detail: str,
    summary_value: str,
    expected_autoconnect: bool,
    expected_interface: str | None,
) -> None:
    """Verify partial detail output falls back only where specified."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            profile_summary_command(),
            process_result(
                stdout=f"Profile:{DEFAULT_UUID}:wifi:--:{summary_value}\n",
            ),
        )
        runner.queue(
            NMCLI_PATH,
            profile_detail_command(DEFAULT_UUID),
            process_result(stdout=detail),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        profile = (await backend.list_saved_wifi_profiles())[0]

        verify(profile.autoconnect is expected_autoconnect)
        verify(profile.interface_name == expected_interface)
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("summary", "detail_queries_expected"),
    [
        ("too:few:fields\n", 0),
        ("Profile:not-a-uuid:wifi:--:yes\n", 0),
    ],
)
def test_invalid_profile_summary_or_uuid_fails_before_detail_query(
    summary: str,
    detail_queries_expected: int,
) -> None:
    """Verify malformed summaries and UUIDs fail with no detail lookup."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(NMCLI_PATH, profile_summary_command(), process_result(stdout=summary))
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        with pytest.raises(WifiError) as caught:
            await backend.list_saved_wifi_profiles()

        verify(caught.value.category == ErrorCategory.PARSE_FAILURE)
        verify(len(runner.requests) - 1 == detail_queries_expected)
        runner.assert_finished()

    asyncio.run(scenario())


def test_profile_limit_boundary_is_accepted() -> None:
    """Verify exactly the configured number of profiles is allowed."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        backend = NmcliWifiBackend(runner, NMCLI_PATH)
        rows: list[str] = []
        uuids: list[str] = []
        for index in range(backend.PROFILE_DETAIL_LIMIT):
            uuid = f"00000000-0000-0000-0000-{index:012d}"
            uuids.append(uuid)
            rows.append(f"Profile {index}:{uuid}:wifi:--:yes")
        runner.queue(
            NMCLI_PATH,
            profile_summary_command(),
            process_result(stdout="\n".join(rows) + "\n"),
        )
        for index, uuid in enumerate(uuids):
            runner.queue(
                NMCLI_PATH,
                profile_detail_command(uuid),
                process_result(stdout=f"SSID {index}\nwpa-psk\n\nyes\n"),
            )

        profiles = await backend.list_saved_wifi_profiles()

        verify(len(profiles) == backend.PROFILE_DETAIL_LIMIT)
        runner.assert_finished()

    asyncio.run(scenario())


def test_profile_limit_overflow_fails_before_detail_queries() -> None:
    """Verify one profile above the bound fails without per-profile commands."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        backend = NmcliWifiBackend(runner, NMCLI_PATH)
        rows = [
            f"Profile {index}:00000000-0000-0000-0000-{index:012d}:wifi:--:yes"
            for index in range(backend.PROFILE_DETAIL_LIMIT + 1)
        ]
        runner.queue(
            NMCLI_PATH,
            profile_summary_command(),
            process_result(stdout="\n".join(rows) + "\n"),
        )

        with pytest.raises(WifiError) as caught:
            await backend.list_saved_wifi_profiles()

        verify(caught.value.category == ErrorCategory.COMMAND_FAILURE)
        verify("Too many" in caught.value.summary)
        verify(str(backend.PROFILE_DETAIL_LIMIT) in (caught.value.technical_details or ""))
        verify(len(runner.requests) == 1)
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", SecurityClass.OPEN),
        (" none ", SecurityClass.OPEN),
        ("WPA-PSK", SecurityClass.WPA2_PERSONAL),
        (" sae ", SecurityClass.WPA3_PERSONAL),
        ("wpa-psk sae", SecurityClass.MIXED_PERSONAL),
        ("wpa-eap", SecurityClass.ENTERPRISE),
        ("IEEE8021X", SecurityClass.ENTERPRISE),
        ("wpa-psk wpa-eap", SecurityClass.ENTERPRISE),
        ("future", SecurityClass.UNKNOWN),
    ],
)
def test_profile_security_classification(raw: str, expected: SecurityClass) -> None:
    """Verify the complete key-management classification matrix."""
    verify(NmcliWifiBackend.profile_security(raw) == expected)


def test_get_active_wifi_connection_returns_none_without_activated_device() -> None:
    """Verify inactive and unmanaged devices do not trigger detail queries."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            device_status_command(),
            process_result(
                stdout=(
                    "wlan0:wifi:disconnected:--\n"
                    "wlan1:wifi:unavailable:--\n"
                    "wlan2:wifi:unmanaged:--\n"
                ),
            ),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        active = await backend.get_active_wifi_connection()

        verify(active is None)
        verify(len(runner.requests) == 1)
        runner.assert_finished()

    asyncio.run(scenario())


def test_get_active_wifi_connection_parses_full_ip_state() -> None:
    """Verify repeated IPv4 and IPv6 values remain ordered and complete."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            device_status_command(),
            process_result(stdout="wlan0:wifi:connected:Fallback profile\n"),
        )
        runner.queue(
            NMCLI_PATH,
            active_detail_command(),
            process_result(
                stdout=(
                    f"GENERAL.CONNECTION:Primary profile\nGENERAL.CON-UUID:{DEFAULT_UUID}\n"
                    "GENERAL.STATE:100 (connected)\n"
                    "IP4.ADDRESS:192.0.2.10/24\nIP4.ADDRESS:192.0.2.11/24\n"
                    "IP4.GATEWAY:192.0.2.1\nIP4.DNS:192.0.2.53\nIP4.DNS:192.0.2.54\n"
                    "IP6.ADDRESS:2001\\:db8\\:\\:10/64\nIP6.ADDRESS:2001\\:db8\\:\\:11/64\n"
                    "IP6.GATEWAY:2001\\:db8\\:\\:1\nIP6.DNS:2001\\:db8\\:\\:53\nIP6.DNS:2001\\:db8\\:\\:54\n"
                ),
            ),
        )
        runner.queue(NMCLI_PATH, ssid_query_command(DEFAULT_UUID), process_result(stdout="Home\n"))
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        active = await backend.get_active_wifi_connection()

        verify(active is not None)
        verify(active.profile_name == "Primary profile")
        verify(active.ipv4.addresses == ("192.0.2.10/24", "192.0.2.11/24"))
        verify(active.ipv4.gateway == "192.0.2.1")
        verify(active.ipv4.dns == ("192.0.2.53", "192.0.2.54"))
        verify(active.ipv6.addresses == ("2001:db8::10/64", "2001:db8::11/64"))
        verify(active.ipv6.gateway == "2001:db8::1")
        verify(active.ipv6.dns == ("2001:db8::53", "2001:db8::54"))
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("general_name", "device_name", "ssid_output", "expected_name", "expected_ssid"),
    [
        ("", "Fallback", "\n", "Fallback", None),
        ("", "--", "Guest\n", "", "Guest"),
        ("", "", "Guest\n", "", "Guest"),
    ],
)
def test_active_connection_optional_name_gateway_and_ssid_fallbacks(
    general_name: str,
    device_name: str,
    ssid_output: str,
    expected_name: str,
    expected_ssid: str | None,
) -> None:
    """Verify optional names, gateways, and blank SSIDs use explicit fallbacks."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            device_status_command(),
            process_result(stdout=f"wlan0:wifi:connected:{device_name}\n"),
        )
        runner.queue(
            NMCLI_PATH,
            active_detail_command(),
            process_result(
                stdout=(
                    f"GENERAL.CONNECTION:{general_name}\nGENERAL.CON-UUID:{DEFAULT_UUID}\n"
                    "GENERAL.STATE:100 (connected)\nIP4.ADDRESS:192.0.2.10/24\n"
                ),
            ),
        )
        runner.queue(
            NMCLI_PATH,
            ssid_query_command(DEFAULT_UUID),
            process_result(stdout=ssid_output),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        active = await backend.get_active_wifi_connection()

        verify(active is not None)
        verify(active.profile_name == expected_name)
        verify(active.ssid == expected_ssid)
        verify(active.ipv4.gateway is None)
        verify(active.ipv6.gateway is None)
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("uuid_line", "technical_fragment"),
    [
        ("", "did not expose"),
        ("GENERAL.CON-UUID:not-a-uuid\n", "invalid UUID"),
    ],
)
def test_active_connection_uuid_failures_prevent_ssid_query(
    uuid_line: str,
    technical_fragment: str,
) -> None:
    """Verify absent or invalid active UUIDs fail before the SSID query."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            device_status_command(),
            process_result(stdout="wlan0:wifi:connected:Home\n"),
        )
        runner.queue(
            NMCLI_PATH,
            active_detail_command(),
            process_result(stdout=f"GENERAL.CONNECTION:Home\n{uuid_line}"),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        with pytest.raises(WifiError) as caught:
            await backend.get_active_wifi_connection()

        verify(caught.value.category == ErrorCategory.PARSE_FAILURE)
        verify(technical_fragment in (caught.value.technical_details or ""))
        verify(len(runner.requests) == 2)
        runner.assert_finished()

    asyncio.run(scenario())
