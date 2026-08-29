#!/usr/bin/env python3
"""Comparison-layout gallery + conclusions renderer (task 16, M4 publish).

PRESENTATION CONVENTION (binding since 2026-08-27, spec §12.1 and the
workspace AGENTS.md 图像对比画廊呈现规范; implemented per the exemplar in
results/gallery/wip-round1): the published gallery uses the side-by-side
comparison layout — per-case two-column table (left = GPT-Image-2 reference
image + upstream original prompt, right = SenseNova reproduction image + the
actually executed prompt), exactly ONE reproduction image per case, BOTH
displays normalized onto a single canvas sized by the reference image's aspect
ratio (long edge 1200, letterbox background = mean of the reference's four
corner pixels, WebP q88) and rendered with the same width attribute, prompts
as separate <details> blocks per column, per-case source attribution, a
directory NOTICE.md for the redistributed reference copies (spec §12.1 #5),
and a top-of-page scoring-status banner.

Inputs:
  * runs/comparisons/final/report.json (preferred; else the highest round-N
    report) — rows are authoritative for status/winner; the ledger is not parsed;
  * results/judge/_baseline/{case}.json — reference-side judging receipts
    (presence is what makes the report "final"; the banner numbers themselves
    come from report.milestone);
  * cases/pilot/case-{id}/ — base.md (upstream original prompt),
    adapted-v*.md (rewritten prompts), provenance.json (title/category/source_url);
  * third_party/ref/data/images/case{id}.* — reference image (gitignored;
    must exist locally at publish time);
  * configs/publish-exclude-cases.txt (--exclude-file) — case ids omitted
    from the gallery entirely, listed in a footnote instead.

Rulings honoured here:
  - "actually executed prompt" = the prompt on disk when the winning image was
    generated: make_gen_jsonl picks the latest adapted-v*.md present (falling
    back to base.md), and rewrites for round N land before round N generation,
    so the prompt is keyed on the GENERATION round parsed from winner_file
    (adapted-vG if it exists, else the newest adapted-vN with N < G, else
    base.md, version 1 — labelled 两侧同题逐字相同); keying on best_from_round
    alone would be wrong for carried winners, whose decision round is newer
    than their generation round;
  - report.json rows are authoritative for status; fail is published as
    "capped" so the conclusions table carries only parity/win/capped strings
    with their negative gap shown honestly; undocumented/unknown statuses are
    never silently relabelled — they render verbatim plus one stderr warning;
  - deferred case ids go to a note line under the conclusions table;
  - a row whose winner_file or reference image is missing on disk is skipped
    from the gallery with a stderr warning and an end-of-run summary, but its
    numbers still show in the conclusions table;
  - provenance.source_url may be empty: backlinks degrade to plain text
    instead of dead markdown links;
  - --dry-run prints the planned sections and writes/copies/normalizes nothing.

Never touches git push or anything under third_party/, runs/, .venv-test/.
"""
import argparse
import json
import re
import sys
from pathlib import Path

MARK_EN = "<!-- GALLERY_EN -->"
MARK_ZH = "<!-- GALLERY_ZH -->"
MARK_TBL = "<!-- RESULTS_TABLE -->"
GALLERY_DIR = Path("results/gallery")
CMP_DIR = GALLERY_DIR / "cmp"
REF_IMAGE_DIR = Path("third_party/ref/data/images")
DEFAULT_EXCLUDE_FILE = Path("configs/publish-exclude-cases.txt")
REPORT_PUBLIC = "results/comparisons/final/report.json"
CHANGELOG_STUB = "- 新增双语画廊与结论表渲染脚本 scripts/render_gallery.py（发布收口）。"

LONG_EDGE = 1200            # normalized canvas long edge (spec §12.1 #3)
WEBP_QUALITY = 88           # normalized display copy quality (spec §12.1 #3)
IMG_WIDTH = 420             # identical width attribute for BOTH columns
STEPS = "50 步"
MODE = "balanced"

# Directory-level copyright notice for the redistributed cmp/ display copies
# (spec §12.1 #5): the reference copies derive from awesome-gpt-image-2
# community case images, belong to their original creators, and ship for
# non-commercial evaluation comparison only; takedown on request. Wording
# mirrors results/gallery/wip-round1/NOTICE.md, adapted to the cmp/ naming.
NOTICE_TEXT = """# 版权与使用声明（NOTICE）

本目录中的 `case{id}.webp` 为参考基线显示副本（规格化：长边 1200、WebP q88），源自 [freestylefly/awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2)（MIT 协议仓库）收录的社区案例效果图，原始创作者见 README 各例的来源链接。这些图片**仅用于本项目的非商业性生成质量评测对比**，著作权归各自创作者所有；如有侵权请联系移除。

`case{id}-winner.webp` 为本仓库管线在 AMD ROCm 7.14.0 上由 SenseNova-U1.5-8B-MoT 生成的复现图显示副本（与参考副本同画布规格化），按确定性种子可复现（seed 见 README 各例复现参数行与台账）。
"""

