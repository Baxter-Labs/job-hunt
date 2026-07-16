import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scoring import scoring_cli  # noqa: E402


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = scoring_cli.main(argv)
    return code, json.loads(buf.getvalue())


def test_select_returns_top_n(tmp_path):
    f = tmp_path / "scored.json"
    f.write_text(json.dumps([
        {"company": "B", "role": "x", "fit_score": 40},
        {"company": "A", "role": "y", "fit_score": 90},
        {"company": "C", "role": "z", "fit_score": 70},
    ]), encoding="utf-8")
    code, out = _run(["select", "--scored-file", str(f), "--n", "2"])
    assert code == 0 and out["ok"] is True
    assert out["total"] == 3 and out["n"] == 2
    assert [r["fit_score"] for r in out["selected"]] == [90, 70]


def test_select_default_n_is_5(tmp_path):
    f = tmp_path / "scored.json"
    f.write_text(json.dumps([{"company": "A", "role": "r", "fit_score": 10}]),
                 encoding="utf-8")
    code, out = _run(["select", "--scored-file", str(f)])
    assert code == 0 and out["n"] == 1        # clamped to len; default cap was 5


def test_select_bad_json_exits_1(tmp_path):
    f = tmp_path / "scored.json"
    f.write_text("not json", encoding="utf-8")
    code, out = _run(["select", "--scored-file", str(f)])
    assert code == 1 and out["ok"] is False


def test_select_non_array_exits_1(tmp_path):
    f = tmp_path / "scored.json"
    f.write_text(json.dumps({"company": "A"}), encoding="utf-8")
    code, out = _run(["select", "--scored-file", str(f)])
    assert code == 1 and out["ok"] is False
