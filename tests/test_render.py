"""Golden tests for the bilingual gallery renderer (task 16).

Fixture per brief Step 1: one parity case + one capped case. Assertions cover
status badges, exact numeric values, repo-relative image paths (never runs/
absolute paths), and the sourceUrl-null guard (15 pilot cases ship without a
provenance.source_url, so a dead markdown link must never be emitted).
"""
import json
from pathlib import Path

import render_gallery as rg


def _row(cid, status, cand, ref, winner=None):
    return {"case_id": cid, "status": status, "candidate_mean": cand,
            "reference_mean": ref, "gap": round(cand - ref, 4),
            "checks": {}, "failed_checks": [],
            "winner_entry_id": "e-best", "winner_seed": "7", "winner_file": winner}


def _report(tmp_path, rnd, per_case, deferred=None):
    d = tmp_path / f"runs/comparisons/round-{rnd}"
    d.mkdir(parents=True)
    total = len(per_case)
    (d / "report.json").write_text(json.dumps(
        {"round": rnd, "per_case": per_case, "deferred": deferred or [],
         "milestone": {"parity_count": sum(r["status"] == "parity" for r in per_case),
                       "win_count": sum(r["status"] == "win" for r in per_case),
                       "target": 24, "total": total, "parity_ratio": 0.0,
                       "overall_gap": 0.0}}), encoding="utf-8")


def _img(tmp_path, rel):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\x89PNG\r\n\x1a\nfixture-bytes")
    return rel


def _prov(tmp_path, cid, url, category="Posters & Typography"):
    p = tmp_path / f"cases/pilot/case-{cid}/provenance.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"case_id": cid, "category": category,
                             "source_url": url}), encoding="utf-8")


def _seed_repo(tmp_path):
    """README/CHANGELOG mirrors of the live repo: ZH gallery marker + table
    marker exist, the EN gallery marker does not."""
    (tmp_path / "README.md").write_text(
        "# awesome-sensenova-u1.5\n\nintro...\n\n"
        "## 画廊\n\n<!-- GALLERY_ZH -->\n\n## 对比结论\n\n"
        "<!-- RESULTS_TABLE -->\n\n## 快速开始\n\nrun it.\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 0.1.0 (2026-08-27)\n\n- init.\n", encoding="utf-8")


def _full_fixture(tmp_path):
    """1 parity (png, linked upstream) + 1 capped/fail (webp, source_url '')."""
    _seed_repo(tmp_path)
    w511 = _img(tmp_path, "runs/genimages/round-2/case511-s7.png")
    w208 = _img(tmp_path, "runs/genimages/round-2/case208-s3.webp")
    _prov(tmp_path, 511, "https://example.com/upstream/case511")
    _prov(tmp_path, 208, "")
    _report(tmp_path, 2, [
        _row(511, "parity", 8.0, 7.2, w511),
        _row(208, "fail", 6.5, 7.1, w208),
    ])
    return w511, w208


# --- main golden path --------------------------------------------------------


