# Copyright (c) 2026 Phillip Chin
"""Provide shared Textual pilot helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.pilot import Pilot
    from textual.widgets import Static

_SETTLE_CYCLES = 4


async def settle(pilot: Pilot[object]) -> None:
    """Allow mounted workers, callbacks, and screen transitions to complete."""
    for _cycle in range(_SETTLE_CYCLES):
        await pilot.pause()


def static_text(widget: Static) -> str:
    """Return stable text from a rendered Static widget."""
    return str(widget.render())
