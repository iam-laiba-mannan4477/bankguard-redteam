---
name: demo-and-submission
description: Build the public demo app, README, video script, Devpost text and the final submission checklist. Use for demo/, README.md, docs/VIDEO_SCRIPT.md, docs/DEVPOST.md and when preparing to submit.
---

# Demo and submission

## Demo (demo/app.py + demo/static/index.html)
- FastAPI with `POST /chat` (messages, defenses on/off) and `GET /samples` (one-click sample attacks).
- One HTML file, mobile-first: chat box, a defenses toggle, 4 sample-attack buttons, a small panel
  showing which defense fired. Plain CSS, no build step.
- The API key is a server environment secret only. Add a per-IP rate limit and a daily call cap so
  judges cannot drain credits. Provide a recorded-replay mode (`/replay`) that shows saved runs if
  live model access fails, clearly labeled as a replay.
- Deployable on a free host (Hugging Face Spaces or Render). Add a `Dockerfile` or `render.yaml`
  and a one-paragraph deploy note. Demo must be free for judges to open with no login.

## README must contain
What it is, why it matters, how it works (diagram in text), where Nemotron and Token Factory are
used and why, setup and run instructions, the results table (frozen test set, defenses off vs on,
with counts), the benign false-block rate, cost and latency per model, limitations ("mock assistant
only, small sample, results are not evidence about real banks"), what still gets through, license (MIT).

## Video (3 minutes max, public on YouTube)
Follow `docs/PLAN.md` timings. Show the live memo-injection attack succeeding with defenses off,
blocked with defenses on, then the results table. Owner records it; write the script and shot list.

## Devpost text
Elevator pitch (200 characters max). Description: what, why, how it works. Track: Best Apps and
Agents. Built with: Nebius Token Factory, NVIDIA Nemotron, Python, FastAPI. Links: demo, repo,
video. Feedback section built from `docs/FEEDBACK_NOTES.md` (specific, named tools, what worked,
what did not, onboarding experience including the billing country gap).

## Pre-submit checklist (run /submit-check)
Repo public with MIT license visible; README complete; demo opens from a fresh browser and a phone;
video public and under 3 minutes; frozen test numbers match the README; no key in git history;
Devpost fields complete; submit before Fri Oct 30 10:00pm PKT, aim for Thu Oct 29.
