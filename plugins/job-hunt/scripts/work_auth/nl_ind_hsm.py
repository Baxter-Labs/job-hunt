"""nl-ind-hsm work-auth provider: check companies against the Dutch IND
recognised-sponsor register (highly-skilled migrants).

Ported from scripts/ind_sponsor_checker.py. The register is read from a CACHED
CSV inside the user's workspace ($JOB_HUNT_HOME/config/nl_ind_hsm_sponsors.csv);
tests populate that file directly, so annotation is fully offline. The live
re-download (download_ind_register) is behind an injectable `fetch` in refresh()
and is never called by tests.
"""

from __future__ import annotations

import csv
import re
import ssl
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from engine import workspace
from work_auth.base import DROP, FLAG, KEEP, WorkAuthProvider

IND_URLS = [
    "https://ind.nl/en/documents/public-register-regular-labour-and-highly-skilled-migrants.csv",
    "https://ind.nl/en/documents/public-register-recognised-sponsors/public-register-regular-labour-and-highly-skilled-migrants.csv",
]

REGISTER_FIELDNAMES = ["company_name", "careers_url", "category", "last_verified"]

DUTCH_SUFFIXES = re.compile(
    r"\b(b\.?v\.?|n\.?v\.?|v\.?o\.?f\.?|c\.?v\.?|u\.?a\.?|"
    r"coöperatief|cooperatief|holding|group|international|"
    r"netherlands|nederland|europe)\b",
    re.IGNORECASE,
)

PUNCT = re.compile(r"[^a-z0-9 ]")
MULTI_SPACE = re.compile(r"\s+")


def normalize_company(name: str) -> str:
    name = name.lower().strip()
    name = DUTCH_SUFFIXES.sub(" ", name)
    name = PUNCT.sub(" ", name)
    name = MULTI_SPACE.sub(" ", name).strip()
    return name


def download_ind_register() -> Optional[list[str]]:
    ctx = ssl.create_default_context()
    for url in IND_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                raw = resp.read().decode("utf-8-sig", errors="replace")
                lines = raw.splitlines()
                if len(lines) < 2:
                    continue
                companies = []
                reader = csv.reader(lines)
                header = next(reader, None)
                if not header:
                    continue
                name_col = 0
                for i, h in enumerate(header):
                    if "naam" in h.lower() or "name" in h.lower():
                        name_col = i
                        break
                for row in reader:
                    if len(row) > name_col and row[name_col].strip():
                        companies.append(row[name_col].strip())
                if companies:
                    return companies
        except Exception:
            continue
    return None


def match_company(query: str, sponsors: list[dict]) -> dict:
    query_norm = normalize_company(query)
    query_tokens = set(query_norm.split())

    if not query_tokens:
        return {"status": "not_found", "matched_entry": None, "confidence": "none"}

    best_match = None
    best_confidence = "none"
    best_score = 0.0

    for sponsor in sponsors:
        sponsor_name = sponsor["company_name"]
        sponsor_norm = normalize_company(sponsor_name)
        sponsor_tokens = set(sponsor_norm.split())

        if not sponsor_tokens:
            continue

        if query_norm == sponsor_norm:
            if sponsor.get("careers_url"):
                return {
                    "status": "confirmed",
                    "matched_entry": sponsor_name,
                    "confidence": "exact",
                    "careers_url": sponsor.get("careers_url", ""),
                }
            if best_score < 1.0:
                best_score = 1.0
                best_match = sponsor_name
                best_confidence = "exact"
            continue

        intersection = query_tokens & sponsor_tokens
        if not intersection:
            continue

        query_coverage = len(intersection) / len(query_tokens)
        sponsor_coverage = len(intersection) / len(sponsor_tokens)
        score = (query_coverage + sponsor_coverage) / 2

        if query_tokens <= sponsor_tokens:
            score = max(score, 0.85)

        has_url = bool(sponsor.get("careers_url"))
        if score > best_score or (score == best_score and has_url):
            best_score = score
            best_match = sponsor_name

            if score >= 0.8:
                best_confidence = "high"
            elif score >= 0.5:
                best_confidence = "possible"
            else:
                best_confidence = "low"

    if best_match and best_confidence in ("exact", "high", "possible"):
        sponsor_row = next((s for s in sponsors if s["company_name"] == best_match), {})
        status = "confirmed" if best_confidence in ("exact", "high") else "possible"
        return {
            "status": status,
            "matched_entry": best_match,
            "confidence": best_confidence,
            "careers_url": sponsor_row.get("careers_url", ""),
        }

    return {"status": "not_found", "matched_entry": None, "confidence": "none"}


