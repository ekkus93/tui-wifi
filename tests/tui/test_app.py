"""Verify test app behavior."""

from __future__ import annotations

import asyncio

import pytest

from tests.assertions import verify

pytest.importorskip("textual")

from tui_wifi.app import WifiTuiApp
from tui_wifi.backends.fake import FakeWifiBackend
from tui_wifi.models import AccessPoint, SecurityClass
from tui_wifi.services.wifi import WifiService
from tui_wifi.ui.widgets.network_list import NetworkTable


def test_main_screen_loads_fake_network_without_real_wifi() -> None:
    """Verify test main screen loads fake network without real wifi."""

    async def scenario() -> None:
        """Perform scenario."""
        backend = FakeWifiBackend()
        backend.access_points["wlan0"] = (
            AccessPoint(
                b"Test Network",
                "Test Network",
                "00:11:22:33:44:55",
                90,
                2412,
                1,
                SecurityClass.WPA2_PERSONAL,
                False,
                "wlan0",
            ),
        )
        app = WifiTuiApp(service=WifiService(backend))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.pause()
            verify(app.screen.query_one(NetworkTable).row_count == 1)

    asyncio.run(scenario())
