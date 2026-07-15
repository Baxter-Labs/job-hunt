import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import apply.apply_cli as CLI  # noqa: E402
import search.tracker as T  # noqa: E402


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = CLI.main(argv)
    return code, json.loads(buf.getvalue().strip().splitlines()[-1])


def _seed_workspace(monkeypatch, tmp_path):
    home = tmp_path / "ws"
    (home / "output").mkdir(parents=True)
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    (home / "profile.json").write_text(json.dumps({
        "schema_version": "1.0",
        "contact": {"name": "Ada Lovelace", "email": "ada@example.com",
                    "phone": "+1", "location": "Amsterdam", "links": []},
        "platforms": ["indeed"],
        "work_auth": {"needs_sponsorship": True, "scheme": "nl-ind-hsm"},
        "apply_prefs": {"auto_submit_simple_forms": False},
    }), encoding="utf-8")
    return home


def _seed_pack(home, slug="acme-backend-engineer", score=70):
    pack = home / "output" / slug
    pack.mkdir(parents=True)
    (pack / "ats_report.json").write_text(json.dumps({
        "company": "Acme", "role": "Backend Engineer",
        "total_keywords": 10, "matched_count": 7, "match_score": score,
        "matched_keywords": ["python"], "missing_keywords": ["kubernetes"],
    }), encoding="utf-8")
    (pack / "cv.pdf").write_text("%PDF", encoding="utf-8")
    return pack


def test_preapply_emits_ats_prefill_and_auto_submit(monkeypatch, tmp_path):
    home = _seed_workspace(monkeypatch, tmp_path)
    _seed_pack(home)
    code, out = _run(["preapply", "--pack", "acme-backend-engineer"])
    assert code == 0 and out["ok"] is True
    assert out["ats_score"] == 70
    assert out["missing_keywords"] == ["kubernetes"]
    assert out["prefill_fields"]["email"] == "ada@example.com"
    assert out["auto_submit"]["allowed"] is False  # toggle off in profile


def test_preapply_auto_submit_gated_by_threshold(monkeypatch, tmp_path):
    home = _seed_workspace(monkeypatch, tmp_path)
    (home / "profile.json").write_text(json.dumps({
        "schema_version": "1.0",
        "contact": {"name": "Ada", "email": "a@e.com", "links": []},
        "platforms": ["indeed"],
        "work_auth": {"needs_sponsorship": False, "scheme": "none"},
        "apply_prefs": {"auto_submit_simple_forms": True, "min_ats_score": 75},
    }), encoding="utf-8")
    _seed_pack(home, score=60)
    code, out = _run(["preapply", "--pack", "acme-backend-engineer"])
    assert out["auto_submit"]["allowed"] is False and "75" in out["auto_submit"]["reason"]


def test_preapply_missing_profile_errors(monkeypatch, tmp_path):
    home = tmp_path / "ws"; (home / "output").mkdir(parents=True)
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    code, out = _run(["preapply", "--pack", "whatever"])
    assert code == 1 and out["ok"] is False


def test_record_upserts_applied(monkeypatch, tmp_path):
    home = _seed_workspace(monkeypatch, tmp_path)
    code, out = _run(["record", "--company", "Acme", "--role", "Backend Engineer",
                      "--status", "applied", "--url", "https://a", "--source", "indeed"])
    assert code == 0 and out["action"] == "added"
    rows = T.load_tracker(home / "tracker.csv")
    assert rows[0]["status"] == "applied"
    assert rows[0]["date_applied"]  # stamped by upsert


def test_record_second_call_updates(monkeypatch, tmp_path):
    home = _seed_workspace(monkeypatch, tmp_path)
    _run(["record", "--company", "Acme", "--role", "R", "--status", "discovered"])
    code, out = _run(["record", "--company", "Acme", "--role", "R", "--status", "applied"])
    assert out["action"] == "updated"
