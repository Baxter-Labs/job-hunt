import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import insights.redflags as rf  # noqa: E402


def _flags(jd):
    return rf.scan_red_flags(jd)


def _by_flag(findings):
    return {f["flag"]: f for f in findings}


# --- shape ---

def test_every_finding_has_exact_keys():
    findings = _flags("Join our fast-paced team of rockstars.")
    assert findings, "expected at least one finding"
    for f in findings:
        assert set(f) == {"flag", "category", "evidence", "severity"}
        assert f["severity"] in {"low", "medium", "high"}
        assert f["category"] in {
            "compensation", "culture", "workload",
            "benefits", "hiring-process", "seniority",
        }


# --- a JD with several flags trips several detectors ---

def test_multi_flag_jd():
    jd = (
        "We are a fast-paced startup and we're like a family. "
        "Looking for a rockstar engineer who can wear many hats. "
        "Competitive salary. Unlimited PTO. This is an unpaid take-home "
        "assignment. Work hard play hard!"
    )
    got = _by_flag(_flags(jd))
    assert "fast-paced" in got and got["fast-paced"]["category"] in {"culture", "workload"}
    assert "family-culture" in got and got["family-culture"]["category"] == "culture"
    assert "rockstar-language" in got
    assert "wear-many-hats" in got and got["wear-many-hats"]["category"] == "workload"
    assert "vague-compensation" in got and got["vague-compensation"]["category"] == "compensation"
    assert "unlimited-pto" in got and got["unlimited-pto"]["category"] == "benefits"
    assert "unpaid-assessment" in got and got["unpaid-assessment"]["severity"] == "high"
    assert "work-hard-play-hard" in got


# --- a clean JD trips nothing ---

def test_clean_jd_has_no_flags():
    jd = (
        "Senior Backend Engineer. Salary range EUR 70,000 to 85,000. "
        "25 days paid holiday. On-call rotation is compensated with an on-call "
        "stipend. We run a structured, paid take-home exercise. 5 years of "
        "experience with Python and PostgreSQL required."
    )
    assert _flags(jd) == []


# --- 'competitive salary' only fires WITHOUT a real figure ---

def test_competitive_salary_with_number_is_not_flagged():
    assert "vague-compensation" not in _by_flag(_flags("Competitive salary of EUR 70,000."))
    assert "vague-compensation" not in _by_flag(_flags("Competitive salary, up to $120k."))


def test_competitive_salary_without_number_is_flagged():
    got = _by_flag(_flags("We offer a competitive salary and great perks."))
    assert "vague-compensation" in got
    assert "competitive salary" in got["vague-compensation"]["evidence"].lower()


# --- on-call only fires when comp is NOT mentioned ---

def test_oncall_without_comp_is_flagged():
    got = _by_flag(_flags("You will join the on-call rotation for production."))
    assert "on-call-uncompensated" in got
    assert got["on-call-uncompensated"]["category"] == "compensation"


def test_oncall_with_comp_is_not_flagged():
    assert "on-call-uncompensated" not in _by_flag(
        _flags("On-call is paid via an on-call stipend."))
    assert "on-call-uncompensated" not in _by_flag(
        _flags("We compensate on-call shifts."))


# --- equity-only ---

def test_equity_only_is_flagged_high():
    got = _by_flag(_flags("Early-stage: compensation is equity-only for now."))
    assert "equity-only-comp" in got and got["equity-only-comp"]["severity"] == "high"


# --- word-boundary correctness: no false positives on substrings ---

def test_word_boundary_no_false_positive():
    # 'ninja' must not match inside 'ninjaneering'; 'guru' not inside 'gurus'? (plural
    # is a real word we DO want) -> use a substring that is NOT a red-flag word.
    assert "rockstar-language" not in _by_flag(_flags("We use the Ninject DI container."))
    # 'family' inside 'family-friendly benefits' is not the 'we are a family' trope.
    assert "family-culture" not in _by_flag(_flags("Family-friendly benefits and parental leave."))


def test_fast_paced_matches_hyphen_and_space():
    assert "fast-paced" in _by_flag(_flags("A fast-paced environment."))
    assert "fast-paced" in _by_flag(_flags("A fast paced environment."))


