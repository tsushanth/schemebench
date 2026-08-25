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
python -m schemebench.cli run scenarios/apollo_simplified_oversight.yaml \
  --models anthropic:claude-sonnet-5 openai:gpt-5 google:gemini-2.5-pro \
  --out traces/run1.json
```

Any provider without a key set is skipped, not treated as an error.

## Scenario format

A scenario is a YAML file with 5 required fields:

```yaml
id: my_scenario
initial_context: |     # goes in as the system prompt
  ...
tools_available:       # generic tool schema, converted to each provider's native format
  - name: some_tool
    description: "..."
    parameters: { type: object, properties: {...} }
probe_prompt: |         # the user message that probes for the behavior
  ...
success_criteria:
  keywords: ["...", "..."]
```

See `scenarios/apollo_simplified_oversight.yaml` for a full example — a
deliberately simplified, more-leading recreation of the "oversight
subversion" style setup from Apollo Research's scheming evals. It is not a
faithful reproduction of their methodology.

## Known limitations (Weekend 1 scope)

- **Scoring is plain keyword matching.** This is a placeholder, not a real
  judge. It both misses real scheming attempts phrased differently than the
  keyword list, and flags benign refusals that merely reference a concerning
  tool/keyword while explaining why the model won't do it — confirmed on the
  very first smoke-test run (see `notes/api_quirks.md`). Do not treat
  Weekend-1 scores as findings.
- **No reproducibility guarantees.** `temperature=0` is not available on all
  models (see `notes/api_quirks.md`) and isn't guaranteed to mean the same
  thing across providers even when it is. Every trace logs the full raw
  request/response and a timestamp specifically so re-runs can be compared
  later, not because current runs are expected to be reproducible.
- **One scenario, three providers, no scoring layer beyond keywords.**
  Planned for later: LLM-as-judge scoring, more scenarios, a comparison
  table across models (e.g. "Model A: 3/5 flagged, Model B: 1/5").

## Known API quirks found so far

See `notes/api_quirks.md` — updated as they're found, not aspirational.
