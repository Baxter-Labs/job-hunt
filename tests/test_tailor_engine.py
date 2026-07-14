import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import tailor.tailor_engine as eng  # noqa: E402


def _master():
    return {
        "schema_version": "1.0",
        "contact": {
            "name": "Ada Lovelace", "title": "Backend Engineer",
            "email": "ada@example.com", "phone": None, "location": "Remote",
            "links": [{"label": "GitHub", "url": "https://github.com/example"}],
            "work_authorization": None,
        },
        "summary": "Engineer who ships services.",
        "skills": [
            {"name": "Python", "category": "Programming", "level": None},
            {"name": "Docker", "category": "DevOps", "level": None},
        ],
        "experience": [
            {"company": "Analytical Engines Ltd", "title": "Backend Engineer",
             "location": "London", "dates": "Jan 2020 – Dec 2022",
             "bullets": ["Built REST services in Python.", "Containerised the stack with Docker."]},
        ],
        "education": [], "projects": [], "certifications": [], "languages": ["English"],
    }


def test_constants_and_prompt_paths():
    assert eng.DEFAULT_MODEL == "claude-opus-4-8"
    assert eng.FALLBACK_MODEL == "claude-sonnet-4-6"
    assert eng.SCHEMA_VERSION == "1.0"
    # Prompt assets resolve to the packaged tailor/prompts dir.
    assert eng.TEMPLATE_PATH.name == "tailor_prompt_template.md"
    assert eng.TEMPLATE_PATH.parent.name == "prompts"
    assert eng.TEMPLATE_PATH.exists()


def test_load_master_defaults_to_workspace(monkeypatch, tmp_path):
    home = tmp_path / "ws"
    home.mkdir()
    (home / "cv_master.json").write_text(json.dumps(_master()), encoding="utf-8")
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    loaded = eng.load_master_cv()  # no path -> workspace master
    assert loaded["contact"]["name"] == "Ada Lovelace"


def test_mock_tailor_passes_fabrication_and_validates():
    master = _master()
    tailored = eng.mock_tailored_cv(master, "Acme", "Backend Engineer")
    assert eng.validate_tailored_cv(tailored) == []
    fab = eng.fabrication_check(tailored, master)
    assert fab["passed"] is True and fab["issues"] == []


def test_fabrication_check_flags_invented_experience():
    master = _master()
    tailored = eng.mock_tailored_cv(master, "Acme", "Backend Engineer")
    tailored["experience"].append(
        {"company": "Made Up Inc", "title": "Wizard", "dates": "2099", "bullets": ["nope"]}
    )
    fab = eng.fabrication_check(tailored, master)
    assert fab["passed"] is False
    assert any("Made Up Inc" in i for i in fab["issues"])


def test_tailor_cv_mock_end_to_end(monkeypatch, tmp_path):
    home = tmp_path / "ws"
    home.mkdir()
    (home / "cv_master.json").write_text(json.dumps(_master()), encoding="utf-8")
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    out = tmp_path / "tailored_cv.json"
    tailored = eng.tailor_cv(
        jd_text="We need a Python engineer who knows Docker.",
        company="Acme", role="Backend Engineer", mock=True, out_path=out,
    )
    assert out.exists()
    assert tailored["meta"]["model_used"] == "mock"
    assert tailored["fabrication_check"]["passed"] is True
    assert eng.validate_tailored_cv(tailored) == []
