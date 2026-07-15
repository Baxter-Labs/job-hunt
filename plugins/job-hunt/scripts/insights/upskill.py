"""Aggregate the *missing* ATS keywords across the user's tracked packs.

Deterministic, workspace-read-only. Reuses the pack's already-computed
``ats_report.json`` (via ``apply.preapply.load_ats_report``) rather than
re-scoring, so the gaps shown here are exactly the gaps ``/job-tailor`` and
``/job-apply`` reported. The "what to learn, with resources and a plan"
narrative is Claude's job in the skill; this module only ranks the factual
gaps.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterable, Optional

# Make sibling packages importable when imported via `python -m insights.*`.
_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from engine import workspace  # noqa: E402
from apply.preapply import load_ats_report  # noqa: E402


def _role_label(report: dict[str, Any]) -> str:
    company = str(report.get("company", "") or "").strip()
    role = str(report.get("role", "") or "").strip()
    if company and role:
        return f"{company} — {role}"
    return company or role or ""


def aggregate_gaps(pack_dirs: Iterable[Any]) -> list[dict]:
    """Rank missing keywords across the given pack directories.

    For each pack that has a readable ``ats_report.json``, tally its
    ``missing_keywords``. Returns ``[{"keyword", "count", "roles"}, ...]`` sorted
    by count (desc) then keyword (asc). ``roles`` is the ordered, de-duplicated
    list of ``"<company> — <role>"`` labels that were missing that keyword.
    """
    counts: dict[str, int] = {}
    roles: dict[str, list[str]] = {}
    for pack_dir in pack_dirs:
        report = load_ats_report(Path(pack_dir))
        if not report:
            continue
        label = _role_label(report)
        for kw in report.get("missing_keywords", []) or []:
            if not isinstance(kw, str):
                continue
            counts[kw] = counts.get(kw, 0) + 1
            bucket = roles.setdefault(kw, [])
            if label and label not in bucket:
                bucket.append(label)
    ranked = sorted(counts, key=lambda k: (-counts[k], k))
    return [{"keyword": k, "count": counts[k], "roles": roles.get(k, [])} for k in ranked]


def iter_pack_dirs(output_root: Optional[Path] = None) -> list[Path]:
    """Immediate subdirectories of the output root that contain an
    ``ats_report.json``, sorted by name. Defaults to the workspace output dir.
    Returns ``[]`` when the root does not exist."""
    root = Path(output_root) if output_root is not None else workspace.output_dir()
    if not root.is_dir():
        return []
    return sorted(
        (d for d in root.iterdir() if d.is_dir() and (d / "ats_report.json").exists()),
        key=lambda p: p.name,
    )
