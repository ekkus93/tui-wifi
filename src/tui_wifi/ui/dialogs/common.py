from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from tui_wifi.models import SecurityClass
from tui_wifi.secrets import SecretValue


@dataclass(frozen=True, slots=True)
class PasswordAnswer:
    password: SecretValue
    autoconnect: bool


@dataclass(frozen=True, slots=True)
class HiddenNetworkAnswer:
    ssid: str
    security: SecurityClass
    password: SecretValue | None
    autoconnect: bool


class ConfirmDialog(ModalScreen[bool]):
    def __init__(self, title: str, message: str, confirm_label: str = "Confirm") -> None:
        super().__init__()
        self.dialog_title = title
        self.message = message
        self.confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.dialog_title, classes="dialog-title")
            yield Static(self.message)
            with Horizontal(classes="dialog-buttons"):
                yield Button(self.confirm_label, id="confirm", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")


class MessageDialog(ModalScreen[None]):
    def __init__(self, title: str, message: str, technical_details: str | None = None) -> None:
        super().__init__()
        self.dialog_title = title
        self.message = message
        self.technical_details = technical_details

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.dialog_title, classes="dialog-title")
            yield Static(self.message)
            if self.technical_details:
                yield Static(self.technical_details, classes="technical-details")
            yield Button("Close", id="close", variant="primary")

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        self.dismiss(None)


class PasswordDialog(ModalScreen[PasswordAnswer | None]):
    def __init__(self, ssid: str) -> None:
        super().__init__()
        self.ssid = ssid

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(f"Connect to {self.ssid}", classes="dialog-title")
            yield Input(placeholder="Wi-Fi password", password=True, id="password")
            yield Checkbox("Show password", id="show-password")
            yield Checkbox("Connect automatically", value=True, id="autoconnect")
            yield Static("", id="validation", classes="validation")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Connect", id="connect", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "show-password":
            self.query_one("#password", Input).password = not event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self._clear_and_dismiss(None)
            return
        value = self.query_one("#password", Input).value
        if value == "":
            self.query_one("#validation", Static).update("Enter the network password.")
            return
        answer = PasswordAnswer(
            SecretValue(value), self.query_one("#autoconnect", Checkbox).value
        )
        self._clear_and_dismiss(answer)

    def _clear_and_dismiss(self, answer: PasswordAnswer | None) -> None:
        self.query_one("#password", Input).value = ""
        self.dismiss(answer)


class HiddenNetworkDialog(ModalScreen[HiddenNetworkAnswer | None]):
    OPTIONS: ClassVar[list[tuple[str, str]]] = [
        ("Open", SecurityClass.OPEN.value),
        ("WPA/WPA2/WPA3 Personal", SecurityClass.MIXED_PERSONAL.value),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("Connect to a hidden network", classes="dialog-title")
            yield Input(placeholder="Network name (SSID)", id="ssid")
            yield Select(
                self.OPTIONS,
                value=SecurityClass.MIXED_PERSONAL.value,
                allow_blank=False,
                id="security",
            )
            yield Input(placeholder="Wi-Fi password", password=True, id="password")
            yield Checkbox("Show password", id="show-password")
            yield Checkbox("Connect automatically", value=True, id="autoconnect")
            yield Static("", id="validation", classes="validation")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Connect", id="connect", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "show-password":
            self.query_one("#password", Input).password = not event.value

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "security":
            is_open = event.value == SecurityClass.OPEN.value
            self.query_one("#password", Input).disabled = is_open

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self._clear_and_dismiss(None)
            return
        ssid = self.query_one("#ssid", Input).value
        if not ssid:
            self.query_one("#validation", Static).update("Enter the network name.")
            return
        selected = self.query_one("#security", Select).value
        if not isinstance(selected, str):
            self.query_one("#validation", Static).update("Select a security type.")
            return
        security = SecurityClass(selected)
        password_text = self.query_one("#password", Input).value
        if security.requires_password and password_text == "":
            self.query_one("#validation", Static).update("Enter the network password.")
            return
        answer = HiddenNetworkAnswer(
            ssid=ssid,
            security=security,
            password=SecretValue(password_text) if security.requires_password else None,
            autoconnect=self.query_one("#autoconnect", Checkbox).value,
        )
        self._clear_and_dismiss(answer)

    def _clear_and_dismiss(self, answer: HiddenNetworkAnswer | None) -> None:
        self.query_one("#password", Input).value = ""
        self.dismiss(answer)
