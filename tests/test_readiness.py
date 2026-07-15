import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import scoring.readiness as readiness  # noqa: E402


MASTER = {
    "contact": {"name": "Ada Placeholder", "email": "ada@example.com"},
    "summary": "Senior backend engineer building Python microservices on AWS.",
    "skills": [{"name": "Python"}, {"name": "SQL"}, {"name": "Docker"},
               {"name": "Kubernetes"}, {"name": "AWS"}],
    "experience": [{"company": "Northwind BV", "title": "Senior Backend Engineer",
                    "dates": "Jan 2019 – Dec 2024",
                    "bullets": ["Built Python microservices with Docker and Kubernetes.",
                                "Designed REST APIs deployed on AWS."]}],
}

STRONG_JD = ("Senior Backend Engineer. Python, SQL, Docker, Kubernetes, REST APIs and AWS. "
             "Design and run microservices in production.")


def _tailored(*, passed=True, name="Ada Placeholder", email="ada@example.com",
              skills=("Python", "SQL", "Docker"), bullets=("Built Python services with Docker.",)):
    return {
        "schema_version": "1.0",
        "contact": {"name": name, "title": "Backend Engineer", "email": email,
                    "phone": None, "location": None, "links": [], "work_authorization": None},
        "summary": "Backend engineer.",
        "skills_grouped": [{"group": "Core", "skills": list(skills)}],
        "experience": [{"company": "Northwind BV", "title": "Senior Backend Engineer",
                        "dates": "Jan 2019 – Dec 2024", "bullets": list(bullets)}],
        "highlights": [], "ats_keywords_used": [],
        "fabrication_check": {"passed": passed, "issues": [] if passed else ["fabricated X"]},
    }


def _seed_pack(root, *, ats_score=72, tailored=None, cv=True, cover=True):
    pack = root / "northwind-bv-backend-engineer"
    pack.mkdir(parents=True)
    (pack / "ats_report.json").write_text(json.dumps({
        "company": "Northwind BV", "role": "Backend Engineer",
        "total_keywords": 10, "matched_count": 7, "missing_count": 3,
        "match_score": ats_score,
        "matched_keywords": ["python", "sql", "docker"],
        "missing_keywords": ["kubernetes", "terraform", "graphql"],
    }), encoding="utf-8")
    if tailored is not None:
        (pack / "tailored_cv.json").write_text(json.dumps(tailored), encoding="utf-8")
    if cv:
        (pack / "cv.pdf").write_text("%PDF fake", encoding="utf-8")
    if cover:
        (pack / "cover_letter.pdf").write_text("%PDF fake", encoding="utf-8")
    return pack


def test_shape_and_ranges(tmp_path):
    pack = _seed_pack(tmp_path, tailored=_tailored())
    r = readiness.readiness_report(pack, MASTER, STRONG_JD)
    assert set(r) == {"readiness_score", "factors", "suggestions", "blocking"}
    assert isinstance(r["readiness_score"], int) and 0 <= r["readiness_score"] <= 100
    assert isinstance(r["blocking"], bool)
    assert isinstance(r["suggestions"], list) and all(isinstance(s, str) for s in r["suggestions"])
    names = {f["name"] for f in r["factors"]}
    assert "Fit" in names and "Completeness" in names and "ATS match" in names
    for f in r["factors"]:
        assert set(f) == {"name", "status", "detail"}
        assert f["status"] in ("pass", "warn", "fail")


def test_deterministic(tmp_path):
    pack = _seed_pack(tmp_path, tailored=_tailored())
    assert (readiness.readiness_report(pack, MASTER, STRONG_JD)
            == readiness.readiness_report(pack, MASTER, STRONG_JD))


def test_fabrication_is_a_hard_gate(tmp_path):
    # passed == False → blocking True, score capped at 0, leading fail factor.
    pack = _seed_pack(tmp_path, ats_score=95, tailored=_tailored(passed=False))
    r = readiness.readiness_report(pack, MASTER, STRONG_JD)
    assert r["blocking"] is True
    assert r["readiness_score"] == 0            # capped even though ATS is 95
    assert r["factors"][0]["name"] == "Fabrication check must pass"
    assert r["factors"][0]["status"] == "fail"


def test_clean_pack_not_blocking_and_fabrication_passes(tmp_path):
    pack = _seed_pack(tmp_path, tailored=_tailored(passed=True))
    r = readiness.readiness_report(pack, MASTER, STRONG_JD)
    assert r["blocking"] is False
    assert r["factors"][0]["name"] == "Fabrication check"
    assert r["factors"][0]["status"] == "pass"
    assert r["readiness_score"] > 0


