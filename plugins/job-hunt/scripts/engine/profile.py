"""User profile schema: load, save, validate.

The profile drives everything: which platforms search runs on, and how the
work-authorisation filter behaves. No user is special-cased.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from engine import workspace

PLATFORMS: set[str] = {
    "linkedin",
    "indeed",
    "naukri",
    "career_pages",
    "greenhouse_lever",
}

SCHEMES: set[str] = {"nl-ind-hsm", "eu-blue-card", "none"}


def default_profile() -> dict[str, Any]:
    """Return an empty-but-valid-shaped profile with safe defaults."""
    return {
        "schema_version": "1.0",
        "contact": {
            "name": "",
            "email": "",
            "phone": None,
            "location": None,
            "links": [],
        },
        "target_locations": [],
        "platforms": [],
        "work_auth": {"needs_sponsorship": False, "scheme": "none"},
        "language_constraints": {"english_only": False},
        "apply_prefs": {"auto_submit_simple_forms": False},
    }


def validate_profile(p: dict[str, Any]) -> list[str]:
    """Return a list of problems ([] == valid)."""
    issues: list[str] = []

    if not isinstance(p, dict):
        return ["root: expected a JSON object"]

    contact = p.get("contact")
    if not isinstance(contact, dict):
        issues.append("contact: missing or not an object")
    else:
        if not (isinstance(contact.get("name"), str) and contact["name"].strip()):
            issues.append("contact.name: required non-empty string")
        if not (isinstance(contact.get("email"), str) and contact["email"].strip()):
            issues.append("contact.email: required non-empty string")

    platforms = p.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        issues.append("platforms: choose at least one platform")
    else:
        for plat in platforms:
            if plat not in PLATFORMS:
                issues.append(
                    f"platforms: unknown platform {plat!r} (allowed: {sorted(PLATFORMS)})"
                )

    wa = p.get("work_auth")
    if not isinstance(wa, dict):
        issues.append("work_auth: missing or not an object")
    else:
        if not isinstance(wa.get("needs_sponsorship"), bool):
            issues.append("work_auth.needs_sponsorship: must be a boolean")
        if wa.get("scheme") not in SCHEMES:
            issues.append(
                f"work_auth.scheme: must be one of {sorted(SCHEMES)}, got {wa.get('scheme')!r}"
            )

    return issues


def load_profile(path: Optional[Path] = None) -> dict[str, Any]:
    path = Path(path) if path is not None else workspace.profile_path()
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}. Run /job-setup first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Profile must be a JSON object: {path}")
    return data


def save_profile(p: dict[str, Any], path: Optional[Path] = None) -> Path:
    path = Path(path) if path is not None else workspace.profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