# Report status -> published wording. "fail" is deliberately surfaced as
# "capped"; deferred rows never reach this map (they live on the note line).
_STATUS_MAP = {"parity": "parity", "win": "win", "fail": "capped"}

# Per-case heading prefix; replace_section must not treat these as section
# boundaries (each gallery case owns one).
_CASE_HEAD = "## case-"

# Column/row labels, zh + en twins of the same comparison structure.
_LABELS = {
    "zh": {
        "banner": "> ✅ 已判分：round {rnd} 全量 {total} 案例双盲评审完成 —— "
                  "parity {p} · win {w} / total {t} · parity 率 {ratio} · "
                  "overall gap {gap}。判分明细：[{link}]({link})",
        "banner_nolink": "> ✅ 已判分：round {rnd} 全量 {total} 案例双盲评审完成 —— "
                         "parity {p} · win {w} / total {t} · parity 率 {ratio} · "
                         "overall gap {gap}",
        "head": "| | 左 · GPT-Image-2（参考基线） "
                "| 右 · SenseNova-U1.5（复现 v{ver}，best from round {rnd}） |",
        "src_link": "上游案例：[来源回链]({url})",
        "src_nolink": "上游案例：未附来源链接",
        "row_img": "| 效果图 | <img src=\"{ref}\" width=\"420\"/> "
                   "| <img src=\"{win}\" width=\"420\"/> |",
        "row_prompt": "| 提示词 | {left} | {right} |",
        "row_params": "| 复现参数 | 上游案例原图 "
                      "| seed {seed} · " + STEPS + " · " + MODE
                      + " · 确定性可复现 · best from round {rnd} |",
        "left_summary": "GPT-Image-2 案例原提示词（点击展开）",
        "right_summary": "SenseNova 执行提示词（v{ver}，两侧同题逐字相同）（点击展开）",
        "right_summary_rw": "SenseNova 执行提示词（v{ver}，经改写）（点击展开）",
        "no_prompt": "（未存档提示词）",
        "footnote": "> 注：{ids} 按 [configs/publish-exclude-cases.txt]"
                    "(configs/publish-exclude-cases.txt) 配置未收录入本画廊"
                    "（仍计入结论表）。",
        "gap_word": "overall gap",
    },
    "en": {
        "banner": "> ✅ Judged: round {rnd} full blind review of {total} cases "
                  "complete — parity {p} · win {w} / total {t} · parity ratio "
                  "{ratio} · overall gap {gap}. Details: [{link}]({link})",
        "banner_nolink": "> ✅ Judged: round {rnd} full blind review of {total} "
                         "cases complete — parity {p} · win {w} / total {t} · "
                         "parity ratio {ratio} · overall gap {gap}",
        "head": "| | Left · GPT-Image-2 (reference baseline) "
                "| Right · SenseNova-U1.5 (repro v{ver}, best from round {rnd}) |",
        "src_link": "upstream: [source]({url})",
        "src_nolink": "upstream: no source link",
        "row_img": "| Image | <img src=\"{ref}\" width=\"420\"/> "
                   "| <img src=\"{win}\" width=\"420\"/> |",
        "row_prompt": "| Prompt | {left} | {right} |",
        "row_params": "| Repro params | upstream reference image "
                      "| seed {seed} · 50 steps · " + MODE
                      + " · deterministic · best from round {rnd} |",
        "left_summary": "GPT-Image-2 original prompt (click to expand)",
        "right_summary": "SenseNova executed prompt (v{ver}, verbatim same prompt) "
                         "(click to expand)",
        "right_summary_rw": "SenseNova executed prompt (v{ver}, rewritten) "
                            "(click to expand)",
        "no_prompt": "(prompt not archived)",
        "footnote": "> Note: {ids} omitted from this gallery per "
                    "[configs/publish-exclude-cases.txt]"
                    "(configs/publish-exclude-cases.txt) (still counted in the "
                    "conclusions table).",
        "gap_word": "overall gap",
    },
}

# ChangeLog idempotence anchor: a heading at line start, not any substring.
_UNRELEASED_RE = re.compile(r"^## Unreleased\b", re.MULTILINE)


