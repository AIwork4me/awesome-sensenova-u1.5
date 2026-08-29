"""Golden tests for the M4 comparison-layout gallery renderer (spec §12.1).

The published gallery must be the side-by-side layout proven in
results/gallery/wip-round1: per-case two-column table (left = GPT-Image-2
reference image + upstream original prompt, right = SenseNova reproduction
image + actually executed prompt), ONE reproduction image per case, both
displays normalized onto one canvas sized by the reference's aspect (long edge
1200, letterbox = mean of the reference's four corner pixels) and rendered with
the same width attribute, a top-of-page scoring banner, a conclusions table,
and an --exclude-file switch that omits listed cases from the gallery entirely
(footnote only). Fixture per spec: one parity case + one excluded case.
"""
import json
import sys
from pathlib import Path

import pytest

import render_gallery as rg

# Smallest valid 1x1 RGB PNG (Pillow-encoded): enough for the renderer to
# open/normalize without needing Pillow to build fixtures; the pixel-exact
# assertions live in the golden test, which builds real sized images.
PNG1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63f8ffff3f0005fe02fe0def46b80000000049454e44ae"
    "426082")


def _row(cid, status, cand, ref, winner=None, seed="7", best_round=2):
    return {"case_id": cid, "status": status, "candidate_mean": cand,
            "reference_mean": ref, "gap": round(cand - ref, 4),
            "checks": {}, "failed_checks": [],
            "winner_entry_id": "e-best", "winner_seed": seed,
            "winner_file": winner, "best_from_round": best_round}


def _report(tmp_path, rnd, per_case, deferred=None):
    d = tmp_path / f"runs/comparisons/{'round-' + str(rnd) if rnd != 'final' else 'final'}"
    d.mkdir(parents=True)
    total = len(per_case)
    (d / "report.json").write_text(json.dumps(
        {"round": rnd, "per_case": per_case, "deferred": deferred or [],
         "milestone": {"parity_count": sum(r["status"] == "parity" for r in per_case),
                       "win_count": sum(r["status"] == "win" for r in per_case),
                       "target": 24, "total": total, "parity_ratio": 0.5,
                       "overall_gap": -0.35}}), encoding="utf-8")


def _img(tmp_path, rel):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(PNG1X1)
    return rel


def _bytes_img(tmp_path, rel, payload):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(payload)
    return rel


def _prov(tmp_path, cid, url, category="Posters & Typography", title="标题五一一"):
    p = tmp_path / f"cases/pilot/case-{cid}/provenance.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"case_id": cid, "title": title, "category": category,
                             "source_url": url}), encoding="utf-8")


def _prompts(tmp_path, cid, base="BASE PROMPT", adapted=None):
    d = tmp_path / f"cases/pilot/case-{cid}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "base.md").write_text(base, encoding="utf-8")
    for v, text in (adapted or {}).items():
        (d / f"adapted-v{v}.md").write_text(text, encoding="utf-8")


def _seed_repo(tmp_path):
    """README/CHANGELOG mirrors of the live repo: ZH gallery marker + table
    marker exist, the EN gallery marker does not (R8 insertion path)."""
    (tmp_path / "README.md").write_text(
        "# awesome-sensenova-u1.5\n\nintro...\n\n"
        "## 画廊\n\n<!-- GALLERY_ZH -->\n\n## 对比结论\n\n"
        "<!-- RESULTS_TABLE -->\n\n## 快速开始\n\nrun it.\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 0.1.0 (2026-08-27)\n\n- init.\n", encoding="utf-8")


