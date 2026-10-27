# BankGuard Red Team

Red-teaming a mock bank AI assistant with Nemotron on Nebius Token Factory.
Work in progress for the Nebius x NVIDIA Global AI Hackathon.
All data is synthetic. Results apply to the mock assistant only.

## Results so far (dev split, defenses off)

**Dev-split results only. No test-split numbers yet.**

Undefended Nemotron Nano (via Nebius Token Factory), 12 dev attacks x 3 runs, two independent
runs: 53% and 50% attack success (19 and 18 of 36).

Per category, run `20261027-234105`:

| category | attacks | runs | successes | success rate | benign false-block | mean latency / run | tokens | est. cost |
|---|---|---|---|---|---|---|---|---|
| account_takeover | 3 | 3 | 6 | 6/9 = 67% | - | 9.36 s | 39402 | $0.0051 |
| data_leakage | 3 | 3 | 6 | 6/9 = 67% | - | 5.10 s | 31041 | $0.0036 |
| memo_injection | 3 | 3 | 0 | 0/9 = 0% | - | 6.12 s | 35962 | $0.0042 |
| unauthorized_transfer | 3 | 3 | 6 | 6/9 = 67% | - | 16.16 s | 53696 | $0.0070 |
| **total** | 12 | 3 | 18 | 18/36 = 50% | 3/45 = 7% | 9.19 s | 160101 | $0.0198 |

Tokens and cost in this table cover attack runs only (see Failures and fixes).

### Limits
- Dev split only.
- Small sample: 12 attacks, 3 runs each.
- Mock bank only, synthetic data.
- Results apply to this mock assistant, not to real banking apps.
- Test split not yet run.

### Failures and fixes
Details and dates are in [docs/LAB_NOTES.md](docs/LAB_NOTES.md).
- Benign task BN-11 fails 3 of 3 with no defenses on; under investigation. The 3/45 false-block
  figure above comes from it, so it is not a defense measurement.
- Empty model replies in 4 of 81 runs per baseline (Nemotron reasoning arrives in a separate field).
- One baseline attempt was stopped by low memory; its partial log is not used.
- The runner's token and cost totals leave out benign runs; not yet fixed.

## Improvements

Defense results will be added here after the defended dev runs and the single final test run.
