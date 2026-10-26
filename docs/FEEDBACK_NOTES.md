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

## Model and API notes (fill during build)
- Tool calling on Nano:
- Tool calling on Super:
- Empty `content` with reasoning in extra fields:
- Safety/guard model availability on Token Factory:
- Latency and cost observations:
- Oct 26: no dedicated NVIDIA safety or guard model appears in the Token Factory model list (30 models)
- Oct 27: tool calling works on Nano (nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B) and Super (nvidia/nemotron-3-super-120b-a12b) via the OpenAI-compatible API, including a tool-result round trip.
- Reasoning models return content=None on tool-call turns; reasoning text is in message.model_extra['reasoning'] (Super also has 'reasoning_content').
- No dedicated NVIDIA guard/safety model in the 30-model list.
- Nano test: 471 tokens total. Super shows prompt cache hits (352 cached tokens).




## What worked well
-
