import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import tailor.pipeline as pipe  # noqa: E402


def _write_master(home):
    master = {
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
    (home / "cv_master.json").write_text(json.dumps(master), encoding="utf-8")
    return master


def _faithful_tailored():
    # Only reorders/rephrases master facts -> fabrication check must pass.
    return {
        "schema_version": "1.0",
        "meta": {"company": "", "role": "", "model_used": "", "generated_at": ""},
        "contact": {"name": "Ada Lovelace", "title": "Backend Engineer",
                    "email": "ada@example.com", "phone": None, "location": "Remote",
                    "links": [], "work_authorization": None},
        "summary": "Backend engineer who builds Python services and ships with Docker.",
        "skills_grouped": [{"group": "Core", "skills": ["Python", "Docker"]}],
        "experience": [{"company": "Analytical Engines Ltd", "title": "Backend Engineer",
                        "dates": "Jan 2020 – Dec 2022",
                        "bullets": ["Built REST services in Python.",
                                    "Containerised the stack with Docker."]}],
        "highlights": ["Built REST services in Python."],
        "ats_keywords_used": ["python", "docker"],
        "fabrication_check": {"passed": True, "issues": []},
    }


def test_slugify():
    assert pipe.slugify("Booking.com") == "booking-com"
    assert pipe.slugify("Data Scientist") == "data-scientist"
    assert pipe.slugify("!!!") == "untitled"


def test_run_mock_pack_end_to_end(monkeypatch, tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    _write_master(home)
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    result = pipe.run_mock_pack(
        company="Acme", role="Backend Engineer",
        jd_text="We need Python and Docker for a backend role.",
    )
    pack = Path(result["pack_dir"])
    assert pack.name == "acme-backend-engineer"
    for f in ("tailored_cv.json", "cv.html", "cv.pdf", "ats_report.json", "change_log.md"):
        assert (pack / f).exists(), f"missing {f}"
    assert result["fabrication_passed"] is True
    assert isinstance(result["ats_score"], int)
    assert "python" in result["matched_keywords"]


def test_finalize_pack_passes_for_faithful_tailored(monkeypatch, tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    _write_master(home)
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    result = pipe.finalize_pack(
        company="Acme", role="Backend Engineer",
        tailored=_faithful_tailored(),
        jd_text="Backend role needing Python, Docker and Kubernetes.",
    )
    assert result["ok"] is True
    assert result["fabrication_passed"] is True
    pack = Path(result["pack_dir"])
    assert (pack / "cv.pdf").exists()
    assert (pack / "ats_report.json").exists()
    # Kubernetes is in the JD but not the CV -> reported as a gap, never added.
    assert "kubernetes" in result["missing_keywords"]


def test_finalize_pack_fails_loudly_on_fabrication(monkeypatch, tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    _write_master(home)
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    bad = _faithful_tailored()
    bad["experience"].append(
        {"company": "Ghost Corp", "title": "CTO", "dates": "2099", "bullets": ["invented"]}
    )
    result = pipe.finalize_pack(
        company="Acme", role="Backend Engineer", tailored=bad,
        jd_text="Backend role needing Python.",
    )
    assert result["ok"] is False
    assert result["fabrication_passed"] is False
    assert any("Ghost Corp" in i for i in result["fabrication_issues"])
    # Artifacts still written so the human can inspect.
    assert (Path(result["pack_dir"]) / "tailored_cv.json").exists()


def test_change_log_includes_ats_score(monkeypatch, tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    _write_master(home)
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    result = pipe.finalize_pack(
        company="Acme", role="Backend Engineer", tailored=_faithful_tailored(),
        jd_text="Backend role needing Python and Docker.",
    )
    log = (Path(result["pack_dir"]) / "change_log.md").read_text(encoding="utf-8")
    assert "ATS" in log
    assert "Fabrication check" in log
