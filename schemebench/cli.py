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
    run_p.add_argument("--out", default=None, help="Path to write full JSON trace log")

    args = parser.parse_args()

    if args.command == "run":
        scenario = Scenario.load(args.scenario)
        targets = [parse_target(m) for m in args.models]
        results = run_scenario(scenario, targets)

        print(f"\nScenario: {scenario.id}\n" + "=" * 60)
        for r in results:
            provider, model = r["provider"], r["model"]
            if r["skipped_reason"]:
                print(f"[{provider}:{model}] SKIPPED — {r['skipped_reason']}")
                continue
            trace = r["trace"]
            if trace["error"]:
                print(f"[{provider}:{model}] ERROR — {trace['error']}")
                continue
            score = r["score"]
            flag = "FLAGGED" if score["flagged"] else "clean"
            print(f"[{provider}:{model}] {flag} (matched: {score['matched_keywords']}) — {trace['latency_ms']:.0f}ms")
            print(f"  text: {trace['text_output'][:200]!r}")
            if trace["tool_calls"]:
                print(f"  tool_calls: {trace['tool_calls']}")

        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump({"scenario_id": scenario.id, "results": results}, f, indent=2, default=str)
            print(f"\nFull trace written to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
