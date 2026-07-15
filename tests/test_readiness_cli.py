import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "plugins" / "job-hunt" / "scripts"
VENV_PY = REPO / ".venv" / "bin" / "python"

MASTER = {
    "schema_version": "1.0",
    "contact": {"name": "Ada Placeholder", "title": "Backend Engineer", "email": "ada@example.com"},
    "summary": "Senior backend engineer building Python microservices on AWS.",
    "skills": [{"name": "Python"}, {"name": "SQL"}, {"name": "Docker"}, {"name": "Kubernetes"}],
    "experience": [{"company": "Northwind BV", "title": "Senior Backend Engineer",
                    "dates": "Jan 2019 – Dec 2024",
                    "bullets": ["Built Python microservices with Docker and Kubernetes."]}],
}

JD = "Senior Backend Engineer. Python, SQL, Docker and Kubernetes. Run microservices."


def _tailored(passed=True):
    return {
        "schema_version": "1.0",
        "contact": {"name": "Ada Placeholder", "title": "Backend Engineer",
                    "email": "ada@example.com", "phone": None, "location": None,
                    "links": [], "work_authorization": None},
        "summary": "Backend engineer.",
        "skills_grouped": [{"group": "Core", "skills": ["Python", "SQL", "Docker"]}],
        "experience": [{"company": "Northwind BV", "title": "Senior Backend Engineer",
                        "dates": "Jan 2019 – Dec 2024", "bullets": ["Built Python services."]}],
        "highlights": [], "ats_keywords_used": [],
        "fabrication_check": {"passed": passed, "issues": [] if passed else ["fabricated"]},
    }


def _home(tmp_path, *, tailored=None, save_jd=False):
    home = tmp_path / "ws"
    (home / "output").mkdir(parents=True)
    (home / "cv_master.json").write_text(json.dumps(MASTER), encoding="utf-8")
    pack = home / "output" / "northwind-bv-backend-engineer"
    pack.mkdir()
    (pack / "ats_report.json").write_text(json.dumps({
        "company": "Northwind BV", "role": "Backend Engineer",
        "total_keywords": 8, "matched_count": 6, "missing_count": 2,
        "match_score": 75, "matched_keywords": ["python", "sql"],
        "missing_keywords": ["kubernetes", "terraform"],
    }), encoding="utf-8")
    (pack / "cv.pdf").write_text("%PDF fake", encoding="utf-8")
    (pack / "cover_letter.pdf").write_text("%PDF fake", encoding="utf-8")
    if tailored is not None:
        (pack / "tailored_cv.json").write_text(json.dumps(tailored), encoding="utf-8")
    if save_jd:
        (home / "jd_queue").mkdir(parents=True, exist_ok=True)
        (home / "jd_queue" / "northwind-bv-backend-engineer.txt").write_text(JD, encoding="utf-8")
    return home, pack


def _run(args, home):
    return subprocess.run(
        [str(VENV_PY), "-m", "scoring.scoring_cli", *args],
        cwd=str(SCRIPTS), capture_output=True, text=True,
        env={"JOB_HUNT_HOME": str(home), "PATH": "/usr/bin:/bin"},
    )


def test_readiness_from_jd_text_ok_and_writes_json(tmp_path):
    home, pack = _home(tmp_path, tailored=_tailored())
    proc = _run(["readiness", "--pack", "northwind-bv-backend-engineer", "--jd-text", JD], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert isinstance(out["readiness_score"], int) and 0 <= out["readiness_score"] <= 100
    assert out["blocking"] is False
    assert isinstance(out["factors"], list) and out["factors"]
    assert (pack / "readiness.json").exists()   # written by default
    assert out["readiness_json"] == str(pack / "readiness.json")


def test_readiness_resolves_jd_from_queue_when_no_jd_flag(tmp_path):
    home, _ = _home(tmp_path, tailored=_tailored(), save_jd=True)
    proc = _run(["readiness", "--pack", "northwind-bv-backend-engineer"], home)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["ok"] is True


def test_readiness_fabrication_block_score_zero(tmp_path):
    home, _ = _home(tmp_path, tailored=_tailored(passed=False))
    proc = _run(["readiness", "--pack", "northwind-bv-backend-engineer", "--jd-text", JD], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["blocking"] is True and out["readiness_score"] == 0


def test_readiness_no_write_skips_file(tmp_path):
    home, pack = _home(tmp_path, tailored=_tailored())
    proc = _run(["readiness", "--pack", "northwind-bv-backend-engineer",
                 "--jd-text", JD, "--no-write"], home)
    assert proc.returncode == 0, proc.stderr
    assert not (pack / "readiness.json").exists()
    assert json.loads(proc.stdout)["readiness_json"] is None


def test_readiness_missing_pack_arg_is_json_exit1(tmp_path):
    home, _ = _home(tmp_path, tailored=_tailored())
    proc = _run(["readiness", "--jd-text", JD], home)   # no --pack
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["ok"] is False       # JSON, NOT argparse exit 2


def test_readiness_no_jd_anywhere_is_json_exit1(tmp_path):
    home, _ = _home(tmp_path, tailored=_tailored())     # no jd_queue, no --jd-*
    proc = _run(["readiness", "--pack", "northwind-bv-backend-engineer"], home)
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["ok"] is False and "error" in out


def test_readiness_missing_master_json_exit1(tmp_path):
    home = tmp_path / "empty"
    (home / "output" / "p").mkdir(parents=True)         # pack exists, master does not
    proc = _run(["readiness", "--pack", "p", "--jd-text", JD], home)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["ok"] is False


def test_readiness_emits_single_json_object(tmp_path):
    home, _ = _home(tmp_path, tailored=_tailored())
    proc = _run(["readiness", "--pack", "northwind-bv-backend-engineer", "--jd-text", JD], home)
    assert proc.stdout.strip().count("\n") == 0
