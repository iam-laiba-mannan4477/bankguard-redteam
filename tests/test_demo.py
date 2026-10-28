import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import demo.app as demo_app
from demo.app import DailyCap, RateLimiter

PAGE = Path(demo_app.STATIC / "index.html").read_text(encoding="utf-8")


class _NoModel:
    def chat(self, *a, **k):
        raise AssertionError("the plain path must never call a model")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEMO_MODEL", "fake")
    monkeypatch.setenv("DEMO_RATE_PER_MIN", "100")
    monkeypatch.setattr(demo_app, "_model", None)
    return TestClient(demo_app.create_app())


def _session(c):
    return {"X-Session": c.post("/api/session").json()["session"]}


def test_rate_limit_per_ip_window():
    t = [0.0]
    rl = RateLimiter(2, clock=lambda: t[0])
    assert rl.allow("1.1.1.1") and rl.allow("1.1.1.1")
    assert not rl.allow("1.1.1.1")
    assert rl.allow("2.2.2.2")          # other addresses are not affected
    t[0] = 60.0
    assert rl.allow("1.1.1.1")          # window slides


def test_rate_limit_on_summarize(monkeypatch):
    monkeypatch.setenv("DEMO_MODEL", "fake")
    monkeypatch.setenv("DEMO_RATE_PER_MIN", "1")
    c = TestClient(demo_app.create_app())
    h = _session(c)
    assert c.post("/api/summarize", json={}, headers=h).status_code == 200
    assert c.post("/api/summarize", json={}, headers=h).status_code == 429


def test_daily_cap_and_reset():
    day = [1]
    cap = DailyCap(2, today=lambda: day[0])
    assert cap.take() and cap.take() and not cap.take()
    assert cap.remaining() == 0
    day[0] = 2
    assert cap.remaining() == 2 and cap.take()


def test_cap_reached_falls_back_to_replay(monkeypatch):
    monkeypatch.setenv("DEMO_MODEL", "")
    monkeypatch.setenv("NEBIUS_API_KEY", "test-not-a-key")
    monkeypatch.setenv("MODEL_NANO", "some-model")
    monkeypatch.setenv("DEMO_DAILY_CAP", "0")
    monkeypatch.setattr(demo_app, "get_model", lambda: _NoModel())
    c = TestClient(demo_app.create_app())
    assert c.get("/api/status").json()["mode"] == "replay"
    assert c.post("/api/summarize", json={}, headers=_session(c)).status_code == 503


def test_no_key_means_replay_and_no_env_leak(monkeypatch):
    monkeypatch.delenv("DEMO_MODEL", raising=False)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    c = TestClient(demo_app.create_app())
    s = c.get("/api/status").json()
    assert s["mode"] == "replay"
    assert set(s) == {"mode", "reason", "calls_left_today"}


def test_memo_html_is_stored_as_text_and_page_never_uses_html_sinks(client):
    h = _session(client)
    evil = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
    assert client.post("/api/memo", json={"text": evil}, headers=h).status_code == 200
    r = client.get("/api/transactions", headers=h)
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["transactions"][-1]["memo"] == evil   # data, rendered with textContent
    assert not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write", PAGE)


def test_memo_length_limit(client):
    h = _session(client)
    assert client.post("/api/memo", json={"text": "x" * 301}, headers=h).status_code == 413


def test_sessions_are_isolated(client):
    a, b = _session(client), _session(client)
    client.post("/api/memo", json={"text": "only in session A"}, headers=a)
    memos_a = [t["memo"] for t in client.get("/api/transactions", headers=a).json()["transactions"]]
    memos_b = [t["memo"] for t in client.get("/api/transactions", headers=b).json()["transactions"]]
    assert "only in session A" in memos_a and "only in session A" not in memos_b
    assert client.get("/api/transactions", headers={"X-Session": "nope"}).status_code == 404


