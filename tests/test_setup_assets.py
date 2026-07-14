import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugins" / "job-hunt"


def _frontmatter(path):
    text = path.read_text()
    assert text.startswith("---"), f"{path} missing frontmatter"
    end = text.index("---", 3)
    body = text[3:end]
    fields = {}
    for line in body.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields


def test_command_frontmatter():
    fields = _frontmatter(PLUGIN / "commands" / "job-setup.md")
    assert "description" in fields


def test_skill_frontmatter():
    fields = _frontmatter(PLUGIN / "skills" / "job-setup" / "SKILL.md")
    assert fields.get("name") == "job-setup"
    assert "description" in fields


def test_templates_are_valid_json_placeholders():
    prof = json.loads((REPO / "templates" / "profile.example.json").read_text())
    master = json.loads((REPO / "templates" / "cv_master.example.json").read_text())
    # No real personal data — placeholder identity only.
    assert prof["contact"]["name"] == "Ada Lovelace"
    assert master["contact"]["name"] == "Ada Lovelace"
    assert "dantepk" not in json.dumps(prof) + json.dumps(master)
    assert "Eshwar" not in json.dumps(prof) + json.dumps(master)


def test_skill_uses_plugin_root_not_absolute_paths():
    text = (PLUGIN / "skills" / "job-setup" / "SKILL.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}" in text
    assert "/Users/dantepk" not in text
