#!/usr/bin/env bash
# Fetch pinned awesome-gpt-image-2 assets into third_party/ref (never committed).
# Usage: bash scripts/fetch-reference.sh [--dry-run]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT="9a7b2e9c39f816d6c699c2a133e11b6d8bfdc464"
CASES_SHA="bfb8a8e71a66beb33bd50590c79d5f22d43ae7c4350bcabb1a1dcd616b39d962"
REF="$ROOT/third_party/ref"
MANIFEST="$ROOT/third_party/ref-manifest.json"
LEDGER="$ROOT/ledger/append.jsonl"

if [ "${1:-}" = "--dry-run" ]; then
    echo "[dry-run] would clone github.com/freestylefly/awesome-gpt-image-2 at $COMMIT"
    echo "[dry-run] would verify data/cases.json sha256 == $CASES_SHA"
    exit 0
fi
mkdir -p "$ROOT/third_party" "$ROOT/ledger"

# True iff the ledger already recorded ref_fetched for the pinned commit.
ledger_has_ref_event() {
    python3 -c '
import sys
sys.path.insert(0, str(__import__("pathlib").Path(sys.argv[1]).parents[1] / "scripts"))
from lib.ledger import load_events
for ev in load_events(sys.argv[1]):
    if ev.get("type") == "ref_fetched" and ev.get("idem") == sys.argv[2][:12]:
        sys.exit(0)
sys.exit(1)
' "$LEDGER" "$COMMIT"
}

# Skip only when everything checks out; any hole falls through to a full repair fetch.
REASON=""
if ! grep -qF "\"commit\":\"$COMMIT\"" "$MANIFEST" 2>/dev/null; then
    REASON="manifest missing or pinned commit absent"
elif [ ! -f "$REF/data/cases.json" ]; then
    REASON="data/cases.json missing"
elif [ "$(sha256sum "$REF/data/cases.json" | cut -d' ' -f1)" != "$CASES_SHA" ]; then
    REASON="data/cases.json sha256 mismatch"
elif ! ledger_has_ref_event; then
    REASON="ledger lacks ref_fetched event for ${COMMIT:0:12}"
fi
if [ -n "$REASON" ]; then
    echo "[repair] ref state incomplete ($REASON); fetching anew"
else
    echo "[skip] ref already fetched at $COMMIT"; exit 0
fi

rm -rf /tmp/agi2-src
# GIT_SSL_NO_VERIFY is required: this container sits behind a TLS-interception proxy.
GIT_SSL_NO_VERIFY=1 git clone https://github.com/freestylefly/awesome-gpt-image-2.git /tmp/agi2-src
git -C /tmp/agi2-src checkout "$COMMIT"
ACTUAL=$(sha256sum /tmp/agi2-src/data/cases.json | cut -d' ' -f1)
if [ "$ACTUAL" != "$CASES_SHA" ]; then
    echo "[FATAL] cases.json sha mismatch: $ACTUAL" >&2; exit 1
fi
# Only after checksum success touch the existing tree: swap in and prune to
# data/, LICENSE, README.md so a failed clone never destroys a good $REF.
rm -rf "$REF"
mv /tmp/agi2-src "$REF"
rm -rf "$REF/.git"
find "$REF" -mindepth 1 -maxdepth 1 ! -name data ! -name LICENSE ! -name README.md -exec rm -rf {} +
# Ledger-first finalize: a crash between these steps leaves no manifest, so the
# next run does a full clean re-fetch instead of skipping forever.
python3 - "$LEDGER" "$COMMIT" <<'PY'
import sys; sys.path.insert(0, str(__import__("pathlib").Path(sys.argv[1]).parents[1] / "scripts"))
from lib.ledger import append_event
append_event(sys.argv[1], "ref_fetched", {"commit": sys.argv[2]}, idem=sys.argv[2][:12])
PY
printf '{"commit":"%s","cases_sha256":"%s","fetched_at":"%s"}\n' \
    "$COMMIT" "$CASES_SHA" "$(date -u +%FT%TZ)" > "$MANIFEST"
echo "[ok] reference fetched and verified"
