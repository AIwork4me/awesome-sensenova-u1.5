import json
from pathlib import Path

import make_gen_jsonl as mgj
from lib.constants import SEEDS_PER_PROMPT
from lib.ledger import append_event


def test_bucket_portrait_priority():
    assert mgj.bucket_for("vertical movie poster for a film") == (1664, 2496)
    assert mgj.bucket_for("wide landscape banner design") == (2496, 1664)
    assert mgj.bucket_for("a cat on mars") == (2048, 2048)


def test_seed_stable_and_range():
    a = mgj.stable_seed(511, 1, 0)
    assert a == mgj.stable_seed(511, 1, 0) and a != mgj.stable_seed(511, 1, 1)
    assert 0 <= a < 2**31 - 1


def _lock(tmp_path, ids):
    p = tmp_path / "configs/pilot.lock.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"size": len(ids),
                             "cases": [{"id": i} for i in ids]}))


def _case_dirs(tmp_path, ids):
    for cid in ids:
        d = tmp_path / f"cases/pilot/case-{cid}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "base.md").write_text("vertical movie poster", encoding="utf-8")


def test_terminal_ledger_freezes_case_in_later_rounds(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _lock(tmp_path, [511, 512])
    _case_dirs(tmp_path, [511, 512])
    # Round 1: no terminal decisions yet, both cases yield their seeds.
    mgj.main(["--round", "1"])
    r1 = [json.loads(l)["type"]
          for l in Path("runs/gen/round-1/gen.jsonl").read_text().splitlines()]
    assert sum(t.startswith("case511-r1-s") for t in r1) == SEEDS_PER_PROMPT
    assert sum(t.startswith("case512-r1-s") for t in r1) == SEEDS_PER_PROMPT
    # Round 2: case 511 carries a TERMINAL status_parity decision -> frozen,
    # yields zero lines; the other case still yields.
    append_event("ledger/append.jsonl", "compared",
                 {"case_id": 511, "round": 1}, idem="cmp-1-511")
    append_event("ledger/append.jsonl", "status_parity",
                 {"case_id": 511, "round": 1, "status": "parity"}, idem="cmp-1-511")
    assert mgj.main(["--round", "2"]) is None
    r2 = [json.loads(l)["type"]
          for l in Path("runs/gen/round-2/gen.jsonl").read_text().splitlines()]
    assert len(r2) == SEEDS_PER_PROMPT
    assert not any(t.startswith("case511-") for t in r2)
    assert all(t.startswith("case512-r2-s") for t in r2)
    out = capsys.readouterr().out
    assert "[gen-jsonl] frozen=1" in out


def test_status_capped_also_freezes():
    evs = [{"type": "status_capped", "payload": {"case_id": 7}},
           {"type": "rewritten", "payload": {"case_id": 7}}]
    assert mgj.frozen_case_ids(evs) == {"7"}
    assert mgj.frozen_case_ids([{"type": "generated", "payload": {"tag": "t"}}]) == set()
