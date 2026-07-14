import importlib.util
from pathlib import Path

MODdir = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"


def _load():
    import sys
    sys.path.insert(0, str(MODdir))
    import engine.workspace as ws
    importlib.reload(ws)
    return ws


def test_get_home_uses_env(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_HUNT_HOME", str(tmp_path / "ws"))
    ws = _load()
    assert ws.get_home() == tmp_path / "ws"


def test_get_home_defaults_to_user_home(monkeypatch):
    monkeypatch.delenv("JOB_HUNT_HOME", raising=False)
    ws = _load()
    assert ws.get_home() == Path("~/.job-hunt").expanduser()


def test_ensure_workspace_creates_dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_HUNT_HOME", str(tmp_path / "ws"))
    ws = _load()
    home = ws.ensure_workspace()
    assert home.is_dir()
    assert ws.output_dir().is_dir()
    assert ws.jd_queue_dir().is_dir()


def test_path_helpers(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_HUNT_HOME", str(tmp_path / "ws"))
    ws = _load()
    assert ws.profile_path().name == "profile.json"
    assert ws.master_cv_path().name == "cv_master.json"
    assert ws.tracker_path().name == "tracker.csv"
