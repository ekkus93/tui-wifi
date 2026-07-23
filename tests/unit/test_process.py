"""Verify test process behavior."""

from __future__ import annotations

import asyncio
import sys

import pytest

from tests.assertions import verify
from tui_wifi.process import (
    AsyncProcessRunner,
    ProcessNonZeroExitError,
    ProcessRequest,
    ProcessTimeoutError,
)

_COMPARISON_VALUE_7 = 7


def test_process_success_and_no_shell_interpretation() -> None:
    """Verify test process success and no shell interpretation."""

    async def scenario() -> None:
        """Perform scenario."""
        result = await AsyncProcessRunner().run(
            ProcessRequest(
                sys.executable,
                ("-c", "import sys; print(sys.argv[1])", "$(touch /tmp/not-run)"),
                timeout=5,
            ),
        )
        verify(result.stdout.strip() == "$(touch /tmp/not-run)")
        verify(result.exit_code == 0)

    asyncio.run(scenario())


def test_process_nonzero_keeps_stdout_and_stderr_separate() -> None:
    """Verify test process nonzero keeps stdout and stderr separate."""

    async def scenario() -> None:
        """Perform scenario."""
        request = ProcessRequest(
            sys.executable,
            ("-c", "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)"),
            timeout=5,
        )
        with pytest.raises(ProcessNonZeroExitError) as caught:
            await AsyncProcessRunner().run(request)
        verify(caught.value.result is not None)
        verify(caught.value.result.stdout.strip() == "out")
        verify(caught.value.result.stderr.strip() == "err")
        verify(caught.value.result.exit_code == _COMPARISON_VALUE_7)

    asyncio.run(scenario())


def test_process_output_redacts_sensitive_argument_values() -> None:
    """Verify test process output redacts sensitive argument values."""

    async def scenario() -> None:
        """Perform scenario."""
        test_credential = "credential-that-must-not-leak"
        request = ProcessRequest(
            sys.executable,
            (
                "-c",
                "import sys; print(sys.argv[1]); print(sys.argv[1], file=sys.stderr); "
                "raise SystemExit(9)",
                test_credential,
            ),
            timeout=5,
            sensitive_arg_indexes=frozenset({2}),
        )
        with pytest.raises(ProcessNonZeroExitError) as caught:
            await AsyncProcessRunner().run(request)
        verify(caught.value.result is not None)
        verify(secret not in caught.value.result.stdout)
        verify(secret not in caught.value.result.stderr)
        verify("<redacted>" in caught.value.result.stdout)
        verify("<redacted>" in caught.value.result.stderr)
        verify(secret not in repr(caught.value.result.command))

    asyncio.run(scenario())


def test_process_timeout_redacts_sensitive_metadata() -> None:
    """Verify test process timeout redacts sensitive metadata."""

    async def scenario() -> None:
        """Perform scenario."""
        request = ProcessRequest(
            sys.executable,
            ("-c", "import time; time.sleep(10)", "actual-password"),
            timeout=0.02,
            sensitive_arg_indexes=frozenset({2}),
        )
        with pytest.raises(ProcessTimeoutError) as caught:
            await AsyncProcessRunner().run(request)
        verify(caught.value.result is not None)
        verify("actual-password" not in repr(caught.value.result.command))

    asyncio.run(scenario())


def test_sensitive_argument_indexes_must_be_valid() -> None:
    """Verify test sensitive argument indexes must be valid."""
    with pytest.raises(ValueError):
        ProcessRequest("command", ("only",), sensitive_arg_indexes=frozenset({1}))
