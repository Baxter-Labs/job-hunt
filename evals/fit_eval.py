"""Evaluate one fit golden case against the REAL scoring.fit scorer.

Never reimplements scoring — imports scoring.fit and calls fit_report exactly as
the plugin does.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import scoring.fit as fit  # noqa: E402


def evaluate_fit_case(case: dict[str, Any]) -> dict[str, Any]:
    report = fit.fit_report(case["master"], case["jd"])
    expect = case["expect"]
    score = report["fit_score"]
    components = report["components"]
    reasons = report["reasons"]

    failures: list[str] = []
    if not (expect["fit_score_min"] <= score <= expect["fit_score_max"]):
        failures.append(
            f"fit_score {score} outside band "
            f"[{expect['fit_score_min']},{expect['fit_score_max']}]"
        )
    for name, bounds in expect.get("components", {}).items():
        val = components[name]
        if not (bounds["min"] <= val <= bounds["max"]):
            failures.append(
                f"component {name}={val} outside [{bounds['min']},{bounds['max']}]"
            )
    for needle in expect.get("must_include_reason", []):
        if not any(needle in r for r in reasons):
            failures.append(f"must_include_reason {needle!r} not found in reasons")

    return {
        "id": case["id"],
        "kind": "fit",
        "source": case.get("_source", case["id"]),
        "passed": not failures,
        "failures": failures,
        "score": score,
    }
