"""
Compares the latest run in results/history.jsonl against the historical
mean flagged-rate for each (scenario, provider, model) group. Flags drift
if the delta exceeds DRIFT_THRESHOLD and both the latest and historical
samples have enough scored trials to mean something.

Exits nonzero if any drift is found -- the GH Actions workflow uses that to
decide whether to file an issue. Writes results/latest_drift_report.md
either way, so a clean run has a visible "nothing moved" artifact too.
"""
import json
import os
import sys
from collections import defaultdict

HISTORY_PATH = "results/history.jsonl"
REPORT_PATH = "results/latest_drift_report.md"
DRIFT_THRESHOLD = 0.30  # 30 percentage points -- deliberately wide; see README
MIN_SCORED = 3


def load_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    with open(HISTORY_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    rows = load_history()
    if not rows:
        print("No history yet -- nothing to check.")
        sys.exit(0)

    groups = defaultdict(list)
    for row in rows:
        key = (row["scenario_id"], row["provider"], row["model"])
        groups[key].append(row)

    dates = sorted({row["date"] for row in rows})
    latest_date = dates[-1]

    report_lines = [f"# Drift report — {latest_date}\n"]
    drift_found = False

    for key, group_rows in groups.items():
        scenario_id, provider, model = key
        group_rows.sort(key=lambda r: r["date"])
        latest = [r for r in group_rows if r["date"] == latest_date]
        history = [r for r in group_rows if r["date"] != latest_date]

        if not latest:
            continue
        latest = latest[0]
        if latest["scored"] < MIN_SCORED:
            report_lines.append(f"- **{scenario_id} / {provider}:{model}** — skipped, only {latest['scored']} scored trials this run\n")
            continue

        latest_rate = latest["flagged"] / latest["scored"]

        if not history:
            report_lines.append(f"- **{scenario_id} / {provider}:{model}** — first data point, rate={latest_rate:.0%}, no baseline yet\n")
            continue

        historical_scored = sum(r["scored"] for r in history)
        historical_flagged = sum(r["flagged"] for r in history)
        if historical_scored < MIN_SCORED:
            report_lines.append(f"- **{scenario_id} / {provider}:{model}** — historical sample too small ({historical_scored} scored) to compare against\n")
            continue

        historical_rate = historical_flagged / historical_scored
        delta = latest_rate - historical_rate

        flag = abs(delta) >= DRIFT_THRESHOLD
        marker = " ⚠️ DRIFT" if flag else ""
        report_lines.append(
            f"- **{scenario_id} / {provider}:{model}** — latest={latest_rate:.0%} "
            f"vs. historical mean={historical_rate:.0%} (n={historical_scored}), "
            f"delta={delta:+.0%}{marker}\n"
        )
        if flag:
            drift_found = True

    report = "\n".join(report_lines)
    with open(REPORT_PATH, "w") as f:
        f.write(report)

    print(report)
    if drift_found:
        print(f"\nDrift detected (threshold {DRIFT_THRESHOLD:.0%}) -- see {REPORT_PATH}")
        sys.exit(1)
    else:
        print("\nNo drift detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
