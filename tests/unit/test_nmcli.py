"""Verify core nmcli execution, parsing, status, radio, devices, and scans."""

from __future__ import annotations

import asyncio

import pytest

from tests.assertions import verify
from tests.nmcli_fixtures import NMCLI_PATH, device_status_command, process_result
from tui_wifi.backends.nmcli import NmcliWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import BackendAvailability, DeviceState, SecurityClass, WifiRadioState
from tui_wifi.process import (
    ProcessMissingExecutableError,
    ProcessNonZeroExitError,
    ProcessRequest,
    ProcessTimeoutError,
)
from tui_wifi.process.fake import FakeProcessRunner

MISSING_PATH = "/missing/nmcli"
NONZERO_EXIT = 10


def test_explicit_nmcli_path_is_used_without_path_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify an explicit executable path bypasses environment lookup."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            ("device", "wifi", "rescan", "ifname", "wlan0"),
            process_result(),
        )
        monkeypatch.setattr("shutil.which", lambda _name: None)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        await backend.request_scan("wlan0")

        verify(runner.requests[0].executable == NMCLI_PATH)
        runner.assert_finished()

    asyncio.run(scenario())


def test_path_lookup_is_used_without_explicit_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify PATH resolution supplies the executable for commands."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            ("device", "wifi", "rescan", "ifname", "wlan0"),
            process_result(),
        )
        monkeypatch.setattr("shutil.which", lambda name: NMCLI_PATH if name == "nmcli" else None)
        backend = NmcliWifiBackend(runner)

        await backend.request_scan("wlan0")

        verify(runner.requests[0].executable == NMCLI_PATH)
        runner.assert_finished()

    asyncio.run(scenario())


def test_missing_executable_status_does_not_call_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify missing nmcli is reported without attempting a subprocess."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        monkeypatch.setattr("shutil.which", lambda _name: None)
        backend = NmcliWifiBackend(runner)

        status = await backend.check_status()

        verify(status.availability == BackendAvailability.MISSING_EXECUTABLE)
        verify(runner.requests == [])

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("process_error", "expected_category"),
    [
        (
            ProcessMissingExecutableError(
                "missing",
                ProcessRequest(MISSING_PATH),
            ),
            ErrorCategory.MISSING_NMCLI,
        ),
        (
            ProcessTimeoutError(
                "timeout",
                ProcessRequest(NMCLI_PATH),
            ),
            ErrorCategory.TIMEOUT,
        ),
    ],
)
def test_process_failures_translate_to_typed_wifi_errors(
    process_error: Exception,
    expected_category: ErrorCategory,
) -> None:
    """Verify missing executables and timeouts retain their original cause."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        command = ("device", "wifi", "rescan", "ifname", "wlan0")
        runner.queue(NMCLI_PATH, command, process_error)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        with pytest.raises(WifiError) as caught:
            await backend.request_scan("wlan0")

        verify(caught.value.category == expected_category)
        verify(caught.value.operation == "nmcli")
        verify(caught.value.__cause__ is process_error)
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize("with_result", [True, False])
def test_nonzero_process_failure_preserves_safe_stderr_and_exit_code(with_result: bool) -> None:
    """Verify command failures use captured data or conservative defaults."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        command = ("device", "wifi", "rescan", "ifname", "wlan0")
        request = ProcessRequest(NMCLI_PATH, command)
        result = (
            process_result(stderr="WiFi is disabled", exit_code=NONZERO_EXIT)
            if with_result
            else None
        )
        process_error = ProcessNonZeroExitError("failed", request, result)
        runner.queue(NMCLI_PATH, command, process_error)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        with pytest.raises(WifiError) as caught:
            await backend.request_scan("wlan0")

        expected = ErrorCategory.WIFI_DISABLED if with_result else ErrorCategory.COMMAND_FAILURE
        verify(caught.value.category == expected)
        verify(caught.value.exit_code == (NONZERO_EXIT if with_result else None))
        verify(caught.value.__cause__ is process_error)
        verify(caught.value.technical_details)
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("stderr", "category"),
    [
        ("NOT AUTHORIZED for operation", ErrorCategory.AUTHORIZATION_DENIED),
        ("Secrets were required", ErrorCategory.MISSING_SECRETS),
        ("Authentication failed", ErrorCategory.AUTHENTICATION_REJECTED),
        ("No network with SSID was found", ErrorCategory.NETWORK_UNAVAILABLE),
        ("DHCP failed", ErrorCategory.IP_CONFIGURATION_FAILED),
        ("NetworkManager is not running", ErrorCategory.NETWORK_MANAGER_UNAVAILABLE),
        ("Wireless is disabled", ErrorCategory.WIFI_DISABLED),
        ("RFKILL hardware switch", ErrorCategory.RADIO_BLOCKED),
        ("unrecognized failure", ErrorCategory.COMMAND_FAILURE),
        ("", ErrorCategory.COMMAND_FAILURE),
    ],
)
def test_command_error_classification_matrix(stderr: str, category: ErrorCategory) -> None:
    """Verify every command-error category and diagnostic field."""
    error = NmcliWifiBackend.classify_command_error(stderr, NONZERO_EXIT, "connect")
    verify(error.category == category)
    verify(error.exit_code == NONZERO_EXIT)
    verify(error.operation == "connect")
    verify(error.technical_details == (stderr.strip() or "nmcli returned a nonzero exit status"))


def test_successful_status_contains_machine_readable_state() -> None:
    """Verify successful status reports version, state, radio, and executable."""

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
            process_result(stdout="enabled:enabled\n"),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        status = await backend.check_status()

        verify(status.availability == BackendAvailability.AVAILABLE)
        verify(status.nmcli_version == "nmcli 1.50")
        verify(status.network_manager_state.value == "connected_global")
        verify(status.wifi_radio == WifiRadioState.ENABLED)
        verify(status.technical_details == f"nmcli={NMCLI_PATH}")
        runner.assert_finished()

    asyncio.run(scenario())
