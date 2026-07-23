from __future__ import annotations

import logging
from pathlib import Path

from tui_wifi.logging_config import configure_debug_logging


def test_debug_logging_uses_xdg_and_is_bounded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    path, warning = configure_debug_logging()
    assert warning is None
    assert path == tmp_path / "tui-wifi" / "debug.log"
    logging.getLogger("tui_wifi.test").debug("redacted metadata only")
    assert path.exists()
