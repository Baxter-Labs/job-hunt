"""Deterministic outcome analytics over the application tracker.

Pure and offline. `funnel_report` computes the applied -> response -> interview
-> offer funnel (with terminal-negative rejected/ghosted counts), overall and
sliced by source, work-auth status, and ATS band. The ATS band comes from an
injected `pack_lookup(company, role) -> match_score|None`, so the core function
never touches the filesystem; `workspace_pack_lookup` builds the real closure
over the workspace `output/` packs for the CLI. No MCP, no network, no writes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Optional

# Make sibling packages importable when imported via `python -m insights.*`.
_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from apply import preapply  # noqa: E402
from search.listing import pack_slug  # noqa: E402

# Furthest funnel stage a status represents. Legacy "discovered" maps to 0 (not
# applied); terminal negatives are handled separately (they count as applied but
# never as a positive response). Mirrors search.tracker's vocabulary, kept local
# so this stays a pure function over generic row dicts.
_STAGE_RANK: dict[str, int] = {
    "discovered": 0,
    "not_applied": 0,
    "pack_generated": 1,
    "applied": 2,
    "response": 3,
    "interview": 4,
    "offer": 5,
}
_TERMINAL_NEGATIVE: frozenset[str] = frozenset({"rejected", "ghosted"})

PackLookup = Callable[[str, str], Optional[int]]


def _norm(status: Any) -> str:
    return (status or "").strip().lower() if isinstance(status, str) else ""


def _rank(status: str) -> int:
    s = _norm(status)
    if s in _TERMINAL_NEGATIVE:
        return 2  # they applied, but no positive progression
    return _STAGE_RANK.get(s, 0)


def _is_applied(status: str) -> bool:
    s = _norm(status)
    return s in _TERMINAL_NEGATIVE or _STAGE_RANK.get(s, 0) >= 2


def _blank_funnel() -> dict[str, Any]:
    return {"total": 0, "applied": 0, "responses": 0, "interviews": 0,
            "offers": 0, "rejected": 0, "ghosted": 0}


def _accumulate(rows: list[dict]) -> dict[str, Any]:
    f = _blank_funnel()
    for row in rows:
        s = _norm(row.get("status"))
        f["total"] += 1
        if _is_applied(s):
            f["applied"] += 1
        r = _rank(s)
        if r >= 3:
            f["responses"] += 1
        if r >= 4:
            f["interviews"] += 1
        if r >= 5:
            f["offers"] += 1
        if s == "rejected":
            f["rejected"] += 1
        if s == "ghosted":
            f["ghosted"] += 1
    return f


def _with_rates(f: dict[str, Any]) -> dict[str, Any]:
    applied = f["applied"]

    def rate(n: int) -> Any:
        return round(n / applied, 3) if applied else 0  # divide-by-zero -> 0

    return {
        **f,
        "response_rate": rate(f["responses"]),
        "interview_rate": rate(f["interviews"]),
        "offer_rate": rate(f["offers"]),
    }


def _band(score: Optional[int]) -> str:
    if score is None:
        return "unknown"
    if score >= 70:
        return "70+"
    if score >= 50:
        return "50-69"
    return "<50"


def _breakdown(rows: list[dict], key_of: Callable[[dict], str]) -> dict[str, Any]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(key_of(row) or "unknown", []).append(row)
    return {k: _with_rates(_accumulate(v)) for k, v in sorted(groups.items())}


def _pct(rate: Any) -> int:
    return round(float(rate) * 100)


def _takeaways(by_source: dict, by_band: dict, min_n: int) -> list[str]:
    out: list[str] = []

    # ATS band: 70+ vs <50 response rate, only when both bands have enough data.
    # The directive must follow whichever band actually converts better — never
    # recommend chasing a higher ATS score when the data shows the opposite.
    hi = by_band.get("70+")
    lo = by_band.get("<50")
    if hi and lo and hi["applied"] >= min_n and lo["applied"] >= min_n:
        hi_rate, lo_rate = hi["response_rate"], lo["response_rate"]
        msg = (
            f"70+ ATS band: {_pct(hi_rate)}% response vs "
            f"{_pct(lo_rate)}% for <50 applications."
        )
        if hi_rate > lo_rate:
            msg += " Prioritise higher-scoring tailors."
        elif lo_rate > hi_rate:
            msg += (
                " Higher ATS isn't converting better here — keep tailoring "
                "honestly and watch the trend as your sample grows."
            )
        else:
            msg += " They're converting about the same so far."
        out.append(msg)

    # Best-converting source, only among sources with enough applications, and
    # only when the top source strictly beats the runner-up (never on a tie).
    eligible = {k: v for k, v in by_source.items() if v["applied"] >= min_n}
    if len(eligible) >= 2:
        ranked = sorted(eligible.items(),
                         key=lambda kv: (kv[1]["response_rate"], kv[1]["applied"]),
                         reverse=True)
        (name, f), (_, runner_up) = ranked[0], ranked[1]
        if f["response_rate"] > runner_up["response_rate"]:
            out.append(
                f"{name}: highest response rate at {_pct(f['response_rate'])}% "
                f"across {f['applied']} applications — send more there."
            )

    return out


def funnel_report(
    rows: list[dict],
    pack_lookup: Optional[PackLookup] = None,
    *,
    min_takeaway_n: int = 3,
) -> dict[str, Any]:
    """Compute the outcome funnel over tracker rows.

    Deterministic: same rows + same pack_lookup -> identical output. `pack_lookup`
    maps (company, role) -> ATS match_score or None; when None, every row's band
    is "unknown". Rates are responses/interviews/offers over applied, rounded to
    3 dp, and exactly 0 when applied == 0. Takeaways are only emitted when the
    compared groups each have at least `min_takeaway_n` applications."""
    rows = list(rows or [])

    def band_of(row: dict) -> str:
        if pack_lookup is None:
            return "unknown"
        return _band(pack_lookup(row.get("company", ""), row.get("role", "")))

    by_source = _breakdown(rows, lambda r: (r.get("source") or "unknown").strip() or "unknown")
    by_work_auth = _breakdown(rows, lambda r: (r.get("work_auth_status") or "n/a").strip() or "n/a")
    by_ats_band = _breakdown(rows, band_of)

    return {
        "min_takeaway_n": min_takeaway_n,
        "overall": _with_rates(_accumulate(rows)),
        "by_source": by_source,
        "by_work_auth": by_work_auth,
        "by_ats_band": by_ats_band,
        "takeaways": _takeaways(by_source, by_ats_band, min_takeaway_n),
    }


def workspace_pack_lookup(output_root: Optional[Path] = None) -> PackLookup:
    """Build a (company, role) -> match_score|None lookup over the workspace packs.

    Reuses the same pack-dir convention as the rest of the engine (pack_slug +
    resolve_pack_dir + load_ats_report). Reads only; returns None for any role
    without a readable ats_report.json."""

    def lookup(company: str, role: str) -> Optional[int]:
        pack_dir = preapply.resolve_pack_dir(pack_slug(company, role), output_root=output_root)
        report = preapply.load_ats_report(pack_dir)
        if not report:
            return None
        score = report.get("match_score")
        return score if isinstance(score, (int, float)) and not isinstance(score, bool) else None

    return lookup
