#!/usr/bin/env python3
"""render_cv.py — the presentation layer of the CV-tailoring pipeline.

Renders a ``tailored_cv.json`` (the §2 interchange schema) into two artefacts:

  * a polished, self-contained ``cv.html`` — embedded CSS, single accent colour,
    one linear column, real typographic hierarchy, generous whitespace, NO
    tables/columns for layout, NO icons-as-text, fully selectable real text;
  * a ``cv.pdf`` rendered from that HTML, trying three backends in order —
    weasyprint -> wkhtmltopdf (subprocess) -> reportlab plain fallback — and
    NEVER hard-crashing when a backend is missing. The backend actually used is
    returned and printed.

The visual target is a senior engineer's own clean CV: name + title header, a
subtle rule under each section heading, restrained colour, lots of air. Not a
flashy multi-column template (those also break ATS parsers).

Public API (see CONTRACT.md §4):

    render_html(tailored: dict) -> str
    write_html(tailored: dict, out_path: Path) -> Path
    render_pdf(html: str, out_path: Path) -> tuple[Path, str]
    render_cv(tailored: dict | Path, out_dir: Path) -> dict[str, Path | str]

CLI:
    python render_cv.py --in PATH --out-dir PATH
    python render_cv.py --self-test [--out-dir PATH]
"""

from __future__ import annotations

import argparse
import html as _html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Self-contained constants. render_cv(out_dir) always takes an explicit dir;
# OUTPUT_ROOT is only the default for the --self-test CLI path.
# ---------------------------------------------------------------------------
CV_SYSTEM_ROOT: Path = Path(__file__).resolve().parent
OUTPUT_ROOT: Path = CV_SYSTEM_ROOT / "output"
SCHEMA_VERSION: str = "1.0"


# ---------------------------------------------------------------------------
# Design tokens. One accent colour, one neutral ink, generous spacing scale.
# Tuned to read like a real senior engineer's document, not a template.
# ---------------------------------------------------------------------------
ACCENT = "#1f5f8b"        # a single, calm steel-blue accent
INK = "#1c2733"           # near-black body text (not pure #000 — softer on paper)
INK_MUTED = "#566372"     # secondary text: dates, locations, meta
RULE = "#d8dee5"          # hairline section rules
PAGE_BG = "#ffffff"


# ===========================================================================
# Small, pure formatting helpers
# ===========================================================================
def _esc(value: Any) -> str:
    """HTML-escape a value, coercing None/blank to empty string."""
    if value is None:
        return ""
    return _html.escape(str(value), quote=True)


