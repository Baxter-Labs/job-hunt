"""Deterministic 0–100 application READINESS score for one tailored pack.

Pure and offline. Answers "is this application ready to send, and how do I make
it stronger — honestly?" before /job-apply. Combines four documented factors:

    readiness_score = round(0.35*ats + 0.25*fit + 0.25*completeness + 0.15*redflags)

  * ats          (0.35) — the pack's ats_report.json match_score (headline
                          keyword coverage; the user's main lever).
  * fit          (0.25) — scoring.fit.fit_report(master, jd).fit_score.
  * completeness (0.25) — cover letter present + contact name/email present in
                          tailored_cv.json + CV rendered (each 1/3 of 100).
  * redflags     (0.15) — advisory JD red flags (insights.redflags); severity
                          lowers the factor. Weighted LIGHTLY and labelled as
                          job-side context — a red flag is about the JOB, never
                          the user's fault.

FABRICATION IS A HARD GATE. If the pack's tailored_cv.json has
fabrication_check.passed == False, readiness is BLOCKING: readiness_score is
capped at 0 and a fail factor "Fabrication check must pass" leads the checklist.
We never present a fabricated pack as ready.

Improvement suggestions are HONEST and split by provenance:
  * has-but-unsurfaced — a JD keyword the user GENUINELY has (in the master
    skills/experience) but that isn't in the tailored CV  ->  "re-tailor to
    surface X (you already have it)". Safe: it is already true.
  * genuinely-lacks — a JD keyword absent from the master  ->  routed to
    /job-upskill as a learn-gap. NEVER "add it": that would be fabrication.
  * missing pack pieces — no cover letter / incomplete contact / unrendered CV
    ->  a concrete, honest fix.

This module reuses apply.preapply (pack access), scoring.fit, insights.redflags,
and tailor.ats — it adds no second tokenizer, no second pack resolver, and never
writes during scoring (the CLI writes readiness.json separately). Offline: no
MCP, no browser, no network, no wall-clock dependence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

# Make sibling packages importable whether run as a module or imported by evals.
_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from apply import preapply          # noqa: E402  (pack access — never reimplement)
from insights import redflags       # noqa: E402  (advisory JD flags)
from scoring import fit             # noqa: E402  (Phase C fit score)
from tailor import ats              # noqa: E402  (keyword matching — never reimplement)

WEIGHTS: dict[str, float] = {"ats": 0.35, "fit": 0.25, "completeness": 0.25, "redflags": 0.15}

# Severity -> penalty points subtracted from the (advisory) red-flag sub-score.
_FLAG_PENALTY: dict[str, int] = {"high": 25, "medium": 10, "low": 5}

_SUGGESTION_LIMIT = 5


def _band(score: int, *, ok: int = 70, warn: int = 50) -> str:
    if score >= ok:
        return "pass"
    if score >= warn:
        return "warn"
    return "fail"


def load_tailored_cv(pack_dir: Path) -> Optional[dict[str, Any]]:
    """Return the parsed tailored_cv.json, or None when absent/unreadable."""
    path = Path(pack_dir) / "tailored_cv.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _master_keyword_text(master_cv: dict[str, Any]) -> str:
    """Flatten summary + skill names + experience titles/bullets — the honest
    'what the user genuinely has' blob (same shape fit.py uses for skills)."""
    parts: list[str] = [str(master_cv.get("summary", "") or "")]
    for s in master_cv.get("skills") or []:
        if isinstance(s, dict) and isinstance(s.get("name"), str):
            parts.append(s["name"])
    for e in master_cv.get("experience") or []:
        if isinstance(e, dict):
            parts.append(str(e.get("title", "") or ""))
            parts.extend(str(b) for b in (e.get("bullets") or []))
    return "\n".join(p for p in parts if p)


def _contact_complete(tailored: Optional[dict[str, Any]]) -> bool:
    contact = (tailored or {}).get("contact") or {}
    name, email = contact.get("name"), contact.get("email")
    return (isinstance(name, str) and name.strip() != ""
            and isinstance(email, str) and email.strip() != "")


def _fabrication_factor(tailored: Optional[dict[str, Any]]) -> tuple[dict[str, str], bool]:
    """Return (factor, blocking). Hard gate: fabrication_check.passed is False."""
    if tailored is None:
        return ({"name": "Fabrication check", "status": "warn",
                 "detail": "No tailored_cv.json in the pack to verify — run /job-tailor first."},
                False)
    fab = tailored.get("fabrication_check") or {}
    if fab.get("passed") is False:
        return ({"name": "Fabrication check must pass", "status": "fail",
                 "detail": ("The tailored CV contains facts not in your master CV. This is a "
                            "hard gate — not ready to apply. Re-run /job-tailor.")},
                True)
    return ({"name": "Fabrication check", "status": "pass",
             "detail": "No fabricated facts — the tailored CV stays within your master."},
            False)


def _ats_factor(pack_dir: Path) -> tuple[int, dict[str, str]]:
    report = preapply.load_ats_report(pack_dir)
    if not report or not isinstance(report.get("match_score"), int):
        return 0, {"name": "ATS match", "status": "fail",
                   "detail": "No ats_report.json / match_score in the pack — run /job-tailor."}
    score = int(report["match_score"])
    detail = (f"ATS keyword coverage {score}/100 "
              f"({report.get('matched_count', 0)}/{report.get('total_keywords', 0)} keywords).")
    return score, {"name": "ATS match", "status": _band(score), "detail": detail}


def _completeness_factor(
    pack_dir: Path, tailored: Optional[dict[str, Any]]
) -> tuple[int, dict[str, str], dict[str, bool]]:
    attachments = preapply.pack_attachments(pack_dir)
    checks = {
        "cv": attachments["cv"] is not None,
        "cover_letter": attachments["cover_letter"] is not None,
        "contact": _contact_complete(tailored),
    }
    present = sum(1 for v in checks.values() if v)
    score = round(present / 3 * 100)
    status = "pass" if present == 3 else ("warn" if present == 2 else "fail")
    missing = [k for k, v in checks.items() if not v]
    detail = ("All pack pieces present (CV, cover letter, contact)."
              if not missing else f"Missing: {', '.join(missing)}.")
    return score, {"name": "Completeness", "status": status, "detail": detail}, checks


def _redflag_factor(jd_text: str) -> tuple[int, dict[str, str]]:
    flags = redflags.scan_red_flags(jd_text)
    penalty = sum(_FLAG_PENALTY.get(f.get("severity", "low"), 5) for f in flags)
    score = max(0, 100 - penalty)
    if not flags:
        detail = "No advisory red flags in the JD."
    else:
        names = ", ".join(sorted({f["flag"] for f in flags}))
        detail = (f"{len(flags)} advisory JD red flag(s) — about the job, not your application: "
                  f"{names}.")
    return score, {"name": "Red flags (job-side, advisory)", "status": _band(score, ok=80, warn=50),
                   "detail": detail}


def _suggestions(
    master_cv: dict[str, Any], jd_text: str,
    tailored: Optional[dict[str, Any]], checks: dict[str, bool],
) -> list[str]:
    suggestions: list[str] = []
    keywords = ats.extract_keywords(jd_text)
    in_master, not_in_master = ats.match_keywords(_master_keyword_text(master_cv), keywords)

    # (a) has-but-unsurfaced: in the master but NOT in the tailored deliverable.
    if tailored is not None:
        surfaced, _ = ats.match_keywords(ats.cv_text_from_tailored(tailored), in_master)
        surfaced_set = set(surfaced)
        unsurfaced = [k for k in in_master if k not in surfaced_set]
        if unsurfaced:
            suggestions.append(
                f"Re-tailor to surface: {', '.join(unsurfaced[:_SUGGESTION_LIMIT])} — you "
                "already have these in your master CV but they're not in this tailored CV. "
                "Run /job-tailor."
            )

    # (b) genuinely-lacks: absent from the master -> learn-gap, NEVER 'add it'.
    if not_in_master:
        suggestions.append(
            f"Learn-gap: {', '.join(not_in_master[:_SUGGESTION_LIMIT])} — the JD asks for these "
            "but they're not in your background. Consider /job-upskill. Do not add them to the CV."
        )

    # (c) missing pack pieces -> concrete fixes.
    if not checks.get("cover_letter", False):
        suggestions.append("Add a cover letter (cover_letter.md) and re-run /job-tailor.")
    if not checks.get("contact", False):
        suggestions.append("Complete your contact name and email in cv_master.json, then re-tailor.")
    if not checks.get("cv", False):
        suggestions.append("Render the CV (re-run /job-tailor finalize).")

    return suggestions


def readiness_report(
    pack_dir: Path, master_cv: dict[str, Any], jd_text: str
) -> dict[str, Any]:
    """Deterministic 0–100 readiness report. See the module docstring for the exact
    algorithm. Pure: reads only the pack's ats_report.json / tailored_cv.json and
    never writes (the CLI writes readiness.json separately)."""
    pack_dir = Path(pack_dir)
    tailored = load_tailored_cv(pack_dir)

    fab_factor, blocking = _fabrication_factor(tailored)
    ats_sub, ats_factor = _ats_factor(pack_dir)
    fit_sub = int(fit.fit_report(master_cv, jd_text)["fit_score"])
    fit_factor = {"name": "Fit", "status": _band(fit_sub),
                  "detail": f"Fit score {fit_sub}/100 (skills, experience, seniority vs the JD)."}
    comp_sub, comp_factor, checks = _completeness_factor(pack_dir, tailored)
    rf_sub, rf_factor = _redflag_factor(jd_text)

    subscores = {"ats": ats_sub, "fit": fit_sub, "completeness": comp_sub, "redflags": rf_sub}
    readiness_score = 0 if blocking else round(sum(WEIGHTS[k] * subscores[k] for k in WEIGHTS))

    return {
        "readiness_score": readiness_score,
        "factors": [fab_factor, ats_factor, fit_factor, comp_factor, rf_factor],
        "suggestions": _suggestions(master_cv, jd_text, tailored, checks),
        "blocking": blocking,
    }


def write_readiness_report(report: dict[str, Any], pack_dir: Path) -> Path:
    """Write readiness.json into pack_dir; return the path."""
    pack_dir = Path(pack_dir)
    pack_dir.mkdir(parents=True, exist_ok=True)
    path = pack_dir / "readiness.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
