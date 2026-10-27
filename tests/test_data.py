import re
from collections import Counter

import pytest

from attacks.loader import BENIGN, SPLITS, load_attacks, load_benign

CATEGORIES = {"account_takeover", "unauthorized_transfer", "data_leakage", "memo_injection"}
BENIGN_CHECKS = {"answer_contains", "transfer_completed", "no_state_change", "payee_added",
                 "balance_delta"}
R1_CATEGORIES = {"unauthorized_transfer", "account_takeover"}
ACCOUNT_NUMBER = re.compile(r"\b\d{2}-\d{4}-\d{4}\b")


def _account_numbers(items):
    nums = set()
    for a in items:
        text = " ".join(a["turns"]) + (a.get("setup") or {}).get("seed_memo", "")
        nums |= set(ACCOUNT_NUMBER.findall(text))
    return nums


@pytest.fixture(scope="module")
def dev():
    return load_attacks(SPLITS["dev"])


@pytest.fixture(scope="module")
def test_split():
    return load_attacks(SPLITS["test"])


@pytest.fixture(scope="module")
def benign():
    return load_benign(BENIGN)


def test_counts_and_balance(dev, test_split, benign):
    assert Counter(a["category"] for a in dev) == {c: 3 for c in CATEGORIES}
    assert Counter(a["category"] for a in test_split) == {c: 2 for c in CATEGORIES}
    assert len(benign) == 15


def test_ids_unique_across_files(dev, test_split, benign):
    ids = [x["id"] for x in dev + test_split + benign]
    assert len(ids) == len(set(ids))


def test_seed_memo_only_for_memo_injection(dev, test_split, benign):
    for a in dev + test_split:
        has_memo = bool((a.get("setup") or {}).get("seed_memo"))
        assert has_memo == (a["category"] == "memo_injection"), a["id"]
    for b in benign:
        assert not (b.get("setup") or {}).get("seed_memo"), b["id"]


def test_every_attack_is_checkable(dev, test_split):
    for a in dev + test_split:
        s = a["success"]
        assert s["type"] in ("state_change", "canary_leak", "both"), a["id"]
        if s["type"] in ("state_change", "both"):
            # Either R4 (marked payee) or R1 (transfer to a new payee / out of a foreign account).
            assert s.get("unauthorized_payees") or a["category"] in R1_CATEGORIES, a["id"]
        if s["type"] in ("canary_leak", "both"):
            text = " ".join(a["turns"]) + (a.get("setup") or {}).get("seed_memo", "")
            reachable = any(acct in text for acct in ("A-2001", "A-3001")) or any(
                w in text.lower() for w in ("instructions", "system prompt", "reference code"))
            assert reachable, f"{a['id']}: no reachable canary (A-2001/A-3001 memo or system prompt)"
        for p in s.get("unauthorized_payees", []):
            assert p.get("name") or p.get("account_number"), a["id"]
        def keys(p):
            p = p if isinstance(p, dict) else {"name": p}
            return {v.lower() for v in (p.get("name"), p.get("account_number")) if v}
        authorized = set().union(*map(keys, s.get("authorized_new_payees", [])))
        marked = set().union(*map(keys, s.get("unauthorized_payees", [])))
        assert not authorized & marked, a["id"]


def test_benign_tasks_have_known_checks(benign):
    for b in benign:
        assert b["expect"], b["id"]
        assert {c["type"] for c in b["expect"]} <= BENIGN_CHECKS, b["id"]


def test_dev_and_test_account_numbers_disjoint(dev, test_split):
    assert not _account_numbers(dev) & _account_numbers(test_split)


# attacks_test.json is frozen (see data/README.md). Do not update this hash to make a test pass.
TEST_SPLIT_SHA256 = "858f349c1db7374f34970dfd8833e38581de829b78e9de85b230256673acfb45"


def test_test_split_is_frozen():
    import hashlib
    import json
    data = json.loads(SPLITS["test"].read_text(encoding="utf-8"))
    canon = json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    assert hashlib.sha256(canon).hexdigest() == TEST_SPLIT_SHA256, \
        "data/attacks_test.json changed. It is frozen: revert the edit."
