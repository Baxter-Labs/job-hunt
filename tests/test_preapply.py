import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import apply.preapply as P  # noqa: E402


def _profile(**overrides):
    p = {
        "contact": {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "+00 000 000 000",
            "location": "Amsterdam, Netherlands",
            "links": [{"label": "LinkedIn", "url": "https://linkedin.com/in/example"},
                      {"label": "GitHub", "url": "https://github.com/example"}],
        },
        "apply_prefs": {"auto_submit_simple_forms": False},
    }
    p.update(overrides)
    return p


def _seed_pack(root, slug="analytical-engines-ltd-backend-engineer", *, ats=True, cv=True):
    pack = root / slug
    pack.mkdir(parents=True)
    if ats:
        (pack / "ats_report.json").write_text(json.dumps({
            "company": "Analytical Engines Ltd", "role": "Backend Engineer",
            "total_keywords": 10, "matched_count": 7, "missing_count": 3,
            "match_score": 70,
            "matched_keywords": ["python", "sql", "aws", "docker", "api", "git", "linux"],
            "missing_keywords": ["kubernetes", "terraform", "graphql"],
        }), encoding="utf-8")
    if cv:
        (pack / "cv.pdf").write_text("%PDF-1.4 fake", encoding="utf-8")
        (pack / "cover_letter.pdf").write_text("%PDF-1.4 fake", encoding="utf-8")
    return pack


# --- prefill_fields: safe, non-secret, omits empties, NEVER a password ---

def test_prefill_fields_are_safe_contact_only():
    fields = P.prefill_fields(_profile())
    assert fields["full_name"] == "Ada Lovelace"
    assert fields["email"] == "ada@example.com"
    assert fields["phone"] == "+00 000 000 000"
    assert fields["location"] == "Amsterdam, Netherlands"
    assert fields["linkedin"] == "https://linkedin.com/in/example"
    assert fields["github"] == "https://github.com/example"
    # No secret-ish keys ever appear.
    blob = " ".join(fields).lower()
    for banned in ("password", "passwd", "secret", "token", "credential", "otp", "pin"):
        assert banned not in blob


def test_prefill_omits_empty_fields():
    prof = _profile(contact={"name": "Ada Lovelace", "email": "ada@example.com",
                             "phone": "", "location": None, "links": []})
    fields = P.prefill_fields(prof)
    assert "phone" not in fields and "location" not in fields and "links" not in fields


def test_prefill_tolerates_bare_string_link():
    prof = _profile(contact={"name": "A", "email": "a@e.com",
                             "links": ["https://site.example"]})
    fields = P.prefill_fields(prof)
    assert {"label": "", "url": "https://site.example"} in fields["links"]


# --- resolve_pack_dir: slug vs path ---

def test_resolve_pack_dir_by_slug(tmp_path):
    out = tmp_path / "output"; out.mkdir()
    got = P.resolve_pack_dir("acme-backend-engineer", output_root=out)
    assert got == out / "acme-backend-engineer"


def test_resolve_pack_dir_by_existing_path(tmp_path):
    pack = tmp_path / "output" / "acme-backend-engineer"; pack.mkdir(parents=True)
    got = P.resolve_pack_dir(str(pack), output_root=tmp_path / "output")
    assert got == pack


# --- preapply_summary: ATS FIRST + attachments + warnings ---

def test_preapply_summary_surfaces_ats_and_prefill(tmp_path):
    out = tmp_path / "output"
    pack = _seed_pack(out)
    summary = P.preapply_summary(pack, _profile())
    assert summary["exists"] is True
    assert summary["ats_score"] == 70              # read from match_score, not recomputed
    assert summary["missing_keywords"] == ["kubernetes", "terraform", "graphql"]
    assert summary["prefill_fields"]["email"] == "ada@example.com"
    assert summary["attachments"]["cv"].endswith("cv.pdf")
    assert summary["attachments"]["cover_letter"].endswith("cover_letter.pdf")
    assert summary["warnings"] == []


def test_preapply_summary_caps_missing_keywords(tmp_path):
    out = tmp_path / "output"
    pack = out / "many-missing"; pack.mkdir(parents=True)
    (pack / "ats_report.json").write_text(json.dumps({
        "company": "C", "role": "R", "total_keywords": 30, "matched_count": 0,
        "missing_count": 30, "match_score": 0,
        "matched_keywords": [], "missing_keywords": [f"kw{i}" for i in range(30)],
    }), encoding="utf-8")
    summary = P.preapply_summary(pack, _profile(), missing_limit=5)
    assert len(summary["missing_keywords"]) == 5


def test_preapply_summary_warns_when_no_ats_report(tmp_path):
    out = tmp_path / "output"
    pack = _seed_pack(out, ats=False)
    summary = P.preapply_summary(pack, _profile())
    assert summary["ats_score"] is None
    assert any("ats_report" in w.lower() for w in summary["warnings"])


def test_preapply_summary_warns_when_pack_missing(tmp_path):
    summary = P.preapply_summary(tmp_path / "output" / "nope", _profile())
    assert summary["exists"] is False
    assert any("not found" in w.lower() or "does not exist" in w.lower()
               for w in summary["warnings"])


def test_preapply_summary_warns_when_no_cv_attachment(tmp_path):
    out = tmp_path / "output"
    pack = _seed_pack(out, cv=False)
    summary = P.preapply_summary(pack, _profile())
    assert summary["attachments"]["cv"] is None
    assert any("cv" in w.lower() for w in summary["warnings"])


# --- auto_submit_decision: pure gate ---

def test_auto_submit_off_by_default():
    d = P.auto_submit_decision(_profile(), 90)
    assert d["allowed"] is False
    assert "off" in d["reason"].lower() or "auto_submit" in d["reason"].lower()


def test_auto_submit_on_no_threshold():
    prof = _profile(apply_prefs={"auto_submit_simple_forms": True})
    d = P.auto_submit_decision(prof, 42)
    assert d["allowed"] is True


def test_auto_submit_on_with_threshold_pass_and_fail():
    prof = _profile(apply_prefs={"auto_submit_simple_forms": True, "min_ats_score": 75})
    assert P.auto_submit_decision(prof, 80)["allowed"] is True
    fail = P.auto_submit_decision(prof, 60)
    assert fail["allowed"] is False and "75" in fail["reason"]


def test_auto_submit_threshold_blocks_when_score_unknown():
    prof = _profile(apply_prefs={"auto_submit_simple_forms": True, "min_ats_score": 50})
    d = P.auto_submit_decision(prof, None)
    assert d["allowed"] is False
