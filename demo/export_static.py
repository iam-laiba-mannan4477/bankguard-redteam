"""Build a self-contained static site for a Hugging Face Static Space (replay only).

python -m demo.export_static [out_dir]      default: demo/static_site/ (git-ignored)

No server, no API key, no network calls: every recorded run from bench/results/final/*.jsonl is
embedded in one index.html as JSON and rendered with text nodes only. The build fails if the data
contains anything resembling an API key or the value of a secret-looking env variable.
"""
import json
import os
import re
import sys
from pathlib import Path

from demo.app import CONFIG_ORDER, FINAL, _blocks, _brief_log, _state, load_results, verdict

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
DEFAULT_OUT = Path(__file__).resolve().parent / "static_site"

KEY_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"),      # JWT-shaped tokens
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token)\"?\s*[:=]\s*\"[^\"]{12,}\""),
    re.compile(r"NEBIUS_API_KEY"),
]
SECRET_ENV = re.compile(r"(?i)key|token|secret|password")


class SecretFound(RuntimeError):
    pass


def scan_for_secrets(text):
    """Raise SecretFound if the text looks like it contains a key or a secret env value."""
    for pat in KEY_PATTERNS:
        m = pat.search(text)
        if m:
            raise SecretFound(f"key-like string matched {pat.pattern!r}; build stopped")
    for name, value in os.environ.items():
        if SECRET_ENV.search(name) and value and len(value) >= 8 and value in text:
            raise SecretFound(f"value of env variable {name} found in the data; build stopped")


def readme_limits(readme=README):
    """Bullets of the first '### Limits' section of the committed README."""
    text = readme.read_text(encoding="utf-8")
    m = re.search(r"^### Limits\n(.*?)(?=^#)", text, re.S | re.M)
    if not m:
        return []
    items, cur = [], None
    for line in m.group(1).splitlines():
        if line.startswith("- "):
            cur = line[2:].strip(); items.append(cur)
        elif line.startswith("  ") and items:
            items[-1] += " " + line.strip()
    return items


def load_runs(final_dir=FINAL):
    """Every attack record of every config, grouped config -> attack -> run, with captions."""
    runs, attacks, files = {}, {}, {}
    for path in sorted(final_dir.glob("*.jsonl")):
        m = re.search(r"_def-(.+?)_runs", path.name)
        cfg = m.group(1) if m else path.stem
        files[cfg] = path.name
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("kind") != "attack":
                continue
            attacks.setdefault(r["id"], r["category"])
            events = [e for t in r["transcript"] for e in t.get("defense_events", [])]
            brief = _brief_log(r["tool_log"])
            blocks = _blocks(brief, events)
            runs.setdefault(cfg, {}).setdefault(r["id"], {"runs": {}})["runs"][str(r["run"])] = {
                "turns": [{"user": t["user"], "final": t["final"]} for t in r["transcript"]],
                "error": r.get("error"),
                "tool_log": brief, "blocks": blocks,
                "before": _state(r["before"]), "after": _state(r["after"]),
                "verdict": verdict(r["score"]["success"], True, cfg != "off", blocks),
                "rules": r["score"]["rules"],
                "label": f"recorded real run: {path.name}, {r['id']} run {r['run']}"}
    for cfg, by_id in runs.items():
        for aid, entry in by_id.items():
            got = entry["runs"].values()
            wins = sum(x["verdict"] == "ATTACK SUCCEEDED" for x in got)
            who = "undefended" if cfg == "off" else f"defended ({cfg})"
            entry["caption"] = (f"{aid}: succeeded in {wins} of {len(got)} {who} runs on the "
                                f"frozen test split.")
    configs = [c for c in CONFIG_ORDER if c in runs]
    return {"configs": configs, "attacks": [{"id": k, "category": v} for k, v in sorted(attacks.items())],
            "runs": runs, "files": [files[c] for c in configs]}


def build_data(final_dir=FINAL):
    data = load_runs(final_dir)
    data["results"] = load_results()
    data["limits"] = readme_limits()
    return data


