"""Resample selection protocol, hardened into a testable script (operator-loop §3).

Covers: deterministic selection, ceil(n * RESAMPLE_RATE) sizing, provenance-free
task rows, private-first manifest resolution under --isolated, selection
provenance without source fields, and no-clobber semantics for historical
artifacts.
"""
import json
from pathlib import Path

from build_resample_tasks import main, select_ids


def _manifest(tmp_path: Path, n: int = 20, private: bool = False):
    mdir = (tmp_path / "runs" / "judge-private" / "round-4") if private \
        else (tmp_path / "runs" / "judge-queue" / "round-4")
    mdir.mkdir(parents=True, exist_ok=True)
    entries = [{"entry_id": f"entry-{i:08x}", "source": "sensenova" if i % 2 else "reference",
                "case_id": i, "round": 4, "seed": str(i),
                "orig_image": str(mdir.parent / "entries" / f"entry-{i:08x}.png")}
               for i in range(n)]
    (mdir / "manifest.json").write_text(json.dumps(entries), encoding="utf-8")
    (tmp_path / "runs" / "judge-queue" / "round-4").mkdir(parents=True, exist_ok=True)
    return entries


def test_selection_deterministic_and_sized(tmp_path):
    entries = _manifest(tmp_path, private=True)  # location must not matter
    seed1, ids1 = select_ids(entries, 4)
    seed2, ids2 = select_ids(entries, 4)
    assert seed1 == seed2 and ids1 == ids2
    import math
    assert len(ids1) == math.ceil(len(entries) * 0.1)
    assert len(set(ids1)) == len(ids1)
    assert set(ids1) <= {e["entry_id"] for e in entries}


def test_resample_tasks_provenance_free(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    entries = _manifest(tmp_path)
    assert main(["--round", "4"]) == 0
    rows = [json.loads(line)
            for line in (tmp_path / "runs/judge-queue/round-4/resample-tasks.jsonl")
            .read_text(encoding="utf-8").splitlines() if line]
    assert rows and all(set(row) == {"entry_id", "image_path", "prompt_path",
                                     "verdict_path"} for row in rows)
    assert all("verdicts-resample" in row["verdict_path"] for row in rows)
    sel = json.loads((tmp_path / "runs/judge-queue/round-4/resample-selection.json")
                     .read_text(encoding="utf-8"))
    assert sel["n_selected"] == len(rows) and "source" not in json.dumps(sel)


def test_isolated_mode_writes_private_provenance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _manifest(tmp_path, private=True)
    assert main(["--round", "4", "--isolated"]) == 0
    priv = tmp_path / "runs/judge-private/round-4/resample-selection.json"
    assert priv.exists()
    assert not (tmp_path / "runs/judge-queue/round-4/resample-selection.json").exists()
    tasks = (tmp_path / "runs/judge-queue/round-4/resample-tasks.jsonl").read_text()
    assert "sensenova" not in tasks and "reference" not in tasks


def test_no_clobber_without_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _manifest(tmp_path)
    q = tmp_path / "runs/judge-queue/round-4/resample-tasks.jsonl"
    q.write_text("HISTORICAL\n", encoding="utf-8")
    assert main(["--round", "4"]) == 0
    assert q.read_text(encoding="utf-8") == "HISTORICAL\n"
    assert main(["--round", "4", "--force"]) == 0
    assert q.read_text(encoding="utf-8") != "HISTORICAL\n"
