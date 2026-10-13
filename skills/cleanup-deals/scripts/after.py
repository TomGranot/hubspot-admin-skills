# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Cleanup Deals — After State
Re-count every finding from before.py and print a before/after comparison.
Read-only. Uses the stale-days and pipeline recorded by before.py unless
overridden, so both runs count the same thing.

    uv run scripts/after.py

Writes data/audit-logs/cleanup-deals-after-summary.csv.
"""

import argparse
import csv
import os
import sys

import deal_findings as df

BEFORE_SUMMARY = os.path.join(df.AUDIT_DIR, "cleanup-deals-before-summary.csv")


def read_before():
    if not os.path.exists(BEFORE_SUMMARY):
        return {}
    with open(BEFORE_SUMMARY, newline="") as f:
        return {r["finding"]: r for r in csv.DictReader(f)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cleanup Deals — After State")
    parser.add_argument("--stale-days", type=int)
    parser.add_argument("--pipeline")
    args = parser.parse_args(argv)
    df.authenticate()

    before = read_before()
    first = next(iter(before.values()), {})
    stale_days = args.stale_days or int(first.get("stale_days") or df.STALE_DAYS_DEFAULT)
    pipeline = args.pipeline if args.pipeline is not None else (first.get("pipeline") or None)

    print("=" * 60)
    print("CLEANUP DEALS — AFTER STATE (read-only)")
    print("=" * 60)
    if not before:
        print(f"  No {BEFORE_SUMMARY} found: showing current counts only.")
    else:
        print(f"  Comparing with before.py run at {first.get('run_at', '?')}")
        if str(stale_days) != first.get("stale_days"):
            print(f"  WARNING: before used --stale-days {first.get('stale_days')}, "
                  f"this run uses {stale_days}. The stale row is not comparable.")
    print()

    results = df.collect(stale_days, pipeline)

    width = max(len(df.label(k, stale_days)) for k in results)
    print(f"  {'Finding'.ljust(width)}  {'Before':>6}  {'After':>6}  {'Change':>6}")
    rows = []
    for key, r in results.items():
        after = len(r["deals"])
        b = before.get(key, {}).get("count")
        change = "" if b in (None, "") else f"{after - int(b):+d}"
        print(f"  {df.label(key, stale_days).ljust(width)}  {b if b not in (None, '') else '-':>6}  "
              f"{after:>6}  {change:>6}")
        rows.append([key, df.label(key, stale_days), b or "", after, change, r["skipped"]])

    path = df.audit_path("cleanup-deals-after-summary.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["finding", "label", "before", "after", "change", "skipped_salesforce"])
        w.writerows(rows)

    print()
    print(f"  Summary CSV: {path}")
    print("  Review tasks change nothing on their own: counts drop as owners work")
    print("  their tasks. Re-run after the task due date for a fair comparison.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
