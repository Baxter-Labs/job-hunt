import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import search.tracker as T  # noqa: E402


def _path(tmp_path):
    return tmp_path / "tracker.csv"


def test_upsert_appends_then_roundtrips(tmp_path):
    p = _path(tmp_path)
    res = T.upsert(company="Acme", role="Backend Engineer", url="https://a",
                   status="discovered", work_auth_status="confirmed",
                   job_id="indeed_1", source="indeed", path=p)
    assert res["action"] == "added"
    rows = T.load_tracker(p)
    assert len(rows) == 1
    assert rows[0]["company"] == "Acme"
    assert rows[0]["work_auth_status"] == "confirmed"
    assert rows[0]["discovered_date"]  # stamped


def test_upsert_updates_existing_same_company_role(tmp_path):
    p = _path(tmp_path)
    T.upsert(company="Acme", role="Backend Engineer", status="discovered", path=p)
    res = T.upsert(company="acme", role="backend engineer", status="applied", path=p)
    assert res["action"] == "updated"
    rows = T.load_tracker(p)
    assert len(rows) == 1
    assert rows[0]["status"] == "applied"


def test_is_duplicate_by_company_role_and_job_id(tmp_path):
    p = _path(tmp_path)
    T.upsert(company="Acme", role="Backend Engineer", job_id="x1", path=p)
    rows = T.load_tracker(p)
    assert T.is_duplicate(rows, "ACME", "backend engineer") is True
    assert T.is_duplicate(rows, "Other", "Other Role", job_id="x1") is True
    assert T.is_duplicate(rows, "Other", "Other Role") is False


def test_load_missing_returns_empty(tmp_path):
    assert T.load_tracker(_path(tmp_path)) == []


def test_summarize_counts(tmp_path):
    p = _path(tmp_path)
    T.upsert(company="A", role="R1", status="discovered", work_auth_status="confirmed", path=p)
    T.upsert(company="B", role="R2", status="applied", work_auth_status="not_found", path=p)
    T.upsert(company="C", role="R3", status="applied", work_auth_status="confirmed", path=p)
    summary = T.summarize(T.load_tracker(p))
    assert summary["total"] == 3
    assert summary["by_status"]["applied"] == 2
    assert summary["by_work_auth"]["confirmed"] == 2


def test_defaults_to_workspace_path(monkeypatch, tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    T.upsert(company="A", role="R", path=None)  # None -> workspace tracker
    assert (home / "tracker.csv").exists()
