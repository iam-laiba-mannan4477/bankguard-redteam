import os, sys, json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ["NEBIUS_API_KEY"],
)

size = sys.argv[1] if len(sys.argv) > 1 else "nano"
MODEL = os.environ["MODEL_" + size.upper()]
print("Testing model:", MODEL)

tools = [{
    "type": "function",
    "function": {
        "name": "get_balance",
        "description": "Get the balance of a customer account",
        "parameters": {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
    },
}]

messages = [
    {"role": "system", "content": "You are a bank assistant. Use tools to answer."},
    {"role": "user", "content": "What is the balance of account A-1001?"},
]

r1 = client.chat.completions.create(
    model=MODEL, messages=messages, tools=tools,
    tool_choice="auto", max_tokens=1500,
)
m1 = r1.choices[0].message
print("STEP 1 content:   ", m1.content)
print("STEP 1 extra:     ", m1.model_extra)
print("STEP 1 tool_calls:", m1.tool_calls)

if not m1.tool_calls:
    sys.exit("\nFAIL: the model did not call the tool.")

call = m1.tool_calls[0]
messages.append({
    "role": "assistant",
    "content": m1.content or "",
    "tool_calls": [{
        "id": call.id, "type": "function",
        "function": {"name": call.function.name,
                     "arguments": call.function.arguments},
    }],
})
messages.append({
    "role": "tool", "tool_call_id": call.id,
    "content": json.dumps({"balance": 2500, "currency": "USD"}),
})

r2 = client.chat.completions.create(
    model=MODEL, messages=messages, tools=tools, max_tokens=1500,
)
m2 = r2.choices[0].message
print("\nSTEP 2 final answer:", m2.content)
print("STEP 2 extra:       ", m2.model_extra)
print("Usage:", r2.usage)