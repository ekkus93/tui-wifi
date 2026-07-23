from __future__ import annotations

import pytest

from tui_wifi.cli import build_parser


def test_cli_interface_and_debug_options() -> None:
    args = build_parser().parse_args(["--interface", "wlan1", "--debug", "--no-mouse"])
    assert args.interface == "wlan1"
    assert args.debug is True
    assert args.no_mouse is True


def test_cli_rejects_unknown_option() -> None:
    with pytest.raises(SystemExit) as caught:
        build_parser().parse_args(["--not-real"])
    assert caught.value.code != 0


def test_main_runs_app_and_propagates_mouse_setting(monkeypatch) -> None:
    import sys
    import types

    calls: dict[str, object] = {}

    class FakeApp:
        def __init__(self, **kwargs: object) -> None:
            calls["kwargs"] = kwargs

        def run(self, *, mouse: bool = True) -> None:
            calls["mouse"] = mouse

    module = types.ModuleType("tui_wifi.app")
    module.WifiTuiApp = FakeApp  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tui_wifi.app", module)

    from tui_wifi.cli import main

    assert main(["--interface", "wlan0", "--no-mouse"]) == 0
    assert calls["mouse"] is False
    assert calls["kwargs"] == {
        "preferred_interface": "wlan0",
        "mouse_enabled": False,
        "startup_warning": None,
    }
