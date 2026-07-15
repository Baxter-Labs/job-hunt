"""Golden-case loader + schema validator for the Job Hunt quality-evals harness.

Golden cases are JSON *data*. Each case pins the intended behavior of a
deterministic scorer as bands + keyword membership. This module only loads and
validates them (stdlib only); the actual scoring lives in tailor.ats /
search.rank and is exercised by ats_eval.py / rank_eval.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
ATS_DIR = GOLDEN_DIR / "ats"
RANK_DIR = GOLDEN_DIR / "rank"
FIT_DIR = GOLDEN_DIR / "fit"
READINESS_DIR = GOLDEN_DIR / "readiness"

ATS_EXPECT_KEYS = frozenset({"score_min", "score_max", "must_match", "must_miss"})
RANK_EXPECT_KEYS = frozenset({"order"})
FIT_EXPECT_KEYS = frozenset({"fit_score_min", "fit_score_max"})
READINESS_EXPECT_KEYS = frozenset({"readiness_score_min", "readiness_score_max"})


class CaseError(Exception):
    """Raised when a golden case is malformed. Fails loudly and names the file."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CaseError(f"{path.name}: invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise CaseError(f"{path.name}: top-level value must be a JSON object")
    return data


def _require(cond: bool, source: str, message: str) -> None:
    if not cond:
        raise CaseError(f"{source}: {message}")


def _validate_common(case: dict[str, Any], source: str) -> None:
    _require(isinstance(case.get("id"), str) and case["id"].strip() != "",
             source, "missing non-empty string 'id'")
    _require(case.get("synthetic") is True,
             source, "'synthetic' must be literally true (synthetic data only)")


def validate_ats_case(case: dict[str, Any], source: str) -> None:
    _validate_common(case, source)
    _require(isinstance(case.get("jd"), str) and case["jd"].strip() != "",
             source, "missing non-empty string 'jd'")
    has_text = isinstance(case.get("cv_text"), str)
    has_tailored = isinstance(case.get("tailored_cv"), dict)
    _require(has_text ^ has_tailored,
             source, "provide exactly one of 'cv_text' (string) or 'tailored_cv' (object)")
    expect = case.get("expect")
    _require(isinstance(expect, dict), source, "missing 'expect' object")
    missing = ATS_EXPECT_KEYS - set(expect)
    _require(not missing, source, f"expect missing key(s): {sorted(missing)}")
    for k in ("score_min", "score_max"):
        _require(isinstance(expect[k], int), source, f"expect.{k} must be an int")
    _require(expect["score_min"] <= expect["score_max"],
             source, "expect.score_min must be <= expect.score_max")
    for k in ("must_match", "must_miss"):
        _require(isinstance(expect[k], list)
                 and all(isinstance(x, str) for x in expect[k]),
                 source, f"expect.{k} must be a list of strings")
    mna = expect.get("must_not_appear", [])
    _require(isinstance(mna, list) and all(isinstance(x, str) for x in mna),
             source, "expect.must_not_appear must be a list of strings")


def validate_rank_case(case: dict[str, Any], source: str) -> None:
    _validate_common(case, source)
    listings = case.get("listings")
    _require(isinstance(listings, list) and all(isinstance(x, dict) for x in listings),
             source, "'listings' must be a list of objects")
    _require(all(isinstance(x.get("id"), str) for x in listings),
             source, "every listing needs a string 'id' (used for order assertions)")
    expect = case.get("expect")
    _require(isinstance(expect, dict), source, "missing 'expect' object")
    missing = RANK_EXPECT_KEYS - set(expect)
    _require(not missing, source, f"expect missing key(s): {sorted(missing)}")
    _require(isinstance(expect["order"], list)
             and all(isinstance(x, str) for x in expect["order"]),
             source, "expect.order must be a list of listing-id strings")
    if "today" in case:
        _require(isinstance(case["today"], str), source, "'today' must be an ISO date string")


