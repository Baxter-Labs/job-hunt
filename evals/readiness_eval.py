"""Evaluate one readiness golden case against the REAL scoring.readiness scorer.

Materializes the case's synthetic pack in a throwaway temp dir (offline, no
network), calls readiness_report exactly as the plugin does, and checks the
score band, the blocking flag, and suggestion membership. Never reimplements
scoring.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import scoring.readiness as readiness  # noqa: E402


def _materialize_pack(spec: dict[str, Any]) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="readiness_eval_"))
    if isinstance(spec.get("ats_report"), dict):
        (tmp / "ats_report.json").write_text(json.dumps(spec["ats_report"]), encoding="utf-8")
    if isinstance(spec.get("tailored_cv"), dict):
        (tmp / "tailored_cv.json").write_text(json.dumps(spec["tailored_cv"]), encoding="utf-8")
    for name in spec.get("files", []):
        (tmp / name).write_text("stub", encoding="utf-8")
    return tmp


def evaluate_readiness_case(case: dict[str, Any]) -> dict[str, Any]:
    pack = _materialize_pack(case.get("pack", {}))
    try:
        report = readiness.readiness_report(pack, case["master"], case["jd"])
    finally:
        shutil.rmtree(pack, ignore_errors=True)

    expect = case["expect"]
    score = report["readiness_score"]
    suggestions = report["suggestions"]
    blob = "\n".join(suggestions).lower()

    failures: list[str] = []
    if not (expect["readiness_score_min"] <= score <= expect["readiness_score_max"]):
        failures.append(
            f"readiness_score {score} outside band "
            f"[{expect['readiness_score_min']},{expect['readiness_score_max']}]"
        )
    if "blocking" in expect and report["blocking"] != expect["blocking"]:
        failures.append(f"blocking {report['blocking']} != expected {expect['blocking']}")
    for needle in expect.get("must_include_suggestion", []):
        if needle.lower() not in blob:
            failures.append(f"must_include_suggestion {needle!r} not found in suggestions")
    for needle in expect.get("must_not_suggest", []):
        if needle.lower() in blob:
            failures.append(f"must_not_suggest {needle!r} unexpectedly found in suggestions")

    return {
        "id": case["id"],
        "kind": "readiness",
        "source": case.get("_source", case["id"]),
        "passed": not failures,
        "failures": failures,
        "score": score,
    }
