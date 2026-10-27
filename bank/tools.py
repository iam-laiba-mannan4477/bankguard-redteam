"""OpenAI-style tool schemas for the four bank tools, and an executor."""
import json

from bank.state import Bank, BankError

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_balance",
        "description": "Get the balance of one of the customer's accounts.",
        "parameters": {"type": "object", "properties": {
            "account_id": {"type": "string", "description": "Account ID, e.g. A-1001"}},
            "required": ["account_id"]}}},
    {"type": "function", "function": {
        "name": "list_transactions",
        "description": "List recent transactions (with memo text) for an account.",
        "parameters": {"type": "object", "properties": {
            "account_id": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "default": 10}},
            "required": ["account_id"]}}},
    {"type": "function", "function": {
        "name": "transfer",
        "description": "Transfer money from an account to a saved payee.",
        "parameters": {"type": "object", "properties": {
            "from_account": {"type": "string"},
            "to_payee_id": {"type": "string", "description": "Payee ID, e.g. P-1"},
            "amount": {"type": "number", "exclusiveMinimum": 0}},
            "required": ["from_account", "to_payee_id", "amount"]}}},
    {"type": "function", "function": {
        "name": "add_payee",
        "description": "Add a new saved payee for the customer.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"},
            "account_number": {"type": "string"}},
            "required": ["name", "account_number"]}}},
]

TOOL_NAMES = {t["function"]["name"] for t in TOOL_SCHEMAS}


def execute_tool(bank: Bank, name, arguments, confirmed=False):
    """Run a tool call from the model. Returns a JSON string (results and errors alike).

    `confirmed` comes only from the defense layer; any `confirmed` the model passes is dropped.
    """
    if name not in TOOL_NAMES:
        return json.dumps({"error": f"unknown tool {name!r}"})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"invalid JSON arguments: {e}"})
    if not isinstance(arguments, dict):
        return json.dumps({"error": "arguments must be an object"})
    args = {k: v for k, v in arguments.items() if k != "confirmed"}
    if name == "transfer":
        args["confirmed"] = confirmed
    try:
        return json.dumps(getattr(bank, name)(**args))
    except TypeError as e:
        return json.dumps({"error": f"bad arguments: {e}"})
    except BankError as e:
        return json.dumps({"error": str(e)})
