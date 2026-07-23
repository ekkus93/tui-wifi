from __future__ import annotations

import asyncio
import sys

import pytest

from tui_wifi.process import (
    AsyncProcessRunner,
    ProcessNonZeroExit,
    ProcessRequest,
    ProcessTimeout,
)


def test_process_success_and_no_shell_interpretation() -> None:
    async def scenario() -> None:
        result = await AsyncProcessRunner().run(
            ProcessRequest(
                sys.executable,
                ("-c", "import sys; print(sys.argv[1])", "$(touch /tmp/not-run)"),
                timeout=5,
            )
        )
        assert result.stdout.strip() == "$(touch /tmp/not-run)"
        assert result.exit_code == 0

    asyncio.run(scenario())


def test_process_nonzero_keeps_stdout_and_stderr_separate() -> None:
    async def scenario() -> None:
        request = ProcessRequest(
            sys.executable,
            ("-c", "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)"),
            timeout=5,
        )
        with pytest.raises(ProcessNonZeroExit) as caught:
            await AsyncProcessRunner().run(request)
        assert caught.value.result is not None
        assert caught.value.result.stdout.strip() == "out"
        assert caught.value.result.stderr.strip() == "err"
        assert caught.value.result.exit_code == 7

    asyncio.run(scenario())


def test_process_timeout_redacts_sensitive_metadata() -> None:
    async def scenario() -> None:
        request = ProcessRequest(
            sys.executable,
            ("-c", "import time; time.sleep(10)", "actual-password"),
            timeout=0.02,
            sensitive_arg_indexes=frozenset({2}),
        )
        with pytest.raises(ProcessTimeout) as caught:
            await AsyncProcessRunner().run(request)
        assert caught.value.result is not None
        assert "actual-password" not in repr(caught.value.result.command)

    asyncio.run(scenario())
