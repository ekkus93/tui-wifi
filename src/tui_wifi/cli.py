# Copyright (c) 2026 Phillip Chin
"""Provide the command-line entry point for tui-wifi."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from tui_wifi import __version__
from tui_wifi.app import WifiTuiApp
from tui_wifi.logging_config import configure_debug_logging

if TYPE_CHECKING:
    from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="tui-wifi",
        description="A desktop-like terminal Wi-Fi manager for NetworkManager.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--debug", action="store_true", help="write redacted debug logs")
    parser.add_argument("--interface", metavar="NAME", help="select a Wi-Fi interface")
    parser.add_argument(
        "--no-mouse",
        action="store_true",
        help="disable mouse capture when supported by the terminal",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and run the TUI until it exits."""
    args = build_parser().parse_args(argv)
    warning: str | None = None
    if args.debug:
        _, warning = configure_debug_logging()

    app = WifiTuiApp(
        preferred_interface=args.interface,
        mouse_enabled=not args.no_mouse,
        startup_warning=warning,
    )
    try:
        app.run(mouse=not args.no_mouse)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
