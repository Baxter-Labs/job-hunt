import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import scoring.select as select  # noqa: E402


def _role(company, role, fit):
    return {"company": company, "role": role, "fit_score": fit}


def test_orders_by_fit_desc():
    scored = [_role("B", "x", 40), _role("A", "y", 90), _role("C", "z", 70)]
    out = select.select_top_n(scored, 2)
    assert [r["fit_score"] for r in out] == [90, 70]
    assert [r["company"] for r in out] == ["A", "C"]


def test_tie_break_company_then_role_case_insensitive():
    scored = [_role("beta", "eng", 80), _role("Alpha", "eng", 80),
              _role("Alpha", "dev", 80)]
    out = select.select_top_n(scored, 3)
    # equal fit -> company asc, then role asc, case-insensitively
    assert [(r["company"], r["role"]) for r in out] == [
        ("Alpha", "dev"), ("Alpha", "eng"), ("beta", "eng")]


def test_n_clamped_to_length_and_zero_floor():
    scored = [_role("A", "y", 90), _role("B", "x", 40)]
    assert len(select.select_top_n(scored, 10)) == 2      # clamp high -> len
    assert select.select_top_n(scored, 0) == []           # zero
    assert select.select_top_n(scored, -3) == []          # negative -> 0
    assert select.select_top_n([], 5) == []               # empty input


def test_returns_new_list_does_not_mutate_input():
    scored = [_role("B", "x", 40), _role("A", "y", 90)]
    before = [dict(r) for r in scored]
    out = select.select_top_n(scored, 1)
    assert scored == before          # input untouched (order + contents)
    assert out[0] is not None


def test_deterministic_same_input_same_output():
    scored = [_role("A", "y", 80), _role("B", "x", 80), _role("C", "z", 80)]
    assert select.select_top_n(scored, 3) == select.select_top_n(scored, 3)


def test_missing_fit_score_treated_as_zero_not_crash():
    scored = [{"company": "A", "role": "y"}, _role("B", "x", 50)]
    out = select.select_top_n(scored, 2)
    assert out[0]["company"] == "B"          # the one with a real fit ranks first


def test_scored_shortlist_convenience_matches_select_top_n():
    scored = [_role("B", "x", 40), _role("A", "y", 90)]
    assert select.scored_shortlist(scored, 1) == select.select_top_n(scored, 1)
