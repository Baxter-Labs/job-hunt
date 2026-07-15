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
    fields = _frontmatter(PLUGIN / "commands" / "job-search.md")
    assert "description" in fields


def test_skill_frontmatter():
    fields = _frontmatter(PLUGIN / "skills" / "job-search" / "SKILL.md")
    assert fields.get("name") == "job-search"
    assert "description" in fields


def test_skill_uses_plugin_root_not_absolute_paths():
    text = (PLUGIN / "skills" / "job-search" / "SKILL.md").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" in text
    assert "/Users/dantepk" not in text


def test_no_personal_data_in_command_or_skill():
    blob = ((PLUGIN / "commands" / "job-search.md").read_text(encoding="utf-8")
            + (PLUGIN / "skills" / "job-search" / "SKILL.md").read_text(encoding="utf-8"))
    assert "Eshwar" not in blob
    assert "dantepk" not in blob


def test_skill_hands_off_to_tailor_and_uses_cli():
    text = (PLUGIN / "skills" / "job-search" / "SKILL.md").read_text(encoding="utf-8")
    assert "/job-tailor" in text
    assert "search.search_cli" in text
    assert "filter-dedupe-rank" in text


def test_skill_is_profile_driven_and_skips_missing_tools():
    text = (PLUGIN / "skills" / "job-search" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "profile" in text
    assert "skip" in text            # unavailable platform -> skipped, never faked
    assert "never" in text and "fabricat" in text
