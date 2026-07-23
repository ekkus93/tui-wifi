"""Provide main functionality."""

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
    """Represent MainScreen."""

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
        """Initialize the instance."""
        super().__init__()
        self.service = service
        self.startup_warning = startup_warning
        self._unsubscribe: Callable[[], None] | None = None

    def compose(self) -> ComposeResult:
        """Perform compose."""
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
        """Perform on mount."""
        self._unsubscribe = self.service.subscribe(self._on_snapshot)
        if self.startup_warning:
            self.notify(self.startup_warning, severity="warning", timeout=8)
        self.run_worker(self.service.startup(), group="startup", exclusive=True)

    def on_unmount(self) -> None:
        """Perform on unmount."""
        if self._unsubscribe is not None:
            self._unsubscribe()

    def _on_snapshot(self, snapshot: ApplicationSnapshot) -> None:
        """Perform on snapshot."""
        if not self.is_mounted:
            return
        self.query_one("#networks", NetworkTable).load_networks(snapshot.networks)
        radio = snapshot.status.wifi_radio
        radio_text = {
            WifiRadioState.ENABLED: "Enabled",
            WifiRadioState.DISABLED: "Disabled",
            WifiRadioState.HARDWARE_BLOCKED: "Blocked",
            WifiRadioState.UNKNOWN: "Unknown",
        }[radio]
        stale = " (stale)" if snapshot.stale else ""
        self.query_one("#radio-status", Static).update(f"Wi-Fi: {radio_text}{stale}")

        message = ""
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
        self.query_one("#message", Static).update(message)

        active = snapshot.active_connection
        if active is None:
            summary = "Not connected"
        else:
            addresses = ", ".join(active.ipv4.addresses)
            summary = f"Connected to {active.ssid or active.profile_name}"
            if addresses:
                summary += f" · {addresses}"
        self.query_one("#connection-summary", Static).update(summary)

        busy = snapshot.operation.phase == OperationPhase.RUNNING
        self.query_one("#connect", Button).disabled = busy or not snapshot.networks
        self.query_one("#disconnect", Button).disabled = busy or active is None
        self.query_one("#refresh", Button).disabled = busy
        self.query_one("#details", Button).disabled = active is None
        self.query_one("#wifi", Button).label = (
            "Disable Wi-Fi" if radio == WifiRadioState.ENABLED else "Enable Wi-Fi"
        )

    def _selected_group(self) -> NetworkGroup | None:
        """Perform selected group."""
        identity = self.query_one("#networks", NetworkTable).selected_identity
        return next(
            (network for network in self.service.snapshot.networks if network.identity == identity),
            None,
        )

    def on_data_table_row_selected(self, _event: NetworkTable.RowSelected) -> None:
        """Perform on data table row selected."""
        self.action_connect()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Perform on button pressed."""
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
        """Perform action cursor down."""
        self.query_one("#networks", NetworkTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Perform action cursor up."""
        self.query_one("#networks", NetworkTable).action_cursor_up()

    def action_refresh_networks(self) -> None:
        """Perform action refresh networks."""
        self.run_worker(self._refresh(), group="refresh", exclusive=True)

    async def _refresh(self) -> None:
        """Perform refresh."""
        await self.service.refresh(request_scan=True)

    def action_connect(self) -> None:
        """Perform action connect."""
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
                self._connect(group, None, True),
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
        """Perform start open."""
        self.run_worker(self._connect(group, None, True), group="mutation", exclusive=True)

    def _start_password(self, group: NetworkGroup, answer: PasswordAnswer | None) -> None:
        """Perform start password."""
        if answer is not None:
            self.run_worker(
                self._connect(group, answer.password, answer.autoconnect),
                group="mutation",
                exclusive=True,
            )

    async def _connect(
        self,
        group: NetworkGroup,
        password: SecretValue | None,
        autoconnect: bool,
    ) -> None:
        """Perform connect."""
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
        except Exception as exc:
            self.app.push_screen(MessageDialog("Unexpected connection error", str(exc)))
        else:
            active = snapshot.active_connection
            if active is not None:
                self.notify(f"Connected to {active.ssid or active.profile_name}", timeout=5)

    def action_disconnect(self) -> None:
        """Perform action disconnect."""
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
        """Perform start disconnect."""
        self.run_worker(self._disconnect(), group="mutation", exclusive=True)

    async def _disconnect(self) -> None:
        """Perform disconnect."""
        try:
            await self.service.disconnect()
        except WifiError as exc:
            self.app.push_screen(MessageDialog(exc.summary, exc.guidance or "Disconnect failed."))

    def action_hidden(self) -> None:
        """Perform action hidden."""
        self.app.push_screen(HiddenNetworkDialog(), self._start_hidden)

    def _start_hidden(self, answer: HiddenNetworkAnswer | None) -> None:
        """Perform start hidden."""
        if answer is not None:
            self.run_worker(self._connect_hidden(answer), group="mutation", exclusive=True)

    async def _connect_hidden(self, answer: HiddenNetworkAnswer) -> None:
        """Perform connect hidden."""
        try:
            await self.service.connect_hidden(
                answer.ssid,
                answer.security,
                answer.password,
                answer.autoconnect,
            )
        except WifiError as exc:
            self.app.push_screen(MessageDialog(exc.summary, exc.guidance or "Connection failed."))
        else:
            self.notify(f"Connected to {answer.ssid}", timeout=5)

    def action_saved(self) -> None:
        """Perform action saved."""
        self.app.push_screen(SavedNetworksScreen(self.service))

    def action_details(self) -> None:
        """Perform action details."""
        self.app.push_screen(DetailsScreen(self.service.snapshot.active_connection))

    def action_toggle_wifi(self) -> None:
        """Perform action toggle wifi."""
        enabled = self.service.snapshot.status.wifi_radio != WifiRadioState.ENABLED
        if not enabled and self.service.snapshot.active_connection is not None:
            self.app.push_screen(
                ConfirmDialog(
                    "Disable Wi-Fi",
                    "This will interrupt the active Wi-Fi connection.",
                    "Disable",
                ),
                lambda confirmed: self._start_toggle(False) if confirmed else None,
            )
        else:
            self._start_toggle(enabled)

    def _start_toggle(self, enabled: bool) -> None:
        """Perform start toggle."""
        self.run_worker(self._toggle(enabled), group="mutation", exclusive=True)

    async def _toggle(self, enabled: bool) -> None:
        """Perform toggle."""
        try:
            await self.service.set_wifi_enabled(enabled)
        except WifiError as exc:
            self.app.push_screen(
                MessageDialog(
                    exc.summary,
                    exc.guidance or "Wi-Fi state did not change.",
                ),
            )
