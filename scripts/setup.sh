#!/usr/bin/env bash
# One-command bring-up after any container rebuild (AGENTS.md persistence rules).
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/env-check.sh
bash scripts/fetch-reference.sh "$@"
mkdir -p runs/genimages runs/judge-queue results/gallery results/judge/_baseline ledger
[ -f .venv-test/bin/pytest ] || { python3 -m venv .venv-test && .venv-test/bin/pip install -q pytest; }
echo "[setup][done]"
