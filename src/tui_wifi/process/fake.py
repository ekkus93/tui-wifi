# Copyright (c) 2026 Phillip Chin
"""Provide fake functionality."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass

from tui_wifi.process.runner import ProcessRequest, ProcessResult, ProcessRunner


@dataclass(slots=True)
class ExpectedProcess:
    """Represent ExpectedProcess."""

    executable: str
    args: tuple[str, ...]
    result: ProcessResult | Exception
    delay: float = 0.0


class FakeProcessRunner(ProcessRunner):
    """Represent FakeProcessRunner."""

    def __init__(self) -> None:
        """Initialize the instance."""
        self.expected: deque[ExpectedProcess] = deque()
        self.invocations: list[tuple[str, ...]] = []
        self.requests: list[ProcessRequest] = []

    def queue(
        self,
        executable: str,
        args: tuple[str, ...],
        result: ProcessResult | Exception,
        *,
        delay: float = 0.0,
    ) -> None:
        """Perform queue."""
        self.expected.append(ExpectedProcess(executable, args, result, delay))

    async def run(self, request: ProcessRequest) -> ProcessResult:
        """Perform run."""
        if not self.expected:
            msg = f"unexpected command: {request.redacted_command!r}"
            raise AssertionError(msg)
        expected = self.expected.popleft()
        actual = (request.executable, *request.args)
        if actual != (expected.executable, *expected.args):
            msg = (
                "command mismatch\n"
                f"expected={(expected.executable, *expected.args)!r}\n"
                f"actual={actual!r}"
            )
            raise AssertionError(
                msg,
            )
        self.requests.append(request)
        self.invocations.append(request.redacted_command)
        if expected.delay:
            await asyncio.sleep(expected.delay)
        if isinstance(expected.result, Exception):
            raise expected.result
        return expected.result

    def assert_finished(self) -> None:
        """Perform assert finished."""
        if self.expected:
            msg = f"{len(self.expected)} expected commands were not executed"
            raise AssertionError(msg)
