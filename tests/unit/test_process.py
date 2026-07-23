"""Verify subprocess lifecycle, decoding, and secret-safe diagnostics."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Coroutine
from typing import Any, TypeVar

import pytest

from tests.assertions import verify
from tui_wifi.process import (
    AsyncProcessRunner,
    ProcessCancelledError,
    ProcessMissingExecutableError,
    ProcessNonZeroExitError,
    ProcessRequest,
    ProcessSpawnError,
    ProcessTimeoutError,
)

T = TypeVar("T")
_EXPECTED_EXIT_CODE = 7
_SIGNAL_EXIT_CODE = -9


def run(coroutine: Coroutine[Any, Any, T]) -> T:
    """Run one coroutine in an isolated event loop."""
    return asyncio.run(coroutine)


class RunnerProbe(AsyncProcessRunner):
    """Expose deterministic helper behavior without test-only source suppressions."""

    @classmethod
    def environment_for(cls, request: ProcessRequest) -> dict[str, str]:
        """Return the environment that the runner would pass to a child."""
        return cls._environment(request)

    @classmethod
    async def stop_process(cls, process: asyncio.subprocess.Process) -> None:
        """Run the bounded process-stop routine for a controlled fake."""
        await cls._stop(process)


class ControlledProcess:
    """Model an asynchronous child process for cancellation and stop tests."""

    def __init__(self, *, ignore_terminate: bool = False) -> None:
        """Initialize process state and synchronization events."""
        self.returncode: int | None = None
        self.ignore_terminate = ignore_terminate
        self.communicate_entered = asyncio.Event()
        self.communicate_release = asyncio.Event()
        self.wait_release = asyncio.Event()
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    async def communicate(self, _stdin: bytes | None) -> tuple[bytes, bytes]:
        """Wait until released and return empty output."""
        self.communicate_entered.set()
        await self.communicate_release.wait()
        return b"", b""

    def terminate(self) -> None:
        """Record termination and optionally make wait complete."""
        self.terminated = True
        if not self.ignore_terminate:
            self.returncode = -15
            self.wait_release.set()

    def kill(self) -> None:
        """Record forced termination and make wait complete."""
        self.killed = True
        self.returncode = _SIGNAL_EXIT_CODE
        self.wait_release.set()

    async def wait(self) -> int:
        """Wait for termination and return the final code."""
        self.wait_calls += 1
        await self.wait_release.wait()
        return self.returncode or 0


def test_timeout_must_be_positive_before_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify zero and negative deadlines fail before process creation."""
    spawn_calls = 0

    async def fake_spawn(*_args: object, **_kwargs: object) -> ControlledProcess:
        """Record an unexpected attempt to spawn."""
        nonlocal spawn_calls
        spawn_calls += 1
        return ControlledProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)
    for timeout in (0, -1):
        request = ProcessRequest("command", ("secret-neighbor",), timeout=timeout)
        with pytest.raises(ValueError, match="timeout must be positive") as caught:
            run(AsyncProcessRunner().run(request))
        verify("secret-neighbor" not in str(caught.value))
    verify(spawn_calls == 0)


def test_environment_is_deterministic_inherited_and_not_mutated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify locale defaults, inheritance, overrides, and parent immutability."""
    monkeypatch.setenv("TUI_WIFI_PARENT_VALUE", "inherited")
    parent_before = os.environ.copy()
    request = ProcessRequest(
        "command",
        environment={"CUSTOM": "value", "LANG": "request-language"},
    )
    environment = RunnerProbe.environment_for(request)
    verify(environment["LC_ALL"] == "C")
    verify(environment["LANG"] == "request-language")
    verify(environment["TUI_WIFI_PARENT_VALUE"] == "inherited")
    verify(environment["CUSTOM"] == "value")
    verify(dict(os.environ) == parent_before)


def test_missing_executable_preserves_redacted_request() -> None:
    """Verify a nonexistent executable produces a typed spawn failure."""

    async def scenario() -> None:
        credential = "missing-executable-secret"
        request = ProcessRequest(
            "/definitely/not/a/real/tui-wifi-executable",
            (credential,),
            sensitive_arg_indexes=frozenset({0}),
        )
        with pytest.raises(ProcessMissingExecutableError) as caught:
            await AsyncProcessRunner().run(request)
        verify(caught.value.request is request)
        verify(caught.value.result is None)
        verify(credential not in repr(caught.value.request.redacted_command))

    run(scenario())


def test_generic_spawn_failure_redacts_operating_system_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify operating-system spawn errors retain their cause without leaking secrets."""

    async def failing_spawn(*_args: object, **_kwargs: object) -> ControlledProcess:
        """Raise a synthetic operating-system error."""
        raise OSError("password=spawn-secret")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", failing_spawn)
    request = ProcessRequest("command")
    with pytest.raises(ProcessSpawnError) as caught:
        run(AsyncProcessRunner().run(request))
    verify("spawn-secret" not in str(caught.value))
    verify(isinstance(caught.value.__cause__, OSError))


