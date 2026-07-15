"""Evaluate one ranking golden case against the REAL search.rank ranker.

Never reimplements ranking — imports search.rank and calls rank_listings
exactly as the plugin does. Recency is deterministic: the case pins `today`.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

_SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import search.rank as rank  # noqa: E402


def _today(case: dict[str, Any]) -> Optional[date]:
    raw = case.get("today")
    return date.fromisoformat(raw) if raw else None


def evaluate_rank_case(case: dict[str, Any]) -> dict[str, Any]:
    ranked = rank.rank_listings(
        case["listings"],
        target_levels=case.get("target_levels", ()),
        today=_today(case),
    )
    order = [item.get("id") for item in ranked]
    expected = case["expect"]["order"]
    failures: list[str] = []
    if order != expected:
        failures.append(f"ranked order {order} != expected {expected}")
    return {
        "id": case["id"],
        "kind": "rank",
        "source": case.get("_source", case["id"]),
        "passed": not failures,
        "failures": failures,
        "order": order,
    }
