"""Domain-agnostic ATS keyword scorer.

Generalizes the old AI/ML-hardcoded matcher (scripts/cv_tailor.py's
SKILL_PATTERNS) into a cross-domain scorer: a curated multi-domain skill/tool
lexicon PLUS salient tokens mined from the JD itself (capitalised proper terms,
acronyms, and frequent domain nouns). Deterministic and fully unit-testable.

The ATS match score is the user's headline "how ready is this application"
signal: round(matched / total * 100). It is honest keyword coverage only and is
NEVER a reason to fabricate — keywords the user genuinely lacks are reported as
gaps in `missing_keywords`, not silently added to the CV.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

# A curated, cross-domain lexicon of skills / tools / methods. Multi-word entries
# are matched as phrases. Intentionally broad (software, data, cloud, product,
# design, marketing, finance, ops) so the scorer is not tied to any one field.
LEXICON: tuple[str, ...] = (
    # programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang",
    "rust", "ruby", "php", "scala", "kotlin", "swift", "r", "matlab", "sql",
    # web / frontend / backend
    "react", "angular", "vue", "node.js", "django", "flask", "spring", "rails",
    "html", "css", "rest", "graphql", "api", "microservices",
    # data / analytics
    "excel", "tableau", "power bi", "looker", "pandas", "numpy", "spark",
    "hadoop", "kafka", "airflow", "dbt", "snowflake", "databricks", "etl",
    "data analysis", "data engineering", "statistics", "a/b testing", "forecasting",
    # ml / ai
    "machine learning", "deep learning", "nlp", "computer vision", "pytorch",
    "tensorflow", "scikit-learn", "llm", "generative ai", "mlops",
    # cloud / devops
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
    "jenkins", "ci/cd", "git", "linux",
    # product / project / design
    "agile", "scrum", "jira", "figma", "roadmap", "stakeholder management",
    "user research", "wireframing", "prototyping", "project management",
    # marketing / sales / business
    "seo", "sem", "google analytics", "hubspot", "salesforce", "crm",
    "content marketing", "email marketing", "copywriting",
    # finance / ops
    "accounting", "financial modelling", "budgeting", "supply chain", "procurement",
)

# Common non-content words to drop when mining salient JD terms.
_STOPWORDS = frozenset("""
a an the and or of to in on for with at by from as is are be this that we you
your our their its it will who what which role team work working experience
years year ability strong excellent good knowledge skills skill including etc
use used using across within into out over per via job description
responsibilities requirements qualifications preferred plus must should would
could candidate about have has had will can new other more most such they them
""".split())

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/-]*")


def normalize(text: str) -> str:
    """Lowercase and keep alphanumerics plus the symbols that appear in real
    tech tokens (+, /, #, ., &, space, hyphen); collapse whitespace."""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9+/#.& -]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _contains(term: str, normalized: str) -> bool:
    """True when `term` occurs in already-normalized text on token boundaries.

    Uses custom boundaries (not \\b) so symbol-bearing tokens like 'c++',
    'ci/cd', 'node.js', 'a/b testing' match correctly, while a single letter
    like 'r' does not match inside 'react' or 'docker'. Plain alphabetic terms
    of length >= 3 also match a trailing plural 's' ('api' -> 'apis').
    """
    suffix = "s?" if (term.isalpha() and len(term) >= 3) else ""
    pattern = rf"(?<![a-z0-9]){re.escape(term)}{suffix}(?![a-z0-9])"
    return re.search(pattern, normalized) is not None


def _salient_terms(jd_text: str, exclude: set[str], limit: int) -> list[str]:
    """Mine salient single-word terms from the JD: non-stopword tokens ranked by
    frequency, boosted for acronyms (ALL-CAPS 2–5 chars) and Capitalised words.
    Deterministic: ties break alphabetically."""
    counts: Counter = Counter()
    salience: dict[str, int] = {}
    for w in _WORD_RE.findall(jd_text or ""):
        lw = w.lower().strip("./#-")
        if len(lw) < 3 or lw in _STOPWORDS or lw in exclude:
            continue
        counts[lw] += 1
        boost = 2 if (w.isupper() and 2 <= len(w) <= 5) else (1 if w[:1].isupper() else 0)
        salience[lw] = max(salience.get(lw, 0), boost)
    ranked = sorted(counts, key=lambda t: (-(counts[t] + salience[t]), t))
    return ranked[:limit]


def extract_keywords(jd_text: str, max_keywords: int = 40) -> list[str]:
    """Return the JD's keyword set: lexicon hits (in lexicon order) followed by
    salient mined terms, deduped, capped at max_keywords. Deterministic."""
    normalized = normalize(jd_text)
    keywords: list[str] = []
    seen: set[str] = set()
    for term in LEXICON:
        if term not in seen and _contains(term, normalized):
            keywords.append(term)
            seen.add(term)
            # Suppress this phrase's component words from salient mining so a
            # matched "a/b testing" doesn't also yield stray "testing"/"a/b".
            for part in re.split(r"[ /.+#-]+", term):
                if len(part) >= 3:
                    seen.add(part)
    for term in _salient_terms(jd_text, exclude=seen, limit=max_keywords):
        if term not in seen:
            keywords.append(term)
            seen.add(term)
    return keywords[:max_keywords]


def match_keywords(cv_text: str, keywords: list[str]) -> tuple[list[str], list[str]]:
    """Split `keywords` into (matched, missing) against the CV text, preserving
    the input order in each list."""
    norm = normalize(cv_text)
    matched: list[str] = []
    missing: list[str] = []
    for kw in keywords:
        (matched if _contains(kw, norm) else missing).append(kw)
    return matched, missing


def ats_score(matched_count: int, total: int) -> int:
    """round(matched / total * 100); 0 when there are no keywords."""
    if total <= 0:
        return 0
    return round(matched_count / total * 100)


def cv_text_from_tailored(tailored: dict[str, Any]) -> str:
    """Flatten a tailored_cv dict's human-readable fields into one text blob for
    keyword matching (title, summary, skill groups + skills, experience titles +
    bullets, highlights, ats_keywords_used)."""
    parts: list[str] = []
    contact = tailored.get("contact", {}) or {}
    parts.append(str(contact.get("title", "")))
    parts.append(str(tailored.get("summary", "")))
    for group in tailored.get("skills_grouped", []) or []:
        if isinstance(group, dict):
            parts.append(str(group.get("group", "")))
            parts.extend(str(s) for s in group.get("skills", []) or [])
    for entry in tailored.get("experience", []) or []:
        if isinstance(entry, dict):
            parts.append(str(entry.get("title", "")))
            parts.extend(str(b) for b in entry.get("bullets", []) or [])
    parts.extend(str(h) for h in tailored.get("highlights", []) or [])
    parts.extend(str(k) for k in tailored.get("ats_keywords_used", []) or [])
    return "\n".join(p for p in parts if p)


def build_ats_report(
    jd_text: str,
    cv_text: str,
    company: str,
    role: str,
    max_keywords: int = 40,
) -> dict[str, Any]:
    """Compute the ATS report: extract JD keywords, match against the CV, and
    package the score + matched/missing lists."""
    keywords = extract_keywords(jd_text, max_keywords)
    matched, missing = match_keywords(cv_text, keywords)
    total = len(keywords)
    return {
        "company": company,
        "role": role,
        "total_keywords": total,
        "matched_count": len(matched),
        "missing_count": len(missing),
        "match_score": ats_score(len(matched), total),
        "matched_keywords": matched,
        "missing_keywords": missing,
    }


def write_ats_report(report: dict[str, Any], out_dir: Path) -> Path:
    """Write ats_report.json into out_dir; return the path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "ats_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
