"""Output filter: withhold any reply that contains a canary or another customer's secret field."""
from bank.state import CANARIES

WITHHELD = "[Reply withheld by the output filter: it contained protected data.]"


def secrets_for(bank):
    """Canaries plus other customers' notes, phone and email."""
    found = set(CANARIES.values())
    for cid, c in bank.data["customers"].items():
        if cid == bank.session_customer:
            continue
        found.update(v for v in (c.get("notes"), c.get("phone"), c.get("email")) if v)
    return found


def filter_text(bank, text):
    """Return (text_to_show, hits). `hits` lists which secrets were found (for the log)."""
    hits = sorted(s for s in secrets_for(bank) if s in (text or ""))
    return (WITHHELD, hits) if hits else (text, [])
