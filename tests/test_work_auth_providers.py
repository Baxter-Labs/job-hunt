import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import work_auth as wa  # noqa: E402


def test_none_provider_keeps_everything():
    prov = wa.get_provider("none")
    ann = prov.annotate(["Acme", "ING"])
    assert ann["Acme"]["status"] == "n/a"
    listing = {"company": "Acme", "work_auth": ann["Acme"]}
    assert prov.gate(listing) == "keep"


def test_eu_blue_card_is_flag_only():
    prov = wa.get_provider("eu-blue-card")
    ann = prov.annotate(["Acme"])
    assert ann["Acme"]["status"] == "flag"
    assert "note" in ann["Acme"]
    assert prov.gate({"company": "Acme", "work_auth": ann["Acme"]}) == "flag"


def test_annotate_dedups_company_list():
    prov = wa.get_provider("none")
    ann = prov.annotate(["Acme", "acme", "Acme"])
    # keyed by the exact input strings; dedup means we don't crash on repeats
    assert "Acme" in ann


def test_gate_returns_only_valid_values():
    for scheme in ("none", "eu-blue-card"):
        prov = wa.get_provider(scheme)
        ann = prov.annotate(["X"])
        assert prov.gate({"company": "X", "work_auth": ann["X"]}) in {"keep", "flag", "drop"}


def test_unknown_scheme_raises():
    import pytest
    with pytest.raises(ValueError):
        wa.get_provider("h1b")
