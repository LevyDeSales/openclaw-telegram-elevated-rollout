#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "[FAIL] $*" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WRAPPER="$SCRIPT_DIR/rescue-openclaw.sh"
HOME_DIR="${HOME:?HOME is required}"
RESCUE_STATE_DIR_RAW="${OPENCLAW_RESCUE_STATE_DIR:-$HOME_DIR/.openclaw-rescue}"
RESCUE_STATE_DIR="${RESCUE_STATE_DIR_RAW%/}"
RESCUE_CONFIG_PATH_RAW="${OPENCLAW_RESCUE_CONFIG_PATH:-$RESCUE_STATE_DIR/openclaw.json}"
RESCUE_CONFIG_PATH="${RESCUE_CONFIG_PATH_RAW%/}"
EXPECTED_RESCUE_STATE_DIR="$HOME_DIR/.openclaw-rescue"
EXPECTED_RESCUE_CONFIG_PATH="$EXPECTED_RESCUE_STATE_DIR/openclaw.json"

[[ -x "$WRAPPER" ]] || fail "wrapper not executable: $WRAPPER"
[[ "$RESCUE_STATE_DIR" == "$EXPECTED_RESCUE_STATE_DIR" ]] || fail "rescue state dir does not match expected rescue target: $RESCUE_STATE_DIR"
[[ "$RESCUE_CONFIG_PATH" == "$EXPECTED_RESCUE_CONFIG_PATH" ]] || fail "rescue config path does not match expected rescue target: $RESCUE_CONFIG_PATH"
[[ -f "$RESCUE_CONFIG_PATH" ]] || fail "rescue config missing: $RESCUE_CONFIG_PATH"
command -v python3 >/dev/null 2>&1 || fail "python3 not found in PATH"
python3 -m json.tool "$RESCUE_CONFIG_PATH" >/dev/null 2>&1 || fail "rescue config is not valid JSON: $RESCUE_CONFIG_PATH"

STATUS_OUTPUT="$($WRAPPER gateway status 2>&1)" || fail "rescue gateway status failed"

printf '%s\n' "$STATUS_OUTPUT"

grep -Fq "Config (cli): ~/.openclaw-rescue/openclaw.json" <<<"$STATUS_OUTPUT" || fail "gateway status did not prove rescue cli config"
grep -Fq "Config (service): ~/.openclaw-rescue/openclaw.json" <<<"$STATUS_OUTPUT" || fail "gateway status did not prove rescue service config"
grep -Fq "RPC probe: ok" <<<"$STATUS_OUTPUT" || fail "rescue RPC probe is not ok"
if grep -Fq "Config (cli): ~/.openclaw/openclaw.json" <<<"$STATUS_OUTPUT"; then
  fail "rescue preflight still points to principal config"
fi
if grep -Fq "Config (service): ~/.openclaw/openclaw.json" <<<"$STATUS_OUTPUT"; then
  fail "rescue service config still points to principal config"
fi

echo "[OK] rescue gateway status references rescue config and rpc is ok"
