import csv
import json
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
VENV_PY = Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python"


def _run(args, home):
    return subprocess.run(
        [str(VENV_PY), "-m", "search.search_cli", *args],
        cwd=str(SCRIPTS), capture_output=True, text=True,
        env={"JOB_HUNT_HOME": str(home), "PATH": "/usr/bin:/bin"},
    )


def _profile(home, scheme="nl-ind-hsm"):
    (home / "profile.json").write_text(json.dumps({
        "schema_version": "1.0",
        "contact": {"name": "Ada Lovelace", "email": "ada@example.com",
                    "phone": None, "location": None, "links": []},
        "target_locations": ["Netherlands"],
        "platforms": ["indeed", "career_pages"],
        "work_auth": {"needs_sponsorship": True, "scheme": scheme},
        "language_constraints": {"english_only": True},
        "apply_prefs": {"auto_submit_simple_forms": False},
    }), encoding="utf-8")


def _register(home, names):
    path = home / "config" / "nl_ind_hsm_sponsors.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["company_name", "careers_url", "category", "last_verified"])
        w.writeheader()
        for n in names:
            w.writerow({"company_name": n, "careers_url": "", "category": "hsm", "last_verified": ""})


def test_annotate_workauth_uses_profile_scheme(tmp_path):
    home = tmp_path / "ws"; (home / "config").mkdir(parents=True)
    _profile(home, "nl-ind-hsm")
    _register(home, ["ASML"])
    proc = _run(["annotate-workauth", "--companies", "ASML,FakeCo"], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["scheme"] == "nl-ind-hsm"
    assert out["statuses"]["ASML"]["status"] == "confirmed"
    assert out["statuses"]["FakeCo"]["status"] == "not_found"


def test_filter_dedupe_rank_end_to_end(tmp_path):
    home = tmp_path / "ws"
    (home / "output").mkdir(parents=True)
    (home / "config").mkdir(parents=True)
    _profile(home, "nl-ind-hsm")
    _register(home, ["ASML", "ING Bank"])
    # Pre-track one listing so dedupe removes it.
    _run(["track", "--company", "ASML", "--role", "AI Engineer"], home)
    listings = [
        {"source": "indeed", "company": "ASML", "role": "AI Engineer",
         "url": "https://a", "job_id": "i1", "posted_date": "2026-07-14"},   # dup
        {"source": "indeed", "company": "ING Bank", "role": "ML Engineer",
         "url": "https://b", "job_id": "i2", "posted_date": "2026-07-14"},   # new, sponsor
        {"source": "indeed", "company": "RandomCo", "role": "Data Scientist",
         "url": "https://c", "job_id": "i3", "posted_date": "2026-07-14"},   # new, not_found
    ]
    lf = tmp_path / "listings.json"
    lf.write_text(json.dumps(listings), encoding="utf-8")
    proc = _run(["filter-dedupe-rank", "--listings-file", str(lf)], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    companies = [l["company"] for l in out["new"]]
    assert "ASML" not in companies            # deduped
    assert companies[0] == "ING Bank"          # sponsor ranks first
    assert "RandomCo" in companies             # not_found still shown (flagged, not dropped)
    assert out["counts"]["new"] == 2
    # Each surviving listing carries its work-auth status + rank score.
    ing = next(l for l in out["new"] if l["company"] == "ING Bank")
    assert ing["work_auth"]["status"] in {"confirmed", "possible"}
    assert "rank_score" in ing


def test_filter_dedupe_rank_collapses_intra_batch_duplicates(tmp_path):
    home = tmp_path / "ws"
    (home / "output").mkdir(parents=True)
    (home / "config").mkdir(parents=True)
    _profile(home, "none")
    listings = [
        {"source": "indeed", "company": "New Co", "role": "Data Scientist",
         "url": "https://a", "job_id": "i1", "posted_date": "2026-07-14"},
        {"source": "linkedin", "company": "New Co", "role": "Data Scientist",
         "url": "https://b", "job_id": "l1", "posted_date": "2026-07-14"},  # same job, 2nd platform
    ]
    lf = tmp_path / "listings.json"
    lf.write_text(json.dumps(listings), encoding="utf-8")
    proc = _run(["filter-dedupe-rank", "--listings-file", str(lf), "--scheme", "none"], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert out["counts"]["new"] == 1
    assert out["counts"]["intra_batch_collapsed"] == 1


def test_filter_dedupe_rank_drop_unknown(tmp_path):
    home = tmp_path / "ws"
    (home / "output").mkdir(parents=True)
    (home / "config").mkdir(parents=True)
    _profile(home, "nl-ind-hsm")
    _register(home, ["ASML"])
    listings = [{"source": "indeed", "company": "RandomCo", "role": "X",
                 "job_id": "z1", "posted_date": "2026-07-14"}]
    lf = tmp_path / "l.json"; lf.write_text(json.dumps(listings), encoding="utf-8")
    proc = _run(["filter-dedupe-rank", "--listings-file", str(lf), "--drop-unknown"], home)
    out = json.loads(proc.stdout)
    assert out["counts"]["new"] == 0          # not_found dropped under strict mode
    assert out["counts"]["dropped"] == 1


def test_status_summary(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    _run(["track", "--company", "A", "--role", "R", "--status", "applied",
          "--work-auth", "confirmed"], home)
    proc = _run(["status"], home)
    out = json.loads(proc.stdout)
    assert out["tracker"]["total"] == 1
    assert out["tracker"]["by_status"]["applied"] == 1


def test_refresh_register_offline_from_file(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    _profile(home, "nl-ind-hsm")
    seed = tmp_path / "seed.txt"
    seed.write_text("Foobar B.V.\nBaz Holding\n", encoding="utf-8")
    proc = _run(["refresh-register", "--from-file", str(seed)], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True and out["count"] == 2
    assert (home / "config" / "nl_ind_hsm_sponsors.csv").exists()


def test_refresh_register_rejects_non_register_scheme(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    _profile(home, "none")
    proc = _run(["refresh-register", "--scheme", "none"], home)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["ok"] is False


def test_log_outcome_valid_status_upserts(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    proc = _run(["log-outcome", "--company", "Acme", "--role", "AI Engineer",
                 "--status", "interview", "--source", "indeed"], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["action"] == "added"
    status_proc = _run(["status"], home)
    summary = json.loads(status_proc.stdout)["tracker"]
    assert summary["by_status"]["interview"] == 1


def test_log_outcome_rejects_unknown_status(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    proc = _run(["log-outcome", "--company", "Acme", "--role", "R",
                 "--status", "hired"], home)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["ok"] is False
