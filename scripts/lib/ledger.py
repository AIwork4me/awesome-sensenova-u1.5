"""Append-only event ledger: the single source of truth shared by every stage."""
import json
import time
from pathlib import Path


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def append_event(path, etype, payload, idem=None):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if idem is not None and p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                old = json.loads(line)
            except json.JSONDecodeError:
                continue
            if old.get("idem") == idem:
                return old
    ev = {"ts": _now(), "type": etype, "idem": idem, "payload": payload}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return ev


def load_events(path):
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def latest(events, etype, key_fn):
    """Newest event of `etype` per key returned by key_fn; later events win."""
    chosen = {}
    for ev in events:
        if ev["type"] != etype:
            continue
        chosen[key_fn(ev)] = ev
    return chosen
