import sys
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import search.rank as R  # noqa: E402

TODAY = date(2026, 7, 15)


def test_sponsorship_score_mapping():
    assert R.sponsorship_score("confirmed") == 3
    assert R.sponsorship_score("possible") == 2
    assert R.sponsorship_score("not_found") == 1
    assert R.sponsorship_score("n/a") == 2
    assert R.sponsorship_score("weird") == 2   # unknown -> neutral


def test_recency_buckets():
    assert R.recency_score("2026-07-12", today=TODAY) == 2   # 3 days
    assert R.recency_score("2026-07-01", today=TODAY) == 1   # 14 days
    assert R.recency_score("2026-05-01", today=TODAY) == 0   # old
    assert R.recency_score("", today=TODAY) == 0             # unknown
    assert R.recency_score("not-a-date", today=TODAY) == 0   # unparseable


def test_level_score():
    assert R.level_score("Senior ML Engineer", ["senior", "lead"]) == 1
    assert R.level_score("Junior Analyst", ["senior", "lead"]) == 0
    assert R.level_score("Anything", []) == 1   # no target -> neutral


def test_rank_score_formula():
    listing = {"role": "Senior Engineer", "posted_date": "2026-07-12",
               "work_auth": {"status": "confirmed"}}
    # 3*100 + 2*10 + 1 = 321
    assert R.rank_score(listing, target_levels=["senior"], today=TODAY) == 321


def test_rank_listings_orders_by_score_then_name():
    listings = [
        {"company": "Zeta", "role": "Engineer", "posted_date": "",
         "work_auth": {"status": "not_found"}},
        {"company": "Alpha", "role": "Engineer", "posted_date": "2026-07-14",
         "work_auth": {"status": "confirmed"}},
        {"company": "Beta", "role": "Engineer", "posted_date": "2026-07-14",
         "work_auth": {"status": "confirmed"}},
    ]
    ranked = R.rank_listings(listings, today=TODAY)
    # Alpha & Beta (confirmed, recent) rank above Zeta; tie broken by company asc.
    assert [l["company"] for l in ranked] == ["Alpha", "Beta", "Zeta"]
    assert all("rank_score" in l for l in ranked)
    assert ranked[0]["rank_score"] >= ranked[-1]["rank_score"]


def test_rank_listings_is_pure():
    original = [{"company": "A", "role": "R", "posted_date": "",
                 "work_auth": {"status": "n/a"}}]
    R.rank_listings(original, today=TODAY)
    assert "rank_score" not in original[0]   # input not mutated
