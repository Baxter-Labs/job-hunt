import json
import sys
from pathlib import Path

EVALS = Path(__file__).resolve().parents[1] / "evals"
sys.path.insert(0, str(EVALS))

import loader  # noqa: E402


def _write(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


def test_golden_dirs_exist():
    assert loader.ATS_DIR.is_dir()
    assert loader.RANK_DIR.is_dir()


def test_validate_ats_case_accepts_well_formed(tmp_path):
    case = {
        "id": "sample",
        "synthetic": True,
        "jd": "Python and SQL required.",
        "cv_text": "Python developer with SQL.",
        "expect": {"score_min": 0, "score_max": 100,
                   "must_match": ["python"], "must_miss": ["sql"],
                   "must_not_appear": []},
    }
    # Should not raise.
    loader.validate_ats_case(case, "sample.json")


def test_validate_ats_case_rejects_missing_expect_key(tmp_path):
    bad = {
        "id": "bad",
        "synthetic": True,
        "jd": "x",
        "cv_text": "y",
        "expect": {"score_min": 0, "score_max": 100, "must_match": []},  # no must_miss
    }
    try:
        loader.validate_ats_case(bad, "bad.json")
        assert False, "expected CaseError"
    except loader.CaseError as e:
        assert "must_miss" in str(e)


def test_validate_ats_case_rejects_non_synthetic():
    bad = {"id": "b", "synthetic": False, "jd": "x", "cv_text": "y",
           "expect": {"score_min": 0, "score_max": 100,
                      "must_match": [], "must_miss": [], "must_not_appear": []}}
    try:
        loader.validate_ats_case(bad, "b.json")
        assert False, "expected CaseError"
    except loader.CaseError as e:
        assert "synthetic" in str(e)


def test_validate_ats_case_requires_exactly_one_cv_source():
    both = {"id": "b", "synthetic": True, "jd": "x", "cv_text": "y",
            "tailored_cv": {}, "expect": {"score_min": 0, "score_max": 100,
            "must_match": [], "must_miss": [], "must_not_appear": []}}
    try:
        loader.validate_ats_case(both, "b.json")
        assert False, "expected CaseError"
    except loader.CaseError as e:
        assert "cv_text" in str(e) or "tailored_cv" in str(e)


def test_validate_rank_case_rejects_missing_order():
    bad = {"id": "r", "synthetic": True, "listings": [], "expect": {}}
    try:
        loader.validate_rank_case(bad, "r.json")
        assert False, "expected CaseError"
    except loader.CaseError as e:
        assert "order" in str(e)


def test_load_ats_cases_reads_and_validates(tmp_path, monkeypatch):
    case = {"id": "tmp", "synthetic": True, "jd": "Python.", "cv_text": "Python.",
            "expect": {"score_min": 0, "score_max": 100,
                       "must_match": ["python"], "must_miss": [], "must_not_appear": []}}
    d = tmp_path / "ats"
    _write(d / "tmp.json", case)
    monkeypatch.setattr(loader, "ATS_DIR", d)
    cases = loader.load_ats_cases()
    assert [c["id"] for c in cases] == ["tmp"]
    assert cases[0]["_source"] == "tmp.json"


import ats_eval  # noqa: E402


def test_evaluate_ats_case_passes_on_matching_expectations():
    case = {
        "id": "inline", "synthetic": True,
        "jd": "Backend role: Python, SQL, Docker and Kubernetes required. AWS a plus.",
        "cv_text": "Python engineer. Built SQL pipelines and shipped with Docker.",
        "expect": {"score_min": 0, "score_max": 100,
                   "must_match": ["python", "sql", "docker"],
                   "must_miss": ["kubernetes", "aws"],
                   "must_not_appear": []},
        "_source": "inline.json",
    }
    res = ats_eval.evaluate_ats_case(case)
    assert res["passed"], res["failures"]
    assert res["kind"] == "ats"
    assert isinstance(res["score"], int)


def test_evaluate_ats_case_flags_band_and_membership_failures():
    case = {
        "id": "wrong", "synthetic": True,
        "jd": "Python and SQL required.",
        "cv_text": "Python developer.",
        "expect": {"score_min": 99, "score_max": 100,      # impossible band
                   "must_match": ["kubernetes"],           # not in JD → never matched
                   "must_miss": ["python"],                # python IS matched
                   "must_not_appear": ["python"]},         # python DOES appear
        "_source": "wrong.json",
    }
    res = ats_eval.evaluate_ats_case(case)
    assert res["passed"] is False
    assert len(res["failures"]) >= 3


def test_ats_tailored_cv_source_excludes_unrendered_keyword():
    # The honesty guard path: a keyword only in ats_keywords_used must NOT count.
    case = {
        "id": "honesty", "synthetic": True,
        "jd": "Backend role: Python, Docker, REST and Kubernetes required.",
        "tailored_cv": {
            "contact": {"title": "Backend Engineer"},
            "summary": "Ships Python services.",
            "skills_grouped": [{"group": "Core", "skills": ["Python", "Docker"]}],
            "experience": [{"title": "Engineer", "bullets": ["Built REST APIs."]}],
            "highlights": [],
            "ats_keywords_used": ["kubernetes"],
        },
        "expect": {"score_min": 0, "score_max": 100,
                   "must_match": ["python", "docker", "rest"],
                   "must_miss": ["kubernetes"], "must_not_appear": []},
        "_source": "honesty.json",
    }
    res = ats_eval.evaluate_ats_case(case)
    assert res["passed"], res["failures"]
