"""Attribution-driven prompt rewriting (scripts/rewrite_prompts.py)."""
import json
from pathlib import Path

import rewrite_prompts as rp
from lib.ledger import append_event, load_events

GAP_CHECK = "a_score_gap: five-dim mean below reference beyond allowance"


def _mk_case(root, cid=511):
    d = root / f"cases/pilot/case-{cid}"
    d.mkdir(parents=True)
    (d / "base.md").write_text("A vertical poster with a credits block at bottom.\n")
    (d / "provenance.json").write_text(json.dumps({"case_id": cid, "history": []}))
    return d


def test_pick_strategy_priority():
    assert rp.pick_strategy(["c_small_text: garbled small text"]) == "S1_drop_microtext"
    assert rp.pick_strategy(["b_display_text: display text incorrect"]
                            ) == "S2_simplify_display_text"
    assert rp.pick_strategy(["d_miss_zero: text missing elements"]
                            ) == "S2_simplify_display_text"
    assert rp.pick_strategy(["a_score_gap: wrong number of workers vs stated quantity"]
                            ) == "S3_explicit_constraints"
    # anatomy keywords outrank composition keywords regardless of rule order
    assert rp.pick_strategy([f"{GAP_CHECK} and hand posture broken near face"]
                            ) == "S5_avoid_anatomy"
    assert rp.pick_strategy(["e_no_visual_defects: visual defects present"]
                            ) == "S5_avoid_anatomy"
    assert rp.pick_strategy([GAP_CHECK]) == "S4_style_anchor"


def test_rewrite_writes_next_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _mk_case(tmp_path, 511)
    outcome = rp.rewrite_one(511, failed_checks=["c_small_text: garbled small text"])
    assert outcome == "rewritten"
    assert (tmp_path / "cases/pilot/case-511/adapted-v2.md").exists()
    new_text = (tmp_path / "cases/pilot/case-511/adapted-v2.md").read_text()
    assert "do NOT render a credits block" in new_text
    prov = json.loads((tmp_path / "cases/pilot/case-511/provenance.json").read_text())
    last = prov["history"][-1]
    assert last["strategy"] == "S1_drop_microtext" and last["small_text_exempt"] is True
    assert last["version"] == 2 and last["failed_checks"] == ["c_small_text: garbled small text"]
    events = load_events(tmp_path / "ledger/append.jsonl")
    rw = [e for e in events if e["type"] == "rewritten"]
    assert len(rw) == 1 and rw[0]["idem"] == "rw-511-2" and rw[0]["payload"]["version"] == 2


def test_rewrite_caps_after_max_rounds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = _mk_case(tmp_path, 42)
    led = tmp_path / "ledger/append.jsonl"
    # simulate three completed rewrite rounds (versions 2-4 on disk + ledger)
    for ver in (2, 3, 4):
        (d / f"adapted-v{ver}.md").write_text(f"round {ver}\n")
        append_event(led, "rewritten", {"case_id": 42, "version": ver,
                                        "strategy": "S4_style_anchor"}, idem=f"rw-42-{ver}")
    outcome = rp.rewrite_one(42, failed_checks=[GAP_CHECK])
    assert outcome == "capped"
    assert not (d / "adapted-v5.md").exists()
    events = load_events(led)
    assert sum(e["type"] == "rewritten" for e in events) == 3
    caps = [e for e in events if e["type"] == "status_capped"]
    assert len(caps) == 1 and caps[0]["idem"] == "cap-42"
    assert caps[0]["payload"]["capped_at_round"] == 3
