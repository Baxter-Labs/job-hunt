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
    assert loader.FIT_DIR.is_dir()


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


def test_validate_fit_case_rejects_missing_master():
    bad = {"id": "f", "synthetic": True, "jd": "x",
           "expect": {"fit_score_min": 0, "fit_score_max": 100}}
    try:
        loader.validate_fit_case(bad, "f.json")
        assert False, "expected CaseError"
    except loader.CaseError as e:
        assert "master" in str(e)


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


import rank_eval  # noqa: E402


def test_evaluate_rank_case_passes_on_expected_order():
    case = {
        "id": "inline-rank", "synthetic": True, "today": "2026-07-15",
        "listings": [
            {"id": "low", "company": "Zeta BV", "role": "Engineer",
             "posted_date": "", "work_auth": {"status": "not_found"}},
            {"id": "high", "company": "Alpha BV", "role": "Engineer",
             "posted_date": "2026-07-14", "work_auth": {"status": "confirmed"}},
        ],
        "expect": {"order": ["high", "low"]},
        "_source": "inline-rank.json",
    }
    res = rank_eval.evaluate_rank_case(case)
    assert res["passed"], res["failures"]
    assert res["kind"] == "rank"
    assert res["order"] == ["high", "low"]


def test_evaluate_rank_case_flags_wrong_order():
    case = {
        "id": "wrong-rank", "synthetic": True, "today": "2026-07-15",
        "listings": [
            {"id": "a", "company": "Alpha BV", "role": "Engineer",
             "posted_date": "2026-07-14", "work_auth": {"status": "confirmed"}},
            {"id": "b", "company": "Beta BV", "role": "Engineer",
             "posted_date": "", "work_auth": {"status": "not_found"}},
        ],
        "expect": {"order": ["b", "a"]},   # deliberately wrong
        "_source": "wrong-rank.json",
    }
    res = rank_eval.evaluate_rank_case(case)
    assert res["passed"] is False
    assert res["failures"]


import fit_eval  # noqa: E402
import re  # noqa: E402  (json already imported at top)
import run_evals  # noqa: E402

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PII_DENYLIST = ("eshwar", "eshwarpkofficial")


def test_all_ats_golden_cases_pass():
    for case in loader.load_ats_cases():
        res = ats_eval.evaluate_ats_case(case)
        assert res["passed"], f"{res['source']}: {res['failures']}"


def test_all_rank_golden_cases_pass():
    for case in loader.load_rank_cases():
        res = rank_eval.evaluate_rank_case(case)
        assert res["passed"], f"{res['source']}: {res['failures']}"


def test_all_fit_golden_cases_pass():
    for case in loader.load_fit_cases():
        res = fit_eval.evaluate_fit_case(case)
        assert res["passed"], f"{res['source']}: {res['failures']}"


def test_golden_cases_are_synthetic_and_have_no_personal_data():
    files = loader.iter_ats_files() + loader.iter_rank_files() + loader.iter_fit_files()
    assert files, "expected golden cases to exist"
    for path in files:
        raw = path.read_text(encoding="utf-8")
        case = json.loads(raw)
        assert case.get("synthetic") is True, f"{path.name}: not marked synthetic"
        assert not _EMAIL_RE.search(raw), f"{path.name}: contains an email address"
        low = raw.lower()
        for token in _PII_DENYLIST:
            assert token not in low, f"{path.name}: contains personal identifier {token!r}"


def test_run_evals_returns_zero_when_all_pass():
    assert run_evals.run() == 0


def test_scorecard_reports_every_case():
    results = run_evals.collect_results()
    text = run_evals.format_scorecard(results)
    assert "PASS" in text
    # 8 ATS + 3 rank + N fit cases accounted for.
    expected_total = 8 + 3 + len(loader.iter_fit_files())
    assert len(results) == expected_total
    for res in results:
        assert res["id"] in text
