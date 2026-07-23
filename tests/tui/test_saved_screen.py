# Copyright (c) 2026 Phillip Chin
"""Verify saved-profile rendering and mutation workflows."""

from __future__ import annotations

import asyncio

from textual.widgets import DataTable, Static

from tests.assertions import verify
from tests.factories import DEFAULT_UUID, application_snapshot, saved_profile
from tests.tui.helpers import settle, static_text
from tui_wifi.app import WifiTuiApp
from tui_wifi.backends.fake import FakeWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.services.wifi import WifiService
from tui_wifi.ui.dialogs.common import ConfirmDialog, MessageDialog
from tui_wifi.ui.screens.saved import SavedNetworksScreen


def test_saved_profiles_render_all_user_visible_fields() -> None:
    """Verify name, SSID, auto-connect, active state, and interface are rendered."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        profile = saved_profile(active=True, autoconnect=False)
        backend.profiles = (profile,)
        service = WifiService(backend)
        app = WifiTuiApp(service=service)
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            service.publish(application_snapshot(profiles=(profile,)))
            app.push_screen(SavedNetworksScreen(service))
            await settle(pilot)
            table = app.screen.query_one("#saved-table", DataTable)
            verify(table.row_count == 1)
            row = tuple(str(cell) for cell in table.get_row(DEFAULT_UUID))
            verify(profile.name in row)
            verify(profile.ssid in row)
            verify("off" in row)
            verify("yes" in row)
            verify("wlan0" in row)

    asyncio.run(scenario())


def test_saved_connect_forget_and_autoconnect_workflows() -> None:
    """Verify exact selected UUID operations, confirmation, and inverse auto-connect."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        profile = saved_profile()
        backend.profiles = (profile,)
        service = WifiService(backend)
        app = WifiTuiApp(service=service)
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            service.publish(application_snapshot(profiles=(profile,)))
            app.push_screen(SavedNetworksScreen(service))
            await settle(pilot)
            backend.calls.clear()

            await pilot.click("#autoconnect")
            await settle(pilot)
            verify(
                ("set_profile_autoconnect", (DEFAULT_UUID, False)) in backend.calls,
            )

            backend.profiles = (profile,)
            service.publish(application_snapshot(profiles=(profile,), generation=2))
            app.screen.query_one("#saved-table", DataTable).move_cursor(row=0)
            backend.calls.clear()
            await pilot.click("#forget")
            await settle(pilot)
            verify(isinstance(app.screen, ConfirmDialog))
            await pilot.click("#cancel")
            await settle(pilot)
            verify(not any(name == "delete_saved_profile" for name, _ in backend.calls))

            await pilot.click("#forget")
            await settle(pilot)
            await pilot.click("#confirm")
            await settle(pilot)
            verify(("delete_saved_profile", DEFAULT_UUID) in backend.calls)

    asyncio.run(scenario())


def test_saved_connect_uses_selected_uuid_and_interface() -> None:
    """Verify activation targets the selected profile and adapter."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        profile = saved_profile()
        backend.profiles = (profile,)
        service = WifiService(backend)
        app = WifiTuiApp(service=service)
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            service.publish(application_snapshot(profiles=(profile,)))
            app.push_screen(SavedNetworksScreen(service))
            await settle(pilot)
            backend.calls.clear()
            await pilot.click("#connect")
            await settle(pilot)
            payloads = [
                payload for name, payload in backend.calls if name == "activate_saved_profile"
            ]
            verify(len(payloads) == 1)
            verify(payloads[0].uuid == DEFAULT_UUID)
            verify(payloads[0].interface == "wlan0")

    asyncio.run(scenario())


def test_saved_empty_selection_no_adapter_and_backend_failure_are_visible() -> None:
    """Verify invalid selection and typed failures never disappear silently."""

    async def scenario() -> None:
        backend = FakeWifiBackend()
        service = WifiService(backend)
        app = WifiTuiApp(service=service)
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            service.publish(application_snapshot(profiles=()))
            app.push_screen(SavedNetworksScreen(service))
            await settle(pilot)
            await pilot.click("#connect")
            await settle(pilot)
            verify(isinstance(app.screen, MessageDialog))
            verify(
                "Select a saved network"
                in " ".join(static_text(w) for w in app.screen.query(Static)),
            )
            await pilot.click("#close")
            await settle(pilot)

            profile = saved_profile()
            service.publish(
                application_snapshot(
                    profiles=(profile,),
                    selected_device=None,
                    generation=2,
                ),
            )
            app.screen.query_one("#saved-table", DataTable).clear()
            app.screen.query_one("#saved-table", DataTable).add_row(
                profile.name,
                profile.ssid,
                "on",
                "",
                "any",
                key=profile.uuid,
            )
            await pilot.click("#connect")
            await settle(pilot)
            verify(isinstance(app.screen, MessageDialog))
            verify("No Wi-Fi adapter" in " ".join(static_text(w) for w in app.screen.query(Static)))
            await pilot.click("#close")
            await settle(pilot)

            service.publish(application_snapshot(profiles=(profile,), generation=3))
            app.screen.query_one("#saved-table", DataTable).clear()
            app.screen.query_one("#saved-table", DataTable).add_row(
                profile.name,
                profile.ssid,
                "on",
                "",
                "wlan0",
                key=profile.uuid,
            )
            backend.failures["set_profile_autoconnect"] = WifiError(ErrorCategory.COMMAND_FAILURE)
            await pilot.click("#autoconnect")
            await settle(pilot)
            verify(isinstance(app.screen, MessageDialog))
            verify(
                "Could not update network"
                in " ".join(static_text(w) for w in app.screen.query(Static)),
            )

    asyncio.run(scenario())
