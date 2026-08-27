# awesome-sensenova-u1.5 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立"提示词盲评→自动改写→重生成"的全自动评测闭环，在 ROCm 7.14.0 + gfx1100 上让 SenseNova-U1.5 与 GPT-Image-2 同题案例量化对比并开源成果。

**Architecture:** 新仓库 `awesome-sensenova-u1.5` 内 14 个纯标准库 Python CLI + 3 个 bash 入口组成七阶段状态机；唯一共享状态是只追加的 `ledger/append.jsonl`；GPU 只有 `generate.sh` 一个触点（包装基础仓库 `run-task.sh` 批量 JSONL）；GLM-5.3-Flash 视觉判官经双后端（本机子代理通道 / 可选智谱 API）按统一量规产出结构化 verdict。

**Tech Stack:** Python 3 stdlib only（运行时零 pip 依赖，pytest 仅测试用）、bash、SenseNova-U1.5-ROCm 现有推理管线（torch 2.12.0+rocm7.14.0）。

**Spec:** `docs/superpowers/specs/2026-08-27-awesome-sensenova-u15-design.md`（全部阈值的出处，执行者必须同时携带阅读）

## Global Constraints

- 运行环境铁律：一切 GPU 工作经 `/workspace/venv-torch212`（torch 版本字符串精确等于 `2.12.0+rocm7.14.0`），本项目不新建任何带 torch 的虚拟环境。
- 本项目自己的脚本只依赖 Python 3 标准库（json/hashlib/argparse/pathlib/random/re/urllib/http 等）；pytest 是唯一的开发期依赖，装进 `.venv-test`。
- 仓库内所有新建 prose（md/txt/commit message）一律自然换行、禁止 76 列硬换行（工作区 AGENTS.md 规范）；代码块内部不受此限。
- 持久化纪律：所有状态在 `/workspace/awesome-sensenova-u1.5` 下；系统级安装永不假设持久，一律写成仓库脚本。
- 台账是唯一事实来源：跨脚本数据传递一律经 `ledger/append.jsonl` 事件回放，幂等键见各任务"Produces"；重复执行任何脚本必须安全（先查事件再动作）。
- 上游资产锁定：freestylefly/awesome-gpt-image-2 commit `9a7b2e9c39f816d6c699c2a133e11b6d8bfdc464`，其 `data/cases.json` sha256 必须等于 `bfb8a8e71a66beb33bd50590c79d5f22d43ae7c4350bcabb1a1dcd616b39d962`；`third_party/ref/` 整体 gitignore，绝不提交上游图片。
- 判官双盲：判官永远拿不到来源信息；`results/judge/` 中也不允许出现对生成方模型的推断描述（schemas.py 中的泄露扫描负责把关）。
- 数值常量（与 spec §8 一致，代码中定义于 `scripts/lib/constants.py`）：`GAP_ALLOW=-0.5`、`PARITY_RATIO=0.8`、`MAX_REWRITE_ROUNDS=3`、`SEEDS_PER_PROMPT=2`、`PILOT_SIZE=30`、`ARBITER_MEAN_DIFF=2.0`、`RESAMPLE_RATE=0.1`。
- 对外发布边界：本计划全程只做本地 commit，`git push` 永远由作者人工触发。
- 关键路径存在性（前置检查）：基础仓库在 `/workspace/SenseNova-U1.5-ROCm`，判官探针凭据在 `docs/receipts/judge-probe-verdict.json`。
- 所有脚本一律假定以仓库根作为当前目录执行（`setup.sh` 与 `operator-loop.md` 中的命令序列均先 `cd` 到根）。

---

### Task 1: 仓库脚手架与测试基座

**Files:** Create: `.gitignore`, `LICENSE`, `tests/conftest.py`, `tests/test_smoke.py`, `README.md`（骨架）, `CHANGELOG.md`（骨架）

**Interfaces:** Produces: 后续所有任务的 pytest 基座；README 里的画廊占位标记 `<!-- GALLERY_EN -->` / `<!-- GALLERY_ZH -->` / `<!-- RESULTS_TABLE -->`（Task 16 会填充）。

- [ ] **Step 1: 写 .gitignore**

```gitignore
third_party/
runs/
.venv-test/
__pycache__/
*.pyc
.DS_Store
```

- [ ] **Step 2: 复制 Apache-2.0 协议文本**

```bash
cp /workspace/SenseNova-U1.5-ROCm/LICENSE LICENSE
```

- [ ] **Step 3: 建 README 骨架与 CHANGELOG**

README.md 内容（骨架即可，后续任务填充）：

```markdown
# awesome-sensenova-u1.5

把 [awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2) 的社区案例作为量化基线，用 SenseNova-U1.5-8B-MoT 在 AMD ROCm 7.14.0 全栈上同题复现，由 GLM-5.3-Flash 视觉判官盲评，自动迭代提示词直至打平，开源提示词库、效果图与全部评审凭据。

## 画廊

<!-- GALLERY_ZH -->

## 对比结论

<!-- RESULTS_TABLE -->

## 快速开始

见 `scripts/setup.sh`。设计文档见 `docs/superpowers/specs/`。
```

CHANGELOG.md：

```markdown
# Changelog

## 0.1.0 (2026-08-27)

- 项目立项；设计 spec 与实施计划入库。
```

- [ ] **Step 4: 建 conftest.py 让测试能 import scripts/lib**

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
```

tests/test_smoke.py：

```python
def test_repo_layout():
    root = Path(__file__).resolve().parents[1]
    assert (root / "docs" / "superpowers" / "specs").is_dir()
```

（顶部需 `from pathlib import Path`）

- [ ] **Step 5: 建 .venv-test 并验证 pytest 可跑**

```bash
python3 -m venv .venv-test && .venv-test/bin/pip install -q pytest && .venv-test/bin/pytest tests/ -q
```
Expected: `1 passed`

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: repo scaffold, license, README skeleton, pytest base"
```

---

### Task 2: 台账库 scripts/lib/ledger.py

**Files:** Create: `scripts/lib/__init__.py`(空), `scripts/lib/ledger.py`; Test: `tests/test_ledger.py`

**Interfaces:** Produces:
- `append_event(path: str|Path, etype: str, payload: dict, idem: str|None = None) -> dict`——追加一行事件；若历史中已有相同 `idem` 则直接返回既有事件且不追加（幂等）。
- `load_events(path) -> list[dict]`；`latest(events, etype, key_fn)` —— 按 `key_fn(event)` 取该键下最新一条指定类型事件。
- 事件格式：`{"ts": ISO-UTC, "type": str, "idem": str|null, "payload": {...}}`。

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**：`.venv-test/bin/pytest tests/test_ledger.py -q` → ImportError
- [ ] **Step 3: 实现 ledger.py**

```python
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
```

- [ ] **Step 4: 跑测试确认通过**：`.venv-test/bin/pytest tests/test_ledger.py -q` → 2 passed
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat: append-only event ledger with idempotency"`

---

### Task 3: verdict schema 校验器 scripts/lib/schemas.py

**Files:** Create: `scripts/lib/schemas.py`; Test: `tests/test_schemas.py`

**Interfaces:** Produces:
- `validate_verdict(verdict: dict) -> list[str]`（空列表=合法；校验对象是附录 B 的 verdict 体）
- `model_identity_leak(verdict: dict) -> list[str]`——扫描文本字段，返回疑似推断生成方的句子片段
- `extract_json(text: str) -> dict|None`——从 LLM 输出里截取第一个平衡 JSON 对象
- 常量 `SCORE_KEYS = ["quality","aesthetics","alignment","real_world_fidelity","creative_generation"]`

- [ ] **Step 1: 失败测试（合法样例抄自本仓库 `docs/receipts/judge-probe-verdict.json` 的候选体结构）**

```python
from schemas import SCORE_KEYS, extract_json, model_identity_leak, validate_verdict

GOOD = {
    "scores": {k: 8 for k in SCORE_KEYS},
    "score_reasons": {k: "ok" for k in SCORE_KEYS},
    "unfulfilled_requirements": [],
    "transcribed_text": ["TITLE"],
    "hard_flags": {
        "display_text_correct": True,
        "small_text_quality": "correct",
        "text_miss_count": 0,
        "visual_defects": False,
    },
}


def test_good_passes():
    assert validate_verdict(GOOD) == []


def test_bad_scores_rejected():
    bad = {**GOOD, "scores": {**GOOD["scores"], "quality": 11}}
    assert any("quality" in e for e in validate_verdict(bad))


def test_missing_hard_flags_rejected():
    bad = {k: v for k, v in GOOD.items() if k != "hard_flags"}
    assert validate_verdict(bad)


def test_identity_leak_scan():
    leaky = {**GOOD, "score_reasons": {**GOOD["score_reasons"], "quality": "typical gpt-image output"}}
    assert model_identity_leak(leaky)
    assert model_identity_leak(GOOD) == []


def test_extract_json_from_fenced():
    txt = 'bla\n```json\n{"a": 1}\n```\ntail'
    assert extract_json(txt) == {"a": 1}
```

- [ ] **Step 2: 跑失败** → ImportError
- [ ] **Step 3: 实现**

