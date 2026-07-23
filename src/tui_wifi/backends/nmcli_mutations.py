"""Provide NetworkManager mutation operations through ``nmcli``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tui_wifi.backends.nmcli_profiles import NmcliProfilesMixin
from tui_wifi.errors import ErrorCategory, WifiError

if TYPE_CHECKING:
    from tui_wifi.backends.base import (
        DisconnectRequest,
        HiddenConnectRequest,
        SavedProfileRequest,
        VisibleConnectRequest,
    )
    from tui_wifi.models import ActiveWifiConnection, SavedProfile, SecurityClass


class NmcliMutationsMixin(NmcliProfilesMixin):
    """Implement connection mutations and verify their resulting state."""

    async def activate_saved_profile(self, request: SavedProfileRequest) -> ActiveWifiConnection:
        """Activate a saved profile on the requested interface."""
        await self._run(
            (
                "--wait",
                "45",
                "connection",
                "up",
                "uuid",
                request.uuid,
                "ifname",
                request.interface,
            ),
            timeout_seconds=self.CONNECT_TIMEOUT,
        )
        return await self._verify_active(request.interface, request.uuid)

    async def connect_visible_network(self, request: VisibleConnectRequest) -> ActiveWifiConnection:
        """Connect to a visible personal or open Wi-Fi network."""
        self._validate_connect_security(request.security, has_password=request.password is not None)
        args = [
            "--wait",
            "45",
            "device",
            "wifi",
            "connect",
            request.ssid,
            "ifname",
            request.interface,
        ]
        sensitive: set[int] = set()
        if request.bssid:
            args.extend(("bssid", request.bssid))
        if request.password is not None:
            args.extend(("password", request.password.reveal()))
            sensitive.add(len(args) - 1)
        await self._run(
            tuple(args),
            timeout_seconds=self.CONNECT_TIMEOUT,
            sensitive_arg_indexes=frozenset(sensitive),
        )
        active = await self._verify_active(request.interface, None, request.ssid)
        if not request.autoconnect:
            await self.set_profile_autoconnect(active.uuid, enabled=False)
        return active

    async def connect_hidden_network(self, request: HiddenConnectRequest) -> ActiveWifiConnection:
        """Connect to a hidden personal or open Wi-Fi network."""
        if not request.ssid:
            raise WifiError(
                ErrorCategory.NETWORK_UNAVAILABLE,
                summary="The hidden SSID cannot be blank.",
            )
        self._validate_connect_security(request.security, has_password=request.password is not None)
        args = [
            "--wait",
            "45",
            "device",
            "wifi",
            "connect",
            request.ssid,
            "ifname",
            request.interface,
            "hidden",
            "yes",
        ]
        sensitive: set[int] = set()
        if request.password is not None:
            args.extend(("password", request.password.reveal()))
            sensitive.add(len(args) - 1)
        await self._run(
            tuple(args),
            timeout_seconds=self.CONNECT_TIMEOUT,
            sensitive_arg_indexes=frozenset(sensitive),
        )
        active = await self._verify_active(request.interface, None, request.ssid)
        if not request.autoconnect:
            await self.set_profile_autoconnect(active.uuid, enabled=False)
        return active

    @staticmethod
    def _validate_connect_security(security: SecurityClass, *, has_password: bool) -> None:
        """Reject unsupported security and missing required credentials."""
        if not security.supported:
            raise WifiError(ErrorCategory.UNSUPPORTED_SECURITY)
        if security.requires_password and not has_password:
            raise WifiError(ErrorCategory.MISSING_SECRETS)

    async def _verify_active(
        self,
        interface: str,
        uuid: str | None,
        ssid: str | None = None,
    ) -> ActiveWifiConnection:
        """Verify the expected active connection after a mutation."""
        active = await self.get_active_wifi_connection()
        if active is None or active.device != interface:
            raise WifiError(
                ErrorCategory.VERIFICATION_FAILURE,
                technical_details=f"no active Wi-Fi connection on {interface}",
            )
        if uuid is not None and active.uuid != uuid:
            raise WifiError(
                ErrorCategory.VERIFICATION_FAILURE,
                technical_details=f"expected UUID {uuid}, observed {active.uuid}",
            )
        if ssid is not None and active.ssid != ssid:
            raise WifiError(
                ErrorCategory.VERIFICATION_FAILURE,
                technical_details=f"expected SSID {ssid!r}, observed {active.ssid!r}",
            )
        return active

    async def disconnect(self, request: DisconnectRequest) -> None:
        """Disconnect one Wi-Fi interface and verify it is inactive."""
        await self._run(
            ("--wait", "15", "device", "disconnect", request.interface),
            timeout_seconds=self.MUTATION_TIMEOUT,
        )
        active = await self.get_active_wifi_connection()
        if active is not None and active.device == request.interface:
            raise WifiError(
                ErrorCategory.VERIFICATION_FAILURE,
                technical_details=f"device {request.interface} remained connected",
            )

    async def delete_saved_profile(self, uuid: str) -> None:
        """Delete a saved profile and verify its removal."""
        await self._run(
            ("connection", "delete", "uuid", uuid),
            timeout_seconds=self.MUTATION_TIMEOUT,
        )
        profiles = await self.list_saved_wifi_profiles()
        if any(profile.uuid == uuid for profile in profiles):
            raise WifiError(
                ErrorCategory.VERIFICATION_FAILURE,
                technical_details=f"profile {uuid} still exists after deletion",
            )

    async def set_profile_autoconnect(self, uuid: str, *, enabled: bool) -> SavedProfile:
        """Set auto-connect on a profile and verify the stored value."""
        await self._run(
            (
                "connection",
                "modify",
                "uuid",
                uuid,
                "connection.autoconnect",
                "yes" if enabled else "no",
            ),
            timeout_seconds=self.MUTATION_TIMEOUT,
        )
        profiles = await self.list_saved_wifi_profiles()
        profile = next((item for item in profiles if item.uuid == uuid), None)
        if profile is None or profile.autoconnect != enabled:
            raise WifiError(
                ErrorCategory.VERIFICATION_FAILURE,
                technical_details=f"autoconnect verification failed for {uuid}",
            )
        return profile

    async def get_connection_details(self) -> ActiveWifiConnection | None:
        """Return details for the active Wi-Fi connection."""
        return await self.get_active_wifi_connection()