def _full_fixture(tmp_path, exclude=(208,), ref_bytes=PNG1X1, win_bytes=PNG1X1):
    """1 parity case (published, with adapted-v2 prompt) + 1 fail case listed
    in configs/publish-exclude-cases.txt (omitted from the gallery)."""
    _seed_repo(tmp_path)
    (tmp_path / "configs").mkdir(exist_ok=True)
    (tmp_path / "configs/publish-exclude-cases.txt").write_text(
        "".join(f"{c}\n" for c in exclude), encoding="utf-8")
    w511 = _bytes_img(tmp_path, "runs/genimages/round-2/case511-s7.png", win_bytes)
    w208 = _img(tmp_path, "runs/genimages/round-1/case208-s3.webp")
    _bytes_img(tmp_path, "third_party/ref/data/images/case511.jpg", ref_bytes)
    _img(tmp_path, "third_party/ref/data/images/case208.jpg")
    _prov(tmp_path, 511, "https://example.com/upstream/case511")
    _prov(tmp_path, 208, "", title="标题二零八")
    _prompts(tmp_path, 511, base="BASE PROMPT 511",
             adapted={2: "BASE PROMPT 511\n\nTypography constraint: no microtext."})
    _prompts(tmp_path, 208, base="BASE PROMPT 208")
    _report(tmp_path, "final", [
        _row(511, "parity", 8.0, 7.2, w511, seed="7", best_round=2),
        _row(208, "fail", 6.5, 7.1, w208, seed="3", best_round=1),
    ])
    return w511, w208


# --- main golden path --------------------------------------------------------


