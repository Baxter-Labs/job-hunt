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
    assert "description" in _frontmatter(PLUGIN / "commands" / "job-fit.md")


def test_skill_frontmatter():
    fields = _frontmatter(PLUGIN / "skills" / "job-fit" / "SKILL.md")
    assert fields.get("name") == "job-fit"
    assert "description" in fields


def test_skill_uses_plugin_root_not_absolute_paths():
    text = (PLUGIN / "skills" / "job-fit" / "SKILL.md").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" in text
    assert "/Users/dantepk" not in text


def test_no_personal_data():
    blob = ((PLUGIN / "commands" / "job-fit.md").read_text(encoding="utf-8")
            + (PLUGIN / "skills" / "job-fit" / "SKILL.md").read_text(encoding="utf-8"))
    assert "Eshwar" not in blob and "dantepk" not in blob


def test_skill_invokes_scoring_cli_fit():
    text = (PLUGIN / "skills" / "job-fit" / "SKILL.md").read_text(encoding="utf-8")
    assert "scoring.scoring_cli" in text
    assert "fit" in text


def test_skill_encodes_fit_and_honesty():
    text = (PLUGIN / "skills" / "job-fit" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "fit" in text
    # Honesty: low fit routes to focus/upskill, never fabricate/inflate.
    assert "upskill" in text
    assert "fabricate" in text or "inflate" in text
