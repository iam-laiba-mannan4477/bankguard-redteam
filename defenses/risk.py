"""Layer 2: transaction risk score and cooling-off. Deterministic.

Cooling-off: a transfer to a payee added in this session is always held.
Otherwise points are added up and the transfer is held at or above the threshold.
"""

def score_transfer(bank, args, added_this_session, attempts_this_session, session_hour):
    """Return (score, reasons, cooling_off)."""
    pid, acct = args.get("to_payee_id"), args.get("from_account")
    amount = float(args.get("amount", 0))
    score, reasons = 0, []
    cooling_off = pid in added_this_session
    if cooling_off:
        score += 50
        reasons.append("payee was added in this session (cooling-off)")
    balance = bank.data["accounts"].get(acct, {}).get("balance", 0) or 0
    if balance and amount / balance >= 0.8:
        score += 40
        reasons.append("amount is 80% or more of the balance")
    elif balance and amount / balance >= 0.5:
        score += 25
        reasons.append("amount is 50% or more of the balance")
    outgoing = [-t["amount"] for t in bank.data["transactions"].get(acct, []) if t["amount"] < 0]
    if outgoing and amount > 2 * max(outgoing):
        score += 20
        reasons.append("amount is more than twice the largest past payment")
    if 0 <= session_hour < 6:
        score += 20
        reasons.append("unusual time (00:00-06:00)")
    if attempts_this_session >= 3:
        score += 20
        reasons.append("many transfer attempts in this session")
    return score, reasons, cooling_off


def should_hold(score, cooling_off, threshold):
    return cooling_off or score >= threshold
