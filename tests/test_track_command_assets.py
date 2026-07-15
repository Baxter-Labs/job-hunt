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
    assert "description" in _frontmatter(PLUGIN / "commands" / "job-track.md")


def test_skill_frontmatter():
    fields = _frontmatter(PLUGIN / "skills" / "job-track" / "SKILL.md")
    assert fields.get("name") == "job-track"
    assert "description" in fields


def test_skill_uses_plugin_root_not_absolute_paths():
    text = (PLUGIN / "skills" / "job-track" / "SKILL.md").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" in text
    assert "/Users/dantepk" not in text


def test_no_personal_data():
    blob = ((PLUGIN / "commands" / "job-track.md").read_text(encoding="utf-8")
            + (PLUGIN / "skills" / "job-track" / "SKILL.md").read_text(encoding="utf-8"))
    assert "Eshwar" not in blob and "dantepk" not in blob


def test_skill_default_is_text_summary_dashboard_is_optional():
    text = (PLUGIN / "skills" / "job-track" / "SKILL.md").read_text(encoding="utf-8")
    low = text.lower()
    # Default text summary path needs no Flask; dashboard is the opt-in sub-action.
    assert "summary" in low
    assert "dashboard" in low
    assert "flask" in low and "optional" in low
    # It reuses the tracker summarize path via the CLI.
    assert "search.search_cli status" in text or "summarize" in low
    # Dashboard launch references the ported app module.
    assert "dashboard.app" in text