def test_stdin_delivery_and_none_stdin_behavior() -> None:
    """Verify ordinary stdin is delivered byte-for-byte and optional."""

    async def scenario() -> None:
        echo = await AsyncProcessRunner().run(
            ProcessRequest(
                sys.executable,
                (
                    "-c",
                    "import sys; data=sys.stdin.buffer.read(); "
                    "sys.stdout.buffer.write(data); sys.stderr.buffer.write(data)",
                ),
                stdin="line one\nline two",
            ),
        )
        verify(echo.stdout == "line one\nline two")
        verify(echo.stderr == "line one\nline two")

        no_input = await AsyncProcessRunner().run(
            ProcessRequest(
                sys.executable,
                ("-c", "import sys; print(sys.stdin is None)"),
            ),
        )
        verify(no_input.stdout.strip() == "False")

    run(scenario())


def test_sensitive_stdin_is_redacted_from_success_and_failure_output() -> None:
    """Verify echoed protected stdin never survives captured diagnostics."""

    async def scenario() -> None:
        credential = "stdin-credential-value"
        script = (
            "import sys; data=sys.stdin.read(); print(data); print(data, file=sys.stderr)"
        )
        success = await AsyncProcessRunner().run(
            ProcessRequest(
                sys.executable,
                ("-c", script),
                stdin=credential,
                sensitive_stdin=True,
            ),
        )
        verify(credential not in success.stdout)
        verify(credential not in success.stderr)
        verify("<redacted>" in success.stdout)
        verify("<redacted>" in success.stderr)

        with pytest.raises(ProcessNonZeroExitError) as caught:
            await AsyncProcessRunner().run(
                ProcessRequest(
                    sys.executable,
                    ("-c", f"{script}; raise SystemExit(2)"),
                    stdin=credential,
                    sensitive_stdin=True,
                ),
            )
        verify(caught.value.result is not None)
        verify(credential not in repr(caught.value.result))
        verify(credential not in str(caught.value))

    run(scenario())


def test_empty_sensitive_stdin_does_not_redact_every_empty_boundary() -> None:
    """Verify empty protected stdin does not trigger empty-string replacement."""

    async def scenario() -> None:
        result = await AsyncProcessRunner().run(
            ProcessRequest(
                sys.executable,
                ("-c", "print('ordinary-output')"),
                stdin="",
                sensitive_stdin=True,
            ),
        )
        verify(result.stdout.strip() == "ordinary-output")
        verify("<redacted>" not in result.stdout)

    run(scenario())


def test_combined_argument_and_stdin_redaction_preserves_neighboring_text() -> None:
    """Verify argument and stdin values are independently removed."""

    async def scenario() -> None:
        argument_secret = "argument-secret-value"
        stdin_secret = "stdin-secret-value"
        result = await AsyncProcessRunner().run(
            ProcessRequest(
                sys.executable,
                (
                    "-c",
                    "import sys; data=sys.stdin.read(); "
                    "print('prefix', sys.argv[1], data, 'suffix'); "
                    "print('error', sys.argv[1], data, file=sys.stderr)",
                    argument_secret,
                ),
                stdin=stdin_secret,
                sensitive_arg_indexes=frozenset({2}),
                sensitive_stdin=True,
            ),
        )
        for output in (result.stdout, result.stderr):
            verify(argument_secret not in output)
            verify(stdin_secret not in output)
            verify("<redacted>" in output)
        verify("prefix" in result.stdout)
        verify("suffix" in result.stdout)
        verify("error" in result.stderr)

    run(scenario())


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_invalid_utf8_is_a_typed_failure_without_partial_output(stream: str) -> None:
    """Verify strict decoding rejects invalid bytes from either output stream."""

    async def scenario() -> None:
        target = "stdout" if stream == "stdout" else "stderr"
        script = f"import sys; sys.{target}.buffer.write(bytes([255]))"
        request = ProcessRequest(sys.executable, ("-c", script))
        with pytest.raises(ProcessSpawnError) as caught:
            await AsyncProcessRunner().run(request)
        verify(caught.value.result is None)
        verify("invalid UTF-8" in str(caught.value))

    run(scenario())


