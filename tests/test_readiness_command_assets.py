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
    assert "description" in _frontmatter(PLUGIN / "commands" / "job-readiness.md")


def test_skill_frontmatter():
    fields = _frontmatter(PLUGIN / "skills" / "job-readiness" / "SKILL.md")
    assert fields.get("name") == "job-readiness"
    assert "description" in fields


def test_skill_uses_plugin_root_not_absolute_paths():
    text = (PLUGIN / "skills" / "job-readiness" / "SKILL.md").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" in text
    assert "/Users/dantepk" not in text


def test_no_personal_data():
    blob = ((PLUGIN / "commands" / "job-readiness.md").read_text(encoding="utf-8")
            + (PLUGIN / "skills" / "job-readiness" / "SKILL.md").read_text(encoding="utf-8"))
    assert "Eshwar" not in blob and "dantepk" not in blob


def test_skill_invokes_scoring_cli_readiness():
    text = (PLUGIN / "skills" / "job-readiness" / "SKILL.md").read_text(encoding="utf-8")
    assert "scoring.scoring_cli" in text
    assert "readiness" in text


def test_skill_encodes_fabrication_gate_and_honest_loop():
    text = (PLUGIN / "skills" / "job-readiness" / "SKILL.md").read_text(encoding="utf-8").lower()
    # Hard fabrication gate.
    assert "fabrication" in text and "blocking" in text
    # Honest improve loop: surface has-but-unsurfaced, route gaps to upskill, never fabricate.
    assert "surface" in text
    assert "/job-upskill" in text
    assert "never" in text and ("fabricate" in text or "inventing" in text or "add" in text)
