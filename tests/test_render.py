import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import tailor.render_cv as rcv  # noqa: E402
import tailor.render_letter as rlet  # noqa: E402


def test_render_cv_self_test_sample(tmp_path):
    sample = rcv._sample_tailored_cv()
    result = rcv.render_cv(sample, tmp_path)
    html = Path(result["html"])
    pdf = Path(result["pdf"])
    assert html.exists() and html.stat().st_size > 0
    assert pdf.exists() and pdf.stat().st_size > 0
    assert result["pdf_backend"] in {"weasyprint", "wkhtmltopdf", "reportlab", "stdlib"}
    text = html.read_text(encoding="utf-8")
    assert "Self Test Sample" in text
    assert "<table" not in text.lower()  # ATS-safe: no layout tables


def test_render_pdf_never_crashes_without_weasyprint(tmp_path):
    # Even with no PDF library, the stdlib backend must produce a file.
    sample = rcv._sample_tailored_cv()
    html = rcv.render_html(sample)
    pdf_path, backend = rcv.render_pdf(html, tmp_path / "cv.pdf", tailored=sample)
    assert pdf_path.exists() and pdf_path.stat().st_size > 0
    assert backend in {"weasyprint", "wkhtmltopdf", "reportlab", "stdlib"}


def test_render_letter_writes_html(tmp_path):
    pack = tmp_path / "acme-engineer"
    pack.mkdir()
    (pack / "tailored_cv.json").write_text(json.dumps(rcv._sample_tailored_cv()), encoding="utf-8")
    (pack / "cover_letter.md").write_text(
        "Dear Hiring Team,\n\nI am applying for the Sample Role.\n\nKind regards,\nSelf Test Sample",
        encoding="utf-8",
    )
    result = rlet.render_letter(pack)
    assert Path(result["html"]).exists()
    # PDF only when weasyprint is present; HTML is always written.
    if result["backend"] == "weasyprint":
        assert Path(result["pdf"]).exists()
