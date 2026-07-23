from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass

from tui_wifi.process.runner import ProcessRequest, ProcessResult, ProcessRunner


@dataclass(slots=True)
class ExpectedProcess:
    executable: str
    args: tuple[str, ...]
    result: ProcessResult | Exception
    delay: float = 0.0


class FakeProcessRunner(ProcessRunner):
    def __init__(self) -> None:
        self.expected: deque[ExpectedProcess] = deque()
        self.invocations: list[tuple[str, ...]] = []

    def queue(
        self,
        executable: str,
        args: tuple[str, ...],
        result: ProcessResult | Exception,
        *,
        delay: float = 0.0,
    ) -> None:
        self.expected.append(ExpectedProcess(executable, args, result, delay))

    async def run(self, request: ProcessRequest) -> ProcessResult:
        if not self.expected:
            raise AssertionError(f"unexpected command: {request.redacted_command!r}")
        expected = self.expected.popleft()
        actual = (request.executable, *request.args)
        if actual != (expected.executable, *expected.args):
            raise AssertionError(
                "command mismatch\n"
                f"expected={(expected.executable, *expected.args)!r}\n"
                f"actual={actual!r}"
            )
        self.invocations.append(request.redacted_command)
        if expected.delay:
            await asyncio.sleep(expected.delay)
        if isinstance(expected.result, Exception):
            raise expected.result
        return expected.result

    def assert_finished(self) -> None:
        if self.expected:
            raise AssertionError(f"{len(self.expected)} expected commands were not executed")
