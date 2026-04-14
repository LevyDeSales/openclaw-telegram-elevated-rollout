#!/usr/bin/env bash
set -euo pipefail

if ! command -v openclaw >/dev/null 2>&1; then
  echo "openclaw not found in PATH" >&2
  exit 127
fi

HOME_DIR="${HOME:?HOME is required}"
PATH_VALUE="${PATH:-/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:/usr/sbin}"
SHELL_VALUE="${SHELL:-/bin/zsh}"
TERM_VALUE="${TERM:-xterm-256color}"
RESCUE_STATE_DIR="${OPENCLAW_RESCUE_STATE_DIR:-$HOME_DIR/.openclaw-rescue}"
RESCUE_CONFIG_PATH="${OPENCLAW_RESCUE_CONFIG_PATH:-$RESCUE_STATE_DIR/openclaw.json}"

exec env -i \
  HOME="$HOME_DIR" \
  PATH="$PATH_VALUE" \
  SHELL="$SHELL_VALUE" \
  TERM="$TERM_VALUE" \
  OPENCLAW_PROFILE="rescue" \
  OPENCLAW_STATE_DIR="$RESCUE_STATE_DIR" \
  OPENCLAW_CONFIG_PATH="$RESCUE_CONFIG_PATH" \
  openclaw "$@"
