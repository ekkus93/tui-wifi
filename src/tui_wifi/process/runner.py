"""Provide runner functionality."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Protocol

from tui_wifi.secrets import redact_arguments, redact_text


@dataclass(frozen=True, slots=True)
class ProcessRequest:
    """Represent ProcessRequest."""

    executable: str
    args: tuple[str, ...] = field(default=(), repr=False)
    timeout: float = 10.0
    environment: dict[str, str] = field(default_factory=dict, repr=False)
    stdin: str | None = field(default=None, repr=False)
    sensitive_arg_indexes: frozenset[int] = frozenset()
    sensitive_stdin: bool = False

    def __post_init__(self) -> None:
        """Perform post init."""
        invalid_indexes = tuple(
            index for index in self.sensitive_arg_indexes if index < 0 or index >= len(self.args)
        )
        if invalid_indexes:
            msg = f"sensitive argument indexes are out of range: {invalid_indexes!r}"
            raise ValueError(msg)

    @property
    def redacted_command(self) -> tuple[str, ...]:
        """Perform redacted command."""
        return (self.executable, *redact_arguments(self.args, self.sensitive_arg_indexes))

    @property
    def sensitive_values(self) -> tuple[str, ...]:
        """Perform sensitive values."""
        argument_values = tuple(self.args[index] for index in self.sensitive_arg_indexes)
        if self.sensitive_stdin and self.stdin:
            return (*argument_values, self.stdin)
        return argument_values


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """Represent ProcessResult."""

    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False
    cancelled: bool = False


class ProcessError(Exception):
    """Represent ProcessError."""

    def __init__(
        self,
        message: str,
        request: ProcessRequest,
        result: ProcessResult | None = None,
    ) -> None:
        """Initialize the instance."""
        self.request = request
        self.result = result
        super().__init__(message)


class ProcessMissingExecutable(ProcessError):
    """Represent ProcessMissingExecutable."""


class ProcessTimeout(ProcessError):
    """Represent ProcessTimeout."""


class ProcessCancelled(ProcessError):
    """Represent ProcessCancelled."""


class ProcessSpawnError(ProcessError):
    """Represent ProcessSpawnError."""


class ProcessNonZeroExit(ProcessError):
    """Represent ProcessNonZeroExit."""


class ProcessRunner(Protocol):
    """Represent ProcessRunner."""

    async def run(self, request: ProcessRequest) -> ProcessResult:
        """Perform run."""
        ...


class AsyncProcessRunner:
    """Represent AsyncProcessRunner."""

    async def run(self, request: ProcessRequest) -> ProcessResult:
        """Perform run."""
        if request.timeout <= 0:
            msg = "process timeout must be positive"
            raise ValueError(msg)

        env = os.environ.copy()
        env.update({"LC_ALL": "C", "LANG": "C"})
        env.update(request.environment)
        started = time.monotonic()
        try:
            process = await asyncio.create_subprocess_exec(
                request.executable,
                *request.args,
                stdin=asyncio.subprocess.PIPE if request.stdin is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError as exc:
            msg = f"executable not found: {request.executable}"
            raise ProcessMissingExecutable(
                msg,
                request,
            ) from exc
        except OSError as exc:
            msg = f"could not start {request.executable}: {redact_text(str(exc))}"
            raise ProcessSpawnError(
                msg,
                request,
            ) from exc

        stdin_bytes = request.stdin.encode() if request.stdin is not None else None
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(stdin_bytes),
                timeout=request.timeout,
            )
        except TimeoutError as exc:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=1.0)
            except TimeoutError:
                process.kill()
                await process.wait()
            result = ProcessResult(
                command=request.redacted_command,
                exit_code=process.returncode if process.returncode is not None else -1,
                stdout="",
                stderr="",
                duration=time.monotonic() - started,
                timed_out=True,
            )
            msg = "process timed out"
            raise ProcessTimeout(msg, request, result) from exc
        except asyncio.CancelledError as exc:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=1.0)
            except TimeoutError:
                process.kill()
                await process.wait()
            result = ProcessResult(
                command=request.redacted_command,
                exit_code=process.returncode if process.returncode is not None else -1,
                stdout="",
                stderr="",
                duration=time.monotonic() - started,
                cancelled=True,
            )
            msg = "process cancelled"
            raise ProcessCancelled(msg, request, result) from exc

        try:
            stdout = stdout_bytes.decode("utf-8", errors="strict")
            stderr = stderr_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            msg = "process returned invalid UTF-8"
            raise ProcessSpawnError(msg, request) from exc

        result = ProcessResult(
            command=request.redacted_command,
            exit_code=process.returncode or 0,
            stdout=redact_text(stdout, request.sensitive_values),
            stderr=redact_text(stderr, request.sensitive_values),
            duration=time.monotonic() - started,
        )
        if result.exit_code != 0:
            msg = f"process exited with status {result.exit_code}"
            raise ProcessNonZeroExit(
                msg,
                request,
                result,
            )
        return result
