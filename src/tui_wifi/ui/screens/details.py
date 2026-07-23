from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from tui_wifi.models import ActiveWifiConnection


class DetailsScreen(Screen[None]):
    BINDINGS = [("escape", "app.pop_screen", "Back"), ("q", "app.pop_screen", "Back")]

    def __init__(self, connection: ActiveWifiConnection | None) -> None:
        super().__init__()
        self.connection = connection

    def compose(self) -> ComposeResult:
        yield Header()
        if self.connection is None:
            yield Static("No active Wi-Fi connection.", classes="empty-state")
        else:
            item = self.connection
            lines = [
                f"Network: {item.ssid or 'Unavailable'}",
                f"Profile: {item.profile_name or 'Unavailable'}",
                f"UUID: {item.uuid or 'Unavailable'}",
                f"Interface: {item.device}",
                f"State: {item.state.value}",
                f"BSSID: {item.bssid or 'Unavailable'}",
                f"IPv4: {', '.join(item.ipv4.addresses) or 'Unavailable'}",
                f"IPv4 gateway: {item.ipv4.gateway or 'Unavailable'}",
                f"IPv4 DNS: {', '.join(item.ipv4.dns) or 'Unavailable'}",
                f"IPv6: {', '.join(item.ipv6.addresses) or 'Unavailable'}",
                f"IPv6 gateway: {item.ipv6.gateway or 'Unavailable'}",
                f"IPv6 DNS: {', '.join(item.ipv6.dns) or 'Unavailable'}",
            ]
            yield Static("\n".join(lines), classes="details")
        yield Footer()