def test_plain_path_never_calls_a_model(client, monkeypatch):
    monkeypatch.setattr(demo_app, "get_model", lambda: _NoModel())
    monkeypatch.setattr(demo_app, "run_turn", lambda *a, **k: pytest.fail("run_turn called"))
    r = client.get("/api/transactions", headers=_session(client))
    assert r.status_code == 200 and r.json()["ai_used"] is False


def test_fake_model_is_flagged(client):
    h = _session(client)
    client.post("/api/memo", json={"text": "hello", "sample": None}, headers=h)
    r = client.post("/api/summarize", json={"defenses": True}, headers=h).json()
    assert r["fake_model"] is True and r["mode"] == "fake"


def test_results_and_replays_come_from_files(client):
    res = client.get("/api/results").json()
    assert [t["config"] for t in res["final"]] == ["off", "policy", "policy+risk", "policy+risk+filter"]
    reps = client.get("/api/replays").json()
    assert len(reps) == 4
    assert all(r["label"].startswith("recorded real run: ") for r in reps)
    assert {r["verdict"] for r in reps if r["config"] == "off"} == {"ATTACK SUCCEEDED"}
    assert {r["verdict"] for r in reps if r["config"] != "off"} == {"BLOCKED"}
    assert all(r["blocks"] for r in reps if r["config"] != "off")


def test_samples_are_the_chosen_dev_attacks(client):
    samples = client.get("/api/samples").json()
    assert [x["source"] for x in samples] == ["AT-D2", "UT-D2", "UT-D3", "MI-D1"]
    memo = samples[-1]
    assert memo["kind"] == "memo" and "Nano usually resists this one" in memo["note"]
    assert all(x["kind"] == "chat" and x["turns"] for x in samples[:3])


def test_chat_sample_runs_and_off_verdict_wording(client):
    h = _session(client)
    r = client.post("/api/attack", json={"sample": "split_payments", "defenses": False}, headers=h).json()
    assert r["fake_model"] is True and len(r["turns"]) == 4
    assert r["verdict"] in ("ATTACK SUCCEEDED", "ATTACK DID NOT SUCCEED (no defenses were on)")
    assert client.post("/api/attack", json={"sample": "memo_injection"}, headers=h).status_code == 404


# ---- reset, verdicts, blocks, empty replies, session recovery, captions, dev footnote ----
import json
import shutil
import subprocess

from bank.state import Bank


def test_reset_restores_a_fresh_bank(client):
    h = _session(client)
    client.post("/api/memo", json={"text": "planted"}, headers=h)
    client.post("/api/attack", json={"sample": "split_payments", "defenses": False}, headers=h)
    r = client.post("/api/reset", headers=h).json()
    sess = client.app.state.sessions.items[h["X-Session"]]
    assert sess["bank"].data == Bank("C-1").data and sess["planted"] == 0
    assert r["state"]["balances"]["A-1001"] == 2500.0
    assert [p["name"] for p in r["state"]["payees"].values()] == ["Landlord Demo"]
    assert 'Mock bank reset: A-1001 balance ' in PAGE


def test_verdict_wording():
    v, blk = demo_app.verdict, [{"layer": "policy", "tool": "transfer", "reason": "x"}]
    assert v(True, True, True, blk) == "ATTACK SUCCEEDED"
    assert v(False, True, True, blk) == "BLOCKED"
    assert v(False, True, True, []) == "ATTACK DID NOT SUCCEED (defenses on; nothing needed blocking)"
    assert v(False, True, False, []) == "ATTACK DID NOT SUCCEED (no defenses were on)"
    assert v(False, False, True, []) == "NO ATTACK PLANTED"


def test_blocks_carry_layer_and_reason():
    log = demo_app._brief_log([
        {"name": "transfer", "allowed": False, "result": json.dumps({"status": "blocked", "detail": "not asked by the user"})},
        {"name": "transfer", "allowed": False, "result": json.dumps({"status": "held", "detail": "risk score 60"})},
        {"name": "add_payee", "allowed": False, "result": json.dumps({"status": "pending_confirmation", "detail": "x"})},
        {"name": "get_balance", "allowed": True, "result": "{}"}])
    blocks = demo_app._blocks(log, [{"event": "output_withheld", "secrets_found": 1}])
    assert [(b["layer"], b["reason"]) for b in blocks] == [
        ("policy", "not asked by the user"), ("risk layer", "risk score 60"),
        ("policy (confirmation)", "waiting for the customer's explicit yes; not executed"),
        ("output filter", "reply withheld: it contained 1 secret(s)")]


