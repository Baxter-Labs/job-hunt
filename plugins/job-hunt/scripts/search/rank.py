"""Deterministic ranking for discovered listings.

The score is documented and reproducible — no ML, no randomness:

    rank_score = sponsorship_score*100 + recency_score*10 + level_score

  * sponsorship_score : work-auth certainty from the provider's status
        confirmed=3, possible/flag/n-a=2 (neutral), not_found=1
  * recency_score     : how fresh the posting is
        <=7 days=2, <=30 days=1, older/unknown/unparseable=0
  * level_score       : match against the user's target seniority
        1 if a target token appears in the role (or no target given), else 0

Listings sort by rank_score desc, then company asc, role asc. Ranking never drops
or fabricates a listing; it only orders what search already found and filtered.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional, Sequence

SPONSORSHIP_SCORE: dict[str, int] = {
    "confirmed": 3,
    "possible": 2,
    "flag": 2,
    "n/a": 2,
    "not_found": 1,
}


def sponsorship_score(status: str) -> int:
    return SPONSORSHIP_SCORE.get(status, 2)


def recency_score(posted_date: str, *, today: Optional[date] = None) -> int:
    if not posted_date:
        return 0
    try:
        posted = date.fromisoformat(posted_date.strip())
    except (ValueError, AttributeError):
        return 0
    ref = today or date.today()
    days = (ref - posted).days
    if days < 0:
        return 0
    if days <= 7:
        return 2
    if days <= 30:
        return 1
    return 0


def level_score(role: str, target_levels: Sequence[str]) -> int:
    if not target_levels:
        return 1  # neutral: no preference expressed
    role_l = (role or "").lower()
    return 1 if any(str(t).lower() in role_l for t in target_levels) else 0


def rank_score(
    listing: dict[str, Any],
    *,
    target_levels: Sequence[str] = (),
    today: Optional[date] = None,
) -> int:
    status = (listing.get("work_auth") or {}).get("status", "n/a")
    s = sponsorship_score(status)
    r = recency_score(listing.get("posted_date", ""), today=today)
    lv = level_score(listing.get("role", ""), target_levels)
    return s * 100 + r * 10 + lv


def rank_listings(
    listings: list[dict[str, Any]],
    *,
    target_levels: Sequence[str] = (),
    today: Optional[date] = None,
) -> list[dict[str, Any]]:
    """Return a new, ranked list; each item gets an added `rank_score`. Pure."""
    scored = []
    for listing in listings:
        item = dict(listing)
        item["rank_score"] = rank_score(item, target_levels=target_levels, today=today)
        scored.append(item)
    scored.sort(key=lambda l: (-l["rank_score"],
                               l.get("company", "").lower(),
                               l.get("role", "").lower()))
    return scored
