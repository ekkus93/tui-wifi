# Copyright (c) 2026 Phillip Chin
"""Verify every NetworkManager mutation and its postcondition checks."""

from __future__ import annotations

import asyncio

import pytest

from tests.assertions import verify
from tests.factories import DEFAULT_UUID, active_connection, saved_profile
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
    DisconnectRequest,
    SavedProfileRequest,
)
from tui_wifi.backends.nmcli import NmcliWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import ActiveWifiConnection
from tui_wifi.process.fake import FakeProcessRunner

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


def test_activate_saved_profile_uses_uuid_and_interface() -> None:
    """Verify saved activation uses the exact UUID and interface and rechecks state."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            (
                "--wait",
                "45",
                "connection",
                "up",
                "uuid",
                DEFAULT_UUID,
                "ifname",
                "wlan0",
            ),
            process_result(),
        )
        queue_active_connection(runner)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        active = await backend.activate_saved_profile(
            SavedProfileRequest(DEFAULT_UUID, "wlan0"),
        )

        verify(active.uuid == DEFAULT_UUID)
        verify(active.device == "wlan0")
        verify(runner.requests[0].timeout == backend.CONNECT_TIMEOUT)
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("returned_interface", "returned_uuid", "detail_fragment"),
    [
        ("wlan1", DEFAULT_UUID, "wlan0"),
        ("wlan0", OTHER_UUID, "expected UUID"),
    ],
)
def test_activate_saved_profile_rejects_mismatched_active_state(
    returned_interface: str,
    returned_uuid: str,
    detail_fragment: str,
) -> None:
    """Verify saved activation rejects a different interface or UUID."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            (
                "--wait",
                "45",
                "connection",
                "up",
                "uuid",
                DEFAULT_UUID,
                "ifname",
                "wlan0",
            ),
            process_result(),
        )
        queue_active_connection(
            runner,
            interface=returned_interface,
            uuid=returned_uuid,
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        with pytest.raises(WifiError) as caught:
            await backend.activate_saved_profile(
                SavedProfileRequest(DEFAULT_UUID, "wlan0"),
            )

        verify(caught.value.category == ErrorCategory.VERIFICATION_FAILURE)
        verify(detail_fragment in (caught.value.technical_details or ""))
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("active", "expected_uuid", "expected_ssid", "detail_fragment"),
    [
        (None, None, None, "no active"),
        (active_connection(device="wlan1"), None, None, "wlan0"),
        (active_connection(uuid=OTHER_UUID), DEFAULT_UUID, None, "expected UUID"),
        (active_connection(ssid="Other"), None, "Home", "expected SSID"),
    ],
)
def test_verify_active_failure_matrix(
    active: ActiveWifiConnection | None,
    expected_uuid: str | None,
    expected_ssid: str | None,
    detail_fragment: str,
) -> None:
    """Verify each active-state mismatch produces a verification failure."""

    async def scenario() -> None:
        backend = StubActiveBackend(active)
        with pytest.raises(WifiError) as caught:
            await backend.verify_active("wlan0", expected_uuid, expected_ssid)

        verify(caught.value.category == ErrorCategory.VERIFICATION_FAILURE)
        verify(detail_fragment in (caught.value.technical_details or ""))

    asyncio.run(scenario())


def test_verify_active_optional_checks_and_identity() -> None:
    """Verify omitted UUID and SSID checks return the exact active object."""

    async def scenario() -> None:
        expected = active_connection(uuid=OTHER_UUID, ssid="Different")
        backend = StubActiveBackend(expected)
        result = await backend.verify_active("wlan0", None, None)
        verify(result is expected)

    asyncio.run(scenario())


@pytest.mark.parametrize("remaining_interface", [None, "wlan1"])
def test_disconnect_uses_bounded_wait_and_accepts_inactive_requested_interface(
    remaining_interface: str | None,
) -> None:
    """Verify disconnect succeeds when the requested interface is inactive."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            ("--wait", "15", "device", "disconnect", "wlan0"),
            process_result(),
        )
        if remaining_interface is None:
            queue_no_active_connection(runner)
        else:
            queue_active_connection(runner, interface=remaining_interface)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        await backend.disconnect(DisconnectRequest("wlan0", DEFAULT_UUID))

        verify(runner.requests[0].timeout == backend.MUTATION_TIMEOUT)
        runner.assert_finished()

    asyncio.run(scenario())


def test_disconnect_fails_when_requested_interface_remains_active() -> None:
    """Verify a false-success disconnect is rejected."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            ("--wait", "15", "device", "disconnect", "wlan0"),
            process_result(),
        )
        queue_active_connection(runner)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        with pytest.raises(WifiError) as caught:
            await backend.disconnect(DisconnectRequest("wlan0", DEFAULT_UUID))

        verify(caught.value.category == ErrorCategory.VERIFICATION_FAILURE)
        verify("remained connected" in (caught.value.technical_details or ""))
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize("profile_remains", [False, True])
def test_delete_saved_profile_verifies_uuid_absence(profile_remains: bool) -> None:
    """Verify deletion re-reads profiles and rejects a retained UUID."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            ("connection", "delete", "uuid", DEFAULT_UUID),
            process_result(),
        )
        if profile_remains:
            queue_profile_verification(runner, enabled=True)
        else:
            runner.queue(NMCLI_PATH, profile_summary_command(), process_result())
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        if profile_remains:
            with pytest.raises(WifiError) as caught:
                await backend.delete_saved_profile(DEFAULT_UUID)
            verify(caught.value.category == ErrorCategory.VERIFICATION_FAILURE)
        else:
            await backend.delete_saved_profile(DEFAULT_UUID)
        verify(runner.requests[0].args[-1] == DEFAULT_UUID)
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize("enabled", [True, False])
def test_set_profile_autoconnect_emits_and_verifies_requested_value(enabled: bool) -> None:
    """Verify auto-connect mutation emits yes/no and returns the stored profile."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        emitted = "yes" if enabled else "no"
        runner.queue(
            NMCLI_PATH,
            (
                "connection",
                "modify",
                "uuid",
                DEFAULT_UUID,
                "connection.autoconnect",
                emitted,
            ),
            process_result(),
        )
        queue_profile_verification(runner, enabled=enabled)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        profile = await backend.set_profile_autoconnect(DEFAULT_UUID, enabled=enabled)

        verify(profile == saved_profile(autoconnect=enabled))
        verify(runner.requests[0].args[-1] == emitted)
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize("profile_state", ["missing", "mismatched"])
def test_set_profile_autoconnect_rejects_unverified_state(profile_state: str) -> None:
    """Verify a missing or mismatched profile value is not accepted."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            (
                "connection",
                "modify",
                "uuid",
                DEFAULT_UUID,
                "connection.autoconnect",
                "yes",
            ),
            process_result(),
        )
        if profile_state == "missing":
            runner.queue(NMCLI_PATH, profile_summary_command(), process_result())
        else:
            queue_profile_verification(runner, enabled=False)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        with pytest.raises(WifiError) as caught:
            await backend.set_profile_autoconnect(DEFAULT_UUID, enabled=True)

        verify(caught.value.category == ErrorCategory.VERIFICATION_FAILURE)
        verify("autoconnect verification failed" in (caught.value.technical_details or ""))
        runner.assert_finished()

    asyncio.run(scenario())
