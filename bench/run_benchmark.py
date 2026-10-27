"""Benchmark runner: attacks (and the benign suite) through the assistant, scored deterministically.

python -m bench.run_benchmark --model fake --split dev
python -m bench.run_benchmark --model nebius --size nano --split dev --runs 3 --defenses off
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from agent.assistant import run_turn
from agent.console import use_utf8_stdout
from agent.models import make_model
from attacks.loader import BENIGN, SPLITS, load_attacks, load_benign
from bank.state import Bank
from scoring.scorer import score_attack, score_benign

RESULTS = Path(__file__).resolve().parent / "results"
FINAL = RESULTS / "final"
PRICES = Path(__file__).resolve().parent / "prices.json"
DEFENSES = ("off", "policy", "policy+risk", "all")
IMPLEMENTED_DEFENSES = ("off",)
PIPELINE_BANNER = "PIPELINE TEST ONLY (FakeModel): these numbers are not results."


def config_name(args):
    model = "fake" if args.model == "fake" else f"nebius-{args.size}"
    return f"{model}_{args.split}_def-{args.defenses}_runs{args.runs}"


def output_dir(args):
    """Test split goes to final/ (once per config). FakeModel may never write there."""
    if args.split != "test":
        return RESULTS
    if args.model == "fake":
        raise SystemExit("Refusing: FakeModel output may not be written to bench/results/final/. "
                         "Use --split dev for pipeline tests.")
    existing = list(FINAL.glob(f"*_{config_name(args)}.jsonl")) if FINAL.exists() else []
    if existing and not args.force:
        raise SystemExit(f"Refusing: test split already run for this config ({existing[0].name}). "
                         "The test set is run once per configuration. Pass --force to override.")
    return FINAL


def apply_setup(bank, setup):
    memo = (setup or {}).get("seed_memo")
    if memo:
        bank.plant_memo(memo, account_id=(setup or {}).get("seed_account"))


def run_item(model, item):
    """Fresh bank, fresh conversation, all turns. Returns the raw record pieces."""
    bank = Bank("C-1")
    apply_setup(bank, item.get("setup"))
    before = bank.snapshot()
    history, outputs, tool_log, transcript = None, [], [], []
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "latency_s": 0.0, "calls": 0}
    error = None
    for turn in item["turns"]:
        try:
            out = run_turn(model, bank, turn, history=history)
        except Exception as e:  # keep the run going; the error is logged and visible
            error = f"{type(e).__name__}: {e}"
            break
        history = out["messages"]
        outputs += out["outputs"]
        tool_log += out["tool_log"]
        transcript.append({"user": turn, "final": out["final"], "rounds": out["rounds"],
                           "capped": out["capped"], "usage": out["usage"]})
        for k in usage:
            usage[k] += out["usage"].get(k, 0)
    usage["latency_s"] = round(usage["latency_s"], 3)
    return bank, before, outputs, tool_log, transcript, usage, history, error


def load_prices(model):
    model_id = getattr(model, "model", None)
    if not model_id or not PRICES.exists():
        return None
    text = PRICES.read_text(encoding="utf-8").strip()
    if not text:
        return None
    try:
        p = json.loads(text).get(model_id)
    except (ValueError, AttributeError) as e:
        raise SystemExit(f"bench/prices.json is not a valid JSON object: {e}")
    if p is None:
        return None
    # {"input_per_1m": float, "output_per_1m": float}, typed in by the owner
    if not all(isinstance(p.get(k), (int, float)) for k in ("input_per_1m", "output_per_1m")):
        raise SystemExit(f"bench/prices.json entry for {model_id} needs numeric "
                         "input_per_1m and output_per_1m")
    return p


def cost(usage, prices):
    if not prices:
        return None
    return (usage["prompt_tokens"] * prices["input_per_1m"]
            + usage["completion_tokens"] * prices["output_per_1m"]) / 1e6


def rate(k, n):
    return f"{k}/{n} = {100 * k / n:.0f}%" if n else "n/a"


def build_table(args, attack_recs, benign_recs, prices, label):
    by_cat = defaultdict(list)
    for r in attack_recs:
        by_cat[r["category"]].append(r)
    bk = sum(not r["score"]["passed"] for r in benign_recs)
    benign_rate = rate(bk, len(benign_recs))

    def row(name, recs, fb):
        n = len(recs)
        k = sum(r["score"]["success"] for r in recs)
        lat = sum(r["usage"]["latency_s"] for r in recs) / n if n else 0
        tok = sum(r["usage"]["prompt_tokens"] + r["usage"]["completion_tokens"] for r in recs)
        c = [cost(r["usage"], prices) for r in recs]
        cs = f"${sum(c):.4f}" if prices else "n/a (no bench/prices.json entry)"
        return (f"| {name} | {len({r['id'] for r in recs})} | {args.runs} | {k} | {rate(k, n)} "
                f"| {fb} | {lat:.2f} s | {tok} | {cs} |")

    lines = [f"# Benchmark: {label}", ""]
    if args.model == "fake":
        lines += [f"**{PIPELINE_BANNER}**", ""]
    lines += ["Attack success = the deterministic scorer saw an unauthorized state change or a "
              "canary leak. Results apply to this mock assistant only.", ""]
    if args.runs <= 3:
        lines += [f"Small sample: {args.runs} run(s) per attack.", ""]
    lines += ["| category | attacks | runs | successes | success rate | benign false-block "
              "| mean latency / run | tokens | est. cost |",
              "|---|---|---|---|---|---|---|---|---|"]
    for cat in sorted(by_cat):
        lines.append(row(cat, by_cat[cat], "-"))
    lines.append(row("**total**", attack_recs, benign_rate))
    lines += ["", "## What still gets through", ""]
    hits = [r for r in attack_recs if r["score"]["success"]]
    if not hits:
        lines.append("Nothing: no attack succeeded in this run.")
    else:
        lines += ["| id | category | run | rules fired | reason (owner) |", "|---|---|---|---|---|"]
        for r in hits:
            lines.append(f"| {r['id']} | {r['category']} | {r['run']} | "
                         f"{', '.join(r['score']['rules'])} | _owner: add one-line reason_ |")
    failed_benign = [r for r in benign_recs if not r["score"]["passed"]]
    if failed_benign:
        lines += ["", "## Benign tasks wrongly failed", ""]
        lines += [f"- {r['id']} (run {r['run']})" for r in failed_benign]
    return "\n".join(lines) + "\n"


def main(argv=None):
    use_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", choices=("fake", "nebius"), default="fake")
    ap.add_argument("--size", choices=("nano", "super", "ultra"), default="nano")
    ap.add_argument("--split", choices=("dev", "test"), default="dev")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--defenses", choices=DEFENSES, default="off")
    ap.add_argument("--attacks", help="override the attack file (dev pipeline checks only)")
    ap.add_argument("--benign", help="override the benign file")
    ap.add_argument("--force", action="store_true", help="re-run the test split for a config")
    args = ap.parse_args(argv)

    if args.model == "fake":
        print(PIPELINE_BANNER)
    if args.runs < 1:
        raise SystemExit("--runs must be >= 1")
    if args.defenses not in IMPLEMENTED_DEFENSES:
        raise SystemExit(f"--defenses {args.defenses} is not implemented yet (defenses/ is empty).")
    if args.attacks and args.split == "test":
        raise SystemExit("--attacks cannot be combined with --split test.")
    out_dir = output_dir(args)

    attack_path = Path(args.attacks) if args.attacks else SPLITS[args.split]
    benign_path = Path(args.benign) if args.benign else BENIGN
    if not attack_path.exists():
        raise SystemExit(f"Attack file not found: {attack_path}")
    attacks = load_attacks(attack_path)
    benign = load_benign(benign_path) if benign_path.exists() else []
    if not benign:
        print(f"Warning: no benign tasks ({benign_path} missing); false-block rate is n/a.")

    model = make_model(args.model, args.size)
    prices = load_prices(model)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    cfg = config_name(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"{stamp}_{cfg}.jsonl"
    meta = {"kind": "meta", "config": cfg, "model": getattr(model, "model", model.name),
            "attack_file": str(attack_path), "benign_file": str(benign_path),
            "started": stamp, "pipeline_test_only": args.model == "fake"}

    attack_recs, benign_recs = [], []
    with log_path.open("w", encoding="utf-8") as log:
        log.write(json.dumps(meta) + "\n")
        for kind, items in (("attack", attacks), ("benign", benign)):
            for item in items:
                for run in range(1, args.runs + 1):
                    t0 = time.perf_counter()
                    bank, before, outputs, tool_log, transcript, usage, msgs, err = \
                        run_item(model, item)
                    after = bank.snapshot()
                    if kind == "attack":
                        score = score_attack(before, after, outputs, tool_log, item)
                        flag = "SUCCESS" if score["success"] else "held"
                    else:
                        score = score_benign(before, after, outputs, tool_log, item)
                        flag = "pass" if score["passed"] else "FAIL"
                    rec = {"kind": kind, "id": item["id"], "category": item.get("category", "benign"),
                           "run": run, "score": score, "usage": usage, "error": err,
                           "wall_s": round(time.perf_counter() - t0, 3),
                           "transcript": transcript, "tool_log": tool_log, "outputs": outputs,
                           "messages": msgs, "before": before, "after": after}
                    log.write(json.dumps(rec) + "\n")
                    (attack_recs if kind == "attack" else benign_recs).append(rec)
                    extra = f" rules={score['rules']}" if kind == "attack" and score["rules"] else ""
                    print(f"{kind:6} {item['id']:>6} run {run}: {flag}{extra}"
                          + (f" ERROR {err}" if err else ""))

    table = build_table(args, attack_recs, benign_recs, prices, cfg)
    md_path = log_path.with_suffix(".md")
    md_path.write_text(table, encoding="utf-8")
    print("\n" + table)
    print(f"Raw log: {log_path}\nTable:   {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
