"""CLI the funnel skills drive. Every subcommand prints one JSON object to
stdout; failures print JSON (`{"ok": false, "error": ...}`) and exit 1.

Subcommands (all deterministic, offline, workspace-read-only):
  * red-flags       --jd-file | --jd-text   -> advisory JD red flags
  * upskill         --pack <slug> | --all    -> ranked missing-keyword gaps
  * followup-context --company --role        -> one application's context

The generative work (learning plans, follow-up email drafts) is Claude's job in
the skills; this CLI only produces their factual inputs. Nothing here sends
email, opens a browser, or touches the network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make sibling packages importable when run as `python -m insights.insights_cli`.
_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from tailor.tailor_engine import load_job_description  # noqa: E402
from apply import preapply  # noqa: E402
from insights import redflags, upskill, followup, analytics  # noqa: E402
from search import tracker as tracker_mod  # noqa: E402


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def cmd_red_flags(args: argparse.Namespace) -> int:
    # Reuse the tailor engine's exactly-one-of validation (raises ValueError).
    jd_text = load_job_description(jd_file=args.jd_file, jd_text=args.jd_text)
    flags = redflags.scan_red_flags(jd_text)
    _emit({"ok": True, "count": len(flags), "red_flags": flags})
    return 0


def cmd_upskill(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root) if args.output_root else None
    if args.all and args.pack:
        raise ValueError("Provide exactly one of --pack <slug> or --all, not both.")
    if args.all:
        pack_dirs = upskill.iter_pack_dirs(output_root)
    elif args.pack:
        pack_dirs = [preapply.resolve_pack_dir(args.pack, output_root=output_root)]
    else:
        raise ValueError("Provide exactly one of --pack <slug> or --all.")
    gaps = upskill.aggregate_gaps(pack_dirs)
    _emit({"ok": True, "packs_scanned": len(pack_dirs), "gaps": gaps})
    return 0


def cmd_followup_context(args: argparse.Namespace) -> int:
    if not args.company or not args.role:
        raise ValueError("Both --company and --role are required.")
    output_root = Path(args.output_root) if args.output_root else None
    ctx = followup.application_context(args.company, args.role, output_root=output_root)
    ctx["ok"] = True
    _emit(ctx)
    return 0


def cmd_analytics(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root) if args.output_root else None
    rows = tracker_mod.load_tracker()
    lookup = analytics.workspace_pack_lookup(output_root=output_root)
    report = analytics.funnel_report(rows, pack_lookup=lookup)
    report["ok"] = True
    _emit(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="insights_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    rf = sub.add_parser("red-flags", help="Scan a JD for advisory red flags.")
    # NOT required at the argparse level: passing neither --jd-file nor
    # --jd-text must NOT trigger argparse's own exit(2)/usage-text error.
    # Instead it falls through to load_job_description, which raises
    # ValueError, caught by main() -> {"ok": false, ...} JSON + exit 1.
    src = rf.add_mutually_exclusive_group(required=False)
    src.add_argument("--jd-file", type=Path, default=None, help="Path to a JD text file.")
    src.add_argument("--jd-text", type=str, default=None, help="Raw JD text.")
    rf.set_defaults(func=cmd_red_flags)

    up = sub.add_parser("upskill", help="Rank missing-keyword gaps across packs.")
    # NOT required at the argparse level, matching red-flags: missing/conflicting
    # --pack/--all must fall through to cmd_upskill's own ValueError -> JSON
    # {"ok": false, ...} + exit 1, not argparse's exit(2)/usage-text error.
    mode = up.add_mutually_exclusive_group(required=False)
    mode.add_argument("--pack", default=None, help="A single pack slug or dir.")
    mode.add_argument("--all", action="store_true", help="All packs in the workspace.")
    up.add_argument("--output-root", default=None, help="Override the output root (tests).")
    up.set_defaults(func=cmd_upskill)

    fu = sub.add_parser("followup-context", help="Assemble one application's context.")
    # NOT required at the argparse level, matching red-flags: a missing --company
    # or --role must fall through to cmd_followup_context's own ValueError ->
    # JSON {"ok": false, ...} + exit 1, not argparse's exit(2)/usage-text error.
    fu.add_argument("--company", required=False, default=None)
    fu.add_argument("--role", required=False, default=None)
    fu.add_argument("--output-root", default=None, help="Override the output root (tests).")
    fu.set_defaults(func=cmd_followup_context)

    an = sub.add_parser("analytics", help="Outcome funnel + breakdowns + takeaways.")
    an.add_argument("--output-root", default=None, help="Override the output root (tests).")
    an.set_defaults(func=cmd_analytics)

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