def _warn(msg):
    print(f"[render][WARN] {msg}", file=sys.stderr)


def load_report(root: Path, rnd=None):
    """The final report if present, else latest round report by numeric round;
    --round pins runs/comparisons/round-N/report.json and must exist."""
    base = root / "runs/comparisons"
    if rnd is not None:
        p = base / f"round-{rnd}" / "report.json"
        if not p.exists():
            print(f"[render] no report for --round {rnd} under {base}",
                  file=sys.stderr)
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    final = base / "final" / "report.json"
    if final.is_file():
        return json.loads(final.read_text(encoding="utf-8"))
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


def load_excludes(path: Path):
    """Whitespace-separated case ids; non-digit tokens (comments) ignored,
    missing file = empty list (same parsing as select-pilot)."""
    if not path.is_file():
        return []
    return sorted({int(t) for t in path.read_text(encoding="utf-8").split()
                   if t.strip().isdigit()})


def _read_text(path: Path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def executed_prompt(root: Path, cid, winner_file, best_round):
    """(text, version, rewritten) for the prompt that was actually on disk
    when the winning image was generated.

    make_gen_jsonl picks the latest adapted-v*.md present (fallback base.md),
    and rewrite rounds land before the generation round they feed, so a winner
    generated in round G was produced by adapted-vG if it exists, else the
    newest adapted-vN with N < G, else base.md (version 1, unmodified —
    labelled 两侧同题逐字相同). G comes from the winner_file path: carried
    winners keep a best_from_round (decision round) that can be NEWER than the
    generation round, so the prompt must key on generation, not decision.
    """
    case_dir = root / f"cases/pilot/case-{cid}"
    adapteds = {}
    for p in case_dir.glob("adapted-v*.md"):
        m = re.fullmatch(r"adapted-v(\d+)\.md", p.name)
        if m:
            adapteds[int(m.group(1))] = p
    m = re.search(r"round-(\d+)", str(winner_file or ""))
    gen_round = int(m.group(1)) if m else (best_round or 0)
    ver = max((v for v in adapteds if v <= gen_round), default=None)
    if ver is None:                                   # base.md = version 1
        text = _read_text(case_dir / "base.md")
        return (text if text is not None else ""), 1, False
    return _read_text(adapteds[ver]) or "", ver, True


def ref_image(root: Path, cid):
    """third_party/ref/data/images/case{id}.* — first sorted match or None."""
    matches = sorted((root / REF_IMAGE_DIR).glob(f"case{cid}.*"))
    return matches[0] if matches else None


def collect_entries(report, root: Path, excludes=()):
    """(gallery entries, skipped ids) over decided rows; excluded ids are
    dropped before anything else and returned separately for the footnote."""
    exclude_set = set(excludes)
    entries, skipped = [], []
    for row in sorted(report["per_case"], key=lambda r: r["case_id"]):
        cid = row["case_id"]
        if cid in exclude_set:
            continue
        wf = row.get("winner_file")
        src = root / wf if wf else None
        if not wf or not src.is_file():
            reason = "winner_file is null" if not wf else f"missing file {wf}"
            _warn(f"case-{cid}: {reason}; gallery entry skipped")
            skipped.append(cid)
            continue
        ref = ref_image(root, cid)
        if ref is None:
            _warn(f"case-{cid}: reference image not found under {REF_IMAGE_DIR}; "
                  "gallery entry skipped")
            skipped.append(cid)
            continue
        prov = provenance(root, cid)
        text, ver, rewritten = executed_prompt(root, cid, wf,
                                               row.get("best_from_round"))
        entries.append({
            "cid": cid,
            # No silent relabel: unknown/missing status keeps its RAW string
            # (main() warns once per case); only documented fail->capped maps.
            "status": _STATUS_MAP.get(row.get("status"), row.get("status")),
            "title": prov.get("title") or "-",
            "category": prov.get("category") or "-",
            "url": prov.get("source_url") or "",
            "seed": row.get("winner_seed") if row.get("winner_seed") else "-",
            "best_round": row.get("best_from_round", "-"),
            "ref_src": ref,
            "win_src": src,
            "ref_webp": CMP_DIR / f"case{cid}.webp",
            "win_webp": CMP_DIR / f"case{cid}-winner.webp",
            "base_text": _read_text(root / f"cases/pilot/case-{cid}/base.md"),
            "exec_text": text,
            "exec_ver": ver,
            "rewritten": rewritten,
        })
    return entries, skipped


def normalize_pair(ref_path, win_path, out_ref, out_win,
                   long_edge=LONG_EDGE, quality=WEBP_QUALITY):
    """Render the reference and the winner onto ONE canvas sized by the
    reference's aspect (long edge `long_edge`), letterbox background = mean of
    the reference's four corner pixels; saved as WebP `quality`.

    Pillow is imported lazily so the module (and every non-rendering test)
    works without it.
    """
    from PIL import Image                       # lazy: keep import PIL-free

    def _rgb(path):
        with Image.open(path) as im:
            return im.convert("RGB")

    ref, win = _rgb(ref_path), _rgb(win_path)
    w, h = ref.size
    scale = long_edge / max(w, h)
    canvas = (max(1, round(w * scale)), max(1, round(h * scale)))
    corners = [ref.getpixel((0, 0)), ref.getpixel((w - 1, 0)),
               ref.getpixel((0, h - 1)), ref.getpixel((w - 1, h - 1))]
    bg = tuple(round(sum(c[i] for c in corners) / 4) for i in range(3))

    def _paste(img):
        s = min(canvas[0] / img.width, canvas[1] / img.height)
        fitted = img.resize((max(1, round(img.width * s)),
                             max(1, round(img.height * s))))
        base = Image.new("RGB", canvas, bg)
        base.paste(fitted, ((canvas[0] - fitted.width) // 2,
                            (canvas[1] - fitted.height) // 2))
        return base

    for img, out in ((_paste(ref), out_ref), (_paste(win), out_win)):
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out, "WEBP", quality=quality)


def update_notice(root: Path) -> bool:
    """Emit results/gallery/cmp/NOTICE.md next to the redistributed reference
    display copies (spec §12.1 #5); idempotent — writes only on content drift."""
    path = root / CMP_DIR / "NOTICE.md"
    if path.exists() and path.read_text(encoding="utf-8") == NOTICE_TEXT:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(NOTICE_TEXT, encoding="utf-8")
    return True


def normalize_images(entries, root: Path):
    """Overwrite the ref display copy and write the winner copy each run."""
    for e in entries:
        normalize_pair(root / e["ref_src"], root / e["win_src"],
                       root / e["ref_webp"], root / e["win_webp"])


def _esc(text):
    """Markdown-table cell safety: escape pipes so prose cannot split a row."""
    return str(text).replace("|", "\\|")


def _details(text, summary, no_prompt_word):
    body = _esc(text if text else "").replace("\r\n", "\n").replace("\n", "<br>")
    return (f"<details><summary>{summary}</summary><br>"
            f"{body if body else no_prompt_word}</details>")


def _fmt_num(v):
    return "n/a" if v is None else str(v)


def _banner(report, lang):
    m = report.get("milestone") or {}
    fmt = {"rnd": report.get("round", "-"),
           "total": _fmt_num(m.get("total")), "t": _fmt_num(m.get("total")),
           "p": _fmt_num(m.get("parity_count")), "w": _fmt_num(m.get("win_count")),
           "ratio": _fmt_num(m.get("parity_ratio")), "gap": _fmt_num(m.get("overall_gap"))}
    L = _LABELS[lang]
    key = "banner" if report.get("round") == "final" else "banner_nolink"
    return L[key].format(link=REPORT_PUBLIC, **fmt)


def _case_section(e, lang):
    L = _LABELS[lang]
    src = L["src_link"].format(url=_esc(e["url"])) if e["url"] else L["src_nolink"]
    lines = [f"{_CASE_HEAD}{e['cid']} · {_esc(e['title'])}"
             f"（{_esc(e['category'])}）· {src}"
             if lang == "zh" else
             f"{_CASE_HEAD}{e['cid']} · {_esc(e['title'])}"
             f" ({_esc(e['category'])}) · {src}",
             "",
             L["head"].format(ver=e["exec_ver"], rnd=e["best_round"]),
             "|---|---|---|",
             L["row_img"].format(ref=e["ref_webp"].as_posix(),
                                 win=e["win_webp"].as_posix()),
             L["row_prompt"].format(
                 left=_details(e["base_text"], L["left_summary"], L["no_prompt"]),
                 right=_details(e["exec_text"],
                                (L["right_summary_rw"] if e["rewritten"]
                                 else L["right_summary"]).format(ver=e["exec_ver"]),
                                L["no_prompt"])),
             L["row_params"].format(seed=_esc(e["seed"]), rnd=e["best_round"])]
    return "\n".join(lines)


def render_comparison(entries, report, excluded, lang):
    """Banner + per-case side-by-side sections + exclusion footnote (spec §12.1)."""
    L = _LABELS[lang]
    parts = [_banner(report, lang)]
    for e in entries:
        parts += ["---", _case_section(e, lang)]
    if excluded:
        ids = "、".join(f"case-{c}" for c in excluded)
        parts += ["", L["footnote"].format(ids=ids)]
    return "\n".join(parts)


def render_table(report):
    """Conclusions table (case/status/two-side means/gap/best round) plus the
    mandatory deferred note line; final reports link the published copy."""
    rnd = report.get("round")
    head = (f"> 来源：round-{rnd} 冻结报告 · Source: frozen round-{rnd} report"
            if rnd != "final" else
            f"> 来源：round-{rnd} 冻结报告 · Source: frozen round-{rnd} report — "
            f"[{REPORT_PUBLIC}]({REPORT_PUBLIC})")
    lines = [head, "",
             "| case | 状态 | 两方均分 | 差值 | best_from_round |",
             "|---|---|---|---|---|"]
    for r in sorted(report["per_case"], key=lambda x: x["case_id"]):
        # Raw passthrough for undocumented statuses — honest reporting beats a
        # tidy enum; the relabel warning itself is emitted once from main().
        st = _STATUS_MAP.get(r.get("status"), r.get("status"))
        lines.append(f"| case-{r['case_id']} | {_esc(st)} "
                     f"| {r['candidate_mean']:.2f} / {r['reference_mean']:.2f} "
                     f"| {r['gap']:+.2f} | {r.get('best_from_round', '-')} |")
    if report.get("deferred"):
        ids = "、".join(f"case-{c}" for c in report["deferred"])
        lines += ["", f"> deferred（未判定，不计入上表 / not listed above）：{ids}"]
    return "\n".join(lines)


def replace_section(text, marker, body):
    """Fill content after `marker` up to the next marker/heading boundary.

    Per-case gallery headings (`## case-…`) belong to the body being replaced,
    not to the document skeleton, so they never terminate the scan.
    """
    lines = text.split("\n")
    mi = next(i for i, l in enumerate(lines) if l.strip() == marker)
    j = mi + 1
    while j < len(lines):
        s = lines[j].lstrip()
        if s.startswith("<!--") or (s.startswith("#")
                                    and not s.startswith(_CASE_HEAD)):
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
        description="Render the comparison-layout README gallery (spec §12.1) "
                    "and conclusions table from the frozen comparison report "
                    "(publish finalization).")
    ap.add_argument("--round", type=int, default=None,
                    help="use runs/comparisons/round-N/report.json instead of "
                         "final/latest")
    ap.add_argument("--exclude-file", default=str(DEFAULT_EXCLUDE_FILE),
                    help="case ids listed here are omitted from the gallery "
                         "entirely (footnote only)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print planned sections only; write nothing")
    a = ap.parse_args(argv)
    root = Path(".")

    excludes = load_excludes(root / a.exclude_file)
    report = load_report(root, a.round)
    if a.round is not None and report is None:
        return 1                       # explicit --round must exist; fail loudly
    if report is None:
        print("[render] no comparison reports found under runs/comparisons; "
              "nothing to publish")
        entries, skipped, excluded = [], [], []
        en_body = zh_body = tbl_body = ""
    else:
        # Honest-reporting guard: flag undocumented statuses once, up front.
        for r in report["per_case"]:
            if r.get("status") not in _STATUS_MAP:
                print(f"[render] unknown status '{r.get('status')}' "
                      f"for case {r.get('case_id')}", file=sys.stderr)
        entries, skipped = collect_entries(report, root, excludes)
        excluded = [c for c in excludes
                    if any(r["case_id"] == c for r in report["per_case"])]
        zh_body = render_comparison(entries, report, excluded, "zh")
        en_body = render_comparison(entries, report, excluded, "en")
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
        normalize_images(entries, root)
    if report is not None and update_notice(root):
        print("[render] results/gallery/cmp/NOTICE.md: written")
    if update_changelog(root / "CHANGELOG.md"):
        print("[render] CHANGELOG.md: added Unreleased stub")

    rnd = report.get("round") if report else "-"
    print(f"[render] done (round={rnd}, gallery={len(entries)}, "
          f"normalized={len(entries)}, excluded={len(excluded)})")
    if report is not None:
        if skipped:
            names = ", ".join(f"case-{c}" for c in skipped)
            print(f"[render] skipped from gallery ({len(skipped)}): {names}")
        else:
            print("[render] gallery complete: no cases skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
