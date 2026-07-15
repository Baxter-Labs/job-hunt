"""Deterministic job-description red-flag scanner.

Curated, documented pattern set that flags language commonly associated with
poor roles: vague compensation, culture-cliche language, unrealistic workload,
questionable benefits, unpaid hiring assessments, and impossible seniority
ranges. Every rule is deterministic and word-boundary-correct so it does not
false-positive on substrings (modelled on tailor/ats.py's matching rigor).

This is a READ/GENERATE-ONLY signal. It never modifies the workspace and never
touches the network. It is advisory: a flag means "read this line carefully",
not "this job is bad".

Return contract: ``scan_red_flags(jd_text)`` returns a list of dicts, each with
exactly ``{"flag", "category", "evidence", "severity"}``. Order is the fixed
detector order below (deterministic and repeatable).
"""

from __future__ import annotations

import re
from typing import Callable, Optional

# Severity vocabulary: "low" (worth noting), "medium" (ask about it),
# "high" (a genuine concern to weigh before applying).

# --- money detection: a real salary figure anywhere in the JD ---------------
# Any of: a currency symbol next to a digit ($80 / € 80 / £70,000), a "k" amount
# (80k / 80 k), a thousands-grouped number (70,000 / 70.000), or a number
# directly qualified by a currency word (70000 EUR / 120 usd).
_MONEY_RE = re.compile(
    r"[$€£]\s?\d"
    r"|\b\d{2,3}\s?k\b"
    r"|\b\d{1,3}[.,]\d{3}\b"
    r"|\b\d+\s?(?:eur|usd|gbp|euros?|dollars?|pounds?)\b",
    re.IGNORECASE,
)

_COMPETITIVE_RE = re.compile(
    r"competitive\s+(?:salary|salaries|compensation|pay|package|remuneration|wage)",
    re.IGNORECASE,
)

# --- on-call detection ------------------------------------------------------
_ONCALL_RE = re.compile(r"\bon[-\s]?call\b", re.IGNORECASE)
_ONCALL_COMP_RE = re.compile(
    r"on[-\s]?call\s+(?:pay|stipend|compensation|allowance|bonus|premium)"
    r"|(?:paid|compensat\w*|extra\s+pay|additional\s+pay)\b[^.]{0,30}?on[-\s]?call"
    r"|on[-\s]?call[^.]{0,30}?(?:is\s+)?(?:paid|compensat\w*)",
    re.IGNORECASE,
)

# --- unpaid assessment ------------------------------------------------------
_ASSESS = r"(?:take[-\s]?home\s+)?(?:assignment|assessment|task|test|project|trial|challenge|case\s+study|exercise)"
_UNPAID_RE = re.compile(
    rf"unpaid\s+{_ASSESS}|{_ASSESS}\s+(?:is\s+|will\s+be\s+)?unpaid",
    re.IGNORECASE,
)

# --- equity-only ------------------------------------------------------------
_EQUITY_ONLY_RE = re.compile(
    r"equity[-\s]?only|only\s+equity|sweat\s+equity|equity\s+in\s+lieu"
    r"|compensation\s+is\s+(?:mainly\s+|primarily\s+)?equity",
    re.IGNORECASE,
)

# --- simple single-shot phrase patterns -------------------------------------
_FAST_PACED_RE = re.compile(r"\bfast[-\s]?paced\b", re.IGNORECASE)
_MANY_HATS_RE = re.compile(
    r"\bwear(?:s|ing)?\s+(?:many|multiple|several|lots\s+of|a\s+lot\s+of)\s+hats\b",
    re.IGNORECASE,
)
_ROCKSTAR_RE = re.compile(r"\b(?:rock\s?stars?|ninjas?|gurus?|superstars?|wizards?)\b", re.IGNORECASE)
_UNLIMITED_PTO_RE = re.compile(
    r"\bunlimited\s+(?:pto|vacation|holidays?|time[-\s]?off|leave|paid\s+time\s+off)\b",
    re.IGNORECASE,
)
_FAMILY_RE = re.compile(
    r"\bwe(?:'re|\s+are)?\s+(?:like\s+)?(?:a|one\s+big)\s+family\b"
    r"|\blike\s+(?:a\s+)?family\b"
    r"|\bwork\s+family\b"
    r"|\bpart\s+of\s+(?:the|our)\s+family\b",
    re.IGNORECASE,
)
_WORK_HARD_PLAY_HARD_RE = re.compile(r"\bwork\s+hard[,\s]+(?:and\s+)?play\s+hard\b", re.IGNORECASE)

