import json
from pathlib import Path
from fixtures import GOOD_VERDICT
import collect_verdicts as collect


def _queue(tmp_path, rnd, entries):
    """Write one blinded queue dir with the given manifest entries and verdict files."""
    for d in [f"runs/judge-queue/round-{rnd}/verdicts", "results/judge/_baseline",
              "results/judge"]:
        Path(d).mkdir(parents=True, exist_ok=True)
    Path("ledger").mkdir(exist_ok=True)
    man = [{k: v for k, v in m.items() if k != "_verdict"} for m in entries]
    Path(f"runs/judge-queue/round-{rnd}/manifest.json").write_text(json.dumps(man))
    for m in entries:
        (Path(f"runs/judge-queue/round-{rnd}/verdicts") / f"{m['entry_id']}.json"
         ).write_text(json.dumps(m["_verdict"]))


def _entry(eid, source="sensenova", case=511, rnd=1):
    return {"entry_id": eid, "source": source, "case_id": case,
            "round": rnd, "seed": "111", "orig_image": "x.png", "_verdict": GOOD_VERDICT}


def test_collect_happy_and_invalid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entries = [_entry("entry-aaaaaaaa"),
               # Brief-fixture gap fix: the brief's only reference entry is the invalid
               # one, so results/judge/_baseline/511.json could never be produced; add a
               # valid reference row so the original baseline assertions stay intact.
               {"entry_id": "entry-bbbbbbbb", "source": "reference", "case_id": 511,
                "round": None, "seed": None, "orig_image": "y.png",
                "_verdict": {"scores": {}}},
               _entry("entry-cccccccc", source="reference")]
    _queue(tmp_path, 1, entries)
    rc = collect.main(["--round", "1"])
    assert rc == 0
    out = json.loads(Path("results/judge/entry-aaaaaaaa.json").read_text())
    assert out["source"] == "sensenova" and out["backend"] == "agent"
    assert out["verdict"]["scores"]["quality"] == 8
    base = json.loads(Path("results/judge/_baseline/511.json").read_text())
    assert base["source"] == "reference"
    assert not Path("results/judge/entry-bbbbbbbb.json").exists()
    evs = Path("ledger/append.jsonl").read_text().splitlines()
    assert any('"judge_failed"' in e for e in evs)


def test_collect_backend_choice_lands_in_envelope(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Explicit --backend glm_api: every envelope must record it (run_judge_api batches).
    _queue(tmp_path, 2, [_entry("entry-glm-aaaa"), _entry("entry-glm-bbbb", source="reference")])
    assert collect.main(["--round", "2", "--backend", "glm_api"]) == 0
    for eid in ("entry-glm-aaaa", "entry-glm-bbbb"):
        env = json.loads(Path(f"results/judge/{eid}.json").read_text())
        assert env["backend"] == "glm_api"
    base = json.loads(Path("results/judge/_baseline/511.json").read_text())
    assert base["backend"] == "glm_api"
    # JUDGE_BACKEND env fallback when --backend is absent; default stays agent.
    monkeypatch.setenv("JUDGE_BACKEND", "glm_api")
    _queue(tmp_path, 3, [_entry("entry-env-aaaa")])
    assert collect.main(["--round", "3"]) == 0
    assert json.loads(Path("results/judge/entry-env-aaaa.json").read_text())["backend"] == "glm_api"
    monkeypatch.delenv("JUDGE_BACKEND")
    _queue(tmp_path, 4, [_entry("entry-def-aaaa")])
    assert collect.main(["--round", "4"]) == 0
    assert json.loads(Path("results/judge/entry-def-aaaa.json").read_text())["backend"] == "agent"
    # Unknown backend values are rejected loudly, not recorded silently.
    import pytest
    with pytest.raises(SystemExit):
        collect.main(["--round", "5", "--backend", "chatgpt"])
