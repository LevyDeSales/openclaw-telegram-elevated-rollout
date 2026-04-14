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
PRINCIPAL_STATE_DIR="${OPENCLAW_PRINCIPAL_STATE_DIR:-$HOME_DIR/.openclaw}"

exec env -i \
  HOME="$HOME_DIR" \
  PATH="$PATH_VALUE" \
  SHELL="$SHELL_VALUE" \
  TERM="$TERM_VALUE" \
  OPENCLAW_STATE_DIR="$PRINCIPAL_STATE_DIR" \
  openclaw "$@"
