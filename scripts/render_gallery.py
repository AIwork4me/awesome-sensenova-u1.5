#!/usr/bin/env python3
"""Bilingual gallery + conclusions renderer (task 16, publish finalization).

Turns the frozen comparison outcome (latest runs/comparisons/round-*/report.json
by round number; --round filters to one) into:

  * results/gallery/case-{id}{ext} — copies of each decided case's winner image
    (source path taken from report row winner_file, never re-derived);
  * README.md placeholders filled: <!-- GALLERY_EN -->, <!-- GALLERY_ZH --> and
    <!-- RESULTS_TABLE -->. The EN marker is inserted above the ZH marker when
    absent (R8: the README must always end up carrying all three);
  * a one-shot "## Unreleased" stub in CHANGELOG.md (idempotent via marker).

Rulings honoured here:
  - report.json rows are authoritative for status; the ledger is not parsed.
    fail rows are published as "capped" so the conclusions table carries only
    parity/win/capped strings, with their negative gap shown honestly;
    undocumented/unknown statuses are never silently relabelled — they render
    verbatim in badge and table plus one stderr warning;
  - deferred case ids go to a note line under the table, never table rows;
  - a row whose winner_file is null or missing on disk is skipped from both
    galleries with a stderr warning and listed in the end-of-run skipped
    summary, but still shows its capped numbers in the conclusions table;
  - provenance.source_url may be empty (15 pilot cases): backlinks degrade to
    plain text instead of dead markdown links;
  - --dry-run prints the planned sections and copies/writes nothing.

Never touches git push or anything under third_party/, runs/, .venv-test/.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

MARK_EN = "<!-- GALLERY_EN -->"
MARK_ZH = "<!-- GALLERY_ZH -->"
MARK_TBL = "<!-- RESULTS_TABLE -->"
GALLERY_DIR = Path("results/gallery")
CHANGELOG_STUB = "- 新增双语画廊与结论表渲染脚本 scripts/render_gallery.py（发布收口）。"

# Report status -> published wording. "fail" is deliberately surfaced as
# "capped"; deferred rows never reach this map (they live on the note line).
_STATUS_MAP = {"parity": "parity", "win": "win", "fail": "capped"}

_LABELS = {
    "zh": ("案例", "我方图", "上游回链",                # header cells
           "我方图", "上游回链",                       # row-cell prefixes
           "上游案例 #{cid}（未附来源链接）"),          # source_url null guard
    "en": ("Case", "Ours", "Upstream",
           "ours", "upstream link",
           "upstream case #{cid} (no source link)"),
}

# ChangeLog idempotence anchor: a heading at line start, not any substring.
_UNRELEASED_RE = re.compile(r"^## Unreleased\b", re.MULTILINE)


def _warn(msg):
    print(f"[render][WARN] {msg}", file=sys.stderr)


def load_report(root: Path, rnd=None):
    """Latest round report by numeric round, or the report of --round."""
    base = root / "runs/comparisons"
    if rnd is not None:
        p = base / f"round-{rnd}" / "report.json"
        if not p.exists():
            print(f"[render] no report for --round {rnd} under {base}",
                  file=sys.stderr)
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    candidates = []
    for p in base.glob("round-*/report.json"):
        try:
            n = int(p.parent.name.split("-", 1)[1])
        except ValueError:
            continue
        candidates.append((n, p))
    if not candidates:
        return None
    latest = max(candidates)
    return json.loads(latest[1].read_text(encoding="utf-8"))


def provenance(root: Path, cid):
    """cases/pilot/case-{id}/provenance.json body, or {} when absent/broken."""
    p = root / f"cases/pilot/case-{cid}/provenance.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def collect_entries(report, root: Path):
    """(gallery entries, skipped ids) over decided rows that have an image."""
    entries, skipped = [], []
    for row in sorted(report["per_case"], key=lambda r: r["case_id"]):
        cid = row["case_id"]
        wf = row.get("winner_file")
        src = root / wf if wf else None
        if not wf or not src.is_file():
            reason = "winner_file is null" if not wf else f"missing file {wf}"
            _warn(f"case-{cid}: {reason}; gallery entry skipped")
            skipped.append(cid)
            continue
        prov = provenance(root, cid)
        entries.append({
            "cid": cid,
            # No silent relabel: unknown/missing status keeps its RAW string
            # (main() warns once per case); only documented fail->capped maps.
            "status": _STATUS_MAP.get(row.get("status"), row.get("status")),
            "category": prov.get("category") or "-",
            "url": prov.get("source_url") or "",
            "src": src,
            "dest": GALLERY_DIR / f"case-{cid}{Path(wf).suffix}",
        })
    return entries, skipped


def copy_images(entries, root: Path):
    for e in entries:
        dest = root / e["dest"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(e["src"], dest)


def _esc(text):
    """Markdown-table cell safety: escape pipes so prose cannot split a row."""
    return str(text).replace("|", "\\|")


def render_gallery(entries, lang):
    """| case-id 类别 | 我方图 <img…> | 上游回链 […] | table; zh/en twins."""
    head, ours_lbl, link_lbl, ours_word, link_word, nolink = _LABELS[lang]
    lines = [f"| {head} | {ours_lbl} | {link_lbl} |", "|---|---|---|"]
    for e in entries:
        img = f"<img src=\"{e['dest'].as_posix()}\" width=\"420\"/>"
        if e["url"]:
            link_cell = f"{link_word} [case {e['cid']}]({_esc(e['url'])})"
        else:               # T5 forward-note: no dead markdown links, ever
            link_cell = nolink.format(cid=e["cid"])
        lines.append(f"| case-{e['cid']} {_esc(e['category'])} `{e['status']}` "
                     f"| {ours_word} {img} | {link_cell} |")
    return "\n".join(lines)


def render_table(report):
    """Conclusions table plus the mandatory deferred note line."""
    lines = [f"> 来源：round-{report.get('round')} 冻结报告 · "
             f"Source: frozen round-{report.get('round')} report", "",
             "| case | 状态 | 我方均分 | 参考均分 | 差值 |",
             "|---|---|---|---|---|"]
    for r in sorted(report["per_case"], key=lambda x: x["case_id"]):
        # Raw passthrough for undocumented statuses — honest reporting beats a
        # tidy enum; the relabel warning itself is emitted once from main().
        st = _STATUS_MAP.get(r.get("status"), r.get("status"))
        lines.append(f"| case-{r['case_id']} | {_esc(st)} "
                     f"| {r['candidate_mean']:.2f} | {r['reference_mean']:.2f} "
                     f"| {r['gap']:+.2f} |")
    if report.get("deferred"):
        ids = "、".join(f"case-{c}" for c in report["deferred"])
        lines += ["", f"> deferred（未判定，不计入上表 / not listed above）：{ids}"]
    return "\n".join(lines)


def replace_section(text, marker, body):
    """Fill content after `marker` up to the next marker/heading boundary."""
    lines = text.split("\n")
    mi = next(i for i, l in enumerate(lines) if l.strip() == marker)
    j = mi + 1
    while j < len(lines):
        s = lines[j].lstrip()
        if s.startswith("<!--") or s.startswith("#"):
            break
        j += 1
    block = [marker]
    if body.strip():
        block += ["", body.rstrip("\n")]
    block += [""]
    return "\n".join(lines[:mi] + block + lines[j:])


def insert_en_marker(text):
    """R8: EN gallery marker goes directly above the ZH one."""
    lines = text.split("\n")
    zi = next(i for i, l in enumerate(lines) if l.strip() == MARK_ZH)
    return "\n".join(lines[:zi] + [MARK_EN, ""] + lines[zi:])


def update_changelog(path: Path) -> bool:
    """Append an Unreleased stub once; idempotent via the Unreleased marker.

    The marker is anchored to line start (multiline regex) so a prose mention
    like "- see ## Unreleased notes" cannot suppress the real stub.
    """
    txt = path.read_text(encoding="utf-8") if path.exists() else "# Changelog\n"
    if _UNRELEASED_RE.search(txt):
        return False
    nl = txt.index("\n", txt.index("# "))       # insert below the top heading
    new = txt[:nl] + "\n\n## Unreleased\n\n" + CHANGELOG_STUB + "\n\n" \
        + txt[nl:].lstrip("\n")
    path.write_text(new, encoding="utf-8")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Render the bilingual README gallery and conclusions table "
                    "from the frozen comparison report (publish finalization).")
    ap.add_argument("--round", type=int, default=None,
                    help="use runs/comparisons/round-N/report.json instead of latest")
    ap.add_argument("--dry-run", action="store_true",
                    help="print planned sections only; write nothing")
    a = ap.parse_args(argv)
    root = Path(".")

    report = load_report(root, a.round)
    if a.round is not None and report is None:
        return 1                       # explicit --round must exist; fail loudly
    if report is None:
        print("[render] no comparison reports found under runs/comparisons; "
              "nothing to publish")
        entries, skipped = [], []
        en_body = zh_body = tbl_body = ""
    else:
        # Honest-reporting guard: flag undocumented statuses once, up front.
        for r in report["per_case"]:
            if r.get("status") not in _STATUS_MAP:
                print(f"[render] unknown status '{r.get('status')}' "
                      f"for case {r.get('case_id')}", file=sys.stderr)
        entries, skipped = collect_entries(report, root)
        en_body = render_gallery(entries, "en")
        zh_body = render_gallery(entries, "zh")
        tbl_body = render_table(report)

    readme = root / "README.md"
    txt = readme.read_text(encoding="utf-8") if readme.exists() else ""
    if MARK_EN not in txt and MARK_ZH in txt:
        txt = insert_en_marker(txt)
    if not all(m in txt for m in (MARK_EN, MARK_ZH, MARK_TBL)):
        missing = [m for m in (MARK_EN, MARK_ZH, MARK_TBL) if m not in txt]
        txt = txt.rstrip("\n") + "\n\n## Gallery / 对比结论\n\n" \
            + "\n\n".join(missing) + "\n"
    for marker, body in ((MARK_EN, en_body), (MARK_ZH, zh_body),
                         (MARK_TBL, tbl_body)):
        txt = replace_section(txt, marker, body)

    if a.dry_run:
        print("--- planned sections (dry-run, nothing written) ---")
        print(MARK_EN + "\n" + en_body)
        print(MARK_ZH + "\n" + zh_body)
        print(MARK_TBL + "\n" + tbl_body)
        print("[render] dry-run complete: no files touched")
        return 0

    if not readme.exists() or readme.read_text(encoding="utf-8") != txt:
        readme.write_text(txt, encoding="utf-8")
    if entries:
        copy_images(entries, root)
    if update_changelog(root / "CHANGELOG.md"):
        print("[render] CHANGELOG.md: added Unreleased stub")

    rnd = report.get("round") if report else "-"
    print(f"[render] done (round={rnd}, gallery={len(entries)}, "
          f"copied={len(entries)})")
    if report is not None:
        if skipped:
            names = ", ".join(f"case-{c}" for c in skipped)
            print(f"[render] skipped from gallery ({len(skipped)}): {names}")
        else:
            print("[render] gallery complete: no cases skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
