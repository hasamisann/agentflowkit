#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
MODEL_FILE="$PROJECT_ROOT/.workflow/config/codex-model.txt"
if [ -f "$MODEL_FILE" ]; then
  CODEX_MODEL=$(tr -d '\r' < "$MODEL_FILE")
else
  CODEX_MODEL=""
fi

if [ -n "$CODEX_MODEL" ]; then
  exec codex -m "$CODEX_MODEL" "$@"
fi

exec codex "$@"
