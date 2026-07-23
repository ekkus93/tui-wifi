# Copyright (c) 2026 Phillip Chin
"""Define structured, user-presentable Wi-Fi failures."""

from __future__ import annotations

from enum import StrEnum
from typing import TypedDict, Unpack


class ErrorCategory(StrEnum):
    """Identify stable failure categories exposed by the application."""

    MISSING_NMCLI = "missing_nmcli"
    NETWORK_MANAGER_UNAVAILABLE = "network_manager_unavailable"
    NO_ADAPTER = "no_adapter"
    UNMANAGED_ADAPTER = "unmanaged_adapter"
    WIFI_DISABLED = "wifi_disabled"
    RADIO_BLOCKED = "radio_blocked"
    AUTHORIZATION_DENIED = "authorization_denied"
    AUTHENTICATION_REJECTED = "authentication_rejected"
    MISSING_SECRETS = "missing_secrets"
    NETWORK_UNAVAILABLE = "network_unavailable"
    UNSUPPORTED_SECURITY = "unsupported_security"
    IP_CONFIGURATION_FAILED = "ip_configuration_failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PARSE_FAILURE = "parse_failure"
    COMMAND_FAILURE = "command_failure"
    VERIFICATION_FAILURE = "verification_failure"
    INTERNAL_FAILURE = "internal_failure"


_DEFAULTS: dict[ErrorCategory, tuple[str, str | None, bool]] = {
    ErrorCategory.MISSING_NMCLI: (
        "The nmcli utility is not installed.",
        "Install NetworkManager's command-line tools and try again.",
        False,
    ),
    ErrorCategory.NETWORK_MANAGER_UNAVAILABLE: (
        "NetworkManager is not available.",
        "Start NetworkManager and verify that your user can access it.",
        True,
    ),
    ErrorCategory.NO_ADAPTER: ("No Wi-Fi adapter was found.", None, True),
    ErrorCategory.UNMANAGED_ADAPTER: (
        "The Wi-Fi adapter is not managed by NetworkManager.",
        "Configure NetworkManager to manage this interface.",
        False,
    ),
    ErrorCategory.WIFI_DISABLED: ("Wi-Fi is disabled.", "Enable Wi-Fi and try again.", True),
    ErrorCategory.RADIO_BLOCKED: (
        "Wi-Fi is blocked by a hardware or software switch.",
        "Clear the rfkill block or hardware switch before retrying.",
        True,
    ),
    ErrorCategory.AUTHORIZATION_DENIED: (
        "NetworkManager denied this operation.",
        "Check Polkit permissions for your user.",
        False,
    ),
    ErrorCategory.AUTHENTICATION_REJECTED: (
        "The Wi-Fi password was rejected.",
        "Check the password and try again.",
        True,
    ),
    ErrorCategory.MISSING_SECRETS: (
        "This saved connection is missing required credentials.",
        "Enter the network password to reconnect.",
        True,
    ),
    ErrorCategory.NETWORK_UNAVAILABLE: (
        "The network is no longer available.",
        "Rescan and move closer to the access point.",
        True,
    ),
    ErrorCategory.UNSUPPORTED_SECURITY: (
        "This network uses a security method that tui-wifi does not support.",
        None,
        False,
    ),
    ErrorCategory.IP_CONFIGURATION_FAILED: (
        "Connected to Wi-Fi, but could not obtain a usable IP configuration.",
        "Check the network's DHCP service and try again.",
        True,
    ),
    ErrorCategory.TIMEOUT: ("The operation timed out.", "Try again.", True),
    ErrorCategory.CANCELLED: ("The operation was cancelled.", None, True),
    ErrorCategory.PARSE_FAILURE: (
        "NetworkManager returned data that tui-wifi could not understand.",
        "Open technical details and report the redacted output.",
        False,
    ),
    ErrorCategory.COMMAND_FAILURE: ("NetworkManager could not complete the operation.", None, True),
    ErrorCategory.VERIFICATION_FAILURE: (
        "NetworkManager reported success, but the resulting state could not be verified.",
        "Refresh the network state before retrying.",
        True,
    ),
    ErrorCategory.INTERNAL_FAILURE: (
        "tui-wifi encountered an unexpected internal error.",
        "Open technical details and report the redacted error.",
        False,
    ),
}


class WifiErrorOptions(TypedDict, total=False):
    """Describe optional structured fields accepted by :class:`WifiError`."""

    summary: str | None
    guidance: str | None
    technical_details: str | None
    exit_code: int | None
    backend_reason: str | None
    retriable: bool | None
    operation: str | None


class WifiError(Exception):
    """Carry a user-facing summary and redacted technical diagnostics."""

    def __init__(
        self,
        category: ErrorCategory,
        **options: Unpack[WifiErrorOptions],
    ) -> None:
        """Initialize a structured Wi-Fi error."""
        default_summary, default_guidance, default_retriable = _DEFAULTS[category]
        summary = options.get("summary")
        guidance = options.get("guidance")
        retriable = options.get("retriable")

        self.category = category
        self.summary = summary or default_summary
        self.guidance = guidance if guidance is not None else default_guidance
        self.technical_details = options.get("technical_details")
        self.exit_code = options.get("exit_code")
        self.backend_reason = options.get("backend_reason")
        self.retriable = default_retriable if retriable is None else retriable
        self.operation = options.get("operation")
        super().__init__(self.summary)

    def __str__(self) -> str:
        """Return the user-facing error summary."""
        return self.summary

    def diagnostic_text(self) -> str:
        """Return redacted diagnostic fields for troubleshooting."""
        fields = [f"category={self.category.value}"]
        if self.operation:
            fields.append(f"operation={self.operation}")
        if self.exit_code is not None:
            fields.append(f"exit_code={self.exit_code}")
        if self.backend_reason:
            fields.append(f"reason={self.backend_reason}")
        if self.technical_details:
            fields.append(self.technical_details)
        return "\n".join(fields)