# --- seniority ---

def test_unrealistic_experience_range_flagged():
    got = _by_flag(_flags("We need 3-12 years of experience."))
    assert "unrealistic-experience-range" in got
    assert got["unrealistic-experience-range"]["category"] == "seniority"


def test_narrow_experience_range_not_flagged():
    assert "unrealistic-experience-range" not in _by_flag(_flags("3-5 years of experience."))


def test_entry_level_with_senior_demand_flagged():
    got = _by_flag(_flags("Junior Developer (graduate) — 6+ years of experience required."))
    assert "entry-level-senior-demand" in got
    assert got["entry-level-senior-demand"]["severity"] == "high"


# --- determinism ---

def test_deterministic_order_and_repeatable():
    jd = "Fast-paced team. Competitive salary. Unlimited PTO."
    a = _flags(jd)
    b = _flags(jd)
    assert a == b
    # order follows detector declaration order (compensation-vague appears before pto)
    flags_in_order = [f["flag"] for f in a]
    assert flags_in_order == sorted(flags_in_order, key=flags_in_order.index)  # stable


# --- Issue 1: family-culture must not fire on GOOD family benefits ---
def test_family_leave_benefit_not_flagged():
    flags = {f["flag"] for f in rf.scan_red_flags(
        "Great benefits including family leave and parental leave.")}
    assert "family-culture" not in flags


def test_family_of_products_not_flagged():
    flags = {f["flag"] for f in rf.scan_red_flags(
        "You will help grow our family of products.")}
    assert "family-culture" not in flags


def test_genuine_family_culture_still_flagged():
    flags = {f["flag"] for f in rf.scan_red_flags(
        "We're like a family here and everyone pitches in after hours.")}
    assert "family-culture" in flags


# --- Issue 2: equity-only must not fire when salary is ALSO offered ---
def test_equity_plus_salary_not_flagged():
    flags = {f["flag"] for f in rf.scan_red_flags(
        "We offer not only equity but also a competitive base salary of 90,000 EUR.")}
    assert "equity-only-comp" not in flags


def test_genuine_equity_only_still_flagged():
    flags = {f["flag"] for f in rf.scan_red_flags(
        "Compensation is equity only for the first year.")}
    assert "equity-only-comp" in flags


# --- Issue 3: entry-level-senior-demand must key off EXPERIENCE, not any year mention ---
def test_junior_with_combined_years_not_flagged():
    flags = {f["flag"] for f in rf.scan_red_flags(
        "Junior Engineer. Join a team with 20 years of combined experience.")}
    assert "entry-level-senior-demand" not in flags


def test_graduate_company_age_not_flagged():
    flags = {f["flag"] for f in rf.scan_red_flags(
        "Graduate role at a company founded 8 years ago.")}
    assert "entry-level-senior-demand" not in flags


def test_genuine_entry_level_senior_demand_still_flagged():
    flags = {f["flag"] for f in rf.scan_red_flags(
        "Entry-level position. Requires 7+ years of experience with distributed systems.")}
    assert "entry-level-senior-demand" in flags


# --- Issue 4: on-call flag must respect negation ---
def test_no_oncall_not_flagged():
    for t in ("This role has no on-call duties.",
              "On-call support is not required for this position."):
        flags = {f["flag"] for f in rf.scan_red_flags(t)}
        assert "on-call-uncompensated" not in flags, t


def test_genuine_uncompensated_oncall_still_flagged():
    flags = {f["flag"] for f in rf.scan_red_flags(
        "You will join an on-call rotation covering nights and weekends.")}
    assert "on-call-uncompensated" in flags


# --- Issue 5 (minor): rockstar-language must not hit tooling/UI terms ---
def test_ninja_buildsystem_and_wizard_not_flagged():
    for t in ("We use the Ninja build system for fast builds.",
              "Users complete an onboarding wizard on first login."):
        flags = {f["flag"] for f in rf.scan_red_flags(t)}
        assert "rockstar-language" not in flags, t


def test_genuine_rockstar_language_still_flagged():
    flags = {f["flag"] for f in rf.scan_red_flags(
        "We're looking for a coding rockstar / ninja to join the team.")}
    assert "rockstar-language" in flags
