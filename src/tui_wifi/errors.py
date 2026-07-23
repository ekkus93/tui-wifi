from __future__ import annotations

from enum import Enum


class ErrorCategory(str, Enum):
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


class WifiError(Exception):
    """Structured, user-presentable failure with redacted diagnostics."""

    def __init__(
        self,
        category: ErrorCategory,
        *,
        summary: str | None = None,
        guidance: str | None = None,
        technical_details: str | None = None,
        exit_code: int | None = None,
        backend_reason: str | None = None,
        retriable: bool | None = None,
        operation: str | None = None,
    ) -> None:
        default_summary, default_guidance, default_retriable = _DEFAULTS[category]
        self.category = category
        self.summary = summary or default_summary
        self.guidance = guidance if guidance is not None else default_guidance
        self.technical_details = technical_details
        self.exit_code = exit_code
        self.backend_reason = backend_reason
        self.retriable = default_retriable if retriable is None else retriable
        self.operation = operation
        super().__init__(self.summary)

    def __str__(self) -> str:
        return self.summary

    def diagnostic_text(self) -> str:
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
