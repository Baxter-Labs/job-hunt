"""CLI the /job-search skill drives. Every subcommand prints one JSON object to
stdout; failures print JSON and exit 1.

The heavy step — actually querying platforms (Indeed MCP, LinkedIn scraper MCP,
Playwright on Naukri/career pages/greenhouse) — is done by Claude in the skill,
because those tools touch the network and are not callable from Python. Claude
hands the raw listings to this CLI, which does the deterministic half: work-auth
annotation, gating, dedupe, ranking, and tracker writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make sibling packages importable when run as `python -m search.search_cli`.
_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from engine import workspace  # noqa: E402
from engine import profile as profile_mod  # noqa: E402
from search import dedupe, listing as listing_mod, rank as rank_mod, tracker as tracker_mod  # noqa: E402
from work_auth import get_provider  # noqa: E402
from work_auth.base import DROP  # noqa: E402


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def _profile_scheme() -> str:
    """The profile's work_auth scheme, or 'none' when there is no profile yet."""
    try:
        prof = profile_mod.load_profile()
    except (FileNotFoundError, ValueError):
        return "none"
    return (prof.get("work_auth") or {}).get("scheme", "none")


def _target_levels() -> list[str]:
    try:
        prof = profile_mod.load_profile()
    except (FileNotFoundError, ValueError):
        return []
    # The profile has no explicit level field in Phase 1 — target_levels stay
    # empty (neutral) unless a future profile adds them. Kept here so ranking
    # wiring is one edit away.
    return list(prof.get("target_levels", [])) if isinstance(prof.get("target_levels"), list) else []


def cmd_annotate_workauth(args: argparse.Namespace) -> int:
    scheme = args.scheme or _profile_scheme()
    provider = get_provider(scheme)
    companies = [c.strip() for c in args.companies.split(",") if c.strip()]
    _emit({"scheme": scheme, "statuses": provider.annotate(companies)})
    return 0


def cmd_filter_dedupe_rank(args: argparse.Namespace) -> int:
    scheme = args.scheme or _profile_scheme()
    provider = get_provider(scheme, **({"drop_unknown": True} if args.drop_unknown else {}))

    raw = json.loads(Path(args.listings_file).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        _emit({"ok": False, "error": "listings file must be a JSON array"})
        return 1
    listings = listing_mod.normalize_listings(raw)
    total_in = len(listings)

    # Annotate every distinct company once, then attach + gate.
    statuses = provider.annotate([l["company"] for l in listings])
    kept: list[dict] = []
    dropped = 0
    for l in listings:
        l["work_auth"] = statuses.get(l["company"], {"status": "n/a"})
        if provider.gate(l) == DROP:
            dropped += 1
            continue
        kept.append(l)

    after_gate = len(kept)
    new = dedupe.filter_new(kept)  # vs workspace tracker + output packs
    before_collapse = len(new)
    new = dedupe.collapse_by_slug(new)  # collapse same job found on 2 platforms
    ranked = rank_mod.rank_listings(new, target_levels=_target_levels())

    _emit({
        "ok": True,
        "scheme": scheme,
        "counts": {
            "total_in": total_in,
            "after_gate": after_gate,
            "dropped": dropped,
            "duplicates": after_gate - before_collapse,
            "intra_batch_collapsed": before_collapse - len(new),
            "new": len(new),
        },
        "new": ranked,
    })
    return 0


def cmd_track(args: argparse.Namespace) -> int:
    workspace.ensure_workspace()
    result = tracker_mod.upsert(
        company=args.company, role=args.role, url=args.url,
        status=args.status, work_auth_status=args.work_auth,
        job_id=args.job_id, source=args.source, notes=args.notes,
    )
    _emit(result)
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    rows = tracker_mod.load_tracker()
    _emit({"home": str(workspace.get_home()), "tracker": tracker_mod.summarize(rows)})
    return 0


def cmd_refresh_register(args: argparse.Namespace) -> int:
    scheme = args.scheme or _profile_scheme()
    if scheme != "nl-ind-hsm":
        _emit({"ok": False, "error": f"scheme {scheme!r} has no register to refresh"})
        return 1
    provider = get_provider(scheme)
    count = provider.refresh(from_file=Path(args.from_file) if args.from_file else None)
    _emit({"ok": True, "scheme": scheme, "count": count,
           "register_path": str(provider.register_path())})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="search_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    aw = sub.add_parser("annotate-workauth")
    aw.add_argument("--companies", required=True, help="Comma-separated company names.")
    aw.add_argument("--scheme", default=None)
    aw.set_defaults(func=cmd_annotate_workauth)

    fr = sub.add_parser("filter-dedupe-rank")
    fr.add_argument("--listings-file", required=True, help="JSON array of raw listings.")
    fr.add_argument("--scheme", default=None)
    fr.add_argument("--drop-unknown", action="store_true",
                    help="Strict: drop listings whose work-auth status is not_found.")
    fr.set_defaults(func=cmd_filter_dedupe_rank)

    tr = sub.add_parser("track")
    tr.add_argument("--company", required=True)
    tr.add_argument("--role", required=True)
    tr.add_argument("--url", default="")
    tr.add_argument("--status", default="discovered")
    tr.add_argument("--work-auth", default="")
    tr.add_argument("--job-id", default="")
    tr.add_argument("--source", default="")
    tr.add_argument("--notes", default="")
    tr.set_defaults(func=cmd_track)

    sub.add_parser("status").set_defaults(func=cmd_status)

    rf = sub.add_parser("refresh-register")
    rf.add_argument("--scheme", default=None)
    rf.add_argument("--from-file", default=None,
                    help="Offline seed: name-per-line or CSV with a company_name column.")
    rf.set_defaults(func=cmd_refresh_register)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        _emit({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
