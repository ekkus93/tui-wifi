"""Verify test logging behavior."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tests.assertions import verify
from tui_wifi.logging_config import configure_debug_logging

if TYPE_CHECKING:
    from pathlib import Path


def test_debug_logging_uses_xdg_and_is_bounded(tmp_path: Path, monkeypatch) -> None:
    """Verify test debug logging uses xdg and is bounded."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    path, warning = configure_debug_logging()
    verify(warning is None)
    verify(path == tmp_path / "tui-wifi" / "debug.log")
    logging.getLogger("tui_wifi.test").debug("redacted metadata only")
    verify(path.exists())