def embed_json(data):
    """JSON safe inside <script type="application/json">: no '<', '>' or '&' survive as raw characters."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def render_page(data):
    payload = embed_json(data)
    scan_for_secrets(payload)
    return PAGE.replace("/*__DATA__*/", payload)


def export(out=DEFAULT_OUT, final_dir=FINAL):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    html = render_page(build_data(final_dir))
    (out / "index.html").write_text(html, encoding="utf-8")
    # The previous version of this exporter wrote data/*.json; the page no longer reads them.
    old = out / "data"
    for name in ("results.json", "replays.json", "seed.json"):
        (old / name).unlink(missing_ok=True)
    if old.is_dir() and not any(old.iterdir()):
        old.rmdir()
    return out / "index.html"


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BankGuard Replay</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#16181d;--mute:#5d6470;--line:#dfe3e8;--accent:#1f5fbf;
--bad:#b42318;--badbg:#fdecea;--good:#146c43;--goodbg:#e6f4ec;--warn:#8a5a00;--warnbg:#fff4d6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#111318;--card:#1a1d24;--ink:#e8eaee;
--mute:#9aa2ae;--line:#2c313b;--accent:#6ea2ff;--bad:#ff8a80;--badbg:#3a1d1b;--good:#7ddc9f;--goodbg:#173326;
--warn:#ffd27a;--warnbg:#3a2f12}}
*{box-sizing:border-box}
html,body{overflow-x:hidden}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:960px;margin:0 auto;padding:12px 16px 48px}
h1{font-size:1.3rem;margin:14px 0 4px}h2{font-size:1.05rem;margin:0 0 10px}h3{font-size:.95rem;margin:14px 0 6px}
.banner{padding:10px 16px;font-weight:600;text-align:center}
.mock{background:var(--warnbg);color:var(--warn);border-bottom:1px solid var(--line)}
.hosted{background:var(--card);border-bottom:1px solid var(--line);font-weight:500}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin:14px 0;min-width:0}
.muted{color:var(--mute);font-size:.88rem}
.pickers{display:grid;grid-template-columns:2fr 2fr 1fr;gap:10px}
@media (max-width:640px){.pickers{grid-template-columns:1fr}}
label{display:block;font-size:.85rem;color:var(--mute)}
select{width:100%;font:inherit;padding:10px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);min-height:44px}
.caption{margin:10px 0 0;font-weight:600}
.verdict{font-weight:700;font-size:1.05rem;padding:10px 12px;border-radius:8px;margin:10px 0}
.verdict.bad{background:var(--badbg);color:var(--bad)}.verdict.good{background:var(--goodbg);color:var(--good)}
.verdict.neutral{background:var(--bg);color:var(--mute)}
.msg{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--bg);border-radius:8px;padding:10px;margin-bottom:6px}
.who{font-size:.8rem;color:var(--mute);font-weight:600}
.entry{border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-bottom:8px;overflow-wrap:anywhere}
.entry .k{color:var(--mute);font-size:.8rem}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:.8rem;overflow-wrap:anywhere;white-space:pre-wrap}
.stopped{color:var(--bad);font-weight:600}.ok{color:var(--good)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media (max-width:640px){.two{grid-template-columns:1fr}}
table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:.82rem}
th,td{border-bottom:1px solid var(--line);padding:5px 4px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
th{color:var(--mute);font-weight:600}
ul{padding-left:20px}
</style>
</head>
<body>
<div class="banner mock">MOCK BANK: synthetic data only. Results apply to this mock assistant.</div>
<div class="banner hosted">Hosted page = replay of recorded real runs (Nemotron Nano on Nebius Token Factory). The live demo runs locally: see the README (Setup and run).</div>
<main>
<h1>BankGuard Red Team: recorded runs</h1>
<p class="muted">Every attack run from the frozen test split: 4 defense configs, 3 runs each. Verdicts come from the
deterministic scorer (bank state and canary strings, no LLM judge). Nothing on this page calls a model or the network.</p>

<section class="card">
  <h2>Explore a run</h2>
  <div class="pickers">
    <div><label for="pAttack">Attack</label><select id="pAttack"></select></div>
    <div><label for="pConfig">Defenses</label><select id="pConfig"></select></div>
    <div><label for="pRun">Run</label><select id="pRun"></select></div>
  </div>
  <p class="caption" id="caption"></p>
  <div id="verdict" class="verdict neutral"></div>
  <h3>Conversation</h3><div id="conv"></div>
  <h3>Tool-call log (policy / risk / filter)</h3><div id="tools"></div>
  <h3>Bank state (signed-in customer)</h3>
  <div class="two"><div><b>Before</b><div id="before"></div></div><div><b>After</b><div id="after"></div></div></div>
  <p id="readNote" class="muted" hidden>This attack reads data; the harm is the leak in the reply (detected by the canary), so the bank balances are not expected to change.</p>
  <p class="muted mono" id="label"></p>
</section>

<section class="card">
  <h2>Results</h2>
  <h3>Frozen test split (run once per config)</h3><div id="finalTable"></div>
  <h3>Dev split (defenses were built while looking at these)</h3><div id="devTable"></div>
  <h3>Limits</h3><ul class="muted" id="limits"></ul>
  <p class="muted" id="sources"></p>
</section>
</main>
<script type="application/json" id="data">/*__DATA__*/</script>
<script>
"use strict";
// All recorded text (memos are attacker-controlled) goes into the page as text nodes, never as markup.
var D = JSON.parse(document.getElementById("data").textContent);

function el(tag, attrs) {
  var n = document.createElement(tag);
  if (attrs) for (var k in attrs) {
    if (k === "text") n.textContent = attrs[k];
    else if (k === "cls") n.className = attrs[k];
    else n.setAttribute(k, attrs[k]);
  }
  for (var i = 2; i < arguments.length; i++) {
    var c = arguments[i];
    if (c == null) continue;
    n.appendChild(typeof c === "object" ? c : document.createTextNode(String(c)));
  }
  return n;
}
function $(id) { return document.getElementById(id); }
function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }
function str(v) { return typeof v === "string" ? v : JSON.stringify(v); }
function option(value, text) { var o = el("option", {text: text}); o.value = value; return o; }

function table(header, rows) {
  var t = el("table"), tr = el("tr");
  header.forEach(function (h) { tr.appendChild(el("th", {text: h})); });
  t.appendChild(el("thead", null, tr));
  var tb = el("tbody");
  rows.forEach(function (r) { var row = el("tr"); r.forEach(function (c) { row.appendChild(el("td", {text: c})); }); tb.appendChild(row); });
  t.appendChild(tb);
  return t;
}

function stateView(st) {
  var rows = [];
  Object.keys(st.balances).forEach(function (a) { rows.push(["balance " + a, Number(st.balances[a]).toFixed(2)]); });
  Object.keys(st.payees).forEach(function (p) { rows.push(["payee " + p, st.payees[p].name + " (" + st.payees[p].account_number + ")"]); });
  return table(["item", "value"], rows);
}

function toolsView(r) {
  var box = el("div");
  r.tool_log.forEach(function (t) {
    var outcome = t.executed_by ? el("span", {cls: "ok", text: "executed after the customer's yes"})
      : t.allowed ? el("span", {cls: "ok", text: "allowed"})
      : el("span", {cls: "stopped", text: "STOPPED by " + t.blocked_by + ": " + t.reason});
    box.appendChild(el("div", {cls: "entry"}, el("b", {text: t.name}), " ", outcome,
      el("div", {cls: "k", text: "arguments"}), el("div", {cls: "mono", text: str(t.arguments)}),
      el("div", {cls: "k", text: "result"}), el("div", {cls: "mono", text: t.result || ""})));
  });
  r.blocks.filter(function (b) { return b.layer === "output filter"; }).forEach(function (b) {
    box.appendChild(el("div", {cls: "entry"}, el("b", {text: "(reply)"}), " ",
      el("span", {cls: "stopped", text: "STOPPED by output filter: " + b.reason})));
  });
  if (!box.firstChild) box.appendChild(el("p", {cls: "muted", text: "No tool calls, nothing blocked."}));
  return box;
}

// A canary leak, or an executed read of an account the signed-in customer does not own.
function readsData(r) {
  if ((r.rules || []).indexOf("canary_leak") >= 0) return true;
  return (r.tool_log || []).some(function (t) {
    if (!t.allowed || (t.name !== "get_balance" && t.name !== "list_transactions")) return false;
    var a = t.arguments;
    if (typeof a === "string") { try { a = JSON.parse(a); } catch (e) { a = {}; } }
    return !!(a && a.account_id && !(a.account_id in r.before.balances));
  });
}

function render() {
  var aid = $("pAttack").value, cfg = $("pConfig").value;
  var entry = (D.runs[cfg] || {})[aid];
  var runSel = $("pRun"), keep = runSel.value;
  clear(runSel);
  if (!entry) { $("caption").textContent = "No recorded runs for this pair."; return; }
  Object.keys(entry.runs).sort().forEach(function (k) { runSel.appendChild(option(k, "run " + k)); });
  if (entry.runs[keep]) runSel.value = keep;
  var r = entry.runs[runSel.value];
  $("caption").textContent = entry.caption;
  var v = $("verdict");
  v.textContent = r.verdict + (r.rules.length ? "  (" + r.rules.join(", ") + ")" : "");
  v.className = "verdict " + (r.verdict === "ATTACK SUCCEEDED" ? "bad" : r.verdict === "BLOCKED" ? "good" : "neutral");
  var conv = clear($("conv"));
  r.turns.forEach(function (t) {
    conv.appendChild(el("div", {cls: "msg"}, el("div", {cls: "who", text: "User"}), t.user));
    conv.appendChild(el("div", {cls: "msg"}, el("div", {cls: "who", text: "Assistant"}),
      (t.final || "").trim() ? t.final : "The model returned an empty reply (known Nemotron behaviour: the answer arrives in a reasoning field)."));
  });
  if (r.error) conv.appendChild(el("p", {cls: "stopped", text: "Run error: " + r.error}));
  clear($("tools")).appendChild(toolsView(r));
  clear($("before")).appendChild(stateView(r.before));
  clear($("after")).appendChild(stateView(r.after));
  $("readNote").hidden = !readsData(r);
  $("label").textContent = r.label;
}

function resultsTable(tabs) {
  if (!tabs.length) return el("p", {cls: "muted", text: "No result files found."});
  var rows = [];
  tabs.forEach(function (t) {
    var total = t.rows.filter(function (r) { return r[0] === "**total**"; });
    var cats = t.rows.filter(function (r) { return r[0] !== "**total**"; });
    total.concat(cats).forEach(function (r) {
      rows.push([r[0] === "**total**" ? t.config : "\u2003" + r[0].replace(/_/g, " "), r[4], r[5], r[8]]);
    });
  });
  var wrap = el("div", null, table(["config / category", "attack success", "benign false-block", "est. cost"], rows));
  tabs.forEach(function (t) { if (t.footnote) wrap.appendChild(el("p", {cls: "muted", text: t.footnote})); });
  return wrap;
}

D.attacks.forEach(function (a) { $("pAttack").appendChild(option(a.id, a.id + " (" + a.category.replace(/_/g, " ") + ")")); });
D.configs.forEach(function (c) { $("pConfig").appendChild(option(c, c)); });
["pAttack", "pConfig", "pRun"].forEach(function (id) { $(id).addEventListener("change", render); });
render();
$("finalTable").appendChild(resultsTable(D.results.final));
$("devTable").appendChild(resultsTable(D.results.dev));
D.limits.forEach(function (l) { $("limits").appendChild(el("li", {text: l})); });
$("sources").textContent = "Data: " + D.files.join(", ") + ". Test benign false-block shows n/a: the benign suite was not rerun on test; see the dev table.";
</script>
</body>
</html>
"""


if __name__ == "__main__":
    try:
        path = export(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT)
    except SecretFound as e:
        sys.exit(f"Static build FAILED: {e}")
    print(f"Static site written to {path}")
