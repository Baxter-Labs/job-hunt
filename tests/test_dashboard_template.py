from pathlib import Path

TEMPLATE = (Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
            / "dashboard" / "templates" / "index.html")


def test_template_exists():
    assert TEMPLATE.exists()


def test_template_is_depersonalised():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "Eshwar" not in text
    assert "HSM Visa Required" not in text
    assert "dantepk" not in text


def test_template_uses_new_pack_filenames_and_download_urls():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "cv.pdf" in text
    assert "cover_letter.pdf" in text
    assert "base_cv.pdf" not in text
    assert "motivational_letter.pdf" not in text
    # New single-slug download route (no nested company/role).
    assert "/download/{{ job.pack_slug }}/" in text


def test_template_surfaces_ats_score():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "ats_score" in text
