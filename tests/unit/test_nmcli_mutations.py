# Copyright (c) 2026 Phillip Chin
"""Verify every NetworkManager mutation and its postcondition checks."""

from __future__ import annotations

import asyncio

import pytest

from tests.assertions import verify
from tests.factories import DEFAULT_BSSID, DEFAULT_UUID
from tests.nmcli_fixtures import (
    NMCLI_PATH,
    active_detail_command,
    device_status_command,
    process_result,
    profile_detail_command,
    profile_summary_command,
    ssid_query_command,
)
from tui_wifi.backends.base import (
    HiddenConnectRequest,
    VisibleConnectRequest,
)
from tui_wifi.backends.nmcli import NmcliWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import ActiveWifiConnection, SecurityClass
from tui_wifi.process.fake import FakeProcessRunner
from tui_wifi.secrets import SecretValue

OTHER_UUID = "00000000-0000-0000-0000-000000000002"


class StubActiveBackend(NmcliWifiBackend):
    """Return a predetermined active connection for verification tests."""

    def __init__(self, active: ActiveWifiConnection | None) -> None:
        """Initialize with the value returned by the active-connection query."""
        super().__init__(FakeProcessRunner(), NMCLI_PATH)
        self.stub_active = active

    async def get_active_wifi_connection(self) -> ActiveWifiConnection | None:
        """Return the predetermined active value."""
        return self.stub_active

    async def verify_active(
        self,
        interface: str,
        uuid: str | None,
        ssid: str | None,
    ) -> ActiveWifiConnection:
        """Expose active-state verification through a test-only public wrapper."""
        return await self._verify_active(interface, uuid, ssid)


def queue_active_connection(
    runner: FakeProcessRunner,
    *,
    interface: str = "wlan0",
    uuid: str = DEFAULT_UUID,
    ssid: str = "Home",
    profile_name: str = "Home profile",
) -> None:
    """Queue the three reads used to reconstruct an active connection."""
    runner.queue(
        NMCLI_PATH,
        device_status_command(),
        process_result(stdout=f"{interface}:wifi:connected:{profile_name}\n"),
    )
    runner.queue(
        NMCLI_PATH,
        active_detail_command(interface),
        process_result(
            stdout=(
                f"GENERAL.CONNECTION:{profile_name}\n"
                f"GENERAL.CON-UUID:{uuid}\n"
                "GENERAL.STATE:100 (connected)\n"
                "IP4.ADDRESS:192.0.2.10/24\n"
            ),
        ),
    )
    runner.queue(NMCLI_PATH, ssid_query_command(uuid), process_result(stdout=f"{ssid}\n"))


def queue_no_active_connection(runner: FakeProcessRunner) -> None:
    """Queue a device read with no activated Wi-Fi device."""
    runner.queue(
        NMCLI_PATH,
        device_status_command(),
        process_result(stdout="wlan0:wifi:disconnected:--\n"),
    )


def queue_profile_verification(
    runner: FakeProcessRunner,
    *,
    enabled: bool,
    uuid: str = DEFAULT_UUID,
) -> None:
    """Queue a saved-profile list and detail lookup."""
    value = "yes" if enabled else "no"
    runner.queue(
        NMCLI_PATH,
        profile_summary_command(),
        process_result(stdout=f"Home profile:{uuid}:wifi:--:{value}\n"),
    )
    runner.queue(
        NMCLI_PATH,
        profile_detail_command(uuid),
        process_result(stdout=f"Home\nwpa-psk\nwlan0\n{value}\n"),
    )


