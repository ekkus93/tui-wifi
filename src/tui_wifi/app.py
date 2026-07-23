# Copyright (c) 2026 Phillip Chin
"""Provide the Textual application entry point."""

from __future__ import annotations

from textual.app import App

from tui_wifi.backends.nmcli import NmcliWifiBackend
from tui_wifi.process import AsyncProcessRunner
from tui_wifi.services.wifi import WifiService
from tui_wifi.ui.screens.main import MainScreen


class WifiTuiApp(App[None]):
    """Run the terminal Wi-Fi manager."""

    TITLE = "tui-wifi"
    SUB_TITLE = "Terminal Wi-Fi Manager"
    CSS_PATH = "ui/tui_wifi.tcss"

    def __init__(
        self,
        *,
        preferred_interface: str | None = None,
        mouse_enabled: bool = True,
        startup_warning: str | None = None,
        service: WifiService | None = None,
    ) -> None:
        """Initialize the application and its Wi-Fi service."""
        super().__init__()
        self.HORIZONTAL_BREAKPOINTS = [
            (0, "-compact"),
            (90, "-normal"),
        ]
        self.mouse_enabled = mouse_enabled
        self.startup_warning = startup_warning
        self.service = service or WifiService(
            NmcliWifiBackend(AsyncProcessRunner()),
            preferred_interface,
        )

    def on_mount(self) -> None:
        """Open the main Wi-Fi screen after application startup."""
        self.push_screen(MainScreen(self.service, self.startup_warning))

    async def on_unmount(self) -> None:
        """Close the service when the application exits."""
        await self.service.close()