def test_weighting_is_exact_blend(tmp_path):
    # Reconstruct the blend from the sub-scores exposed via the factors/details.
    pack = _seed_pack(tmp_path, ats_score=72, tailored=_tailored())
    r = readiness.readiness_report(pack, MASTER, STRONG_JD)
    ats_sub = 72
    fit_sub = readiness.fit.fit_report(MASTER, STRONG_JD)["fit_score"]
    comp_sub = 100                              # cv + cover + contact all present
    flags = readiness.redflags.scan_red_flags(STRONG_JD)
    penalty = sum({"high": 25, "medium": 10, "low": 5}[f["severity"]] for f in flags)
    rf_sub = max(0, 100 - penalty)
    expected = round(0.35*ats_sub + 0.25*fit_sub + 0.25*comp_sub + 0.15*rf_sub)
    assert r["readiness_score"] == expected


def test_suggestion_has_but_unsurfaced_says_re_tailor_not_upskill(tmp_path):
    # Master HAS Kubernetes; JD wants it; the tailored CV omits it → "surface", NOT upskill.
    tailored = _tailored(skills=("Python", "SQL", "Docker"),
                         bullets=("Built Python services with Docker.",))  # no kubernetes
    pack = _seed_pack(tmp_path, tailored=tailored)
    r = readiness.readiness_report(pack, MASTER, STRONG_JD)
    surface = [s for s in r["suggestions"] if s.startswith("Re-tailor to surface:")]
    assert surface, r["suggestions"]
    assert "kubernetes" in surface[0].lower()
    # The anti-fabrication guarantee: a keyword the user HAS is never routed to upskill.
    learn = " ".join(s for s in r["suggestions"] if s.startswith("Learn-gap:")).lower()
    assert "kubernetes" not in learn


def test_suggestion_genuinely_lacks_routes_to_upskill_never_add(tmp_path):
    jd = "Backend Engineer. Python, SQL and Rust required."   # master has no Rust
    tailored = _tailored(skills=("Python", "SQL"), bullets=("Built Python and SQL services.",))
    pack = _seed_pack(tmp_path, tailored=tailored)
    r = readiness.readiness_report(pack, MASTER, jd)
    learn = [s for s in r["suggestions"] if s.startswith("Learn-gap:")]
    assert learn and "rust" in learn[0].lower()
    assert "/job-upskill" in learn[0]
    assert "do not add" in learn[0].lower()
    # Rust must NOT be offered as a "surface" suggestion — the user genuinely lacks it.
    surface = " ".join(s for s in r["suggestions"] if s.startswith("Re-tailor to surface:")).lower()
    assert "rust" not in surface


def test_missing_cover_letter_and_contact_produce_concrete_fixes(tmp_path):
    tailored = _tailored(name="", email="")                    # incomplete contact
    pack = _seed_pack(tmp_path, tailored=tailored, cover=False) # no cover letter
    r = readiness.readiness_report(pack, MASTER, STRONG_JD)
    blob = " ".join(r["suggestions"]).lower()
    assert "cover letter" in blob
    assert "contact" in blob
    comp = [f for f in r["factors"] if f["name"] == "Completeness"][0]
    assert comp["status"] in ("warn", "fail")


def test_missing_ats_report_is_fail_factor(tmp_path):
    pack = tmp_path / "empty-pack"
    pack.mkdir()
    r = readiness.readiness_report(pack, MASTER, STRONG_JD)
    ats_factor = [f for f in r["factors"] if f["name"] == "ATS match"][0]
    assert ats_factor["status"] == "fail"


def test_redflag_factor_is_labelled_advisory_and_weighted_light(tmp_path):
    jd = STRONG_JD + " We are like a family and work hard, play hard. Competitive salary."
    pack = _seed_pack(tmp_path, tailored=_tailored())
    r = readiness.readiness_report(pack, MASTER, jd)
    rf = [f for f in r["factors"] if f["name"].startswith("Red flags")][0]
    assert "advisory" in rf["name"].lower()
    assert "about the job" in rf["detail"].lower()


def test_write_readiness_report_roundtrips(tmp_path):
    pack = _seed_pack(tmp_path, tailored=_tailored())
    r = readiness.readiness_report(pack, MASTER, STRONG_JD)
    path = readiness.write_readiness_report(r, pack)
    assert path == pack / "readiness.json"
    assert json.loads(path.read_text(encoding="utf-8")) == r
