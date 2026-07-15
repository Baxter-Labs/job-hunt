"""Deterministic 0–100 fit score between a master CV and a job description.

Pure and offline. Blends three sub-scores with fixed, documented weights:

    fit_score = round(0.5*skills + 0.3*experience + 0.2*seniority)

  * skills     — ats keyword coverage of the JD by the flattened master text.
  * experience — the SAME JD keywords matched against only the master's role
                 titles + summary (the "right kind of role" signal).
  * seniority  — JD seniority cue vs the master's latest title (or rough years),
                 scored by distance on an ordered ladder; ambiguous → neutral 70.

Keyword extraction/matching is delegated ENTIRELY to tailor.ats — this module
adds no second tokenizer. Nothing here ever invents facts: missing JD keywords
are reported as honest gaps, never added to the CV. A low fit is a signal to
focus elsewhere or /job-upskill, never a licence to fabricate.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Optional

# Make sibling `tailor` importable whether run as a module or imported by evals.
_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from tailor import ats  # noqa: E402  (reuse — never reimplement keyword logic)

WEIGHTS: dict[str, float] = {"skills": 0.5, "experience": 0.3, "seniority": 0.2}

# Ordered seniority ladder; index == seniority level.
LADDER: tuple[str, ...] = (
    "intern", "junior", "mid", "senior", "staff", "lead", "principal", "head", "director",
)

# Cue synonyms per rung, longest phrases first so multi-word cues win. Matched
# against ats.normalize(text) on word boundaries.
_CUES: tuple[tuple[int, tuple[str, ...]], ...] = (
    (0, ("working student", "internship", "intern")),
    (1, ("entry level", "entry-level", "new grad", "junior", "graduate", "associate", "jr")),
    (2, ("mid level", "mid-level", "intermediate", "mid")),
    (3, ("senior", "sr")),
    (4, ("staff",)),
    (5, ("team lead", "tech lead", "lead")),
    (6, ("principal",)),
    (7, ("head of", "head")),
    (8, ("vice president", "director", "vp")),
)

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def _cue_indices(text: str) -> list[int]:
    """All ladder indices whose cue appears in `text` (word-boundary match)."""
    norm = ats.normalize(text or "")
    hits: list[int] = []
    for idx, phrases in _CUES:
        for phrase in phrases:
            pat = rf"(?<![a-z0-9]){re.escape(ats.normalize(phrase))}(?![a-z0-9])"
            if re.search(pat, norm):
                hits.append(idx)
                break
    return hits


def _jd_seniority(jd_text: str) -> Optional[int]:
    hits = _cue_indices(jd_text)
    return max(hits) if hits else None


def _rough_years(experience: list[dict[str, Any]]) -> Optional[int]:
    years: set[int] = set()
    for e in experience:
        if isinstance(e, dict):
            years.update(int(y) for y in _YEAR_RE.findall(str(e.get("dates", ""))))
    if len(years) < 2:
        return None
    return max(years) - min(years)


def _years_to_index(years: int) -> int:
    if years < 2:
        return 1
    if years < 5:
        return 2
    if years < 9:
        return 3
    return 5


def _master_seniority(master_cv: dict[str, Any]) -> Optional[int]:
    experience = [e for e in (master_cv.get("experience") or []) if isinstance(e, dict)]
    if experience:
        title_hits = _cue_indices(str(experience[0].get("title", "")))
        if title_hits:
            return max(title_hits)
    years = _rough_years(experience)
    if years is not None:
        return _years_to_index(years)
    return None


def _seniority_component(master_cv: dict[str, Any], jd_text: str) -> tuple[int, str]:
    jd_idx = _jd_seniority(jd_text)
    master_idx = _master_seniority(master_cv)
    if jd_idx is None or master_idx is None:
        return 70, ("Seniority: no clear cue in the JD or your latest title — "
                    "treated as neutral.")
    distance = abs(jd_idx - master_idx)
    score = max(20, 100 - 20 * distance)
    jl, ml = LADDER[jd_idx], LADDER[master_idx]
    if distance == 0:
        reason = f"Seniority: JD asks {jl}, your latest title is {ml} — aligned."
    elif jd_idx > master_idx:
        reason = f"Seniority: JD asks {jl}, your latest title is {ml} — {distance} level(s) up."
    else:
        reason = (f"Seniority: JD asks {jl}, your latest title is {ml} — "
                  f"you're {distance} level(s) above the ask.")
    return score, reason


def _master_text(master_cv: dict[str, Any]) -> str:
    parts: list[str] = [str(master_cv.get("summary", "") or "")]
    for s in master_cv.get("skills") or []:
        if isinstance(s, dict) and isinstance(s.get("name"), str):
            parts.append(s["name"])
    for e in master_cv.get("experience") or []:
        if isinstance(e, dict):
            parts.append(str(e.get("title", "") or ""))
            parts.extend(str(b) for b in (e.get("bullets") or []))
    return "\n".join(p for p in parts if p)


def _role_text(master_cv: dict[str, Any]) -> str:
    parts = [str(e.get("title", "") or "")
             for e in (master_cv.get("experience") or []) if isinstance(e, dict)]
    parts.append(str(master_cv.get("summary", "") or ""))
    return "\n".join(p for p in parts if p)


def fit_report(master_cv: dict[str, Any], jd_text: str) -> dict[str, Any]:
    """Deterministic 0–100 fit report. See module docstring for the exact algorithm."""
    keywords = ats.extract_keywords(jd_text, max_keywords=40)
    total = len(keywords)

    matched, missing = ats.match_keywords(_master_text(master_cv), keywords)
    skills = ats.ats_score(len(matched), total)

    matched_role, _ = ats.match_keywords(_role_text(master_cv), keywords)
    experience = ats.ats_score(len(matched_role), total)

    seniority, seniority_reason = _seniority_component(master_cv, jd_text)

    components = {"skills": skills, "experience": experience, "seniority": seniority}
    fit_score = round(sum(WEIGHTS[k] * components[k] for k in WEIGHTS))

    reasons = [f"Skills match: {len(matched)}/{total} JD keywords covered."]
    if missing:
        reasons.append("Top skill gaps: " + ", ".join(missing[:5]) + ".")
    reasons.append(
        f"Experience relevance: {experience}/100 (your role titles + summary vs the JD)."
    )
    reasons.append(seniority_reason)

    return {"fit_score": fit_score, "components": components, "reasons": reasons}
