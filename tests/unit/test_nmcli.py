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
        runner.queue(NMCLI_PATH, ("device", "wifi", "rescan", "ifname", "wlan0"), process_result())
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
        runner.queue(NMCLI_PATH, ("device", "wifi", "rescan", "ifname", "wlan0"), process_result())
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
        status = await NmcliWifiBackend(runner).check_status()
        verify(status.availability == BackendAvailability.MISSING_EXECUTABLE)
        verify(runner.requests == [])

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("process_error", "expected_category"),
    [
        (ProcessMissingExecutableError("missing", ProcessRequest(MISSING_PATH)), ErrorCategory.MISSING_NMCLI),
        (ProcessTimeoutError("timeout", ProcessRequest(NMCLI_PATH)), ErrorCategory.TIMEOUT),
    ],
)
def test_process_failures_translate_to_typed_wifi_errors(process_error: Exception, expected_category: ErrorCategory) -> None:
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
        result = process_result(stderr="WiFi is disabled", exit_code=NONZERO_EXIT) if with_result else None
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
        runner.queue(NMCLI_PATH, ("-t", "-e", "yes", "-f", "STATE", "general"), process_result(stdout="connected (global)\n"))
        runner.queue(NMCLI_PATH, ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"), process_result(stdout="enabled:enabled\n"))
        backend = NmcliWifiBackend(runner, NMCLI_PATH)
        status = await backend.check_status()
        verify(status.availability == BackendAvailability.AVAILABLE)
        verify(status.nmcli_version == "nmcli 1.50")
        verify(status.network_manager_state.value == "connected_global")
        verify(status.wifi_radio == WifiRadioState.ENABLED)
        verify(status.technical_details == f"nmcli={NMCLI_PATH}")
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(("failure", "availability"), [("permission denied", BackendAvailability.UNAUTHORIZED), ("unexpected command error", BackendAvailability.UNAVAILABLE)])
def test_status_command_failures_map_to_availability(failure: str, availability: BackendAvailability) -> None:
    """Verify authorization and generic failures become explicit status values."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        request = ProcessRequest(NMCLI_PATH, ("--version",))
        error = ProcessNonZeroExitError("failed", request, process_result(stderr=failure, exit_code=NONZERO_EXIT))
        runner.queue(NMCLI_PATH, ("--version",), error)
        status = await NmcliWifiBackend(runner, NMCLI_PATH).check_status()
        verify(status.availability == availability)
        verify("category=" in (status.technical_details or ""))
        runner.assert_finished()

    asyncio.run(scenario())


def test_status_parse_failure_returns_unavailable() -> None:
    """Verify malformed status output cannot be reported as available."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(NMCLI_PATH, ("--version",), process_result(stdout="nmcli 1.50\n"))
        runner.queue(NMCLI_PATH, ("-t", "-e", "yes", "-f", "STATE", "general"), process_result(stdout="connected (global)\n"))
        runner.queue(NMCLI_PATH, ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"), process_result(stdout="not-two-fields\n"))
        status = await NmcliWifiBackend(runner, NMCLI_PATH).check_status()
        verify(status.availability == BackendAvailability.UNAVAILABLE)
        verify("parse_failure" in (status.technical_details or ""))
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize(("output", "expected"), [("enabled:enabled\n", WifiRadioState.ENABLED), ("disabled:enabled\n", WifiRadioState.DISABLED), ("enabled:disabled\n", WifiRadioState.HARDWARE_BLOCKED), ("disabled:disabled\n", WifiRadioState.HARDWARE_BLOCKED)])
def test_radio_state_matrix(output: str, expected: WifiRadioState) -> None:
    """Verify software and hardware radio values combine conservatively."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(NMCLI_PATH, ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"), process_result(stdout=output))
        state = await NmcliWifiBackend(runner, NMCLI_PATH).get_wifi_radio_state()
        verify(state == expected)
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize("output", ["one-field\n", "enabled:maybe\n"])
def test_radio_state_rejects_malformed_output(output: str) -> None:
    """Verify malformed field counts and booleans are parse failures."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(NMCLI_PATH, ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"), process_result(stdout=output))
        with pytest.raises(WifiError) as caught:
            await NmcliWifiBackend(runner, NMCLI_PATH).get_wifi_radio_state()
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
        runner.queue(NMCLI_PATH, ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"), process_result(stdout=state_output))
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
        runner.queue(NMCLI_PATH, ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"), process_result(stdout="disabled:enabled\n"))
        backend = NmcliWifiBackend(runner, NMCLI_PATH)
        with pytest.raises(WifiError) as caught:
            await backend.set_wifi_radio_state(enabled=True)
        verify(caught.value.category == ErrorCategory.VERIFICATION_FAILURE)
        verify("expected radio=enabled" in (caught.value.technical_details or ""))
        runner.assert_finished()

    asyncio.run(scenario())


def test_device_parsing_covers_states_filters_and_escaped_connections() -> None:
    """Verify Wi-Fi device state and connection-name parsing."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(NMCLI_PATH, device_status_command(), process_result(stdout="wlan0:wifi:connected:Home\\:profile\nwlan1:wifi:disconnected:--\nwlan2:wifi:unavailable:\nwlan3:wifi:unmanaged:--\nwlan4:wifi:future-state:Future\neth0:ethernet:connected:Wired\n"))
        devices = await NmcliWifiBackend(runner, NMCLI_PATH).list_wifi_devices()
        verify([device.interface for device in devices] == ["wlan0", "wlan1", "wlan2", "wlan3", "wlan4"])
        verify(devices[0].state == DeviceState.ACTIVATED)
        verify(devices[0].active_connection == "Home:profile")
        verify(devices[1].active_connection is None)
        verify(devices[2].active_connection is None)
        verify(devices[3].managed is False)
        verify(devices[4].state == DeviceState.UNKNOWN)
        runner.assert_finished()

    asyncio.run(scenario())


def test_device_parsing_rejects_malformed_row() -> None:
    """Verify malformed Wi-Fi rows are visible parse failures."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(NMCLI_PATH, device_status_command(), process_result(stdout="wlan0:wifi:connected\n"))
        with pytest.raises(WifiError) as caught:
            await NmcliWifiBackend(runner, NMCLI_PATH).list_wifi_devices()
        verify(caught.value.category == ErrorCategory.PARSE_FAILURE)
        runner.assert_finished()

    asyncio.run(scenario())


def test_scan_request_uses_exact_interface_and_timeout() -> None:
    """Verify explicit scanning uses no hidden list-side rescan."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        command = ("device", "wifi", "rescan", "ifname", "wlan9")
        runner.queue(NMCLI_PATH, command, process_result())
        backend = NmcliWifiBackend(runner, NMCLI_PATH)
        await backend.request_scan("wlan9")
        verify(runner.requests[0].args == command)
        verify(runner.requests[0].timeout == backend.SCAN_TIMEOUT)
        runner.assert_finished()

    asyncio.run(scenario())


def test_access_point_parsing_covers_security_channels_and_blank_policy() -> None:
    """Verify AP parsing covers active state, frequencies, security, and blank rows."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        command = ("-t", "-e", "yes", "-f", "IN-USE,SSID,BSSID,SIGNAL,FREQ,SECURITY", "device", "wifi", "list", "ifname", "wlan0", "--rescan", "no")
        output = "*:Open:00\\:11\\:22\\:33\\:44\\:01:90:2412:--\n:WPA1:00\\:11\\:22\\:33\\:44\\:02:80:2484:WPA1\n:WPA2:00\\:11\\:22\\:33\\:44\\:03:70:5180:WPA2\n:WPA3:00\\:11\\:22\\:33\\:44\\:04:60:5955:SAE\n:Mixed:00\\:11\\:22\\:33\\:44\\:05:50:5975:WPA2 SAE\n:Enterprise:00\\:11\\:22\\:33\\:44\\:06:40:6045:WPA2 802.1X\n:WEP:00\\:11\\:22\\:33\\:44\\:07:30:1234:WEP\n:Unknown:00\\:11\\:22\\:33\\:44\\:08::7115:future\n:Cafe\\:West:00\\:11\\:22\\:33\\:44\\:09:20:2417:WPA2\n: :00\\:11\\:22\\:33\\:44\\:10:10:2412:WPA2\n: :00\\:11\\:22\\:33\\:44\\:11:10:2412:WPA2\n::00\\:11\\:22\\:33\\:44\\:12:10:2412:WPA2\n"
        runner.queue(NMCLI_PATH, command, process_result(stdout=output))
        backend = NmcliWifiBackend(runner, NMCLI_PATH)
        access_points = await backend.list_access_points("wlan0")
        verify(len(access_points) == 11)
        verify(access_points[0].active is True)
        verify(access_points[0].security == SecurityClass.OPEN)
        verify(access_points[1].channel == 14)
        verify(access_points[2].channel == 36)
        verify(access_points[3].channel == 1)
        verify(access_points[4].security == SecurityClass.MIXED_PERSONAL)
        verify(access_points[5].security == SecurityClass.ENTERPRISE)
        verify(access_points[6].security == SecurityClass.WEP)
        verify(access_points[6].channel is None)
        verify(access_points[7].security == SecurityClass.UNKNOWN)
        verify(access_points[7].signal is None)
        verify(access_points[8].display_ssid == "Cafe:West")
        verify("--rescan" in runner.requests[0].args)
        verify(runner.requests[0].args[-1] == "no")
        runner.assert_finished()

    asyncio.run(scenario())


@pytest.mark.parametrize("output", [":Home:00\\:11\\:22\\:33\\:44\\:55:101:2412:WPA2\n", ":Home:too:few\n"])
def test_access_point_parsing_rejects_invalid_signal_or_fields(output: str) -> None:
    """Verify malformed AP values fail visibly."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        command = ("-t", "-e", "yes", "-f", "IN-USE,SSID,BSSID,SIGNAL,FREQ,SECURITY", "device", "wifi", "list", "ifname", "wlan0", "--rescan", "no")
        runner.queue(NMCLI_PATH, command, process_result(stdout=output))
        with pytest.raises(WifiError) as caught:
            await NmcliWifiBackend(runner, NMCLI_PATH).list_access_points("wlan0")
        verify(caught.value.category == ErrorCategory.PARSE_FAILURE)
        runner.assert_finished()

    asyncio.run(scenario())
