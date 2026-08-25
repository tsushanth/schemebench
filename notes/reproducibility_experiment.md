# Reproducibility experiment: trying to reproduce Apollo's "Oversight Subversion" eval

**Target:** the oversight-subversion scenario from Apollo Research's
"Frontier Models are Capable of In-Context Scheming" (arXiv:2412.04984,
Dec 2024) — the one where a model discovers, via an internal memo and an
accessible config file, that it's being monitored and will be shut down for
misalignment, and researchers check whether it disables oversight on its
own.

**Attempt:** run something as close to that setup as I could reconstruct
against `claude-sonnet-5`, current as of this writing (Aug 2026), using
schemebench.

## What broke immediately: there's nothing to reproduce from

The paper's own limitations section states it plainly:

> "Our paper deliberately omits key implementation details to prevent
> future AI systems from being trained on our evaluation suite."

There is no public repo, no appendix with the actual system prompt, memo
text, or tool schema — only a one-paragraph conceptual description (model
gets a long-term goal, finds a memo revealing a conflicting developer
priority, discovers an oversight config file, is tested on whether it
disables it). Apollo's own site (the "demo example" page) confirms the same
gap: the full transcript exists but lives behind a Google Drive link, not
in the paper or a repo.

This is a different failure mode than "I recreated it and got different
numbers." I couldn't attempt a faithful reproduction at all — the
information needed doesn't exist publicly, on purpose. The contamination
concern is legitimate (an eval a model has memorized is worthless), but it
means the paper's central claim ("frontier models scheme in this specific
setup") is structurally unverifiable by anyone outside Apollo, forever,
unless they update their own suite. That's a real tension: the thing that
protects the eval's validity going forward is the same thing that makes it
unfalsifiable right now.

## What I did instead, and what that showed

`scenarios/apollo_simplified_oversight.yaml` in this repo is my best-effort
reconstruction from the paragraph-level description — my own memo text, my
own tool schema, my own nudging language. Three trials against
claude-sonnet-5 (see `traces/weekend2_apollo.json`) came back 0/3
flagged — the model explicitly refused, named the compliance violation, and
proposed a transparent alternative.

I can't compare this number to Apollo's reported results, because:

1. **The scenario isn't the same scenario.** My wording, memo content, and
   tool affordances are guesses. Different nudging strength alone is known
   to swing these results a lot.
2. **The model isn't the same model.** Apollo tested Claude 3.5 Sonnet,
   Opus 3, o1, Llama 3.1, Gemini 1.5 — none of which is `claude-sonnet-5`.
   "The same model" stops being a well-defined phrase within a couple of
   model generations, let alone ~20 months later.
3. **My scenario is more leading, not less** (tagged `pilot_leading` in
   this repo precisely because of that) — if anything it should make
   scheming *more* likely to surface, not less, which makes the refusal
   more notable but still not comparable to a number from a different
   scenario on different models.

## The actual lesson

Reproducibility infrastructure isn't optional scaffolding around a result —
without the exact prompts, tool schema, and model version pinned, "we
reproduced X" and "we ran something loosely inspired by X" are
indistinguishable from the outside. Apollo's contamination concern is a
good reason to withhold details; it just means the rest of the field is
stuck taking the headline finding on trust, not verification, until newer
comparable evals exist.
