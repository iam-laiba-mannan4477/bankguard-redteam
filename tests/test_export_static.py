import json
import re

import pytest

import demo.export_static as ex


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    path = ex.export(tmp_path_factory.mktemp("site"))
    html = path.read_text(encoding="utf-8")
    raw = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1)
    return html, json.loads(raw)


def test_export_makes_no_network_calls_and_loads_nothing_external(built):
    html, _ = built
    assert not re.search(r"\bfetch\(|XMLHttpRequest|WebSocket|sendBeacon|EventSource|import\(", html)
    assert not re.search(r"\b(src|href)\s*=", html)          # no external scripts, styles or images
    assert "<link" not in html


def test_export_has_all_four_configs_and_every_run(built):
    _, data = built
    assert data["configs"] == ["off", "policy", "policy+risk", "policy+risk+filter"]
    for cfg in data["configs"]:
        assert set(data["runs"][cfg]) == {a["id"] for a in data["attacks"]}
        assert all(set(e["runs"]) == {"1", "2", "3"} for e in data["runs"][cfg].values())
    assert [t["config"] for t in data["results"]["final"]] == data["configs"]
    assert any(t.get("footnote") for t in data["results"]["dev"])
    assert data["limits"]


def test_captions_match_raw_success_counts(built):
    _, data = built
    for path in ex.FINAL.glob("*.jsonl"):
        cfg = re.search(r"_def-(.+?)_runs", path.name).group(1)
        recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
        for aid, entry in data["runs"][cfg].items():
            wins = sum(r["score"]["success"] for r in recs if r.get("kind") == "attack" and r["id"] == aid)
            assert entry["caption"].startswith(f"{aid}: succeeded in {wins} of 3 ")


def test_blocked_only_when_something_stopped(built):
    _, data = built
    for cfg, by_id in data["runs"].items():
        for entry in by_id.values():
            for r in entry["runs"].values():
                if r["verdict"] == "BLOCKED":
                    assert cfg != "off" and r["blocks"]
                if cfg != "off" and not r["blocks"] and r["verdict"] != "ATTACK SUCCEEDED":
                    assert r["verdict"] == "ATTACK DID NOT SUCCEED (defenses on; nothing needed blocking)"


def test_recorded_text_is_escaped():
    evil = '</script><img src=x onerror="alert(1)"><script>alert(2)</script> &  '
    html = ex.render_page({"reply": evil})
    raw = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1)
    assert "<img" not in html and "alert(2)</script>" not in html
    assert json.loads(raw) == {"reply": evil}                 # still the exact text, as data
    assert not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write", ex.PAGE)


def test_build_fails_on_key_like_strings(monkeypatch):
    with pytest.raises(ex.SecretFound):
        ex.render_page({"reply": "here is sk-abcdefghijklmnopqrstuvwxyz123456"})
    monkeypatch.setenv("SOME_SERVICE_TOKEN", "value-that-must-not-leak-42")
    with pytest.raises(ex.SecretFound):
        ex.render_page({"reply": "oops value-that-must-not-leak-42"})


def test_banners_present(built):
    html, _ = built
    assert "MOCK BANK: synthetic data only. Results apply to this mock assistant." in html
    assert ("Hosted page = replay of recorded real runs (Nemotron Nano on Nebius Token Factory). "
            "The live demo runs locally: see the README (Setup and run).") in html
