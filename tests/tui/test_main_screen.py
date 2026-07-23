# Copyright (c) 2026 Phillip Chin
"""Verify main-screen states, workflows, shortcuts, and responsive behavior."""

from __future__ import annotations

import asyncio

import pytest
from textual.widgets import Button, Static

from tests.assertions import verify
from tests.factories import (
    access_point,
    active_connection,
    application_snapshot,
    backend_status,
    network_group,
)
from tests.tui.helpers import settle, static_text
from tui_wifi.app import WifiTuiApp
from tui_wifi.backends.fake import FakeWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import (
    OperationKind,
    OperationPhase,
    OperationStatus,
    SecurityClass,
    WifiRadioState,
)
from tui_wifi.services.wifi import WifiService
from tui_wifi.ui.dialogs.common import (
    ConfirmDialog,
    HiddenNetworkDialog,
    MessageDialog,
    PasswordDialog,
)
from tui_wifi.ui.screens.details import DetailsScreen
from tui_wifi.ui.screens.saved import SavedNetworksScreen
from tui_wifi.ui.widgets.network_list import NetworkTable

EXPECTED_DUPLICATE_ROWS = 2


def test_main_screen_renders_status_priority_connection_and_stale_marker() -> None:
    """Verify every main status state is rendered visibly in priority order."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        service = WifiService(backend)
        app = WifiTuiApp(service=service)
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            message = app.screen.query_one("#message", Static)
            radio = app.screen.query_one("#radio-status", Static)
            summary = app.screen.query_one("#connection-summary", Static)

            cases = (
                (
                    application_snapshot(
                        operation=OperationStatus(
                            OperationKind.REFRESH,
                            OperationPhase.RUNNING,
                            message="Working now",
                        ),
                        error="lower priority",
                    ),
                    "Working now",
                ),
                (application_snapshot(error="Visible error"), "Visible error"),
                (application_snapshot(warning="Visible warning"), "Visible warning"),
                (application_snapshot(selected_device=None), "No usable Wi-Fi adapter"),
                (
                    application_snapshot(
                        status=backend_status(wifi_radio=WifiRadioState.DISABLED),
                    ),
                    "Wi-Fi is disabled",
                ),
                (
                    application_snapshot(
                        status=backend_status(wifi_radio=WifiRadioState.HARDWARE_BLOCKED),
                    ),
                    "Wi-Fi is blocked",
                ),
                (application_snapshot(), "No nearby networks"),
                (
                    application_snapshot(networks=(network_group(),)),
                    "1 network(s) found on wlan0",
                ),
            )
            for snapshot, expected in cases:
                service.publish(snapshot)
                await pilot.pause()
                verify(expected in static_text(message))

            connected = application_snapshot(
                active=active_connection(),
                networks=(network_group(connected=True),),
                stale=True,
            )
            service.publish(connected)
            await pilot.pause()
            verify("Connected to Home" in static_text(summary))
            verify("192.0.2.10/24" in static_text(summary))
            verify("stale" in static_text(radio))

    asyncio.run(scenario())


def test_action_enablement_and_wifi_label_follow_snapshot() -> None:
    """Verify action buttons are disabled during invalid or busy states."""

    async def scenario() -> None:
        service = WifiService(FakeWifiBackend())
        app = WifiTuiApp(service=service)
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            service.publish(application_snapshot())
            await pilot.pause()
            verify(app.screen.query_one("#connect", Button).disabled is True)
            verify(app.screen.query_one("#disconnect", Button).disabled is True)
            verify(app.screen.query_one("#details", Button).disabled is True)
            verify(str(app.screen.query_one("#wifi", Button).label) == "Disable Wi-Fi")

            service.publish(
                application_snapshot(
                    networks=(network_group(),),
                    active=active_connection(),
                ),
            )
            await pilot.pause()
            verify(app.screen.query_one("#connect", Button).disabled is False)
            verify(app.screen.query_one("#disconnect", Button).disabled is False)
            verify(app.screen.query_one("#details", Button).disabled is False)

            service.publish(
                application_snapshot(
                    networks=(network_group(),),
                    active=active_connection(),
                    operation=OperationStatus(
                        OperationKind.CONNECT,
                        OperationPhase.RUNNING,
                    ),
                ),
            )
            await pilot.pause()
            verify(app.screen.query_one("#connect", Button).disabled is True)
            verify(app.screen.query_one("#disconnect", Button).disabled is True)
            verify(app.screen.query_one("#refresh", Button).disabled is True)

            service.publish(
                application_snapshot(
                    status=backend_status(wifi_radio=WifiRadioState.DISABLED),
                ),
            )
            await pilot.pause()
            verify(str(app.screen.query_one("#wifi", Button).label) == "Enable Wi-Fi")

    asyncio.run(scenario())


def test_secured_open_unsupported_and_multiple_saved_connection_routing() -> None:
    """Verify selected security and profile state choose the correct workflow."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        service = WifiService(backend)
        app = WifiTuiApp(service=service)
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)

            service.publish(application_snapshot(networks=(network_group(),)))
            await pilot.pause()
            await pilot.click("#connect")
            await settle(pilot)
            verify(isinstance(app.screen, PasswordDialog))
            await pilot.click("#cancel")
            await settle(pilot)

            service.publish(
                application_snapshot(
                    networks=(network_group(security=SecurityClass.OPEN),),
                ),
            )
            await pilot.pause()
            await pilot.click("#connect")
            await settle(pilot)
            verify(isinstance(app.screen, ConfirmDialog))
            await pilot.click("#cancel")
            await settle(pilot)
            verify(not any(name == "connect_visible_network" for name, _ in backend.calls))

            service.publish(
                application_snapshot(
                    networks=(
                        network_group(
                            security=SecurityClass.ENTERPRISE,
                            supported=False,
                        ),
                    ),
                ),
            )
            await pilot.pause()
            await pilot.click("#connect")
            await settle(pilot)
            verify(isinstance(app.screen, MessageDialog))
            await pilot.click("#close")
            await settle(pilot)

            service.publish(
                application_snapshot(
                    networks=(
                        network_group(
                            saved_profile_uuids=(
                                "00000000-0000-0000-0000-000000000001",
                                "00000000-0000-0000-0000-000000000002",
                            ),
                        ),
                    ),
                ),
            )
            await pilot.pause()
            await pilot.click("#connect")
            await settle(pilot)
            verify(isinstance(app.screen, MessageDialog))
            verify(
                "More than one saved profile"
                in " ".join(static_text(widget) for widget in app.screen.query(Static)),
            )

    asyncio.run(scenario())


