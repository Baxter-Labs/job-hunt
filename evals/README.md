# Quality Evals Harness

Deterministic, offline regression gate for the Job Hunt plugin's two scored
behaviors:

- **ATS scoring** — `tailor.ats.build_ats_report` (JD keyword extraction +
  CV coverage → `match_score`).
- **Listing ranking** — `search.rank.rank_listings` (sponsorship × recency ×
  level → stable order).

Unlike a model-graded eval, our scorers are **deterministic Python**, so each
golden case asserts **exact/banded numbers + keyword membership** — a hard
regression gate. This is modeled on the layout of the MIT-licensed
[career-ops](https://github.com/santifer/career-ops) `evals/` (golden labeled
cases + fixtures + methodology), credited in `../ACKNOWLEDGMENTS.md`; the
difference is that career-ops measures model *agreement*, while we lock exact
deterministic output.

## What's here

- `golden/ats/*.json` — one ATS case per file (domain-diverse + regression guards).
- `golden/rank/*.json` — one ranking case per file.
- `loader.py` — schema + validation (malformed cases fail loudly).
- `ats_eval.py` / `rank_eval.py` — call the REAL scorers and diff against `expect`.
- `run_evals.py` — scorecard CLI (`PASS`/`FAIL` per case, non-zero exit on failure).

## Running

    # From repo root, using the project venv:
    .venv/bin/python evals/run_evals.py        # human-readable scorecard
    .venv/bin/python -m pytest tests/test_evals.py -q   # as a CI gate

## ATS case schema (`golden/ats/<id>.json`)

    {
      "id": "software-backend",         // unique, matches filename stem
      "synthetic": true,                 // REQUIRED — synthetic data only
      "jd": "…synthetic job description…",
      "cv_text": "…synthetic CV text…",  // exactly one of cv_text OR tailored_cv
      "tailored_cv": { … },              // a tailored_cv dict; flattened via
                                         //   cv_text_from_tailored (excludes
                                         //   ats_keywords_used → honest score)
      "company": "Synthetic BV",         // optional, cosmetic
      "role": "Backend Engineer",        // optional, cosmetic
      "expect": {
        "score_min": 56,                 // inclusive band on match_score
        "score_max": 62,
        "must_match": ["python", "sql"], // MUST appear in matched_keywords
        "must_miss":  ["kubernetes"],    // MUST appear in missing_keywords
        "must_not_appear": ["kubernetes."] // optional: in NEITHER list
      }
    }

## Ranking case schema (`golden/rank/<id>.json`)

    {
      "id": "sponsorship-dominates",
      "synthetic": true,
      "today": "2026-07-15",             // pins recency; deterministic
      "target_levels": ["senior"],       // optional; passed to rank_listings
      "listings": [ { "id": "…", "company": "…", "role": "…",
                      "posted_date": "YYYY-MM-DD",
                      "work_auth": {"status": "confirmed"} }, … ],
      "expect": { "order": ["id-first", "id-second", …] }
    }

## Labeling methodology

Bands and membership lists are **hand-set from the deterministic scorer's
intended behavior**, then confirmed by running the real scorer once. Bands
(`score_min`/`score_max`) are intentionally a few points wide so that *benign*
lexicon growth (which shifts the keyword total by a term or two) does not break
the suite, while `must_match` / `must_miss` / `must_not_appear` lock the actual
quality behavior — the part a regression would corrupt. If a change *should*
move a band, update the case in the same commit and say why.

## Adding a case

1. Pick a domain or a specific behavior/bug to guard.
2. Write synthetic `jd` + `cv_text` (placeholder identities only — e.g. Ada
   Lovelace; no personal data).
3. Run `.venv/bin/python evals/run_evals.py` to see the real numbers, then set
   `expect` with a tight band + the salient `must_match`/`must_miss` terms.
4. Add `tests/test_evals.py` stays green; commit the JSON.
