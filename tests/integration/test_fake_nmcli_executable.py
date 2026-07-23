"""Verify test fake nmcli executable behavior."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from tests.assertions import verify
from tui_wifi.process import AsyncProcessRunner, ProcessRequest

if TYPE_CHECKING:
    from pathlib import Path


def test_fake_executable_receives_exact_arguments_and_locale(tmp_path: Path) -> None:
    """Verify test fake executable receives exact arguments and locale."""
    executable = tmp_path / "nmcli"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "print(os.environ['LC_ALL'])\n"
        "print('|'.join(sys.argv[1:]))\n",
    )
    executable.chmod(0o755)

    async def scenario() -> None:
        """Perform scenario."""
        result = await AsyncProcessRunner().run(
            ProcessRequest(
                os.fspath(executable),
                ("device", "wifi", "list", "SSID:with colon"),
                timeout=5,
            ),
        )
        lines = result.stdout.splitlines()
        verify(lines == ["C", "device|wifi|list|SSID:with colon"])

    asyncio.run(scenario())
