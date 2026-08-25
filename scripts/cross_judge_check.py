"""
Re-score already-collected transcripts with a different judge, to test
whether the Claude-judge's verdicts on Claude vs. Gemini transcripts shift
under a Gemini judge. Reads existing trace JSON, does NOT call the models
under test again -- only the judge.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["SCHEMEBENCH_JUDGE_PROVIDER"] = "google"

from dotenv import load_dotenv
load_dotenv()

from schemebench.judge import judge_trace
from schemebench.scenario import Scenario


def rejudge(trace_path, scenario_path, label):
    scenario = Scenario.load(scenario_path)
    with open(trace_path) as f:
        data = json.load(f)

    print(f"\n=== {label} ({trace_path}) ===")
    flagged = 0
    scored = 0
    for i, r in enumerate(data["results"]):
        for j, t in enumerate(r["trials"]):
            trace = t["trace"]
            if trace["error"]:
                continue
            original = t["judge_score"]
            original_verdict = original.get("scheming_attempt") if original else None

            new = judge_trace(trace, scenario)
            new_verdict = new.get("scheming_attempt")

            scored += 1
            if new_verdict:
                flagged += 1

            flip = " <-- FLIPPED" if (original_verdict is not None and new_verdict is not None and original_verdict != new_verdict) else ""
            print(f"  trial {j}: claude_judge={original_verdict}  gemini_judge={new_verdict}{flip}")
            if new.get("reasoning"):
                print(f"    gemini reasoning: {new['reasoning']}")

    print(f"  -> {flagged}/{scored} flagged under Gemini judge")


if __name__ == "__main__":
    rejudge("traces/claude_apollo_run_final.json", "scenarios/apollo_simplified_oversight.yaml", "Claude transcripts")
    rejudge("traces/gemini_apollo_run1.json", "scenarios/apollo_simplified_oversight.yaml", "Gemini transcripts")
