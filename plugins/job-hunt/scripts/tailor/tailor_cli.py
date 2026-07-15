"""CLI the /job-tailor skill drives. Every subcommand prints one JSON object to
stdout; failures print JSON and exit 1.

The heavy semantic step (turning the master CV + JD into tailored_cv.json) is
done by Claude in the skill. This CLI handles the deterministic half: saving the
JD, assembling the tailoring prompt, fabrication-checking + rendering + ATS-
scoring the Claude-authored result (`finalize`), and a deterministic offline
`mock-pack` used for tests and smoke.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make sibling packages importable when run as `python -m tailor.tailor_cli`
# from the scripts/ dir (the skill's invocation) or from anywhere.
_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from engine import workspace  # noqa: E402
from tailor import pipeline, tailor_engine  # noqa: E402


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def _jd_text(args: argparse.Namespace) -> str:
    """Resolve JD text from --jd-file or --jd-text (exactly one)."""
    return tailor_engine.load_job_description(
        jd_file=Path(args.jd_file) if args.jd_file else None,
        jd_text=args.jd_text,
    )


def cmd_check(_args: argparse.Namespace) -> int:
    _emit({
        "home": str(workspace.get_home()),
        "has_master": workspace.master_cv_path().exists(),
        "has_profile": workspace.profile_path().exists(),
    })
    return 0


def cmd_save_jd(args: argparse.Namespace) -> int:
    workspace.ensure_workspace()
    text = _jd_text(args)
    slug = f"{pipeline.slugify(args.company)}-{pipeline.slugify(args.role)}"
    jd_path = workspace.jd_queue_dir() / f"{slug}.txt"
    jd_path.write_text(text, encoding="utf-8")
    _emit({"ok": True, "jd_path": str(jd_path), "pack_slug": slug})
    return 0


def cmd_build_prompt(args: argparse.Namespace) -> int:
    master = tailor_engine.load_master_cv()  # workspace master
    prompt = tailor_engine.build_prompt(master, _jd_text(args), args.company, args.role)
    _emit({"prompt": prompt})
    return 0


def cmd_mock_pack(args: argparse.Namespace) -> int:
    workspace.ensure_workspace()
    result = pipeline.run_mock_pack(
        company=args.company, role=args.role, jd_text=_jd_text(args),
    )
    _emit(result)
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    workspace.ensure_workspace()
    tailored = json.loads(Path(args.tailored_file).read_text(encoding="utf-8"))
    result = pipeline.finalize_pack(
        company=args.company, role=args.role, tailored=tailored,
        jd_text=_jd_text(args), model=args.model,
    )
    _emit(result)
    return 0 if result.get("ok") else 1


def _add_jd_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--company", required=True)
    p.add_argument("--role", required=True)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--jd-file", type=str, help="Path to a JD text file.")
    src.add_argument("--jd-text", type=str, help="Raw JD text.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tailor_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check").set_defaults(func=cmd_check)

    sj = sub.add_parser("save-jd"); _add_jd_args(sj); sj.set_defaults(func=cmd_save_jd)
    bp = sub.add_parser("build-prompt"); _add_jd_args(bp); bp.set_defaults(func=cmd_build_prompt)
    mp = sub.add_parser("mock-pack"); _add_jd_args(mp); mp.set_defaults(func=cmd_mock_pack)

    fin = sub.add_parser("finalize"); _add_jd_args(fin)
    fin.add_argument("--tailored-file", required=True,
                     help="Path to the Claude-authored tailored_cv JSON.")
    fin.add_argument("--model", default=tailor_engine.DEFAULT_MODEL)
    fin.set_defaults(func=cmd_finalize)

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
