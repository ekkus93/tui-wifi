from __future__ import annotations

import asyncio
import os
from pathlib import Path

from tui_wifi.process import AsyncProcessRunner, ProcessRequest


def test_fake_executable_receives_exact_arguments_and_locale(tmp_path: Path) -> None:
    executable = tmp_path / "nmcli"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "print(os.environ['LC_ALL'])\n"
        "print('|'.join(sys.argv[1:]))\n"
    )
    executable.chmod(0o755)

    async def scenario() -> None:
        result = await AsyncProcessRunner().run(
            ProcessRequest(
                os.fspath(executable),
                ("device", "wifi", "list", "SSID:with colon"),
                timeout=5,
            )
        )
        lines = result.stdout.splitlines()
        assert lines == ["C", "device|wifi|list|SSID:with colon"]

    asyncio.run(scenario())
