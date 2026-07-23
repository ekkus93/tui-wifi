from __future__ import annotations

from textual.widgets import DataTable

from tui_wifi.models import NetworkGroup


class NetworkTable(DataTable[str]):
    """A stable, color-independent list of visible Wi-Fi networks."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("", "Network", "Signal", "Security", "Saved")

    def load_networks(self, networks: tuple[NetworkGroup, ...]) -> None:
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
        if current_identity is not None:
            try:
                row = self.get_row_index(current_identity)
            except Exception:
                return
            self.move_cursor(row=row)

    @property
    def selected_identity(self) -> str | None:
        if self.row_count == 0:
            return None
        coordinate = self.cursor_coordinate
        try:
            return str(self.coordinate_to_cell_key(coordinate).row_key.value)
        except Exception:
            return None
