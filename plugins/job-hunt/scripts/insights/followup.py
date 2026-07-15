"""Assemble one application's context for a follow-up email DRAFT.

Deterministic, offline, workspace-read-only. This module DOES NOT and MUST NOT
send anything — it only gathers the facts (tracker row + pack ATS score) that
Claude uses in the skill to draft a follow-up email the user then reviews and
sends themselves. No network, no mail, no side effects.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

# Make sibling packages importable when imported via `python -m insights.*`.
_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from search import tracker as tracker_mod  # noqa: E402
from search.listing import pack_slug  # noqa: E402
from apply import preapply  # noqa: E402


def _find_row(rows: list[dict], company: str, role: str) -> Optional[dict]:
    comp = company.lower().strip()
    rol = role.lower().strip()
    for row in rows:
        if (row.get("company", "").lower().strip() == comp
                and row.get("role", "").lower().strip() == rol):
            return row
    return None


def application_context(
    company: str,
    role: str,
    *,
    tracker_rows: Optional[list[dict]] = None,
    output_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Gather the follow-up context for one (company, role).

    Returns ``{"company", "role", "status", "date_applied", "url", "source",
    "has_pack", "ats_score"}``. Tracker fields default to ``""`` when there is no
    matching row; ``ats_score`` is the pack's ``match_score`` or ``None``. Reads
    only — never sends, never writes.
    """
    rows = tracker_rows if tracker_rows is not None else tracker_mod.load_tracker()
    row = _find_row(rows, company, role) or {}

    pack_dir = preapply.resolve_pack_dir(pack_slug(company, role), output_root=output_root)
    report = preapply.load_ats_report(pack_dir)

    return {
        "company": company,
        "role": role,
        "status": row.get("status", "") or "",
        "date_applied": row.get("date_applied", "") or "",
        "url": row.get("url", "") or "",
        "source": row.get("source", "") or "",
        "has_pack": report is not None,
        "ats_score": report.get("match_score") if report else None,
    }