def _clean(value: Any) -> str:
    """Trim and collapse internal whitespace; '' for None."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _is_url(value: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9+.\-]*://", value, re.IGNORECASE))


def _normalise_url(value: str) -> str:
    """Make a link href safe and absolute-ish without inventing a scheme."""
    v = _clean(value)
    if not v:
        return ""
    if _is_url(v) or v.startswith("mailto:") or v.startswith("tel:"):
        return v
    # bare domain like "linkedin.com/in/x" -> https://...
    return "https://" + v


def _display_link(label: str, url: str) -> str:
    """Human-readable link text: prefer the label, else strip the scheme."""
    label = _clean(label)
    if label:
        return label
    stripped = re.sub(r"^[a-z][a-z0-9+.\-]*://", "", _clean(url), flags=re.IGNORECASE)
    return stripped.rstrip("/")


def _as_dict(tailored: "dict[str, Any] | Path") -> dict[str, Any]:
    """Accept a dict or a path to tailored_cv.json; return a dict."""
    if isinstance(tailored, (str, Path)):
        path = Path(tailored)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path} did not contain a JSON object")
        return data
    if isinstance(tailored, dict):
        return tailored
    raise TypeError(f"tailored must be dict or Path, got {type(tailored)!r}")


# ===========================================================================
# HTML rendering — pure function, complete self-contained document
# ===========================================================================
def _css() -> str:
    """Embedded stylesheet. One column, single accent, print-ready (A4).

    Deliberately uses only block flow (no float/grid/flex for *content* order)
    so the linear reading order an ATS parser sees matches the visual order.
    A flex row is used only for the inline contact line, which degrades to a
    simple wrapped run of text and carries no semantic ordering risk.
    """
    return f"""
    :root {{
      --accent: {ACCENT};
      --ink: {INK};
      --muted: {INK_MUTED};
      --rule: {RULE};
      --page: {PAGE_BG};
    }}

    * {{ box-sizing: border-box; }}

    html, body {{
      margin: 0;
      padding: 0;
      background: #eceff3;
      color: var(--ink);
      font-family: Georgia, "Iowan Old Style", "Times New Roman", serif;
      font-size: 10.1pt;
      line-height: 1.36;
      -webkit-font-smoothing: antialiased;
    }}

    /* A4 sheet with tight-but-readable margins; centred for on-screen preview. */
    .sheet {{
      max-width: 200mm;
      margin: 14px auto;
      padding: 15mm 17mm 15mm 17mm;
      background: var(--page);
      box-shadow: 0 1px 3px rgba(20, 30, 45, 0.12);
    }}

    /* ---- Header: name + title + contact ---- */
    header.cv-head {{ margin-bottom: 11px; }}

    .cv-name {{
      font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif;
      font-size: 20pt;
      font-weight: 700;
      letter-spacing: 0.2px;
      color: var(--ink);
      margin: 0 0 1px 0;
      line-height: 1.1;
    }}

    .cv-title {{
      font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif;
      font-size: 10.6pt;
      font-weight: 500;
      letter-spacing: 0.4px;
      color: var(--accent);
      margin: 0 0 6px 0;
    }}

    .cv-contact {{
      font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif;
      font-size: 9pt;
      color: var(--muted);
      line-height: 1.45;
    }}
    .cv-contact a {{ color: var(--muted); text-decoration: none; }}
    .cv-contact a:hover {{ text-decoration: underline; }}
    .cv-contact .sep {{ color: var(--rule); padding: 0 6px; }}

    .cv-authz {{
      font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif;
      font-size: 8.8pt;
      color: var(--ink);
      margin-top: 4px;
    }}
    .cv-authz strong {{ color: var(--accent); font-weight: 600; }}

    /* ---- Section headings: small caps + subtle full-width rule ---- */
    section.cv-sec {{ margin-top: 11px; }}
    section.cv-sec:first-of-type {{ margin-top: 3px; }}

    h2.cv-h2 {{
      font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif;
      font-size: 9.6pt;
      font-weight: 700;
      letter-spacing: 1.4px;
      text-transform: uppercase;
      color: var(--accent);
      margin: 0 0 6px 0;
      padding-bottom: 3px;
      border-bottom: 1px solid var(--rule);
    }}

    /* ---- Summary ---- */
    .cv-summary {{ margin: 0; text-align: left; }}

    /* ---- Highlights ---- */
    ul.cv-highlights {{
      margin: 0;
      padding-left: 16px;
      list-style: none;
    }}
    ul.cv-highlights li {{
      position: relative;
      margin: 0 0 3px 0;
      padding-left: 4px;
    }}
    ul.cv-highlights li::before {{
      content: "";
      position: absolute;
      left: -12px;
      top: 0.6em;
      width: 4px;
      height: 4px;
      background: var(--accent);
      border-radius: 50%;
    }}

    /* ---- Skills: definition-style rows, NOT a layout table ---- */
    .cv-skill-row {{ margin: 0 0 4px 0; }}
    .cv-skill-row:last-child {{ margin-bottom: 0; }}
    .cv-skill-group {{
      font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif;
      font-weight: 700;
      font-size: 9.3pt;
      color: var(--ink);
    }}
    .cv-skill-list {{ color: var(--ink); }}

    /* ---- Experience ---- */
    .cv-job {{ margin: 0 0 8px 0; }}
    .cv-job:last-child {{ margin-bottom: 0; }}

    .cv-job-head {{ margin-bottom: 2px; }}
    .cv-job-role {{
      font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif;
      font-size: 10.4pt;
      font-weight: 700;
      color: var(--ink);
    }}
    .cv-job-company {{
      font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif;
      font-size: 10pt;
      font-weight: 600;
      color: var(--accent);
    }}
    .cv-job-meta {{
      font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif;
      font-size: 8.8pt;
      color: var(--muted);
      margin-top: 1px;
    }}

    ul.cv-bullets {{
      margin: 3px 0 0 0;
      padding-left: 16px;
      list-style: none;
    }}
    ul.cv-bullets li {{
      position: relative;
      margin: 0 0 3px 0;
    }}
    ul.cv-bullets li::before {{
      content: "";
      position: absolute;
      left: -12px;
      top: 0.62em;
      width: 3.5px;
      height: 3.5px;
      background: var(--muted);
      border-radius: 50%;
    }}

    /* ---- Education ---- */
    .cv-edu {{ margin: 0 0 5px 0; }}
    .cv-edu:last-child {{ margin-bottom: 0; }}
    .cv-edu-degree {{
      font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif;
      font-weight: 700;
      font-size: 10pt;
      color: var(--ink);
    }}
    .cv-edu-inst {{ color: var(--accent); font-weight: 600; }}
    .cv-edu-meta {{
      font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif;
      font-size: 8.8pt;
      color: var(--muted);
    }}
    .cv-edu-detail {{ font-size: 9.6pt; margin-top: 1px; }}

    /* ---- Simple comma/inline runs (certs, languages) ---- */
    .cv-inline {{ margin: 0; }}
    .cv-lang-item {{ white-space: nowrap; }}
    .cv-lang-level {{ color: var(--muted); }}

    /* ---- Print / PDF rules: real A4, no shadow, keep job blocks intact ---- */
    @page {{ size: A4; margin: 13mm 14mm; }}
    @media print {{
      html, body {{ background: #fff; font-size: 9.9pt; }}
      .sheet {{
        max-width: none;
        margin: 0;
        padding: 0;
        box-shadow: none;
      }}
      /* Keep each job/edu block whole; let long sections flow across pages. */
      .cv-job, .cv-edu {{ page-break-inside: avoid; }}
      h2.cv-h2 {{ page-break-after: avoid; }}
      a {{ color: var(--muted); }}
    }}
    """.strip()


def _render_header(contact: dict[str, Any]) -> str:
    name = _esc(_clean(contact.get("name")) or "Name")
    title = _clean(contact.get("title"))

    # Contact line: real text, plain separators (no icon glyphs — ATS-safe).
    bits: list[str] = []
    email = _clean(contact.get("email"))
    if email:
        bits.append(f'<a href="mailto:{_esc(email)}">{_esc(email)}</a>')
    phone = _clean(contact.get("phone"))
    if phone:
        tel = re.sub(r"[^\d+]", "", phone)
        bits.append(f'<a href="tel:{_esc(tel)}">{_esc(phone)}</a>')
    location = _clean(contact.get("location"))
    if location:
        bits.append(_esc(location))

    links = contact.get("links") or []
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, dict):
                continue
            url = _normalise_url(link.get("url", ""))
            if not url:
                continue
            text = _display_link(link.get("label", ""), url)
            bits.append(f'<a href="{_esc(url)}">{_esc(text)}</a>')

    sep = '<span class="sep">&middot;</span>'
    contact_line = sep.join(bits)

    authz = _clean(contact.get("work_authorization"))
    authz_html = (
        f'\n      <div class="cv-authz"><strong>Work authorisation:</strong> '
        f"{_esc(authz)}</div>"
        if authz
        else ""
    )

    title_html = f'\n      <p class="cv-title">{_esc(title)}</p>' if title else ""

    return (
        '    <header class="cv-head">\n'
        f'      <h1 class="cv-name">{name}</h1>'
        f"{title_html}\n"
        f'      <div class="cv-contact">{contact_line}</div>'
        f"{authz_html}\n"
        "    </header>"
    )


def _section(title: str, body: str) -> str:
    if not body.strip():
        return ""
    return (
        '    <section class="cv-sec">\n'
        f'      <h2 class="cv-h2">{_esc(title)}</h2>\n'
        f"{body}\n"
        "    </section>"
    )


def _render_summary(summary: str) -> str:
    summary = _clean(summary)
    if not summary:
        return ""
    return _section("Summary", f'      <p class="cv-summary">{_esc(summary)}</p>')


def _render_highlights(highlights: Any) -> str:
    if not isinstance(highlights, list):
        return ""
    items = [_clean(h) for h in highlights if _clean(h)]
    if not items:
        return ""
    lis = "\n".join(f"        <li>{_esc(it)}</li>" for it in items)
    return _section("Key Highlights", f'      <ul class="cv-highlights">\n{lis}\n      </ul>')


def _render_skills(skills_grouped: Any) -> str:
    if not isinstance(skills_grouped, list):
        return ""
    rows: list[str] = []
    for grp in skills_grouped:
        if not isinstance(grp, dict):
            continue
        group = _clean(grp.get("group"))
        skills = grp.get("skills") or []
        if isinstance(skills, list):
            names = [_clean(s) for s in skills if _clean(s)]
        else:
            names = []
        if not names:
            continue
        listed = ", ".join(_esc(n) for n in names)
        if group:
            rows.append(
                '      <p class="cv-skill-row">'
                f'<span class="cv-skill-group">{_esc(group)}:</span> '
                f'<span class="cv-skill-list">{listed}</span></p>'
            )
        else:
            rows.append(f'      <p class="cv-skill-row"><span class="cv-skill-list">{listed}</span></p>')
    if not rows:
        return ""
    return _section("Skills", "\n".join(rows))


def _render_experience(experience: Any) -> str:
    if not isinstance(experience, list):
        return ""
    jobs: list[str] = []
    for job in experience:
        if not isinstance(job, dict):
            continue
        company = _clean(job.get("company"))
        title = _clean(job.get("title"))
        dates = _clean(job.get("dates"))
        location = _clean(job.get("location"))
        bullets = job.get("bullets") or []
        bullet_items = [_clean(b) for b in bullets if isinstance(bullets, list) and _clean(b)]

        # Role line then company line keeps reading order ATS-friendly.
        head_parts = []
        if title:
            head_parts.append(f'<span class="cv-job-role">{_esc(title)}</span>')
        if company:
            sep = " &mdash; " if title else ""
            head_parts.append(f'{sep}<span class="cv-job-company">{_esc(company)}</span>')
        head = "".join(head_parts)

        meta_bits = [b for b in (dates, location) if b]
        meta = (
            f'\n        <div class="cv-job-meta">{_esc(" · ".join(meta_bits))}</div>'
            if meta_bits
            else ""
        )

        bullets_html = ""
        if bullet_items:
            lis = "\n".join(f"          <li>{_esc(b)}</li>" for b in bullet_items)
            bullets_html = f'\n        <ul class="cv-bullets">\n{lis}\n        </ul>'

        jobs.append(
            '      <div class="cv-job">\n'
            f'        <div class="cv-job-head">{head}</div>'
            f"{meta}"
            f"{bullets_html}\n"
            "      </div>"
        )
    if not jobs:
        return ""
    return _section("Experience", "\n".join(jobs))


def _render_education(education: Any) -> str:
    if not isinstance(education, list):
        return ""
    items: list[str] = []
    for edu in education:
        if not isinstance(edu, dict):
            continue
        institution = _clean(edu.get("institution"))
        degree = _clean(edu.get("degree"))
        dates = _clean(edu.get("dates"))
        details = _clean(edu.get("details"))

        line_parts = []
        if degree:
            line_parts.append(f'<span class="cv-edu-degree">{_esc(degree)}</span>')
        if institution:
            sep = " &mdash; " if degree else ""
            line_parts.append(f'{sep}<span class="cv-edu-inst">{_esc(institution)}</span>')
        line = "".join(line_parts)

        meta = f'\n        <div class="cv-edu-meta">{_esc(dates)}</div>' if dates else ""
        detail = f'\n        <div class="cv-edu-detail">{_esc(details)}</div>' if details else ""
        items.append(
            '      <div class="cv-edu">\n'
            f"        <div>{line}</div>"
            f"{meta}"
            f"{detail}\n"
            "      </div>"
        )
    if not items:
        return ""
    return _section("Education", "\n".join(items))


def _render_projects(projects: Any) -> str:
    if not isinstance(projects, list):
        return ""
    items: list[str] = []
    for proj in projects:
        if isinstance(proj, dict):
            name = _clean(proj.get("name"))
            details = _clean(proj.get("details"))
        else:
            name, details = _clean(proj), ""
        if not (name or details):
            continue
        # Reuse the education classes so projects match the rest of the document.
        name_html = (
            f'<span class="cv-edu-degree">{_esc(name)}</span>' if name else ""
        )
        detail_html = (
            f'\n        <div class="cv-edu-detail">{_esc(details)}</div>'
            if details
            else ""
        )
        items.append(
            '      <div class="cv-edu">\n'
            f"        <div>{name_html}</div>"
            f"{detail_html}\n"
            "      </div>"
        )
    if not items:
        return ""
    return _section("Projects", "\n".join(items))


def _render_certifications(certs: Any) -> str:
    if not isinstance(certs, list):
        return ""
    items = [_clean(c) for c in certs if _clean(c)]
    if not items:
        return ""
    body = ", ".join(_esc(c) for c in items)
    return _section("Certifications", f'      <p class="cv-inline">{body}</p>')


def _render_languages(langs: Any) -> str:
    if not isinstance(langs, list):
        return ""
    parts: list[str] = []
    for lang in langs:
        if isinstance(lang, dict):
            name = _clean(lang.get("name"))
            level = _clean(lang.get("level"))
        else:
            name, level = _clean(lang), ""
        if not name:
            continue
        if level:
            parts.append(
                f'<span class="cv-lang-item">{_esc(name)} '
                f'<span class="cv-lang-level">({_esc(level)})</span></span>'
            )
        else:
            parts.append(f'<span class="cv-lang-item">{_esc(name)}</span>')
    if not parts:
        return ""
    body = ", ".join(parts)
    return _section("Languages", f'      <p class="cv-inline">{body}</p>')


def render_html(tailored: dict[str, Any]) -> str:
    """Return a complete, self-contained HTML document for the tailored CV.

    Pure function: no I/O, no globals mutated. ATS-safe (one linear column, no
    layout tables, no icon glyphs, real selectable text), single accent colour,
    real typographic hierarchy.
    """
    if not isinstance(tailored, dict):
        raise TypeError("render_html expects a dict (tailored_cv schema)")

    contact = tailored.get("contact") or {}
    if not isinstance(contact, dict):
        contact = {}

    page_name = _clean(contact.get("name")) or "Curriculum Vitae"

    sections = "\n".join(
        s
        for s in (
            _render_summary(tailored.get("summary", "")),
            _render_highlights(tailored.get("highlights")),
            _render_skills(tailored.get("skills_grouped")),
            _render_experience(tailored.get("experience")),
            _render_projects(tailored.get("projects")),
            _render_education(tailored.get("education")),
            _render_certifications(tailored.get("certifications")),
            _render_languages(tailored.get("languages")),
        )
        if s
    )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{_esc(page_name)} — CV</title>\n"
        '  <meta name="generator" content="render_cv.py">\n'
        f'  <meta name="schema-version" content="{_esc(SCHEMA_VERSION)}">\n'
        "  <style>\n"
        f"{_css()}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <main class="sheet">\n'
        f"{_render_header(contact)}\n"
        f"{sections}\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def write_html(tailored: dict[str, Any], out_path: Path) -> Path:
    """Render and write the HTML document. Returns the written path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(tailored), encoding="utf-8")
    return out_path


# ===========================================================================
# PDF rendering — graceful three-backend degradation
# ===========================================================================
def _pdf_via_weasyprint(html: str, out_path: Path) -> bool:
    """Try weasyprint. Return True on success, False if unavailable.

    Note: when weasyprint is pip-installed but its native libraries
    (pango/cairo/gdk-pixbuf) are missing, importing it emits a warning via its
    own logger and then raises ImportError. We catch the raise and fall through
    cleanly to the next backend; the logger warning is weasyprint's own and is
    harmless.
    """
    try:
        from weasyprint import HTML  # type: ignore
    except Exception:  # noqa: BLE001 - not installed / native libs missing
        return False
    try:
        HTML(string=html, base_url=str(out_path.parent)).write_pdf(str(out_path))
    except Exception as exc:  # noqa: BLE001 - render error is recoverable -> next backend
        print(f"[render_cv] weasyprint present but failed: {exc}", file=sys.stderr)
        return False
    return out_path.exists() and out_path.stat().st_size > 0


def _pdf_via_wkhtmltopdf(html: str, out_path: Path) -> bool:
    """Try wkhtmltopdf via subprocess if it is on PATH."""
    exe = shutil.which("wkhtmltopdf")
    if not exe:
        return False
    tmp_html = out_path.with_suffix(".src.html")
    try:
        tmp_html.write_text(html, encoding="utf-8")
        proc = subprocess.run(
            [
                exe,
                "--quiet",
                "--encoding", "utf-8",
                "--enable-local-file-access",
                "--page-size", "A4",
                "--margin-top", "16mm",
                "--margin-bottom", "16mm",
                "--margin-left", "15mm",
                "--margin-right", "15mm",
                str(tmp_html),
                str(out_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        if proc.returncode != 0:
            print(
                f"[render_cv] wkhtmltopdf exited {proc.returncode}: "
                f"{proc.stderr.decode('utf-8', 'replace').strip()[:300]}",
                file=sys.stderr,
            )
            return False
    except Exception as exc:  # noqa: BLE001 - recoverable -> next backend
        print(f"[render_cv] wkhtmltopdf failed: {exc}", file=sys.stderr)
        return False
    finally:
        try:
            tmp_html.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
    return out_path.exists() and out_path.stat().st_size > 0


# --- reportlab fallback: regenerate a clean PDF from extracted text ---------
def _strip_tags(fragment: str) -> str:
    """Convert a small HTML fragment to plain text (entities decoded)."""
    text = re.sub(r"<[^>]+>", "", fragment)
    return _html.unescape(text).strip()


def _text_blocks_from_tailored(tailored: dict[str, Any]) -> list[tuple[str, str]]:
    """Flatten the tailored CV into (style, text) blocks for the plain fallback.

    style in {"name","title","contact","authz","h2","summary","bullet",
              "skill","job-head","job-meta","edu","inline"}.
    """
    blocks: list[tuple[str, str]] = []
    contact = tailored.get("contact") or {}
    if isinstance(contact, dict):
        if _clean(contact.get("name")):
            blocks.append(("name", _clean(contact.get("name"))))
        if _clean(contact.get("title")):
            blocks.append(("title", _clean(contact.get("title"))))
        cbits = []
        for key in ("email", "phone", "location"):
            if _clean(contact.get(key)):
                cbits.append(_clean(contact.get(key)))
        for link in contact.get("links") or []:
            if isinstance(link, dict):
                url = _normalise_url(link.get("url", ""))
                if url:
                    cbits.append(_display_link(link.get("label", ""), url))
        if cbits:
            blocks.append(("contact", "  ·  ".join(cbits)))
        if _clean(contact.get("work_authorization")):
            blocks.append(("authz", "Work authorisation: " + _clean(contact.get("work_authorization"))))

    if _clean(tailored.get("summary")):
        blocks.append(("h2", "Summary"))
        blocks.append(("summary", _clean(tailored.get("summary"))))

    highlights = tailored.get("highlights")
    if isinstance(highlights, list):
        hs = [_clean(h) for h in highlights if _clean(h)]
        if hs:
            blocks.append(("h2", "Key Highlights"))
            blocks.extend(("bullet", h) for h in hs)

    skills_grouped = tailored.get("skills_grouped")
    if isinstance(skills_grouped, list):
        rows = []
        for grp in skills_grouped:
            if not isinstance(grp, dict):
                continue
            group = _clean(grp.get("group"))
            names = [_clean(s) for s in (grp.get("skills") or []) if _clean(s)]
            if not names:
                continue
            rows.append(f"{group}: {', '.join(names)}" if group else ", ".join(names))
        if rows:
            blocks.append(("h2", "Skills"))
            blocks.extend(("skill", r) for r in rows)

    experience = tailored.get("experience")
    if isinstance(experience, list):
        added_head = False
        for job in experience:
            if not isinstance(job, dict):
                continue
            title = _clean(job.get("title"))
            company = _clean(job.get("company"))
            dates = _clean(job.get("dates"))
            location = _clean(job.get("location"))
            bullets = [_clean(b) for b in (job.get("bullets") or []) if _clean(b)]
            head = " — ".join([p for p in (title, company) if p])
            meta = " · ".join([p for p in (dates, location) if p])
            if not (head or meta or bullets):
                continue
            if not added_head:
                blocks.append(("h2", "Experience"))
                added_head = True
            if head:
                blocks.append(("job-head", head))
            if meta:
                blocks.append(("job-meta", meta))
            blocks.extend(("bullet", b) for b in bullets)

    projects = tailored.get("projects")
    if isinstance(projects, list):
        added_head = False
        for proj in projects:
            if isinstance(proj, dict):
                name = _clean(proj.get("name"))
                details = _clean(proj.get("details"))
            else:
                name, details = _clean(proj), ""
            if not (name or details):
                continue
            if not added_head:
                blocks.append(("h2", "Projects"))
                added_head = True
            if name:
                blocks.append(("edu", name))
            if details:
                blocks.append(("inline", details))

    education = tailored.get("education")
    if isinstance(education, list):
        added_head = False
        for edu in education:
            if not isinstance(edu, dict):
                continue
            degree = _clean(edu.get("degree"))
            institution = _clean(edu.get("institution"))
            dates = _clean(edu.get("dates"))
            details = _clean(edu.get("details"))
            line = " — ".join([p for p in (degree, institution) if p])
            if not (line or dates or details):
                continue
            if not added_head:
                blocks.append(("h2", "Education"))
                added_head = True
            if line:
                blocks.append(("edu", line))
            if dates:
                blocks.append(("job-meta", dates))
            if details:
                blocks.append(("inline", details))

    certs = tailored.get("certifications")
    if isinstance(certs, list):
        cs = [_clean(c) for c in certs if _clean(c)]
        if cs:
            blocks.append(("h2", "Certifications"))
            blocks.append(("inline", ", ".join(cs)))

    langs = tailored.get("languages")
    if isinstance(langs, list):
        parts = []
        for lang in langs:
            if isinstance(lang, dict):
                name, level = _clean(lang.get("name")), _clean(lang.get("level"))
            else:
                name, level = _clean(lang), ""
            if name:
                parts.append(f"{name} ({level})" if level else name)
        if parts:
            blocks.append(("h2", "Languages"))
            blocks.append(("inline", ", ".join(parts)))

    return blocks


def _pdf_via_reportlab(html: str, out_path: Path, tailored: Optional[dict[str, Any]]) -> bool:
    """Plain, dependable reportlab fallback.

    Prefers structured ``tailored`` (cleaner output); otherwise reconstructs
    text from the HTML so the function still honours its (html, out_path)
    contract when called standalone.
    """
    try:
        from reportlab.lib.colors import HexColor  # type: ignore
        from reportlab.lib.enums import TA_LEFT  # type: ignore
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.lib.styles import ParagraphStyle  # type: ignore
        from reportlab.lib.units import mm  # type: ignore
        from reportlab.platypus import (  # type: ignore
            HRFlowable,
            ListFlowable,
            ListItem,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
        )
    except Exception:  # noqa: BLE001 - reportlab not installed
        return False

    if tailored is not None:
        blocks = _text_blocks_from_tailored(tailored)
    else:
        # Derive rough blocks from the rendered HTML body as a last resort.
        body = re.search(r"<body[^>]*>(.*)</body>", html, re.DOTALL | re.IGNORECASE)
        chunk = body.group(1) if body else html
        blocks = [("summary", _strip_tags(chunk))]

    accent = HexColor(ACCENT)
    ink = HexColor(INK)
    muted = HexColor(INK_MUTED)
    rule = HexColor(RULE)

    s_name = ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=20,
                            leading=23, textColor=ink, spaceAfter=1)
    s_title = ParagraphStyle("title", fontName="Helvetica", fontSize=11,
                             leading=14, textColor=accent, spaceAfter=6)
    s_contact = ParagraphStyle("contact", fontName="Helvetica", fontSize=8.5,
                               leading=12, textColor=muted, spaceAfter=2)
    s_authz = ParagraphStyle("authz", fontName="Helvetica", fontSize=8.5,
                             leading=12, textColor=ink, spaceAfter=4)
    s_h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=9.5,
                          leading=12, textColor=accent, spaceBefore=10,
                          spaceAfter=3, alignment=TA_LEFT)
    s_body = ParagraphStyle("body", fontName="Times-Roman", fontSize=9.6,
                            leading=13.5, textColor=ink, spaceAfter=2)
    s_skill = ParagraphStyle("skill", parent=s_body, spaceAfter=3)
    s_jobhead = ParagraphStyle("jobhead", fontName="Helvetica-Bold", fontSize=10,
                               leading=13, textColor=ink, spaceBefore=4, spaceAfter=0)
    s_jobmeta = ParagraphStyle("jobmeta", fontName="Helvetica", fontSize=8.5,
                               leading=11, textColor=muted, spaceAfter=2)
    s_bullet = ParagraphStyle("bullet", parent=s_body, spaceAfter=2)

    def esc(t: str) -> str:
        return _html.escape(t, quote=False)

    story: list[Any] = []
    pending_bullets: list[str] = []

    def flush_bullets() -> None:
        if not pending_bullets:
            return
        items = [
            ListItem(Paragraph(esc(b), s_bullet), leftIndent=10, value=None)
            for b in pending_bullets
        ]
        story.append(
            ListFlowable(
                items,
                bulletType="bullet",
                bulletColor=muted,
                bulletFontSize=5,
                start="circle",
                leftIndent=12,
            )
        )
        pending_bullets.clear()

    for style, text in blocks:
        if style != "bullet":
            flush_bullets()
        if style == "name":
            story.append(Paragraph(esc(text), s_name))
        elif style == "title":
            story.append(Paragraph(esc(text), s_title))
        elif style == "contact":
            story.append(Paragraph(esc(text), s_contact))
        elif style == "authz":
            story.append(Paragraph(esc(text), s_authz))
        elif style == "h2":
            story.append(Paragraph(esc(text.upper()), s_h2))
            story.append(HRFlowable(width="100%", thickness=0.6, color=rule,
                                    spaceBefore=1, spaceAfter=5))
        elif style == "summary":
            story.append(Paragraph(esc(text), s_body))
        elif style == "skill":
            story.append(Paragraph(esc(text), s_skill))
        elif style == "job-head":
            story.append(Paragraph(esc(text), s_jobhead))
        elif style == "job-meta":
            story.append(Paragraph(esc(text), s_jobmeta))
        elif style == "edu":
            story.append(Paragraph(esc(text), s_jobhead))
        elif style == "inline":
            story.append(Paragraph(esc(text), s_body))
        elif style == "bullet":
            pending_bullets.append(text)
        else:
            story.append(Paragraph(esc(text), s_body))
    flush_bullets()

    try:
        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=A4,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            title="CV",
        )
        doc.build(story)
    except Exception as exc:  # noqa: BLE001
        print(f"[render_cv] reportlab failed: {exc}", file=sys.stderr)
        return False
    return out_path.exists() and out_path.stat().st_size > 0


def _pdf_via_stdlib(html: str, out_path: Path, tailored: Optional[dict[str, Any]]) -> bool:
    """Last-resort, dependency-free PDF writer (pure stdlib).

    None of the three real backends (weasyprint/wkhtmltopdf/reportlab) may be
    installed on a given machine. The contract requires the PDF step to degrade
    gracefully and never crash the pipeline, so this backend ALWAYS produces a
    valid, openable PDF using nothing but the standard library. The output is a
    plain, single-font text layout (Helvetica, built-in PDF base font) — not
    pretty, but readable and a real PDF. It is intentionally last in the order
    so the nicer backends win whenever they are present.
    """
    # Build the same flattened text blocks the reportlab fallback uses, so the
    # content matches; fall back to stripping the HTML body if no structured
    # data was provided.
    if tailored is not None:
        blocks = _text_blocks_from_tailored(tailored)
    else:
        body = re.search(r"<body[^>]*>(.*)</body>", html, re.DOTALL | re.IGNORECASE)
        chunk = body.group(1) if body else html
        blocks = [("summary", _strip_tags(chunk))]

    # --- lay text out into lines on A4 (in PDF points; 1pt = 1/72 inch) -------
    page_w, page_h = 595.276, 841.890  # A4 in points
    left_margin, right_margin = 56.0, 56.0
    top_margin, bottom_margin = 56.0, 56.0
    usable_w = page_w - left_margin - right_margin

    # Per-style font size and leading. Helvetica metrics ~0.5*size avg char w.
    style_size = {
        "name": 18.0, "title": 12.0, "contact": 9.0, "authz": 9.0,
        "h2": 11.0, "summary": 10.0, "skill": 10.0, "job-head": 10.5,
        "job-meta": 9.0, "edu": 10.5, "inline": 10.0, "bullet": 10.0,
    }

    def wrap(text: str, size: float, indent: float = 0.0) -> list[str]:
        avail = usable_w - indent
        max_chars = max(8, int(avail / (size * 0.5)))
        words = text.split()
        lines: list[str] = []
        cur = ""
        for w in words:
            cand = (cur + " " + w).strip()
            if len(cand) <= max_chars:
                cur = cand
            else:
                if cur:
                    lines.append(cur)
                # very long single token: hard-split
                while len(w) > max_chars:
                    lines.append(w[:max_chars])
                    w = w[max_chars:]
                cur = w
        if cur:
            lines.append(cur)
        return lines or [""]

    # Map the handful of common non-Latin-1 punctuation marks we actually emit
    # (em/en dash, smart quotes, ellipsis, bullet) to their WinAnsiEncoding code
    # points so they render as the right glyph instead of "?" under latin-1.
    _winansi = {
        "—": "\x97",  # em dash —
        "–": "\x96",  # en dash –
        "‘": "\x91",  # ‘
        "’": "\x92",  # ’
        "“": "\x93",  # “
        "”": "\x94",  # ”
        "…": "\x85",  # …
        "•": "\x95",  # •
        "·": "\xb7",  # middle dot ·
        "²": "\xb2",  # ²
    }

    def to_winansi(s: str) -> str:
        for uni, win in _winansi.items():
            s = s.replace(uni, win)
        return s

    def pdf_escape(s: str) -> str:
        s = to_winansi(s)
        return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    # Assemble drawing ops, paginating when we run off the bottom of a page.
    pages: list[list[tuple[float, float, float, str]]] = []  # (x, y, size, text)
    current: list[tuple[float, float, float, str]] = []
    y = page_h - top_margin

    def new_page() -> None:
        nonlocal current, y
        if current:
            pages.append(current)
        current = []
        y = page_h - top_margin

    for style, text in blocks:
        size = style_size.get(style, 10.0)
        indent = 14.0 if style == "bullet" else 0.0
        prefix = "- " if style == "bullet" else ""
        gap_before = 6.0 if style in ("h2", "job-head", "name") else 2.0
        text = pdf_escape(text)
        lines = wrap(prefix + text if prefix else text, size, indent)
        # space before block
        y -= gap_before
        for ln in lines:
            line_h = size * 1.32
            if y - line_h < bottom_margin:
                new_page()
            y -= line_h
            current.append((left_margin + indent, y, size, ln))
        y -= 1.5  # small space after block
    if current:
        pages.append(current)
    if not pages:
        pages = [[(left_margin, page_h - top_margin, 10.0, "")]]

    # --- emit a minimal but valid multi-page PDF ------------------------------
    objects: list[bytes] = []

    def add_obj(body: bytes) -> int:
        objects.append(body)
        return len(objects)  # 1-based object number

    # Reserve: 1=Catalog, 2=Pages, then per page (Page + Contents), then Font.
    font_num_placeholder = "FONT"
    page_obj_nums: list[int] = []
    content_obj_nums: list[int] = []

    # We need object numbers before writing the Pages object. Pre-compute layout:
    # obj1 catalog, obj2 pages, font last. Pages and contents in between.
    n_pages = len(pages)
    catalog_num = 1
    pages_num = 2
    first_page_num = 3
    # pages occupy: page i -> page obj (3 + 2i), contents obj (4 + 2i)
    for i in range(n_pages):
        page_obj_nums.append(first_page_num + 2 * i)
        content_obj_nums.append(first_page_num + 2 * i + 1)
    font_num = first_page_num + 2 * n_pages

    # Build content streams.
    content_streams: list[bytes] = []
    for ops in pages:
        parts = ["BT", "/F1 10 Tf"]
        prev_size = None
        for (x, yy, size, text) in ops:
            if size != prev_size:
                parts.append(f"/F1 {size:.2f} Tf")
                prev_size = size
            parts.append(f"1 0 0 1 {x:.2f} {yy:.2f} Tm ({text}) Tj")
        parts.append("ET")
        content_streams.append(("\n".join(parts)).encode("latin-1", "replace"))

    # Now write objects in numeric order 1..font_num.
    body_chunks: list[bytes] = []
    offsets: list[int] = []
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    cursor = len(header)

    def write_obj(num: int, payload: bytes) -> None:
        nonlocal cursor
        while len(offsets) < num:
            offsets.append(0)
        chunk = f"{num} 0 obj\n".encode("latin-1") + payload + b"\nendobj\n"
        offsets[num - 1] = cursor
        body_chunks.append(chunk)
        cursor += len(chunk)

    # 1: Catalog
    write_obj(catalog_num, f"<< /Type /Catalog /Pages {pages_num} 0 R >>".encode("latin-1"))
    # 2: Pages
    kids = " ".join(f"{n} 0 R" for n in page_obj_nums)
    write_obj(
        pages_num,
        f"<< /Type /Pages /Count {n_pages} /Kids [{kids}] >>".encode("latin-1"),
    )
    # per-page Page + Contents
    for i in range(n_pages):
        pnum = page_obj_nums[i]
        cnum = content_obj_nums[i]
        page_dict = (
            f"<< /Type /Page /Parent {pages_num} 0 R "
            f"/MediaBox [0 0 {page_w:.3f} {page_h:.3f}] "
            f"/Resources << /Font << /F1 {font_num} 0 R >> >> "
            f"/Contents {cnum} 0 R >>"
        ).encode("latin-1")
        write_obj(pnum, page_dict)
        stream = content_streams[i]
        cobj = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream"
        )
        write_obj(cnum, cobj)
    # font
    write_obj(
        font_num,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    )

    # xref + trailer
    n_objs = font_num
    xref_offset = cursor
    xref_lines = [b"xref", f"0 {n_objs + 1}".encode("latin-1"), b"0000000000 65535 f "]
    for i in range(n_objs):
        xref_lines.append(f"{offsets[i]:010d} 00000 n ".encode("latin-1"))
    xref = b"\n".join(xref_lines) + b"\n"
    trailer = (
        f"trailer\n<< /Size {n_objs + 1} /Root {catalog_num} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("latin-1")

    try:
        with open(out_path, "wb") as fh:
            fh.write(header)
            for chunk in body_chunks:
                fh.write(chunk)
            fh.write(xref)
            fh.write(trailer)
    except OSError as exc:
        print(f"[render_cv] stdlib PDF writer failed: {exc}", file=sys.stderr)
        return False
    return out_path.exists() and out_path.stat().st_size > 0


def render_pdf(
    html: str,
    out_path: Path,
    *,
    tailored: Optional[dict[str, Any]] = None,
) -> tuple[Path, str]:
    """Write a PDF from ``html``. Returns (path, backend_used).

    backend_used is one of "weasyprint" | "wkhtmltopdf" | "reportlab" | "stdlib".
    Backend order: weasyprint (import) -> wkhtmltopdf (subprocess, if on PATH)
    -> reportlab plain-text fallback -> a dependency-free stdlib PDF writer.
    The stdlib backend always succeeds, so a missing PDF library degrades the
    *quality* of the PDF but NEVER crashes the pipeline (per CONTRACT.md §4).
    Only raises if even the stdlib writer fails to produce a file (e.g. the
    output path is unwritable — a genuine I/O error).

    ``tailored`` is an optional fast path so the reportlab/stdlib fallbacks can
    render from structured data; the public contract is satisfied by
    (html, out_path) alone.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if _pdf_via_weasyprint(html, out_path):
        return out_path, "weasyprint"
    if _pdf_via_wkhtmltopdf(html, out_path):
        return out_path, "wkhtmltopdf"
    if _pdf_via_reportlab(html, out_path, tailored):
        return out_path, "reportlab"
    if _pdf_via_stdlib(html, out_path, tailored):
        return out_path, "stdlib"

    raise RuntimeError(
        f"Could not write a PDF to {out_path} (even the dependency-free stdlib "
        "writer failed — check the output path is writable)."
    )


# ===========================================================================
# Top-level orchestration
# ===========================================================================
def render_cv(
    tailored: "dict[str, Any] | Path",
    out_dir: Path,
) -> dict[str, "Path | str"]:
    """Render both artefacts into ``out_dir``.

    Accepts an in-memory tailored dict (pipeline fast path) or a path to a
    ``tailored_cv.json`` (standalone CLI) — output is identical.
    Returns {"html": Path, "pdf": Path, "pdf_backend": str}.
    """
    data = _as_dict(tailored)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    html_path = write_html(data, out_dir / "cv.html")
    html_str = render_html(data)
    pdf_path, backend = render_pdf(html_str, out_dir / "cv.pdf", tailored=data)

    return {"html": html_path, "pdf": pdf_path, "pdf_backend": backend}


# ===========================================================================
# Self-test sample (guarded under --self-test)
# ===========================================================================
def _sample_tailored_cv() -> dict[str, Any]:
    """A synthetic, schema-valid tailored_cv.json for the self-test render path.

    Deliberately fictional: the name, employers, and contact details are obvious
    placeholders ("Self Test Sample", "Example Corp", example.com) so nobody
    mistakes this fixture for the real candidate in config/cv_master.json. It
    exercises every render section (summary, skills, experience, education,
    highlights, languages) so --self-test covers the full layout.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "company": "Example Corp",
            "role": "Sample Role",
            "model_used": "mock",
            "generated_at": "2026-01-01T00:00:00Z",
        },
        "contact": {
            "name": "Self Test Sample",
            "title": "Sample Role",
            "email": "selftest@example.com",
            "phone": "+00 00 000 0000",
            "location": "Sample City",
            "links": [
                {"label": "Example", "url": "https://example.com"},
                {"label": "Source", "url": "https://example.com/source"},
            ],
            "work_authorization": "Synthetic self-test record - not real candidate data.",
        },
        "summary": (
            "Synthetic self-test record used to exercise the renderer; this is "
            "not real candidate data. The paragraph is intentionally long so it "
            "tests line wrapping, spacing, and the summary block, and it includes "
            "a figure like 42% and a value such as 95ms so numeric glyphs render "
            "correctly across both the HTML and PDF backends."
        ),
        "skills_grouped": [
            {"group": "Group Alpha", "skills": [
                "Sample Skill One", "Sample Skill Two", "Sample Skill Three"]},
            {"group": "Group Beta", "skills": [
                "Placeholder A", "Placeholder B", "Placeholder C"]},
            {"group": "Group Gamma", "skills": [
                "Example Tool", "Example Framework", "Example Platform"]},
        ],
        "experience": [
            {
                "company": "Example Corp",
                "title": "Senior Sample Engineer",
                "dates": "Jan 2024 – Present",
                "location": "Sample City",
                "bullets": [
                    "Placeholder achievement written long enough to wrap onto a "
                    "second line, which exercises the bullet renderer and spacing.",
                    "Second placeholder bullet with a number (123) to check "
                    "numeric rendering.",
                    "Third placeholder bullet, kept short.",
                ],
            },
            {
                "company": "Sample Industries Inc.",
                "title": "Sample Engineer",
                "dates": "Jun 2021 – Dec 2023",
                "location": "Sample City",
                "bullets": [
                    "Placeholder bullet describing fictional work used only to "
                    "fill the experience section of the self-test fixture.",
                    "Another placeholder bullet for layout coverage.",
                ],
            },
        ],
        "education": [
            {
                "institution": "Example University",
                "degree": "BSc Sample Studies",
                "dates": "",
                "details": "Placeholder education entry for render coverage.",
            },
        ],
        "highlights": [
            "Placeholder highlight one, with a figure like 42%.",
            "Placeholder highlight two for the highlights block.",
        ],
        "ats_keywords_used": [
            "sample keyword", "placeholder", "example", "self-test",
        ],
        "languages": [
            {"name": "English", "level": "fluent"},
            {"name": "Sample Language", "level": ""},
        ],
        "certifications": [],
        "fabrication_check": {"passed": True, "issues": []},
    }


