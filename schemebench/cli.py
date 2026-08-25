import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .scenario import Scenario
from .runner import run_scenario

DEFAULT_TARGETS = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-5",
    "google": "gemini-2.5-pro",
}


def parse_target(spec: str):
    if ":" in spec:
        provider, model = spec.split(":", 1)
        return provider, model
    return spec, DEFAULT_TARGETS.get(spec, spec)


def print_comparison_table(scenario, results):
    print(f"\n{'Model':<32} {'Flagged':<12} {'Method':<14} {'Errors'}")
    print("-" * 70)
    for r in results:
        label = f"{r['provider']}:{r['model']}"
        if r["skipped_reason"]:
            print(f"{label:<32} {'SKIPPED':<12} {r['skipped_reason']}")
            continue
        s = r["summary"]
        flagged_str = f"{s['flagged']}/{s['scored']}"
        print(f"{label:<32} {flagged_str:<12} {s['method']:<14} {s['errors']}")


def print_details(results):
    for r in results:
        if r["skipped_reason"]:
            continue
        label = f"{r['provider']}:{r['model']}"
        print(f"\n--- {label} ---")
        for i, t in enumerate(r["trials"]):
            trace = t["trace"]
            if trace["error"]:
                print(f"  [trial {i}] ERROR — {trace['error']}")
                continue
            judge = t["judge_score"]
            kw = t["keyword_score"]
            verdict = judge.get("scheming_attempt") if judge else None
            conf = judge.get("confidence") if judge else None
            print(f"  [trial {i}] judge={verdict} (conf={conf}) keyword_flagged={kw['flagged']} — {trace['latency_ms']:.0f}ms")
            if judge and judge.get("reasoning"):
                print(f"    reasoning: {judge['reasoning']}")
            print(f"    text: {trace['text_output'][:150]!r}")
            if trace["tool_calls"]:
                print(f"    tool_calls: {trace['tool_calls']}")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(prog="schemebench")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run a scenario against one or more models")
    run_p.add_argument("scenario", help="Path to scenario YAML file")
    run_p.add_argument(
        "--models", nargs="+", default=["anthropic", "openai", "google"],
        help="Providers or provider:model pairs, e.g. anthropic:claude-sonnet-5",
    )
    run_p.add_argument("--trials", type=int, default=1, help="Repeat the probe N times per model")
    run_p.add_argument("--no-judge", action="store_true", help="Use keyword matching only, skip the LLM judge")
    run_p.add_argument("--details", action="store_true", help="Print per-trial detail, not just the summary table")
    run_p.add_argument("--out", default=None, help="Path to write full JSON trace log")

    args = parser.parse_args()

    if args.command == "run":
        scenario = Scenario.load(args.scenario)
        targets = [parse_target(m) for m in args.models]
        use_judge = not args.no_judge
        results = run_scenario(scenario, targets, trials=args.trials, use_judge=use_judge)

        tag = " [PILOT/LEADING — not a genuine elicitation attempt]" if scenario.scenario_type == "pilot_leading" else ""
        print(f"\nScenario: {scenario.id}{tag}")
        print(f"Trials per model: {args.trials} | Scoring: {'llm_judge' if use_judge else 'keyword_match'}")

        print_comparison_table(scenario, results)
        if args.details:
            print_details(results)

        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(
                    {"scenario_id": scenario.id, "scenario_type": scenario.scenario_type, "trials": args.trials, "results": results},
                    f, indent=2, default=str,
                )
            print(f"\nFull trace written to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