```python
"""Verdict schema validation (spec Appendix B) plus LLM-output helpers."""
import json
import re

SCORE_KEYS = ["quality", "aesthetics", "alignment", "real_world_fidelity", "creative_generation"]
_SMALL_TEXT = {"correct", "mildly_deformed", "garbled"}
_BANNED = re.compile(r"gpt[-_ ]?image|sensenova|openai", re.I)


def validate_verdict(v):
    errs = []
    scores = v.get("scores")
    if not isinstance(scores, dict):
        return ["scores: missing object"]
    for k in SCORE_KEYS:
        val = scores.get(k)
        if not isinstance(val, int) or isinstance(val, bool) or not 0 <= val <= 10:
            errs.append(f"scores.{k}: must be int in [0,10]")
    reasons = v.get("score_reasons")
    if not isinstance(reasons, dict) or any(k not in reasons for k in SCORE_KEYS):
        errs.append("score_reasons: must cover all five dims")
    for key in ("unfulfilled_requirements", "transcribed_text"):
        if not isinstance(v.get(key), list):
            errs.append(f"{key}: must be list")
    hf = v.get("hard_flags")
    if not isinstance(hf, dict):
        errs.append("hard_flags: missing object")
        return errs
    if not isinstance(hf.get("display_text_correct"), bool):
        errs.append("hard_flags.display_text_correct: must be bool")
    if hf.get("small_text_quality") not in _SMALL_TEXT:
        errs.append("hard_flags.small_text_quality: enum correct|mildly_deformed|garbled")
    miss = hf.get("text_miss_count")
    if not isinstance(miss, int) or isinstance(miss, bool) or miss < 0:
        errs.append("hard_flags.text_miss_count: must be int >= 0")
    if not isinstance(hf.get("visual_defects"), bool):
        errs.append("hard_flags.visual_defects: must be bool")
    return errs


def model_identity_leak(v):
    texts = [str(t) for t in v.get("transcribed_text", [])]
    texts += [str(t) for t in v.get("unfulfilled_requirements", [])]
    reasons = v.get("score_reasons") or {}
    texts += [str(x) for x in reasons.values()]
    return [t[:120] for t in texts if _BANNED.search(t)]


def extract_json(text):
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    start = None
    return None
```

同时在 T3 建立 `tests/fixtures.py` 共享合法样例（后续 T11/T13/T15 复用同一份）：

```python
from schemas import SCORE_KEYS

GOOD_VERDICT = {
    "scores": {k: 8 for k in SCORE_KEYS},
    "score_reasons": {k: "ok" for k in SCORE_KEYS},
    "unfulfilled_requirements": [],
    "transcribed_text": ["TITLE"],
    "hard_flags": {
        "display_text_correct": True,
        "small_text_quality": "correct",
        "text_miss_count": 0,
        "visual_defects": False,
    },
}
```

- [ ] **Step 4: 跑通过** → 5 passed
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat: verdict schema validator, identity-leak scan, json extraction"`

---

### Task 4: 上游参考数据拉取 scripts/fetch-reference.sh

**Files:** Create: `scripts/fetch-reference.sh`

**Interfaces:** Consumes: Global Constraints 中的 commit/sha256 常量。Produces: `third_party/ref/{data/cases.json,data/images/,LICENSE,README.md}`、`third_party/ref-manifest.json`（内容含 commit、cases.json sha256、fetch 时间）、台账事件 `ref_fetched`（idem=commit 前 12 位）。再跑一遍若 manifest 中 commit 相同则跳过（幂等）。

- [ ] **Step 1: 写脚本**

```bash
#!/usr/bin/env bash
# Fetch pinned awesome-gpt-image-2 assets into third_party/ref (never committed).
# Usage: bash scripts/fetch-reference.sh [--dry-run]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT="9a7b2e9c39f816d6c699c2a133e11b6d8bfdc464"
CASES_SHA="bfb8a8e71a66beb33bd50590c79d5f22d43ae7c4350bcabb1a1dcd616b39d962"
REF="$ROOT/third_party/ref"
LEDGER="$ROOT/ledger/append.jsonl"
mkdir -p "$ROOT/third_party"

if [ -f "$REF/../ref-manifest.json" ] && grep -q "$COMMIT" "$REF/../ref-manifest.json"; then
    echo "[skip] ref already fetched at $COMMIT"; exit 0
fi
if [ "${1:-}" = "--dry-run" ]; then
    echo "[dry-run] would clone github.com/freestylefly/awesome-gpt-image-2 at $COMMIT"
    echo "[dry-run] would verify data/cases.json sha256 == $CASES_SHA"
    exit 0
fi
rm -rf /tmp/agi2-src "$REF"
GIT_SSL_NO_VERIFY=1 git clone https://github.com/freestylefly/awesome-gpt-image-2.git /tmp/agi2-src
git -C /tmp/agi2-src checkout "$COMMIT"
ACTUAL=$(sha256sum /tmp/agi2-src/data/cases.json | cut -d' ' -f1)
if [ "$ACTUAL" != "$CASES_SHA" ]; then
    echo "[FATAL] cases.json sha mismatch: $ACTUAL" >&2; exit 1
fi
mv /tmp/agi2-src "$REF-parent" && rm -rf "$REF-parent"/.github "$REF-parent"/src \
    || mv /tmp/agi2-src "$REF"
rm -rf "$REF/.git"
printf '{"commit":"%s","cases_sha256":"%s","fetched_at":"%s"}\n' \
    "$COMMIT" "$CASES_SHA" "$(date -u +%FT%TZ)" > "$ROOT/third_party/ref-manifest.json"
python3 - "$LEDGER" "$COMMIT" <<'PY'
import sys; sys.path.insert(0, __import__("pathlib").Path(sys.argv[1]).parents[1] / "scripts")
from lib.ledger import append_event
append_event(sys.argv[1], "ref_fetched", {"commit": sys.argv[2]}, idem=sys.argv[2][:12])
PY
echo "[ok] reference fetched and verified"
```

（注：executor 若发现 clone 出的目录结构与上面两个 mv 分支处理不符，以"最终 `$REF` 下有 `data/cases.json` 与 `data/images/`"为准收尾。）

- [ ] **Step 2: 语法与 dry-run 自测**

```bash
bash -n scripts/fetch-reference.sh && bash scripts/fetch-reference.sh --dry-run
```
Expected: 两行 `[dry-run]` 输出，退出码 0

- [ ] **Step 3: Checkpoint（联网实跑，一次性）**

```bash
bash scripts/fetch-reference.sh && ls third_party/ref/data/images | wc -l
```
Expected: 图片数 ≥ 500 且打印 `[ok]`

- [ ] **Step 4: 再跑一遍确认幂等跳过** → `[skip]`
- [ ] **Step 5: Commit**（确认 `git status` 不含 third_party/ 后）`git add -A && git commit -m "feat: pinned reference fetcher with sha256 verification"`

---

### Task 5: Pilot 策展 scripts/select-pilot.py

**Files:** Create: `scripts/select-pilot.py`; Test: `tests/test_select_pilot.py`

**Interfaces:** Consumes: `third_party/ref/data/cases.json`、台账路径默认 `ledger/append.jsonl`。Produces:
- `configs/pilot.lock.json`：`{"upstream_commit": ..., "cases_sha256": ..., "size": 30, "cases": [{"id","title","category","prompt_len"}...]}`（按 id 升序）
- `cases/pilot/case-{id}/base.md`（案例原始 prompt 一字不改）与 `provenance.json`（case 元数据 + sourceUrl 回链 + selected_at）
- 台账事件 `case_selected`（idem=`sel-{id}`）

配额常量（合计 30）：Posters & Typography 6、Photography & Realism 4、UI & Interfaces 4、Illustration & Art 3、Charts & Infographics 2、Products & E-commerce 2、Brand & Logos 1、Scenes & Storytelling 2、Architecture & Spaces 1、History & Classical Themes 2、Documents & Publishing 1、Characters & People 1、Other Use Cases 1。

- [ ] **Step 1: 失败测试**

```python
import json
import select_pilot as sp


def _mk(cid, cat, prompt):
    return {"id": cid, "title": f"t{cid}", "category": cat, "prompt": prompt,
            "image": f"/images/case{cid}.jpg", "sourceUrl": "https://x.com/x"}


def _bank():
    c = [_mk(i, "Posters & Typography", "poster art") for i in range(10)]
    c += [_mk(100 + i, "UI & Interfaces", "clean ui screenshot") for i in range(8)]
    c += [_mk(200, "Photography & Realism", "upload your portrait and edit it")]
    return {"repository": "r", "cases": c}


def test_edit_cases_filtered(tmp_path):
    picked = sp.pick_cases(_bank(), exclude_file=None)
    ids = [x["id"] for x in picked]
    assert 200 not in ids


def test_quota_total_and_order(tmp_path):
    picked = sp.pick_cases(_bank(), exclude_file=None)
    cats = {}
    for x in picked:
        cats[x["category"]] = cats.get(x["category"], 0) + 1
    assert sum(cats.values()) == min(sp.PILOT_SIZE, 18)  # bank too small → take all
    assert picked == sorted(picked, key=lambda x: x["id"])
```

- [ ] **Step 2: 跑失败** → ModuleNotFoundError
- [ ] **Step 3: 实现 select-pilot.py**

