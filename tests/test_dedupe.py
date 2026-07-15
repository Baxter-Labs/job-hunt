import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "job-hunt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import search.dedupe as D  # noqa: E402
import search.tracker as T  # noqa: E402


def test_pack_dir_matches_phase2_convention(tmp_path):
    out = D.pack_dir_for("Acme", "Backend Engineer", output_root=tmp_path)
    assert out.name == "acme-backend-engineer"


def test_is_duplicate_in_tracker(tmp_path):
    tracker = tmp_path / "tracker.csv"
    T.upsert(company="Acme", role="Backend Engineer", job_id="x1", path=tracker)
    rows = T.load_tracker(tracker)
    out = tmp_path / "output"; out.mkdir()
    res = D.is_duplicate("acme", "backend engineer", tracker_rows=rows, output_root=out)
    assert res["is_duplicate"] is True
    assert res["in_tracker"] is True
    assert res["in_filesystem"] is False


def test_is_duplicate_in_filesystem(tmp_path):
    out = tmp_path / "output"
    pack = out / "acme-backend-engineer"; pack.mkdir(parents=True)
    (pack / "cv.pdf").write_text("x")     # existing pack, non-empty
    res = D.is_duplicate("Acme", "Backend Engineer", tracker_rows=[], output_root=out)
    assert res["is_duplicate"] is True
    assert res["in_filesystem"] is True
    assert res["existing_path"] == str(pack)


def test_is_duplicate_false_when_new(tmp_path):
    out = tmp_path / "output"; out.mkdir()
    res = D.is_duplicate("Fresh", "Role", tracker_rows=[], output_root=out)
    assert res["is_duplicate"] is False


def test_filter_new_removes_duplicates(tmp_path):
    tracker = tmp_path / "tracker.csv"
    T.upsert(company="Acme", role="Backend Engineer", path=tracker)
    rows = T.load_tracker(tracker)
    out = tmp_path / "output"; out.mkdir()
    listings = [
        {"company": "Acme", "role": "Backend Engineer"},   # dup (tracker)
        {"company": "New Co", "role": "Data Scientist"},    # new
    ]
    kept = D.filter_new(listings, tracker_rows=rows, output_root=out)
    assert [l["company"] for l in kept] == ["New Co"]


def test_collapse_by_slug_keeps_first_of_intra_batch_duplicates():
    listings = [
        {"company": "Acme", "role": "Backend Engineer", "job_id": "indeed-1"},
        {"company": "Acme", "role": "Backend Engineer", "job_id": "linkedin-9"},  # same job, 2nd platform
        {"company": "New Co", "role": "Data Scientist", "job_id": "indeed-2"},
    ]
    unique = D.collapse_by_slug(listings)
    assert [l["job_id"] for l in unique] == ["indeed-1", "indeed-2"]
    assert len(unique) == 2
