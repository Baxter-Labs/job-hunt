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
    assert "description" in _frontmatter(PLUGIN / "commands" / "job-followup.md")


def test_skill_frontmatter():
    fields = _frontmatter(PLUGIN / "skills" / "job-followup" / "SKILL.md")
    assert fields.get("name") == "job-followup"
    assert "description" in fields


def test_skill_uses_plugin_root_not_absolute_paths():
    text = (PLUGIN / "skills" / "job-followup" / "SKILL.md").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" in text
    assert "/Users/dantepk" not in text


def test_no_personal_data():
    blob = ((PLUGIN / "commands" / "job-followup.md").read_text(encoding="utf-8")
            + (PLUGIN / "skills" / "job-followup" / "SKILL.md").read_text(encoding="utf-8"))
    assert "Eshwar" not in blob and "dantepk" not in blob


def test_skill_invokes_cli_and_never_sends():
    text = (PLUGIN / "skills" / "job-followup" / "SKILL.md").read_text(encoding="utf-8")
    assert "insights.insights_cli" in text
    assert "followup-context" in text
    low = text.lower()
    # BINDING: drafts only, never sends; the user reviews and sends.
    assert "draft" in low
    assert "never send" in low or "does not send" in low or "not send" in low
    assert "review" in low
