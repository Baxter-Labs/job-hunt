"""Deterministic top-N selection of fit-scored roles for the auto-pipeline.

Pure and offline: list-in / list-out, no I/O, no network, no wall-clock. Given
roles each carrying a `fit_score` (and identity fields `company`, `role`), return
the top-N by fit_score descending, with a deterministic tie-break by company then
role (case-insensitive). `n` is clamped to [0, len]. Never mutates the input.

This is the ONLY new Python in Phase D. Selection is a diagnostic ordering step,
never a licence to fabricate: a role's fit_score comes from scoring.fit and is
reported as-is. Roles that later fail the fabrication gate are surfaced as blocked
by the skill, not silently dropped here.
"""

from __future__ import annotations

from typing import Any


def _fit(role: dict[str, Any]) -> int:
    value = role.get("fit_score", 0)
    return value if isinstance(value, int) else 0


def _sort_key(role: dict[str, Any]) -> tuple[int, str, str]:
    # Descending fit -> negate; ascending company then role, case-insensitive.
    return (-_fit(role), str(role.get("company", "")).lower(),
            str(role.get("role", "")).lower())


def select_top_n(scored: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """Top-N fit-scored roles, deterministic. See module docstring for the contract."""
    ordered = sorted(scored, key=_sort_key)
    n = max(0, min(int(n), len(ordered)))
    return ordered[:n]


def scored_shortlist(listings_with_fit: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """Convenience alias: pick the top-N fit-scored listings for the pipeline shortlist."""
    return select_top_n(listings_with_fit, n)
