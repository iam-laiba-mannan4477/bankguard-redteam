# BankGuard Red Team

Red-teaming a mock bank AI assistant with Nemotron on Nebius Token Factory.
Work in progress for the Nebius x NVIDIA Global AI Hackathon.
All data is synthetic. Results apply to the mock assistant only.

## Setup and run

All customers, accounts, balances and secrets are synthetic. Nothing here touches a real bank,
real API or real person's data.

Requires Python 3.10 or newer (developed on 3.12).

```
python -m venv .venv
.venv\Scriptsctivate        # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the repo root (it is git-ignored) with these variables:

- `NEBIUS_API_KEY`: your Nebius Token Factory API key
- `MODEL_NANO`, `MODEL_SUPER`, `MODEL_ULTRA`: model IDs copied from the Token Factory model list
  (IDs get retired, so they are not hardcoded)

Run the tests and the benchmark:

```
pytest -q
python -m bench.run_benchmark --model fake --split dev                      # offline pipeline test, not results
python -m bench.run_benchmark --model nebius --size nano --split dev --runs 3 --defenses off
```

`--defenses` takes `off`, `policy`, `policy+risk` or `policy+risk+filter`. Logs and tables go to
`bench/results/`.

Run the demo (not built yet; this will be the command):

```
uvicorn demo.app:app --reload
```

## Nebius and NVIDIA usage

- Model: NVIDIA Nemotron, served through Nebius Token Factory at
  `https://api.tokenfactory.nebius.com/v1/` with the OpenAI-compatible `openai` SDK. No other
  provider is used for the model.
- All results so far use Nemotron Nano (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, the ID recorded
  in the run logs). Super and Ultra are configured but not used yet.
- Why Nemotron: it is an open NVIDIA model with tool calling, which the assistant needs for its
  four bank tools. Nano is cheap and fast enough to run every attack several times.

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
- The 3/45 benign false-block above came only from BN-11, and the cause was a wrong pass check:
  the model correctly answered "No." but the check also demanded the balance figure. The check
  was fixed; a benign-only re-run (Nano, defenses off, 3 runs) passed 45 of 45.
- Empty model replies in 4 of 81 runs per baseline (Nemotron reasoning arrives in a separate field).
- One baseline attempt was stopped by low memory; its partial log is not used.
- The runner's token and cost totals leave out benign runs; not yet fixed.

## Improvements

Defense results will be added here after the defended dev runs and the single final test run.