# --- seniority --------------------------------------------------------------
_YEARS_RANGE_RE = re.compile(
    r"\b(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\s*\+?\s*years?\b", re.IGNORECASE
)
_ENTRY_RE = re.compile(
    r"\b(?:junior|entry[-\s]?level|new\s+grad|graduate|intern(?:ship)?)\b", re.IGNORECASE
)
_HIGH_YEARS_RE = re.compile(r"\b(\d{1,2})\s*\+?\s*years?\b", re.IGNORECASE)

_EXPERIENCE_RANGE_SPAN = 6   # a >=6-year advertised range is implausibly wide
_ENTRY_SENIOR_YEARS = 5      # >=5 years demanded of an "entry"/"junior" role


def _finding(flag: str, category: str, severity: str, match: re.Match) -> dict:
    return {
        "flag": flag,
        "category": category,
        "evidence": match.group(0).strip(),
        "severity": severity,
    }


def _detect_vague_compensation(text: str) -> list[dict]:
    m = _COMPETITIVE_RE.search(text)
    if m and not _MONEY_RE.search(text):
        return [_finding("vague-compensation", "compensation", "medium", m)]
    return []


def _detect_oncall(text: str) -> list[dict]:
    m = _ONCALL_RE.search(text)
    if m and not _ONCALL_COMP_RE.search(text):
        return [_finding("on-call-uncompensated", "compensation", "medium", m)]
    return []


def _detect_equity_only(text: str) -> list[dict]:
    m = _EQUITY_ONLY_RE.search(text)
    return [_finding("equity-only-comp", "compensation", "high", m)] if m else []


def _detect_unpaid_assessment(text: str) -> list[dict]:
    m = _UNPAID_RE.search(text)
    return [_finding("unpaid-assessment", "hiring-process", "high", m)] if m else []


def _detect_experience_range(text: str) -> list[dict]:
    for m in _YEARS_RANGE_RE.finditer(text):
        lo, hi = int(m.group(1)), int(m.group(2))
        if hi - lo >= _EXPERIENCE_RANGE_SPAN:
            return [_finding("unrealistic-experience-range", "seniority", "low", m)]
    return []


def _detect_entry_level_senior_demand(text: str) -> list[dict]:
    entry = _ENTRY_RE.search(text)
    if not entry:
        return []
    for m in _HIGH_YEARS_RE.finditer(text):
        if int(m.group(1)) >= _ENTRY_SENIOR_YEARS:
            return [_finding("entry-level-senior-demand", "seniority", "high", m)]
    return []


def _simple(flag: str, category: str, severity: str, pattern: re.Pattern) -> Callable[[str], list[dict]]:
    def detect(text: str) -> list[dict]:
        m = pattern.search(text)
        return [_finding(flag, category, severity, m)] if m else []
    return detect


# Fixed, deterministic detector order. Compensation first (highest signal),
# then culture/workload, benefits, hiring-process, seniority.
_DETECTORS: tuple[Callable[[str], list[dict]], ...] = (
    _detect_vague_compensation,
    _detect_equity_only,
    _detect_oncall,
    _simple("fast-paced", "workload", "low", _FAST_PACED_RE),
    _simple("wear-many-hats", "workload", "medium", _MANY_HATS_RE),
    _simple("rockstar-language", "culture", "low", _ROCKSTAR_RE),
    _simple("family-culture", "culture", "medium", _FAMILY_RE),
    _simple("work-hard-play-hard", "culture", "medium", _WORK_HARD_PLAY_HARD_RE),
    _simple("unlimited-pto", "benefits", "low", _UNLIMITED_PTO_RE),
    _detect_unpaid_assessment,
    _detect_experience_range,
    _detect_entry_level_senior_demand,
)


def scan_red_flags(jd_text: Optional[str]) -> list[dict]:
    """Scan a job description for advisory red flags.

    Returns a list of ``{"flag", "category", "evidence", "severity"}`` dicts in
    a fixed detector order. Deterministic and repeatable; a clean JD returns
    ``[]``. Never mutates anything and never touches the network.
    """
    text = jd_text or ""
    findings: list[dict] = []
    for detector in _DETECTORS:
        findings.extend(detector(text))
    return findings
