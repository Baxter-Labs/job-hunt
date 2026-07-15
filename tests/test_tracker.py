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


def test_statuses_vocabulary_is_ordered_and_documented():
    assert T.STATUSES == (
        "not_applied", "pack_generated", "applied",
        "response", "interview", "offer", "rejected", "ghosted",
    )
    assert T.is_valid_status("offer") is True
    assert T.is_valid_status("bogus") is False


def test_applied_or_beyond_classification():
    for s in ("applied", "response", "interview", "offer", "rejected", "ghosted"):
        assert T.applied_or_beyond(s) is True, s
    for s in ("not_applied", "pack_generated", "discovered", ""):
        assert T.applied_or_beyond(s) is False, s


def test_log_outcome_validates_status(tmp_path):
    p = _path(tmp_path)
    res = T.log_outcome(company="Acme", role="Backend Engineer",
                        status="interview", path=p)
    assert res["action"] == "added"
    rows = T.load_tracker(p)
    assert rows[0]["status"] == "interview"
    # An interview implies the application happened -> date_applied stamped.
    assert rows[0]["date_applied"]


def test_log_outcome_rejects_unknown_status(tmp_path):
    p = _path(tmp_path)
    try:
        T.log_outcome(company="Acme", role="R", status="hired", path=p)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "hired" in str(e)
    assert T.load_tracker(p) == []  # nothing written


def test_upsert_stamps_date_applied_for_terminal_negative(tmp_path):
    p = _path(tmp_path)
    T.upsert(company="Acme", role="R", status="rejected", path=p)
    rows = T.load_tracker(p)
    assert rows[0]["date_applied"]  # rejected implies they applied
