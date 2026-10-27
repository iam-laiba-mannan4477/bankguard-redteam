import argparse
import json

import pytest

from bench import run_benchmark as rb


def _args(**kw):
    d = dict(model="fake", size="nano", split="dev", runs=1, defenses="off", force=False)
    d.update(kw)
    return argparse.Namespace(**d)


def test_fake_never_writes_to_final():
    with pytest.raises(SystemExit, match="final"):
        rb.output_dir(_args(split="test"))


def test_dev_goes_to_results():
    assert rb.output_dir(_args()) == rb.RESULTS


def test_test_split_refused_if_config_already_final(tmp_path, monkeypatch):
    monkeypatch.setattr(rb, "FINAL", tmp_path)
    a = _args(model="nebius", split="test", runs=3)
    assert rb.output_dir(a) == tmp_path
    (tmp_path / f"20261029-120000_{rb.config_name(a)}.jsonl").write_text("{}")
    with pytest.raises(SystemExit, match="once per configuration"):
        rb.output_dir(a)
    assert rb.output_dir(_args(model="nebius", split="test", runs=3, force=True)) == tmp_path


def test_end_to_end_fake_on_fixture(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(rb, "RESULTS", tmp_path)
    rb.main(["--model", "fake", "--attacks", "tests/fixtures/one_attack.json",
             "--benign", "tests/fixtures/one_benign.json"])
    out = capsys.readouterr().out
    assert "PIPELINE TEST ONLY" in out and "1/1 = 100%" in out
    assert len(list(tmp_path.glob("*.jsonl"))) == 1 and len(list(tmp_path.glob("*.md"))) == 1


def test_unknown_defense_config_refused():
    with pytest.raises(SystemExit):
        rb.main(["--model", "fake", "--defenses", "all"])


def test_seed_memo_comes_only_from_setup():
    item = json.loads(open("tests/fixtures/one_attack.json", encoding="utf-8").read())[0]
    bank, before, *_ = rb.run_item(rb.make_model("fake"), item)
    assert "unauthorized_payee" in rb.score_attack(before, bank.snapshot(), [], [], item)["rules"]
    clean = dict(item, setup={})
    bank, before, outputs, tool_log, *_ = rb.run_item(rb.make_model("fake"), clean)
    assert not rb.score_attack(before, bank.snapshot(), outputs, tool_log, clean)["success"]
