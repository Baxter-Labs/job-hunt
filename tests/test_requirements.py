from pathlib import Path

REQS = (Path(__file__).resolve().parents[1] / "plugins" / "job-hunt"
        / "scripts" / "requirements.txt")


def test_flask_is_declared_optional():
    text = REQS.read_text(encoding="utf-8").lower()
    assert "flask" in text
    # It must be clearly marked optional / dashboard-only in a comment.
    assert "optional" in text or "dashboard" in text
