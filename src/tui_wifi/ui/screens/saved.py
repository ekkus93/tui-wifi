"""Provide the saved-network management screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static

from tui_wifi.backends.base import SavedProfileRequest
from tui_wifi.errors import WifiError
from tui_wifi.ui.dialogs.common import ConfirmDialog, MessageDialog

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from tui_wifi.services.wifi import WifiService


class SavedNetworksScreen(Screen[None]):
    """Display and modify saved NetworkManager Wi-Fi profiles."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", "Back"),
        ("q", "app.pop_screen", "Back"),
    ]

    def __init__(self, service: WifiService) -> None:
        """Initialize the screen with its application service."""
        super().__init__()
        self.service = service

    def compose(self) -> ComposeResult:
        """Compose saved-profile widgets and actions."""
        yield Header()
        yield Static("Saved networks", classes="screen-title")
        yield DataTable(id="saved-table")
        with Horizontal(classes="action-bar"):
            yield Button("Connect", id="connect", variant="primary")
            yield Button("Forget", id="forget", variant="error")
            yield Button("Toggle auto-connect", id="autoconnect")
            yield Button("Back", id="back")
        yield Footer()

    def on_mount(self) -> None:
        """Configure the saved-profile table and load its rows."""
        table = self.query_one("#saved-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Profile", "SSID", "Auto", "Active", "Interface")
        self._reload()

    def _reload(self) -> None:
        """Reload rows from the latest service snapshot."""
        table = self.query_one("#saved-table", DataTable)
        table.clear()
        for profile in self.service.snapshot.profiles:
            table.add_row(
                profile.name,
                profile.ssid or "--",
                "on" if profile.autoconnect else "off",
                "yes" if profile.active else "",
                profile.interface_name or "any",
                key=profile.uuid,
            )

    def _selected_uuid(self) -> str | None:
        """Return the UUID of the selected saved profile."""
        table = self.query_one("#saved-table", DataTable)
        if table.row_count == 0:
            return None
        try:
            cell_key = table.coordinate_to_cell_key(table.cursor_coordinate)
        except LookupError:
            return None
        return str(cell_key.row_key.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch a saved-profile action button."""
        if event.button.id == "back":
            self.app.pop_screen()
            return
        selected_uuid = self._selected_uuid()
        profile = self.service.profile_by_uuid(selected_uuid) if selected_uuid else None
        if profile is None:
            self.app.push_screen(MessageDialog("Saved networks", "Select a saved network."))
            return
        profile_uuid = profile.uuid
        if event.button.id == "forget":
            self.app.push_screen(
                ConfirmDialog(
                    "Forget network",
                    f"Forget saved profile {profile.name!r}?",
                    "Forget",
                ),
                lambda confirmed: self._start_delete(profile_uuid) if confirmed else None,
            )
        elif event.button.id == "autoconnect":
            self.run_worker(
                self._set_autoconnect(
                    profile_uuid,
                    enabled=not profile.autoconnect,
                ),
                group="saved",
            )
        elif event.button.id == "connect":
            selected = self.service.snapshot.selected_device
            if selected is None:
                self.app.push_screen(
                    MessageDialog(
                        "Cannot connect",
                        "No Wi-Fi adapter is available.",
                    ),
                )
                return
            self.run_worker(self._activate(profile_uuid, selected), group="saved")

    def _start_delete(self, uuid: str) -> None:
        """Start deletion for one saved profile."""
        self.run_worker(self._delete(uuid), group="saved")

    async def _delete(self, uuid: str) -> None:
        """Delete one saved profile and reload the table."""
        try:
            await self.service.delete_profile(uuid)
            self._reload()
        except WifiError as exc:
            self.app.push_screen(MessageDialog("Could not forget network", exc.summary))

    async def _set_autoconnect(self, uuid: str, *, enabled: bool) -> None:
        """Update auto-connect for one saved profile."""
        try:
            await self.service.set_profile_autoconnect(uuid, enabled=enabled)
            self._reload()
        except WifiError as exc:
            self.app.push_screen(MessageDialog("Could not update network", exc.summary))

    async def _activate(self, uuid: str, interface: str) -> None:
        """Activate one saved profile on the selected interface."""
        try:
            await self.service.backend.activate_saved_profile(
                SavedProfileRequest(uuid, interface),
            )
            await self.service.refresh()
            self.app.pop_screen()
        except WifiError as exc:
            self.app.push_screen(MessageDialog("Could not connect", exc.summary))
