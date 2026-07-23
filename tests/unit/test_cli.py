"""Verify test cli behavior."""

from __future__ import annotations

import pytest

from tests.assertions import verify
from tui_wifi.cli import build_parser


def test_cli_interface_and_debug_options() -> None:
    """Verify test cli interface and debug options."""
    args = build_parser().parse_args(["--interface", "wlan1", "--debug", "--no-mouse"])
    verify(args.interface == "wlan1")
    verify(args.debug is True)
    verify(args.no_mouse is True)


def test_cli_rejects_unknown_option() -> None:
    """Verify test cli rejects unknown option."""
    with pytest.raises(SystemExit) as caught:
        build_parser().parse_args(["--not-real"])
    verify(caught.value.code != 0)


def test_main_runs_app_and_propagates_mouse_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify test main runs app and propagates mouse setting."""
    import sys
    import types

    calls: dict[str, object] = {}

    class FakeApp:
        """Represent FakeApp."""

        def __init__(self, **kwargs: object) -> None:
            """Initialize the instance."""
            calls["kwargs"] = kwargs

        def run(self, *, mouse: bool = True) -> None:
            """Perform run."""
            calls["mouse"] = mouse

    module = types.ModuleType("tui_wifi.app")
    module.WifiTuiApp = FakeApp  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tui_wifi.app", module)

    from tui_wifi.cli import main

    verify(main(["--interface", "wlan0", "--no-mouse"]) == 0)
    verify(calls["mouse"] is False)
    verify(
        calls["kwargs"]
        == {
            "preferred_interface": "wlan0",
            "mouse_enabled": False,
            "startup_warning": None,
        },
    )
