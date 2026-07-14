from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROMPTS = REPO / "plugins" / "job-hunt" / "scripts" / "tailor" / "prompts"


def test_prompt_files_present_and_nonempty():
    for name in ("recruiter_persona.md", "humanizer_rules.md", "tailor_prompt_template.md"):
        p = PROMPTS / name
        assert p.exists(), f"missing {p}"
        assert p.stat().st_size > 0


def test_template_has_all_six_placeholders():
    text = (PROMPTS / "tailor_prompt_template.md").read_text(encoding="utf-8")
    for token in ("{PERSONA}", "{HUMANIZER_RULES}", "{MASTER_CV_JSON}",
                  "{JOB_DESCRIPTION}", "{COMPANY}", "{ROLE}"):
        assert token in text, f"template missing {token}"


def test_humanizer_has_machine_scannable_ban_list():
    text = (PROMPTS / "humanizer_rules.md").read_text(encoding="utf-8").lower()
    for banned in ("leverage", "delve", "robust", "seamless", "underscore"):
        assert f"`{banned}`" in text, f"ban-list missing {banned}"


def test_no_personal_data_in_prompts():
    blob = "".join((PROMPTS / n).read_text(encoding="utf-8")
                   for n in ("recruiter_persona.md", "humanizer_rules.md", "tailor_prompt_template.md"))
    assert "dantepk" not in blob
    assert "Eshwar" not in blob