```python
#!/usr/bin/env python3
"""Select the 30-case pilot batch deterministically (spec §5 SELECT)."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from lib.constants import PILOT_SIZE
from lib.ledger import append_event

QUOTAS = {
    "Posters & Typography": 6,
    "Photography & Realism": 4,
    "UI & Interfaces": 4,
    "Illustration & Art": 3,
    "Charts & Infographics": 2,
    "Products & E-commerce": 2,
    "Brand & Logos": 1,
    "Scenes & Storytelling": 2,
    "Architecture & Spaces": 1,
    "History & Classical Themes": 2,
    "Documents & Publishing": 1,
    "Characters & People": 1,
    "Other Use Cases": 1,
}
EDIT_MARKERS = (
    "upload", "uploads", "uploaded", "attach ", "attached",
    "photo i provide", "provide the photo", "for each photo",
    "reference image you", "the uploaded",
)


def is_edit_case(prompt: str) -> bool:
    low = " " + prompt.lower()
    return any(m in low for m in EDIT_MARKERS)


def pick_cases(cases_data: dict, exclude_file) -> list:
    """Filter, then quota-sample per category (id-ascending), redistributing any
    shortfall to still-hungry categories in quota-decreasing order."""
    excludes = set()
    if exclude_file and Path(exclude_file).exists():
        excludes = {int(x) for x in Path(exclude_file).read_text().split() if x.strip().isdigit()}
    by_cat = {}
    for c in cases_data["cases"]:
        if c["id"] in excludes or is_edit_case(c.get("prompt", "")):
            continue
        by_cat.setdefault(c.get("category", "Other Use Cases"), []).append(c)
    picked = []
    hungry = []
    for cat, quota in sorted(QUOTAS.items(), key=lambda kv: -kv[1]):
        cand = sorted(by_cat.get(cat, []), key=lambda x: x["id"])[:quota]
        picked += cand
        short = quota - len(cand)
        if short > 0 and by_cat.get(cat):
            hungry.append((short, cat))
    if hungry:
        taken_ids = {x["id"] for x in picked}
        for _, cat in hungry:
            rest = [x for x in sorted(by_cat.get(cat, []), key=lambda x: x["id"]) if x["id"] not in taken_ids]
            picked += rest[:1]
            taken_ids |= {x["id"] for x in rest[:1]}
    return sorted(picked, key=lambda x: x["id"])[:PILOT_SIZE]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="third_party/ref/data/cases.json")
    ap.add_argument("--ledger", default="ledger/append.jsonl")
    ap.add_argument("--exclude-file", default="configs/exclude-cases.txt")
    args = ap.parse_args()
    data = json.loads(Path(args.ref).read_text(encoding="utf-8"))
    cases = pick_cases(data, args.exclude_file)
    print(f"[select] picked {len(cases)} cases")
    cas_dir = Path("cases/pilot")
    lock_cases = []
    for c in cases:
        d = cas_dir / f"case-{c['id']}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "base.md").write_text(c["prompt"] + "\n", encoding="utf-8")
        meta = {"case_id": c["id"], "title": c.get("title"), "category": c.get("category"),
                "source_url": c.get("sourceUrl"), "upstream_image": c.get("image"),
                "styles": c.get("styles"), "scenes": c.get("scenes"),
                "selected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        (d / "provenance.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        append_event(args.ledger, "case_selected", {"case_id": c["id"]}, idem=f"sel-{c['id']}")
        lock_cases.append({"id": c["id"], "title": c.get("title"), "category": c.get("category"),
                           "prompt_len": len(c.get("prompt", ""))})
    manifest = json.loads(Path("third_party/ref-manifest.json").read_text())
    Path("configs/pilot.lock.json").write_text(json.dumps(
        {"upstream_commit": manifest["commit"], "cases_sha256": manifest["cases_sha256"],
         "size": len(lock_cases), "cases": lock_cases}, ensure_ascii=False, indent=2), encoding="utf-8")
    # Curation is not fully automatic by design: surface picks for a human glance.
    risky = [c["id"] for c in cases if c.get("category") in ("Characters & People", "Photography & Realism")]
    if risky:
        print(f"[review] likeness-sensitive categories picked: {risky}", file=sys.stderr)


if __name__ == "__main__":
    main()
```

同时建 `scripts/lib/constants.py`：

```python
GAP_ALLOW = -0.5
PARITY_RATIO = 0.8
MAX_REWRITE_ROUNDS = 3
SEEDS_PER_PROMPT = 2
PILOT_SIZE = 30
ARBITER_MEAN_DIFF = 2.0
RESAMPLE_RATE = 0.1
```

测试里 `select_pilot.py` 的导入方式靠 conftest 把 `scripts/` 加进 sys.path，但模块在 `scripts/` 根而 lib 在 `scripts/lib/`——所以 conftest 还需加第二行 sys.path 或在 select_pilot 顶部插 `sys.path.insert(0, str(Path(__file__).parent))` 后 `from lib.constants import ...`。executor 保持两者一致即可（计划已用后者方案，tests 里直接 `import select_pilot` 也要求 conftest 含 `sys.path.insert(0, str(ROOT/"scripts"))`，已有）。

- [ ] **Step 4: 跑通过** → 2 passed
- [ ] **Step 5: Checkpoint（真实数据）**

```bash
.venv-test/bin/python scripts/select-pilot.py && .venv-test/bin/python -c "import json;d=json.load(open('configs/pilot.lock.json'));print(d['size'],len({c['category'] for c in d['cases']}))"
```
Expected: `30 <类别数≤13>`；stderr 出现 review 行则按 specs §12 目视确认排除真人肖像案例，必要时把它们 id 写入 `configs/exclude-cases.txt` 后重跑（脚本可重跑，锁文件覆盖）。

- [ ] **Step 6: Commit** `git add -A && git commit -m "feat: deterministic 30-case pilot selection with edit-case filter"`

---

### Task 6: 环境自检 scripts/env-check.sh 与 setup.sh

**Files:** Create: `scripts/env-check.sh`, `scripts/setup.sh`

**Interfaces:** Consumes: `/workspace/venv-torch212`、`/workspace/SenseNova-U1.5-ROCm`。Produces: setup.sh 是全项目推荐入口；两者均可独立重复执行。

- [ ] **Step 1: env-check.sh**

```bash
#!/usr/bin/env bash
# Four hard assertions before anything touches the GPU (spec §9).
set -uo pipefail
fail() { echo "[env-check][FAIL] $*" >&2; exit 1; }
VENV_PY=/workspace/venv-torch212/bin/python
[ -x "$VENV_PY" ] || fail "venv-torch212 missing"
V=$("$VENV_PY" - <<'PY'
try:
    import torch; print(torch.__version__)
except Exception as e:
    print("IMPORT_FAIL", e)
PY
) || true
[ "$V" = "2.12.0+rocm7.14.0" ] || fail "torch version '$V' != 2.12.0+rocm7.14.0"
"$VENV_PY" -c "import torch.cuda, sys; torch.cuda.init(); sys.exit(0)" || fail "GPU init failed"
grep -q '^export HSA_OVERRIDE_GFX_VERSION=11.0.0$' /workspace/env.sh 2>/dev/null \
  || grep -q '^HSA_OVERRIDE_GFX_VERSION=11.0.0$' /workspace/env.sh 2>/dev/null \
  || [ -n "${HSA_OVERRIDE_GFX_VERSION:-}" ] \
  || fail "HSA_OVERRIDE_GFX_VERSION=11.0.0 absent (add 'export HSA_OVERRIDE_GFX_VERSION=11.0.0' to /workspace/env.sh)"
[ -d /workspace/SenseNova-U1.5-ROCm/third_party/SenseNova-U1 ] || fail "base repo checkout incomplete"
[ -f /workspace/SenseNova-U1.5-ROCm/scripts/run-task.sh ] || fail "run-task.sh missing"
echo "[env-check][PASS] rocm7.14 stack, gpu init, base repo"
```

- [ ] **Step 2: setup.sh**

```bash
#!/usr/bin/env bash
# One-command bring-up after any container rebuild (AGENTS.md persistence rules).
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/env-check.sh
bash scripts/fetch-reference.sh "$@"
mkdir -p runs/genimages runs/judge-queue results/gallery results/judge/_baseline ledger
[ -f .venv-test/bin/pytest ] || { python3 -m venv .venv-test && .venv-test/bin/pip install -q pytest; }
echo "[setup][done]"
```

- [ ] **Step 3: 自测** `bash -n scripts/env-check.sh && bash -n scripts/setup.sh` → 无输出退出码 0；随后实跑 `bash scripts/env-check.sh` → `[env-check][PASS] …`（Checkpoint：本机当前应通过，若 WARN HSA 行出现则依提示补 /workspace/env.sh 并 source 验证）
- [ ] **Step 4: Commit** `git add -A && git commit -m "feat: rocm7.14 env assertions and one-command setup"`

---

### Task 7: 生成批单 scripts/make-gen-jsonl.py

**Files:** Create: `scripts/make-gen-jsonl.py`; Test: `tests/test_make_gen_jsonl.py`

**Interfaces:** Consumes: `configs/pilot.lock.json`、`cases/pilot/*/base.md`、可选 `cases/pilot/*/adapted-v*.md`（多版本时选版本号最大的那个——这是 REWRITE 回灌的入口）、台账。Produces: `runs/gen/round-{R}/gen.jsonl`，每行字段恰为上游支持的四键 + type：`{"prompt":..., "width":..., "height":..., "seed":..., "type":"case{id}-r{R}-s{seed}"}`；跳过台账里本轮已有 `generated` 事件的 tag（断点续跑语义）。

尺寸桶规则：prompt 小写含 `vertical|portrait|poster|book cover` → 1664×2496；含 `horizontal|landscape|widescreen|banner` → 2496×1664；否则 2048×2048（命中多组时按顺序取先命中的那一组）。

种子：`stable_seed(case_id, round, k) = blake2b(f"{case_id}|{round}|{k}", digest_size=8) 大端整数 mod (2**31 - 1)`。

- [ ] **Step 1: 失败测试**

```python
import json
from make_gen_jsonl import bucket_for, stable_seed


def test_bucket_portrait_priority():
    assert bucket_for("vertical movie poster for a film") == (1664, 2496)
    assert bucket_for("wide landscape banner design") == (2496, 1664)
    assert bucket_for("a cat on mars") == (2048, 2048)


def test_seed_stable_and_range():
    a = stable_seed(511, 1, 0)
    assert a == stable_seed(511, 1, 0) and a != stable_seed(511, 1, 1)
    assert 0 <= a < 2**31 - 1
```

- [ ] **Step 2: 跑失败**
- [ ] **Step 3: 实现**

```python
#!/usr/bin/env python3
"""Build one batched JSONL per generation round (spec §5 GENERATE)."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from lib.constants import SEEDS_PER_PROMPT
from lib.ledger import append_event, latest, load_events

BUCKETS = [(("vertical", "portrait", "poster", "book cover"), (1664, 2496)),
           (("horizontal", "landscape", "widescreen", "banner"), (2496, 1664)),
           ((None,), (2048, 2048))]


def bucket_for(prompt: str):
    low = prompt.lower()
    for keys, wh in BUCKETS[:-1]:
        if any(k in low for k in keys):
            return wh
    return BUCKETS[-1][1]


def stable_seed(case_id, rnd, k) -> int:
    h = hashlib.blake2b(f"{case_id}|{rnd}|{k}".encode(), digest_size=8).digest()
    return int.from_bytes(h, "big") % (2**31 - 1)


def latest_prompt_text(case_dir: Path) -> str:
    adapteds = sorted(case_dir.glob("adapted-v*.md"))
    src = adapteds[-1] if adapteds else case_dir / "base.md"
    return src.read_text(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--ledger", default="ledger/append.jsonl")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = Path(args.out or f"runs/gen/round-{args.round}/gen.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {ev["payload"]["tag"] for ev in load_events(args.ledger)
            if ev["type"] == "generated"}
    lock = json.loads(Path("configs/pilot.lock.json").read_text())
    lines = []
    for c in lock["cases"]:
        cid = c["id"]
        text = latest_prompt_text(Path(f"cases/pilot/case-{cid}"))
        w, h = bucket_for(text)
        for k in range(SEEDS_PER_PROMPT):
            seed = stable_seed(cid, args.round, k)
            tag = f"case{cid}-r{args.round}-s{seed}"
            if tag in done:
                continue
            lines.append(json.dumps({"prompt": text, "width": w, "height": h,
                                     "seed": seed, "type": tag}, ensure_ascii=False))
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"[gen-jsonl] round={args.round} pending={len(lines)} -> {out}")


if __name__ == "__main__":
    main()
```

