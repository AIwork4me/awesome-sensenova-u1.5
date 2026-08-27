from ledger import append_event, load_events


def test_append_and_load_roundtrip(tmp_path):
    p = tmp_path / "append.jsonl"
    append_event(p, "case_selected", {"case_id": 511})
    evs = load_events(p)
    assert len(evs) == 1 and evs[0]["payload"]["case_id"] == 511
    assert evs[0]["ts"].endswith("Z")


def test_idempotent_dedupe(tmp_path):
    p = tmp_path / "append.jsonl"
    append_event(p, "generated", {"f": 1}, idem="case511|r1|42")
    append_event(p, "generated", {"f": 1}, idem="case511|r1|42")
    assert len(load_events(p)) == 1
