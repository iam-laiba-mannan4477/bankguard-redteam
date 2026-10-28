# Feedback notes (Nebius Token Factory, AI Cloud, NVIDIA models)

Required hackathon feedback; also eligible for the Most Valuable Feedback prize.
Be specific: name the tool, say what you tried, what happened, what would help.

## 2026-10-21 to 2026-10-25: onboarding
- Applied to the Nebius Builder Program on Oct 21; got an "under review, up to two business days" email.
- Used the Devpost promo form with the activation code; promo code arrived by email.
- Token Factory onboarding shows a billing form with a mandatory card section. The Country of
  residence list does not include Pakistan, so billing cannot be completed and the promo code could
  not be applied from this screen. Docs say a promo code can be applied without billing details;
  the onboarding screen did not show that option. Docs also disagree about whether a card is required
  (one page says card required, another says it is not).
- Contacted Nebius via Contact us, Discord and the hackathon manager on Oct 25.

## Model and API notes
- Tool calling on Nano and Super: works (Oct 27 entry below); all benchmark results use Nano.
- Empty `content` with reasoning in extra fields: see Oct 27 entry below; in the full undefended
  baselines `message.content` was empty in 4 of 81 runs each (docs/LAB_NOTES.md, 2026-10-27).
- Safety/guard model availability: none in the list (Oct 26 entry below).
- Latency and cost: speed varied with no errors in the logs: mean 3.3 s per model call in run
  `20261027-210454`, 2.9 s in `20261027-234105`, 20.8 s in the partial `20261027-221939` (one
  UT-D1 run took 150.7 s). A full 81-run dev configuration cost $0.0329-$0.0377 (README dev table).
- Oct 26: no dedicated NVIDIA safety or guard model appears in the Token Factory model list (30 models)
- Oct 27: tool calling works on Nano (nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B) and Super (nvidia/nemotron-3-super-120b-a12b) via the OpenAI-compatible API, including a tool-result round trip.
- Reasoning models return content=None on tool-call turns; reasoning text is in message.model_extra['reasoning'] (Super also has 'reasoning_content').
- No dedicated NVIDIA guard/safety model in the 30-model list.
- Nano test: 471 tokens total. Super shows prompt cache hits (352 cached tokens).
- Oct 27: assistant-loop smoke test on Nano ("What is my balance?", 2 tool rounds, 3 calls):
  3,208 completion tokens vs 2,377 prompt tokens, 15.4 s total. Reasoning output dominates
  completion tokens on a simple two-tool request, which drives cost. A per-request reasoning
  budget or a documented way to turn reasoning down would help.
- Oct 27: behavior varied between runs of the same request: one run called get_balance on one
  account (A-1001), another called it on both accounts and summed them. Benchmark uses multiple runs.
- Oct 27: Nano's answer contained a non-breaking hyphen (U+2011). On a Windows console (cp1252)
  print() raised `UnicodeEncodeError: 'charmap' codec can't encode character '‑'`.
  Fix: reconfigure stdout to UTF-8 in our scripts. Worth a note in the Token Factory quickstart.




## What worked well
- The OpenAI-compatible endpoint: the standard `openai` SDK worked with only a base URL change.
- Tool calling on Nano was good enough to run the whole benchmark (4 tools, multi-turn).
- A mid-conversation `system` message after a tool result was accepted (2026-10-28).
- Low cost: under 4 cents for a full 81-run configuration.
