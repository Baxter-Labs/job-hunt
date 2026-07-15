import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
VENV_PY = Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python"


def _run(args, home):
    return subprocess.run(
        [str(VENV_PY), "-m", "insights.insights_cli", *args],
        cwd=str(SCRIPTS), capture_output=True, text=True,
        env={"JOB_HUNT_HOME": str(home), "PATH": "/usr/bin:/bin"},
    )


def _seed_pack(home, slug, company, role, missing, score=50):
    pack = home / "output" / slug
    pack.mkdir(parents=True)
    (pack / "ats_report.json").write_text(json.dumps({
        "company": company, "role": role, "total_keywords": 10,
        "matched_count": 10 - len(missing), "missing_count": len(missing),
        "match_score": score, "matched_keywords": [], "missing_keywords": missing,
    }), encoding="utf-8")
    return pack


# --- red-flags ---

def test_red_flags_from_text(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    proc = _run(["red-flags", "--jd-text",
                 "Fast-paced team of rockstars. Competitive salary."], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    flags = {f["flag"] for f in out["red_flags"]}
    assert {"fast-paced", "rockstar-language", "vague-compensation"} <= flags
    assert out["count"] == len(out["red_flags"])


def test_red_flags_from_file(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    jd = tmp_path / "jd.txt"; jd.write_text("Unlimited PTO and we are a family.", encoding="utf-8")
    proc = _run(["red-flags", "--jd-file", str(jd)], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    flags = {f["flag"] for f in out["red_flags"]}
    assert "unlimited-pto" in flags and "family-culture" in flags


def test_red_flags_requires_exactly_one_source(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    proc = _run(["red-flags"], home)  # neither --jd-file nor --jd-text
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["ok"] is False


def test_red_flags_clean_jd_empty(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    proc = _run(["red-flags", "--jd-text",
                 "Salary EUR 70,000. 25 days holiday. 4 years Python."], home)
    out = json.loads(proc.stdout)
    assert out["ok"] is True and out["count"] == 0 and out["red_flags"] == []


# --- upskill ---

def test_upskill_all(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    _seed_pack(home, "acme-backend", "Acme", "Backend", ["kubernetes", "terraform"])
    _seed_pack(home, "globex-platform", "Globex", "Platform", ["kubernetes"])
    proc = _run(["upskill", "--all"], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True and out["packs_scanned"] == 2
    assert out["gaps"][0]["keyword"] == "kubernetes" and out["gaps"][0]["count"] == 2


def test_upskill_single_pack(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    _seed_pack(home, "acme-backend", "Acme", "Backend", ["graphql"])
    proc = _run(["upskill", "--pack", "acme-backend"], home)
    out = json.loads(proc.stdout)
    assert out["ok"] is True and out["packs_scanned"] == 1
    assert [g["keyword"] for g in out["gaps"]] == ["graphql"]


def test_upskill_all_no_packs(tmp_path):
    home = tmp_path / "ws"; (home / "output").mkdir(parents=True)
    proc = _run(["upskill", "--all"], home)
    out = json.loads(proc.stdout)
    assert out["ok"] is True and out["packs_scanned"] == 0 and out["gaps"] == []


def test_upskill_no_args_returns_json_exit1(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    proc = _run(["upskill"], home)  # no --pack/--all
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["ok"] is False and "error" in out


# --- followup-context ---

def test_followup_context(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    _seed_pack(home, "acme-backend-engineer", "Acme", "Backend Engineer",
               ["kubernetes"], score=82)
    # record an application via the apply CLI's tracker path
    subprocess.run(
        [str(VENV_PY), "-m", "search.search_cli", "track",
         "--company", "Acme", "--role", "Backend Engineer",
         "--status", "applied", "--url", "https://acme.example"],
        cwd=str(SCRIPTS), capture_output=True, text=True,
        env={"JOB_HUNT_HOME": str(home), "PATH": "/usr/bin:/bin"},
    )
    proc = _run(["followup-context", "--company", "Acme", "--role", "Backend Engineer"], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert out["status"] == "applied"
    assert out["has_pack"] is True and out["ats_score"] == 82


def test_followup_context_unknown(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    proc = _run(["followup-context", "--company", "Nobody", "--role", "Nothing"], home)
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert out["status"] == "" and out["has_pack"] is False and out["ats_score"] is None


def test_followup_context_missing_args_returns_json_exit1(tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    proc = _run(["followup-context", "--company", "Acme"], home)  # missing --role
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["ok"] is False and "error" in out
