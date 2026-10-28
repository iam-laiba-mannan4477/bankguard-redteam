# BankGuard Red Team: build plan

Deadline: Fri Oct 30, 2026 10:00pm PKT. Submit Thu Oct 29. About 22 working hours.

## Architecture
```
attacker (scripted attacks; LLM variations are cut)  -->  assistant under test (Nemotron + tools)
                                                              |  tool calls
                                                              v
                                                       mock bank (synthetic state, canary)
                                                              |
                         scorer: state diff + canary check  <-- snapshots before/after
                                                              |
defenses wrap the assistant: input check -> tool-call policy -> risk score -> output check
benchmark runner: attacks x runs x (defenses off/on) -> results/*.json + markdown table
demo: FastAPI chat with defenses toggle + one-click sample attacks
```

## Scope
Keep: 4 categories x 5 attacks (20), 15 benign tasks, 4 tools (get_balance, list_transactions,
transfer, add_payee), 3 runs per attack, 3 defenses.
Categories: account_takeover, unauthorized_transfer, data_leakage, memo_injection.
Cut: scam-victim interception, SIM swap simulation, LLM-generated variations, Tavily, dashboard polish.
Split: 12 dev attacks, 8 test attacks (frozen).

## Day by day
### Sun Oct 25 night (max 45 min)
Repo, venv, .gitignore (.env), .env.example, copy this kit in, commit.
If Nebius access is unblocked: key, check_models, tool-calling test. If not, continue with FakeModel.
### Mon Oct 26 (4.5h)
Mock bank, tool schemas and executor, model interface (FakeModel + NebiusModel), assistant loop,
scorer, runner. Hand-test 5 attacks against FakeModel. Gate: assistant completes a tool loop.
### Tue Oct 27 (4.5h)
20 attacks (data files), 15 benign tasks, dev/test split frozen, defenses in plain Python
(policy + risk), demo skeleton. If Nebius works: real baseline, 3 runs each.
### Wed Oct 28 (4.5h)
Real model runs: baseline, defended dev runs, nemotron safety check layer, frozen test run ONCE,
failure analysis (5 lines on what still gets through).
### Thu Oct 29 (5h)
Deploy demo (free host, key as server secret, rate limit), README with results, 3-minute video,
Devpost text, feedback, SUBMIT.
### Fri Oct 30
Buffer, fixes only, hard stop 6pm PKT.

## Cut order if behind
1. nemotron safety check layer  2. fourth category  3. demo toggle polish.
Never cut: scorer, frozen test set, benign suite, public demo, README, video.

## Blocker plan (Nebius billing country)
Pakistan may be missing from Token Factory billing. Contacted Nebius (Contact us, Discord, hackathon
manager). Decision point: Tue noon PKT. Fallback: a trusted teammate in a supported country owns the
Token Factory account; the owner builds against FakeModel until then. No other model providers allowed.

## Video (3 min)
0:00 problem. 0:25 attack succeeds (defenses off). 1:00 same attack blocked.
Use an attack a defense really stopped (recorded AT-T1 or UT-T1 replay), not memo injection:
Nano mostly ignores memo injection even with defenses off (dev 0 of 9; test 1 of 6), so the benchmark does not show that the memo defense works.
1:45 results table + false-block rate. 2:30 what still gets through, repo, feedback.

## Feedback notes (required, prize-eligible)
Track in docs/FEEDBACK_NOTES.md: signup, credits, billing country gap, reasoning-content behavior,
tool-calling quality, safety model availability, docs gaps, what worked.
