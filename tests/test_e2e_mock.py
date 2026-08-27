"""Zero-GPU end-to-end smoke over synthetic data (spec §11): batch ledger ->
blinded queue -> collection -> parity decision, wired on tmp cwd only."""
import json
from pathlib import Path

from fixtures import GOOD_VERDICT


def _png(b):
    return b"\x89PNG\r\n\x1a\n" + bytes(b)


def _write_ref(tmp_path):
    p = tmp_path / "fake-ref.png"
    p.write_bytes(_png([9]))
    return p


def test_pipeline_smoke(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for d in ["ledger", "configs", "cases/pilot/case-511",
              "runs/genimages/round-1", "runs/judge-queue/round-1/verdicts",
              "results/judge/_baseline", "results/judge"]:
        Path(d).mkdir(parents=True, exist_ok=True)
    Path("ledger/append.jsonl").write_text("")
    Path("configs/pilot.lock.json").write_text(json.dumps(
        {"upstream_commit": "x", "cases_sha256": "y", "size": 1,
         "cases": [{"id": 511, "title": "t", "category": "Posters & Typography",
                    "prompt_len": 9}]}))
    Path("cases/pilot/case-511/base.md").write_text("a vertical poster\n")
    # Minimal provenance: exempt() tolerates a missing/empty history.
    Path("cases/pilot/case-511/provenance.json").write_text(json.dumps(
        {"case_id": 511}))
    img = Path("runs/genimages/round-1/0001_case511-r1-s111_2048x2048.png")
    img.write_bytes(_png([1, 2, 3]))
    from lib.ledger import append_event
    append_event("ledger/append.jsonl", "generated",
                 {"tag": "case511-r1-s111", "file": str(img), "sha256": "x"},
                 idem="case511-r1-s111")

    # Stage 2: blinded queue assembly (pure logic face; current code reads the
    # image bytes either way, so both synthetic files must exist on disk).
    import build_judge_tasks as bjt
    rows = bjt.plan_rows(
        gen_events=[{"payload": {"tag": "case511-r1-s111", "file": str(img)}}],
        case_dirs={511: {"prompt_text": "a vertical poster\n",
                         "upstream_image": _write_ref(tmp_path)}},
        baseline_existing=set(),
        queue_dir=Path("runs/judge-queue/round-1"), rnd=1, copies=False)
    assert len(rows) == 2

    # Seed synthetic verdicts for every planned entry plus the manifest that
    # collect_verdicts consumes (plan_rows with copies=False skips materialize).
    q = Path("runs/judge-queue/round-1")
    man = []
    for r in rows:
        man.append({"entry_id": r["entry_id"], "source": r["source"],
                    "case_id": r["case_id"], "round": r["round"],
                    "seed": r["seed"], "orig_image": r["image_path"]})
        v = json.loads(json.dumps(GOOD_VERDICT))
        if r["source"] == "sensenova":
            v["hard_flags"]["small_text_quality"] = "garbled"  # force a fail path
        (q / "verdicts" / f"{r['entry_id']}.json").write_text(json.dumps(v))
    (q / "manifest.json").write_text(json.dumps(man))

    # Stage 3: validate + persist envelopes (reference one becomes baseline).
    import collect_verdicts as collect
    assert collect.main(["--round", "1"]) == 0
    assert len(list(Path("results/judge").glob("*.json"))) == len(rows)
    assert Path("results/judge/_baseline/511.json").exists()

    # Stage 4: formal decision engine over the collected envelopes.
    import compare_parity as cp
    assert cp.main(["--round", "1"]) == 0
    report = json.loads(Path("runs/comparisons/round-1/report.json").read_text())
    assert set(report) >= {"round", "per_case", "milestone", "deferred"}
    assert report["milestone"]["total"] == len(report["per_case"])
    statuses = {r["status"] for r in report["per_case"]}
    assert statuses <= {"parity", "win", "fail"}
    assert "fail" in statuses          # garbled sensenova verdict must be caught