（测试文件顶部同样 `from pathlib import Path` 不需要；conftest 已供 sys.path。）

- [ ] **Step 4: 跑通过**
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat: deterministic batched jsonl builder with resume semantics"`

---

### Task 8: GPU 包装 scripts/generate.sh 与对账 scripts/reconcile_generation.py

**Files:** Create: `scripts/generate.sh`, `scripts/reconcile_generation.py`; Test: `tests/test_reconcile.py`

**Interfaces:** Consumes: 基础仓库 `run-task.sh t2i --jsonl X --output_dir Y --cfg_scale 4.0 --cfg_norm none --timestep_shift 3.0 --num_steps 50`（海报 receipt 验证过的参数组合）；批量命名规律 `{i+1:04d}_{type}_{w}x{h}.png`（`type` 即我们的 tag）。Produces: 台账 `generated`（payload: tag/output_file/sha256，idem=tag）、`gen_failed`（idem=`tag#attempt{n}`）。

- [ ] **Step 1: generate.sh**

```bash
#!/usr/bin/env bash
# The single GPU touchpoint. Retries the whole pending batch up to 2 times;
# make-gen-jsonl already skips completed tags, so retries converge naturally.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
ROUND="${1:?usage: generate.sh ROUND}"
bash scripts/env-check.sh
mkdir -p "runs/genimages/round-$ROUND" "runs/genlogs"
PY=/workspace/venv-torch212/bin/python
for attempt in 1 2 3; do
    $PY scripts/make-gen-jsonl.py --round "$ROUND"
    if [ ! -s "runs/gen/round-$ROUND/gen.jsonl" ]; then
        echo "[generate] nothing pending"; break
    fi
    LOG="runs/genlogs/round-$ROUND.attempt$attempt.log"
    echo "[generate] attempt=$attempt log=$LOG"
    (cd /workspace/SenseNova-U1.5-ROCm && VRAM_MODE=balanced bash scripts/run-task.sh t2i \
        --jsonl "$ROOT/runs/gen/round-$ROUND/gen.jsonl" \
        --output_dir "$ROOT/runs/genimages/round-$ROUND" \
        --cfg_scale 4.0 --cfg_norm none --timestep_shift 3.0 --num_steps 50) 2>&1 | tee "$LOG"
    $PY scripts/reconcile_generation.py --round "$ROUND" --attempt "$attempt"
    LEFT=$(( $(wc -l < "runs/gen/round-$ROUND/gen.jsonl") ))
    if [ "$LEFT" -le 0 ]; then break; fi
done
echo "[generate] round=$ROUND finished"
```

- [ ] **Step 2: reconcile 失败测试**

```python
import json
from reconcile_generation import parse_tags


def test_parse_tags_maps_files(tmp_path):
    (tmp_path / "0001_case511-r1-s111_1664x2496.png").write_bytes(b"x")
    m = parse_tags(tmp_path)
    assert m == {"case511-r1-s111": "0001_case511-r1-s111_1664x2496.png"}
```

- [ ] **Step 3: reconcile 实现**

