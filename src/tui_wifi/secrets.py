from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

_REDACTED = "<redacted>"


@dataclass(slots=True)
class SecretValue:
    _value: str

    def reveal(self) -> str:
        return self._value

    def clear(self) -> None:
        self._value = ""

    def __str__(self) -> str:
        return _REDACTED

    def __repr__(self) -> str:
        return "SecretValue(<redacted>)"


def redact_arguments(args: Iterable[str], sensitive_indexes: frozenset[int]) -> tuple[str, ...]:
    return tuple(
        _REDACTED if index in sensitive_indexes else value
        for index, value in enumerate(args)
    )


def redact_text(text: str, secrets: Iterable[str] = ()) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, _REDACTED)
    redacted = re.sub(
        r"(?i)(password|psk|passwd)(\s*[:=]\s*|\s+)([^\s,;]+)",
        rf"\1\2{_REDACTED}",
        redacted,
    )
    return redacted