def test_connect_visible_open_network_uses_no_password_argument() -> None:
    """Verify open-network commands contain no credential argument."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        command = (
            "--wait",
            "45",
            "device",
            "wifi",
            "connect",
            "Cafe",
            "ifname",
            "wlan0",
        )
        runner.queue(NMCLI_PATH, command, process_result())
        queue_active_connection(runner, ssid="Cafe", profile_name="Cafe")
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        active = await backend.connect_visible_network(
            VisibleConnectRequest("Cafe", "wlan0", SecurityClass.OPEN),
        )

        verify(active.ssid == "Cafe")
        verify(active.device == "wlan0")
        verify("password" not in runner.requests[0].args)
        verify(runner.requests[0].sensitive_arg_indexes == frozenset())
        verify(runner.requests[0].timeout == backend.CONNECT_TIMEOUT)
        runner.assert_finished()

    asyncio.run(scenario())


def test_connect_visible_personal_network_marks_password_sensitive() -> None:
    """Verify a visible-network password is redacted at its exact argument index."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        credential = "synthetic-visible-credential"
        command = (
            "--wait",
            "45",
            "device",
            "wifi",
            "connect",
            "Home",
            "ifname",
            "wlan0",
            "password",
            credential,
        )
        runner.queue(NMCLI_PATH, command, process_result())
        queue_active_connection(runner)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        active = await backend.connect_visible_network(
            VisibleConnectRequest(
                "Home",
                "wlan0",
                SecurityClass.WPA2_PERSONAL,
                SecretValue(credential),
            ),
        )

        request = runner.requests[0]
        verify(active.uuid == DEFAULT_UUID)
        verify(request.sensitive_arg_indexes == frozenset({9}))
        verify(credential not in repr(request.redacted_command))
        verify("<redacted>" in repr(request.redacted_command))
        verify(credential not in repr(runner.invocations))
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize("bssid", [DEFAULT_BSSID, None])
def test_connect_visible_network_bssid_argument_policy(bssid: str | None) -> None:
    """Verify BSSID pinning is exact and omitted when not requested."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        args = [
            "--wait",
            "45",
            "device",
            "wifi",
            "connect",
            "Home",
            "ifname",
            "wlan0",
        ]
        if bssid is not None:
            args.extend(("bssid", bssid))
        runner.queue(NMCLI_PATH, tuple(args), process_result())
        queue_active_connection(runner)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        await backend.connect_visible_network(
            VisibleConnectRequest(
                "Home",
                "wlan0",
                SecurityClass.OPEN,
                bssid=bssid,
            ),
        )

        request = runner.requests[0]
        verify(request.args.count("bssid") == (1 if bssid is not None else 0))
        verify(request.sensitive_arg_indexes == frozenset())
        runner.assert_finished()

    asyncio.run(scenario())


def test_connect_visible_network_disables_autoconnect_after_verified_connection() -> None:
    """Verify autoconnect is changed only after active-state verification."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            (
                "--wait",
                "45",
                "device",
                "wifi",
                "connect",
                "Home",
                "ifname",
                "wlan0",
            ),
            process_result(),
        )
        queue_active_connection(runner)
        runner.queue(
            NMCLI_PATH,
            (
                "connection",
                "modify",
                "uuid",
                DEFAULT_UUID,
                "connection.autoconnect",
                "no",
            ),
            process_result(),
        )
        queue_profile_verification(runner, enabled=False)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        active = await backend.connect_visible_network(
            VisibleConnectRequest(
                "Home",
                "wlan0",
                SecurityClass.OPEN,
                autoconnect=False,
            ),
        )

        verify(active.uuid == DEFAULT_UUID)
        verify(runner.requests[4].args[3] == DEFAULT_UUID)
        verify(runner.requests[4].args[-1] == "no")
        runner.assert_finished()

    asyncio.run(scenario())


def test_connect_visible_network_does_not_modify_autoconnect_when_enabled() -> None:
    """Verify default autoconnect does not emit a profile modification."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            (
                "--wait",
                "45",
                "device",
                "wifi",
                "connect",
                "Home",
                "ifname",
                "wlan0",
            ),
            process_result(),
        )
        queue_active_connection(runner)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        await backend.connect_visible_network(
            VisibleConnectRequest("Home", "wlan0", SecurityClass.OPEN),
        )

        verify(all(request.args[:2] != ("connection", "modify") for request in runner.requests))
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "security",
    [SecurityClass.WEP, SecurityClass.ENTERPRISE, SecurityClass.UNKNOWN],
)
def test_connect_visible_network_rejects_unsupported_security(
    security: SecurityClass,
) -> None:
    """Verify unsupported visible security fails before process execution."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        with pytest.raises(WifiError) as caught:
            await backend.connect_visible_network(
                VisibleConnectRequest("Unsupported", "wlan0", security),
            )

        verify(caught.value.category == ErrorCategory.UNSUPPORTED_SECURITY)
        verify(runner.requests == [])

    asyncio.run(scenario())


