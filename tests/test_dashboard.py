import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

# Flask is an OPTIONAL dependency; skip the whole module cleanly when absent.
pytest.importorskip("flask")

import dashboard.app as dash  # noqa: E402
import search.tracker as T  # noqa: E402


def _seed(home):
    (home / "output").mkdir(parents=True, exist_ok=True)
    T.upsert(company="Acme", role="Backend Engineer", url="https://a",
             status="pack_generated", work_auth_status="confirmed",
             source="indeed", path=home / "tracker.csv")
    pack = home / "output" / "acme-backend-engineer"
    pack.mkdir(parents=True)
    (pack / "ats_report.json").write_text(json.dumps({
        "company": "Acme", "role": "Backend Engineer",
        "total_keywords": 10, "matched_count": 7, "match_score": 70,
        "matched_keywords": ["python"], "missing_keywords": ["kubernetes"],
    }), encoding="utf-8")
    (pack / "cv.pdf").write_text("%PDF-1.4", encoding="utf-8")
    return pack


def _client(home):
    app = dash.create_app(home=home)
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_lists_role_with_ats(tmp_path):
    _seed(tmp_path)
    resp = _client(tmp_path).get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Acme" in body
    assert "70" in body  # ATS % surfaced


def test_api_jobs_returns_ats_score(tmp_path):
    _seed(tmp_path)
    resp = _client(tmp_path).get("/api/jobs")
    data = json.loads(resp.get_data(as_text=True))
    assert data[0]["company"] == "Acme"
    assert data[0]["ats_score"] == 70


def test_download_allows_known_file(tmp_path):
    _seed(tmp_path)
    resp = _client(tmp_path).get("/download/acme-backend-engineer/cv.pdf")
    assert resp.status_code == 200


def test_download_rejects_unknown_file(tmp_path):
    _seed(tmp_path)
    resp = _client(tmp_path).get("/download/acme-backend-engineer/secrets.env")
    assert resp.status_code == 403


def test_download_blocks_path_traversal(tmp_path):
    _seed(tmp_path)
    resp = _client(tmp_path).get("/download/acme-backend-engineer/..%2f..%2ftracker.csv")
    assert resp.status_code in (403, 404)


def test_empty_workspace_renders(tmp_path):
    (tmp_path / "output").mkdir()
    resp = _client(tmp_path).get("/")
    assert resp.status_code == 200


def test_no_personal_data_in_app_source():
    src = (SCRIPTS / "dashboard" / "app.py").read_text(encoding="utf-8")
    assert "Eshwar" not in src and "dantepk" not in src
