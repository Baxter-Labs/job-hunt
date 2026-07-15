import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import scoring.fit as fit  # noqa: E402


def _master(**over):
    base = {
        "summary": "Senior backend engineer building Python services on AWS.",
        "skills": [
            {"name": "Python", "category": "Programming", "level": None},
            {"name": "SQL", "category": "Data", "level": None},
            {"name": "Docker", "category": "DevOps", "level": None},
            {"name": "Kubernetes", "category": "DevOps", "level": None},
        ],
        "experience": [
            {"company": "Northwind BV", "title": "Senior Backend Engineer",
             "location": "Amsterdam", "dates": "Jan 2019 – Dec 2024",
             "bullets": ["Built Python microservices with Docker and Kubernetes.",
                         "Designed REST APIs deployed on AWS."]},
        ],
    }
    base.update(over)
    return base


STRONG_JD = ("Senior Backend Engineer. Python, SQL, Docker, Kubernetes, REST APIs and AWS. "
             "Design and run microservices in production.")


def test_shape_and_ranges():
    r = fit.fit_report(_master(), STRONG_JD)
    assert set(r) == {"fit_score", "components", "reasons"}
    assert set(r["components"]) == {"skills", "experience", "seniority"}
    for v in (r["fit_score"], *r["components"].values()):
        assert isinstance(v, int) and 0 <= v <= 100
    assert isinstance(r["reasons"], list) and all(isinstance(s, str) for s in r["reasons"])


def test_deterministic():
    assert fit.fit_report(_master(), STRONG_JD) == fit.fit_report(_master(), STRONG_JD)


def test_strong_fit_high_score_and_aligned_seniority():
    r = fit.fit_report(_master(), STRONG_JD)
    assert r["components"]["skills"] >= 70
    assert r["components"]["seniority"] == 100          # senior vs senior, distance 0
    assert r["fit_score"] >= 70
    assert any(s.startswith("Skills match:") for s in r["reasons"])
    assert any("aligned" in s for s in r["reasons"])


def test_weighting_is_exact_blend():
    r = fit.fit_report(_master(), STRONG_JD)
    c = r["components"]
    expected = round(0.5 * c["skills"] + 0.3 * c["experience"] + 0.2 * c["seniority"])
    assert r["fit_score"] == expected


def test_skills_reuses_ats_keyword_coverage():
    # A JD keyword the master genuinely lacks lowers skills and shows up as a gap,
    # and is NEVER silently added (honesty).
    jd = "Backend Engineer. Python and Rust required."
    r = fit.fit_report(_master(), jd)          # master has no Rust
    assert any("rust" in s.lower() for s in r["reasons"] if s.startswith("Top skill gaps:"))
    assert r["components"]["skills"] < 100


def test_seniority_mismatch_penalised_and_explained():
    jr = _master(experience=[{"company": "Acme BV", "title": "Junior ML Engineer",
                              "dates": "Jan 2023 – Dec 2024",
                              "bullets": ["Trained models in PyTorch and Python."]}],
                 summary="Junior ML engineer.")
    jd = "Principal Machine Learning Engineer. Python, PyTorch, deep learning at scale."
    r = fit.fit_report(jr, jd)
    # junior(1) vs principal(6) → distance 5 → clamped 20
    assert r["components"]["seniority"] == 20
    assert any("level" in s and "up" in s for s in r["reasons"] if s.startswith("Seniority:"))


def test_ambiguous_seniority_is_neutral_70():
    m = _master(experience=[{"company": "Acme BV", "title": "Engineer",
                             "dates": "Present", "bullets": ["Wrote Python."]}],
                summary="Engineer.")
    jd = "Engineer. Python and SQL."                 # no seniority cue in JD or title/years
    assert fit.fit_report(m, jd)["components"]["seniority"] == 70


def test_empty_jd_scores_zero_skills_not_crash():
    r = fit.fit_report(_master(), "")
    assert r["components"]["skills"] == 0
    assert isinstance(r["fit_score"], int)


def test_no_experience_is_neutral_seniority_and_zero_experience():
    m = {"summary": "", "skills": [{"name": "Python"}], "experience": []}
    r = fit.fit_report(m, "Python developer.")
    assert r["components"]["experience"] == 0
    assert r["components"]["seniority"] == 70


def test_master_above_ask_direction():
    jd = "Junior Backend Engineer. Python and SQL."
    r = fit.fit_report(_master(), jd)                # senior(3) vs junior(1) → distance 2 → 60
    assert r["components"]["seniority"] == 60
    assert any("above the ask" in s for s in r["reasons"])


_SENIOR_MASTER = {
    "summary": "Backend engineer.",
    "skills": [{"name": "Python", "category": "Programming", "level": None},
               {"name": "SQL", "category": "Data", "level": None}],
    "experience": [{"company": "Acme", "title": "Senior Backend Engineer",
                    "location": "Remote", "dates": "2018 – 2024",
                    "bullets": ["Built and ran production services."]}],
}


def test_jd_body_verbs_do_not_change_seniority():
    # 'lead'/'staff' as prose verbs/nouns in the JD BODY must not inflate the target level.
    clean = fit.fit_report(_SENIOR_MASTER, "Senior Backend Engineer\nPython and SQL required.")
    noisy = fit.fit_report(_SENIOR_MASTER,
        "Senior Backend Engineer\nYou will lead the design of microservices and manage a "
        "staff of engineers. Python and SQL.")
    assert clean["components"]["seniority"] == noisy["components"]["seniority"] == 100


def test_clean_title_seniority_mismatch_still_detected():
    # A genuinely higher title in the JD's first line is still detected as a mismatch.
    r = fit.fit_report(_SENIOR_MASTER, "Principal Backend Engineer\nPython and SQL.")
    assert r["components"]["seniority"] < 100
    assert any("principal" in reason.lower() for reason in r["reasons"])


def test_master_compound_title_not_read_as_lead():
    # 'Lead Generation Specialist' must NOT be read as seniority level 'lead'.
    master = {"summary": "Marketing.",
              "skills": [{"name": "SEO", "category": "Marketing", "level": None}],
              "experience": [{"company": "Acme", "title": "Lead Generation Specialist",
                              "location": "Remote", "dates": "2020 – 2024",
                              "bullets": ["Ran demand-gen campaigns."]}]}
    r = fit.fit_report(master, "Senior Marketing Manager\nSEO and campaigns.")
    assert "above the ask" not in " ".join(r["reasons"]).lower()
    assert "level(s) up" not in " ".join(r["reasons"]).lower() or r["components"]["seniority"] >= 60
