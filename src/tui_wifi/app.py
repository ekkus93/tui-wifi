"""Provide app functionality."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App

from tui_wifi.backends.nmcli import NmcliWifiBackend
from tui_wifi.process import AsyncProcessRunner
from tui_wifi.services.wifi import WifiService
from tui_wifi.ui.screens.main import MainScreen


class WifiTuiApp(App[None]):
    """Represent WifiTuiApp."""

    TITLE = "tui-wifi"
    SUB_TITLE = "Terminal Wi-Fi Manager"
    CSS_PATH = "ui/tui_wifi.tcss"
    HORIZONTAL_BREAKPOINTS: ClassVar[list[tuple[int, str]]] = [
        (0, "-compact"),
        (90, "-normal"),
    ]

    def __init__(
        self,
        *,
        preferred_interface: str | None = None,
        mouse_enabled: bool = True,
        startup_warning: str | None = None,
        service: WifiService | None = None,
    ) -> None:
        """Initialize the instance."""
        super().__init__()
        self.mouse_enabled = mouse_enabled
        self.startup_warning = startup_warning
        self.service = service or WifiService(
            NmcliWifiBackend(AsyncProcessRunner()),
            preferred_interface,
        )

    def on_mount(self) -> None:
        """Perform on mount."""
        self.push_screen(MainScreen(self.service, self.startup_warning))

    async def on_unmount(self) -> None:
        """Perform on unmount."""
        await self.service.close()
