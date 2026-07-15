import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import insights.followup as F  # noqa: E402
from search.listing import pack_slug  # noqa: E402


def _rows():
    return [
        {"discovered_date": "2026-07-01", "date_applied": "2026-07-10",
         "company": "Acme", "role": "Backend Engineer", "url": "https://acme.example/job",
         "status": "applied", "work_auth_status": "confirmed",
         "job_id": "a1", "source": "indeed", "notes": ""},
    ]


def _seed_pack(out, company, role, score):
    pack = out / pack_slug(company, role)
    pack.mkdir(parents=True)
    (pack / "ats_report.json").write_text(json.dumps({
        "company": company, "role": role, "total_keywords": 10,
        "matched_count": 8, "missing_count": 2, "match_score": score,
        "matched_keywords": [], "missing_keywords": ["kubernetes", "terraform"],
    }), encoding="utf-8")
    return pack


def test_context_from_tracker_and_pack(tmp_path):
    out = tmp_path / "output"
    _seed_pack(out, "Acme", "Backend Engineer", 82)
    ctx = F.application_context("Acme", "Backend Engineer",
                                tracker_rows=_rows(), output_root=out)
    assert ctx == {
        "company": "Acme", "role": "Backend Engineer",
        "status": "applied", "date_applied": "2026-07-10",
        "url": "https://acme.example/job", "source": "indeed",
        "has_pack": True, "ats_score": 82,
    }


def test_context_matches_case_insensitively(tmp_path):
    out = tmp_path / "output"
    ctx = F.application_context("acme", "backend engineer",
                                tracker_rows=_rows(), output_root=out)
    assert ctx["status"] == "applied"
    assert ctx["source"] == "indeed"


def test_context_no_tracker_row(tmp_path):
    out = tmp_path / "output"
    _seed_pack(out, "Globex", "Platform Engineer", 60)
    ctx = F.application_context("Globex", "Platform Engineer",
                                tracker_rows=_rows(), output_root=out)
    assert ctx["status"] == "" and ctx["date_applied"] == ""
    assert ctx["url"] == "" and ctx["source"] == ""
    assert ctx["has_pack"] is True and ctx["ats_score"] == 60


def test_context_no_pack(tmp_path):
    out = tmp_path / "output"; out.mkdir()
    ctx = F.application_context("Acme", "Backend Engineer",
                                tracker_rows=_rows(), output_root=out)
    assert ctx["has_pack"] is False and ctx["ats_score"] is None
    assert ctx["status"] == "applied"  # tracker row still resolved


def test_context_reads_tracker_when_rows_not_passed(tmp_path, monkeypatch):
    # When tracker_rows is None, it loads via search.tracker against JOB_HUNT_HOME.
    home = tmp_path / "ws"; home.mkdir()
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    import importlib
    import engine.workspace as ws
    importlib.reload(ws)
    from search import tracker as tr
    tr.upsert(company="Acme", role="Backend Engineer", status="applied",
              url="https://x", source="indeed", path=home / "tracker.csv")
    out = home / "output"; out.mkdir()
    ctx = F.application_context("Acme", "Backend Engineer", output_root=out)
    assert ctx["status"] == "applied"