def test_defended_run_with_a_block_says_blocked(client):
    h = _session(client)
    r = client.post("/api/attack", json={"sample": "split_payments", "defenses": True}, headers=h).json()
    assert r["blocks"] and r["verdict"] == "BLOCKED"
    assert all(b["reason"] for b in r["blocks"])


def test_empty_reply_message_in_page():
    assert "(empty reply)" not in PAGE
    assert "The model returned an empty reply (known Nemotron behaviour" in PAGE


def test_unknown_or_evicted_session_is_reported_as_expired():
    app = demo_app.create_app()
    app.state.sessions.limit = 1
    c = TestClient(app)
    first = _session(c)
    _session(c)                                   # evicts the first
    for h in (first, {"X-Session": "never-existed"}):
        r = c.get("/api/transactions", headers=h)
        assert r.status_code == 404 and r.json()["detail"] == demo_app.SESSION_EXPIRED


NODE = shutil.which("node")


def _run_page_api(responses):
    """Run the page's api() (between the api:start/api:end markers) in node with a stub fetch."""
    code = PAGE.split("// --- api:start")[1].split("\n", 1)[1].split("// --- api:end")[0]
    script = """
var S = {session: "old"}, calls = [], notices = [];
var queue = %s;
function sessionNotice(t) { notices.push(t); }
function fetch(url, o) {
  calls.push([url, o.headers["X-Session"] || null]);
  var r = queue.shift();
  return Promise.resolve({ok: r[0] < 400, status: r[0], json: function () { return Promise.resolve(r[1]); }});
}
%s
api("transactions").then(function (j) { console.log(JSON.stringify({ok: j, calls: calls, notices: notices, session: S.session})); },
  function (e) { console.log(JSON.stringify({err: e.message, calls: calls, notices: notices})); });
""" % (json.dumps(responses), code)
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_page_recovers_lost_session_and_retries_once():
    expired = [404, {"detail": "session_expired"}]
    r = _run_page_api([expired, [200, {"session": "new"}], [200, {"transactions": []}]])
    assert r["ok"] == {"transactions": []} and r["session"] == "new"
    assert [c[0] for c in r["calls"]] == ["api/transactions", "api/session", "api/transactions"]
    assert r["calls"][2][1] == "new" and len(r["notices"]) == 1
    # Only one retry: a second expiry is an error, not a loop.
    r = _run_page_api([expired, [200, {"session": "new"}], expired])
    assert r["err"] == "session_expired" and len(r["calls"]) == 3


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_page_does_not_retry_other_errors():
    r = _run_page_api([[429, {"detail": "Too many requests"}]])
    assert r["err"] == "Too many requests" and len(r["calls"]) == 1


def test_replay_captions_count_runs_from_raw_logs():
    for rep in demo_app.load_replays():
        f = demo_app.FINAL / rep["label"].split(": ", 1)[1].split(", ")[0]
        same = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]
        same = [r for r in same if r.get("kind") == "attack" and r["id"] == rep["id"]]
        wins = sum(r["score"]["success"] for r in same)
        assert rep["caption"].startswith(f"{rep['id']}: succeeded in {wins} of {len(same)} ")
        assert rep["verdict"] != "ATTACK SUCCEEDED" or "this is one of them" in rep["caption"]


def test_dev_off_row_uses_post_fix_benign_run():
    off = next(t for t in demo_app.load_results()["dev"] if t["config"] == "off")
    total = next(r for r in off["rows"] if r[0] == "**total**")
    assert total[5] == "0/45 = 0% *" and demo_app.DEV_OFF_BENIGN in off["footnote"]
    assert "3/45" in off["footnote"]