def test_gallery_golden_comparison_layout(tmp_path, monkeypatch):
    """Spec §12.1 golden: side-by-side table, width=420 on BOTH images, prompt
    details in both columns, exclusion footnote, banner numbers, normalized
    cmp/ images, idempotent re-run."""
    pytest.importorskip("PIL")
    from PIL import Image
    import io

    # reference 600x400 with four distinct corners; winner 300x1200 solid fill.
    # Corner mean = ((10+40+70+100)/4, (20+50+80+110)/4, (30+60+90+120)/4)
    #            = (55, 65, 75) → the winner letterbox color after normalize.
    ref = Image.new("RGB", (600, 400), (255, 255, 255))
    for xy, c in (((0, 0), (10, 20, 30)), ((599, 0), (40, 50, 60)),
                  ((0, 399), (70, 80, 90)), ((599, 399), (100, 110, 120))):
        ref.putpixel(xy, c)
    win = Image.new("RGB", (300, 1200), (200, 50, 150))
    buf_r, buf_w = io.BytesIO(), io.BytesIO()
    ref.save(buf_r, "PNG")
    win.save(buf_w, "PNG")

    monkeypatch.chdir(tmp_path)
    _full_fixture(tmp_path, ref_bytes=buf_r.getvalue(), win_bytes=buf_w.getvalue())
    assert rg.main([]) == 0

    md = (tmp_path / "README.md").read_text(encoding="utf-8")
    # R8: all three markers exist, EN above ZH, table last
    assert md.count("<!-- GALLERY_EN -->") == 1
    assert md.count("<!-- GALLERY_ZH -->") == 1
    assert md.count("<!-- RESULTS_TABLE -->") == 1
    assert md.index("GALLERY_EN") < md.index("GALLERY_ZH") < md.index("RESULTS_TABLE")
    assert "runs/genimages" not in md and "runs/comparisons" not in md

    zh = md.split("<!-- GALLERY_ZH -->")[1].split("## 对比结论")[0]
    en = md.split("<!-- GALLERY_EN -->")[1].split("<!-- GALLERY_ZH -->")[0]

    # scoring banner: 已判分 status + milestone numbers + public report link
    assert "✅ 已判分" in zh
    assert "parity 1 · win 0 / total 2" in zh
    assert "parity 率 0.5" in zh and "overall gap -0.35" in zh
    assert "[results/comparisons/final/report.json](results/comparisons/final/report.json)" in zh

    # per-case section: heading with provenance title/category + source link
    assert ("## case-511 · 标题五一一（Posters & Typography）"
            "· 上游案例：[来源回链](https://example.com/upstream/case511)") in zh

    # side-by-side table: both images same width attribute, normalized copies
    assert ("| | 左 · GPT-Image-2（参考基线） "
            "| 右 · SenseNova-U1.5（复现 v2，best from round 2） |") in zh
    assert '<img src="results/gallery/cmp/case511.webp" width="420"/>' in zh
    assert '<img src="results/gallery/cmp/case511-winner.webp" width="420"/>' in zh

    # prompt details in BOTH columns: upstream original vs actually executed
    assert ("<details><summary>GPT-Image-2 案例原提示词（点击展开）</summary>"
            "<br>BASE PROMPT 511</details>") in zh
    assert ("<details><summary>SenseNova 执行提示词（v2，经改写）（点击展开）</summary>"
            "<br>BASE PROMPT 511<br><br>Typography constraint: no microtext.</details>") in zh

    # reproduction-parameter row (seed from winner_seed, best_from_round)
    assert ("| 复现参数 | 上游案例原图 "
            "| seed 7 · 50 步 · balanced · 确定性可复现 · best from round 2 |") in zh

    # excluded case: footnote only — no per-case section, no cmp images
    assert "## case-208" not in md
    assert "case208" not in zh and "case208" not in en
    assert "configs/publish-exclude-cases.txt" in zh
    footnote = [l for l in zh.splitlines() if l.startswith("> 注")]
    assert len(footnote) == 1 and "case-208" in footnote[0]
    assert not (tmp_path / "results/gallery/cmp/case208.webp").exists()
    assert not (tmp_path / "results/gallery/cmp/case208-winner.webp").exists()

    # redistribution notice (spec §12.1 #5): directory-level NOTICE.md ships
    # with the cmp/ display copies, naming the upstream repo and the
    # non-commercial evaluation-only scope
    notice = tmp_path / "results/gallery/cmp/NOTICE.md"
    assert notice.exists()
    ntxt = notice.read_text(encoding="utf-8")
    assert "非商业" in ntxt and "awesome-gpt-image-2" in ntxt
    assert "确定性种子" in ntxt and "case{id}-winner.webp" in ntxt

    # normalization: one canvas sized by the reference aspect (long edge 1200)
    def _near(got, want, tol=2):        # q88 WebP is lossy: allow tiny drift
        return all(abs(a - b) <= tol for a, b in zip(got, want))

    with Image.open(tmp_path / "results/gallery/cmp/case511.webp") as im:
        assert im.size == (1200, 800) and im.format == "WEBP"
    with Image.open(tmp_path / "results/gallery/cmp/case511-winner.webp") as im:
        assert im.size == (1200, 800) and im.format == "WEBP"
        rgb = im.convert("RGB")
        assert _near(rgb.getpixel((2, 2)), (55, 65, 75))          # letterbox
        assert _near(rgb.getpixel((600, 400)), (200, 50, 150))    # content

    # EN twin keeps the same comparison structure
    assert "| | Left · GPT-Image-2 (reference baseline) " \
           "| Right · SenseNova-U1.5 (repro v2, best from round 2) |" in en
    assert "seed 7 · 50 steps · balanced · deterministic · best from round 2" in en
    assert "✅ Judged" in en and "parity 1 · win 0 / total 2" in en

    # conclusions table: both cases kept (scoring record), new columns
    tbl = md.split("<!-- RESULTS_TABLE -->")[1].split("## 快速开始")[0]
    assert "| case | 状态 | 两方均分 | 差值 | best_from_round |" in tbl
    assert "| case-511 | parity | 8.00 / 7.20 | +0.80 | 2 |" in tbl
    assert "| case-208 | capped | 6.50 / 7.10 | -0.60 | 1 |" in tbl

    # idempotent second run: README stable, Unreleased stub appears once,
    # NOTICE.md content drift-free
    md1, cl1 = md, (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    ntxt1 = (tmp_path / "results/gallery/cmp/NOTICE.md").read_text(encoding="utf-8")
    assert cl1.count("## Unreleased") == 1
    assert rg.main([]) == 0
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == md1
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == cl1
    assert (tmp_path / "results/gallery/cmp/NOTICE.md").read_text(encoding="utf-8") == ntxt1


def test_unmodified_prompt_labeled_verbatim_same(tmp_path, monkeypatch, capsys):
    """No adapted files + best_from_round 1 → executed prompt IS base.md (v1)
    and the right column must carry the 两侧同题逐字相同 marker."""
    monkeypatch.chdir(tmp_path)
    _seed_repo(tmp_path)
    _img(tmp_path, "runs/genimages/round-1/c5.png")
    _img(tmp_path, "third_party/ref/data/images/case300.jpg")
    _prov(tmp_path, 300, "")
    _prompts(tmp_path, 300, base="ONLY BASE 300")
    _report(tmp_path, "final", [_row(300, "win", 9.0, 8.5, "runs/genimages/round-1/c5.png",
                                     seed="11", best_round=1)])
    assert rg.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "右 · SenseNova-U1.5（复现 v1，best from round 1）" in out
    assert "SenseNova 执行提示词（v1，两侧同题逐字相同）" in out
    assert "ONLY BASE 300" in out
    assert "seed 11 · 50 步 · balanced · 确定性可复现 · best from round 1" in out


def test_dry_run_prints_planned_sections_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _full_fixture(tmp_path)
    md_before = (tmp_path / "README.md").read_text(encoding="utf-8")
    cl_before = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert rg.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "results/gallery/cmp/case511.webp" in out
    assert "GALLERY_EN" in out and "RESULTS_TABLE" in out
    assert "✅ 已判分" in out
    # nothing written: README/CHANGELOG untouched, no cmp images, no NOTICE
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == md_before
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == cl_before
    assert not (tmp_path / "results/gallery/cmp/case511.webp").exists()
    assert not (tmp_path / "results/gallery/cmp/NOTICE.md").exists()


def test_final_report_wins_and_round_filter(tmp_path, monkeypatch):
    """runs/comparisons/final/report.json outranks every round-N report;
    --round still pins an older one (banner without public link then)."""
    monkeypatch.chdir(tmp_path)
    _seed_repo(tmp_path)
    _img(tmp_path, "runs/genimages/round-1/r1.png")
    _img(tmp_path, "third_party/ref/data/images/case511.jpg")
    _prov(tmp_path, 511, "")
    _prompts(tmp_path, 511, base="B")
    _report(tmp_path, 1, [_row(511, "fail", 4.0, 9.0, "runs/genimages/round-1/r1.png",
                               best_round=1)])
    _report(tmp_path, "final", [_row(511, "parity", 8.0, 8.0,
                                     "runs/genimages/round-1/r1.png", best_round=1)])
    assert rg.main([]) == 0
    md = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "| case-511 | parity | 8.00 / 8.00 | +0.00 | 1 |" in md
    assert "round final" in md
    assert "results/comparisons/final/report.json" in md

    (tmp_path / "README.md").unlink()
    _seed_repo(tmp_path)
    assert rg.main(["--round", "1"]) == 0
    md = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "| case-511 | capped | 4.00 / 9.00 | -5.00 | 1 |" in md
    assert "round 1" in md
    assert "results/comparisons/final/report.json" not in md


def test_missing_round_report_is_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed_repo(tmp_path)
    assert rg.main(["--round", "9"]) == 1
    assert "--round 9" in capsys.readouterr().err


def test_null_winner_or_missing_ref_skipped_from_gallery(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed_repo(tmp_path)
    wpng = _img(tmp_path, "runs/genimages/round-1/ok.png")
    _img(tmp_path, "third_party/ref/data/images/case511.jpg")   # ref only for 511
    _prov(tmp_path, 511, "")
    _prov(tmp_path, 208, "")
    _prompts(tmp_path, 511, base="B5")
    _prompts(tmp_path, 208, base="B208")
    _report(tmp_path, 1, [
        _row(511, "parity", 8.0, 8.0, wpng, best_round=1),
        _row(208, "fail", 5.0, 6.0, "runs/genimages/round-1/gone.png", best_round=1),
        _row(33, "win", 9.0, 8.0, None, best_round=1),
    ], deferred=[34])
    assert rg.main([]) == 0
    captured = capsys.readouterr()
    md = (tmp_path / "README.md").read_text(encoding="utf-8")
    galleries = md.split("<!-- RESULTS_TABLE -->")[0]
    assert "## case-208" not in galleries and "## case-33" not in galleries
    tbl = md.split("<!-- RESULTS_TABLE -->")[1]
    assert "| case-208 | capped | 5.00 / 6.00 | -1.00 | 1 |" in tbl
    assert "case-34" in tbl                      # deferred goes to note line
    assert "| case-34 |" not in tbl
    assert "case-208" in captured.err and "case-33" in captured.err
    assert "skipped" in captured.out
    # 511 published fine (winner + ref both present)
    assert (tmp_path / "results/gallery/cmp/case511.webp").exists()
    assert (tmp_path / "results/gallery/cmp/case511-winner.webp").exists()


def test_unknown_status_kept_raw_and_warned(tmp_path, monkeypatch, capsys):
    """An undocumented status must never be relabelled 'capped'; it shows
    verbatim in the conclusions table with a stderr warning."""
    monkeypatch.chdir(tmp_path)
    _seed_repo(tmp_path)
    _img(tmp_path, "runs/genimages/round-3/odd.png")
    _img(tmp_path, "third_party/ref/data/images/case777.jpg")
    _prov(tmp_path, 777, "https://example.com/u777")
    _prompts(tmp_path, 777, base="B")
    _report(tmp_path, 3, [_row(777, "weird", 7.0, 7.0,
                               "runs/genimages/round-3/odd.png", best_round=1)])
    assert rg.main([]) == 0
    err = capsys.readouterr().err
    assert "unknown status 'weird' for case 777" in err
    md = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "| case-777 | weird | 7.00 / 7.00 | +0.00 | 1 |" in md
    assert "capped" not in md


def test_pipes_escaped_in_prompts_and_prose(tmp_path, monkeypatch):
    """'|' inside prompt text / category / url prose is escaped so every case
    keeps exactly one intact markdown row in the two-column table."""
    monkeypatch.chdir(tmp_path)
    _seed_repo(tmp_path)
    _img(tmp_path, "runs/genimages/round-1/p.png")
    _img(tmp_path, "third_party/ref/data/images/case511.jpg")
    _prov(tmp_path, 511, "https://example.com/a|b", category="Posters | Typography")
    _prompts(tmp_path, 511, base="draw | a | pipe")
    _report(tmp_path, 1, [_row(511, "parity", 8.0, 8.0,
                               "runs/genimages/round-1/p.png", best_round=1)])
    pytest.importorskip("PIL")
    assert rg.main([]) == 0
    md = (tmp_path / "README.md").read_text(encoding="utf-8")
    zh = md.split("<!-- GALLERY_ZH -->")[1].split("## 对比结论")[0]
    rows = [l for l in zh.splitlines() if l.startswith("| 效果图 |")]
    assert len(rows) == 1                       # exactly one intact image row
    unescaped = rows[0].replace("\\|", "")
    assert unescaped.count("|") == 4            # 3-col row has only 4 real pipes
    assert "draw \\| a \\| pipe" in zh
    assert "Posters \\| Typography" in zh


def test_empty_state_is_graceful(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed_repo(tmp_path)
    assert rg.main([]) == 0                       # rc 0, friendly message
    assert "no comparison reports" in capsys.readouterr().out
    md = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert md.index("GALLERY_EN") < md.index("GALLERY_ZH") < md.index("RESULTS_TABLE")


def test_normalize_pair_needs_pil_only_at_call_time():
    """Pillow is imported lazily inside normalize_pair: blocking it must not
    break the module import, only the actual image call."""
    monkey = pytest.MonkeyPatch()
    monkey.setitem(sys.modules, "PIL", None)
    try:
        with pytest.raises(ImportError):
            rg.normalize_pair("a.png", "b.png", "a.webp", "b.webp")
    finally:
        monkey.undo()
