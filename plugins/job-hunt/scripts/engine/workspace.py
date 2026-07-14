"""Resolve and create the per-user Job Hunt workspace.

The workspace holds ALL personal data (profile, master CV, tailored packs,
tracker). Its location comes from the JOB_HUNT_HOME env var, defaulting to
~/.job-hunt. Nothing here is specific to any user.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_HOME = "~/.job-hunt"


def get_home() -> Path:
    """Return the workspace root (not created)."""
    raw = os.environ.get("JOB_HUNT_HOME") or DEFAULT_HOME
    return Path(raw).expanduser()


def ensure_workspace() -> Path:
    """Create the workspace root and standard subdirectories; return the root."""
    home = get_home()
    home.mkdir(parents=True, exist_ok=True)
    output_dir().mkdir(parents=True, exist_ok=True)
    jd_queue_dir().mkdir(parents=True, exist_ok=True)
    return home


def profile_path() -> Path:
    return get_home() / "profile.json"


def master_cv_path() -> Path:
    return get_home() / "cv_master.json"


def tracker_path() -> Path:
    return get_home() / "tracker.csv"


def output_dir() -> Path:
    return get_home() / "output"


def jd_queue_dir() -> Path:
    return get_home() / "jd_queue"