def test_open_confirm_password_submit_and_authentication_failure() -> None:
    """Verify confirmed connections run once and typed failures remain visible."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        service = WifiService(backend)
        app = WifiTuiApp(service=service)
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            backend.calls.clear()
            service.publish(
                application_snapshot(
                    networks=(network_group(security=SecurityClass.OPEN),),
                ),
            )
            await pilot.pause()
            await pilot.click("#connect")
            await settle(pilot)
            await pilot.click("#confirm")
            await settle(pilot)
            verify(
                len([name for name, _payload in backend.calls if name == "connect_visible_network"])
                == 1,
            )

            backend.calls.clear()
            backend.failures["connect_visible_network"] = WifiError(
                ErrorCategory.AUTHENTICATION_REJECTED,
            )
            service.publish(application_snapshot(networks=(network_group(),)))
            await pilot.pause()
            await pilot.click("#connect")
            await settle(pilot)
            password = app.screen.query_one("#password")
            password.value = "rejected-secret"
            app.screen.query_one("#autoconnect").value = False
            await pilot.click("#connect")
            await settle(pilot)
            verify(isinstance(app.screen, MessageDialog))
            verify(
                "password was rejected"
                in " ".join(static_text(widget) for widget in app.screen.query(Static)).lower(),
            )
            verify(
                len([name for name, _payload in backend.calls if name == "connect_visible_network"])
                == 1,
            )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "security",
    [SecurityClass.ENTERPRISE, SecurityClass.WEP, SecurityClass.UNKNOWN],
)
def test_unsupported_security_never_reaches_backend(security: SecurityClass) -> None:
    """Verify every unsupported class bypasses password and backend mutation paths."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        service = WifiService(backend)
        app = WifiTuiApp(service=service)
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            backend.calls.clear()
            service.publish(
                application_snapshot(
                    networks=(network_group(security=security, supported=False),),
                ),
            )
            await pilot.pause()
            await pilot.click("#connect")
            await settle(pilot)
            verify(isinstance(app.screen, MessageDialog))
            verify(not isinstance(app.screen, PasswordDialog))
            verify(not any(name == "connect_visible_network" for name, _ in backend.calls))

    asyncio.run(scenario())


