from __future__ import annotations

import asyncio

from tui_wifi.backends.nmcli import NmcliWifiBackend
from tui_wifi.models import BackendAvailability, SecurityClass
from tui_wifi.process.fake import FakeProcessRunner
from tui_wifi.process.runner import ProcessResult


def result(stdout: str = "", stderr: str = "", exit_code: int = 0) -> ProcessResult:
    return ProcessResult(("nmcli",), exit_code, stdout, stderr, 0.01)


def test_status_uses_explicit_machine_readable_commands() -> None:
    async def scenario() -> None:
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
        assert status.availability == BackendAvailability.AVAILABLE
        assert status.wifi_radio.value == "enabled"
        runner.assert_finished()

    asyncio.run(scenario())


def test_command_error_classification_is_conservative() -> None:
    backend = NmcliWifiBackend(FakeProcessRunner(), "/usr/bin/nmcli")
    assert backend._classify_command_error(
        "Secrets were required", 4, "connect"
    ).category.value == "missing_secrets"
    assert backend._classify_command_error(
        "authentication failed", 4, "connect"
    ).category.value == "authentication_rejected"
    assert backend._classify_command_error(
        "unrecognized failure", 10, "connect"
    ).category.value == "command_failure"


def test_profile_security() -> None:
    assert NmcliWifiBackend._profile_security("") == SecurityClass.OPEN
    assert NmcliWifiBackend._profile_security("wpa-psk") == SecurityClass.WPA2_PERSONAL
    assert NmcliWifiBackend._profile_security("sae") == SecurityClass.WPA3_PERSONAL
    assert NmcliWifiBackend._profile_security("wpa-eap") == SecurityClass.ENTERPRISE


def test_read_devices_and_access_points() -> None:
    async def scenario() -> None:
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
                ":Hidden:00\\:11\\:22\\:33\\:44\\:66:50:5180:WPA2 802.1X\n"
            ),
        )
        backend = NmcliWifiBackend(runner, "/usr/bin/nmcli")
        devices = await backend.list_wifi_devices()
        access_points = await backend.list_access_points("wlan0")
        assert len(devices) == 1
        assert devices[0].active_connection == "Home:profile"
        assert access_points[0].display_ssid == "Home:West"
        assert access_points[0].channel == 1
        assert access_points[1].security == SecurityClass.ENTERPRISE
        runner.assert_finished()

    asyncio.run(scenario())
