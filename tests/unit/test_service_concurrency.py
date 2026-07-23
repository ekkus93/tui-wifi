# Copyright (c) 2026 Phillip Chin
"""Verify Wi-Fi service generation ordering, cancellation, and serialization."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from tests.assertions import verify
from tests.factories import access_point, network_group
from tui_wifi.backends.fake import FakeWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import (
    AccessPoint,
    ActiveWifiConnection,
    OperationKind,
    OperationPhase,
    SecurityClass,
)
from tui_wifi.secrets import SecretValue
from tui_wifi.services.wifi import WifiService

EXPECTED_SECOND_VALUE = 2


if TYPE_CHECKING:
    from tui_wifi.backends.base import HiddenConnectRequest, VisibleConnectRequest


class SequencedRefreshBackend(FakeWifiBackend):
    """Return a paused old scan result followed by an immediate new result."""

    def __init__(self) -> None:
        """Initialize deterministic scan gates and result ordering."""
        super().__init__()
        self.first_entered = asyncio.Event()
        self.release_first = asyncio.Event()
        self.access_point_calls = 0

    async def list_access_points(self, interface: str) -> tuple[AccessPoint, ...]:
        """Pause the first listing while allowing the second to complete."""
        self.calls.append(("list_access_points", interface))
        self.access_point_calls += 1
        if self.access_point_calls == 1:
            self.first_entered.set()
            await self.release_first.wait()
            return (access_point(ssid="Old"),)
        return (access_point(ssid="New"),)


class SerializedMutationBackend(FakeWifiBackend):
    """Pause selected mutations and record backend concurrency."""

    def __init__(self) -> None:
        """Initialize mutation gates and counters."""
        super().__init__()
        self.first_entered = asyncio.Event()
        self.release_first = asyncio.Event()
        self.second_entered = asyncio.Event()
        self.mutation_entries = 0
        self.concurrent_mutations = 0
        self.maximum_concurrent_mutations = 0
        self.mutation_order: list[str] = []
        self.failure: BaseException | None = None

    async def connect_visible_network(
        self,
        request: VisibleConnectRequest,
    ) -> ActiveWifiConnection:
        """Pause the first mutation and expose whether the second overlaps."""
        self.calls.append(("connect_visible_network", request))
        self.mutation_entries += 1
        entry = self.mutation_entries
        self.concurrent_mutations += 1
        self.maximum_concurrent_mutations = max(
            self.maximum_concurrent_mutations,
            self.concurrent_mutations,
        )
        self.mutation_order.append(f"enter-{entry}")
        if entry == 1:
            self.first_entered.set()
            try:
                await self.release_first.wait()
            finally:
                self.concurrent_mutations -= 1
        else:
            self.second_entered.set()
            self.concurrent_mutations -= 1
        if self.failure is not None and entry == 1:
            raise self.failure
        return await super().connect_visible_network(request)


async def initialized_service(backend: FakeWifiBackend) -> WifiService:
    """Return a service with one selected adapter and coherent initial state."""
    service = WifiService(backend)
    await service.refresh()
    backend.calls.clear()
    return service


def test_older_refresh_cannot_overwrite_newer_generation() -> None:
    """Verify a late old refresh candidate is discarded deterministically."""

    async def scenario() -> None:
        backend = SequencedRefreshBackend()
        service = WifiService(backend)
        published: list[tuple[int, tuple[str, ...]]] = []
        service.subscribe(
            lambda snapshot: published.append(
                (snapshot.generation, tuple(group.display_ssid for group in snapshot.networks)),
            ),
        )
        first = asyncio.create_task(service.refresh())
        await backend.first_entered.wait()
        second = asyncio.create_task(service.refresh())
        second_result = await second
        verify(tuple(group.display_ssid for group in second_result.networks) == ("New",))
        backend.release_first.set()
        await first
        verify(service.snapshot.generation == EXPECTED_SECOND_VALUE)
        verify(tuple(group.display_ssid for group in service.snapshot.networks) == ("New",))
        verify((1, ("Old",)) not in published)

    asyncio.run(scenario())


def test_close_during_running_refresh_keeps_explicit_current_contract() -> None:
    """Verify close prevents future work but does not cancel an in-flight refresh."""

    async def scenario() -> None:
        backend = SequencedRefreshBackend()
        service = WifiService(backend)
        task = asyncio.create_task(service.refresh())
        await backend.first_entered.wait()
        await service.close()
        backend.release_first.set()
        completed = await task
        verify(tuple(group.display_ssid for group in completed.networks) == ("Old",))
        calls = len(backend.calls)
        verify(await service.refresh() is completed)
        verify(len(backend.calls) == calls)

    asyncio.run(scenario())


def test_mutations_are_serialized_and_publish_running_states() -> None:
    """Verify a second mutation cannot enter until the first releases the lock."""

    async def scenario() -> None:
        backend = SerializedMutationBackend()
        service = await initialized_service(backend)
        phases: list[tuple[OperationKind, OperationPhase, str | None]] = []
        service.subscribe(
            lambda snapshot: phases.append(
                (snapshot.operation.kind, snapshot.operation.phase, snapshot.operation.target),
            ),
        )
        first = asyncio.create_task(service.connect_network(network_group(display_ssid="First")))
        await backend.first_entered.wait()
        second = asyncio.create_task(service.connect_network(network_group(display_ssid="Second")))
        await asyncio.sleep(0)
        verify(backend.second_entered.is_set() is False)
        backend.release_first.set()
        await first
        await backend.second_entered.wait()
        await second
        verify(backend.maximum_concurrent_mutations == 1)
        verify(backend.mutation_order == ["enter-1", "enter-2"])
        verify((OperationKind.CONNECT, OperationPhase.RUNNING, "First") in phases)
        verify((OperationKind.CONNECT, OperationPhase.RUNNING, "Second") in phases)

    asyncio.run(scenario())


def test_wifi_error_releases_lock_and_publishes_failed_operation() -> None:
    """Verify typed failure does not prevent a later mutation from completing."""

    async def scenario() -> None:
        backend = SerializedMutationBackend()
        service = await initialized_service(backend)
        backend.failure = WifiError(
            ErrorCategory.AUTHENTICATION_REJECTED,
            guidance="Try another credential.",
        )
        first = asyncio.create_task(service.connect_network(network_group(display_ssid="First")))
        await backend.first_entered.wait()
        backend.release_first.set()
        with pytest.raises(WifiError):
            await first
        verify(service.snapshot.operation.phase == OperationPhase.FAILED)
        verify(service.snapshot.error == "The Wi-Fi password was rejected.")
        verify(service.snapshot.warning == "Try another credential.")

        backend.failure = None
        await service.connect_network(network_group(display_ssid="Second"))
        verify(backend.mutation_entries == EXPECTED_SECOND_VALUE)

    asyncio.run(scenario())


def test_cancellation_clears_password_releases_lock_and_sets_cancelled_phase() -> None:
    """Verify cancellation remains distinct and a subsequent mutation can proceed."""

    async def scenario() -> None:
        backend = SerializedMutationBackend()
        service = await initialized_service(backend)
        password = SecretValue("cancelled-secret")
        task = asyncio.create_task(
            service.connect_network(
                network_group(display_ssid="First"),
                password=password,
            ),
        )
        await backend.first_entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        verify(password.reveal() == "")
        verify(service.snapshot.operation.phase == OperationPhase.CANCELLED)
        verify(service.snapshot.operation.message == "Operation cancelled.")

        backend.release_first.set()
        await service.connect_network(network_group(display_ssid="Second"))
        verify(backend.mutation_entries == EXPECTED_SECOND_VALUE)

    asyncio.run(scenario())


def test_unexpected_exception_propagates_and_releases_lock() -> None:
    """Verify internal exceptions are never converted into quiet success."""

    async def scenario() -> None:
        backend = SerializedMutationBackend()
        service = await initialized_service(backend)
        backend.failure = RuntimeError("synthetic internal failure")
        task = asyncio.create_task(service.connect_network(network_group(display_ssid="First")))
        await backend.first_entered.wait()
        backend.release_first.set()
        with pytest.raises(RuntimeError, match="synthetic internal failure"):
            await task
        verify(service.snapshot.operation.phase == OperationPhase.RUNNING)

        backend.failure = None
        await service.connect_network(network_group(display_ssid="Second"))
        verify(backend.mutation_entries == EXPECTED_SECOND_VALUE)

    asyncio.run(scenario())


def test_hidden_cancellation_clears_password() -> None:
    """Verify hidden-network credentials are cleared when the task is cancelled."""

    class HiddenGateBackend(FakeWifiBackend):
        """Pause hidden connection entry until the caller cancels it."""

        def __init__(self) -> None:
            super().__init__()
            self.entered = asyncio.Event()
            self.release = asyncio.Event()

        async def connect_hidden_network(
            self,
            request: HiddenConnectRequest,
        ) -> ActiveWifiConnection:
            self.calls.append(("connect_hidden_network", request))
            self.entered.set()
            await self.release.wait()
            return await super().connect_hidden_network(request)

    async def scenario() -> None:
        backend = HiddenGateBackend()
        service = await initialized_service(backend)
        password = SecretValue("hidden-cancel-secret")
        task = asyncio.create_task(
            service.connect_hidden(
                "Hidden",
                SecurityClass.WPA2_PERSONAL,
                password,
                autoconnect=True,
            ),
        )
        await backend.entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        verify(password.reveal() == "")
        verify(service.snapshot.operation.phase == OperationPhase.CANCELLED)
        backend.release.set()

    asyncio.run(scenario())
