# Copyright (c) 2026 Phillip Chin
"""Verify compatibility with NetworkManager 1.36 terse output."""

from __future__ import annotations

import asyncio

from tests.assertions import verify
from tests.factories import DEFAULT_UUID
from tests.nmcli_fixtures import (
    NMCLI_PATH,
    active_detail_command,
    device_status_command,
    process_result,
    ssid_query_command,
)
from tui_wifi.backends.nmcli import NmcliWifiBackend
from tui_wifi.backends.parsing import parse_nm_state, split_escaped_key_value
from tui_wifi.models import NetworkManagerState
from tui_wifi.process.fake import FakeProcessRunner


def test_property_split_preserves_literal_and_escaped_ipv6_colons() -> None:
    """Verify only the first unescaped property delimiter separates key and value."""
    verify(
        split_escaped_key_value("IP6.ADDRESS[1]:fe80::3aff:3dfc:c7b9:dbaa/64")
        == ("IP6.ADDRESS[1]", "fe80::3aff:3dfc:c7b9:dbaa/64"),
    )
    verify(
        split_escaped_key_value(r"IP6.GATEWAY:2001\:db8\:\:1") == ("IP6.GATEWAY", "2001:db8::1"),
    )


def test_legacy_connected_global_state_is_recognized() -> None:
    """Verify older nmcli releases' plain connected state is not reported as unknown."""
    verify(parse_nm_state("connected") == NetworkManagerState.CONNECTED_GLOBAL)


def test_networkmanager_136_active_connection_output_is_parsed() -> None:
    """Verify indexed IP properties and literal IPv6 colons from nmcli 1.36."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            device_status_command(),
            process_result(stdout="wlo1:wifi:connected:Home profile\n"),
        )
        runner.queue(
            NMCLI_PATH,
            active_detail_command(interface="wlo1"),
            process_result(
                stdout=(
                    "GENERAL.CONNECTION:Home profile\n"
                    f"GENERAL.CON-UUID:{DEFAULT_UUID}\n"
                    "GENERAL.STATE:100 (connected)\n"
                    "IP4.ADDRESS[1]:192.0.2.109/24\n"
                    "IP4.GATEWAY:192.0.2.1\n"
                    "IP4.DNS[1]:192.0.2.42\n"
                    "IP4.DNS[2]:192.0.2.53\n"
                    "IP4.DNS[3]:192.0.2.54\n"
                    "IP6.ADDRESS[1]:fe80::3aff:3dfc:c7b9:dbaa/64\n"
                    "IP6.GATEWAY:\n"
                ),
            ),
        )
        runner.queue(
            NMCLI_PATH,
            ssid_query_command(DEFAULT_UUID),
            process_result(stdout="Home\n"),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        active = await backend.get_active_wifi_connection()

        verify(active is not None)
        verify(active.device == "wlo1")
        verify(active.ipv4.addresses == ("192.0.2.109/24",))
        verify(active.ipv4.gateway == "192.0.2.1")
        verify(active.ipv4.dns == ("192.0.2.42", "192.0.2.53", "192.0.2.54"))
        verify(active.ipv6.addresses == ("fe80::3aff:3dfc:c7b9:dbaa/64",))
        verify(active.ipv6.gateway is None)
        verify(active.ipv6.dns == ())
        runner.assert_finished()

    asyncio.run(scenario())
