# Prompts to paste into Claude Code, in order

Setup: put this kit's files in the root of your `bankguard-redteam` repo (keep the `.claude/` folder),
open a terminal in the repo, run `claude`, and paste prompt 1. Review each result before the next.
Commit after every prompt. Do not paste your API key into Claude Code; it reads `.env` through code
only, and `.claude/settings.json` blocks it from opening `.env`.

## Prompt 1: scaffold and mock bank (Mon, about 1.5h)
Read CLAUDE.md and docs/PLAN.md. Use the mock-bank skill. Create the folder layout from CLAUDE.md,
requirements.txt (openai, python-dotenv, fastapi, uvicorn, pytest), and the mock bank with 3 synthetic
customers, canary secrets, the four tools with JSON schemas and an executor, snapshot() and diff().
Write pytest tests and run them. Show me the file list and test output.

## Prompt 2: model interface and assistant loop (Mon, about 1.5h)
Use the nebius-model-client skill. Implement agent/models.py with the chat interface, a gullible
FakeModel that obeys instructions found in user text and in memo text, and NebiusModel that reads
model IDs from env vars. Implement the assistant loop (system prompt, tool-call rounds, cap of 6).
Make it runnable with the fake model only, since I may not have Nebius access yet. Add a small test
where the fake model gets tricked by a memo injection. Do not call the network.

## Prompt 3: scorer and runner (Mon, about 1.5h)
Use the scorer-and-benchmark skill. Implement scoring/scorer.py with the four deterministic rules
and tests with near-misses, then bench/run_benchmark.py with the arguments in the skill, raw jsonl
logs and the markdown table. Run it on a single hand-written attack with the fake model and show the output.

## Prompt 4: attacks and benign tasks (Tue, about 2h)
Use the attack-catalog skill. Write data/attacks_dev.json (12), data/attacks_test.json (8) and
data/benign.json (15), balanced across the four categories, with checkable success criteria. Then
run the attack-reviewer subagent on them and fix what it reports. Commit the test file and do not
edit it again afterwards.

## Prompt 5: defenses (Tue/Wed, about 2.5h)
Use the defenses skill. Implement layer 1 (tool-call policy with real confirmation and untrusted
data wrapping), layer 2 (risk score and cooling-off), the output filter, config switches, and tests.
Run dev attacks and the benign suite with the fake model to confirm the pipeline works. Report the
dev success rate and benign false-block rate per configuration. Never run the test split.

## Prompt 6: real model runs (Wed, needs Nebius access)
Check that `.env` has the key and model IDs (do not read the file; use python-dotenv to load and
print only whether each variable is set). Run a one-call tool-calling test on nano, then
/run-baseline `nebius --size nano`. Implement layer 3 (safety check) if time allows. Run the defended
dev configurations, then, only when I say so, the frozen test split once per configuration into
bench/results/final/. Log friction with /log-feedback.

## Prompt 7: demo (Thu morning, about 2h)
Use the demo-and-submission skill. Build demo/app.py and demo/static/index.html with the chat box,
defenses toggle, 4 sample attacks, rate limit, daily cap and replay mode, plus deployment files for
Hugging Face Spaces or Render. Test locally with the fake model and show me how to run it.

## Prompt 8: docs and submission (Thu afternoon, about 2h)
Write README.md using only numbers from bench/results/final/, docs/VIDEO_SCRIPT.md with timings,
and docs/DEVPOST.md (elevator pitch under 200 characters, description, built-with, feedback from
docs/FEEDBACK_NOTES.md). Then run /submit-check and use the results-auditor subagent. List the
failures and fix them.

## If Nebius access is still blocked on Wednesday
Tell Claude Code: "Token Factory is blocked for my account. Finish prompts 1 to 5 and 7 with the
fake model, make everything switch to the real model by setting env vars, and write a runbook for
running the real benchmark in under 30 minutes once access arrives." Then use the teammate fallback
from docs/PLAN.md.
