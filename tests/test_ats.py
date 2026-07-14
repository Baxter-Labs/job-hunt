import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import tailor.ats as ats  # noqa: E402


def test_ats_score_formula():
    assert ats.ats_score(3, 4) == 75
    assert ats.ats_score(1, 3) == 33   # round(33.33)
    assert ats.ats_score(2, 3) == 67   # round(66.66)
    assert ats.ats_score(0, 0) == 0    # no keywords -> 0, never divide-by-zero


def test_match_keywords_word_boundary_exact():
    cv = "I built REST APIs in Python and deployed with Docker."
    keywords = ["python", "docker", "kubernetes", "rest"]
    matched, missing = ats.match_keywords(cv, keywords)
    assert matched == ["python", "docker", "rest"]
    assert missing == ["kubernetes"]


def test_single_letter_lexicon_no_false_positive():
    # "r" (the language) must NOT match inside "docker"/"react".
    matched, missing = ats.match_keywords("We use Docker and React.", ["r"])
    assert matched == []
    assert missing == ["r"]


def test_extract_keywords_finds_lexicon_terms():
    jd = "We use Python, SQL, Docker and AWS every day."
    kws = set(ats.extract_keywords(jd))
    assert {"python", "sql", "docker", "aws"} <= kws
    assert "kubernetes" not in kws  # not mentioned -> not a keyword


def test_extract_keywords_is_domain_agnostic():
    # A marketing JD: the OLD AI/ML-hardcoded matcher would find nothing here.
    jd = "Drive SEO, run Google Analytics dashboards, own content marketing and HubSpot."
    kws = set(ats.extract_keywords(jd))
    assert {"seo", "google analytics", "content marketing", "hubspot"} <= kws


def test_extract_keywords_mines_salient_non_lexicon_terms():
    jd = ("Experience with the Foobar platform required. Foobar powers our stack; "
          "Foobar expertise is essential.")
    assert "foobar" in ats.extract_keywords(jd)


def test_build_ats_report_shape_and_consistency():
    jd = "Backend role: Python, SQL, Docker and Kubernetes required. AWS a plus."
    cv = "Python engineer. Built SQL pipelines and Dockerised services."
    report = ats.build_ats_report(jd, cv, "Acme", "Backend Engineer")
    assert set(report) == {
        "company", "role", "total_keywords", "matched_count", "missing_count",
        "match_score", "matched_keywords", "missing_keywords",
    }
    assert report["matched_count"] + report["missing_count"] == report["total_keywords"]
    assert report["match_score"] == ats.ats_score(report["matched_count"], report["total_keywords"])
    assert "python" in report["matched_keywords"]
    assert "sql" in report["matched_keywords"]
    # Honest gaps: things the CV lacks are reported as missing, not fabricated in.
    assert "kubernetes" in report["missing_keywords"]
    assert "aws" in report["missing_keywords"]


def test_cv_text_from_tailored_flattens_fields():
    tailored = {
        "contact": {"title": "Backend Engineer"},
        "summary": "Ships services.",
        "skills_grouped": [{"group": "Core", "skills": ["Python", "Docker"]}],
        "experience": [{"title": "Engineer", "bullets": ["Built REST APIs."]}],
        "highlights": ["Cut latency."],
        "ats_keywords_used": ["python"],
    }
    text = ats.cv_text_from_tailored(tailored).lower()
    for token in ("backend engineer", "python", "docker", "rest apis", "cut latency"):
        assert token in text


def test_write_ats_report(tmp_path):
    report = ats.build_ats_report("Python role.", "Python dev.", "Acme", "Dev")
    path = ats.write_ats_report(report, tmp_path)
    assert path.name == "ats_report.json"
    assert json.loads(path.read_text())["company"] == "Acme"


def test_extract_keywords_strips_trailing_punctuation():
    jd = "Strong Python skills. Experience with Kubernetes."
    kws = ats.extract_keywords(jd)
    assert "kubernetes" in kws
    assert "kubernetes." not in kws
    assert "python" in kws
    assert "python." not in kws


def test_api_keyword_matches_plural_apis():
    matched, missing = ats.match_keywords("Built REST APIs for the platform.", ["api"])
    assert matched == ["api"]
    assert missing == []


def test_singular_boundary_still_strict_for_short_terms():
    # plural allowance must NOT loosen single-letter terms
    matched, missing = ats.match_keywords("We use React and Go daily.", ["r"])
    assert matched == [] and missing == ["r"]


def test_extract_keywords_does_not_remine_multiword_components():
    jd = "Run A/B testing and content marketing daily. A/B testing is core."
    kws = ats.extract_keywords(jd)
    assert "a/b testing" in kws
    assert "content marketing" in kws
    assert "testing" not in kws
    assert "marketing" not in kws
