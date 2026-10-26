---
description: Run the undefended baseline on the dev split and summarize it
---

Run the benchmark with defenses off on the dev split, 3 runs per attack:

`python -m bench.run_benchmark --model $ARGUMENTS --split dev --runs 3 --defenses off`

(`$ARGUMENTS` is `fake` or `nebius --size nano`.) Then show the markdown table, the three attacks
that succeeded most often, and the token and latency totals. If model is `fake`, state that the
numbers are pipeline tests only. Do not run the test split.
