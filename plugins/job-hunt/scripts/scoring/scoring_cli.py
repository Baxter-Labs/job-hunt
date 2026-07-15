"""CLI the fit-scoring skill drives. Prints one JSON object; errors exit 1.

Subcommands (deterministic, offline, workspace-read-only):
  * fit         --jd-file | --jd-text   -> {"ok": true, "fit_score", "components", "reasons"}
  * readiness   --pack [--jd-file | --jd-text] [--no-write]
                -> {"ok": true, "readiness_score", "factors", "suggestions", "blocking", ...}

The fit score is a diagnostic only. A low fit routes the user to focus elsewhere
or /job-upskill; it is never a reason to fabricate. This CLI loads the workspace
master CV and the JD, computes the score, and prints it — nothing here writes
files, sends email, opens a browser, or touches the network (readiness optionally
writes readiness.json into the pack it just scored).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from tailor.tailor_engine import load_job_description, load_master_cv  # noqa: E402
from scoring import fit  # noqa: E402
from engine import workspace  # noqa: E402
from apply import preapply  # noqa: E402
from scoring import readiness  # noqa: E402


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def cmd_fit(args: argparse.Namespace) -> int:
    # Reuse the tailor engine's exactly-one-of validation (raises ValueError),
    # and its workspace master loader (raises FileNotFoundError/ValueError).
    jd_text = load_job_description(jd_file=args.jd_file, jd_text=args.jd_text)
    master_cv = load_master_cv()
    report = fit.fit_report(master_cv, jd_text)
    _emit({"ok": True, **report})
    return 0


def _resolve_jd(args: argparse.Namespace, pack_dir: Path) -> str:
    """JD from --jd-file/--jd-text if given, else the pack's stored jd_queue/<slug>.txt."""
    if args.jd_file is not None or args.jd_text is not None:
        return load_job_description(jd_file=args.jd_file, jd_text=args.jd_text)
    slug = Path(pack_dir).name
    jd_path = workspace.jd_queue_dir() / f"{slug}.txt"
    if jd_path.exists():
        return load_job_description(jd_file=jd_path)
    raise ValueError(
        f"No JD found for pack {slug!r} (looked in {jd_path}); pass --jd-file or --jd-text."
    )


def cmd_readiness(args: argparse.Namespace) -> int:
    if not args.pack:
        raise ValueError("--pack <slug|dir> is required.")
    output_root = Path(args.output_root) if args.output_root else None
    pack_dir = preapply.resolve_pack_dir(args.pack, output_root=output_root)
    jd_text = _resolve_jd(args, pack_dir)
    master_cv = load_master_cv()
    report = readiness.readiness_report(pack_dir, master_cv, jd_text)
    written = None if args.no_write else str(readiness.write_readiness_report(report, pack_dir))
    _emit({"ok": True, "pack_dir": str(pack_dir), "readiness_json": written, **report})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scoring_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    ft = sub.add_parser("fit", help="Score the workspace master CV against a JD.")
    # NOT required at the argparse level: passing neither --jd-file nor --jd-text
    # must fall through to load_job_description's ValueError -> {"ok": false} + exit 1,
    # never argparse's own exit(2)/usage error.
    src = ft.add_mutually_exclusive_group(required=False)
    src.add_argument("--jd-file", type=Path, default=None, help="Path to a JD text file.")
    src.add_argument("--jd-text", type=str, default=None, help="Raw JD text.")
    ft.set_defaults(func=cmd_fit)

    rd = sub.add_parser("readiness", help="Score a pack's readiness to send.")
    # --pack is NOT argparse-required: a missing --pack must fall through to
    # cmd_readiness's ValueError -> {"ok": false} + exit 1, never argparse exit 2.
    rd.add_argument("--pack", default=None, help="Pack slug or directory.")
    src2 = rd.add_mutually_exclusive_group(required=False)
    src2.add_argument("--jd-file", type=Path, default=None, help="Path to a JD text file.")
    src2.add_argument("--jd-text", type=str, default=None, help="Raw JD text.")
    rd.add_argument("--output-root", default=None, help="Override the output root (tests).")
    rd.add_argument("--no-write", action="store_true", help="Do not write readiness.json.")
    rd.set_defaults(func=cmd_readiness)

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
