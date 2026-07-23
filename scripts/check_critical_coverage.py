# Copyright (c) 2026 Phillip Chin
"""Enforce structured branch-coverage floors for safety-critical modules."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CoverageGate:
    """Define the minimum branch percentage for one production module."""

    path: str
    minimum: float


GATES = (
    CoverageGate("src/tui_wifi/backends/nmcli_mutations.py", 90.0),
    CoverageGate("src/tui_wifi/backends/nmcli_profiles.py", 85.0),
    CoverageGate("src/tui_wifi/backends/nmcli_core.py", 85.0),
    CoverageGate("src/tui_wifi/services/wifi.py", 85.0),
    CoverageGate("src/tui_wifi/process/runner.py", 90.0),
)


def branch_percentage(report: dict[str, Any], path: str) -> float:
    """Return one module's branch coverage from a coverage.py JSON report."""
    files = report.get("files")
    if not isinstance(files, dict) or path not in files:
        message = f"coverage report does not contain required module: {path}"
        raise ValueError(message)
    file_report = files[path]
    if not isinstance(file_report, dict):
        message = f"coverage report contains invalid module data: {path}"
        raise TypeError(message)
    summary = file_report.get("summary")
    if not isinstance(summary, dict):
        message = f"coverage report contains no summary for module: {path}"
        raise TypeError(message)
    value = summary.get("percent_branches_covered")
    if not isinstance(value, int | float):
        message = f"coverage report contains no branch percentage for module: {path}"
        raise TypeError(message)
    return float(value)


def evaluate(report: dict[str, Any]) -> tuple[str, ...]:
    """Return human-readable failures for all unmet module gates."""
    failures: list[str] = []
    for gate in GATES:
        actual = branch_percentage(report, gate.path)
        if actual < gate.minimum:
            failures.append(
                f"{gate.path}: branch coverage {actual:.2f}% is below {gate.minimum:.2f}%",
            )
    return tuple(failures)


def load_report(path: Path) -> dict[str, Any]:
    """Load and validate the top-level JSON coverage object."""
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        message = "coverage report root must be a JSON object"
        raise TypeError(message)
    return value


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report",
        nargs="?",
        type=Path,
        default=Path("coverage.json"),
        help="coverage.py JSON report path",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Check all critical module gates and return a shell-compatible status."""
    args = build_parser().parse_args(argv)
    try:
        failures = evaluate(load_report(args.report))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        sys.stderr.write(f"critical coverage check failed: {exc}\n")
        return 2
    if failures:
        sys.stderr.write("critical coverage gates failed:\n")
        for failure in failures:
            sys.stderr.write(f"- {failure}\n")
        return 1
    sys.stdout.write("All critical module branch-coverage gates passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
