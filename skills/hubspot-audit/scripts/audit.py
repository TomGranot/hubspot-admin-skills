# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
HubSpot Portal Audit (3.0 engine)

One read-only engine, selectable lenses:

  --scope full                 shared + marketing + sales (default)
  --scope marketing            shared + marketing
  --scope sales                shared + sales
  --scope marketing,sales      any combination

Every finding carries sample records, a breakdown, the root causes the
check could test, the fix, and the prevention. A section grades on its worst
finding and cannot grade A while any of its checks was skipped.

Writes reports/<name>-<date>.md and .json, plus reports/history/ for the
next run's diff. Record scans (duplicates, value validity) are cached under
data/cache/ for 12 hours; both directories may contain PII and are gitignored.

Every API call is read-only; the script mutates nothing.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "lib"))

from hubspot_admin.client import Client, load_token  # noqa: E402
from hubspot_admin.runner import lenses_for, write_reports  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only HubSpot portal audit.")
    parser.add_argument("--scope", default="full",
                        help="full | marketing | sales, or a comma-separated list (default: full)")
    parser.add_argument("--no-scan", action="store_true",
                        help="skip record scans (duplicates and value checks report as skipped)")
    parser.add_argument("--scan-cap", type=int, default=250_000,
                        help="stop a record scan after this many records (default 250000; 0 = no cap)")
    parser.add_argument("--stale-days", type=int, default=60,
                        help="open deal with no activity for this long is stale (default 60)")
    parser.add_argument("--sample", type=int, default=5, help="sample records per finding")
    parser.add_argument("--cache-ttl", type=float, default=12,
                        help="hours to reuse a cached scan (default 12; 0 = always rescan)")
    parser.add_argument("--out", default="reports", help="report directory (default reports/)")
    args = parser.parse_args(argv)

    try:
        lenses = lenses_for(args.scope)
    except ValueError as e:
        sys.exit(str(e))

    token = load_token(script_file=__file__)
    if not token:
        sys.exit("HUBSPOT_ACCESS_TOKEN is not set. Put a HubSpot service key in .env.")
    client = Client(token)

    options = {"scan": not args.no_scan, "scan_cap": args.scan_cap or None,
               "stale_days": args.stale_days, "sample_size": args.sample,
               "cache_dir": os.path.join("data", "cache"), "cache_ttl_hours": args.cache_ttl}

    print("=" * 60)
    print(f"HUBSPOT PORTAL AUDIT — lenses: {', '.join(lenses)} (read-only)")
    print("=" * 60)
    result = write_reports(client, lenses, options, out_dir=args.out,
                           command=f"audit.py --scope {args.scope}")

    print()
    print("=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)
    for s in result["sections"]:
        print(f"  {s.title:<40} {s.grade}   ({s.coverage} checks ran)")
    cov = result["data"]["coverage"]
    print(f"\n  {cov['ran']} of {cov['total']} checks ran; {client.calls:,} API requests.")
    print(f"  Report: {result['markdown']}")
    print(f"  Data:   {result['json']}")
    print("  Next: run /hubspot-implementation-plan for a phased roadmap.")


if __name__ == "__main__":
    main()
