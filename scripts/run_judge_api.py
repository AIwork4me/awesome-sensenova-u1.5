#!/usr/bin/env python3
"""Optional glm_api judge backend: OpenAI-compatible cloud vision endpoint.

The pipeline's default agent backend does NOT depend on this script; it exists
so external users / CI can run the same blinded queue through an HTTP API.
It consumes rows of runs/judge-queue/round-{N}/tasks.jsonl (keys exactly
image_path / prompt_path / verdict_path), posts one multimodal
chat.completions request per entry, extracts the JSON verdict from the reply,
validates it with lib.schemas.validate_verdict and writes the verdict file so
collect_verdicts.py can consume the round unchanged.

Environment (all read at call time):
  GLM_API_KEY     required; missing -> immediate exit code 2 with guidance.
  GLM_API_BASE    default https://api.z.ai/api/paas/v4/chat/completions
  GLM_VLM_MODEL   default glm-4.6v (override with any model your key supports)

Exit codes: 0 verdict written; 2 missing GLM_API_KEY; 3 HTTP/network failure
(stderr carries a three-class diagnosis: 401 bad key, 404 wrong base/model
path, timeout/unreachable); 4 reply unusable as a verdict (nothing written).

Usage: python scripts/run_judge_api.py --tasks runs/judge-queue/round-1/tasks.jsonl
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from lib.schemas import extract_json, validate_verdict

RC_OK = 0
RC_MISSING_KEY = 2
RC_HTTP = 3
RC_BAD_VERDICT = 4

DEFAULT_API_BASE = "https://api.z.ai/api/paas/v4/chat/completions"
DEFAULT_VLM_MODEL = "glm-4.6v"

SYSTEM = (Path(__file__).resolve().parent / "judge-prompt.md").read_text(encoding="utf-8")

# The cloud model cannot write files or use tools: this line replaces the
# prompt's verdict_path clause; this script writes the verdict file instead.
REPLY_INSTRUCTION = (
    "\n\n【API 判官附加指令】本次评审通过 API 进行：待评审图像已随本消息附上，"
    "无需调用任何工具或读取文件。你没有文件系统与工具权限，不要尝试写文件。"
    "请直接在回复中输出且只输出一个符合上文结构的 JSON 对象"
    "（从 `{` 开始到 `}` 结束，无代码块标记、无其他文字）；脚本会代你把该 "
    "JSON 写入 verdict 文件后再统一收集。"
)

_MIME_BY_SUFFIX = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                   ".png": "image/png", ".webp": "image/webp"}


def guess_mime(image_path) -> str:
    return _MIME_BY_SUFFIX.get(Path(image_path).suffix.lower(), "application/octet-stream")


def _diag_block():
    """Shared stderr reference covering the three common failure classes."""
    print("Common causes:\n"
          "  401 Unauthorized        -> GLM_API_KEY wrong/expired/not valid for this endpoint\n"
          "  404 Not Found           -> wrong GLM_API_BASE path or unsupported GLM_VLM_MODEL\n"
          "  timeout / unreachable   -> network, firewall, proxy, or wrong host/port",
          file=sys.stderr)


def run_one(entry_cfg: dict) -> int:
    """Judge a single entry via the OpenAI-compatible endpoint; see module doc."""
    key = os.environ.get("GLM_API_KEY")
    if not key:
        print("[judge-api] FATAL: GLM_API_KEY is not set.\n"
              "Get an API key (z.ai / bigmodel.cn open platform) and export it:\n"
              "  export GLM_API_KEY=<your-key>\n"
              f"Optional: export GLM_API_BASE (default {DEFAULT_API_BASE}),\n"
              f"          export GLM_VLM_MODEL (default {DEFAULT_VLM_MODEL}).",
              file=sys.stderr)
        return RC_MISSING_KEY
    base = os.environ.get("GLM_API_BASE") or DEFAULT_API_BASE
    model = os.environ.get("GLM_VLM_MODEL") or DEFAULT_VLM_MODEL
    img = Path(entry_cfg["image_path"])
    user_text = Path(entry_cfg["prompt_path"]).read_text(encoding="utf-8").rstrip() \
        + REPLY_INSTRUCTION
    b64 = base64.standard_b64encode(img.read_bytes()).decode("ascii")
    content = [{"type": "text", "text": user_text},
               {"type": "image_url", "image_url":
                {"url": f"data:{guess_mime(img)};base64,{b64}"}}]
    body = {"model": model, "temperature": 0,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": content}]}
    req = urllib.request.Request(base, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    try:
        raw = urllib.request.urlopen(req, timeout=180).read()
        resp = json.loads(raw)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read(500).decode("utf-8", "replace")
        except OSError:
            pass
        print(f"[judge-api] FATAL: HTTP {e.code} POSTing {base}\n{detail}", file=sys.stderr)
        if e.code in (401, 403):
            print(f"[judge-api] HTTP {e.code}: credential rejected -- check GLM_API_KEY.",
                  file=sys.stderr)
        elif e.code == 404:
            print(f"[judge-api] HTTP 404: endpoint or model not found -- check GLM_API_BASE "
                  f"path and GLM_VLM_MODEL={model}.", file=sys.stderr)
        else:
            print(f"[judge-api] HTTP {e.code}: server rejected the request.", file=sys.stderr)
        _diag_block()
        return RC_HTTP
    except json.JSONDecodeError as e:
        # 200 but non-JSON body (proxy/gateway HTML, truncation): upstream anomaly.
        print(f"[judge-api] FATAL: {base} returned a non-JSON body ({e}); raw head follows",
              file=sys.stderr)
        print(f"[judge-api] body head: {raw[:300]!r}", file=sys.stderr)
        _diag_block()
        return RC_HTTP
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"[judge-api] FATAL: request to {base} timed out or was unreachable: {e}",
              file=sys.stderr)
        _diag_block()
        return RC_HTTP
    try:
        text = resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print(f"[judge-api] FATAL: reply from {base} lacks choices[0].message.content; "
              f"a wrong GLM_API_BASE path or unsupported GLM_VLM_MODEL often produces "
              f"such bodies: {str(resp)[:300]}", file=sys.stderr)
        _diag_block()
        return RC_HTTP
    verdict = extract_json(text) if isinstance(text, str) else None
    if verdict is None:
        errs = ["reply contained no JSON object (expected exactly one {...} object)"]
    else:
        errs = validate_verdict(verdict)
    if errs:
        print(f"[judge-api] FATAL: model reply failed verdict validation: {errs[:3]}",
              file=sys.stderr)
        print(f"[judge-api] reply head: {str(text or '')[:300]}", file=sys.stderr)
        print(f"[judge-api] no verdict file written for {entry_cfg['verdict_path']}",
              file=sys.stderr)
        return RC_BAD_VERDICT
    Path(entry_cfg["verdict_path"]).write_text(
        json.dumps(verdict, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[judge-api] model={model} wrote {entry_cfg['verdict_path']}")
    return RC_OK


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Run a judge queue through an OpenAI-compatible GLM API endpoint.")
    ap.add_argument("--tasks", required=True,
                    help="tasks.jsonl produced by build_judge_tasks.py")
    args = ap.parse_args(argv)
    rows = [json.loads(line)
            for line in Path(args.tasks).read_text(encoding="utf-8").splitlines()
            if line.strip()]
    done = skipped = failed = 0
    last_rc = RC_OK
    for row in rows:
        if Path(row["verdict_path"]).exists():  # idempotent reruns
            skipped += 1
            continue
        rc = run_one(row)
        if rc == RC_OK:
            done += 1
        else:
            failed += 1
            last_rc = rc
            print(f"[judge-api] rc={rc} for {row['verdict_path']}", file=sys.stderr)
    print(f"[judge-api] tasks={len(rows)} done={done} skipped={skipped} failed={failed}")
    return last_rc


if __name__ == "__main__":
    raise SystemExit(main())
