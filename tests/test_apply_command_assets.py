from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugins" / "job-hunt"


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{path} missing frontmatter"
    end = text.index("---", 3)
    fields = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields


def test_command_frontmatter():
    fields = _frontmatter(PLUGIN / "commands" / "job-apply.md")
    assert "description" in fields


def test_skill_frontmatter():
    fields = _frontmatter(PLUGIN / "skills" / "job-apply" / "SKILL.md")
    assert fields.get("name") == "job-apply"
    assert "description" in fields


def test_skill_uses_plugin_root_not_absolute_paths():
    text = (PLUGIN / "skills" / "job-apply" / "SKILL.md").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" in text
    assert "/Users/dantepk" not in text


def test_no_personal_data():
    blob = ((PLUGIN / "commands" / "job-apply.md").read_text(encoding="utf-8")
            + (PLUGIN / "skills" / "job-apply" / "SKILL.md").read_text(encoding="utf-8"))
    assert "Eshwar" not in blob and "dantepk" not in blob


def test_skill_states_safety_and_ats_first():
    text = (PLUGIN / "skills" / "job-apply" / "SKILL.md").read_text(encoding="utf-8")
    low = text.lower()
    # ATS shown before applying.
    assert "ats" in low and ("before" in low)
    # Explicit stop-conditions incl. CAPTCHA/login/consent.
    assert "captcha" in low and "login" in low and "consent" in low
    assert "stop" in low or "halt" in low
    # Never store/type passwords.
    assert "password" in low and "never" in low
    # Playwright-driven (skill), auto-submit is opt-in.
    assert "playwright" in low
    assert "auto_submit_simple_forms" in text
    # Drives the CLI.
    assert "apply.apply_cli" in text and "preapply" in text
