"""Provide the nearby-network table widget."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import DataTable

if TYPE_CHECKING:
    from tui_wifi.models import NetworkGroup


class NetworkTable(DataTable[str]):
    """Display a stable, color-independent list of visible Wi-Fi networks."""

    def on_mount(self) -> None:
        """Configure table columns and row selection."""
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("", "Network", "Signal", "Security", "Saved")

    def load_networks(self, networks: tuple[NetworkGroup, ...]) -> None:
        """Replace table rows while preserving the selected network when possible."""
        current_identity = self.selected_identity
        self.clear()
        for network in networks:
            marker = "*" if network.connected else ""
            signal = "--" if network.signal is None else f"{network.signal}%"
            security = network.security.value.replace("_", " ")
            if not network.supported:
                security += " (unsupported)"
            saved = "yes" if network.saved_profile_uuids else ""
            self.add_row(
                marker,
                network.display_ssid,
                signal,
                security,
                saved,
                key=network.identity,
            )
        if current_identity is None:
            return
        for row_index, row_key in enumerate(self.rows):
            if str(row_key.value) == current_identity:
                self.move_cursor(row=row_index)
                return

    @property
    def selected_identity(self) -> str | None:
        """Return the stable identity of the selected row."""
        if self.row_count == 0:
            return None
        try:
            cell_key = self.coordinate_to_cell_key(self.cursor_coordinate)
        except LookupError:
            return None
        return str(cell_key.row_key.value)
