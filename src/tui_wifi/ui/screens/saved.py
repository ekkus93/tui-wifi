from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static

from tui_wifi.services.wifi import WifiService
from tui_wifi.ui.dialogs.common import ConfirmDialog, MessageDialog


class SavedNetworksScreen(Screen[None]):
    BINDINGS = [("escape", "app.pop_screen", "Back"), ("q", "app.pop_screen", "Back")]

    def __init__(self, service: WifiService) -> None:
        super().__init__()
        self.service = service

    def compose(self) -> ComposeResult:
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
        table = self.query_one("#saved-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Profile", "SSID", "Auto", "Active", "Interface")
        self._reload()

    def _reload(self) -> None:
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
        table = self.query_one("#saved-table", DataTable)
        if table.row_count == 0:
            return None
        try:
            return str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
        except Exception:
            return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
            return
        uuid = self._selected_uuid()
        profile = self.service.profile_by_uuid(uuid) if uuid else None
        if profile is None:
            self.app.push_screen(MessageDialog("Saved networks", "Select a saved network."))
            return
        if event.button.id == "forget":
            self.app.push_screen(
                ConfirmDialog(
                    "Forget network",
                    f"Forget saved profile {profile.name!r}?",
                    "Forget",
                ),
                lambda confirmed: self._start_delete(uuid) if confirmed else None,
            )
        elif event.button.id == "autoconnect":
            self.run_worker(self._set_autoconnect(uuid, not profile.autoconnect), group="saved")
        elif event.button.id == "connect":
            selected = self.service.snapshot.selected_device
            if selected is None:
                self.app.push_screen(
                    MessageDialog(
                        "Cannot connect",
                        "No Wi-Fi adapter is available.",
                    )
                )
                return
            self.run_worker(self._activate(uuid, selected), group="saved")

    def _start_delete(self, uuid: str) -> None:
        self.run_worker(self._delete(uuid), group="saved")

    async def _delete(self, uuid: str) -> None:
        try:
            await self.service.delete_profile(uuid)
            self._reload()
        except Exception as exc:
            self.app.push_screen(MessageDialog("Could not forget network", str(exc)))

    async def _set_autoconnect(self, uuid: str, enabled: bool) -> None:
        try:
            await self.service.set_profile_autoconnect(uuid, enabled)
            self._reload()
        except Exception as exc:
            self.app.push_screen(MessageDialog("Could not update network", str(exc)))

    async def _activate(self, uuid: str, interface: str) -> None:
        from tui_wifi.backends.base import SavedProfileRequest

        try:
            await self.service.backend.activate_saved_profile(SavedProfileRequest(uuid, interface))
            await self.service.refresh()
            self.app.pop_screen()
        except Exception as exc:
            self.app.push_screen(MessageDialog("Could not connect", str(exc)))
