import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "plugins" / "job-hunt" / "scripts"
VENV_PY = REPO / ".venv" / "bin" / "python"

MASTER = {
    "schema_version": "1.0",
    "contact": {"name": "Ada Placeholder", "title": "Backend Engineer",
                "email": "ada@example.com"},
    "summary": "Senior backend engineer building Python services on AWS.",
    "skills": [{"name": "Python"}, {"name": "SQL"}, {"name": "Docker"}],
    "experience": [{"company": "Northwind BV", "title": "Senior Backend Engineer",
                    "dates": "Jan 2019 – Dec 2024",
                    "bullets": ["Built Python services with Docker.",
                                "Ran SQL pipelines."]}],
}


def _home(tmp_path):
    home = tmp_path / "ws"
    home.mkdir()
    (home / "cv_master.json").write_text(json.dumps(MASTER), encoding="utf-8")
    return home


def _run(args, home):
    return subprocess.run(
        [str(VENV_PY), "-m", "scoring.scoring_cli", *args],
        cwd=str(SCRIPTS), capture_output=True, text=True,
        env={"JOB_HUNT_HOME": str(home), "PATH": "/usr/bin:/bin"},
    )


def test_fit_from_text_ok(tmp_path):
    home = _home(tmp_path)
    proc = _run(["fit", "--jd-text",
                 "Senior Backend Engineer. Python, SQL and Docker."], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert isinstance(out["fit_score"], int) and 0 <= out["fit_score"] <= 100
    assert set(out["components"]) == {"skills", "experience", "seniority"}
    assert isinstance(out["reasons"], list) and out["reasons"]


def test_fit_from_file_ok(tmp_path):
    home = _home(tmp_path)
    jd = tmp_path / "jd.txt"
    jd.write_text("Backend Engineer. Python and SQL.", encoding="utf-8")
    proc = _run(["fit", "--jd-file", str(jd)], home)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["ok"] is True


def test_fit_requires_exactly_one_jd_source_json_exit1(tmp_path):
    home = _home(tmp_path)
    proc = _run(["fit"], home)                  # neither --jd-file nor --jd-text
    assert proc.returncode == 1
    out = json.loads(proc.stdout)               # JSON, NOT argparse exit 2
    assert out["ok"] is False and "error" in out


def test_fit_missing_master_json_exit1(tmp_path):
    home = tmp_path / "empty"
    home.mkdir()                                # no cv_master.json
    proc = _run(["fit", "--jd-text", "Python."], home)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["ok"] is False


def test_fit_emits_single_json_object(tmp_path):
    home = _home(tmp_path)
    proc = _run(["fit", "--jd-text", "Python and SQL."], home)
    assert proc.stdout.strip().count("\n") == 0  # exactly one line / one object
