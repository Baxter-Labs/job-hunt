"""Job Hunt tracking dashboard (OPTIONAL — needs Flask).

Ported from the personal Resumes dashboard (dashboard/app.py). Re-pathed to the
user's workspace: reads $JOB_HUNT_HOME/tracker.csv and the flat pack layout
$JOB_HUNT_HOME/output/<company-slug>-<role-slug>/, surfacing each role's ATS
match score (read straight from ats_report.json["match_score"]) and safe pack
download links. De-personalised: no user name, no visa badge, no hardcoded region.

`create_app(home=…)` returns a Flask app closed over the workspace paths so tests
drive it with a test client and no bound port. Flask is imported at module top;
callers that lack Flask should not import this module (the /job-track text summary
path never does).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request, send_from_directory

_SCRIPTS = Path(__file__).resolve().parents[1]
import sys
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from engine import workspace  # noqa: E402
from search.listing import pack_slug  # noqa: E402
from search.tracker import FIELDNAMES  # noqa: E402

# Download allow-list: only these filenames may be served from a pack dir.
SAFE_FILES = frozenset({
    "cv.pdf", "cv.html", "tailored_cv.json", "ats_report.json",
    "change_log.md", "cover_letter.pdf", "cover_letter.md",
    "job_description.txt", "job_link.txt",
})


def _read_ats(pack_dir: Path) -> Optional[dict]:
    path = pack_dir / "ats_report.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def create_app(home: Optional[object] = None) -> Flask:
    """Build the dashboard app. `home` overrides the workspace root (tests);
    when None, the live $JOB_HUNT_HOME is used at request time."""
    app = Flask(__name__)
    fixed_home = Path(home).expanduser() if home is not None else None

    def home_dir() -> Path:
        return fixed_home if fixed_home is not None else workspace.get_home()

    def tracker_csv() -> Path:
        return home_dir() / "tracker.csv"

    def output_dir() -> Path:
        return home_dir() / "output"

    def read_tracker() -> list[dict]:
        """Ported from the source read_tracker: read each tracker row and enrich
        with its pack (ATS score + which safe files exist)."""
        rows: list[dict] = []
        tracker = tracker_csv()
        if not tracker.exists():
            return rows
        with tracker.open(newline="", encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                company = (row.get("company") or "").strip()
                role = (row.get("role") or "").strip()
                if not company:
                    continue
                slug = pack_slug(company, role)
                pack_dir = output_dir() / slug
                has_pack = pack_dir.is_dir()
                ats = _read_ats(pack_dir) if has_pack else None
                pack_files = {}
                if has_pack:
                    for name in sorted(p.name for p in pack_dir.iterdir() if p.is_file()):
                        if name in SAFE_FILES:
                            pack_files[name] = {"size": (pack_dir / name).stat().st_size}
                rows.append({
                    "id": i,
                    "company": company,
                    "role": role,
                    "url": row.get("url", ""),
                    "status": row.get("status", "not_applied"),
                    "work_auth_status": row.get("work_auth_status", ""),
                    "source": row.get("source", ""),
                    "discovered_date": row.get("discovered_date", ""),
                    "date_applied": row.get("date_applied", ""),
                    "notes": row.get("notes", ""),
                    "job_id": row.get("job_id", ""),
                    "pack_slug": slug,
                    "has_pack": has_pack,
                    "pack_files": pack_files,
                    "ats_data": ats,
                    "ats_score": ats.get("match_score") if ats else None,
                })
        return rows

    def scan_all_packs() -> list[dict]:
        """Ported from the source scan_all_packs, adapted to the flat pack layout."""
        packs: list[dict] = []
        out = output_dir()
        if not out.is_dir():
            return packs
        for pack_dir in sorted(p for p in out.iterdir() if p.is_dir()):
            ats = _read_ats(pack_dir)
            pack_files = {
                p.name: {"size": p.stat().st_size}
                for p in sorted(pack_dir.iterdir()) if p.is_file() and p.name in SAFE_FILES
            }
            packs.append({
                "company": (ats or {}).get("company", pack_dir.name),
                "role": (ats or {}).get("role", ""),
                "pack_slug": pack_dir.name,
                "pack_files": pack_files,
                "ats_data": ats,
                "ats_score": ats.get("match_score") if ats else None,
            })
        return packs

    def write_tracker(rows: list[dict]) -> None:
        tracker = tracker_csv()
        tracker.parent.mkdir(parents=True, exist_ok=True)
        with tracker.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in FIELDNAMES})

    @app.route("/")
    def index():
        jobs = read_tracker()
        all_packs = scan_all_packs()
        tracked = {j["pack_slug"] for j in jobs}
        extra_packs = [p for p in all_packs if p["pack_slug"] not in tracked]
        stats = {
            "total": len(jobs),
            "packs_ready": sum(1 for j in jobs if j["has_pack"]),
            "applied": sum(1 for j in jobs if j["status"] in ("applied", "interview", "offer")),
            "work_auth_ok": sum(1 for j in jobs if j.get("work_auth_status") == "confirmed"),
            "extra_packs": len(extra_packs),
        }
        return render_template("index.html", jobs=jobs, extra_packs=extra_packs, stats=stats)

    @app.route("/api/jobs")
    def api_jobs():
        return jsonify(read_tracker())

    @app.route("/api/update-status", methods=["POST"])
    def api_update_status():
        data = request.get_json(silent=True) or {}
        idx = data.get("id")
        new_status = data.get("status")
        # Reload the raw tracker rows so we write ALL columns back, not the enriched view.
        tracker = tracker_csv()
        raw: list[dict] = []
        if tracker.exists():
            with tracker.open(newline="", encoding="utf-8") as f:
                raw = list(csv.DictReader(f))
        if not isinstance(idx, int) or not (0 <= idx < len(raw)):
            return jsonify({"ok": False, "error": "invalid id"}), 400
        raw[idx]["status"] = new_status
        write_tracker(raw)
        return jsonify({"ok": True})

    def _safe_send(pack_slug_arg: str, filename: str, *, as_attachment: bool):
        if filename not in SAFE_FILES:
            return "Not allowed", 403
        directory = (output_dir() / pack_slug_arg).resolve()
        # Ensure the resolved dir stays inside output_dir (defeat traversal).
        if output_dir().resolve() not in directory.parents and directory != output_dir().resolve():
            return "Not allowed", 403
        target = directory / filename
        if not target.exists():
            return "File not found", 404
        return send_from_directory(str(directory), filename, as_attachment=as_attachment)

    @app.route("/download/<pack_slug>/<filename>")
    def download_file(pack_slug, filename):
        return _safe_send(pack_slug, filename, as_attachment=True)

    @app.route("/view/<pack_slug>/<filename>")
    def view_file(pack_slug, filename):
        return _safe_send(pack_slug, filename, as_attachment=False)

    return app


def main() -> None:
    app = create_app()
    print("\n  Job Hunt Dashboard  ->  http://127.0.0.1:5050\n")
    app.run(host="127.0.0.1", port=5050)


if __name__ == "__main__":
    main()
