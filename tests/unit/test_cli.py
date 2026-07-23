# Copyright (c) 2026 Phillip Chin
"""Verify command-line behavior."""

from __future__ import annotations

import pytest

from tests.assertions import verify
from tui_wifi import cli


def test_cli_interface_and_debug_options() -> None:
    """Verify interface, debug, and mouse command-line options."""
    args = cli.build_parser().parse_args(["--interface", "wlan1", "--debug", "--no-mouse"])
    verify(args.interface == "wlan1")
    verify(args.debug is True)
    verify(args.no_mouse is True)


def test_cli_rejects_unknown_option() -> None:
    """Verify unknown command-line options fail visibly."""
    with pytest.raises(SystemExit) as caught:
        cli.build_parser().parse_args(["--not-real"])
    verify(caught.value.code != 0)


def test_main_runs_app_and_propagates_mouse_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify main constructs the app with resolved command-line settings."""
    calls: dict[str, object] = {}

    class FakeApp:
        """Record construction and run arguments for the CLI test."""

        def __init__(self, **kwargs: object) -> None:
            """Record application constructor arguments."""
            calls["kwargs"] = kwargs

        def run(self, *, mouse: bool = True) -> None:
            """Record the resolved mouse setting."""
            calls["mouse"] = mouse

    monkeypatch.setattr(cli, "WifiTuiApp", FakeApp)

    verify(cli.main(["--interface", "wlan0", "--no-mouse"]) == 0)
    verify(calls["mouse"] is False)
    verify(
        calls["kwargs"]
        == {
            "preferred_interface": "wlan0",
            "mouse_enabled": False,
            "startup_warning": None,
        },
    )
