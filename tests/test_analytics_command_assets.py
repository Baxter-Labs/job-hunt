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
    assert "description" in _frontmatter(PLUGIN / "commands" / "job-analytics.md")


def test_skill_frontmatter():
    fields = _frontmatter(PLUGIN / "skills" / "job-analytics" / "SKILL.md")
    assert fields.get("name") == "job-analytics"
    assert "description" in fields


def test_skill_uses_plugin_root_not_absolute_paths():
    text = (PLUGIN / "skills" / "job-analytics" / "SKILL.md").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" in text
    assert "/Users/dantepk" not in text


def test_no_personal_data():
    blob = ((PLUGIN / "commands" / "job-analytics.md").read_text(encoding="utf-8")
            + (PLUGIN / "skills" / "job-analytics" / "SKILL.md").read_text(encoding="utf-8"))
    assert "Eshwar" not in blob and "dantepk" not in blob


def test_skill_wires_the_analytics_cli_and_log_outcome():
    text = (PLUGIN / "skills" / "job-analytics" / "SKILL.md").read_text(encoding="utf-8")
    assert "insights.insights_cli analytics" in text
    assert "search.search_cli log-outcome" in text


def test_skill_is_honest_about_small_samples():
    low = (PLUGIN / "skills" / "job-analytics" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "small" in low and "sample" in low  # honesty guard present


def test_track_command_points_to_analytics():
    text = (PLUGIN / "commands" / "job-track.md").read_text(encoding="utf-8")
    assert "analytics" in text.lower()
