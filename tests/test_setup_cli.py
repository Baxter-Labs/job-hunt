import json
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
VENV_PY = Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python"


def _run(args, home):
    env = {"JOB_HUNT_HOME": str(home), "PATH": "/usr/bin:/bin"}
    proc = subprocess.run(
        [str(VENV_PY), "-m", "engine.setup_cli", *args],
        cwd=str(SCRIPTS),
        capture_output=True,
        text=True,
        env={**env},
    )
    return proc


def test_init_workspace(tmp_path):
    home = tmp_path / "ws"
    proc = _run(["init-workspace"], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert Path(out["home"]) == home
    assert (home / "output").is_dir()


def test_write_profile_valid(tmp_path):
    home = tmp_path / "ws"
    _run(["init-workspace"], home)
    profile = {
        "schema_version": "1.0",
        "contact": {"name": "Ada Lovelace", "email": "ada@example.com",
                     "phone": None, "location": None, "links": []},
        "target_locations": ["Netherlands"],
        "platforms": ["indeed"],
        "work_auth": {"needs_sponsorship": True, "scheme": "nl-ind-hsm"},
        "language_constraints": {"english_only": True},
        "apply_prefs": {"auto_submit_simple_forms": False},
    }
    proc = _run(["write-profile", "--json", json.dumps(profile)], home)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["ok"] is True
    assert (home / "profile.json").exists()


def test_write_profile_invalid_returns_issues(tmp_path):
    home = tmp_path / "ws"
    _run(["init-workspace"], home)
    bad = {"contact": {"name": "", "email": ""}, "platforms": [],
            "work_auth": {"needs_sponsorship": True, "scheme": "h1b"}}
    proc = _run(["write-profile", "--json", json.dumps(bad)], home)
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["ok"] is False and out["issues"]


def test_show_reports_state(tmp_path):
    home = tmp_path / "ws"
    _run(["init-workspace"], home)
    proc = _run(["show"], home)
    out = json.loads(proc.stdout)
    assert out["has_profile"] is False
    assert out["has_master"] is False


def test_write_master_valid(tmp_path):
    home = tmp_path / "ws"
    _run(["init-workspace"], home)
    master = {
        "schema_version": "1.0",
        "contact": {"name": "Ada Lovelace", "title": "ML Engineer",
                     "email": "ada@example.com", "phone": None, "location": None,
                     "links": [], "work_authorization": None},
        "summary": "Engineer.",
        "skills": [{"name": "Python", "category": "Programming", "level": None}],
        "experience": [{"company": "Analytical Engines", "title": "ML Engineer",
                         "location": "London", "dates": "Jan 2020 – Dec 2022",
                         "bullets": ["Built models."]}],
        "education": [], "projects": [], "certifications": [], "languages": ["English"],
    }
    proc = _run(["write-master", "--json", json.dumps(master)], home)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["ok"] is True
    assert (home / "cv_master.json").exists()


def test_extract_cv_missing_file_returns_clean_json(tmp_path):
    home = tmp_path / "ws"
    _run(["init-workspace"], home)
    proc = _run(["extract-cv", "--pdf", str(tmp_path / "nope.pdf")], home)
    assert proc.returncode == 1
    out = json.loads(proc.stdout)  # must be clean JSON, not a traceback
    assert out["ok"] is False and "error" in out
