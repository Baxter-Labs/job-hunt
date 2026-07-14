import sys
from pathlib import Path

MODdir = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(MODdir))

import engine.profile as prof  # noqa: E402


def _valid_profile():
    p = prof.default_profile()
    p["contact"]["name"] = "Ada Lovelace"
    p["contact"]["email"] = "ada@example.com"
    p["target_locations"] = ["Netherlands"]
    p["platforms"] = ["indeed", "career_pages"]
    p["work_auth"] = {"needs_sponsorship": True, "scheme": "nl-ind-hsm"}
    return p


def test_default_profile_is_valid_shape():
    p = prof.default_profile()
    assert "contact" in p and "platforms" in p and "work_auth" in p
    assert p["apply_prefs"]["auto_submit_simple_forms"] is False


def test_validate_accepts_good_profile():
    assert prof.validate_profile(_valid_profile()) == []


def test_validate_rejects_unknown_platform():
    p = _valid_profile()
    p["platforms"] = ["indeed", "monster"]
    issues = prof.validate_profile(p)
    assert any("monster" in i for i in issues)


def test_validate_rejects_unknown_scheme():
    p = _valid_profile()
    p["work_auth"]["scheme"] = "h1b"
    issues = prof.validate_profile(p)
    assert any("scheme" in i for i in issues)


def test_validate_requires_name_and_email():
    p = _valid_profile()
    p["contact"]["name"] = ""
    p["contact"]["email"] = ""
    issues = prof.validate_profile(p)
    assert any("name" in i for i in issues)
    assert any("email" in i for i in issues)


def test_validate_requires_at_least_one_platform():
    p = _valid_profile()
    p["platforms"] = []
    issues = prof.validate_profile(p)
    assert any("platform" in i for i in issues)


def test_validate_rejects_wrong_schema_version():
    p = _valid_profile()
    p["schema_version"] = "2.0"
    assert any("schema_version" in i for i in prof.validate_profile(p))


def test_validate_rejects_non_list_target_locations():
    p = _valid_profile()
    p["target_locations"] = "Netherlands"
    assert any("target_locations" in i for i in prof.validate_profile(p))


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "profile.json"
    p = _valid_profile()
    prof.save_profile(p, path)
    loaded = prof.load_profile(path)
    assert loaded["contact"]["name"] == "Ada Lovelace"
