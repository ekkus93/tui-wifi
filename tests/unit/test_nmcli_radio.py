"""Verify nmcli status-failure and radio behavior."""

from __future__ import annotations

import asyncio

import pytest

from tests.assertions import verify
from tests.nmcli_fixtures import NMCLI_PATH, process_result
from tui_wifi.backends.nmcli import NmcliWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import BackendAvailability, WifiRadioState
from tui_wifi.process import ProcessNonZeroExitError, ProcessRequest
from tui_wifi.process.fake import FakeProcessRunner

NONZERO_EXIT = 10


@pytest.mark.parametrize(
    ("failure", "availability"),
    [
        ("permission denied", BackendAvailability.UNAUTHORIZED),
        ("unexpected command error", BackendAvailability.UNAVAILABLE),
    ],
)
def test_status_command_failures_map_to_availability(
    failure: str,
    availability: BackendAvailability,
) -> None:
    """Verify authorization and generic failures become explicit status values."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        request = ProcessRequest(NMCLI_PATH, ("--version",))
        error = ProcessNonZeroExitError(
            "failed",
            request,
            process_result(stderr=failure, exit_code=NONZERO_EXIT),
        )
        runner.queue(NMCLI_PATH, ("--version",), error)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        status = await backend.check_status()

        verify(status.availability == availability)
        verify("category=" in (status.technical_details or ""))
        runner.assert_finished()

    asyncio.run(scenario())


def test_status_parse_failure_returns_unavailable() -> None:
    """Verify malformed status output cannot be reported as available."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(NMCLI_PATH, ("--version",), process_result(stdout="nmcli 1.50\n"))
        runner.queue(
            NMCLI_PATH,
            ("-t", "-e", "yes", "-f", "STATE", "general"),
            process_result(stdout="connected (global)\n"),
        )
        runner.queue(
            NMCLI_PATH,
            ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"),
            process_result(stdout="not-two-fields\n"),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        status = await backend.check_status()

        verify(status.availability == BackendAvailability.UNAVAILABLE)
        verify("parse_failure" in (status.technical_details or ""))
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("enabled:enabled\n", WifiRadioState.ENABLED),
        ("disabled:enabled\n", WifiRadioState.DISABLED),
        ("enabled:disabled\n", WifiRadioState.HARDWARE_BLOCKED),
        ("disabled:disabled\n", WifiRadioState.HARDWARE_BLOCKED),
    ],
)
def test_radio_state_matrix(output: str, expected: WifiRadioState) -> None:
    """Verify software and hardware radio values combine conservatively."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"),
            process_result(stdout=output),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)
        state = await backend.get_wifi_radio_state()
        verify(state == expected)
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize("output", ["one-field\n", "enabled:maybe\n"])
def test_radio_state_rejects_malformed_output(output: str) -> None:
    """Verify malformed field counts and booleans are parse failures."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"),
            process_result(stdout=output),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)
        with pytest.raises(WifiError) as caught:
            await backend.get_wifi_radio_state()
        verify(caught.value.category == ErrorCategory.PARSE_FAILURE)
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize("enabled", [True, False])
def test_radio_mutation_emits_command_and_verifies_state(enabled: bool) -> None:
    """Verify radio mutation re-reads and returns the requested state."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        emitted = "on" if enabled else "off"
        state_output = "enabled:enabled\n" if enabled else "disabled:enabled\n"
        runner.queue(NMCLI_PATH, ("radio", "wifi", emitted), process_result())
        runner.queue(
            NMCLI_PATH,
            ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"),
            process_result(stdout=state_output),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        state = await backend.set_wifi_radio_state(enabled=enabled)

        verify(state == (WifiRadioState.ENABLED if enabled else WifiRadioState.DISABLED))
        verify(runner.requests[0].timeout == backend.MUTATION_TIMEOUT)
        runner.assert_finished()

    asyncio.run(scenario())


def test_radio_mutation_rejects_mismatched_state() -> None:
    """Verify a successful command with the wrong resulting state fails."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(NMCLI_PATH, ("radio", "wifi", "on"), process_result())
        runner.queue(
            NMCLI_PATH,
            ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"),
            process_result(stdout="disabled:enabled\n"),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        with pytest.raises(WifiError) as caught:
            await backend.set_wifi_radio_state(enabled=True)

        verify(caught.value.category == ErrorCategory.VERIFICATION_FAILURE)
        verify("expected radio=enabled" in (caught.value.technical_details or ""))
        runner.assert_finished()

    asyncio.run(scenario())
