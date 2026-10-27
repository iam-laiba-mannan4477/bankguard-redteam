"""One benign request through the assistant loop with NebiusModel (MODEL_NANO). Uses the network.

Run: python real_smoke_test.py
"""
import sys

from agent.assistant import run_turn
from agent.console import use_utf8_stdout
from agent.models import ModelError, NebiusModel
from bank.state import Bank


def main():
    use_utf8_stdout()
    try:
        model = NebiusModel("nano")  # loads .env via python-dotenv
    except ModelError as e:
        sys.exit(f"Setup error: {e}")
    print("Model:", model.model)
    try:
        out = run_turn(model, Bank("C-1"), "What is my balance?")
    except ModelError as e:
        sys.exit(f"Model call failed: {e}")
    for c in out["tool_log"]:
        print(f"tool round {c['round']}: {c['name']}({c['arguments']}) -> {c['result']}")
    print("\nFinal answer:", out["final"] or "(empty)")
    print("Usage:", out["usage"], "| rounds:", out["rounds"], "| capped:", out["capped"])
    if model.empty_content_events:
        print(f"Note: {model.empty_content_events} empty-content response(s); "
              "log this in docs/FEEDBACK_NOTES.md")


if __name__ == "__main__":
    main()
