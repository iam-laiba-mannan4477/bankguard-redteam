# Tools, MCP servers, plugins, guardrails: what to use and what to skip

## Use
- **Claude Code built-in tools** (read, edit, bash, glob, grep): everything in this project.
- **Skills** (`.claude/skills/*/SKILL.md`): six, included. They load only when relevant.
- **Subagents** (`.claude/agents/*.md`): results-auditor and attack-reviewer, both read-only.
- **Slash commands** (`.claude/commands/*.md`): /run-baseline, /submit-check, /log-feedback.
- **Hook** (`.claude/hooks/block_secrets.sh`): blocks git commit/push if `.env` or an API key is staged.
- **Permissions** (`.claude/settings.json`): denies reading or editing `.env`, force-push, rm -rf,
  curl and wget; allows python, pytest, uvicorn and basic git. Review it and adjust to taste.
- **pytest** is your safety net: bank, scorer and defenses must have tests.

## MCP servers: none are required
Everything runs from Python and the shell. Add MCP servers only if you hit a real need:
- GitHub MCP: only to manage the repo or issues from Claude Code; `git` already covers commits.
- Tavily MCP: skip. The Tavily prize needs deep Tavily use, which is out of this scope.
- Do not add MCP servers that can read your files, email or browser for this project. More access
  means more risk and nothing here needs it.
If you add one later, add it to `.mcp.json` yourself after reading what it can access.

## Plugins
None needed. A plugin bundles skills, agents, commands and hooks, which you already have as plain
project files. Packaging this as a plugin is a nice-to-have after the hackathon, not before it.

## Runtime guardrails (inside the product)
Described in the defenses skill: tool-call policy, risk score with cooling-off, Nemotron safety
check, output filter. Those are what the benchmark measures. They are separate from the Claude Code
permissions above, which protect your machine and your keys while building.

## Claude Code safety habits
- Run it in the repo folder only. Do not give it access to folders with personal files.
- Never paste keys or card details into the prompt.
- Review diffs before committing.
- If a key is ever committed, delete it in the Token Factory console and create a new one.
