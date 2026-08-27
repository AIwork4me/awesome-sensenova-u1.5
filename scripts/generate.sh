#!/usr/bin/env bash
# The single GPU touchpoint. Retries the whole pending batch up to 2 times;
# make_gen_jsonl already skips completed tags, so retries converge naturally.
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
    (cd /workspace/SenseNova-U1.5-ROCm && VRAM_MODE=balanced bash scripts/run-task.sh t2i \
        --jsonl "$ROOT/runs/gen/round-$ROUND/gen.jsonl" \
        --output_dir "$ROOT/runs/genimages/round-$ROUND" \
        --cfg_scale 4.0 --cfg_norm none --timestep_shift 3.0 --num_steps 50) 2>&1 | tee "$LOG"
    $PY scripts/reconcile_generation.py --round "$ROUND" --attempt "$attempt"
    LEFT=$(( $(wc -l < "runs/gen/round-$ROUND/gen.jsonl") ))
    if [ "$LEFT" -le 0 ]; then break; fi
done
echo "[generate] round=$ROUND finished"
