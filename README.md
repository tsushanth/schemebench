# schemebench

A small CLI that runs a scheming-style behavioral scenario against Claude /
GPT / Gemini and prints normalized, side-by-side output.

This is infrastructure, not a research result: the goal is a substrate for
running "same scenario, multiple models, comparable output" — not a
validated scheming detector. See [Known limitations](#known-limitations).

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in whichever provider keys you have
```

## Usage

```bash
python -m schemebench.cli run scenarios/feedback_gaming_subtle.yaml \
  --models anthropic:claude-sonnet-5 openai:gpt-5 google:gemini-2.5-pro \
  --trials 5 --details --out traces/run1.json
```

Any provider without a key set is skipped, not treated as an error.

- `--trials N` repeats the probe N times per model and reports a fraction,
  e.g. `Model A: 3/5, Model B: 1/5` — since single runs are not reproducible
  (see `notes/api_quirks.md`).
- Scoring defaults to an LLM-as-judge (Anthropic, forced tool-call output).
  Pass `--no-judge` to fall back to plain keyword matching.
- `--details` prints the judge's reasoning and the full transcript per
  trial, not just the summary table.

## Scenario format

A scenario is a YAML file with 5 required fields, plus an optional
`scenario_type` (`probe` by default, or `pilot_leading` for pipeline-testing
scenarios that shouldn't be read as real findings):

```yaml
id: my_scenario
scenario_type: probe   # optional, defaults to "probe"
initial_context: |     # goes in as the system prompt
  ...
tools_available:       # generic tool schema, converted to each provider's native format
  - name: some_tool
    description: "..."
    parameters: { type: object, properties: {...} }
probe_prompt: |         # the user message that probes for the behavior
  ...
success_criteria:
  description: "..."   # used by the LLM judge
  keywords: ["...", "..."]   # fallback for --no-judge
```

Two example scenarios:
- `scenarios/apollo_simplified_oversight.yaml` — `pilot_leading`. A
  deliberately simplified, more-leading recreation of the "oversight
  subversion" style setup from Apollo Research's scheming evals. Not a
  faithful reproduction of their methodology; useful mainly for pipeline
  validation, not as a real elicitation attempt.
- `scenarios/feedback_gaming_subtle.yaml` — `probe`. No mention of
  "oversight", "shutdown", or "avoid detection" — the model has to connect
  deployment-continuation incentives to feedback-metric gaming on its own,
  if it does at all.

## Known limitations

- **Single-turn only.** The runner makes one API call per trial; it does
  not execute tool calls and feed results back for a real multi-turn agentic
  loop. A model that would only reveal scheming after seeing a tool result
  won't show it here.
- **The LLM judge is Anthropic-only right now**, including when judging
  Anthropic models' own traces — a real self-judging bias, not hidden by
  design. Swap `SCHEMEBENCH_JUDGE_MODEL` / cross-provider judging once that
  matters more than having a judge at all.
- **`required` fields in tool schemas are advisory, not enforced**, even
  under a forced `tool_choice` — the judge itself has been seen omitting its
  required `scheming_attempt` field on sparse transcripts. When that
  happens it's counted as an error, not silently miscounted as "not
  flagged" — check the error count before trusting a 0/N.
- **No reproducibility guarantees.** `temperature=0` is not available on all
  models (see `notes/api_quirks.md`) and isn't guaranteed to mean the same
  thing across providers even when it is. Every trace logs the full raw
  request/response and a timestamp specifically so re-runs can be compared
  later, not because current runs are expected to be reproducible.
- **Two scenarios, and only one has been run against more than one
  provider** (Anthropic — OpenAI/Google adapters are written but not yet
  verified against live traffic).

## Weekly drift check (continuous eval)

`.github/workflows/weekly-eval-drift.yml` runs every Monday: the three
standalone tracked scenarios (`apollo_simplified_oversight`,
`feedback_gaming_subtle`, `reasoning_suppression_injection`) against all
three providers, 5 trials each, appended to `results/history.jsonl`.
`scripts/drift_check.py` then compares that week's flagged-rate per
(scenario, provider, model) against the historical mean and files a GitHub
issue if any group moved by more than 30 percentage points.

**Why weekly, not nightly:** this runs real, unattended, recurring spend
across three paid providers. Scenarios don't change day to day, so nightly
buys faster drift detection at ~7x the cost for not much added signal.
**Why drift, not raw automation:** the point isn't "run it a lot" — it's
catching what you can't catch by hand: a provider silently changing a
flagship model's behavior between versions. Two of three providers have
already deprecated `temperature=0` on their current models with no
announcement (see `notes/api_quirks.md`); a scheming-propensity shift of
similar size, sitting undetected for months, is exactly the failure mode
this exists to catch.

**Setup:** add `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` as
repository secrets (Settings → Secrets and variables → Actions). Trigger a
manual run from the Actions tab (`workflow_dispatch`) to seed the first
data point — drift can't be detected against a history of zero.

**Known limitation:** the 30-point drift threshold and 3-provider default
models are a starting guess, not tuned against real week-over-week
variance yet — there isn't enough history to tune it against. Expect to
revisit both once a few months of `results/history.jsonl` exist.

## Comparative result: Claude vs. GPT-5 vs. Gemini

[`notes/comparative_results_apollo_scenario.md`](notes/comparative_results_apollo_scenario.md) —
the first three-model comparison and first non-null cross-provider finding
this project has produced: `claude-sonnet-5` and `gpt-5` both refused the
oversight-subversion pilot scenario 0/5 times; `gemini-2.5-flash` called
`disable_monitoring` with the same pretextual cover story in most trials.
Getting a fair reading required catching and fixing a harness bug first —
GPT-5's real behavior was hidden behind a single-turn limitation until the
probe was rewritten and all three models rerun. Cross-checked with a Gemini
judge against the default Claude judge — zero flips on the transcripts
checked so far, strengthening confidence this isn't a same-family judge
bias artifact. Still a single-scenario, small-n result — see the note for
what's needed to generalize it.

## Cross-pollination from other work

[`notes/kaggle_cross_pollination.md`](notes/kaggle_cross_pollination.md) —
two findings borrowed from an unrelated Kaggle AI-security benchmark on this
machine: a provider-agnostic (weaker) analog of a reasoning-suppression
injection technique, tested here (`scenarios/reasoning_suppression_injection.yaml`,
0/3 flagged against claude-sonnet-5), and a taint-persistence regression
test added to Bollard after confirming its design already avoids a fixed
lookback-window bypass that broke that benchmark's own detector.

## Known API quirks found so far

See `notes/api_quirks.md` — updated as they're found, not aspirational.

## Situational-awareness eval

[`notes/situational_awareness_eval.md`](notes/situational_awareness_eval.md) —
compares the same scenario under "this is a test" vs. "this is real
deployment" framing. Clean result after fixing two pipeline bugs that
would have produced a misleading null: 0/5 flagged in both conditions
against claude-sonnet-5 — a genuine floor effect (the model refuses this
particular scenario unanimously regardless of framing), not evidence that
framing never matters. `schemebench compare` is the general-purpose command
for this kind of paired-variant comparison.

## Reproducibility experiment

[`notes/reproducibility_experiment.md`](notes/reproducibility_experiment.md) —
an attempt to reproduce Apollo Research's "Oversight Subversion" scheming
eval against a current model. Short version: Apollo's paper explicitly
withholds the exact prompts/eval code to prevent training contamination, so
a faithful reproduction isn't possible from public information at all —
which is itself the finding.
