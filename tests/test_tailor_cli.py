import json
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
VENV_PY = Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python"


def _master():
    return {
        "schema_version": "1.0",
        "contact": {"name": "Ada Lovelace", "title": "Backend Engineer",
                    "email": "ada@example.com", "phone": None, "location": "Remote",
                    "links": [], "work_authorization": None},
        "summary": "Engineer who ships services.",
        "skills": [{"name": "Python", "category": "Programming", "level": None},
                   {"name": "Docker", "category": "DevOps", "level": None}],
        "experience": [{"company": "Analytical Engines Ltd", "title": "Backend Engineer",
                        "location": "London", "dates": "Jan 2020 – Dec 2022",
                        "bullets": ["Built REST services in Python.",
                                    "Containerised the stack with Docker."]}],
        "education": [], "projects": [], "certifications": [], "languages": ["English"],
    }


def _faithful_tailored():
    return {
        "schema_version": "1.0",
        "meta": {"company": "", "role": "", "model_used": "", "generated_at": ""},
        "contact": {"name": "Ada Lovelace", "title": "Backend Engineer",
                    "email": "ada@example.com", "phone": None, "location": "Remote",
                    "links": [], "work_authorization": None},
        "summary": "Backend engineer building Python services shipped with Docker.",
        "skills_grouped": [{"group": "Core", "skills": ["Python", "Docker"]}],
        "experience": [{"company": "Analytical Engines Ltd", "title": "Backend Engineer",
                        "dates": "Jan 2020 – Dec 2022",
                        "bullets": ["Built REST services in Python."]}],
        "highlights": [], "ats_keywords_used": ["python", "docker"],
        "fabrication_check": {"passed": True, "issues": []},
    }


def _run(args, home):
    proc = subprocess.run(
        [str(VENV_PY), "-m", "tailor.tailor_cli", *args],
        cwd=str(SCRIPTS), capture_output=True, text=True,
        env={"JOB_HUNT_HOME": str(home), "PATH": "/usr/bin:/bin"},
    )
    return proc


def _setup(tmp_path):
    home = tmp_path / "ws"
    (home / "output").mkdir(parents=True)
    (home / "jd_queue").mkdir(parents=True)
    (home / "cv_master.json").write_text(json.dumps(_master()), encoding="utf-8")
    return home


def test_check_reports_master(tmp_path):
    home = _setup(tmp_path)
    proc = _run(["check"], home)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["has_master"] is True


def test_save_jd(tmp_path):
    home = _setup(tmp_path)
    proc = _run(["save-jd", "--company", "Acme", "--role", "Backend Engineer",
                 "--jd-text", "Python and Docker backend role."], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert Path(out["jd_path"]).exists()


def test_mock_pack(tmp_path):
    home = _setup(tmp_path)
    proc = _run(["mock-pack", "--company", "Acme", "--role", "Backend Engineer",
                 "--jd-text", "We need Python and Docker."], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    pack = Path(out["pack_dir"])
    assert (pack / "cv.pdf").exists()
    assert (pack / "ats_report.json").exists()
    assert (pack / "change_log.md").exists()
    assert isinstance(out["ats_score"], int)
    assert out["fabrication_passed"] is True


def test_finalize_ok(tmp_path):
    home = _setup(tmp_path)
    tf = tmp_path / "tailored.json"
    tf.write_text(json.dumps(_faithful_tailored()), encoding="utf-8")
    proc = _run(["finalize", "--company", "Acme", "--role", "Backend Engineer",
                 "--jd-text", "Python, Docker and Kubernetes backend role.",
                 "--tailored-file", str(tf)], home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert out["fabrication_passed"] is True
    assert "kubernetes" in out["missing_keywords"]
    assert (Path(out["pack_dir"]) / "cv.pdf").exists()


def test_finalize_fails_loudly_on_fabrication(tmp_path):
    home = _setup(tmp_path)
    bad = _faithful_tailored()
    bad["experience"].append({"company": "Ghost Corp", "title": "CTO",
                              "dates": "2099", "bullets": ["invented"]})
    tf = tmp_path / "bad.json"
    tf.write_text(json.dumps(bad), encoding="utf-8")
    proc = _run(["finalize", "--company", "Acme", "--role", "Backend Engineer",
                 "--jd-text", "Python backend role.", "--tailored-file", str(tf)], home)
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["ok"] is False
    assert out["fabrication_passed"] is False


def test_finalize_rejects_non_object_tailored(tmp_path):
    home = _setup(tmp_path)
    tf = tmp_path / "arr.json"
    tf.write_text("[]", encoding="utf-8")
    proc = _run(["finalize", "--company", "Acme", "--role", "Backend Engineer",
                 "--jd-text", "Python role.", "--tailored-file", str(tf)], home)
    assert proc.returncode == 1
    out = json.loads(proc.stdout)   # clean JSON, not a traceback
    assert out["ok"] is False and "error" in out
