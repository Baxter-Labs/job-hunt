#!/usr/bin/env python3
"""render_letter.py - render a tailored cover letter to a clean PDF + HTML.

Reads a pack's ``tailored_cv.json`` (for the candidate's contact details and the
target company/role) and a sibling ``cover_letter.md`` (the letter body:
salutation, paragraphs, sign-off), then writes ``cover_letter.html`` and
``cover_letter.pdf`` into the pack, styled to match the CV (same accent colour,
serif body, A4 margins). PDF uses weasyprint; if it is unavailable the HTML is
still written and the PDF step is skipped (never crashes).

Usage:
    render_letter.py --pack /path/to/output/<company>-<role>
"""

from __future__ import annotations

import argparse
import html as _html
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

ACCENT = "#1f5f8b"
INK = "#1c2733"
INK_MUTED = "#566372"
RULE = "#d8dee5"


def _esc(value: Any) -> str:
    return _html.escape(str(value if value is not None else ""), quote=True)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value if value is not None else "")).strip()


def _letter_css() -> str:
    return f"""
    @page {{ size: A4; margin: 18mm 18mm; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; color: {INK};
      font-family: Georgia, "Iowan Old Style", "Times New Roman", serif;
      font-size: 10.6pt; line-height: 1.5;
    }}
    .lh-name {{
      font-family: "Helvetica Neue", Arial, sans-serif;
      font-size: 18pt; font-weight: 700; margin: 0; color: {INK};
    }}
    .lh-title {{
      font-family: "Helvetica Neue", Arial, sans-serif;
      font-size: 10.5pt; color: {ACCENT}; margin: 1px 0 7px 0;
    }}
    .lh-contact {{
      font-family: "Helvetica Neue", Arial, sans-serif;
      font-size: 9pt; color: {INK_MUTED};
      padding-bottom: 10px; border-bottom: 1px solid {RULE}; margin-bottom: 16px;
    }}
    .lh-contact a {{ color: {INK_MUTED}; text-decoration: none; }}
    .meta {{ margin: 0 0 14px 0; font-size: 10pt; }}
    .meta .date {{ color: {INK_MUTED}; }}
    p {{ margin: 0 0 10px 0; text-align: left; }}
    """.strip()


def render_letter(pack: Path) -> dict[str, Any]:
    pack = Path(pack)
    cv = json.loads((pack / "tailored_cv.json").read_text(encoding="utf-8"))
    body_path = pack / "cover_letter.md"
    if not body_path.exists():
        raise FileNotFoundError(f"missing {body_path}")
    body_md = body_path.read_text(encoding="utf-8")

    c = cv.get("contact", {}) or {}
    meta = cv.get("meta", {}) or {}

    bits: list[str] = []
    for key in ("email", "phone", "location"):
        if _clean(c.get(key)):
            bits.append(_esc(_clean(c.get(key))))
    for link in c.get("links", []) or []:
        if isinstance(link, dict) and _clean(link.get("url")):
            bits.append(
                f'<a href="{_esc(link["url"])}">'
                f'{_esc(_clean(link.get("label")) or link["url"])}</a>'
            )
    contact_line = " &middot; ".join(bits)

    paras = [p.strip() for p in re.split(r"\n\s*\n", body_md.strip()) if p.strip()]
    body_html = "\n    ".join(
        "<p>" + _esc(p).replace("\n", "<br>") + "</p>" for p in paras
    )

    today = date.today()
    today_str = f"{today.day} {today.strftime('%B %Y')}"

    recipient = _clean(meta.get("company"))
    role = _clean(meta.get("role"))

    html = (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <style>\n{_letter_css()}\n  </style>\n</head>\n<body>\n"
        "  <header>\n"
        f'    <p class="lh-name">{_esc(_clean(c.get("name")))}</p>\n'
        f'    <p class="lh-title">{_esc(_clean(c.get("title")))}</p>\n'
        f'    <div class="lh-contact">{contact_line}</div>\n'
        "  </header>\n"
        '  <div class="meta">\n'
        f'    <div class="date">{_esc(today_str)}</div>\n'
        f"    <div>Hiring Team, {_esc(recipient)}</div>\n"
        f"    <div>Re: {_esc(role)}</div>\n"
        "  </div>\n"
        f"  {body_html}\n"
        "</body>\n</html>\n"
    )

    (pack / "cover_letter.html").write_text(html, encoding="utf-8")

    backend = "html-only"
    try:
        from weasyprint import HTML  # type: ignore

        HTML(string=html, base_url=str(pack)).write_pdf(str(pack / "cover_letter.pdf"))
        backend = "weasyprint"
    except Exception as exc:  # noqa: BLE001 - PDF optional; HTML always written
        print(f"[render_letter] PDF skipped ({exc})", file=sys.stderr)

    return {
        "html": pack / "cover_letter.html",
        "pdf": pack / "cover_letter.pdf",
        "backend": backend,
    }


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="render_letter.py")
    ap.add_argument("--pack", required=True, type=Path, help="Pack dir with tailored_cv.json + cover_letter.md")
    args = ap.parse_args(argv)
    result = render_letter(args.pack)
    print(f"HTML: {result['html']}")
    print(f"PDF : {result['pdf']}  (backend: {result['backend']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
