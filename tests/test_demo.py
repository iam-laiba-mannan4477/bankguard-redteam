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
