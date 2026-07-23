# Copyright (c) 2026 Phillip Chin
"""Provide the main Wi-Fi management screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static

from tui_wifi.errors import WifiError
from tui_wifi.models import ApplicationSnapshot, NetworkGroup, OperationPhase, WifiRadioState
from tui_wifi.ui.dialogs.common import (
    ConfirmDialog,
    HiddenNetworkAnswer,
    HiddenNetworkDialog,
    MessageDialog,
    PasswordAnswer,
    PasswordDialog,
)
from tui_wifi.ui.screens.details import DetailsScreen
from tui_wifi.ui.screens.saved import SavedNetworksScreen
from tui_wifi.ui.widgets.network_list import NetworkTable

if TYPE_CHECKING:
    from collections.abc import Callable

    from textual.app import ComposeResult

    from tui_wifi.secrets import SecretValue
    from tui_wifi.services.wifi import WifiService


class MainScreen(Screen[None]):
    """Display nearby networks and common Wi-Fi actions."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("r", "refresh_networks", "Refresh"),
        ("d", "disconnect", "Disconnect"),
        ("h", "hidden", "Hidden"),
        ("s", "saved", "Saved"),
        ("w", "toggle_wifi", "Wi-Fi"),
        ("i", "details", "Details"),
        ("enter", "connect", "Connect"),
        ("q", "quit", "Quit"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, service: WifiService, startup_warning: str | None = None) -> None:
        """Initialize the screen with its application service."""
        super().__init__()
        self.service = service
        self.startup_warning = startup_warning
        self._unsubscribe: Callable[[], None] | None = None

    def compose(self) -> ComposeResult:
        """Compose the main screen widgets."""
        yield Header(show_clock=True)
        with Vertical(id="main-body"):
            with Horizontal(id="status-row"):
                yield Label("Wi-Fi", id="title")
                yield Static("Checking NetworkManager…", id="radio-status")
            yield Static("Loading nearby networks…", id="message")
            yield NetworkTable(id="networks")
            yield Static("", id="connection-summary")
            with Horizontal(classes="action-bar"):
                yield Button("Connect", id="connect", variant="primary")
                yield Button("Disconnect", id="disconnect")
                yield Button("Refresh", id="refresh")
                yield Button("Details", id="details")
                yield Button("Hidden", id="hidden")
                yield Button("Saved", id="saved")
                yield Button("Wi-Fi", id="wifi")
        yield Footer()

    def on_mount(self) -> None:
        """Subscribe to state changes and start initial discovery."""
        self._unsubscribe = self.service.subscribe(self._on_snapshot)
        if self.startup_warning:
            self.notify(self.startup_warning, severity="warning", timeout=8)
        self.run_worker(self.service.startup(), group="startup", exclusive=True)

    def on_unmount(self) -> None:
        """Unsubscribe from service updates."""
        if self._unsubscribe is not None:
            self._unsubscribe()

    @staticmethod
    def _radio_text(radio: WifiRadioState) -> str:
        """Return a human-readable Wi-Fi radio state."""
        return {
            WifiRadioState.ENABLED: "Enabled",
            WifiRadioState.DISABLED: "Disabled",
            WifiRadioState.HARDWARE_BLOCKED: "Blocked",
            WifiRadioState.UNKNOWN: "Unknown",
        }[radio]

    @staticmethod
    def _message_for(snapshot: ApplicationSnapshot, radio: WifiRadioState) -> str:
        """Choose the most important current status message."""
        if snapshot.operation.phase == OperationPhase.RUNNING:
            message = snapshot.operation.message or "Working…"
        elif snapshot.error:
            message = snapshot.error
        elif snapshot.warning:
            message = snapshot.warning
        elif snapshot.selected_device is None:
            message = "No usable Wi-Fi adapter was found."
        elif radio == WifiRadioState.DISABLED:
            message = "Wi-Fi is disabled. Press W to enable it."
        elif radio == WifiRadioState.HARDWARE_BLOCKED:
            message = "Wi-Fi is blocked by a hardware or software switch."
        elif not snapshot.networks:
            message = "No nearby networks were found. Press R to scan again."
        else:
            message = f"{len(snapshot.networks)} network(s) found on {snapshot.selected_device}."
        return message

    @staticmethod
    def _connection_summary(snapshot: ApplicationSnapshot) -> str:
        """Build the compact active-connection summary."""
        active = snapshot.active_connection
        if active is None:
            return "Not connected"
        addresses = ", ".join(active.ipv4.addresses)
        summary = f"Connected to {active.ssid or active.profile_name}"
        return f"{summary} · {addresses}" if addresses else summary

    def _update_action_widgets(
        self,
        snapshot: ApplicationSnapshot,
        radio: WifiRadioState,
    ) -> None:
        """Enable and label actions from the current snapshot."""
        active = snapshot.active_connection
        busy = snapshot.operation.phase == OperationPhase.RUNNING
        self.query_one("#connect", Button).disabled = busy or not snapshot.networks
        self.query_one("#disconnect", Button).disabled = busy or active is None
        self.query_one("#refresh", Button).disabled = busy
        self.query_one("#details", Button).disabled = active is None
        self.query_one("#wifi", Button).label = (
            "Disable Wi-Fi" if radio == WifiRadioState.ENABLED else "Enable Wi-Fi"
        )

    def _on_snapshot(self, snapshot: ApplicationSnapshot) -> None:
        """Render one coherent application snapshot."""
        if not self.is_mounted:
            return
        self.query_one("#networks", NetworkTable).load_networks(snapshot.networks)
        radio = snapshot.status.wifi_radio
        stale = " (stale)" if snapshot.stale else ""
        self.query_one("#radio-status", Static).update(
            f"Wi-Fi: {self._radio_text(radio)}{stale}",
        )
        self.query_one("#message", Static).update(self._message_for(snapshot, radio))
        self.query_one("#connection-summary", Static).update(
            self._connection_summary(snapshot),
        )
        self._update_action_widgets(snapshot, radio)

    def _selected_group(self) -> NetworkGroup | None:
        """Return the network selected in the table."""
        identity = self.query_one("#networks", NetworkTable).selected_identity
        return next(
            (network for network in self.service.snapshot.networks if network.identity == identity),
            None,
        )

    def on_data_table_row_selected(self, _event: NetworkTable.RowSelected) -> None:
        """Connect when the user activates a network row."""
        self.action_connect()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch a pressed action button."""
        actions = {
            "connect": self.action_connect,
            "disconnect": self.action_disconnect,
            "refresh": self.action_refresh_networks,
            "details": self.action_details,
            "hidden": self.action_hidden,
            "saved": self.action_saved,
            "wifi": self.action_toggle_wifi,
        }
        action = actions.get(event.button.id or "")
        if action:
            action()

    def action_cursor_down(self) -> None:
        """Move the network selection down."""
        self.query_one("#networks", NetworkTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move the network selection up."""
        self.query_one("#networks", NetworkTable).action_cursor_up()

    def action_refresh_networks(self) -> None:
        """Start a fresh network scan."""
        self.run_worker(self._refresh(), group="refresh", exclusive=True)

    async def _refresh(self) -> None:
        """Refresh networks through the service."""
        await self.service.refresh(request_scan=True)

    def action_connect(self) -> None:
        """Start the appropriate connection workflow for the selected network."""
        group = self._selected_group()
        if group is None:
            self.app.push_screen(MessageDialog("Connect", "Select a network first."))
            return
        if not group.supported:
            self.app.push_screen(
                MessageDialog(
                    "Unsupported network",
                    "This network uses an authentication method that "
                    "tui-wifi does not yet support.",
                    f"Detected security: {group.security.value}",
                ),
            )
            return
        if len(group.saved_profile_uuids) == 1:
            self.run_worker(
                self._connect(group, None, autoconnect=True),
                group="mutation",
                exclusive=True,
            )
            return
        if len(group.saved_profile_uuids) > 1:
            self.app.push_screen(
                MessageDialog(
                    "Multiple saved profiles",
                    "More than one saved profile matches this network. "
                    "Open Saved Networks and select the exact profile.",
                ),
            )
            return
        if not group.security.requires_password:
            self.app.push_screen(
                ConfirmDialog(
                    "Open network",
                    f"{group.display_ssid!r} is not encrypted. Connect anyway?",
                    "Connect",
                ),
                lambda confirmed: self._start_open(group) if confirmed else None,
            )
            return
        self.app.push_screen(
            PasswordDialog(group.display_ssid),
            lambda answer: self._start_password(group, answer),
        )

    def _start_open(self, group: NetworkGroup) -> None:
        """Connect to a confirmed open network."""
        self.run_worker(
            self._connect(group, None, autoconnect=True),
            group="mutation",
            exclusive=True,
        )

    def _start_password(self, group: NetworkGroup, answer: PasswordAnswer | None) -> None:
        """Connect using a submitted password dialog answer."""
        if answer is not None:
            self.run_worker(
                self._connect(
                    group,
                    answer.password,
                    autoconnect=answer.autoconnect,
                ),
                group="mutation",
                exclusive=True,
            )

    async def _connect(
        self,
        group: NetworkGroup,
        password: SecretValue | None,
        *,
        autoconnect: bool,
    ) -> None:
        """Connect to one visible network and report expected failures."""
        try:
            snapshot = await self.service.connect_network(
                group,
                password=password,
                autoconnect=autoconnect,
            )
        except WifiError as exc:
            self.app.push_screen(
                MessageDialog(
                    exc.summary,
                    exc.guidance or "The connection did not succeed.",
                    exc.diagnostic_text(),
                ),
            )
        else:
            active = snapshot.active_connection
            if active is not None:
                self.notify(f"Connected to {active.ssid or active.profile_name}", timeout=5)

    def action_disconnect(self) -> None:
        """Ask before disconnecting the active network."""
        active = self.service.snapshot.active_connection
        if active is None:
            return
        self.app.push_screen(
            ConfirmDialog(
                "Disconnect",
                f"Disconnect from {active.ssid or active.profile_name!r}?",
                "Disconnect",
            ),
            lambda confirmed: self._start_disconnect() if confirmed else None,
        )

    def _start_disconnect(self) -> None:
        """Start the disconnect worker."""
        self.run_worker(self._disconnect(), group="mutation", exclusive=True)

    async def _disconnect(self) -> None:
        """Disconnect and present expected failures."""
        try:
            await self.service.disconnect()
        except WifiError as exc:
            self.app.push_screen(MessageDialog(exc.summary, exc.guidance or "Disconnect failed."))

    def action_hidden(self) -> None:
        """Open the hidden-network dialog."""
        self.app.push_screen(HiddenNetworkDialog(), self._start_hidden)

    def _start_hidden(self, answer: HiddenNetworkAnswer | None) -> None:
        """Start a hidden-network connection from a dialog answer."""
        if answer is not None:
            self.run_worker(self._connect_hidden(answer), group="mutation", exclusive=True)

    async def _connect_hidden(self, answer: HiddenNetworkAnswer) -> None:
        """Connect to a hidden network and present expected failures."""
        try:
            await self.service.connect_hidden(
                answer.ssid,
                answer.security,
                answer.password,
                autoconnect=answer.autoconnect,
            )
        except WifiError as exc:
            self.app.push_screen(MessageDialog(exc.summary, exc.guidance or "Connection failed."))
        else:
            self.notify(f"Connected to {answer.ssid}", timeout=5)

    def action_saved(self) -> None:
        """Open the saved-network screen."""
        self.app.push_screen(SavedNetworksScreen(self.service))

    def action_details(self) -> None:
        """Open details for the active connection."""
        self.app.push_screen(DetailsScreen(self.service.snapshot.active_connection))

    def action_toggle_wifi(self) -> None:
        """Enable Wi-Fi or confirm before disabling an active connection."""
        enabled = self.service.snapshot.status.wifi_radio != WifiRadioState.ENABLED
        if not enabled and self.service.snapshot.active_connection is not None:
            self.app.push_screen(
                ConfirmDialog(
                    "Disable Wi-Fi",
                    "This will interrupt the active Wi-Fi connection.",
                    "Disable",
                ),
                lambda confirmed: self._start_toggle(enabled=False) if confirmed else None,
            )
        else:
            self._start_toggle(enabled=enabled)

    def _start_toggle(self, *, enabled: bool) -> None:
        """Start the Wi-Fi radio worker."""
        self.run_worker(
            self._toggle(enabled=enabled),
            group="mutation",
            exclusive=True,
        )

    async def _toggle(self, *, enabled: bool) -> None:
        """Change the Wi-Fi radio state and present expected failures."""
        try:
            await self.service.set_wifi_enabled(enabled=enabled)
        except WifiError as exc:
            self.app.push_screen(
                MessageDialog(
                    exc.summary,
                    exc.guidance or "Wi-Fi state did not change.",
                ),
            )
