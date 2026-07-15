"""Deduplicate discovered listings against the workspace tracker and existing
output packs. Ported from scripts/job_pipeline.py's `check-duplicate` action:
a listing is a duplicate if it is already in tracker.csv (same company+role, or
same job_id) OR an application pack already exists for it on disk. Re-pathed to
the workspace; no network, no MCP.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from engine import workspace
from search.listing import pack_slug
from search import tracker as tracker_mod


def pack_dir_for(company: str, role: str, output_root: Optional[Path] = None) -> Path:
    """`output_root/<company-slug>-<role-slug>` (not created). Defaults to the
    workspace output dir; matches Phase-2 tailor.pipeline.pack_dir_for."""
    root = Path(output_root) if output_root is not None else workspace.output_dir()
    return root / pack_slug(company, role)


def is_duplicate(
    company: str,
    role: str,
    *,
    tracker_rows: list[dict],
    output_root: Optional[Path] = None,
    job_id: str = "",
) -> dict[str, Any]:
    """Ported from job_pipeline.check_duplicate. Returns the same four fields."""
    comp = company.lower().strip()
    rl = role.lower().strip()

    in_tracker = False
    for row in tracker_rows:
        if (row.get("company", "").lower().strip() == comp
                and row.get("role", "").lower().strip() == rl):
            in_tracker = True
            break
        if job_id and row.get("job_id", "") == job_id:
            in_tracker = True
            break

    existing_dir = pack_dir_for(company, role, output_root)
    in_filesystem = existing_dir.exists() and any(existing_dir.iterdir())

    return {
        "is_duplicate": bool(in_tracker or in_filesystem),
        "in_tracker": in_tracker,
        "in_filesystem": in_filesystem,
        "existing_path": str(existing_dir) if in_filesystem else None,
    }


def filter_new(
    listings: list[dict[str, Any]],
    *,
    tracker_rows: Optional[list[dict]] = None,
    output_root: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Return only listings that are not duplicates. Loads the workspace tracker
    when `tracker_rows` is None."""
    rows = tracker_rows if tracker_rows is not None else tracker_mod.load_tracker()
    kept: list[dict[str, Any]] = []
    for listing in listings:
        res = is_duplicate(
            listing.get("company", ""), listing.get("role", ""),
            tracker_rows=rows, output_root=output_root,
            job_id=listing.get("job_id", ""),
        )
        if not res["is_duplicate"]:
            kept.append(listing)
    return kept
