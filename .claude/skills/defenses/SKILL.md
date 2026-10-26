---
name: defenses
description: Build or tune the guardrail layers (tool-call policy, transaction risk score with cooling-off, Nemotron safety check) around the assistant. Use when working in defenses/ or when dev attack results need improving.
---

# Defenses (guardrails)

Defenses wrap the assistant. The mock bank stays naive so the baseline is honest.
Tune ONLY against `data/attacks_dev.json` and `data/benign.json`. Never look at the test split results.

## Layer 1: tool-call policy (defenses/policy.py), plain Python, deterministic
- `transfer` requires a real confirmation step: the policy pauses the call, asks the user in the chat
  to confirm amount and payee, and only then executes with `confirmed=true`. The model can never set
  `confirmed` itself.
- No `add_payee` and `transfer` to that new payee in the same conversation turn.
- Tool arguments must refer to the session customer's own accounts.
- Untrusted text rule: memo, payee name and any tool-result text is wrapped as data
  (`<untrusted_data>...</untrusted_data>`) and the system prompt states it is never instructions.
- Rate and amount limits per session.

## Layer 2: transaction risk score (defenses/risk.py), deterministic
Score from: new payee, amount versus history, recent contact-detail change, repeated attempts.
Above a threshold: hold the transfer (cooling-off) and tell the user why. Keep the threshold
configurable. Report how many benign tasks it wrongly holds.

## Layer 3: Nemotron safety check (defenses/safety_check.py)
Check user input and assistant output with a Nemotron classifier prompt that returns structured JSON
`{"risk": "low|medium|high", "reason": "..."}`. If a dedicated NVIDIA safety/guard model is available
on Token Factory (check `models.txt`), prefer it; otherwise say plainly in the README that this is an
LLM-based classifier prompt. Use the Nano model for it and record cost and latency.
This layer is the first to cut if time runs out.

## Output filter
Always scan assistant output for canary strings and account-number patterns of other customers and
redact them. Log each redaction.

## Rules
- Every defense has a config switch so the benchmark can run off/on combinations.
- After each change, re-run dev attacks and the benign suite and record both numbers in
  `docs/FEEDBACK_NOTES.md` or the results folder.
- Guardrails will not reach 0 percent. Document what still gets through; do not overfit to dev.
