"""CLI the /job-setup skill drives. Every subcommand prints a JSON object to
stdout; invalid input exits 1 with {"ok": false, "issues": [...]}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine import cv_import, profile as profile_mod, workspace


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def cmd_init_workspace(_args: argparse.Namespace) -> int:
    home = workspace.ensure_workspace()
    _emit({"home": str(home)})
    return 0


def cmd_extract_cv(args: argparse.Namespace) -> int:
    text = cv_import.extract_pdf_text([Path(p) for p in args.pdf])
    _emit({"text": text, "chars": len(text)})
    return 0


def cmd_write_profile(args: argparse.Namespace) -> int:
    data = json.loads(args.json)
    issues = profile_mod.validate_profile(data)
    if issues:
        _emit({"ok": False, "issues": issues})
        return 1
    path = profile_mod.save_profile(data)
    _emit({"ok": True, "path": str(path)})
    return 0


def cmd_write_master(args: argparse.Namespace) -> int:
    data = json.loads(args.json)
    issues = cv_import.validate_master_cv(data)
    if issues:
        _emit({"ok": False, "issues": issues})
        return 1
    path = cv_import.save_master_cv(data)
    _emit({"ok": True, "path": str(path)})
    return 0


def cmd_show(_args: argparse.Namespace) -> int:
    _emit({
        "home": str(workspace.get_home()),
        "has_profile": workspace.profile_path().exists(),
        "has_master": workspace.master_cv_path().exists(),
    })
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="setup_cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-workspace").set_defaults(func=cmd_init_workspace)

    ex = sub.add_parser("extract-cv")
    ex.add_argument("--pdf", action="append", required=True, help="Path to a CV PDF (repeatable).")
    ex.set_defaults(func=cmd_extract_cv)

    wp = sub.add_parser("write-profile")
    wp.add_argument("--json", required=True, help="Profile JSON string.")
    wp.set_defaults(func=cmd_write_profile)

    wm = sub.add_parser("write-master")
    wm.add_argument("--json", required=True, help="Master CV JSON string.")
    wm.set_defaults(func=cmd_write_master)

    sub.add_parser("show").set_defaults(func=cmd_show)
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
