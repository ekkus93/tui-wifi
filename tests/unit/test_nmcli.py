"""Verify test nmcli behavior."""

from __future__ import annotations

import asyncio

from tests.assertions import verify
from tui_wifi.backends.nmcli import NmcliWifiBackend
from tui_wifi.models import BackendAvailability, SecurityClass
from tui_wifi.process.fake import FakeProcessRunner
from tui_wifi.process.runner import ProcessResult


def result(stdout: str = "", stderr: str = "", exit_code: int = 0) -> ProcessResult:
    """Perform result."""
    return ProcessResult(("nmcli",), exit_code, stdout, stderr, 0.01)


def test_status_uses_explicit_machine_readable_commands() -> None:
    """Verify test status uses explicit machine readable commands."""

    async def scenario() -> None:
        """Perform scenario."""
        runner = FakeProcessRunner()
        runner.queue("/usr/bin/nmcli", ("--version",), result("nmcli tool, version 1.50\n"))
        runner.queue(
            "/usr/bin/nmcli",
            ("-t", "-e", "yes", "-f", "STATE", "general"),
            result("connected (global)\n"),
        )
        runner.queue(
            "/usr/bin/nmcli",
            ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"),
            result("enabled:enabled\n"),
        )
        status = await NmcliWifiBackend(runner, "/usr/bin/nmcli").check_status()
        verify(status.availability == BackendAvailability.AVAILABLE)
        verify(status.wifi_radio.value == "enabled")
        runner.assert_finished()

    asyncio.run(scenario())


def test_command_error_classification_is_conservative() -> None:
    """Verify test command error classification is conservative."""
    backend = NmcliWifiBackend(FakeProcessRunner(), "/usr/bin/nmcli")
    verify(
        backend._classify_command_error("Secrets were required", 4, "connect").category.value
        == "missing_secrets",
    )
    verify(
        backend._classify_command_error("authentication failed", 4, "connect").category.value
        == "authentication_rejected",
    )
    verify(
        backend._classify_command_error("unrecognized failure", 10, "connect").category.value
        == "command_failure",
    )


def test_profile_security() -> None:
    """Verify test profile security."""
    verify(NmcliWifiBackend._profile_security("") == SecurityClass.OPEN)
    verify(NmcliWifiBackend._profile_security("wpa-psk") == SecurityClass.WPA2_PERSONAL)
    verify(NmcliWifiBackend._profile_security("sae") == SecurityClass.WPA3_PERSONAL)
    verify(NmcliWifiBackend._profile_security("wpa-eap") == SecurityClass.ENTERPRISE)


def test_read_devices_and_access_points() -> None:
    """Verify test read devices and access points."""

    async def scenario() -> None:
        """Perform scenario."""
        runner = FakeProcessRunner()
        runner.queue(
            "/usr/bin/nmcli",
            ("-t", "-e", "yes", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"),
            result("wlan0:wifi:connected:Home\\:profile\neth0:ethernet:connected:Wired\n"),
        )
        runner.queue(
            "/usr/bin/nmcli",
            (
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
            ),
            result(
                "*:Home\\:West:00\\:11\\:22\\:33\\:44\\:55:91:2412:WPA2\n"
                ":Hidden:00\\:11\\:22\\:33\\:44\\:66:50:5180:WPA2 802.1X\n",
            ),
        )
        backend = NmcliWifiBackend(runner, "/usr/bin/nmcli")
        devices = await backend.list_wifi_devices()
        access_points = await backend.list_access_points("wlan0")
        verify(len(devices) == 1)
        verify(devices[0].active_connection == "Home:profile")
        verify(access_points[0].display_ssid == "Home:West")
        verify(access_points[0].channel == 1)
        verify(access_points[1].security == SecurityClass.ENTERPRISE)
        runner.assert_finished()

    asyncio.run(scenario())
