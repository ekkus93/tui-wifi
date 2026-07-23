# Copyright (c) 2026 Phillip Chin
"""Verify the Textual application with a fake backend."""

from __future__ import annotations

import asyncio

import pytest

from tests.assertions import verify

pytest.importorskip("textual")

from textual.binding import Binding

from tui_wifi.app import WifiTuiApp
from tui_wifi.backends.fake import FakeWifiBackend
from tui_wifi.models import AccessPoint, SecurityClass
from tui_wifi.services.wifi import WifiService
from tui_wifi.ui.screens.main import MainScreen
from tui_wifi.ui.widgets.network_list import NetworkTable


def test_main_screen_q_binding_targets_priority_app_quit() -> None:
    """Verify Q always resolves to the application quit action."""
    quit_binding = next(
        binding
        for binding in MainScreen.BINDINGS
        if isinstance(binding, Binding) and binding.key == "q"
    )

    verify(quit_binding.action == "app.quit")
    verify(quit_binding.priority)


def test_main_screen_loads_fake_network_without_real_wifi() -> None:
    """Verify the main screen renders a fake network without touching host Wi-Fi."""

    async def scenario() -> None:
        """Run the Textual application with deterministic backend state."""
        backend = FakeWifiBackend()
        backend.access_points["wlan0"] = (
            AccessPoint(
                ssid=b"Test Network",
                display_ssid="Test Network",
                bssid="00:11:22:33:44:55",
                signal=90,
                frequency=2412,
                channel=1,
                security=SecurityClass.WPA2_PERSONAL,
                active=False,
                device="wlan0",
            ),
        )
        app = WifiTuiApp(service=WifiService(backend))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.pause()
            verify(app.screen.query_one(NetworkTable).row_count == 1)

    asyncio.run(scenario())