def test_hidden_disconnect_radio_details_saved_and_refresh_shortcuts() -> None:
    """Verify documented shortcuts open screens or invoke exact service operations."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        backend.access_points["wlan0"] = (access_point(),)
        backend.active = active_connection()
        service = WifiService(backend)
        app = WifiTuiApp(service=service)
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            backend.calls.clear()

            await pilot.press("r")
            await settle(pilot)
            verify(any(name == "request_scan" for name, _ in backend.calls))

            await pilot.press("h")
            await settle(pilot)
            verify(isinstance(app.screen, HiddenNetworkDialog))
            await pilot.click("#cancel")
            await settle(pilot)

            await pilot.press("s")
            await settle(pilot)
            verify(isinstance(app.screen, SavedNetworksScreen))
            app.pop_screen()
            await settle(pilot)

            service.publish(
                application_snapshot(
                    networks=(network_group(connected=True),),
                    active=active_connection(),
                ),
            )
            await pilot.pause()
            await pilot.press("i")
            await settle(pilot)
            verify(isinstance(app.screen, DetailsScreen))
            app.pop_screen()
            await settle(pilot)

            await pilot.press("d")
            await settle(pilot)
            verify(isinstance(app.screen, ConfirmDialog))
            await pilot.click("#cancel")
            await settle(pilot)
            verify(not any(name == "disconnect" for name, _ in backend.calls))

            await pilot.press("d")
            await settle(pilot)
            await pilot.click("#confirm")
            await settle(pilot)
            verify(len([name for name, _ in backend.calls if name == "disconnect"]) == 1)

    asyncio.run(scenario())


def test_wifi_disable_confirmation_enable_directly_and_failure_visibility() -> None:
    """Verify destructive radio changes confirm while enabling acts directly."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        service = WifiService(backend)
        app = WifiTuiApp(service=service)
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            service.publish(application_snapshot(active=active_connection()))
            await pilot.pause()
            backend.calls.clear()
            app.screen.action_toggle_wifi()
            await settle(pilot)
            verify(isinstance(app.screen, ConfirmDialog))
            await pilot.click("#cancel")
            await settle(pilot)
            verify(not any(name == "set_wifi_radio_state" for name, _ in backend.calls))

            app.screen.action_toggle_wifi()
            await settle(pilot)
            await pilot.click("#confirm")
            await settle(pilot)
            verify(len([name for name, _ in backend.calls if name == "set_wifi_radio_state"]) == 1)

            backend.calls.clear()
            service.publish(
                application_snapshot(
                    status=backend_status(wifi_radio=WifiRadioState.DISABLED),
                ),
            )
            await pilot.pause()
            backend.failures["set_wifi_radio_state"] = WifiError(ErrorCategory.RADIO_BLOCKED)
            app.screen.action_toggle_wifi()
            await settle(pilot)
            verify(isinstance(app.screen, MessageDialog))
            verify(len([name for name, _ in backend.calls if name == "set_wifi_radio_state"]) == 1)

    asyncio.run(scenario())


def test_network_selection_persists_and_duplicates_remain_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify logical selection, disappearance fallback, and lookup failure safety."""

    async def scenario() -> None:
        service = WifiService(FakeWifiBackend())
        app = WifiTuiApp(service=service)
        secured = network_group(identity="Cafe\0wpa2", display_ssid="Cafe")
        open_group = network_group(
            identity="Cafe\0open",
            display_ssid="Cafe",
            security=SecurityClass.OPEN,
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            service.publish(application_snapshot(networks=(secured, open_group)))
            await pilot.pause()
            table = app.screen.query_one(NetworkTable)
            verify(table.row_count == EXPECTED_DUPLICATE_ROWS)
            table.move_cursor(row=1)
            selected = table.selected_identity
            service.publish(application_snapshot(networks=(open_group, secured), generation=2))
            await pilot.pause()
            verify(table.selected_identity == selected)

            service.publish(application_snapshot(networks=(secured,), generation=3))
            await pilot.pause()
            verify(table.selected_identity != selected)

            def raise_lookup(_coordinate: object) -> object:
                """Raise the lookup failure exercised by this test."""
                raise LookupError

            monkeypatch.setattr(table, "coordinate_to_cell_key", raise_lookup)
            verify(table.selected_identity is None)

    asyncio.run(scenario())


def test_responsive_breakpoint_classes_follow_terminal_width() -> None:
    """Verify compact and normal layouts activate at documented widths."""

    async def compact_scenario() -> None:
        app = WifiTuiApp(service=WifiService(FakeWifiBackend()))
        async with app.run_test(size=(60, 30)) as pilot:
            await settle(pilot)
            verify(app.screen.has_class("-compact"))

    async def normal_scenario() -> None:
        app = WifiTuiApp(service=WifiService(FakeWifiBackend()))
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            verify(app.screen.has_class("-normal"))

    asyncio.run(compact_scenario())
    asyncio.run(normal_scenario())
