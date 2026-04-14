#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "[FAIL] $*" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSPECTOR="$SCRIPT_DIR/inspect_telegram_elevated.py"

[[ -x "$INSPECTOR" ]] || fail "inspector not executable: $INSPECTOR"
command -v python3 >/dev/null 2>&1 || fail "python3 not found in PATH"

INSPECT_OUTPUT="$(python3 "$INSPECTOR" --target rescue-local 2>&1)" || fail "rescue inspector failed"

printf '%s\n' "$INSPECT_OUTPUT"

grep -Fq -- "[OK] gateway context proved for target: rescue-local" <<<"$INSPECT_OUTPUT" || fail "rescue context not proved after restart"
grep -Fq -- "[OK] global elevated gate is enabled" <<<"$INSPECT_OUTPUT" || fail "global elevated gate not enabled after restart"
grep -Fq -- "[OK] requested sender appears in global telegram allowlist: 6204912070" <<<"$INSPECT_OUTPUT" || fail "sender missing from global telegram allowlist after restart"
grep -Fq -- "- watchdog" <<<"$INSPECT_OUTPUT" || fail "watchdog agent missing from inspector output"
grep -Fq -- "- updater" <<<"$INSPECT_OUTPUT" || fail "updater agent missing from inspector output"
grep -Fq -- "effective.availableSender : true" <<<"$INSPECT_OUTPUT" || fail "rescue validation did not find an enabled agent available to the sender"

grep -Fq -- "- override.enabled          : true" <<<"$INSPECT_OUTPUT" || fail "watchdog override enabled=true not visible after restart"
grep -Fq -- "- override.enabled          : false" <<<"$INSPECT_OUTPUT" || fail "updater override enabled=false not visible after restart"

echo "[OK] rescue post-restart validation confirms validated elevated shape"
