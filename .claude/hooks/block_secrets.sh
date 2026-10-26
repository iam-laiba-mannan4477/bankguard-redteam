#!/usr/bin/env bash
# PreToolUse hook for Bash. Blocks git commit/push when staged changes contain an API key
# or when .env is staged. Reads the tool call JSON on stdin. Exit code 2 blocks the call.
input="$(cat)"
cmd="$(printf '%s' "$input" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)"

case "$cmd" in
  *"git commit"*|*"git push"*) ;;
  *) exit 0 ;;
esac

if git diff --cached --name-only 2>/dev/null | grep -Eq '(^|/)\.env$'; then
  echo "BLOCKED: .env is staged. Unstage it (git restore --staged .env) and make sure .gitignore lists it." >&2
  exit 2
fi

if git diff --cached 2>/dev/null | grep -Eq '^\+.*(NEBIUS_API_KEY|API_KEY|SECRET)[A-Z_]*[[:space:]]*=[[:space:]]*["'"'"']?[A-Za-z0-9._-]{20,}'; then
  echo "BLOCKED: staged changes look like they contain an API key. Remove it before committing. If a key was ever committed, rotate it in the Token Factory console." >&2
  exit 2
fi

exit 0