```python
#!/usr/bin/env python3
"""Map produced images back to tags and record generated/gen_failed events."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from lib.ledger import append_event, load_events

NAME_RE = re.compile(r"^(\d{4})_(.+)-r(\d+)-s(\d+)_(\d+)x(\d+)\.png$")
# NOTE: the `type` field we emit is `case{id}-r{n}-s{seed}`, so group(2) here is
# `case{id}` and groups 3/4 carry round/seed again. The full tag is group(2)+suffix.


def parse_tags(img_dir: Path) -> dict:
    out = {}
    for f in sorted(Path(img_dir).iterdir()):
        m = NAME_RE.match(f.name)
        if not m:
            continue
        tag = f"{m.group(2)}-r{m.group(3)}-s{m.group(4)}"
        out[tag] = f.name
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--ledger", default="ledger/append.jsonl")
    args = ap.parse_args()
    img_dir = Path(f"runs/genimages/round-{args.round}")
    want = {}
    for line in Path(f"runs/gen/round-{args.round}/gen.jsonl").read_text().splitlines():
        if line.strip():
            s = json.loads(line)
            want[s["type"]] = s
    have = parse_tags(img_dir)
    have_all = {ev["payload"]["tag"] for ev in load_events(args.ledger) if ev["type"] == "generated"}
    for tag in sorted(want):
        if tag in have_all:
            continue
        fn = have.get(tag)
        if not fn:
            append_event(args.ledger, "gen_failed",
                         {"tag": tag, "attempt": args.attempt}, idem=f"{tag}#{args.attempt}")
            continue
        p = img_dir / fn
        append_event(args.ledger, "generated",
                     {"tag": tag, "file": str(p),
                      "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}, idem=tag)
    print(f"[reconcile] want={len(want)} new_done={sum(1 for t in want if t in have and t not in have_all)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试通过**（regex 正确吞掉 `-r1-s111` 尾段是本任务的关键断言点，若匹配失败优先修 NAME_RE/tag 拼接的一致性）
- [ ] **Step 5: Checkpoint（首次真机出图，约 5–20 分钟）**

```bash
bash scripts/generate.sh 1 && ls runs/genimages/round-1 | wc -l && grep -c '"generated"' ledger/append.jsonl
```
Expected: 图片数与 generated 事件数一致（首轮因只有单 case 场景不同而不同——建议先 `echo '{"id":<某个已选 case>}'` 手工临时缩小 lock 副本作冒烟，或直接接受全量首轮长耗时）。备注写入 PR 描述。中途 OOM 时调低 `%` 不设——按基础仓库 VRAM_MODE 文档改用 `VRAM_MODE=low` 重试并在 CHANGELOG 记录。

- [ ] **Step 6: Commit** `git add -A && git commit -m "feat: gpu wrapper with batch retry and tag reconciliation"`

---

### Task 9: 双盲队列组装 scripts/build-judge-tasks.py

**Files:** Create: `scripts/build_judge_tasks.py`（模块名下划线，方便测试）; Test: `tests/test_build_judge_tasks.py`

**Interfaces:** Consumes: 台账 `generated`、`cases/pilot/*/provenance.json`（内含 upstream_image）、`third_party/ref/data/images/`。Produces 目录 `runs/judge-queue/round-{R}/`：
- `entries/entry-{sha8}.{png|jpg}`——中性副本（sha8=image bytes 前 8 位 hex；碰撞直接报错，概率可忽略）
- `prompts/{entry_id}.txt`——该图自己的生成提示词（我们的是实际执行的 adapted/base 文本；参考图的是上游原 prompt）
- `manifest.json`——`[{entry_id, source: "sensenova"|"reference", case_id, round, seed|null, orig_image, prompt_text_sha}]`（乱序存放；映射仅供 collect 使用）
- `tasks.jsonl`——按乱序排列的派发单 `{entry_id, image_path, prompt_path, verdict_path}`；对已存在 verdict 的 entry 跳过（重派安全）
- 参考基线缓存：`results/judge/_baseline/{case_id}.json` 已存在则不再入队（一张参考图整项目只评一次）

乱序算法：`random.Random(int(sha256(f"queue-{R}").hexdigest()[:16], 16)).shuffle(rows)`——同轮重建同一顺序（确定性），判官不可见 salt 之外的信息本身不保证对抗盲，工程盲性以"文件名中性+判官规程禁止查看 manifest"为准（已在 judge 规程写明）。

- [ ] **Step 1: 失败测试**

```python
import json
from build_judge_tasks import neutral_entry_id, plan_rows


def test_neutral_entry_id_stable_short():
    a = neutral_entry_id(b"hello world")
    assert a.startswith("entry-") and len(a) == len("entry-") + 8
    assert a == neutral_entry_id(b"hello world")


def test_plan_rows_includes_reference_once(tmp_path):
    made = plan_rows(gen_events=[{"payload": {"tag": "case511-r1-s1", "file": "a.png"}}],
                     case_dirs={511: {"prompt_text": "p", "upstream_image": "ref.jpg"}},
                     baseline_existing=set(), queue_dir=tmp_path, rnd=1, copies=True)
    srcs = sorted(r["source"] for r in made)
    assert srcs == ["reference", "sensenova"]
```

- [ ] **Step 2: 跑失败**
- [ ] **Step 3: 实现（完整逻辑含文件复制、manifest/tasks 写盘、跳过已 verdict）**

```python
#!/usr/bin/env python3
"""Assemble a blinded judging queue for one round (spec §6.2, §6.4)."""
import argparse
import hashlib
import json
import random
import re
import shutil
from pathlib import Path

from lib.ledger import load_events

TAG_RE = re.compile(r"^case(\d+)-r(\d+)-s(\d+)$")


def neutral_entry_id(image_bytes: bytes) -> str:
    return "entry-" + hashlib.sha256(image_bytes).hexdigest()[:8]


def _prompt_of(case_dir: Path) -> str:
    ad = sorted(case_dir.glob("adapted-v*.md"))
    src = ad[-1] if ad else case_dir / "base.md"
    return src.read_text(encoding="utf-8")


def plan_rows(gen_events, case_dirs, baseline_existing, queue_dir: Path, rnd: int, copies=False):
    """Return shuffled row dicts; with copies=True also materialize the queue dir."""
    q = Path(queue_dir)
    rows = []
    for ev in gen_events:
        pay = ev["payload"]
        m = TAG_RE.match(pay["tag"])
        case_id = int(m.group(1))
        cd = Path(f"cases/pilot/case-{case_id}")
        info = {"source": "sensenova", "case_id": case_id, "round": rnd,
                "seed": pay["tag"].rsplit("-s", 1)[-1],
                "orig_image": pay["file"],
                "prompt_text": _prompt_of(cd)}
        rows.append(info)
    for case_id, meta in sorted(case_dirs.items()):
        if case_id in baseline_existing:
            continue
        rows.append({"source": "reference", "case_id": case_id, "round": None,
                     "seed": None, "orig_image": str(meta["upstream_image"]),
                     "prompt_text": meta["prompt_text"]})
    rng = random.Random(int(hashlib.sha256(f"queue-{rnd}".encode()).hexdigest()[:16], 16))
    rng.shuffle(rows)
    made = []
    (q / "entries").mkdir(parents=True, exist_ok=True)
    (q / "prompts").mkdir(parents=True, exist_ok=True)
    for row in rows:
        raw = Path(row["orig_image"]).read_bytes()
        eid = neutral_entry_id(raw)
        ipath = q / "entries" / f"{eid}{Path(row['orig_image']).suffix.lower()}"
        ppath = q / "prompts" / f"{eid}.txt"
        vpath = q / "verdicts" / f"{eid}.json"
        if vpath.exists():
            continue
        if copies:
            if not ipath.exists():
                shutil.copyfile(row["orig_image"], ipath)
            ppath.write_text(row["prompt_text"], encoding="utf-8")
        made.append({"entry_id": eid, "source": row["source"], "case_id": row["case_id"],
                     "round": row["round"], "seed": row["seed"],
                     "image_path": str(ipath), "prompt_path": str(ppath),
                     "verdict_path": str(vpath)})
    if copies:
        def pub(r):
            return {k: r[k] for k in ("entry_id", "source", "case_id", "round", "seed")}
        manifest = [{"entry_id": r["entry_id"], "source": r["source"], "case_id": r["case_id"],
                     "round": r["round"], "seed": r["seed"],
                     "orig_image": r["image_path"],
                     "prompt_text_sha": hashlib.sha256(r["prompt_text"].encode()).hexdigest()}
                    for r in made]
        (q / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        with (q / "tasks.jsonl").open("w", encoding="utf-8") as f:
            for r in made:
                f.write(json.dumps({k: r[k] for k in ("entry_id", "image_path", "prompt_path", "verdict_path")}) + "\n")
    return made


def main():
    import re as _re
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    args = ap.parse_args()
    gens = [e for e in load_events("ledger/append.jsonl") if e["type"] == "generated"]
    gens_r = [e for e in gens if f"-r{args.round}-" in e["payload"]["tag"]]
    lock = json.loads(Path("configs/pilot.lock.json").read_text())
    refs_root = Path("third_party/ref/data/images")
    case_dirs = {}
    for c in lock["cases"]:
        cd = Path(f"cases/pilot/case-{c['id']}")
        prov = json.loads((cd / "provenance.json").read_text())
        imgs = list(refs_root.glob(f"case{c['id']}.*"))
        if not imgs:
            raise SystemExit(f"[FATAL] upstream image missing for case {c['id']}")
        case_dirs[c["id"]] = {"prompt_text": (cd / "base.md").read_text(),
                              "upstream_image": imgs[0], "prov": prov}
    baseline = {json.loads(p.read_text())["case_id"]
                for p in Path("results/judge/_baseline").glob("*.json")}
    rows = plan_rows(gens_r, case_dirs, baseline,
                     Path(f"runs/judge-queue/round-{args.round}"), args.round, copies=True)
    print(f"[judge-queue] round={args.round} entries={len(rows)}")


if __name__ == "__main__":
    main()
```

（注：TAG_RE 不匹配的 generated 事件直接抛错停下而不是静默跳过——台账与批单格式强耦合，宁断勿错。main() 里 `import re as _re` 的过渡写法删除。金标准回归通过后若判官理由深度不足，可从 `/workspace/Qwen-Image-Bench/checklists.py` 五维清单扩充 judge-prompt.md 各维子弹项；任何扩充后必须复跑 Task 10 回归夹具。）

- [ ] **Step 4: 跑通过**
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat: blinded judging queue assembly with baseline caching"`

---

### Task 10: 判官提示词模板 judge-prompt.md 与金标准凭据

**Files:** Create: `scripts/judge-prompt.md`, `docs/receipts/golden-judge-probe.md`; Test: `tests/test_judge_prompt.py`

**Interfaces:** Produces: 后端无关的判官任务书全文；`golden-judge-probe.md` 定义回归夹具的预期分数区间（Task 12 的评审回归用它验收）。

- [ ] **Step 1: 写 judge-prompt.md 全文如下（逐字使用）**

````markdown
你是一名专业的文生图（T2I）质量评审员。这是一次匿名评测：候选者身份保密。你不允许猜测或推断任何图像由哪个模型或产品生成；评分与理由中出现此类判断即为无效输出。

任务：对下面列出的每一个 entry 独立完成评审。各 entry 之间互不影响，不要互相比较。

对每个 entry：
1. 用 Read 工具读取其提示词文件与图像文件（必须真实读图）。
2. 文字转写核查：把图中出现的所有可辨认文字逐条转写出来；凡是看起来像文字但实为乱码/伪字符的区块，明确标注 GARBLED 并估算乱码字符数量；将提示词中要求的每一句具体文案与图中对应文字逐一比对拼写。
3. 按下方量规对五个维度各打一个 0–10 整数分（10=卓越）：
   - quality 质量：物理逻辑（光影/重力/反射）、材质纹理、边缘清晰度、细节丰富度、AI 塑料感、分辨率伪影
   - aesthetics 美学：构图、色彩和谐、光影氛围、人物解剖学正确性、情绪表达、风格还原度
   - alignment 提示词遵循度：数量/颜色/形状/材质匹配、动作姿态、2D/3D 布局、场景类型；未遵循项逐条列进 unfulfilled_requirements
   - real_world_fidelity 写实与文化忠实度：真实地标/物品/文化元素是否经得起现实核对、公平性与合规
   - creative_generation 创意与设计执行：想象力、多元素融合无缝度、信息层级、镜头语言
4. 填写 hard_flags：display_text_correct（大号标题级文字是否逐字正确）、small_text_quality（correct|mildly_deformed|garbled 三档）、text_miss_count（要求文案中错误/缺失条数）、visual_defects（画面级硬伤如肢体崩坏、结构性畸变，true/false）。
5. 每个 entry 在你的最终回复里输出一段 JSON（也单独写成 verdict 文件到指定的 verdict_path），结构严格为：

{"scores":{"quality":0,"aesthetics":0,"alignment":0,"real_world_fidelity":0,"creative_generation":0},
 "score_reasons":{"quality":"","aesthetics":"","alignment":"","real_world_fidelity":"","creative_generation":""},
 "unfulfilled_requirements":[],"transcribed_text":[],
 "hard_flags":{"display_text_correct":true,"small_text_quality":"correct","text_miss_count":0,"visual_defects":false}}

规则：只依据图中可见证据；不确定时降分并在理由中说明不确定性；verdict 文件里只写这一个 JSON 对象，无多余文本；文件路径必须与本任务书给出的完全一致（历史上出现过任务书编号与文件名不一致的情况，一律以任务书写明的路径为准，不得自行排序猜测）。
````

- [ ] **Step 2: 金标准凭据 golden-judge-probe.md**

```markdown
# 判官金标准回归夹具

用途：每当 `scripts/judge-prompt.md`、schemas.py 评分逻辑或判官后端发生变更后，手工重跑一次双评审并以区间校验。

固定输入（两份都来自本机现存文件）：
- A 案：提示词=基础仓库 examples/posters-2026-08.jsonl 中含 KUNG FU 的行；图像=基础仓库 docs/results/gallery/posters/kungfu-girls.webp
- B 案：提示词=上游 data/cases.json 中 id=511 的 prompt；图像=third_party/ref/data/images/case511.jpg

流程：将 A/B 以中性编号交给判官（按 Task 12 操作手册派发一个子代理），收集两份 verdict。

验收区间（来自 2026-08-27 探针实测，verdict 凭据在本仓库 docs/receipts/judge-probe-verdict.json）：
- 五维均分：A ∈ [6.5, 8.5]，B ∈ [8.5, 10]
- A 的 hard_flags.small_text_quality 必须为 garbled
- B 的 hard_flags.display_text_correct 必须为 true 且 transcribed_text 包含坐标串 33.9249° S, 18.4241° E

区间外即判定回归失败：先查判官输出是否违规（身份推断/schema 缺陷），再查量规改动是否引入偏差；两者都不是则升级为议题讨论。
```

- [ ] **Step 3: 轻量守护测试**

```python
def test_judge_prompt_contains_schema_keys_and_ban():
    t = (Path(__file__).resolve().parents[1] / "scripts" / "judge-prompt.md").read_text(encoding="utf-8")
    for key in ("real_world_fidelity", "text_miss_count", "不允许猜测或推断", "GARBLED"):
        assert key in t
```

- [ ] **Step 4: 跑通 + Commit** `git add -A && git commit -m "feat: judge prompt template and golden probe regression fixture"`

---

### Task 11: 判定采集 scripts/collect_verdicts.py

**Files:** Create: `scripts/collect_verdicts.py`; Test: `tests/test_collect.py`

**Interfaces:** Consumes: `runs/judge-queue/round-{R}/{manifest.json,tasks.jsonl,verdicts/*.json}`、schemas 库。Produces:
- `results/judge/{entry_id}.json`——信封：`{"schema_version":"1.0","entry_id","backend":"agent","judged_at","source","case_id","round","seed","verdict"}`
- 参考图条目另写 `results/judge/_baseline/{case_id}.json`（同信封）
- 非法判定移入 `verdicts-invalid/` 并记台账 `judge_failed`（idem=entry_id）；模型身份泄露同样判废
- 台账 `judged`（idem=entry_id，payload 含 entry/source/case/results_path）

- [ ] **Step 1: 失败测试（端到端 tmp 结构）**

```python
import json
from pathlib import Path
from fixtures import GOOD_VERDICT
import collect_verdicts as collect


def test_collect_happy_and_invalid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for d in ["ledger", "runs/judge-queue/round-1/verdicts", "results/judge/_baseline", "results/judge"]:
        Path(d).mkdir(parents=True)
    Path("ledger/append.jsonl").write_text("")
    man = [{"entry_id": "entry-aaaaaaaa", "source": "sensenova", "case_id": 511,
            "round": 1, "seed": "111", "orig_image": "x.png"},
           {"entry_id": "entry-bbbbbbbb", "source": "reference", "case_id": 511,
            "round": None, "seed": None, "orig_image": "y.png"}]
    Path("runs/judge-queue/round-1/manifest.json").write_text(json.dumps(man))
    Path("runs/judge-queue/round-1/verdicts/entry-aaaaaaaa.json").write_text(json.dumps(GOOD_VERDICT))
    Path("runs/judge-queue/round-1/verdicts/entry-bbbbbbbb.json").write_text(json.dumps({"scores": {}}))
    rc = collect.main(["--round", "1"])
    assert rc == 0
    out = json.loads(Path("results/judge/entry-aaaaaaaa.json").read_text())
    assert out["source"] == "sensenova" and out["verdict"]["scores"]["quality"] == 8
    base = json.loads(Path("results/judge/_baseline/511.json").read_text())
    assert base["source"] == "reference"
    assert not Path("results/judge/entry-bbbbbbbb.json").exists()
    evs = Path("ledger/append.jsonl").read_text().splitlines()
    assert any('"judge_failed"' in e for e in evs)
```

（GOOD_VERDICT 一律从 `tests/fixtures.py` 导入——T3 已建；模块名与脚本文件名一致：脚本是 `collect_verdicts.py`。）

- [ ] **Step 2: 实现**

```python
#!/usr/bin/env python3
"""Validate judge outputs, enrich envelopes, persist receipts (spec §6.4)."""
import argparse
import json
import shutil
import time
from pathlib import Path

from lib.ledger import append_event
from lib.schemas import model_identity_leak, validate_verdict


def _collect_round(rnd: int, ledger: str, root: Path = Path(".")) -> int:
    q = root / f"runs/judge-queue/round-{rnd}"
    man = {m["entry_id"]: m for m in json.loads((q / "manifest.json").read_text())}
    inv = q / "verdicts-invalid"
    n_bad = 0
    for eid, m in man.items():
        vp = q / "verdicts" / f"{eid}.json"
        outp = root / "results/judge" / f"{eid}.json"
        if not vp.exists() or outp.exists():
            continue
        try:
            verdict = json.loads(vp.read_text())
        except json.JSONDecodeError:
            verdict = None
        errs = validate_verdict(verdict) if isinstance(verdict, dict) else ["not a json object"]
        leaks = model_identity_leak(verdict) if isinstance(verdict, dict) else ["n/a"]
        if errs or leaks:
            inv.mkdir(parents=True, exist_ok=True)
            shutil.move(str(vp), str(inv / f"{eid}.json"))
            append_event(root / ledger, "judge_failed",
                         {"entry_id": eid, "errors": errs[:3], "leaks": leaks[:1]}, idem=eid)
            n_bad += 1
            continue
        env = {"schema_version": "1.0", "entry_id": eid, "backend": "agent",
               "judged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "source": m["source"], "case_id": m["case_id"],
               "round": m["round"], "seed": m["seed"], "verdict": verdict}
        outp.write_text(json.dumps(env, ensure_ascii=False, indent=1), encoding="utf-8")
        if m["source"] == "reference":
            bp = root / f"results/judge/_baseline/{m['case_id']}.json"
            bp.write_text(json.dumps(env, ensure_ascii=False, indent=1), encoding="utf-8")
        append_event(root / ledger, "judged",
                     {"entry_id": eid, "source": m["source"], "case_id": m["case_id"],
                      "results_path": str(outp)}, idem=eid)
    print(f"[collect] round={rnd} persisted={len(man) - n_bad} invalid={n_bad}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--ledger", default="ledger/append.jsonl")
    a = ap.parse_args(argv)
    return _collect_round(a.round, a.ledger)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: 跑通过**
- [ ] **Step 4: Commit** `git add -A && git commit -m "feat: verdict collection with schema gate and baseline split"`

---

### Task 12: 评审操作手册 docs/operator-loop.md（自动化运行协议）

**Files:** Create: `docs/operator-loop.md`

**Interfaces:** Consumes: Tasks 7–11 的命令面。Produces: 任何无人值守会话（本机的 ZCode 定时会话/未来 cron 化的判官代理）都能照做的一页式协议；其中含派发子代理判官的完整提示词模板（变量仅 entry 批次路径）、一致性抽检规则、轮次推进决策树。

- [ ] **Step 1: 写文档，核心内容如下（完整成文由 executor 按此提纲展开为自然换行的 md）**

手册章节与要点（不得省略任何一条）：

1. **一轮的定义**：generate → build-judge-tasks → 判官批阅 → collect → compare → （有 fail 且轮次<3）rewrite-prompts → 回到 generate（仅失败的 case 会出现在新批单里）。给出每一步的精确命令行（Task 7/8/9/11/13/14 的 invocation 原文）。
2. **判官派发模板**：主代理（或定时会话里的代理）读取 `tasks.jsonl`，每批 ≤6 个 entry，构造消息＝Task 10 的 judge-prompt.md 全文 + 本批清单（逐条列出 image_path / prompt_path / verdict_path 三个绝对路径），经子代理工具发出；子代理回复后核对 verdict_path 文件均已落盘，缺失者重派一次。
3. **一致性抽检**：每轮结束前随机抽取 ceil(entries×0.1) 个已判 entry 重新走一遍第 2 步（新 verdict 写 verdicts-resample/），比较两次五维均差；任一差值 > ARBITER_MEAN_DIFF(2.0) 即追加第三次仲裁评审，三个结果逐维取中位数写回正式 verdict（脚本外人工/代理步骤，过程记入台账 judge_failed 注释事件）。
4. **非法输出协议**：collect 报 invalid 后，读取 invalid 文件定位问题；属可修复格式（markdown fence、尾随逗号）由评审代理修正重交一次，二次仍失败则将该 entry 标记跳过并计入报告 caveat。
5. **终止条件**：report 中无 fail 案例，或所有未达标案例已达 MAX_REWRITE_ROUNDS=3 轮上限。达标 → 进入 PUBLISH（Task 16）；未达 → 如实在 README 结论表标注 gap。
6. **成本护栏**：单轮判官 token 消耗预算 ≈ entries×40k；连续两轮超出预算 50% 以上时暂停并核对批阅是否有重复派发。
7. **金标准回归**指针：链接 `docs/receipts/golden-judge-probe.md`，量规/模板变更后必跑。

- [ ] **Step 2: 自检**：文档中出现的每条命令逐一复制执行 `--help` 或 `bash -n` 等价物确证可运行（比如 `python3 scripts/make_gen_jsonl.py --help` 应正常退出）。
- [ ] **Step 3: Commit** `git add -A && git commit -m "docs: unattended judging/operator loop protocol"`

---

### Task 13: 打平判定 scripts/compare_parity.py

**Files:** Create: `scripts/compare_parity.py`; Test: `tests/test_compare.py`

**Interfaces:** Consumes: `results/judge/` 信封、`results/judge/_baseline/`、`configs/pilot.lock.json`、台账。Produces: `runs/comparisons/round-{R}/report.json`、台账 `compared`（idem=`cmp-{R}-{case}`）与冻结类事件 `status_parity` / `status_capped`（idem 同上）；控制台汇总表；milestone 字段 `{"parity_ratio": float, "target": 24, "total": 30, "overall_gap": float}`。

best-of-N：同 case 同轮的多枚种子 entry 各算五维均分，取最高者为该 case 本轮代表；五条判定（spec §8 a–e）依次评估：(a) 代表均分 ≥ 基线均分 − 0.5；(b) display_text_correct；(c) small_text_quality ≠ garbled（除非该 case 当前生效版本 provenance 标记 `small_text_exempt=true`——rewrite 任务 S1 策略写入）；(d) text_miss_count==0；(e) visual_defects=false。全过 → parity；代表分比基线还高 0 分以上且其余硬项全过 → 附带标注 win；否则 fail。

- [ ] **Step 1: 失败测试（四个边界用例一次写全）**

```python
import json
from pathlib import Path
from fixtures import GOOD_VERDICT
from schemas import SCORE_KEYS
import compare_parity as cp

S = lambda q: {k: q for k in SCORE_KEYS}


def _env(entry, src, case, rnd, q, flags):
    v = json.loads(json.dumps(GOOD_VERDICT))
    v["scores"] = S(q)
    return {"schema_version": "1.0", "entry_id": entry, "backend": "agent", "judged_at": "t",
            "source": src, "case_id": case, "round": rnd, "seed": "1", "verdict": v}


def _layout(tmp_path, baseline_env, cand_env):
    (tmp_path / "results/judge/_baseline").mkdir(parents=True)
    (tmp_path / "results/judge").mkdir(parents=True, exist_ok=True)
    b = tmp_path / f"results/judge/_baseline/{cand_env['case_id']}.json"
    b.write_text(json.dumps(baseline_env))
    c = tmp_path / f"results/judge/{cand_env['entry_id']}.json"
    c.write_text(json.dumps(cand_env))
    (tmp_path / "runs/comparisons").mkdir(parents=True, exist_ok=True)
    return cand_env


def test_gap_exactly_at_allowance_passes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    e = _layout(tmp_path, _env("e0", "reference", 511, None, 8, GOOD_VERDICT["hard_flags"]),
                _env("e1", "sensenova", 511, 1, 8 - abs(cp.GAP_ALLOW), GOOD_VERDICT["hard_flags"]))
    row = cp.decide(e, _env("e0", "reference", 511, None, 8, GOOD_VERDICT["hard_flags"]), False)
    assert row["status"] == "parity"


def test_garbled_small_text_fails_without_exempt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bad = json.loads(json.dumps(GOOD_VERDICT["hard_flags"])) | {"small_text_quality": "garbled"}
    e = _env("e1", "sensenova", 511, 1, 10, bad)
    row = cp.decide(e, _env("e0", "reference", 511, None, 0, GOOD_VERDICT["hard_flags"]), False)
    assert row["status"] == "fail" and not row["checks"]["c_small_text"]


def test_visual_defect_fails_even_with_high_score(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bad = json.loads(json.dumps(GOOD_VERDICT["hard_flags"])) | {"visual_defects": True}
    e = _env("e1", "sensenova", 511, 1, 10, bad)
    row = cp.decide(e, _env("e0", "reference", 511, None, 0, GOOD_VERDICT["hard_flags"]), False)
    assert row["status"] == "fail" and not row["checks"]["e_no_visual_defects"]


def test_exempt_rescues_garbled_case(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bad = json.loads(json.dumps(GOOD_VERDICT["hard_flags"])) | {"small_text_quality": "garbled"}
    e = _env("e1", "sensenova", 511, 2, 9, bad)
    row = cp.decide(e, _env("e0", "reference", 511, None, 8, GOOD_VERDICT["hard_flags"]), True)
    assert row["status"] == "parity" and row["checks"]["c_small_text"]
```

（阈值一律 `from lib.constants import GAP_ALLOW` 引用，测试与实现共用； exemption 第三参即 `compare_parity.exempt()` 的返回值，main() 按 case 求值传入。）

- [ ] **Step 2: 实现（要点）**

```python
#!/usr/bin/env python3
"""Formal parity decision (spec §8)."""
import argparse
import json
from pathlib import Path

from lib.constants import GAP_ALLOW
from lib.ledger import append_event

SCORE_KEYS = ["quality", "aesthetics", "alignment", "real_world_fidelity", "creative_generation"]


def mean(v):
    return sum(v["verdict"]["scores"][k] for k in SCORE_KEYS) / len(SCORE_KEYS)


def exempt(case_id, root=Path(".")):
    p = root / f"cases/pilot/case-{case_id}/provenance.json"
    if not p.exists():
        return False
    hist = json.loads(p.read_text()).get("history", [])
    return bool(hist and hist[-1].get("small_text_exempt"))


def decide(env_cand, env_ref, is_exempt):
    mcand, mref = mean(env_cand), mean(env_ref)
    hf = env_cand["verdict"]["hard_flags"]
    checks = {
        "a_score_gap": (mcand - mref) >= GAP_ALLOW,
        "b_display_text": hf["display_text_correct"],
        "c_small_text": (hf["small_text_quality"] != "garbled") or is_exempt,
        "d_miss_zero": hf["text_miss_count"] == 0,
        "e_no_visual_defects": not hf["visual_defects"],
    }
    status = "parity" if all(checks.values()) else "fail"
    if status == "parity" and mcand > mref:
        status = "win"          # informational bonus label
    return {"candidate_mean": mcand, "reference_mean": mref, "checks": checks, "status": status}
```

main() 负责：读 results/judge 中 round=R 且 source==sensenova 的最新信封按 case 聚合 best-of-N → 对照 baseline → 写 report/台账；report 里附 `per_case[].failed_checks` 文案化列表（喂给 rewrite）。win 事件仍写 compared；只有 parity/win 冻结。

- [ ] **Step 3: 四个边界用例全绿**
- [ ] **Step 4: Checkpoint（真实数据首跑，在完成一轮真实判官之后）**

```bash
.venv-test/bin/python scripts/compare_parity.py --round 1 && cat runs/comparisons/round-1/report.json | head -30
```
Expected: 30 条 per_case 记录 + milestone 字段

- [ ] **Step 5: Commit** `git add -A && git commit -m "feat: formal parity decision engine per spec section 8"`

---

### Task 14: 提示词改写 scripts/rewrite_prompts.py

**Files:** Create: `scripts/rewrite_prompts.py`; Test: `tests/test_rewrite.py`

**Interfaces:** Consumes: report.json 的 per_case（字段 case_id/status/failed_checks，来自 Task 13）、cases/pilot 源文件。Produces: `adapted-v{n+1}.md`、provenance.json 追加 `history[]`（原句摘要/策略/触发原因/版本号/`small_text_exempt` 标志）、台账 `rewritten`（idem=`rw-{case}-{ver}`）；轮次达 MAX_REWRITE_ROUNDS 的 case 打 `capped` 标志并在台账记 `status_capped`。策略施加统一收敛在纯函数 `apply_strategy(text: str, strategy_id: str) -> str` 里，未来接入 LLM 改写只需替换该函数的实现而不动管线。

策略选择顺序与内容（常量字典，全部为实际拼接用的英文指令块）：

```python
STRATEGIES = {
    "S1_drop_microtext": {
        "trigger": "small_text_quality == garbled",
        "directive": ("Typography constraint: do NOT render a credits block, billing block "
                      "or any micro-print paragraph. Limit all typography to the main title "
                      "and, if specified, the subtitle and a short date/release line only."),
        "sets_small_text_exempt": True,
    },
    "S2_simplify_display_text": {
        "trigger": "display_text_correct == false or text_miss_count > 0",
        "directive": ("Typography constraint: render ONLY the required title strings; use short "
                      "letterforms, high contrast between text and background, and avoid any "
                      "decorative distortion of glyphs. Spell each word exactly as given."),
        "sets_small_text_exempt": False,
    },
    "S3_explicit_constraints": {
        "trigger": "unfulfilled mentions count/layout/position words",
        "directive": ("Composition constraints: follow the quantities below literally and place "
                      "objects as stated; prefer explicit enumeration over prose description."),
        "sets_small_text_exempt": False,
    },
    "S4_style_anchor": {
        "trigger": "default when others absent (style/aesthetic shortfall)",
        "directive": ("Style anchoring: identify the medium (flat vector poster / photographic "
                      "print / ink painting), name the palette explicitly, and reference the era "
                      "and genre in the first sentence of the prompt."),
        "sets_small_text_exempt": False,
    },
    "S5_avoid_anatomy": {
        "trigger": "visual_defects == true or unfulfilled mentions hands/face/limbs",
        "directive": ("Subject rendering constraints: favor medium or wide shots; keep hands "
                      "either naturally occupied or out of frame; avoid close-ups of faces with "
                      "complex expressions."),
        "sets_small_text_exempt": False,
    },
}
KEYWORD_RULES = [("count|quantity|number of", "S3_explicit_constraints"),
                 ("hand|finger|limb|face|anatom", "S5_avoid_anatomy"),
                 ("color|layout|position|background", "S3_explicit_constraints")]
```

分类函数 `pick_strategy(case_report_row)`：hard_flags.garbled → S1；display_text 错或 miss>0 → S2；否则按 unfulfilled 文本正则查 KEYWORD_RULES 命中序首个；visual_defects → S5 优先于 S3/S4；无命中 → S4。一次只应用一个策略（避免叠加漂移，首轮失败后的区分度更好分析）。

- [ ] **Step 1: 失败测试**

```python
import json
from pathlib import Path
import rewrite_prompts as rp


def _mk_case(root, cid=511):
    d = root / f"cases/pilot/case-{cid}"
    d.mkdir(parents=True)
    (d / "base.md").write_text("A vertical poster with a credits block at bottom.\n")
    (d / "provenance.json").write_text(json.dumps(
        {"case_id": cid, "history": []}))
    return d


def test_pick_strategy_priority():
    row_g = {"hard_flags": {"small_text_quality": "garbled", "display_text_correct": True}}
    assert rp.pick_strategy(row_g) == "S1_drop_microtext"
    row_d = {"hard_flags": {"small_text_quality": "correct", "display_text_correct": False,
                            "visual_defects": False, "text_miss_count": 0}}
    assert rp.pick_strategy(row_d) == "S2_simplify_display_text"


def test_rewrite_writes_next_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _mk_case(tmp_path, 511)
    rp.rewrite_one(511, failed_checks=["c_small_text: garbled small text"])
    assert (tmp_path / "cases/pilot/case-511/adapted-v2.md").exists()
    new_text = (tmp_path / "cases/pilot/case-511/adapted-v2.md").read_text()
    assert "do NOT render a credits block" in new_text
    hist = json.loads((tmp_path / "cases/pilot/case-511/provenance.json").read_text())["history"]
    assert hist[-1]["strategy"] == "S1_drop_microtext" and hist[-1]["small_text_exempt"] is True
```

实现要点：新版本文本 = `apply_strategy(latest_prompt_text(case_dir), s)`，其中 `apply_strategy(text, s) = text.rstrip() + "\n\n" + STRATEGIES[s]["directive"]`；pick_strategy 的入参 hard_flags 来自 report.json 中该 case 代表 entry 的 verdict。main() 遍历 report 中 status==fail 且轮次未达上限的 case，逐个 rewrite_one；达上限的记 status_capped 事件。rewritten 台账事件 payload 含 version/strategy/failed_checks；每次施加历史以 provenance.history 列表承载 `{version, strategy, failed_checks, applied_directive, small_text_exempt, ts}`。

- [ ] **Step 2: 跑通过**
- [ ] **Step 3: Commit** `git add -A && git commit -m "feat: attribution-driven prompt rewriting with strategy templates"`

---

### Task 15: glm_api 判官后端 scripts/run_judge_api.py（随仓发布件）

**Files:** Create: `scripts/run_judge_api.py`; Test: `tests/test_run_judge_api.py`

**Interfaces:** Consumes: 环境变量 `GLM_API_KEY`（必需，缺失立即退出并打印指引）、`GLM_API_BASE`（默认 `https://api.z.ai/api/paas/v4/chat/completions`）、`GLM_VLM_MODEL`（默认 `glm-4.6v`，用户可按自己可用型号覆盖）。Produces: 与 agent 后端完全一致的 verdict 文件（供 collect 直接消费）；网络/鉴权错误按要求码退出（stderr 给出三类常见原因对照）。

请求体形态（OpenAI 兼容 chat.completions，视觉走 content 多模态数组）：

```python
content = [{"type": "text", "text": user_text},
           {"type": "image_url", "image_url": {"url": f"data:image;base64,{b64}"}}]
body = {"model": MODEL, "temperature": 0,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": content}]}
req = urllib.request.Request(BASE, data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json",
                                      "Authorization": f"Bearer {KEY}"})
resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
text = resp["choices"][0]["message"]["content"]
verdict = extract_json(text)      # lib.schemas
```

SYSTEM = judge-prompt.md 全文读入；user_text = 单 entry 提示词 + 要求把 JSON 写入 stdout 的变体说明（API 后端无法写文件，由本脚本代写 verdict 文件后再走统一 collect）。

- [ ] **Step 1: 失败测试（线程内 http.server 返回固定 OpenAI 兼容响应）**

```python
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from fixtures import GOOD_VERDICT
import run_judge_api as rja


def _spawn_mock_server(auth_ok: str):
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.headers["Authorization"] == auth_ok
            body = json.dumps({"choices": [{"message": {"content":
                "```json\n" + json.dumps(GOOD_VERDICT) + "\n```"}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/api/paas/v4/chat/completions"


def test_api_backend_normalizes(monkeypatch, tmp_path):
    srv, url = _spawn_mock_server("Bearer k-123")
    monkeypatch.setenv("GLM_API_BASE", url)
    monkeypatch.setenv("GLM_API_KEY", "k-123")
    img = tmp_path / "im.png"; img.write_bytes(b"\x89PNG\r\n\x1a\nrest")
    pr = tmp_path / "p.txt"; pr.write_text("a poster")
    vp = tmp_path / "v.json"
    rc = rja.run_one({"image_path": str(img), "prompt_path": str(pr), "verdict_path": str(vp)})
    assert rc == 0 and json.loads(vp.read_text())["scores"]["quality"] == 8
    srv.shutdown()


def test_missing_key_fails_fast(monkeypatch):
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    assert rja.run_one({}) == 2
```

- [ ] **Step 2: 实现 + 缺 key 的快速失败测试**（`KeyError→exit 2, stderr 引导语`）
- [ ] **Step 3: 跑通过 + Commit** `git add -A && git commit -m "feat: optional glm_api judge backend openai-compatible"`

---

### Task 16: 画廊渲染 scripts/render_gallery.py 与发布收口

**Files:** Create: `scripts/render_gallery.py`; Modify: `README.md`（仅占位符区域）; Test: `tests/test_render.py`

**Interfaces:** Consumes: 台账 `status_parity`/`status_capped` 及 report.json、`results/judge/`、获胜原图（runs/genimages 下）。Produces: `results/gallery/case-{id}.{png|webp}`（从获胜 entry 复制）、README 三个占位符替换为双语画廊与结论表（EN/ZH 两种语序段落由本脚本同时生成）、CHANGELOG 追加发行小节；绝不触碰 push。

渲染规则：画廊行格式 `| case-id 类别 | 我方图 <img src results/gallery/... width=420/> | 上游回链 [case {id}]({sourceUrl}) |`；结论表列 = case、状态(parity/win/capped)、我方均分、参考均分、差值；ZH 区块同构中文标签。capped 案例在表中如实展示负差值。

- [ ] **Step 1: 失败测试（fixture 造 1 个 parity + 1 个 capped，断言 README 片段包含状态徽标与正确数值、包含我们仓内相对路径而非 runs/ 绝对路径）**
- [ ] **Step 2: 实现渲染 + 落盘**
- [ ] **Step 3: 全量回归** `.venv-test/bin/pytest tests/ -q` 全绿
- [ ] **Step 4: 发布前总检清单（写入 PR 描述）**

```bash
bash scripts/env-check.sh && .venv-test/bin/pytest tests/ -q && git status --short third_party runs .venv-test
```
Expected: 测试全绿且三个敏感路径均被 ignore（status 干净）

- [ ] **Step 5: Commit** `git add -A && git commit -m "feat: bilingual gallery renderer and publish finalization"`

---

### Task 17: 全链路 mock 冒烟测试（CI 可跑，零 GPU）

**Files:** Create: `tests/test_e2e_mock.py`

**Interfaces:** Consumes: Tasks 7–16 的全部纯 Python 面。Produces: 一条命令 `.venv-test/bin/pytest tests/test_e2e_mock.py -q` 即验证"批单→队列→采集→判定"四段管线在合成数据上端到端贯通；这是 spec §11 端到端冒烟要求的落点，也是未来 CI 的主入口。

- [ ] **Step 1: 写冒烟测试**

```python
"""Zero-GPU end-to-end smoke over synthetic data (spec §11)."""
import json
from pathlib import Path

from fixtures import GOOD_VERDICT


def _png(b):
    return b"\x89PNG\r\n\x1a\n" + bytes(b)


def test_pipeline_smoke(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for d in ["ledger", "configs", "cases/pilot/case-511",
              "runs/genimages/round-1", "runs/gen/round-1",
              "runs/judge-queue/round-1/verdicts",
              "results/judge/_baseline", "results/judge"]:
        Path(d).mkdir(parents=True, exist_ok=True)
    Path("ledger/append.jsonl").write_text("")
    Path("configs/pilot.lock.json").write_text(json.dumps(
        {"upstream_commit": "x", "cases_sha256": "y", "size": 1,
         "cases": [{"id": 511, "title": "t", "category": "Posters & Typography", "prompt_len": 9}]}))
    Path("cases/pilot/case-511/base.md").write_text("a vertical poster\n")
    prov = {"case_id": 511, "history": []}
    Path("cases/pilot/case-511/provenance.json").write_text(json.dumps(prov))
    img = Path("runs/genimages/round-1/0001_case511-r1-s111_2048x2048.png")
    img.write_bytes(_png([1, 2, 3]))
    from lib.ledger import append_event
    append_event("ledger/append.jsonl", "generated",
                 {"tag": "case511-r1-s111", "file": str(img), "sha256": "x"},
                 idem="case511-r1-s111")

    import build_judge_tasks as bjt
    rows = bjt.plan_rows(
        [{"payload": {"tag": "case511-r1-s111", "file": str(img)}}],
        {511: {"prompt_text": "a vertical poster\n",
               "upstream_image": str(_write_ref(tmp_path))}},
        baseline_existing=set(),
        queue_dir=Path("runs/judge-queue/round-1"), rnd=1, copies=False)
    # seed synthetic verdicts for every planned entry
    man = []
    q = Path("runs/judge-queue/round-1")
    rng_src = json.dumps([{k: r[k] for k in ("entry_id", "source", "case_id")} for r in rows])
    for r in rows:
        m = {"entry_id": r["entry_id"], "source": r["source"], "case_id": r["case_id"],
             "round": r["round"], "seed": r["seed"], "orig_image": r["image_path"]}
        man.append(m)
        vp = q / "verdicts" / f"{r['entry_id']}.json"
        flags = dict(GOOD_VERDICT["hard_flags"])
        if r["source"] == "reference":
            pass
        v = json.loads(json.dumps(GOOD_VERDICT))
        if r["source"] == "sensenova":
            v["hard_flags"] = flags | {"small_text_quality": "garbled"}   # force a fail path too
        vp.write_text(json.dumps(v))
    (q / "manifest.json").write_text(json.dumps(man))

    import collect_verdicts as collect
    assert collect.main(["--round", "1"]) == 0
    import compare_parity as cp
    assert cp.main(["--round", "1"]) == 0
    report = json.loads(Path("runs/comparisons/round-1/report.json").read_text())
    assert report["milestone"]["total"] == len(report["per_case"])
    statuses = {r["status"] for r in report["per_case"]}
    assert statuses <= {"parity", "win", "fail"}


def _write_ref(tmp_path):
    p = tmp_path / "fake-ref.jpg"
    p.write_bytes(_png([9]))
    return p
```

（`build_judge_tasks.plan_rows` 以 copies=False 跑通纯逻辑面即可覆盖"账单↔队列↔manifest"的接口缝合；真实文件复制路径由其单元测试与真机 checkpoint 另行保障。executor 若发现 plan_rows 在 copies=False 时仍尝试读图字节数据，则把 neutral_entry_id 的计算改为可选参数跳过——接口保持，行为仅影响本测试。允许的最小改动以不破坏 Task 9 测试为准。）

- [ ] **Step 2: 全量回归**

```bash
.venv-test/bin/pytest tests/ -q
```
Expected: all passed（本任务常绿后即成为 CI 主入口）

- [ ] **Step 3: Commit** `git add -A && git commit -m "test: zero-gpu e2e pipeline smoke"`

---

## 里程碑对照（spec §13 ↔ 任务）

| Milestone | 由哪些任务达成 |
|---|---|
| M0 脚手架+取数+策展 | Task 1–6 |
| M1 生成链路打通（含真机 checkpoint） | Task 7–8 |
| M2 盲评判官全 Pilot 首轮 | Task 9–13（Task 10 金标准夹具先行验证） |
| M3 改写循环至收敛 | Task 14 + operator-loop 协议驱动若干轮 |
| M4 渲染发布成品 | Task 16 + Task 17（CI 冒烟入口固化）|

## 风险与预案（执行者须知）

- 真机时长超预期：first GPU checkpoint 先用临时缩小的 lock（单 case）冒烟，再放全量过夜跑。
- 上游图片扩展名非 .jpg 统一假设：Task 9 已用 glob 兜底，遇 SVG 罕例跳过并挑备选 case。
- base repo CLI 行为与本文引用有出入时（如 run-task.sh 参数演进）：以 `/workspace/SenseNova-U1.5-ROCm/scripts/run-task.sh` 现场帮助为准并在 CHANGELOG 记录差异，不修改基础仓库。
