"""Coordinate coherent Wi-Fi state and backend mutations."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tui_wifi.backends.base import (
    DisconnectRequest,
    HiddenConnectRequest,
    SavedProfileRequest,
    VisibleConnectRequest,
    WifiBackend,
)
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.grouping import group_networks
from tui_wifi.models import (
    AccessPoint,
    ApplicationSnapshot,
    BackendAvailability,
    BackendStatus,
    DeviceState,
    NetworkGroup,
    OperationKind,
    OperationPhase,
    OperationStatus,
    SavedProfile,
    SecurityClass,
    WifiDevice,
    WifiRadioState,
)

if TYPE_CHECKING:
    from tui_wifi.secrets import SecretValue

SnapshotListener = Callable[[ApplicationSnapshot], None]


class WifiService:
    """Maintain coherent application state around one Wi-Fi backend."""

    def __init__(self, backend: WifiBackend, preferred_interface: str | None = None) -> None:
        """Initialize the service with a backend and optional preferred interface."""
        self.backend = backend
        self.preferred_interface = preferred_interface
        self.snapshot = ApplicationSnapshot(BackendStatus(BackendAvailability.UNKNOWN))
        self._listeners: list[SnapshotListener] = []
        self._refresh_generation = 0
        self.operation_counter = 0
        self.mutation_lock = asyncio.Lock()
        self._closed = False

    def subscribe(self, listener: SnapshotListener) -> Callable[[], None]:
        """Subscribe to coherent snapshot updates and return an unsubscribe callback."""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            """Remove the listener when it is still registered."""
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def publish(self, snapshot: ApplicationSnapshot) -> None:
        """Publish one coherent snapshot to all current listeners."""
        self.snapshot = snapshot
        for listener in tuple(self._listeners):
            listener(snapshot)

    async def startup(self) -> ApplicationSnapshot:
        """Validate the platform and load the initial Wi-Fi state."""
        if not sys.platform.startswith("linux"):
            error = WifiError(
                ErrorCategory.INTERNAL_FAILURE,
                summary="tui-wifi currently supports Linux only.",
            )
            self.publish(replace(self.snapshot, error=error.summary))
            return self.snapshot
        return await self.refresh(request_scan=True)

    async def refresh(self, *, request_scan: bool = False) -> ApplicationSnapshot:
        """Load one coherent backend snapshot, optionally requesting a scan first."""
        if self._closed:
            return self.snapshot
        self._refresh_generation += 1
        generation = self._refresh_generation
        previous = self.snapshot
        operation = OperationStatus(
            OperationKind.SCAN if request_scan else OperationKind.REFRESH,
            OperationPhase.RUNNING,
            operation_id=generation,
            message="Scanning for networks…" if request_scan else "Refreshing network state…",
        )
        self.publish(replace(previous, operation=operation, error=None))
        try:
            status = await self.backend.check_status()
            if status.availability != BackendAvailability.AVAILABLE:
                raise self._status_error(status)
            radio = await self.backend.get_wifi_radio_state()
            status = replace(status, wifi_radio=radio)
            devices = await self.backend.list_wifi_devices()
            selected = self._select_device(devices)
            active = await self.backend.get_active_wifi_connection()
            profiles = await self.backend.list_saved_wifi_profiles()
            access_points: tuple[AccessPoint, ...] = ()
            warning = None
            if selected is not None and radio == WifiRadioState.ENABLED:
                if request_scan:
                    try:
                        await self.backend.request_scan(selected)
                    except WifiError as exc:
                        warning = f"Scan request failed: {exc.summary}"
                access_points = await self.backend.list_access_points(selected)
            networks = group_networks(access_points, profiles, active)
            candidate = ApplicationSnapshot(
                status=status,
                devices=devices,
                selected_device=selected,
                networks=networks,
                profiles=profiles,
                active_connection=active,
                operation=OperationStatus(
                    operation.kind,
                    OperationPhase.SUCCEEDED,
                    operation_id=generation,
                ),
                last_refresh=datetime.now(UTC),
                warning=warning,
                stale=False,
                generation=generation,
            )
        except WifiError as exc:
            candidate = replace(
                previous,
                operation=OperationStatus(
                    operation.kind,
                    OperationPhase.FAILED,
                    message=exc.summary,
                    operation_id=generation,
                ),
                error=exc.summary,
                warning=exc.guidance,
                stale=bool(previous.networks or previous.devices),
                generation=generation,
            )
        if generation == self._refresh_generation:
            self.publish(candidate)
        return self.snapshot

    @staticmethod
    def _status_error(status: BackendStatus) -> WifiError:
        """Translate backend availability into a structured error."""
        if status.availability == BackendAvailability.MISSING_EXECUTABLE:
            return WifiError(ErrorCategory.MISSING_NMCLI)
        if status.availability == BackendAvailability.UNAUTHORIZED:
            return WifiError(ErrorCategory.AUTHORIZATION_DENIED)
        return WifiError(ErrorCategory.NETWORK_MANAGER_UNAVAILABLE)

    def _select_device(self, devices: tuple[WifiDevice, ...]) -> str | None:
        """Select one managed adapter without silently choosing among ambiguous devices."""
        managed = tuple(device for device in devices if device.managed)
        if self.preferred_interface:
            selected = next(
                (device for device in managed if device.interface == self.preferred_interface),
                None,
            )
            if selected is None:
                raise WifiError(
                    ErrorCategory.NO_ADAPTER,
                    summary=f"Wi-Fi interface {self.preferred_interface!r} is unavailable.",
                )
            return selected.interface
        active = next(
            (device for device in managed if device.state == DeviceState.ACTIVATED),
            None,
        )
        if active:
            return active.interface
        if len(managed) == 1:
            return managed[0].interface
        if not managed:
            return None
        interfaces = ", ".join(sorted(device.interface for device in managed))
        raise WifiError(
            ErrorCategory.NO_ADAPTER,
            summary=(
                "Multiple Wi-Fi adapters are available. "
                f"Restart with --interface NAME ({interfaces})."
            ),
        )

    async def connect_network(
        self,
        group: NetworkGroup,
        *,
        password: SecretValue | None = None,
        autoconnect: bool = True,
    ) -> ApplicationSnapshot:
        """Connect to a visible network and clear any supplied password afterward."""
        if not group.supported:
            raise WifiError(ErrorCategory.UNSUPPORTED_SECURITY)
        interface = self._require_interface()
        try:
            async with self._mutation(
                OperationKind.CONNECT,
                group.display_ssid,
                "Connecting to the network…",
            ):
                if len(group.saved_profile_uuids) == 1 and password is None:
                    await self.backend.activate_saved_profile(
                        SavedProfileRequest(group.saved_profile_uuids[0], interface),
                    )
                else:
                    bssid = group.member_bssids[0] if len(group.member_bssids) == 1 else None
                    await self.backend.connect_visible_network(
                        VisibleConnectRequest(
                            group.display_ssid,
                            interface,
                            group.security,
                            password,
                            bssid,
                            autoconnect,
                        ),
                    )
        finally:
            if password is not None:
                password.clear()
        return await self.refresh()

    async def connect_hidden(
        self,
        ssid: str,
        security: SecurityClass,
        password: SecretValue | None,
        *,
        autoconnect: bool,
    ) -> ApplicationSnapshot:
        """Connect to a hidden network and clear any supplied password afterward."""
        interface = self._require_interface()
        try:
            async with self._mutation(
                OperationKind.CONNECT,
                ssid,
                "Connecting to hidden network…",
            ):
                await self.backend.connect_hidden_network(
                    HiddenConnectRequest(
                        ssid,
                        interface,
                        security,
                        password,
                        autoconnect,
                    ),
                )
        finally:
            if password is not None:
                password.clear()
        return await self.refresh()

    async def disconnect(self) -> ApplicationSnapshot:
        """Disconnect the active Wi-Fi connection when one exists."""
        active = self.snapshot.active_connection
        if active is None:
            return self.snapshot
        async with self._mutation(
            OperationKind.DISCONNECT,
            active.ssid,
            "Disconnecting…",
        ):
            await self.backend.disconnect(DisconnectRequest(active.device, active.uuid))
        return await self.refresh()

    async def set_wifi_enabled(self, *, enabled: bool) -> ApplicationSnapshot:
        """Enable or disable the Wi-Fi radio and refresh the resulting state."""
        async with self._mutation(
            OperationKind.RADIO,
            "Wi-Fi",
            "Enabling Wi-Fi…" if enabled else "Disabling Wi-Fi…",
        ):
            await self.backend.set_wifi_radio_state(enabled=enabled)
        return await self.refresh(request_scan=enabled)

    async def delete_profile(self, uuid: str) -> ApplicationSnapshot:
        """Delete one saved profile and refresh state."""
        async with self._mutation(
            OperationKind.DELETE_PROFILE,
            uuid,
            "Forgetting network…",
        ):
            await self.backend.delete_saved_profile(uuid)
        return await self.refresh()

    async def set_profile_autoconnect(self, uuid: str, *, enabled: bool) -> ApplicationSnapshot:
        """Update auto-connect for one saved profile and refresh state."""
        async with self._mutation(
            OperationKind.AUTOCONNECT,
            uuid,
            "Updating saved network…",
        ):
            await self.backend.set_profile_autoconnect(uuid, enabled=enabled)
        return await self.refresh()

    def profile_by_uuid(self, uuid: str) -> SavedProfile | None:
        """Return one saved profile by UUID."""
        return next(
            (profile for profile in self.snapshot.profiles if profile.uuid == uuid),
            None,
        )

    def _require_interface(self) -> str:
        """Return the selected interface or raise a visible adapter error."""
        if not self.snapshot.selected_device:
            raise WifiError(ErrorCategory.NO_ADAPTER)
        return self.snapshot.selected_device

    class _MutationContext:
        """Publish mutation lifecycle state while serializing backend writes."""

        def __init__(
            self,
            service: WifiService,
            kind: OperationKind,
            target: str | None,
            message: str,
        ) -> None:
            """Initialize one mutation lifecycle context."""
            self.service = service
            self.kind = kind
            self.target = target
            self.message = message

        async def __aenter__(self) -> None:
            """Acquire the mutation lock and publish the running state."""
            await self.service.mutation_lock.acquire()
            self.service.operation_counter += 1
            self.service.publish(
                replace(
                    self.service.snapshot,
                    operation=OperationStatus(
                        self.kind,
                        OperationPhase.RUNNING,
                        self.target,
                        self.message,
                        self.service.operation_counter,
                    ),
                    error=None,
                ),
            )

        async def __aexit__(
            self,
            exc_type: object,
            exc: object,
            traceback: object,
        ) -> bool:
            """Publish expected failure state and always release the mutation lock."""
            del exc_type, traceback
            try:
                if isinstance(exc, WifiError):
                    self.service.publish(
                        replace(
                            self.service.snapshot,
                            operation=OperationStatus(
                                self.kind,
                                OperationPhase.FAILED,
                                self.target,
                                exc.summary,
                                self.service.operation_counter,
                            ),
                            error=exc.summary,
                            warning=exc.guidance,
                        ),
                    )
                elif isinstance(exc, asyncio.CancelledError):
                    self.service.publish(
                        replace(
                            self.service.snapshot,
                            operation=OperationStatus(
                                self.kind,
                                OperationPhase.CANCELLED,
                                self.target,
                                "Operation cancelled.",
                                self.service.operation_counter,
                            ),
                        ),
                    )
            finally:
                self.service.mutation_lock.release()
            return False

    def _mutation(
        self,
        kind: OperationKind,
        target: str | None,
        message: str,
    ) -> _MutationContext:
        """Create a serialized mutation lifecycle context."""
        return self._MutationContext(self, kind, target, message)

    async def close(self) -> None:
        """Prevent future refresh work after application shutdown."""
        self._closed = True
