"""Assemble the pre-apply summary + safe prefill map + the auto-submit gate.

Everything in this module is PURE and OFFLINE. Browser automation — opening the
apply page, prefilling fields, attaching files, and any submit — is performed by
CLAUDE via the Playwright MCP inside the /job-apply SKILL, NEVER by this module.
The testable Python is only: reading the pack's ats_report.json, building the
safe prefill field map from the profile, choosing which pack files to attach, and
deciding whether auto-submit is permitted.

SAFETY (binding):
  * prefill_fields returns ONLY non-secret contact fields (name, email, phone,
    location, public profile links). It NEVER returns or handles a password,
    secret, token, or answer to a login/consent challenge. The user authenticates
    their own accounts.
  * The ATS match score is surfaced FIRST (spec §5.4) so the user can re-tailor
    or proceed before anything opens.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from engine import workspace


def resolve_pack_dir(pack: str, output_root: Optional[Path] = None) -> Path:
    """Resolve a pack argument to a directory.

    Accepts either a pack SLUG ('acme-backend-engineer') resolved under the
    output root (defaults to the workspace output dir), or an existing/absolute
    PATH used as-is. Never creates anything.
    """
    root = Path(output_root) if output_root is not None else workspace.output_dir()
    p = Path(pack).expanduser()
    if p.is_absolute() or p.exists() or os.sep in str(pack):
        return p
    return root / pack


def load_ats_report(pack_dir: Path) -> Optional[dict[str, Any]]:
    """Return the parsed ats_report.json, or None when absent/unreadable."""
    path = Path(pack_dir) / "ats_report.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


# Public profile-link labels we recognise and flatten to their own field.
_LINK_KEYS = (
    ("linkedin", ("linkedin",)),
    ("github", ("github",)),
    ("website", ("portfolio", "website", "site", "homepage")),
)


def prefill_fields(profile: dict[str, Any]) -> dict[str, Any]:
    """Build the SAFE, non-secret prefill field map from the profile contact.

    Returns only name/email/phone/location and public profile links. Empty values
    are omitted. NEVER returns a password, secret, token, or credential — the user
    authenticates their own accounts.
    """
    contact = profile.get("contact") or {}
    fields: dict[str, Any] = {}

    def put(key: str, value: Any) -> None:
        if isinstance(value, str) and value.strip():
            fields[key] = value.strip()

    put("full_name", contact.get("name"))
    put("email", contact.get("email"))
    put("phone", contact.get("phone"))
    put("location", contact.get("location"))

    normalized_links: list[dict[str, str]] = []
    for item in contact.get("links") or []:
        if isinstance(item, dict):
            url = str(item.get("url", "")).strip()
            if not url:
                continue
            label = str(item.get("label", "")).strip()
            normalized_links.append({"label": label, "url": url})
            low = label.lower()
            for field_key, needles in _LINK_KEYS:
                if field_key not in fields and any(n in low for n in needles):
                    fields[field_key] = url
                    break
        elif isinstance(item, str) and item.strip():
            normalized_links.append({"label": "", "url": item.strip()})

    if normalized_links:
        fields["links"] = normalized_links
    return fields


def pack_attachments(pack_dir: Path) -> dict[str, Optional[str]]:
    """Which files to attach: prefer cv.pdf then cv.html; cover_letter.pdf then .md."""
    pack_dir = Path(pack_dir)

    def first_existing(*names: str) -> Optional[str]:
        for name in names:
            candidate = pack_dir / name
            if candidate.exists():
                return str(candidate)
        return None

    return {
        "cv": first_existing("cv.pdf", "cv.html"),
        "cover_letter": first_existing("cover_letter.pdf", "cover_letter.md"),
    }


def preapply_summary(
    pack_dir: Path,
    profile: dict[str, Any],
    *,
    missing_limit: int = 15,
) -> dict[str, Any]:
    """The pre-apply payload. ATS FIRST (spec §5.4), then the safe prefill map and
    the attachments to hand to the Playwright MCP, plus factual warnings. Nothing
    here opens a browser or the network."""
    pack_dir = Path(pack_dir)
    exists = pack_dir.is_dir()
    warnings: list[str] = []

    if not exists:
        warnings.append(f"Pack directory not found: {pack_dir}. Run /job-tailor first.")

    report = load_ats_report(pack_dir) if exists else None
    if exists and report is None:
        warnings.append("No ats_report.json in the pack; ATS score is unknown. "
                        "Re-run /job-tailor to compute it before applying.")

    ats_score = report.get("match_score") if report else None
    missing = list(report.get("missing_keywords", []) or []) if report else []
    matched = list(report.get("matched_keywords", []) or []) if report else []

    attachments = pack_attachments(pack_dir) if exists else {"cv": None, "cover_letter": None}
    if exists and attachments["cv"] is None:
        warnings.append("No cv.pdf/cv.html in the pack to attach.")
    if exists and attachments["cover_letter"] is None:
        warnings.append("No cover_letter.pdf/cover_letter.md in the pack to attach.")

    return {
        "pack_dir": str(pack_dir),
        "exists": exists,
        "company": report.get("company", "") if report else "",
        "role": report.get("role", "") if report else "",
        "ats_score": ats_score,
        "total_keywords": report.get("total_keywords", 0) if report else 0,
        "matched_count": report.get("matched_count", 0) if report else 0,
        "matched_keywords": matched[:missing_limit],
        "missing_keywords": missing[:missing_limit],
        "prefill_fields": prefill_fields(profile),
        "attachments": attachments,
        "warnings": warnings,
    }


def auto_submit_decision(profile: dict[str, Any], ats_score: Optional[int]) -> dict[str, Any]:
    """Pure gate for clicking submit on a SIMPLE form (no CAPTCHA/login/consent).

    Returns allowed=True only when apply_prefs.auto_submit_simple_forms is True
    AND (no min_ats_score gate is set OR ats_score >= min_ats_score). Even when
    allowed, the SKILL still halts at any CAPTCHA/login/consent and never enters
    credentials — this decision only concerns the opt-in toggle.
    """
    prefs = profile.get("apply_prefs") or {}
    if not bool(prefs.get("auto_submit_simple_forms", False)):
        return {"allowed": False,
                "reason": "apply_prefs.auto_submit_simple_forms is off; manual submit required."}

    threshold = prefs.get("min_ats_score")
    if threshold is not None:
        try:
            threshold = int(threshold)
        except (TypeError, ValueError):
            threshold = None

    if threshold is not None:
        if ats_score is None:
            return {"allowed": False,
                    "reason": f"ATS score unknown; min_ats_score {threshold} gate cannot be satisfied."}
        if int(ats_score) < threshold:
            return {"allowed": False,
                    "reason": f"ATS score {ats_score} is below min_ats_score {threshold}."}
        return {"allowed": True,
                "reason": (f"Toggle on and ATS score {ats_score} >= min_ats_score {threshold}; "
                           "submit allowed on simple forms only (still halts at CAPTCHA/login/consent).")}

    return {"allowed": True,
            "reason": ("Toggle on; no min_ats_score gate; submit allowed on simple forms only "
                       "(still halts at CAPTCHA/login/consent).")}