def test_gallery_table_and_copies(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _, _ = _full_fixture(tmp_path)
    assert rg.main([]) == 0

    md = (tmp_path / "README.md").read_text(encoding="utf-8")
    # R8: all three markers exist, EN above ZH, table last
    assert md.count("<!-- GALLERY_EN -->") == 1
    assert md.count("<!-- GALLERY_ZH -->") == 1
    assert md.count("<!-- RESULTS_TABLE -->") == 1
    assert md.index("GALLERY_EN") < md.index("GALLERY_ZH") < md.index("RESULTS_TABLE")

    # repo-relative committed paths only; no runs/ leakage into the README
    assert "results/gallery/case-511.png" in md
    assert "results/gallery/case-208.webp" in md
    assert "runs/genimages" not in md
    assert "runs/comparisons" not in md

    # copied winner images land under results/gallery with suffix preserved
    g511 = tmp_path / "results/gallery/case-511.png"
    g208 = tmp_path / "results/gallery/case-208.webp"
    assert g511.read_bytes() == b"\x89PNG\r\n\x1a\nfixture-bytes"
    assert g208.exists()

    # status badges appear in the gallery rows (inline-code chips)
    assert "`parity`" in md and "`capped`" in md

    # ZH row golden fragments
    zh = md.split("<!-- GALLERY_ZH -->")[1].split("## 对比结论")[0]
    assert "| 案例 | 我方图 | 上游回链 |" in zh
    assert "我方图 <img src=\"results/gallery/case-511.png\" width=\"420\"/>" in zh
    assert "上游回链 [case 511](https://example.com/upstream/case511)" in zh
    # sourceUrl null-guard: plain text, never a dead markdown link
    assert "上游案例 #208（未附来源链接）" in zh
    assert "](http" not in zh.split("case-208")[1]

    # EN row equivalents
    en = md.split("<!-- GALLERY_EN -->")[1].split("<!-- GALLERY_ZH -->")[0]
    assert "| Case | Ours | Upstream |" in en
    assert "ours <img src=\"results/gallery/case-511.png\" width=\"420\"/>" in en
    assert "upstream link [case 511](https://example.com/upstream/case511)" in en
    assert "upstream case #208 (no source link)" in en

    # conclusions table: exact status strings and honest negative gap
    tbl = md.split("<!-- RESULTS_TABLE -->")[1].split("## 快速开始")[0]
    assert "| case | 状态 | 我方均分 | 参考均分 | 差值 |" in tbl
    assert "| case-511 | parity | 8.00 | 7.20 | +0.80 |" in tbl
    assert "| case-208 | capped | 6.50 | 7.10 | -0.60 |" in tbl
    assert "fail" not in tbl          # capped wording only, per ruling

    # idempotent second run: README stable, Unreleased stub appears once
    md1 = md
    cl1 = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert cl1.count("## Unreleased") == 1
    assert "render_gallery" in cl1
    assert rg.main([]) == 0
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == md1
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == cl1


def test_latest_round_wins_and_round_filter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_repo(tmp_path)
    _prov(tmp_path, 511, "https://example.com/u/511")
    w1 = _img(tmp_path, "runs/genimages/round-1/r1.png")
    w2 = _img(tmp_path, "runs/genimages/round-2/r2.png")
    _report(tmp_path, 1, [_row(511, "fail", 4.0, 9.0, w1)])
    _report(tmp_path, 2, [_row(511, "win", 9.0, 8.0, w2)])
    assert rg.main([]) == 0
    md = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "| case-511 | win | 9.00 | 8.00 | +1.00 |" in md
    assert "round-2" in md

    (tmp_path / "README.md").unlink()
    _seed_repo(tmp_path)
    assert rg.main(["--round", "1"]) == 0
    md = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "| case-511 | capped | 4.00 | 9.00 | -5.00 |" in md
    assert "round-1" in md


def test_missing_round_report_is_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed_repo(tmp_path)
    assert rg.main(["--round", "9"]) == 1
    assert "--round 9" in capsys.readouterr().err


def test_null_winner_skipped_from_gallery_listed_at_end(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed_repo(tmp_path)
    wpng = _img(tmp_path, "runs/genimages/round-1/ok.png")
    _prov(tmp_path, 511, "")
    _prov(tmp_path, 208, "")
    _report(tmp_path, 1, [
        _row(511, "parity", 8.0, 8.0, wpng),
        _row(208, "fail", 5.0, 6.0, None),      # hand-forged/partial state
    ], deferred=[33])
    assert rg.main([]) == 0
    captured = capsys.readouterr()
    md = (tmp_path / "README.md").read_text(encoding="utf-8")
    zh_en_galleries = md.split("<!-- RESULTS_TABLE -->")[0]
    assert "case-208" not in zh_en_galleries     # skipped from both galleries
    tbl = md.split("<!-- RESULTS_TABLE -->")[1]
    assert "| case-208 | capped | 5.00 | 6.00 | -1.00 |" in tbl
    assert "case-33" in tbl                      # deferred goes to note line, not a row
    assert "| case-33 |" not in tbl
    assert "case-208" in captured.err            # per-case stderr warning
    assert "skipped" in captured.out             # end-of-run skipped summary
    assert not (tmp_path / "results/gallery/case-208.png").exists()


def test_dry_run_prints_planned_sections_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _full_fixture(tmp_path)
    md_before = (tmp_path / "README.md").read_text(encoding="utf-8")
    cl_before = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert rg.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    # planned fragments visible on stdout
    assert "results/gallery/case-511.png" in out
    assert "GALLERY_EN" in out and "RESULTS_TABLE" in out
    assert "上游案例 #208（未附来源链接）" in out
    # nothing written: README untouched, changelog untouched, no copies
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == md_before
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == cl_before
    assert not (tmp_path / "results/gallery/case-511.png").exists()


def test_empty_state_is_graceful(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed_repo(tmp_path)
    assert rg.main([]) == 0                       # rc 0, friendly message
    assert "no comparison reports" in capsys.readouterr().out
    md = (tmp_path / "README.md").read_text(encoding="utf-8")
    # R8 still satisfied: renderer ensures all three markers exist
    assert md.index("GALLERY_EN") < md.index("GALLERY_ZH") < md.index("RESULTS_TABLE")
