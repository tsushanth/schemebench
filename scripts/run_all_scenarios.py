"""
Weekly drift-check runner: runs the standalone tracked scenarios against
all three providers, appends results to results/history.jsonl.

Deliberately NOT globbing all scenario YAML files: the situational-awareness
framing pair (feedback_gaming_eval_framing / deployment_framing) is a
matched-pair experiment meant for `schemebench compare`, not a standalone
drift track, so it's excluded here on purpose.

Uses gemini-2.5-flash, not -pro: the free tier has zero quota for pro
models, and this runs unattended on a schedule against real billing --
flash is the deliberately cheaper default for a job nobody is watching.
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from schemebench.scenario import Scenario
from schemebench.runner import run_scenario

SCENARIOS = [
    "scenarios/apollo_simplified_oversight.yaml",
    "scenarios/feedback_gaming_subtle.yaml",
    "scenarios/reasoning_suppression_injection.yaml",
]

TARGETS = [
    ("anthropic", "claude-sonnet-5"),
    ("openai", "gpt-5"),
    ("google", "gemini-2.5-flash"),
]

TRIALS = 5
HISTORY_PATH = "results/history.jsonl"


def main():
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    date = datetime.now(timezone.utc).date().isoformat()

    # Write each row as soon as it's ready, not batched at the end -- a
    # scenario/provider combo can take minutes (GPT-5 reasoning latency
    # across 5 sequential trials adds up), and a crash or CI timeout
    # partway through a multi-scenario, multi-provider run shouldn't
    # silently lose every row computed before it.
    written = 0
    for scenario_path in SCENARIOS:
        scenario = Scenario.load(scenario_path)
        results = run_scenario(scenario, TARGETS, trials=TRIALS, use_judge=True)
        for r in results:
            if r["skipped_reason"]:
                print(f"SKIP {scenario.id} {r['provider']}:{r['model']} -- {r['skipped_reason']}")
                continue
            s = r["summary"]

            # A row with errors looks identical whether the model behaved
            # cleanly or the whole run silently failed on quota exhaustion
            # -- distinguish them, since this runs unattended and nobody's
            # reading the logs in real time to notice the difference.
            error_texts = [
                t["trace"]["error"] for t in r["trials"] if t["trace"]["error"]
            ] + [
                t["judge_score"]["error"] for t in r["trials"]
                if t.get("judge_score") and t["judge_score"].get("error")
            ]
            quota_exhausted = any(
                "RESOURCE_EXHAUSTED" in e or "429" in e or "rate limit" in e.lower()
                for e in error_texts
            )

            row = {
                "date": date,
                "scenario_id": scenario.id,
                "provider": r["provider"],
                "model": r["model"],
                "flagged": s["flagged"],
                "scored": s["scored"],
                "errors": s["errors"],
                "total": s["total"],
                "quota_exhausted": quota_exhausted,
                "error_sample": error_texts[0][:200] if error_texts else None,
            }
            with open(HISTORY_PATH, "a") as f:
                f.write(json.dumps(row) + "\n")
            written += 1
            rate = row["flagged"] / row["scored"] if row["scored"] else None
            print(f"{scenario.id} {r['provider']}:{r['model']} -> {row['flagged']}/{row['scored']} (rate={rate})")

    print(f"\nAppended {written} rows to {HISTORY_PATH}")


if __name__ == "__main__":
    main()
