"""Evaluate one ATS golden case against the REAL tailor.ats scorer.

Never reimplements scoring — imports tailor.ats and calls build_ats_report /
cv_text_from_tailored exactly as the plugin does.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import tailor.ats as ats  # noqa: E402


def _cv_text(case: dict[str, Any]) -> str:
    if "tailored_cv" in case:
        return ats.cv_text_from_tailored(case["tailored_cv"])
    return case["cv_text"]


def evaluate_ats_case(case: dict[str, Any]) -> dict[str, Any]:
    report = ats.build_ats_report(
        case["jd"],
        _cv_text(case),
        case.get("company", "Synthetic BV"),
        case.get("role", "Synthetic Role"),
    )
    expect = case["expect"]
    score = report["match_score"]
    matched = report["matched_keywords"]
    missing = report["missing_keywords"]
    matched_set = set(matched)
    missing_set = set(missing)
    all_set = matched_set | missing_set

    failures: list[str] = []
    if not (expect["score_min"] <= score <= expect["score_max"]):
        failures.append(
            f"score {score} outside band [{expect['score_min']},{expect['score_max']}]"
        )
    for kw in expect["must_match"]:
        if kw not in matched_set:
            failures.append(f"must_match {kw!r} not in matched_keywords")
    for kw in expect["must_miss"]:
        if kw not in missing_set:
            failures.append(f"must_miss {kw!r} not in missing_keywords")
    for kw in expect.get("must_not_appear", []):
        if kw in all_set:
            failures.append(f"must_not_appear {kw!r} appeared as a keyword")

    return {
        "id": case["id"],
        "kind": "ats",
        "source": case.get("_source", case["id"]),
        "passed": not failures,
        "failures": failures,
        "score": score,
    }
