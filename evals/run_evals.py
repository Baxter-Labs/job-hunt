"""Quality-evals scorecard CLI for the Job Hunt plugin.

Loads the golden cases, runs the REAL scorers via the evaluators, prints a
readable PASS/FAIL scorecard, and exits non-zero if any case fails.
Deterministic and offline — no API, no MCP, no network.

    .venv/bin/python evals/run_evals.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Support both `python evals/run_evals.py` and `import run_evals` (after the
# evals dir is on sys.path, as tests do): make sibling modules importable.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import loader  # noqa: E402
import ats_eval  # noqa: E402
import rank_eval  # noqa: E402


def collect_results() -> list[dict]:
    results: list[dict] = []
    for case in loader.load_ats_cases():
        results.append(ats_eval.evaluate_ats_case(case))
    for case in loader.load_rank_cases():
        results.append(rank_eval.evaluate_rank_case(case))
    return results


def format_scorecard(results: list[dict]) -> str:
    lines: list[str] = []
    lines.append("Job Hunt — Quality Evals Scorecard")
    lines.append("=" * 40)
    for res in results:
        status = "PASS" if res["passed"] else "FAIL"
        if res["kind"] == "ats":
            detail = f"score={res['score']}"
        else:
            detail = f"order={res['order']}"
        lines.append(f"[{status}] {res['kind']:4} {res['id']:28} {detail}")
        for failure in res["failures"]:
            lines.append(f"         └─ {failure}")
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    lines.append("-" * 40)
    lines.append(f"{passed}/{total} cases passed")
    return "\n".join(lines)


def run() -> int:
    results = collect_results()
    print(format_scorecard(results))
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(run())
