import csv
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import work_auth as wa  # noqa: E402
import work_auth.nl_ind_hsm as ind  # noqa: E402


def _seed_register(home, rows):
    path = home / "config" / "nl_ind_hsm_sponsors.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["company_name", "careers_url", "category", "last_verified"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def test_normalize_company_strips_dutch_suffixes():
    assert ind.normalize_company("ASML Netherlands B.V.") == "asml"


def test_annotate_confirmed_and_not_found(monkeypatch, tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    _seed_register(home, [
        {"company_name": "ASML", "careers_url": "https://asml.com/careers",
         "category": "highly_skilled_migrant", "last_verified": "2026-07-01"},
        {"company_name": "ING Bank", "careers_url": "", "category": "hsm", "last_verified": ""},
    ])
    prov = wa.get_provider("nl-ind-hsm")
    ann = prov.annotate(["ASML", "ING", "TotallyFakeCo"])
    assert ann["ASML"]["status"] == "confirmed"
    assert ann["ASML"]["careers_url"] == "https://asml.com/careers"
    assert ann["ING"]["status"] in {"confirmed", "possible"}   # token-subset match on "ing"
    assert ann["TotallyFakeCo"]["status"] == "not_found"


def test_gate_keep_flag_drop(monkeypatch, tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    _seed_register(home, [{"company_name": "ASML", "careers_url": "",
                           "category": "hsm", "last_verified": ""}])
    prov = wa.get_provider("nl-ind-hsm")
    assert prov.gate({"work_auth": {"status": "confirmed"}}) == "keep"
    assert prov.gate({"work_auth": {"status": "possible"}}) == "flag"
    assert prov.gate({"work_auth": {"status": "not_found"}}) == "flag"
    strict = wa.get_provider("nl-ind-hsm", drop_unknown=True)
    assert strict.gate({"work_auth": {"status": "not_found"}}) == "drop"


def test_refresh_from_names_is_offline(monkeypatch, tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    prov = wa.get_provider("nl-ind-hsm")
    n = prov.refresh(from_names=["Foobar B.V.", "Baz Holding"])
    assert n == 2
    assert prov.register_path().exists()
    # A refreshed sponsor now annotates as confirmed/possible, fully offline.
    assert prov.annotate(["Foobar"])["Foobar"]["status"] in {"confirmed", "possible"}


def test_refresh_uses_injected_fetch_not_network(monkeypatch, tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    prov = wa.get_provider("nl-ind-hsm")
    calls = {"n": 0}

    def fake_fetch():
        calls["n"] += 1
        return ["Injected Sponsor N.V.", "Another Sponsor"]

    n = prov.refresh(fetch=fake_fetch)  # no from_names/from_file -> uses fetch
    assert n == 2 and calls["n"] == 1
    assert prov.annotate(["Injected Sponsor"])["Injected Sponsor"]["status"] in {"confirmed", "possible"}


def test_missing_register_annotates_not_found(monkeypatch, tmp_path):
    home = tmp_path / "ws"; home.mkdir()
    monkeypatch.setenv("JOB_HUNT_HOME", str(home))
    prov = wa.get_provider("nl-ind-hsm")   # no register seeded
    assert prov.load_sponsors() == []
    assert prov.annotate(["ASML"])["ASML"]["status"] == "not_found"
