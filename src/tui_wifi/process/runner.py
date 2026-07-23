"""Run subprocesses with strict timeouts and credential-safe diagnostics."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Protocol

from tui_wifi.secrets import redact_arguments, redact_text

_TERMINATION_TIMEOUT_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class ProcessRequest:
    """Describe one subprocess invocation."""

    executable: str
    args: tuple[str, ...] = field(default=(), repr=False)
    timeout: float = 10.0
    environment: dict[str, str] = field(default_factory=dict, repr=False)
    stdin: str | None = field(default=None, repr=False)
    sensitive_arg_indexes: frozenset[int] = frozenset()
    sensitive_stdin: bool = False

    def __post_init__(self) -> None:
        """Reject sensitive argument indexes that do not exist."""
        invalid_indexes = tuple(
            index for index in self.sensitive_arg_indexes if index < 0 or index >= len(self.args)
        )
        if invalid_indexes:
            message = f"sensitive argument indexes are out of range: {invalid_indexes!r}"
            raise ValueError(message)

    @property
    def redacted_command(self) -> tuple[str, ...]:
        """Return the executable and arguments with secrets removed."""
        return (self.executable, *redact_arguments(self.args, self.sensitive_arg_indexes))

    @property
    def sensitive_values(self) -> tuple[str, ...]:
        """Return secret values that must be removed from captured output."""
        argument_values = tuple(self.args[index] for index in self.sensitive_arg_indexes)
        if self.sensitive_stdin and self.stdin:
            return (*argument_values, self.stdin)
        return argument_values


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """Describe a completed or interrupted subprocess."""

    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False
    cancelled: bool = False


class ProcessError(Exception):
    """Base class for subprocess failures with redacted context."""

    def __init__(
        self,
        message: str,
        request: ProcessRequest,
        result: ProcessResult | None = None,
    ) -> None:
        """Initialize the subprocess failure."""
        self.request = request
        self.result = result
        super().__init__(message)


class ProcessMissingExecutableError(ProcessError):
    """Indicate that the requested executable does not exist."""


class ProcessTimeoutError(ProcessError):
    """Indicate that the subprocess exceeded its deadline."""


class ProcessCancelledError(ProcessError):
    """Indicate that the caller cancelled the subprocess operation."""


class ProcessSpawnError(ProcessError):
    """Indicate that the subprocess could not start or decode its output."""


class ProcessNonZeroExitError(ProcessError):
    """Indicate that the subprocess exited unsuccessfully."""


class ProcessRunner(Protocol):
    """Define the process-execution contract used by backends."""

    async def run(self, request: ProcessRequest) -> ProcessResult:
        """Run one process request and return its captured result."""
        ...


class AsyncProcessRunner:
    """Execute subprocesses asynchronously with strict failure handling."""

    @staticmethod
    def _environment(request: ProcessRequest) -> dict[str, str]:
        """Build a deterministic subprocess environment."""
        environment = os.environ.copy()
        environment.update({"LC_ALL": "C", "LANG": "C"})
        environment.update(request.environment)
        return environment

    @staticmethod
    async def _spawn(
        request: ProcessRequest,
        environment: dict[str, str],
    ) -> asyncio.subprocess.Process:
        """Start a subprocess and translate operating-system failures."""
        try:
            return await asyncio.create_subprocess_exec(
                request.executable,
                *request.args,
                stdin=asyncio.subprocess.PIPE if request.stdin is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=environment,
            )
        except FileNotFoundError as exc:
            message = f"executable not found: {request.executable}"
            raise ProcessMissingExecutableError(message, request) from exc
        except OSError as exc:
            message = f"could not start {request.executable}: {redact_text(str(exc))}"
            raise ProcessSpawnError(message, request) from exc

    @staticmethod
    async def _stop(process: asyncio.subprocess.Process) -> None:
        """Terminate a subprocess and escalate to kill when necessary."""
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=_TERMINATION_TIMEOUT_SECONDS)
        except TimeoutError:
            process.kill()
            await process.wait()

    @staticmethod
    def _interrupted_result(
        request: ProcessRequest,
        process: asyncio.subprocess.Process,
        started: float,
        *,
        timed_out: bool = False,
        cancelled: bool = False,
    ) -> ProcessResult:
        """Build a redacted result for an interrupted subprocess."""
        return ProcessResult(
            command=request.redacted_command,
            exit_code=process.returncode if process.returncode is not None else -1,
            stdout="",
            stderr="",
            duration=time.monotonic() - started,
            timed_out=timed_out,
            cancelled=cancelled,
        )

    async def _communicate(
        self,
        request: ProcessRequest,
        process: asyncio.subprocess.Process,
        started: float,
    ) -> tuple[bytes, bytes]:
        """Exchange process data and convert interruption into typed errors."""
        stdin_bytes = request.stdin.encode() if request.stdin is not None else None
        try:
            return await asyncio.wait_for(
                process.communicate(stdin_bytes),
                timeout=request.timeout,
            )
        except TimeoutError as exc:
            await self._stop(process)
            result = self._interrupted_result(
                request,
                process,
                started,
                timed_out=True,
            )
            message = "process timed out"
            raise ProcessTimeoutError(message, request, result) from exc
        except asyncio.CancelledError as exc:
            await self._stop(process)
            result = self._interrupted_result(
                request,
                process,
                started,
                cancelled=True,
            )
            message = "process cancelled"
            raise ProcessCancelledError(message, request, result) from exc

    @staticmethod
    def _decode_output(
        request: ProcessRequest,
        stdout_bytes: bytes,
        stderr_bytes: bytes,
    ) -> tuple[str, str]:
        """Decode strict UTF-8 output and redact all sensitive values."""
        try:
            stdout = stdout_bytes.decode("utf-8", errors="strict")
            stderr = stderr_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            message = "process returned invalid UTF-8"
            raise ProcessSpawnError(message, request) from exc
        return (
            redact_text(stdout, request.sensitive_values),
            redact_text(stderr, request.sensitive_values),
        )

    async def run(self, request: ProcessRequest) -> ProcessResult:
        """Execute one process request or raise a typed process error."""
        if request.timeout <= 0:
            message = "process timeout must be positive"
            raise ValueError(message)

        started = time.monotonic()
        process = await self._spawn(request, self._environment(request))
        stdout_bytes, stderr_bytes = await self._communicate(request, process, started)
        stdout, stderr = self._decode_output(request, stdout_bytes, stderr_bytes)
        result = ProcessResult(
            command=request.redacted_command,
            exit_code=process.returncode or 0,
            stdout=stdout,
            stderr=stderr,
            duration=time.monotonic() - started,
        )
        if result.exit_code != 0:
            message = f"process exited with status {result.exit_code}"
            raise ProcessNonZeroExitError(message, request, result)
        return result
