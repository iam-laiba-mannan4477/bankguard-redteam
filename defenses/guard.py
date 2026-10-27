"""Per-conversation guard: wires the enabled layers into the assistant loop.

The harness (this class), not the model, owns confirmation: a write that passes the policy
becomes `pending`, the harness appends its own confirmation question to the reply, and the
action runs only if the user's NEXT message is an explicit yes. Anything else cancels it.
"""
import json

from bank.tools import execute_tool
from defenses import output_filter, policy, risk
from defenses.config import CONFIGS, DefenseConfig


def _args(arguments):
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except ValueError:
            return {}
    return arguments if isinstance(arguments, dict) else {}


def _describe(name, args):
    if name == "transfer":
        return (f"transfer {float(args.get('amount', 0)):,.2f} from {args.get('from_account')} "
                f"to payee {args.get('to_payee_id')}")
    return f"add payee '{args.get('name')}' with account {args.get('account_number')}"


class Guard:
    def __init__(self, bank, config="off"):
        self.bank = bank
        self.cfg = CONFIGS[config] if isinstance(config, str) else (config or DefenseConfig())
        self.pending = None           # {"name", "args"} awaiting the user's yes
        self.user_text = ""
        self.added_payees = set()     # payee IDs added in this session
        self.transferred = 0.0
        self.transfer_attempts = 0
        self.events = []              # every block / hold / confirmation / redaction, for the log
        self._turn_notes = []
        self._done_this_turn = set()

    @property
    def active(self):
        return self.cfg.policy or self.cfg.risk or self.cfg.filter

    # ---- system prompt ----
    def system_prompt_suffix(self):
        return policy.SYSTEM_PROMPT_ADDITION if self.cfg.policy else ""

    # ---- turn start: resolve a pending action from the user's own message ----
    def start_turn(self, user_text):
        """Returns (note_for_model or None, tool_log entries for actions the harness executed)."""
        self.user_text = user_text or ""
        self._turn_notes, self._done_this_turn = [], set()
        if not self.pending:
            return None, []
        pending, self.pending = self.pending, None
        desc = _describe(pending["name"], pending["args"])
        if not policy.is_explicit_yes(self.user_text):
            self.events.append({"event": "confirmation_cancelled", "action": desc})
            return f"Bank system: the customer did not confirm, so this was cancelled: {desc}.", []
        result = execute_tool(self.bank, pending["name"], pending["args"], confirmed=True)
        self.after_execute(pending["name"], pending["args"], result)
        self._done_this_turn.add(pending["name"])
        self.events.append({"event": "confirmed_by_user", "action": desc, "result": result})
        entry = {"round": 0, "name": pending["name"], "arguments": pending["args"],
                 "allowed": True, "result": result, "executed_by": "harness_after_user_yes"}
        return (f"Bank system: the customer explicitly confirmed and the bank executed: {desc}. "
                f"Result: {result}. Do not repeat this action."), [entry]

    # ---- each tool call ----
    def check(self, name, arguments):
        """Return (execute: bool, result_if_not_executed: str|None, confirmed: bool)."""
        args = _args(arguments)
        is_write = name in policy.WRITE_TOOLS
        if self.cfg.policy:
            if is_write and name in self._done_this_turn:
                return self._stop(name, args, "blocked", "already executed after the customer's "
                                                         "confirmation this turn")
            reason = policy.check_call(self.bank, name, args, self.user_text, self.transferred)
            if reason:
                return self._stop(name, args, "blocked", reason)
        if name == "transfer" and self.cfg.risk:
            self.transfer_attempts += 1
            score, reasons, cooling = risk.score_transfer(
                self.bank, args, self.added_payees, self.transfer_attempts, self.cfg.session_hour)
            if risk.should_hold(score, cooling, self.cfg.risk_threshold):
                self._turn_notes.append(f"Held by the bank for review (risk score {score}): "
                                        f"{_describe(name, args)}. Reasons: {'; '.join(reasons)}.")
                return self._stop(name, args, "held", f"risk score {score}: {'; '.join(reasons)}")
        if self.cfg.policy and is_write:
            if self.pending:
                return self._stop(name, args, "blocked", "another action is already waiting "
                                                         "for the customer's confirmation")
            self.pending = {"name": name, "args": args}
            desc = _describe(name, args)
            self._turn_notes.append(f"Please confirm: {desc}. Reply \"yes\" to go ahead; "
                                    "anything else cancels it.")
            self.events.append({"event": "confirmation_requested", "action": desc})
            return False, json.dumps({"status": "pending_confirmation", "detail":
                                      "The bank will ask the customer directly. Do not claim it "
                                      "is done."}), False
        return True, None, False

    def _stop(self, name, args, status, reason):
        self.events.append({"event": status, "tool": name, "arguments": args, "reason": reason})
        return False, json.dumps({"status": status, "detail": reason}), False

    def after_execute(self, name, arguments, result):
        try:
            data = json.loads(result)
        except ValueError:
            return
        if data.get("status") != "ok":
            return
        if name == "add_payee":
            self.added_payees.add(data.get("payee_id"))
        elif name == "transfer":
            self.transferred += float(_args(arguments).get("amount", 0))

    def wrap_result(self, name, result):
        return policy.wrap_untrusted(name, result) if self.cfg.policy else result

    # ---- output ----
    def filter(self, text):
        if not self.cfg.filter or not text:
            return text
        shown, hits = output_filter.filter_text(self.bank, text)
        if hits:
            self.events.append({"event": "output_withheld", "secrets_found": len(hits)})
        return shown

    def harness_message(self):
        """Text the harness itself adds to the reply (confirmation questions, hold notices)."""
        return "\n".join(self._turn_notes)
