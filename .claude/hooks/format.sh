#!/bin/bash
# Auto-format Python after Claude edits a file. Always exits 0 so it never blocks Claude.
input=$(cat)
file=""
if command -v jq >/dev/null 2>&1; then
  file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')
fi
command -v uv >/dev/null 2>&1 || exit 0
case "$file" in
  *.py) uv run --quiet ruff format --quiet "$file" >/dev/null 2>&1 ;;
  "")   uv run --quiet ruff format --quiet "${CLAUDE_PROJECT_DIR:-.}" >/dev/null 2>&1 ;;
esac
exit 0
