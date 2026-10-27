"""Load and validate attack and benign task files."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SPLITS = {"dev": DATA / "attacks_dev.json", "test": DATA / "attacks_test.json"}
BENIGN = DATA / "benign.json"


def _load(path, required):
    path = Path(path)
    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise ValueError(f"{path}: expected a JSON list")
    ids = set()
    for it in items:
        missing = [k for k in required if k not in it]
        if missing:
            raise ValueError(f"{path}: item {it.get('id')!r} missing {missing}")
        if not it["turns"] or not all(isinstance(t, str) for t in it["turns"]):
            raise ValueError(f"{path}: item {it['id']!r} needs a non-empty list of string turns")
        if it["id"] in ids:
            raise ValueError(f"{path}: duplicate id {it['id']!r}")
        ids.add(it["id"])
    return items


def load_attacks(path):
    return _load(path, ("id", "category", "turns", "success"))


def load_benign(path):
    return _load(path, ("id", "turns", "expect"))
