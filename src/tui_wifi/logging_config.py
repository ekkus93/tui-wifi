# Copyright (c) 2026 Phillip Chin
"""Provide logging config functionality."""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path


def configure_debug_logging() -> tuple[Path | None, str | None]:
    """Configure bounded debug logging under XDG state, returning a warning on failure."""
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    path = base / "tui-wifi" / "debug.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        handler = logging.handlers.RotatingFileHandler(
            path,
            maxBytes=1_000_000,
            backupCount=2,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root = logging.getLogger("tui_wifi")
        root.setLevel(logging.DEBUG)
        root.addHandler(handler)
    except OSError as exc:
        return None, f"Debug logging could not be enabled: {exc}"
    return path, None
