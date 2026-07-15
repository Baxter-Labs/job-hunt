import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import insights.analytics as A  # noqa: E402


def _row(company, role, status, source="indeed", work_auth="confirmed"):
    return {"company": company, "role": role, "status": status,
            "source": source, "work_auth_status": work_auth}


def test_overall_funnel_counts_and_rates():
    rows = [
        _row("A", "R", "applied"),
        _row("B", "R", "response"),
        _row("C", "R", "interview"),
        _row("D", "R", "offer"),
        _row("E", "R", "rejected"),   # applied, but not a positive response
        _row("F", "R", "pack_generated"),  # not applied
        _row("G", "R", "not_applied"),     # not applied
    ]
    rep = A.funnel_report(rows)
    o = rep["overall"]
    assert o["total"] == 7
    assert o["applied"] == 5        # applied, response, interview, offer, rejected
    assert o["responses"] == 3      # response, interview, offer
    assert o["interviews"] == 2     # interview, offer
    assert o["offers"] == 1         # offer
    assert o["rejected"] == 1
    assert o["response_rate"] == round(3 / 5, 3)
    assert o["interview_rate"] == round(2 / 5, 3)
    assert o["offer_rate"] == round(1 / 5, 3)


def test_divide_by_zero_rates_are_zero():
    rows = [_row("A", "R", "not_applied"), _row("B", "R", "pack_generated")]
    o = A.funnel_report(rows)["overall"]
    assert o["applied"] == 0
    assert o["response_rate"] == 0
    assert o["interview_rate"] == 0
    assert o["offer_rate"] == 0


def test_empty_rows_report_is_all_zero_no_takeaways():
    rep = A.funnel_report([])
    assert rep["overall"]["total"] == 0
    assert rep["overall"]["applied"] == 0
    assert rep["takeaways"] == []
    assert rep["by_source"] == {}


def test_breakdown_by_source_and_work_auth():
    rows = [
        _row("A", "R", "response", source="indeed", work_auth="confirmed"),
        _row("B", "R", "applied", source="indeed", work_auth="not_found"),
        _row("C", "R", "offer", source="linkedin", work_auth="confirmed"),
    ]
    rep = A.funnel_report(rows)
    assert rep["by_source"]["indeed"]["applied"] == 2
    assert rep["by_source"]["indeed"]["responses"] == 1
    assert rep["by_source"]["linkedin"]["offers"] == 1
    assert rep["by_work_auth"]["confirmed"]["applied"] == 2
    assert rep["by_work_auth"]["not_found"]["applied"] == 1


def test_ats_band_join_uses_pack_lookup():
    rows = [
        _row("Hi", "R", "response"),
        _row("Mid", "R", "applied"),
        _row("Lo", "R", "applied"),
        _row("None", "R", "applied"),
    ]
    scores = {("Hi", "R"): 82, ("Mid", "R"): 55, ("Lo", "R"): 30}

    def lookup(company, role):
        return scores.get((company, role))  # "None" -> None -> unknown band

    rep = A.funnel_report(rows, pack_lookup=lookup)
    assert rep["by_ats_band"]["70+"]["applied"] == 1
    assert rep["by_ats_band"]["70+"]["responses"] == 1
    assert rep["by_ats_band"]["50-69"]["applied"] == 1
    assert rep["by_ats_band"]["<50"]["applied"] == 1
    assert rep["by_ats_band"]["unknown"]["applied"] == 1


def test_small_n_suppresses_takeaways():
    # Only 2 applications in each band -> below min_takeaway_n (3) -> no ATS takeaway.
    rows = [
        _row("H1", "R", "response"), _row("H2", "R", "applied"),
        _row("L1", "R", "applied"), _row("L2", "R", "applied"),
    ]
    scores = {("H1", "R"): 80, ("H2", "R"): 75, ("L1", "R"): 20, ("L2", "R"): 10}
    rep = A.funnel_report(rows, pack_lookup=lambda c, r: scores.get((c, r)))
    assert rep["takeaways"] == []


def test_big_enough_sample_emits_ats_band_takeaway():
    rows = (
        [_row(f"H{i}", "R", "response") for i in range(3)]     # 3x 70+, all responded
        + [_row(f"L{i}", "R", "applied") for i in range(3)]    # 3x <50, none responded
    )
    scores = {}
    for i in range(3):
        scores[(f"H{i}", "R")] = 80
        scores[(f"L{i}", "R")] = 20
    rep = A.funnel_report(rows, pack_lookup=lambda c, r: scores.get((c, r)))
    assert any("70+ ATS band" in t and "<50" in t for t in rep["takeaways"])


def test_band_takeaway_does_not_recommend_high_when_low_converts_better():
    # 3 apps in 70+ band, none responded; 3 apps in <50 band, all responded.
    rows = (
        [_row("Co", f"hi{i}", "applied") for i in range(3)]
        + [_row("Co", f"lo{i}", "response") for i in range(3)]
    )
    scores = {}
    for i in range(3):
        scores[("Co", f"hi{i}")] = 80
        scores[("Co", f"lo{i}")] = 30
    rep = A.funnel_report(rows, pack_lookup=lambda c, r: scores.get((c, r)))
    joined = " ".join(rep["takeaways"]).lower()
    assert "prioritise higher-scoring" not in joined and "prioritize higher-scoring" not in joined


def test_band_takeaway_recommends_high_when_high_converts_better():
    rows = (
        [_row("Co", f"hi{i}", "response") for i in range(3)]
        + [_row("Co", f"lo{i}", "applied") for i in range(3)]
    )
    scores = {}
    for i in range(3):
        scores[("Co", f"hi{i}")] = 80
        scores[("Co", f"lo{i}")] = 30
    rep = A.funnel_report(rows, pack_lookup=lambda c, r: scores.get((c, r)))
    assert any("higher-scoring" in t.lower() for t in rep["takeaways"])


def test_best_source_takeaway_suppressed_on_tie():
    # two sources, equal response rate, >=3 each -> no "send more there".
    rows = (
        [_row("Co", f"a{i}", "response" if i == 0 else "applied", source="indeed")
         for i in range(3)]
        + [_row("Co", f"b{i}", "response" if i == 0 else "applied", source="linkedin")
           for i in range(3)]
    )
    rep = A.funnel_report(rows)
    assert "send more there" not in " ".join(rep["takeaways"]).lower()