def _self_test(out_dir: Path) -> int:
    """Render the bundled sample and report what was produced."""
    sample = _sample_tailored_cv()
    out_dir = Path(out_dir)
    print(f"[render_cv] self-test → {out_dir}")
    result = render_cv(sample, out_dir)
    html_path = Path(result["html"])
    pdf_path = Path(result["pdf"])
    backend = str(result["pdf_backend"])

    ok_html = html_path.exists() and html_path.stat().st_size > 0
    ok_pdf = pdf_path.exists() and pdf_path.stat().st_size > 0

    # Lightweight sanity: HTML must contain the name and be selectable text.
    html_text = html_path.read_text(encoding="utf-8") if ok_html else ""
    name_in_html = "Self Test Sample" in html_text
    no_layout_table = "<table" not in html_text.lower()

    print(f"  HTML written : {ok_html}  ({html_path})")
    print(f"  name present : {name_in_html}")
    print(f"  no <table>   : {no_layout_table}")
    print(f"  PDF written  : {ok_pdf}  ({pdf_path})")
    print(f"  PDF backend  : {backend}")

    passed = ok_html and ok_pdf and name_in_html and no_layout_table
    print(f"[render_cv] self-test {'PASSED' if passed else 'FAILED'}")
    return 0 if passed else 1


