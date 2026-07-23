"""Verify asynchronous process execution."""

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

_EXPECTED_EXIT_CODE = 7


def test_process_success_and_no_shell_interpretation() -> None:
    """Verify arguments are passed without shell interpretation."""

    async def scenario() -> None:
        """Run a successful child process."""
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
    """Verify unsuccessful output streams remain separate."""

    async def scenario() -> None:
        """Run a child process that exits unsuccessfully."""
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
        verify(caught.value.result.exit_code == _EXPECTED_EXIT_CODE)

    asyncio.run(scenario())


def test_process_output_redacts_sensitive_argument_values() -> None:
    """Verify echoed sensitive arguments are removed from all diagnostics."""

    async def scenario() -> None:
        """Run a child process that echoes a protected argument."""
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
        verify(test_credential not in caught.value.result.stdout)
        verify(test_credential not in caught.value.result.stderr)
        verify("<redacted>" in caught.value.result.stdout)
        verify("<redacted>" in caught.value.result.stderr)
        verify(test_credential not in repr(caught.value.result.command))

    asyncio.run(scenario())


def test_process_timeout_redacts_sensitive_metadata() -> None:
    """Verify timeout diagnostics retain no protected argument value."""

    async def scenario() -> None:
        """Run a child process beyond its deadline."""
        request = ProcessRequest(
            sys.executable,
            ("-c", "import time; time.sleep(10)", "test-credential-value"),
            timeout=0.02,
            sensitive_arg_indexes=frozenset({2}),
        )
        with pytest.raises(ProcessTimeoutError) as caught:
            await AsyncProcessRunner().run(request)
        verify(caught.value.result is not None)
        verify("test-credential-value" not in repr(caught.value.result.command))

    asyncio.run(scenario())


def test_sensitive_argument_indexes_must_be_valid() -> None:
    """Verify invalid sensitive argument indexes fail immediately."""
    with pytest.raises(ValueError, match="out of range"):
        ProcessRequest("command", ("only",), sensitive_arg_indexes=frozenset({1}))
