"""CLI the /job-apply skill drives. Every subcommand prints one JSON object to
stdout; failures print JSON and exit 1.

The heavy step — opening the apply page, prefilling fields, attaching files, and
any submit — is done by CLAUDE via the Playwright MCP in the skill, because that
touches the browser/network and is not callable from Python. This CLI does only
the deterministic half: assemble the pre-apply summary (ATS score shown FIRST) +
the safe prefill map + the auto-submit gate, and record tracker updates.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make sibling packages importable when run as `python -m apply.apply_cli`.
_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from engine import workspace  # noqa: E402
from engine import profile as profile_mod  # noqa: E402
from apply import preapply  # noqa: E402
from search import tracker as tracker_mod  # noqa: E402


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def cmd_preapply(args: argparse.Namespace) -> int:
    profile = profile_mod.load_profile()  # raises FileNotFoundError/ValueError -> handled in main
    output_root = Path(args.output_root) if args.output_root else None
    pack_dir = preapply.resolve_pack_dir(args.pack, output_root=output_root)
    summary = preapply.preapply_summary(pack_dir, profile, missing_limit=args.missing_limit)
    summary["ok"] = True
    summary["auto_submit"] = preapply.auto_submit_decision(profile, summary["ats_score"])
    _emit(summary)
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    workspace.ensure_workspace()
    result = tracker_mod.upsert(
        company=args.company, role=args.role, url=args.url,
        status=args.status, work_auth_status=args.work_auth,
        job_id=args.job_id, source=args.source, notes=args.notes,
    )
    _emit(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apply_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    pa = sub.add_parser("preapply", help="Assemble the pre-apply summary (ATS shown first).")
    pa.add_argument("--pack", required=True, help="Pack slug or directory path.")
    pa.add_argument("--output-root", default=None, help="Override the output root (tests).")
    pa.add_argument("--missing-limit", type=int, default=15)
    pa.set_defaults(func=cmd_preapply)

    rc = sub.add_parser("record", help="Record an apply/prepare event in the tracker.")
    rc.add_argument("--company", required=True)
    rc.add_argument("--role", required=True)
    rc.add_argument("--status", default="applied")
    rc.add_argument("--url", default="")
    rc.add_argument("--work-auth", default="")
    rc.add_argument("--job-id", default="")
    rc.add_argument("--source", default="")
    rc.add_argument("--notes", default="")
    rc.set_defaults(func=cmd_record)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        _emit({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