def test_cancellation_stops_child_and_returns_redacted_cancelled_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cancellation terminates and reaps the child deterministically."""

    async def scenario() -> None:
        process = ControlledProcess()

        async def fake_spawn(*_args: object, **_kwargs: object) -> ControlledProcess:
            """Return the controlled process."""
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)
        credential = "cancel-secret-value"
        request = ProcessRequest(
            "command",
            (credential,),
            sensitive_arg_indexes=frozenset({0}),
        )
        task = asyncio.create_task(AsyncProcessRunner().run(request))
        await process.communicate_entered.wait()
        task.cancel()
        with pytest.raises(ProcessCancelledError) as caught:
            await task
        verify(process.terminated is True)
        verify(process.wait_calls >= 1)
        verify(caught.value.result is not None)
        verify(caught.value.result.cancelled is True)
        verify(caught.value.result.timed_out is False)
        verify(credential not in repr(caught.value.result.command))

    run(scenario())


def test_terminate_escalates_to_kill_and_reaps_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a child that ignores terminate is killed after the bounded wait."""

    async def scenario() -> None:
        process = ControlledProcess(ignore_terminate=True)
        monkeypatch.setattr("tui_wifi.process.runner._TERMINATION_TIMEOUT_SECONDS", 0.001)
        await RunnerProbe.stop_process(process)
        verify(process.terminated is True)
        verify(process.killed is True)
        verify(process.wait_calls >= 2)
        verify(process.returncode == _SIGNAL_EXIT_CODE)

    run(scenario())


def test_timeout_result_flags_duration_and_redaction() -> None:
    """Verify interrupted timeout metadata is explicit and credential-safe."""

    async def scenario() -> None:
        credential = "timeout-secret-value"
        request = ProcessRequest(
            sys.executable,
            ("-c", "import time; time.sleep(10)", credential),
            timeout=0.01,
            sensitive_arg_indexes=frozenset({2}),
        )
        with pytest.raises(ProcessTimeoutError) as caught:
            await AsyncProcessRunner().run(request)
        result = caught.value.result
        verify(result is not None)
        verify(result.timed_out is True)
        verify(result.cancelled is False)
        verify(result.exit_code in {-1, -15, _SIGNAL_EXIT_CODE})
        verify(result.stdout == "")
        verify(result.stderr == "")
        verify(result.duration >= 0)
        verify(credential not in repr(result.command))

    run(scenario())


@pytest.mark.parametrize("exit_code", [_EXPECTED_EXIT_CODE, _SIGNAL_EXIT_CODE])
def test_nonzero_exit_codes_are_preserved(exit_code: int) -> None:
    """Verify positive and signal-style failures retain exact return codes."""

    async def scenario() -> None:
        script = (
            "import sys; print('out', flush=True); "
            "print('err', file=sys.stderr, flush=True); "
            f"raise SystemExit({exit_code})"
            if exit_code >= 0
            else "import os,signal; os.kill(os.getpid(), signal.SIGKILL)"
        )
        with pytest.raises(ProcessNonZeroExitError) as caught:
            await AsyncProcessRunner().run(ProcessRequest(sys.executable, ("-c", script)))
        verify(caught.value.result is not None)
        verify(caught.value.result.exit_code == exit_code)
        if exit_code > 0:
            verify(caught.value.result.stdout.strip() == "out")
            verify(caught.value.result.stderr.strip() == "err")

    run(scenario())


def test_success_keeps_stdout_and_stderr_separate() -> None:
    """Verify a zero exit returns independently captured streams."""

    async def scenario() -> None:
        result = await AsyncProcessRunner().run(
            ProcessRequest(
                sys.executable,
                ("-c", "import sys; print('out'); print('err', file=sys.stderr)"),
            ),
        )
        verify(result.exit_code == 0)
        verify(result.stdout.strip() == "out")
        verify(result.stderr.strip() == "err")

    run(scenario())


def test_sensitive_argument_indexes_must_be_valid() -> None:
    """Verify invalid sensitive argument indexes fail immediately."""
    with pytest.raises(ValueError, match="out of range"):
        ProcessRequest("command", ("only",), sensitive_arg_indexes=frozenset({1}))
