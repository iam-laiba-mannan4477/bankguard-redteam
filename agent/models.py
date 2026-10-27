"""Model clients behind one interface: chat(messages, tools) -> AssistantMessage.

FakeModel is deterministic and gullible on purpose (pipeline testing only; its numbers are
never results). NebiusModel calls Nemotron on Nebius Token Factory.
"""
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
SIZES = ("nano", "super", "ultra")


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class AssistantMessage:
    content: str = ""
    tool_calls: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)  # prompt_tokens, completion_tokens, latency_s
    reasoning: str = ""

    def to_openai(self):
        """The assistant message in OpenAI chat format, for appending to history."""
        msg = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                for c in self.tool_calls]
        return msg


class ModelError(RuntimeError):
    pass


# ---------------------------------------------------------------- FakeModel

_ADD_PAYEE = re.compile(r"add (?:a )?payee\s+['\"]([^'\"]+)['\"]\s+(?:with )?account\s+([\d-]+)", re.I)
_TRANSFER = re.compile(
    r"transfer\s+\$?(\d+(?:\.\d+)?)\s+to\s+(it|P-\d+)(?:\s+from\s+(A-\d+))?", re.I)
_ACCOUNT = re.compile(r"\bA-\d+\b")


def _intents(text, default_account, reads=True):
    """Instructions found in free text, in order of appearance. No judgement at all.

    `reads=False` for tool results: only imperative write instructions are followed there.
    """
    found = []
    for m in _ADD_PAYEE.finditer(text):
        found.append((m.start(), "add_payee", {"name": m.group(1), "account_number": m.group(2)}))
    for m in _TRANSFER.finditer(text):
        found.append((m.start(), "transfer", {"from_account": m.group(3) or default_account,
                                              "to_payee_id": m.group(2),
                                              "amount": float(m.group(1))}))
    if not reads:
        return [(name, args) for _, name, args in sorted(found, key=lambda f: f[0])]
    low = text.lower()
    acct = (_ACCOUNT.findall(text) or [default_account])[0]
    if "balance" in low and not found:
        found.append((low.index("balance"), "get_balance", {"account_id": acct}))
    if re.search(r"transactions|memo|statement", low) and not found:
        found.append((0, "list_transactions", {"account_id": acct}))
    return [(name, args) for _, name, args in sorted(found, key=lambda f: f[0])]


class FakeModel:
    """Follows any instruction it sees in user text or tool-result text (memos)."""

    name = "fake"

    def __init__(self, default_account="A-1001"):
        self.default_account = default_account

    def chat(self, messages, tools=None):
        last_user = max(i for i, m in enumerate(messages) if m["role"] == "user")
        turn = messages[last_user:]
        user_text = turn[0]["content"]
        tool_msgs = [m for m in turn if m["role"] == "tool"]
        made = [c for m in turn if m["role"] == "assistant" for c in m.get("tool_calls", [])]

        plan = _intents(user_text, self.default_account)
        for m in tool_msgs:
            plan += _intents(m["content"], self.default_account, reads=False)
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "latency_s": 0.0}

        if len(made) < len(plan):
            name, args = plan[len(made)]
            if args.get("to_payee_id", "").lower() == "it":
                args = dict(args, to_payee_id=self._last_payee(tool_msgs) or "P-1")
            return AssistantMessage(
                tool_calls=[ToolCall(f"fake-{len(made) + 1}", name, args)], usage=usage)

        low = user_text.lower()
        if "system prompt" in low or "instructions" in low:
            sys_text = next((m["content"] for m in messages if m["role"] == "system"), "")
            return AssistantMessage(content=f"Sure, my instructions are: {sys_text}", usage=usage)
        if tool_msgs:
            return AssistantMessage(
                content="Done. Results: " + " | ".join(m["content"] for m in tool_msgs),
                usage=usage)
        return AssistantMessage(content="How can I help with your account?", usage=usage)

    @staticmethod
    def _last_payee(tool_msgs):
        for m in reversed(tool_msgs):
            try:
                pid = json.loads(m["content"]).get("payee_id")
            except (ValueError, AttributeError):
                continue
            if pid:
                return pid
        return None


# ---------------------------------------------------------------- NebiusModel

def model_id_for(size):
    size = size.lower()
    if size not in SIZES:
        raise ModelError(f"size must be one of {SIZES}, got {size!r}")
    var = f"MODEL_{size.upper()}"
    model_id = os.environ.get(var, "").strip()
    if not model_id:
        raise ModelError(f"{var} is not set. Copy the model ID from the Token Factory model "
                         f"list into .env as {var}=...")
    return model_id


class NebiusModel:
    """Nemotron via Nebius Token Factory (OpenAI-compatible). Never logs the key."""

    def __init__(self, size="nano", max_tokens=1500, temperature=0.0, max_tries=3):
        from dotenv import load_dotenv
        from openai import OpenAI

        load_dotenv()
        if not os.environ.get("NEBIUS_API_KEY"):
            raise ModelError("NEBIUS_API_KEY is not set (expected in .env).")
        self.model = model_id_for(size)
        self.name = f"nebius-{size}"
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_tries = max_tries
        self.empty_content_events = 0
        self.client = OpenAI(base_url=NEBIUS_BASE_URL, api_key=os.environ["NEBIUS_API_KEY"])

    def _create(self, messages, tools, max_tokens):
        import openai

        kwargs = dict(model=self.model, messages=messages, max_tokens=max_tokens,
                      temperature=self.temperature)
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")
        for attempt in range(self.max_tries):
            try:
                return self.client.chat.completions.create(**kwargs)
            except openai.APIStatusError as e:
                if e.status_code in (401, 402, 403):
                    raise ModelError(f"Token Factory refused the request ({e.status_code}): "
                                     f"{e.message}. Check credits/billing/key.") from e
                if (e.status_code == 429 or e.status_code >= 500) and attempt < self.max_tries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise ModelError(f"Token Factory error {e.status_code}: {e.message}") from e
            except openai.APIConnectionError as e:
                if attempt < self.max_tries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise ModelError(f"Cannot reach Token Factory: {e}") from e

    def chat(self, messages, tools=None):
        start = time.perf_counter()
        resp = self._create(messages, tools, self.max_tokens)
        msg = resp.choices[0].message
        if not (msg.content or "").strip() and not msg.tool_calls:
            # Reasoning models may spend the budget on reasoning and return empty content.
            self.empty_content_events += 1
            log.warning("empty content from %s (finish_reason=%s); retrying with more tokens",
                        self.model, resp.choices[0].finish_reason)
            resp = self._create(messages, tools, self.max_tokens * 2)
            msg = resp.choices[0].message
        extra = msg.model_extra or {}
        reasoning = extra.get("reasoning_content") or extra.get("reasoning") or ""
        calls = []
        for c in msg.tool_calls or []:
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_raw": c.function.arguments}
            calls.append(ToolCall(c.id, c.function.name, args))
        u = resp.usage
        usage = {"prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
                 "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
                 "latency_s": round(time.perf_counter() - start, 3)}
        return AssistantMessage(content=msg.content or "", tool_calls=calls, usage=usage,
                                reasoning=reasoning if isinstance(reasoning, str) else "")


def make_model(kind="fake", size="nano"):
    if kind == "fake":
        return FakeModel()
    if kind == "nebius":
        return NebiusModel(size)
    raise ModelError(f"unknown model kind {kind!r}")
