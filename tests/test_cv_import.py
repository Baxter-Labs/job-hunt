import sys
from pathlib import Path

MODdir = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(MODdir))

import engine.cv_import as cvi  # noqa: E402


def _valid_master():
    return {
        "schema_version": "1.0",
        "contact": {
            "name": "Ada Lovelace",
            "title": "ML Engineer",
            "email": "ada@example.com",
            "phone": None,
            "location": None,
            "links": [],
            "work_authorization": None,
        },
        "summary": "Engineer.",
        "skills": [{"name": "Python", "category": "Programming", "level": None}],
        "experience": [
            {
                "company": "Analytical Engines",
                "title": "ML Engineer",
                "location": "London",
                "dates": "Jan 2020 – Dec 2022",
                "bullets": ["Built models."],
            }
        ],
        "education": [],
        "projects": [],
        "certifications": [],
        "languages": ["English"],
    }


def test_validate_accepts_good_master():
    assert cvi.validate_master_cv(_valid_master()) == []


def test_validate_rejects_missing_contact_name():
    m = _valid_master()
    m["contact"]["name"] = ""
    issues = cvi.validate_master_cv(m)
    assert any("contact.name" in i for i in issues)


def test_validate_rejects_bad_experience_item():
    m = _valid_master()
    m["experience"][0].pop("dates")
    issues = cvi.validate_master_cv(m)
    assert any("experience[0].dates" in i for i in issues)


def test_validate_rejects_skill_without_name():
    m = _valid_master()
    m["skills"][0].pop("name")
    issues = cvi.validate_master_cv(m)
    assert any("skills[0].name" in i for i in issues)


def test_validate_rejects_wrong_schema_version():
    m = _valid_master()
    m["schema_version"] = "2.0"
    issues = cvi.validate_master_cv(m)
    assert any("schema_version" in i for i in issues)


def test_extract_pdf_text_reads_text(tmp_path):
    pdf = tmp_path / "cv.pdf"
    _write_minimal_pdf(pdf, "Hello CV Text")
    text = cvi.extract_pdf_text([pdf])
    assert "Hello CV Text" in text


def test_save_master_roundtrip(tmp_path):
    path = tmp_path / "cv_master.json"
    cvi.save_master_cv(_valid_master(), path)
    assert path.exists()
    import json
    assert json.loads(path.read_text())["contact"]["name"] == "Ada Lovelace"


def _write_minimal_pdf(path, text):
    """Write a tiny one-page PDF containing `text` using reportlab (a test-only
    dependency). Skip the check if reportlab is not installed."""
    import importlib.util
    if importlib.util.find_spec("reportlab") is None:
        import pytest
        pytest.skip("reportlab not installed; PDF text-extraction check skipped")
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, text)
    c.save()