# ===========================================================================
# CLI
# ===========================================================================
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="render_cv.py",
        description="Render tailored_cv.json into a clean, ATS-safe cv.html + cv.pdf.",
    )
    p.add_argument("--in", dest="in_path", type=Path,
                   help="Path to tailored_cv.json")
    p.add_argument("--out-dir", dest="out_dir", type=Path,
                   help="Directory to write cv.html and cv.pdf into")
    p.add_argument("--self-test", action="store_true",
                   help="Render a bundled sample CV (no input file needed)")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.self_test:
        out_dir = args.out_dir or (OUTPUT_ROOT / "_self_test")
        return _self_test(out_dir)

    if not args.in_path or not args.out_dir:
        print("error: --in and --out-dir are required (or use --self-test)",
              file=sys.stderr)
        return 2

    if not args.in_path.exists():
        print(f"error: input not found: {args.in_path}", file=sys.stderr)
        return 2

    try:
        result = render_cv(args.in_path, args.out_dir)
    except Exception as exc:  # noqa: BLE001 - report cleanly, non-zero exit
        print(f"error: render failed: {exc}", file=sys.stderr)
        return 1

    html_path = Path(result["html"])
    pdf_path = Path(result["pdf"])
    backend = str(result["pdf_backend"])

    print(f"HTML : {html_path}")
    print(f"PDF  : {pdf_path}")
    print(f"PDF backend used: {backend}")

    ok = (
        html_path.exists() and html_path.stat().st_size > 0
        and pdf_path.exists() and pdf_path.stat().st_size > 0
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
