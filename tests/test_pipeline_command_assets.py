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
    assert "description" in _frontmatter(PLUGIN / "commands" / "job-pipeline.md")


def test_skill_frontmatter():
    fields = _frontmatter(PLUGIN / "skills" / "job-pipeline" / "SKILL.md")
    assert fields.get("name") == "job-pipeline"
    assert "description" in fields


def test_skill_uses_plugin_root_not_absolute_paths():
    text = (PLUGIN / "skills" / "job-pipeline" / "SKILL.md").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" in text
    assert "/Users/dantepk" not in text


def test_no_personal_data():
    blob = ((PLUGIN / "commands" / "job-pipeline.md").read_text(encoding="utf-8")
            + (PLUGIN / "skills" / "job-pipeline" / "SKILL.md").read_text(encoding="utf-8"))
    assert "Eshwar" not in blob and "dantepk" not in blob


def test_skill_orchestrates_the_full_chain():
    text = (PLUGIN / "skills" / "job-pipeline" / "SKILL.md").read_text(encoding="utf-8")
    # It drives the existing CLIs in sequence.
    assert "search_cli filter-dedupe-rank" in text
    assert "scoring.scoring_cli fit" in text
    assert "scoring.scoring_cli select" in text
    assert "tailor.tailor_cli finalize" in text
    assert "scoring.scoring_cli readiness" in text


def test_skill_user_approves_every_apply_no_new_auto_submit():
    text = (PLUGIN / "skills" / "job-pipeline" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "/job-apply" in text
    assert "approve" in text            # user approves every send
    assert "auto-submit" in text and "no new" in text   # no new auto-submit


def test_skill_never_fabricate_and_blocked_not_hidden():
    text = (PLUGIN / "skills" / "job-pipeline" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "never" in text and ("fabricate" in text or "inventing" in text)
    assert "fabrication" in text and "blocked" in text   # failed gate surfaced as blocked
    assert "/job-upskill" in text                        # genuine gaps route to upskill


def test_skill_skip_not_fake_unavailable_tools():
    text = (PLUGIN / "skills" / "job-pipeline" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "skip" in text and ("unavailable" in text or "not available" in text)
    assert "never fake" in text or "never fabricate" in text