class NlIndHsmProvider(WorkAuthProvider):
    """Annotate companies against the cached IND recognised-sponsor register."""

    scheme = "nl-ind-hsm"

    def __init__(self, *, register_path: Optional[Path] = None, drop_unknown: bool = False):
        self._register_path = Path(register_path) if register_path else None
        self.drop_unknown = drop_unknown

    def register_path(self) -> Path:
        if self._register_path is not None:
            return self._register_path
        return workspace.get_home() / "config" / "nl_ind_hsm_sponsors.csv"

    def load_sponsors(self) -> list[dict]:
        path = self.register_path()
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _save_sponsors(self, rows: list[dict]) -> None:
        path = self.register_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=REGISTER_FIELDNAMES)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in REGISTER_FIELDNAMES})

    def annotate(self, companies: list[str]) -> dict[str, dict[str, Any]]:
        sponsors = self.load_sponsors()
        out: dict[str, dict[str, Any]] = {}
        for name in dict.fromkeys(companies):
            if not str(name).strip():
                continue
            out[name] = match_company(name, sponsors)
        return out

    def gate(self, listing: dict[str, Any]) -> str:
        status = self._status_of(listing)
        if status == "confirmed":
            return KEEP
        if status == "not_found":
            return DROP if self.drop_unknown else FLAG
        return FLAG  # "possible" (and any other) -> flag for manual review

    def refresh(
        self,
        *,
        from_names: Optional[list[str]] = None,
        from_file: Optional[Path] = None,
        fetch: Optional[Callable[[], Optional[list[str]]]] = None,
    ) -> int:
        """Rebuild the cached register. Precedence: from_names > from_file > fetch.
        `fetch` defaults to the live IND downloader; tests inject a fake fetch or
        pass from_names/from_file so nothing hits the network."""
        names: Optional[list[str]] = None
        if from_names is not None:
            names = [n for n in from_names if str(n).strip()]
        elif from_file is not None:
            text = Path(from_file).read_text(encoding="utf-8-sig", errors="replace")
            # Accept a plain name-per-line list OR a CSV with a company_name column.
            names = _parse_seed_names(text)
        else:
            fetcher = fetch or download_ind_register
            names = fetcher() or []

        existing = {r["company_name"]: r for r in self.load_sponsors()}
        today = datetime.now().strftime("%Y-%m-%d")
        for name in names:
            if name in existing:
                existing[name]["last_verified"] = today
            else:
                existing[name] = {"company_name": name, "careers_url": "",
                                  "category": "highly_skilled_migrant", "last_verified": today}
        self._save_sponsors(list(existing.values()))
        return len(existing)


def _parse_seed_names(text: str) -> list[str]:
    """Extract company names from a refresh seed file (name-per-line, or a CSV
    with a company_name/name header)."""
    lines = text.splitlines()
    if not lines:
        return []
    reader = csv.reader(lines)
    rows = list(reader)
    header = [h.strip().lower() for h in rows[0]] if rows else []
    if any(h in ("company_name", "name", "naam") for h in header):
        col = next(i for i, h in enumerate(header)
                   if h in ("company_name", "name", "naam"))
        return [r[col].strip() for r in rows[1:] if len(r) > col and r[col].strip()]
    return [ln.strip() for ln in lines if ln.strip()]
