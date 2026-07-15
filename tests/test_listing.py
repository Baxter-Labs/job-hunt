import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import search.listing as L  # noqa: E402


def test_slugify_matches_pack_convention():
    assert L.slugify("Booking.com") == "booking-com"
    assert L.slugify("Data Scientist") == "data-scientist"
    assert L.slugify("!!!") == "untitled"


def test_pack_slug():
    assert L.pack_slug("Acme", "Backend Engineer") == "acme-backend-engineer"


def test_normalize_fills_canonical_fields():
    out = L.normalize_listing({"company": " ASML ", "role": "AI Engineer"})
    for key in L.CANONICAL_FIELDS:
        assert key in out
    assert out["company"] == "ASML"          # stripped
    assert out["source"] == ""               # missing -> ""
    assert out["job_id"] == ""


def test_normalize_preserves_extra_keys_and_coerces_str():
    out = L.normalize_listing({"company": "ING", "role": "ML Engineer",
                               "job_id": 12345, "apply_confidence": 0.9})
    assert out["job_id"] == "12345"          # coerced to str
    assert out["apply_confidence"] == 0.9    # extra key preserved verbatim


def test_normalize_listings_batch():
    out = L.normalize_listings([{"company": "A", "role": "X"},
                                {"company": "B", "role": "Y"}])
    assert [o["company"] for o in out] == ["A", "B"]
