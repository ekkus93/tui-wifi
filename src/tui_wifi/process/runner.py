from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Protocol

from tui_wifi.secrets import redact_arguments, redact_text


@dataclass(frozen=True, slots=True)
class ProcessRequest:
    executable: str
    args: tuple[str, ...] = field(default=(), repr=False)
    timeout: float = 10.0
    environment: dict[str, str] = field(default_factory=dict, repr=False)
    stdin: str | None = field(default=None, repr=False)
    sensitive_arg_indexes: frozenset[int] = frozenset()
    sensitive_stdin: bool = False

    def __post_init__(self) -> None:
        invalid_indexes = tuple(
            index for index in self.sensitive_arg_indexes if index < 0 or index >= len(self.args)
        )
        if invalid_indexes:
            raise ValueError(f"sensitive argument indexes are out of range: {invalid_indexes!r}")

    @property
    def redacted_command(self) -> tuple[str, ...]:
        return (self.executable, *redact_arguments(self.args, self.sensitive_arg_indexes))

    @property
    def sensitive_values(self) -> tuple[str, ...]:
        argument_values = tuple(self.args[index] for index in self.sensitive_arg_indexes)
        if self.sensitive_stdin and self.stdin:
            return (*argument_values, self.stdin)
        return argument_values


@dataclass(frozen=True, slots=True)
class ProcessResult:
    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False
    cancelled: bool = False


class ProcessError(Exception):
    def __init__(
        self, message: str, request: ProcessRequest, result: ProcessResult | None = None
    ) -> None:
        self.request = request
        self.result = result
        super().__init__(message)


class ProcessMissingExecutable(ProcessError):
    pass


class ProcessTimeout(ProcessError):
    pass


class ProcessCancelled(ProcessError):
    pass


class ProcessSpawnError(ProcessError):
    pass


class ProcessNonZeroExit(ProcessError):
    pass


class ProcessRunner(Protocol):
    async def run(self, request: ProcessRequest) -> ProcessResult: ...


class AsyncProcessRunner:
    async def run(self, request: ProcessRequest) -> ProcessResult:
        if request.timeout <= 0:
            raise ValueError("process timeout must be positive")

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
            raise ProcessMissingExecutable(
                f"executable not found: {request.executable}", request
            ) from exc
        except OSError as exc:
            raise ProcessSpawnError(
                f"could not start {request.executable}: {redact_text(str(exc))}", request
            ) from exc

        stdin_bytes = request.stdin.encode() if request.stdin is not None else None
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(stdin_bytes), timeout=request.timeout
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
            raise ProcessTimeout("process timed out", request, result) from exc
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
            raise ProcessCancelled("process cancelled", request, result) from exc

        try:
            stdout = stdout_bytes.decode("utf-8", errors="strict")
            stderr = stderr_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ProcessSpawnError("process returned invalid UTF-8", request) from exc

        result = ProcessResult(
            command=request.redacted_command,
            exit_code=process.returncode or 0,
            stdout=redact_text(stdout, request.sensitive_values),
            stderr=redact_text(stderr, request.sensitive_values),
            duration=time.monotonic() - started,
        )
        if result.exit_code != 0:
            raise ProcessNonZeroExit(
                f"process exited with status {result.exit_code}", request, result
            )
        return result
