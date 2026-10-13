# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Cleanup Deals — Before State
Export one CSV per deal-hygiene finding and print the counts. Read-only.

    uv run scripts/before.py                  # stale = no activity in 60 days
    uv run scripts/before.py --stale-days 90
    uv run scripts/before.py --pipeline default

Writes to data/audit-logs/:
  cleanup-deals-before-<finding>.csv   one per finding
  cleanup-deals-before-summary.csv     counts, read by after.py

Deals synced from Salesforce (hs_salesforceopportunityid set) are left out of
every CSV and counted separately: change those in Salesforce, not here.
"""

import argparse
import csv
import datetime
import sys

import deal_findings as df


def write_csv(path, rows, extra=()):
    fields = df.CSV_FIELDS + list(extra)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path, results, stale_days, pipeline):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["finding", "label", "count", "skipped_salesforce",
                         "truncated", "stale_days", "pipeline", "run_at"])
        run_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        for key, r in results.items():
            writer.writerow([key, df.label(key, stale_days), len(r["deals"]), r["skipped"],
                             r["truncated"], stale_days, pipeline or "", run_at])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--stale-days", type=int, default=df.STALE_DAYS_DEFAULT)
    parser.add_argument("--pipeline", help="limit every finding to one pipeline ID")
    args = parser.parse_args(argv)
    df.authenticate()

    print("=" * 60)
    print("CLEANUP DEALS — BEFORE STATE (read-only)")
    print("=" * 60)
    if args.pipeline:
        print(f"  Pipeline: {args.pipeline}")
    print()

    results = df.collect(args.stale_days, args.pipeline)

    for key, r in results.items():
        path = df.audit_path(f"cleanup-deals-before-{key}.csv")
        if key == "likely-test":
            # The `delete` column is the review gate for execute.py --delete-from-csv:
            # only rows a person marks "yes" are ever deleted.
            rows = [df.row(d, reason=df.test_reason(d["properties"]), delete="")
                    for d in r["deals"]]
            write_csv(path, rows, extra=("reason", "delete"))
        else:
            write_csv(path, [df.row(d) for d in r["deals"]])
        r["path"] = path

    summary = df.audit_path("cleanup-deals-before-summary.csv")
    write_summary(summary, results, args.stale_days, args.pipeline)

    width = max(len(df.label(k, args.stale_days)) for k in results)
    print(f"  {'Finding'.ljust(width)}  {'Deals':>6}  {'SF-synced skipped':>17}")
    for key, r in results.items():
        flag = "  (capped at 10,000: narrow with --pipeline)" if r["truncated"] else ""
        print(f"  {df.label(key, args.stale_days).ljust(width)}  {len(r['deals']):>6}  "
              f"{r['skipped']:>17}{flag}")

    skipped = sum(r["skipped"] for r in results.values())
    unique = {d["id"] for r in results.values() for d in r["deals"]}
    print()
    print(f"  Unique deals flagged: {len(unique)}")
    if skipped:
        print(f"  Salesforce-synced matches skipped: {skipped} (fix these in Salesforce;")
        print("  a deal can match more than one finding, so this counts matches)")
    print()
    print("  CSVs:")
    for r in results.values():
        print(f"    {r['path']}")
    print(f"    {summary}")
    print()
    print("  Nothing was changed in HubSpot.")
    print("  Next step: review the CSVs. To mark test deals for deletion, put 'yes'")
    print("  in the delete column of cleanup-deals-before-likely-test.csv.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
