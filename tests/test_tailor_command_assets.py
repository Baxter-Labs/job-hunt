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
    fields = _frontmatter(PLUGIN / "commands" / "job-tailor.md")
    assert "description" in fields


def test_skill_frontmatter():
    fields = _frontmatter(PLUGIN / "skills" / "cv-tailor" / "SKILL.md")
    assert fields.get("name") == "cv-tailor"
    assert "description" in fields


def test_skill_uses_plugin_root_not_absolute_paths():
    text = (PLUGIN / "skills" / "cv-tailor" / "SKILL.md").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" in text
    assert "/Users/dantepk" not in text


def test_no_personal_data_in_command_or_skill():
    blob = ((PLUGIN / "commands" / "job-tailor.md").read_text(encoding="utf-8")
            + (PLUGIN / "skills" / "cv-tailor" / "SKILL.md").read_text(encoding="utf-8"))
    assert "Eshwar" not in blob
    assert "dantepk" not in blob


def test_skill_mentions_ats_and_fabrication():
    text = (PLUGIN / "skills" / "cv-tailor" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "ats" in text
    assert "fabricat" in text
    assert "cover_letter.md" in text
