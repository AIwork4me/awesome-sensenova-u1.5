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
