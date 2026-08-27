#!/usr/bin/env bash
# The single GPU touchpoint. Up to 3 attempts total: each attempt regenerates
# the pending batch from the ledger, and make_gen_jsonl skips completed tags.
# A hard run-task failure is logged, partial results are still reconciled,
# and the loop proceeds so remaining work is retried on the next attempt.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
ROUND="${1:?usage: generate.sh ROUND}"
bash scripts/env-check.sh
mkdir -p "runs/genimages/round-$ROUND" "runs/genlogs"
PY=/workspace/venv-torch212/bin/python
for attempt in 1 2 3; do
    $PY scripts/make_gen_jsonl.py --round "$ROUND"
    if [ ! -s "runs/gen/round-$ROUND/gen.jsonl" ]; then
        echo "[generate] nothing pending"; break
    fi
    LOG="runs/genlogs/round-$ROUND.attempt$attempt.log"
    echo "[generate] attempt=$attempt log=$LOG"
    if ! ( cd /workspace/SenseNova-U1.5-ROCm && VRAM_MODE="${VRAM_MODE:-balanced}" bash scripts/run-task.sh t2i \
        --jsonl "$ROOT/runs/gen/round-$ROUND/gen.jsonl" \
        --output_dir "$ROOT/runs/genimages/round-$ROUND" \
        --cfg_scale 4.0 --cfg_norm none --timestep_shift 3.0 --num_steps 50 ) 2>&1 | tee "$LOG"; then
        echo "[generate] run-task exited nonzero; reconciling partial results before retry"
    fi
    $PY scripts/reconcile_generation.py --round "$ROUND" --attempt "$attempt"
done
echo "[generate] round=$ROUND finished"
