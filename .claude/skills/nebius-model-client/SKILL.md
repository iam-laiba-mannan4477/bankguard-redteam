---
name: nebius-model-client
description: Build or debug the model interface, FakeModel, and NebiusModel client for Nemotron on Nebius Token Factory, including tool calling and reasoning-field handling. Use when working in agent/ or when a model call fails.
---

# Model client

## Interface (agent/models.py)
One method: `chat(messages, tools) -> AssistantMessage` where AssistantMessage has `content`,
`tool_calls` (list of id, name, arguments dict) and `usage`. The assistant loop does not know which
model it talks to.

## FakeModel
Deterministic and gullible on purpose: it follows instructions found in user text and in tool-result
text (memos), so the undefended baseline shows attacks succeeding. Used only to test the pipeline
and to let work continue when Token Factory access is blocked. Its numbers are never results.

## NebiusModel
- `openai.OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/", api_key=os.environ["NEBIUS_API_KEY"])`
- Model ID from env: `MODEL_NANO`, `MODEL_SUPER`, `MODEL_ULTRA`. Fail with a clear message if unset.
- Load env with python-dotenv. Never print the key or the full request headers.
- Tool calling: pass `tools=[...]`, `tool_choice="auto"`. When the model returns tool calls, append the
  assistant message with its `tool_calls`, then one `{"role":"tool","tool_call_id":...,"content":...}`
  message per call, then call again. Cap at 6 tool rounds per turn.
- Reasoning models: `message.content` can be empty while text is in an extra field (inspect
  `message.model_extra`). Use a generous `max_tokens` (1500 or more), and if `content` is empty after
  tool rounds, retry once with a higher limit. Record every occurrence in `docs/FEEDBACK_NOTES.md`.
- Retries: on 429 or 5xx, exponential backoff up to 3 tries. On 401/402/403 stop and surface the
  exact message to the owner (credits or billing problem), do not loop.
- Track tokens and latency per call. Cost table uses prices read from the Token Factory console,
  typed into `bench/prices.json` by the owner. Do not invent prices.

## Rules
- All NVIDIA model calls go to Nebius. No other provider, per the hackathon rules.
- Routing for the demo: Nano for the assistant and safety check, escalate to Super only if a
  structured check returns low confidence. Keep routing logic small and measurable.
