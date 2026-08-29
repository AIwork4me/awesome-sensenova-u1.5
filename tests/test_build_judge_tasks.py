import pytest

from build_judge_tasks import neutral_entry_id, plan_rows


def test_neutral_entry_id_stable_short():
    a = neutral_entry_id(b"hello world")
    assert a.startswith("entry-") and len(a) == len("entry-") + 8
    assert a == neutral_entry_id(b"hello world")


def test_plan_rows_includes_reference_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.png").write_bytes(b"img-sensenova-bytes")
    (tmp_path / "ref.jpg").write_bytes(b"img-reference-bytes")
    case_dir = tmp_path / "cases" / "pilot" / "case-511"
    case_dir.mkdir(parents=True)
    (case_dir / "base.md").write_text("p", encoding="utf-8")
    made = plan_rows(gen_events=[{"payload": {"tag": "case511-r1-s1", "file": "a.png"}}],
                     case_dirs={511: {"prompt_text": "p", "upstream_image": "ref.jpg"}},
                     baseline_existing=set(), queue_dir=tmp_path, rnd=1, copies=True)
    srcs = sorted(r["source"] for r in made)
    assert srcs == ["reference", "sensenova"]


def test_plan_rows_unmatched_tag_raises(tmp_path):
    with pytest.raises(KeyError):
        plan_rows(gen_events=[{"payload": {"tag": "case-not-a-tag"}}],
                  case_dirs={}, baseline_existing=set(), queue_dir=tmp_path,
                  rnd=1, copies=False)


def test_plan_rows_order_deterministic_and_complete(tmp_path, monkeypatch):
    # source-blind protocol carrier: the queue order must be a deterministic
    # permutation seeded by the round, so re-assembly cannot reshuffle history.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.png").write_bytes(b"img-a")
    (tmp_path / "b.png").write_bytes(b"img-b")
    (tmp_path / "ref.jpg").write_bytes(b"img-reference-bytes")
    case_dir = tmp_path / "cases" / "pilot" / "case-7"
    case_dir.mkdir(parents=True)
    (case_dir / "base.md").write_text("p", encoding="utf-8")
    gens = [{"payload": {"tag": f"case7-r1-s{i}", "file": n}}
            for i, n in enumerate(("a.png", "b.png"))]
    dirs = {7: {"prompt_text": "p", "upstream_image": "ref.jpg"}}
    rows1 = plan_rows(gen_events=gens, case_dirs=dirs, baseline_existing=set(),
                      queue_dir=tmp_path, rnd=1, copies=False)
    rows2 = plan_rows(gen_events=gens, case_dirs=dirs, baseline_existing=set(),
                      queue_dir=tmp_path, rnd=1, copies=False)
    ids1 = [r["entry_id"] for r in rows1]
    assert ids1 == [r["entry_id"] for r in rows2]
    assert len(ids1) == len(set(ids1)) == 3
    assert sorted(r["source"] for r in rows1) == ["reference", "sensenova", "sensenova"]
