"""CLI the fit-scoring skill drives. Prints one JSON object; errors exit 1.

Subcommand (deterministic, offline, workspace-read-only):
  * fit   --jd-file | --jd-text   -> {"ok": true, "fit_score", "components", "reasons"}

The fit score is a diagnostic only. A low fit routes the user to focus elsewhere
or /job-upskill; it is never a reason to fabricate. This CLI loads the workspace
master CV and the JD, computes the score, and prints it — nothing here writes
files, sends email, opens a browser, or touches the network.
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