def test_connect_visible_personal_network_requires_password() -> None:
    """Verify personal security without a password fails before execution."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        with pytest.raises(WifiError) as caught:
            await backend.connect_visible_network(
                VisibleConnectRequest("Home", "wlan0", SecurityClass.WPA2_PERSONAL),
            )

        verify(caught.value.category == ErrorCategory.MISSING_SECRETS)
        verify(runner.requests == [])

    asyncio.run(scenario())


def test_connect_hidden_open_network_uses_hidden_yes() -> None:
    """Verify hidden open connections include the explicit hidden flag."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        command = (
            "--wait",
            "45",
            "device",
            "wifi",
            "connect",
            "Hidden Cafe",
            "ifname",
            "wlan0",
            "hidden",
            "yes",
        )
        runner.queue(NMCLI_PATH, command, process_result())
        queue_active_connection(runner, ssid="Hidden Cafe", profile_name="Hidden Cafe")
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        active = await backend.connect_hidden_network(
            HiddenConnectRequest("Hidden Cafe", "wlan0", SecurityClass.OPEN),
        )

        verify(active.ssid == "Hidden Cafe")
        verify(runner.requests[0].sensitive_arg_indexes == frozenset())
        runner.assert_finished()

    asyncio.run(scenario())


def test_connect_hidden_personal_network_marks_password_sensitive_and_disables_autoconnect() -> (
    None
):
    """Verify hidden passwords and post-connect autoconnect updates are safe."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        credential = "synthetic-hidden-credential"
        command = (
            "--wait",
            "45",
            "device",
            "wifi",
            "connect",
            "Hidden Home",
            "ifname",
            "wlan0",
            "hidden",
            "yes",
            "password",
            credential,
        )
        runner.queue(NMCLI_PATH, command, process_result())
        queue_active_connection(runner, ssid="Hidden Home", profile_name="Hidden Home")
        runner.queue(
            NMCLI_PATH,
            (
                "connection",
                "modify",
                "uuid",
                DEFAULT_UUID,
                "connection.autoconnect",
                "no",
            ),
            process_result(),
        )
        queue_profile_verification(runner, enabled=False)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        await backend.connect_hidden_network(
            HiddenConnectRequest(
                "Hidden Home",
                "wlan0",
                SecurityClass.WPA2_PERSONAL,
                SecretValue(credential),
                autoconnect=False,
            ),
        )

        verify(runner.requests[0].sensitive_arg_indexes == frozenset({11}))
        verify(credential not in repr(runner.requests[0].redacted_command))
        verify(runner.requests[4].args[-1] == "no")
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("hidden_request", "category"),
    [
        (HiddenConnectRequest("", "wlan0", SecurityClass.OPEN), ErrorCategory.NETWORK_UNAVAILABLE),
        (
            HiddenConnectRequest("Hidden", "wlan0", SecurityClass.ENTERPRISE),
            ErrorCategory.UNSUPPORTED_SECURITY,
        ),
        (
            HiddenConnectRequest("Hidden", "wlan0", SecurityClass.WPA2_PERSONAL),
            ErrorCategory.MISSING_SECRETS,
        ),
    ],
)
def test_connect_hidden_network_rejects_invalid_request_before_process(
    hidden_request: HiddenConnectRequest,
    category: ErrorCategory,
) -> None:
    """Verify invalid hidden requests do not execute nmcli."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        with pytest.raises(WifiError) as caught:
            await backend.connect_hidden_network(hidden_request)

        verify(caught.value.category == category)
        verify(runner.requests == [])

    asyncio.run(scenario())
