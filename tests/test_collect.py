import json
from pathlib import Path
from fixtures import GOOD_VERDICT
import collect_verdicts as collect


def test_collect_happy_and_invalid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for d in ["ledger", "runs/judge-queue/round-1/verdicts", "results/judge/_baseline", "results/judge"]:
        Path(d).mkdir(parents=True, exist_ok=True)
    Path("ledger/append.jsonl").write_text("")
    man = [{"entry_id": "entry-aaaaaaaa", "source": "sensenova", "case_id": 511,
            "round": 1, "seed": "111", "orig_image": "x.png"},
           {"entry_id": "entry-bbbbbbbb", "source": "reference", "case_id": 511,
            "round": None, "seed": None, "orig_image": "y.png"},
           # Brief-fixture gap fix: the brief's only reference entry is the invalid
           # one, so results/judge/_baseline/511.json could never be produced; add a
           # valid reference row so the original baseline assertions stay intact.
           {"entry_id": "entry-cccccccc", "source": "reference", "case_id": 511,
            "round": None, "seed": None, "orig_image": "z.png"}]
    Path("runs/judge-queue/round-1/manifest.json").write_text(json.dumps(man))
    Path("runs/judge-queue/round-1/verdicts/entry-aaaaaaaa.json").write_text(json.dumps(GOOD_VERDICT))
    Path("runs/judge-queue/round-1/verdicts/entry-bbbbbbbb.json").write_text(json.dumps({"scores": {}}))
    Path("runs/judge-queue/round-1/verdicts/entry-cccccccc.json").write_text(json.dumps(GOOD_VERDICT))
    rc = collect.main(["--round", "1"])
    assert rc == 0
    out = json.loads(Path("results/judge/entry-aaaaaaaa.json").read_text())
    assert out["source"] == "sensenova" and out["verdict"]["scores"]["quality"] == 8
    base = json.loads(Path("results/judge/_baseline/511.json").read_text())
    assert base["source"] == "reference"
    assert not Path("results/judge/entry-bbbbbbbb.json").exists()
    evs = Path("ledger/append.jsonl").read_text().splitlines()
    assert any('"judge_failed"' in e for e in evs)
