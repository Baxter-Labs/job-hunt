"""Normalized JobListing schema + shared slug helpers.

A JobListing is a plain dict with a fixed set of canonical keys. Claude collects
raw listing dicts from whatever platform tools the user's profile selected (Indeed
MCP, LinkedIn scraper MCP, Playwright on Naukri/career pages/greenhouse) and hands
them here for canonicalisation before the deterministic engine annotates, filters,
dedupes and ranks them. Nothing here touches the network.
"""

from __future__ import annotations

import re
from typing import Any

CANONICAL_FIELDS: tuple[str, ...] = (
    "source",       # platform key, one of profile.platforms
    "company",
    "role",
    "location",
    "url",          # apply / listing URL
    "job_id",       # platform job id (stable where available)
    "posted_date",  # "" or ISO YYYY-MM-DD
    "level",        # optional seniority hint, e.g. "senior"
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lowercase, collapse non-alphanumerics to single hyphens, strip ends.

    Ported from scripts/job_pipeline.py's slugify; returns "untitled" on empty so
    it matches the Phase-2 tailor.pipeline.slugify contract (pack dirs must line
    up between search dedupe and tailor output)."""
    value = (value or "").strip().lower()
    value = _SLUG_RE.sub("-", value).strip("-")
    return value or "untitled"


def pack_slug(company: str, role: str) -> str:
    """The `<company>-<role>` slug used for output pack dirs (Phase-2 convention)."""
    return f"{slugify(company)}-{slugify(role)}"


def normalize_listing(raw: dict[str, Any]) -> dict[str, Any]:
    """Canonicalise one raw listing dict: ensure every canonical key exists
    (default ""), string-coerce and strip canonical string fields, and preserve
    any extra keys the caller included."""
    if not isinstance(raw, dict):
        raise ValueError(f"listing must be a dict, got {type(raw).__name__}")
    out: dict[str, Any] = dict(raw)  # preserve extras
    for key in CANONICAL_FIELDS:
        val = out.get(key, "")
        if val is None:
            val = ""
        out[key] = str(val).strip() if not isinstance(val, str) else val.strip()
    return out


def normalize_listings(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Canonicalise a list of raw listings."""
    return [normalize_listing(item) for item in raw]
