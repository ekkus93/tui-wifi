# Copyright (c) 2026 Phillip Chin
"""Verify password, confirmation, message, and hidden-network dialogs."""

from __future__ import annotations

import asyncio

from textual.widgets import Checkbox, Input, Select, Static

from tests.assertions import verify
from tests.tui.helpers import settle, static_text
from tui_wifi.app import WifiTuiApp
from tui_wifi.backends.fake import FakeWifiBackend
from tui_wifi.models import SecurityClass
from tui_wifi.services.wifi import WifiService
from tui_wifi.ui.dialogs.common import (
    ConfirmDialog,
    HiddenNetworkAnswer,
    HiddenNetworkDialog,
    MessageDialog,
    PasswordAnswer,
    PasswordDialog,
)


def test_password_dialog_validation_visibility_and_submission() -> None:
    """Verify obscuring, show-password, validation, auto-connect, submit, and cancel."""

    async def scenario() -> None:
        app = WifiTuiApp(service=WifiService(FakeWifiBackend()))
        answers: list[PasswordAnswer | None] = []
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            app.push_screen(PasswordDialog("Home"), answers.append)
            await settle(pilot)
            password = app.screen.query_one("#password", Input)
            verify(password.password is True)

            await pilot.click("#connect")
            await settle(pilot)
            verify(
                "Enter the network password"
                in static_text(app.screen.query_one("#validation", Static)),
            )
            verify(answers == [])

            password.value = "synthetic-password"
            await pilot.click("#show-password")
            verify(password.password is False)
            app.screen.query_one("#autoconnect", Checkbox).value = False
            await pilot.click("#connect")
            await settle(pilot)
            verify(len(answers) == 1)
            answer = answers[0]
            verify(isinstance(answer, PasswordAnswer))
            verify(answer.password.reveal() == "synthetic-password")
            verify(answer.autoconnect is False)
            verify(password.value == "")

            answers.clear()
            app.push_screen(PasswordDialog("Home"), answers.append)
            await settle(pilot)
            app.screen.query_one("#password", Input).value = "cancelled-secret"
            await pilot.click("#cancel")
            await settle(pilot)
            verify(answers == [None])

    asyncio.run(scenario())


def test_hidden_dialog_open_personal_validation_and_cancel() -> None:
    """Verify hidden-network field validation and exact answer construction."""

    async def scenario() -> None:
        app = WifiTuiApp(service=WifiService(FakeWifiBackend()))
        answers: list[HiddenNetworkAnswer | None] = []
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            app.push_screen(HiddenNetworkDialog(), answers.append)
            await settle(pilot)

            await pilot.click("#connect")
            await settle(pilot)
            verify(
                "Enter the network name"
                in static_text(app.screen.query_one("#validation", Static)),
            )
            app.screen.query_one("#ssid", Input).value = "Hidden Personal"
            await settle(pilot)
            await pilot.click("#connect")
            await settle(pilot)
            verify(
                "Enter the network password"
                in static_text(app.screen.query_one("#validation", Static)),
            )

            app.screen.query_one("#password", Input).value = "hidden-secret"
            app.screen.query_one("#autoconnect", Checkbox).value = False
            await pilot.click("#show-password")
            verify(app.screen.query_one("#password", Input).password is False)
            await pilot.click("#connect")
            await settle(pilot)
            personal = answers.pop()
            verify(isinstance(personal, HiddenNetworkAnswer))
            verify(personal.ssid == "Hidden Personal")
            verify(personal.security == SecurityClass.MIXED_PERSONAL)
            verify(personal.password is not None)
            verify(personal.password.reveal() == "hidden-secret")
            verify(personal.autoconnect is False)

            app.push_screen(HiddenNetworkDialog(), answers.append)
            await settle(pilot)
            app.screen.query_one("#ssid", Input).value = "Hidden Open"
            app.screen.query_one("#security", Select).value = SecurityClass.OPEN.value
            await settle(pilot)
            verify(app.screen.query_one("#password", Input).disabled is True)
            await pilot.click("#connect")
            await settle(pilot)
            open_answer = answers.pop()
            verify(isinstance(open_answer, HiddenNetworkAnswer))
            verify(open_answer.security == SecurityClass.OPEN)
            verify(open_answer.password is None)

            app.push_screen(HiddenNetworkDialog(), answers.append)
            await settle(pilot)
            app.screen.query_one("#ssid", Input).value = "Cancelled"
            app.screen.query_one("#password", Input).value = "cancelled-secret"
            await pilot.click("#cancel")
            await settle(pilot)
            verify(answers == [None])

    asyncio.run(scenario())


def test_confirm_and_message_dialog_callbacks() -> None:
    """Verify destructive confirmation and informational dismissal results."""

    async def scenario() -> None:
        app = WifiTuiApp(service=WifiService(FakeWifiBackend()))
        confirmations: list[bool] = []
        messages: list[None] = []
        async with app.run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            app.push_screen(
                ConfirmDialog("Delete", "Delete it?", "Delete"),
                confirmations.append,
            )
            await settle(pilot)
            await pilot.click("#cancel")
            await settle(pilot)
            verify(confirmations == [False])

            app.push_screen(
                ConfirmDialog("Delete", "Delete it?", "Delete"),
                confirmations.append,
            )
            await settle(pilot)
            await pilot.click("#confirm")
            await settle(pilot)
            verify(confirmations == [False, True])

            app.push_screen(
                MessageDialog("Failure", "Friendly text", "safe details"),
                messages.append,
            )
            await settle(pilot)
            visible_text = " ".join(static_text(widget) for widget in app.screen.query(Static))
            verify("Friendly text" in visible_text)
            verify("safe details" in visible_text)
            await pilot.click("#close")
            await settle(pilot)
            verify(messages == [None])

    asyncio.run(scenario())
