import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import insights.upskill as U  # noqa: E402


def _pack(root, slug, company, role, missing):
    pack = root / slug
    pack.mkdir(parents=True)
    (pack / "ats_report.json").write_text(json.dumps({
        "company": company, "role": role,
        "total_keywords": 10, "matched_count": 10 - len(missing),
        "missing_count": len(missing), "match_score": 50,
        "matched_keywords": [], "missing_keywords": missing,
    }), encoding="utf-8")
    return pack


def test_aggregate_counts_and_ranks(tmp_path):
    out = tmp_path / "output"
    p1 = _pack(out, "acme-backend", "Acme", "Backend Engineer",
               ["kubernetes", "terraform", "graphql"])
    p2 = _pack(out, "globex-platform", "Globex", "Platform Engineer",
               ["kubernetes", "terraform"])
    p3 = _pack(out, "initech-sre", "Initech", "SRE",
               ["kubernetes"])
    gaps = U.aggregate_gaps([p1, p2, p3])
    # kubernetes (3) > terraform (2) > graphql (1)
    assert [g["keyword"] for g in gaps] == ["kubernetes", "terraform", "graphql"]
    assert gaps[0] == {
        "keyword": "kubernetes", "count": 3,
        "roles": ["Acme — Backend Engineer", "Globex — Platform Engineer", "Initech — SRE"],
    }
    assert gaps[1]["count"] == 2
    assert gaps[2]["roles"] == ["Acme — Backend Engineer"]


def test_aggregate_tie_break_alphabetical(tmp_path):
    out = tmp_path / "output"
    p1 = _pack(out, "a-role", "A", "Role", ["zebra", "alpha"])
    gaps = U.aggregate_gaps([p1])
    # both count==1; alphabetical tie-break
    assert [g["keyword"] for g in gaps] == ["alpha", "zebra"]


def test_aggregate_skips_packs_without_report(tmp_path):
    out = tmp_path / "output"
    p1 = _pack(out, "acme-backend", "Acme", "Backend", ["kubernetes"])
    empty = out / "no-report"; empty.mkdir()
    gaps = U.aggregate_gaps([p1, empty])
    assert [g["keyword"] for g in gaps] == ["kubernetes"]


def test_aggregate_empty_input(tmp_path):
    assert U.aggregate_gaps([]) == []


def test_iter_pack_dirs_finds_only_report_dirs(tmp_path):
    out = tmp_path / "output"
    _pack(out, "acme-backend", "Acme", "Backend", ["kubernetes"])
    _pack(out, "globex-platform", "Globex", "Platform", ["terraform"])
    (out / "not-a-pack").mkdir()  # no ats_report.json -> skipped
    found = U.iter_pack_dirs(out)
    names = [p.name for p in found]
    assert names == ["acme-backend", "globex-platform"]  # sorted, report-bearing only


def test_iter_pack_dirs_missing_root(tmp_path):
    assert U.iter_pack_dirs(tmp_path / "nope") == []
