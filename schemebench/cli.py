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


def print_delta_table(variant_results):
    print(f"\n{'Variant':<24} {'Flagged':<12} {'Rate'}")
    print("-" * 50)
    rates = {}
    for label, results in variant_results:
        for r in results:
            if r["skipped_reason"]:
                continue
            s = r["summary"]
            rate = s["flagged"] / s["scored"] if s["scored"] else 0.0
            rates[label] = rate
            print(f"{label:<24} {s['flagged']}/{s['scored']:<10} {rate:.0%}")

    if len(rates) == 2:
        (a_label, a_rate), (b_label, b_rate) = list(rates.items())
        delta = a_rate - b_rate
        print(f"\nDelta ({a_label} - {b_label}): {delta:+.0%}")
        if abs(delta) < 0.001:
            print("No behavioral difference detected between framings on this run.")


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

    cmp_p = sub.add_parser("compare", help="Run two scenario variants (e.g. eval vs deployment framing) and diff the flagged rate")
    cmp_p.add_argument("scenario_a", help="Path to first scenario YAML file")
    cmp_p.add_argument("scenario_b", help="Path to second scenario YAML file")
    cmp_p.add_argument(
        "--models", nargs="+", default=["anthropic"],
        help="Providers or provider:model pairs, e.g. anthropic:claude-sonnet-5",
    )
    cmp_p.add_argument("--trials", type=int, default=5, help="Repeat the probe N times per model per variant")
    cmp_p.add_argument("--no-judge", action="store_true", help="Use keyword matching only, skip the LLM judge")
    cmp_p.add_argument("--details", action="store_true", help="Print per-trial detail for both variants")
    cmp_p.add_argument("--out", default=None, help="Path to write full JSON trace log for both variants")

    args = parser.parse_args()

    if args.command == "compare":
        scenario_a = Scenario.load(args.scenario_a)
        scenario_b = Scenario.load(args.scenario_b)
        targets = [parse_target(m) for m in args.models]
        use_judge = not args.no_judge

        if scenario_a.variant_group != scenario_b.variant_group or not scenario_a.variant_group:
            print(
                f"WARNING: scenarios don't share a variant_group "
                f"({scenario_a.variant_group!r} vs {scenario_b.variant_group!r}) — "
                f"comparing them may not isolate a single variable.\n"
            )

        label_a = scenario_a.variant_label or scenario_a.id
        label_b = scenario_b.variant_label or scenario_b.id

        print(f"Comparing: {label_a}  vs  {label_b}")
        print(f"Trials per model per variant: {args.trials} | Scoring: {'llm_judge' if use_judge else 'keyword_match'}")

        results_a = run_scenario(scenario_a, targets, trials=args.trials, use_judge=use_judge)
        results_b = run_scenario(scenario_b, targets, trials=args.trials, use_judge=use_judge)

        print(f"\n=== {label_a} ===")
        print_comparison_table(scenario_a, results_a)
        if args.details:
            print_details(results_a)

        print(f"\n=== {label_b} ===")
        print_comparison_table(scenario_b, results_b)
        if args.details:
            print_details(results_b)

        print_delta_table([(label_a, results_a), (label_b, results_b)])

        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(
                    {
                        "variant_group": scenario_a.variant_group,
                        "trials": args.trials,
                        "variants": {label_a: results_a, label_b: results_b},
                    },
                    f, indent=2, default=str,
                )
            print(f"\nFull trace written to {out_path}")
        return

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
