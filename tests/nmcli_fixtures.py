# Copyright (c) 2026 Phillip Chin
"""Provide reusable nmcli command and result fixtures."""

from __future__ import annotations

from tui_wifi.process import ProcessResult

NMCLI_PATH = "/usr/bin/nmcli"


def process_result(
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    timed_out: bool = False,
    cancelled: bool = False,
) -> ProcessResult:
    """Build a process result without embedding sensitive command arguments."""
    return ProcessResult(
        command=(NMCLI_PATH,),
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration=0.01,
        timed_out=timed_out,
        cancelled=cancelled,
    )


def device_status_command() -> tuple[str, ...]:
    """Return the exact machine-readable device-status command."""
    return ("-t", "-e", "yes", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status")


def active_detail_command(interface: str = "wlan0") -> tuple[str, ...]:
    """Return the exact active-connection detail command."""
    return (
        "-t",
        "-e",
        "yes",
        "-f",
        (
            "GENERAL.CONNECTION,GENERAL.CON-UUID,GENERAL.STATE,IP4.ADDRESS,IP4.GATEWAY,"
            "IP4.DNS,IP6.ADDRESS,IP6.GATEWAY,IP6.DNS"
        ),
        "device",
        "show",
        interface,
    )


def ssid_query_command(uuid: str) -> tuple[str, ...]:
    """Return the exact profile SSID query command."""
    return (
        "-t",
        "-e",
        "yes",
        "-g",
        "802-11-wireless.ssid",
        "connection",
        "show",
        "uuid",
        uuid,
    )


def profile_summary_command() -> tuple[str, ...]:
    """Return the exact saved-profile summary command."""
    return (
        "-t",
        "-e",
        "yes",
        "-f",
        "NAME,UUID,TYPE,DEVICE,AUTOCONNECT",
        "connection",
        "show",
    )


def profile_detail_command(uuid: str) -> tuple[str, ...]:
    """Return the exact saved-profile detail command."""
    return (
        "-t",
        "-e",
        "yes",
        "-g",
        (
            "802-11-wireless.ssid,802-11-wireless-security.key-mgmt,"
            "connection.interface-name,connection.autoconnect"
        ),
        "connection",
        "show",
        "uuid",
        uuid,
    )