def validate_fit_case(case: dict[str, Any], source: str) -> None:
    _validate_common(case, source)
    _require(isinstance(case.get("jd"), str) and case["jd"].strip() != "",
             source, "missing non-empty string 'jd'")
    _require(isinstance(case.get("master"), dict),
             source, "missing 'master' object (a synthetic cv_master fragment)")
    expect = case.get("expect")
    _require(isinstance(expect, dict), source, "missing 'expect' object")
    missing = FIT_EXPECT_KEYS - set(expect)
    _require(not missing, source, f"expect missing key(s): {sorted(missing)}")
    for k in ("fit_score_min", "fit_score_max"):
        _require(isinstance(expect[k], int), source, f"expect.{k} must be an int")
    _require(expect["fit_score_min"] <= expect["fit_score_max"],
             source, "expect.fit_score_min must be <= expect.fit_score_max")
    comps = expect.get("components", {})
    _require(isinstance(comps, dict), source, "expect.components must be an object")
    for name, bounds in comps.items():
        _require(name in ("skills", "experience", "seniority"),
                 source, f"expect.components has unknown key {name!r}")
        _require(isinstance(bounds, dict)
                 and isinstance(bounds.get("min"), int)
                 and isinstance(bounds.get("max"), int)
                 and bounds["min"] <= bounds["max"],
                 source, f"expect.components.{name} must be {{min:int,max:int}} with min<=max")
    reasons = expect.get("must_include_reason", [])
    _require(isinstance(reasons, list) and all(isinstance(x, str) for x in reasons),
             source, "expect.must_include_reason must be a list of strings")


def validate_readiness_case(case: dict[str, Any], source: str) -> None:
    _validate_common(case, source)
    _require(isinstance(case.get("jd"), str) and case["jd"].strip() != "",
             source, "missing non-empty string 'jd'")
    _require(isinstance(case.get("master"), dict),
             source, "missing 'master' object (a synthetic cv_master fragment)")
    pack = case.get("pack", {})
    _require(isinstance(pack, dict), source, "'pack' must be an object when present")
    if "ats_report" in pack:
        _require(isinstance(pack["ats_report"], dict), source, "pack.ats_report must be an object")
    if "tailored_cv" in pack:
        _require(isinstance(pack["tailored_cv"], dict), source, "pack.tailored_cv must be an object")
    if "files" in pack:
        _require(isinstance(pack["files"], list) and all(isinstance(x, str) for x in pack["files"]),
                 source, "pack.files must be a list of strings")
    expect = case.get("expect")
    _require(isinstance(expect, dict), source, "missing 'expect' object")
    missing = READINESS_EXPECT_KEYS - set(expect)
    _require(not missing, source, f"expect missing key(s): {sorted(missing)}")
    for k in ("readiness_score_min", "readiness_score_max"):
        _require(isinstance(expect[k], int), source, f"expect.{k} must be an int")
    _require(expect["readiness_score_min"] <= expect["readiness_score_max"],
             source, "expect.readiness_score_min must be <= expect.readiness_score_max")
    if "blocking" in expect:
        _require(isinstance(expect["blocking"], bool), source, "expect.blocking must be a bool")
    reasons = expect.get("must_include_suggestion", [])
    _require(isinstance(reasons, list) and all(isinstance(x, str) for x in reasons),
             source, "expect.must_include_suggestion must be a list of strings")
    absent = expect.get("must_not_suggest", [])
    _require(isinstance(absent, list) and all(isinstance(x, str) for x in absent),
             source, "expect.must_not_suggest must be a list of strings")


def iter_ats_files() -> list[Path]:
    return sorted(ATS_DIR.glob("*.json"))


def iter_rank_files() -> list[Path]:
    return sorted(RANK_DIR.glob("*.json"))


def load_ats_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in iter_ats_files():
        case = load_json(path)
        validate_ats_case(case, path.name)
        case["_source"] = path.name
        cases.append(case)
    return cases


def load_rank_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in iter_rank_files():
        case = load_json(path)
        validate_rank_case(case, path.name)
        case["_source"] = path.name
        cases.append(case)
    return cases


def iter_fit_files() -> list[Path]:
    return sorted(FIT_DIR.glob("*.json"))


def load_fit_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in iter_fit_files():
        case = load_json(path)
        validate_fit_case(case, path.name)
        case["_source"] = path.name
        cases.append(case)
    return cases


def iter_readiness_files() -> list[Path]:
    return sorted(READINESS_DIR.glob("*.json"))


def load_readiness_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in iter_readiness_files():
        case = load_json(path)
        validate_readiness_case(case, path.name)
        case["_source"] = path.name
        cases.append(case)
    return cases
