#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "[FAIL] $*" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WRAPPER="$SCRIPT_DIR/principal-openclaw.sh"
HOME_DIR="${HOME:?HOME is required}"
PRINCIPAL_STATE_DIR_RAW="${OPENCLAW_PRINCIPAL_STATE_DIR:-$HOME_DIR/.openclaw}"
PRINCIPAL_STATE_DIR="${PRINCIPAL_STATE_DIR_RAW%/}"
EXPECTED_PRINCIPAL_STATE_DIR="$HOME_DIR/.openclaw"
EXPECTED_PRINCIPAL_CONFIG_PATH="$EXPECTED_PRINCIPAL_STATE_DIR/openclaw.json"

[[ -x "$WRAPPER" ]] || fail "wrapper not executable: $WRAPPER"
[[ "$PRINCIPAL_STATE_DIR" == "$EXPECTED_PRINCIPAL_STATE_DIR" ]] || fail "principal state dir does not match expected principal target: $PRINCIPAL_STATE_DIR"
[[ "$PRINCIPAL_STATE_DIR" != *".openclaw-rescue"* ]] || fail "principal state dir still points to rescue: $PRINCIPAL_STATE_DIR"
[[ -f "$EXPECTED_PRINCIPAL_CONFIG_PATH" ]] || fail "principal config missing: $EXPECTED_PRINCIPAL_CONFIG_PATH"
command -v python3 >/dev/null 2>&1 || fail "python3 not found in PATH"
python3 -m json.tool "$EXPECTED_PRINCIPAL_CONFIG_PATH" >/dev/null 2>&1 || fail "principal config is not valid JSON: $EXPECTED_PRINCIPAL_CONFIG_PATH"

STATUS_OUTPUT="$($WRAPPER gateway status 2>&1)" || fail "principal gateway status failed"
printf '%s\n' "$STATUS_OUTPUT"

grep -Fq "Config (cli): ~/.openclaw/openclaw.json" <<<"$STATUS_OUTPUT" || fail "gateway status did not prove principal cli config"
grep -Fq "Config (service): ~/.openclaw/openclaw.json" <<<"$STATUS_OUTPUT" || fail "gateway status did not prove principal service config"
grep -Fq "RPC probe: ok" <<<"$STATUS_OUTPUT" || fail "principal RPC probe is not ok"
if grep -Fq ".openclaw-rescue" <<<"$STATUS_OUTPUT"; then
  fail "principal preflight still references rescue"
fi

AGENT_COUNT="$(python3 - <<'PY'
import json, os, sys
path=os.path.expanduser('~/.openclaw/openclaw.json')
with open(path, 'r', encoding='utf-8') as f:
    data=json.load(f)
agents=((data.get('agents') or {}).get('list') or [])
if not isinstance(agents, list):
    print('INVALID')
    sys.exit(0)
print(len([a for a in agents if isinstance(a, dict) and a.get('id')]))
PY
)"
[[ "$AGENT_COUNT" != "INVALID" ]] || fail "principal config does not contain a valid agents.list"
[[ "$AGENT_COUNT" -gt 0 ]] || fail "principal config has no agents to plan against"

echo "[OK] principal gateway status references principal config and rpc is ok"
echo "[OK] principal config contains $AGENT_COUNT agent(s)"
