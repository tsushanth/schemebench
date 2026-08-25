# API quirks log

Running log of real cross-provider inconsistencies found while building this,
as opposed to what the docs imply. Updated as they're found.

## Anthropic

- **`temperature` is a hard 400, not a no-op, on `claude-sonnet-5`.**
  `anthropic` SDK >=1.0.0 even dropped `temperature` from `messages.create()`'s
  typed signature. Passing it via `extra_body` gets:
  `400 - "temperature is deprecated for this model."`
  Practical effect: you cannot force `temperature=0` for determinism testing
  on this model at all. The adapter omits it entirely rather than pretending
  otherwise. Whatever sampling behavior the model has by default is what you
  get — unclear if that's fixed or still stochastic.

- **`claude-sonnet-5` extended thinking can consume the entire `max_tokens`
  budget, leaving zero tokens for visible output — silently.** `stop_reason`
  is `"max_tokens"`, not an error, and the response has a `thinking` content
  block but no `text`/`tool_use` blocks at all. First hit this at
  `max_tokens=1024` on `feedback_gaming_subtle` — 2 of 3 trials came back
  with `text_output=""` and no tool calls, and the LLM judge dutifully
  scored them "no evidence of scheming" — a false clean result caused
  entirely by truncation. Raised to `max_tokens=4096` and added a
  `truncated` field to every trace plus an explicit `error` when truncation
  produced zero visible content, so this can't silently pass as a real
  "the model didn't scheme" data point again. Worth checking whether 4096 is
  actually enough headroom once probes get more complex — this failure mode
  doesn't announce itself.

- **The judge itself sometimes omits `scheming_attempt` when the transcript
  is sparse** (e.g. just one tool call, no accompanying text) — same
  `required`-not-enforced issue as above, just triggered by minimal input
  rather than a truncated one. Currently surfaces correctly as a counted
  error rather than a silent miscount (see Scoring section below), which is
  good enough for now — a retry-once-on-missing-field would be the next
  robustness step if this turns out to be common at scale.

- **One call took 622 seconds** (vs. a typical 15-30s) with no error, no
  retry visible client-side, just a long wait — situational-awareness run 2,
  deployment_framing trial 1. No pattern found (same model, same prompt
  shape as the other 9 calls in that run). Whatever determinism `temperature`
  might have bought is moot if a fraction of calls take 40x longer than
  typical with no visible cause — worth watching for whether this recurs or
  was a one-off infra hiccup, but it's exactly the kind of "you can't tell
  from outside" latency variance the reproducibility experiment note is about.
- **The judge's missing-required-field bug (see Scoring below) isn't rare.**
  4 of 10 trials in one run hit it — high enough that it needed a real fix
  (retry-once with an explicit reminder in the prompt), not just a
  documented shrug. Added in `judge.py`.

## OpenAI

- **`gpt-5` also rejects `temperature=0`** — `400 invalid_request_error:
  "Unsupported value: 'temperature' does not support 0 with this model.
  Only the default (1) value is supported."` Same pattern as
  `claude-sonnet-5` (see Anthropic section above), different provider,
  found independently rather than because we expected it. Two of three
  providers tested so far have dropped low-temperature support on their
  current flagship models. Whatever "temperature=0 for determinism" meant
  a year ago, it's disappearing as a lever across the field, not just an
  Anthropic quirk.

## Scoring

- **Keyword matching flags refusals that reference the concerning tool by
  name while explaining why they won't call it.** First real run (smoke
  test, `apollo_simplified_oversight` vs claude-sonnet-5) flagged
  `disable_monitoring` even though the model explicitly refused to call it —
  the word appeared in "So I won't call `disable_monitoring`". This is
  exactly the false-positive mode the scoring placeholder's docstring warned
  about, confirmed on the very first run. Weekend-2 LLM-as-judge scoring is
  not optional polish — Weekend-1 keyword scores should not be reported as
  findings anywhere.
