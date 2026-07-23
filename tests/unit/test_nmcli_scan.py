# Copyright (c) 2026 Phillip Chin
"""Verify nmcli device parsing and scan behavior."""

from __future__ import annotations

import asyncio

import pytest

from tests.assertions import verify
from tests.nmcli_fixtures import NMCLI_PATH, device_status_command, process_result
from tui_wifi.backends.nmcli import NmcliWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import DeviceState, SecurityClass
from tui_wifi.process import ProcessNonZeroExitError, ProcessRequest
from tui_wifi.process.fake import FakeProcessRunner

NONZERO_EXIT = 10
EXPECTED_ACCESS_POINT_COUNT = 11
CHANNEL_14 = 14
CHANNEL_36 = 36


def test_device_parsing_covers_states_filters_and_escaped_connections() -> None:
    """Verify Wi-Fi device state and connection-name parsing."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        runner.queue(
            NMCLI_PATH,
            device_status_command(),
            process_result(
                stdout=(
                    "wlan0:wifi:connected:Home\\:profile\n"
                    "wlan1:wifi:disconnected:--\n"
                    "wlan2:wifi:unavailable:\n"
                    "wlan3:wifi:unmanaged:--\n"
                    "wlan4:wifi:future-state:Future\n"
                    "eth0:ethernet:connected:Wired\n"
                ),
            ),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        devices = await backend.list_wifi_devices()

        verify(
            [device.interface for device in devices]
            == ["wlan0", "wlan1", "wlan2", "wlan3", "wlan4"],
        )
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
        runner.queue(
            NMCLI_PATH,
            device_status_command(),
            process_result(stdout="wlan0:wifi:connected\n"),
        )
        backend = NmcliWifiBackend(runner, NMCLI_PATH)
        with pytest.raises(WifiError) as caught:
            await backend.list_wifi_devices()
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


def test_scan_request_propagates_typed_backend_error() -> None:
    """Verify scan command failures remain typed and visible."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        command = ("device", "wifi", "rescan", "ifname", "wlan0")
        request = ProcessRequest(NMCLI_PATH, command)
        process_error = ProcessNonZeroExitError(
            "failed",
            request,
            process_result(stderr="rfkill blocked", exit_code=NONZERO_EXIT),
        )
        runner.queue(NMCLI_PATH, command, process_error)
        backend = NmcliWifiBackend(runner, NMCLI_PATH)
        with pytest.raises(WifiError) as caught:
            await backend.request_scan("wlan0")
        verify(caught.value.category == ErrorCategory.RADIO_BLOCKED)
        runner.assert_finished()

    asyncio.run(scenario())


def test_access_point_parsing_covers_security_channels_and_blank_policy() -> None:
    """Verify AP parsing covers active state, frequencies, security, and blank rows."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        command = (
            "-t",
            "-e",
            "yes",
            "-f",
            "IN-USE,SSID,BSSID,SIGNAL,FREQ,SECURITY",
            "device",
            "wifi",
            "list",
            "ifname",
            "wlan0",
            "--rescan",
            "no",
        )
        output = (
            "*:Open:00\\:11\\:22\\:33\\:44\\:01:90:2412:--\n"
            ":WPA1:00\\:11\\:22\\:33\\:44\\:02:80:2484:WPA1\n"
            ":WPA2:00\\:11\\:22\\:33\\:44\\:03:70:5180:WPA2\n"
            ":WPA3:00\\:11\\:22\\:33\\:44\\:04:60:5955:SAE\n"
            ":Mixed:00\\:11\\:22\\:33\\:44\\:05:50:5975:WPA2 SAE\n"
            ":Enterprise:00\\:11\\:22\\:33\\:44\\:06:40:6045:WPA2 802.1X\n"
            ":WEP:00\\:11\\:22\\:33\\:44\\:07:30:1234:WEP\n"
            ":Unknown:00\\:11\\:22\\:33\\:44\\:08::7115:future\n"
            ":Cafe\\:West:00\\:11\\:22\\:33\\:44\\:09:20:2417:WPA2\n"
            ": :00\\:11\\:22\\:33\\:44\\:10:10:2412:WPA2\n"
            ": :00\\:11\\:22\\:33\\:44\\:11:10:2412:WPA2\n"
            "::00\\:11\\:22\\:33\\:44\\:12:10:2412:WPA2\n"
        )
        runner.queue(NMCLI_PATH, command, process_result(stdout=output))
        backend = NmcliWifiBackend(runner, NMCLI_PATH)

        access_points = await backend.list_access_points("wlan0")

        verify(len(access_points) == EXPECTED_ACCESS_POINT_COUNT)
        verify(access_points[0].active is True)
        verify(access_points[0].security == SecurityClass.OPEN)
        verify(access_points[1].channel == CHANNEL_14)
        verify(access_points[2].channel == CHANNEL_36)
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


@pytest.mark.parametrize(
    "output",
    [
        ":Home:00\\:11\\:22\\:33\\:44\\:55:101:2412:WPA2\n",
        ":Home:too:few\n",
    ],
)
def test_access_point_parsing_rejects_invalid_signal_or_fields(output: str) -> None:
    """Verify malformed AP values fail visibly."""

    async def scenario() -> None:
        runner = FakeProcessRunner()
        command = (
            "-t",
            "-e",
            "yes",
            "-f",
            "IN-USE,SSID,BSSID,SIGNAL,FREQ,SECURITY",
            "device",
            "wifi",
            "list",
            "ifname",
            "wlan0",
            "--rescan",
            "no",
        )
        runner.queue(NMCLI_PATH, command, process_result(stdout=output))
        backend = NmcliWifiBackend(runner, NMCLI_PATH)
        with pytest.raises(WifiError) as caught:
            await backend.list_access_points("wlan0")
        verify(caught.value.category == ErrorCategory.PARSE_FAILURE)
        runner.assert_finished()

    asyncio.run(scenario())
