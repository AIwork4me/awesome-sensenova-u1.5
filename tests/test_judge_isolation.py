"""Source-isolation properties of the judge queue assembly (hardening pass).

Properties (spec: future source-isolated judge workspace):
1. public tasks.jsonl carries no `source` field;
2. public prompt files carry no provenance wording;
3. public filenames use neutral content-hash entry IDs only;
4. in --isolated mode the judge-visible queue dir contains no manifest.json;
5. the private manifest keeps the full entry_id -> source mapping;
6. isolation does not change the deterministic shuffle;
7. default (non-isolated) assembly still writes manifest.json into the queue
   dir, so historical frozen artifacts and the operator workflow are untouched.
"""
import json
from pathlib import Path

import pytest

from build_judge_tasks import plan_rows


def _fixture(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.png").write_bytes(b"img-a")
    (tmp_path / "b.png").write_bytes(b"img-b")
    (tmp_path / "ref.jpg").write_bytes(b"img-reference-bytes")
    case_dir = tmp_path / "cases" / "pilot" / "case-7"
    case_dir.mkdir(parents=True)
    (case_dir / "base.md").write_text("a calm lake at dawn", encoding="utf-8")
    gens = [{"payload": {"tag": f"case7-r1-s{i}", "file": n}}
            for i, n in enumerate(("a.png", "b.png"))]
    dirs = {7: {"prompt_text": "a calm lake at dawn", "upstream_image": "ref.jpg"}}
    return gens, dirs


def test_isolated_queue_hides_provenance(tmp_path, monkeypatch):
    gens, dirs = _fixture(tmp_path, monkeypatch)
    q = tmp_path / "runs" / "judge-queue" / "round-1"
    priv = tmp_path / "runs" / "judge-private" / "round-1"
    plan_rows(gens, dirs, set(), q, 1, copies=True, manifest_dir=priv)

    tasks = [json.loads(line)
             for line in (q / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert tasks and all("source" not in row for row in tasks)          # (1)
    for row in tasks:
        p = tmp_path / row["prompt_path"]
        assert p.exists() and "sensenova" not in p.read_text(encoding="utf-8") \
            and "reference" not in p.read_text(encoding="utf-8")        # (2)
        assert p.parent.name == "prompts"
        img = tmp_path / row["image_path"]
        assert img.parent.name == "entries" and img.name.startswith("entry-")  # (3)
    assert not (q / "manifest.json").exists()                           # (4)
    man = json.loads((priv / "manifest.json").read_text(encoding="utf-8"))
    assert {m["entry_id"] for m in man} == {row["entry_id"] for row in tasks}
    assert {m["source"] for m in man} == {"reference", "sensenova"}     # (5)


def test_isolated_order_matches_default(tmp_path, monkeypatch):
    gens, dirs = _fixture(tmp_path, monkeypatch)
    q1 = tmp_path / "runs" / "judge-queue" / "round-1"
    priv = tmp_path / "runs" / "judge-private" / "round-1"
    q2 = tmp_path / "runs" / "judge-queue" / "round-1b"
    a = plan_rows(gens, dirs, set(), q1, 1, copies=True, manifest_dir=priv)
    b = plan_rows(gens, dirs, set(), q2, 1, copies=True)
    assert [r["entry_id"] for r in a] == [r["entry_id"] for r in b]     # (6)


def test_default_assembly_keeps_manifest_in_queue(tmp_path, monkeypatch):
    gens, dirs = _fixture(tmp_path, monkeypatch)
    q = tmp_path / "runs" / "judge-queue" / "round-1"
    plan_rows(gens, dirs, set(), q, 1, copies=True)
    man = json.loads((q / "manifest.json").read_text(encoding="utf-8"))  # (7)
    assert {m["source"] for m in man} == {"reference", "sensenova"}


def test_collect_prefers_private_manifest(tmp_path, monkeypatch):
    from collect_verdicts import _manifest_path
    q = tmp_path / "runs" / "judge-queue" / "round-2"
    q.mkdir(parents=True)
    (q / "manifest.json").write_text("[]", encoding="utf-8")
    assert _manifest_path(q, tmp_path) == q / "manifest.json"            # historical
    priv = tmp_path / "runs" / "judge-private" / "round-2"
    priv.mkdir(parents=True)
    (priv / "manifest.json").write_text("[]", encoding="utf-8")
    assert _manifest_path(q, tmp_path) == priv / "manifest.json"         # isolated
