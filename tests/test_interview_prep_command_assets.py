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
    assert "description" in _frontmatter(PLUGIN / "commands" / "job-interview-prep.md")


def test_skill_frontmatter():
    fields = _frontmatter(PLUGIN / "skills" / "interview-prep" / "SKILL.md")
    assert fields.get("name") == "interview-prep"
    assert "description" in fields


def test_skill_uses_plugin_root_not_absolute_paths():
    text = (PLUGIN / "skills" / "interview-prep" / "SKILL.md").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" in text
    assert "/Users/dantepk" not in text


def test_no_personal_data():
    blob = ((PLUGIN / "commands" / "job-interview-prep.md").read_text(encoding="utf-8")
            + (PLUGIN / "skills" / "interview-prep" / "SKILL.md").read_text(encoding="utf-8"))
    assert "Eshwar" not in blob and "dantepk" not in blob


def test_skill_is_grounded_in_master_cv_only():
    text = (PLUGIN / "skills" / "interview-prep" / "SKILL.md").read_text(encoding="utf-8")
    low = text.lower()
    # BINDING: talking points grounded ONLY in the master CV; never invent.
    assert "master cv" in low
    assert "never" in low and ("invent" in low or "fabricat" in low)
