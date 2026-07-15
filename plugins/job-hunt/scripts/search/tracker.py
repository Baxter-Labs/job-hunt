"""Append or update entries in the application tracker CSV.

Ported from scripts/update_tracker.py (Resumes repo). CSV read/write and
is_duplicate logic are ported verbatim; only the path resolution (now the
workspace tracker.csv), field names (generic, de-personalised), and the
public entry points (upsert/summarize replace the argparse CLI) changed.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from engine import workspace  # Phase-1 workspace path resolution


def _resolve(path: Optional[Path]) -> Path:
    return Path(path) if path is not None else workspace.tracker_path()


FIELDNAMES = [
    "discovered_date",
    "date_applied",
    "company",
    "role",
    "url",
    "status",
    "work_auth_status",
    "job_id",
    "source",
    "notes",
]


def load_tracker(path: Optional[Path] = None) -> list[dict]:
    tracker = _resolve(path)
    if not tracker.exists():
        return []
    with tracker.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_tracker(rows: list[dict], path: Optional[Path] = None) -> Path:
    tracker = _resolve(path)
    tracker.parent.mkdir(parents=True, exist_ok=True)
    with tracker.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})
    return tracker


def is_duplicate(rows: list[dict], company: str, role: str, job_id: str = "") -> bool:
    comp_lower = company.lower().strip()
    role_lower = role.lower().strip()
    for row in rows:
        if row.get("company", "").lower().strip() == comp_lower and row.get("role", "").lower().strip() == role_lower:
            return True
        if job_id and row.get("job_id", "") == job_id:
            return True
    return False


def upsert(
    *,
    company: str,
    role: str,
    url: str = "",
    status: str = "discovered",
    work_auth_status: str = "",
    job_id: str = "",
    source: str = "",
    notes: str = "",
    path: Optional[Path] = None,
) -> dict:
    """Append a new tracker row, or update the matching one in place.

    Match key: same company+role (case-insensitive) OR same job_id. On update,
    only non-empty incoming fields overwrite. Returns {"action": ...}."""
    rows = load_tracker(path)
    today = datetime.now().strftime("%Y-%m-%d")

    if is_duplicate(rows, company, role, job_id):
        for row in rows:
            same = (row.get("company", "").lower().strip() == company.lower().strip()
                    and row.get("role", "").lower().strip() == role.lower().strip())
            same_id = bool(job_id) and row.get("job_id", "") == job_id
            if same or same_id:
                if status:
                    row["status"] = status
                    if status == "applied" and not row.get("date_applied"):
                        row["date_applied"] = today
                if url:
                    row["url"] = url
                if job_id:
                    row["job_id"] = job_id
                if work_auth_status:
                    row["work_auth_status"] = work_auth_status
                if source:
                    row["source"] = source
                if notes:
                    row["notes"] = notes
                break
        save_tracker(rows, path)
        return {"action": "updated", "company": company, "role": role}

    rows.append({
        "discovered_date": today,
        "date_applied": today if status == "applied" else "",
        "company": company,
        "role": role,
        "url": url,
        "status": status,
        "work_auth_status": work_auth_status,
        "job_id": job_id,
        "source": source,
        "notes": notes,
    })
    save_tracker(rows, path)
    return {"action": "added", "company": company, "role": role}


def summarize(rows: list[dict]) -> dict:
    """Counts by status and by work-auth status (the /job-search status view)."""
    by_status: dict[str, int] = {}
    by_work_auth: dict[str, int] = {}
    for row in rows:
        s = (row.get("status") or "unknown").strip() or "unknown"
        w = (row.get("work_auth_status") or "n/a").strip() or "n/a"
        by_status[s] = by_status.get(s, 0) + 1
        by_work_auth[w] = by_work_auth.get(w, 0) + 1
    return {"total": len(rows), "by_status": by_status, "by_work_auth": by_work_auth}
