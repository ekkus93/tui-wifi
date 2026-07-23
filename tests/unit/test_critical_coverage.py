"""Verify structured critical-module coverage enforcement."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check_critical_coverage import GATES, branch_percentage, evaluate, load_report, main
from tests.assertions import verify


def report_with_percentage(percentage: float) -> dict[str, object]:
    """Build a complete synthetic report with one percentage for every gate."""
    return {
        "files": {
            gate.path: {"summary": {"percent_branches_covered": percentage}}
            for gate in GATES
        },
    }


def write_report(path: Path, percentage: float) -> None:
    """Write a synthetic structured coverage report."""
    path.write_text(json.dumps(report_with_percentage(percentage)), encoding="utf-8")


def test_all_module_gates_pass_at_or_above_threshold() -> None:
    """Verify equality with the strongest configured floor is accepted."""
    report = report_with_percentage(100.0)
    for gate in GATES:
        report["files"][gate.path]["summary"]["percent_branches_covered"] = gate.minimum
    verify(evaluate(report) == ())


def test_all_failures_are_reported_together() -> None:
    """Verify the checker does not hide later module regressions."""
    failures = evaluate(report_with_percentage(0.0))
    verify(len(failures) == len(GATES))
    for gate in GATES:
        verify(any(gate.path in failure for failure in failures))


def test_missing_or_invalid_module_data_fails_explicitly() -> None:
    """Verify absent and malformed structured fields are never treated as zero or success."""
    with pytest.raises(ValueError, match="required module"):
        branch_percentage({"files": {}}, GATES[0].path)
    with pytest.raises(ValueError, match="no summary"):
        branch_percentage({"files": {GATES[0].path: {}}}, GATES[0].path)
    with pytest.raises(ValueError, match="no branch percentage"):
        branch_percentage(
            {"files": {GATES[0].path: {"summary": {}}}},
            GATES[0].path,
        )


def test_load_report_rejects_non_object_root(tmp_path: Path) -> None:
    """Verify malformed JSON report shapes fail before gate evaluation."""
    report_path = tmp_path / "coverage.json"
    report_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="root"):
        load_report(report_path)


def test_main_statuses_cover_success_regression_and_invalid_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify shell statuses and diagnostics for every command outcome."""
    report_path = tmp_path / "coverage.json"
    write_report(report_path, 100.0)
    verify(main([str(report_path)]) == 0)
    verify("passed" in capsys.readouterr().out)

    write_report(report_path, 0.0)
    verify(main([str(report_path)]) == 1)
    verify("gates failed" in capsys.readouterr().out)

    report_path.write_text("not-json", encoding="utf-8")
    verify(main([str(report_path)]) == 2)
    verify("check failed" in capsys.readouterr().out)
