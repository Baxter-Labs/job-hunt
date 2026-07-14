import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_marketplace_manifest_is_valid():
    data = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
    assert data["name"] == "job-hunt"
    plugins = {p["name"]: p for p in data["plugins"]}
    assert "job-hunt" in plugins
    assert plugins["job-hunt"]["source"] == "./plugins/job-hunt"


def test_plugin_manifest_is_valid():
    data = json.loads(
        (REPO / "plugins" / "job-hunt" / ".claude-plugin" / "plugin.json").read_text()
    )
    assert data["name"] == "job-hunt"
    assert "version" in data
    assert "description" in data
