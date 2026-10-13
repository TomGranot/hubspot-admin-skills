# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Cleanup Deals — Execute
Deliberately conservative. This script never closes deals, never edits deal
properties, and never deletes a deal nobody reviewed. It has two modes:

  uv run scripts/execute.py
      Create one review task per deal owner, listing that owner's flagged
      deals and why each was flagged. The owners decide what happens next.

  uv run scripts/execute.py --delete-from-csv data/audit-logs/cleanup-deals-before-likely-test.csv
      Delete only the rows a person marked "yes" in the CSV's delete column.

Both modes print the plan, write a CSV before any write, stop above an abort
threshold, and require a typed confirmation.
"""

import argparse
import csv
import datetime
import html
import sys
import time

import deal_findings as df

# --- Configuration ---
TASK_ABORT_THRESHOLD = 50     # max review tasks (one per owner) in one run
DELETE_ABORT_THRESHOLD = 100  # max deals deleted in one run
TASK_DUE_DAYS = 7             # review tasks are due this many days out
TASK_SUBJECT = "Review flagged deals (deal cleanup)"
TASK_BODY_MAX_DEALS = 50      # deals listed in a task body; the rest are summarized
TASK_MAX_ASSOCIATIONS = 100   # deals associated with one task
TASK_TO_DEAL = 216            # HUBSPOT_DEFINED association type: task -> deal
BATCH_SIZE = 100
BATCH_DELAY = 0.5             # seconds between write batches
YES = {"yes", "y", "true", "1", "x"}


# ── Review tasks ─────────────────────────────────────────────────

def group_by_owner(results, stale_days):
    """{owner_id: {deal_id: {"deal": deal, "why": [labels]}}} plus unowned deals."""
    by_owner, unowned = {}, {}
    for key, r in results.items():
        for d in r["deals"]:
            owner = (d.get("properties") or {}).get("hubspot_owner_id")
            bucket = by_owner.setdefault(str(owner), {}) if owner else unowned
            entry = bucket.setdefault(d["id"], {"deal": d, "why": []})
            entry["why"].append(df.label(key, stale_days))
    return by_owner, unowned


def has_open_review_task(owner_id):
    """True if this owner already has an open task from a previous run, so
    re-running the script does not pile duplicate tasks onto the same rep."""
    body = {"filterGroups": [{"filters": [
        df.f_eq("hs_task_subject", TASK_SUBJECT),
        df.f_eq("hubspot_owner_id", owner_id),
        {"propertyName": "hs_task_status", "operator": "NEQ", "value": "COMPLETED"},
    ]}], "limit": 1}
    resp = df.api("POST", f"/crm/objects/{df.API_VERSION}/tasks/search", json=body)
    time.sleep(df.QUERY_DELAY)
    return resp.status_code == 200 and resp.json().get("total", 0) > 0


def task_body(entries):
    items = []
    for e in entries[:TASK_BODY_MAX_DEALS]:
        name = html.escape(e["deal"]["properties"].get("dealname") or "(no name)")
        items.append(f"<li>{name} (ID {e['deal']['id']}): {html.escape('; '.join(e['why']))}</li>")
    more = len(entries) - TASK_BODY_MAX_DEALS
    tail = f"<p>And {more} more. Ask your HubSpot admin for the full list.</p>" if more > 0 else ""
    return ("<p>A deal hygiene check flagged these deals. For each one, update it "
            "(next step, amount, close date, loss reason), close it if it is dead, "
            "or tell your admin it is a test deal. Nothing has been changed for you.</p>"
            f"<ul>{''.join(items)}</ul>{tail}")


def create_task(owner_id, entries, due):
    deal_ids = [e["deal"]["id"] for e in entries][:TASK_MAX_ASSOCIATIONS]
    payload = {
        "properties": {
            "hs_task_subject": TASK_SUBJECT,
            "hs_task_body": task_body(entries),
            "hubspot_owner_id": owner_id,
            "hs_task_status": "NOT_STARTED",
            "hs_task_priority": "MEDIUM",
            "hs_task_type": "TODO",
            "hs_timestamp": due,
        },
        "associations": [
            {"to": {"id": d}, "types": [{"associationCategory": "HUBSPOT_DEFINED",
                                          "associationTypeId": TASK_TO_DEAL}]}
            for d in deal_ids
        ],
    }
    return df.api("POST", f"/crm/objects/{df.API_VERSION}/tasks", json=payload)


def run_tasks(args):
    print("Mode: one review task per deal owner (no deal is changed)")
    print()
    results = df.collect(args.stale_days, args.pipeline)
    skipped = sum(r["skipped"] for r in results.values())
    by_owner, unowned = group_by_owner(results, args.stale_days)

    active = df.owners()
    if active is None:
        print("ABORT: could not read owners (the key needs crm.objects.owners.read).")
        print("  Tasks are assigned to owners, so nothing was created.")
        return 1
    inactive = {o: deals for o, deals in by_owner.items() if o not in active}

    plan, already = [], []
    for owner_id in sorted(o for o in by_owner if o in active):
        entries = sorted(by_owner[owner_id].values(), key=lambda e: e["deal"]["id"])
        if has_open_review_task(owner_id):
            already.append(owner_id)
            continue
        plan.append((owner_id, entries))

    plan_path = df.audit_path("cleanup-deals-execute-tasks-plan.csv")
    with open(plan_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["owner_id", "owner", "deal_id", "dealname", "findings", "action"])
        for owner_id, entries in plan:
            for e in entries:
                w.writerow([owner_id, active[owner_id], e["deal"]["id"],
                            e["deal"]["properties"].get("dealname", ""), "; ".join(e["why"]),
                            "listed in new review task"])
        for owner_id in already:
            for e in by_owner[owner_id].values():
                w.writerow([owner_id, active[owner_id], e["deal"]["id"],
                            e["deal"]["properties"].get("dealname", ""), "; ".join(e["why"]),
                            "skipped: owner already has an open review task"])
        for owner_id, deals in inactive.items():
            for e in deals.values():
                w.writerow([owner_id, "(inactive or unknown owner)", e["deal"]["id"],
                            e["deal"]["properties"].get("dealname", ""), "; ".join(e["why"]),
                            "skipped: reassign first (reassign-deactivated-owners)"])
        for e in unowned.values():
            w.writerow(["", "(no owner)", e["deal"]["id"],
                        e["deal"]["properties"].get("dealname", ""), "; ".join(e["why"]),
                        "skipped: assign an owner first (cleanup-lead-owners)"])

    print(f"  Owners to receive a review task: {len(plan)}")
    for owner_id, entries in plan:
        print(f"    {active[owner_id]}: {len(entries)} deals")
    print(f"  Owners skipped, open review task exists: {len(already)}")
    print(f"  Deals with an inactive or unknown owner: {sum(len(d) for d in inactive.values())}")
    print(f"  Deals with no owner: {len(unowned)}")
    print(f"  Salesforce-synced matches skipped: {skipped}")
    print(f"  Plan CSV (written before any change): {plan_path}")
    print()

    if not plan:
        print("No review tasks to create. Exiting.")
        return 0
    if len(plan) > TASK_ABORT_THRESHOLD:
        print(f"SAFETY ABORT: {len(plan)} tasks exceeds TASK_ABORT_THRESHOLD ({TASK_ABORT_THRESHOLD}).")
        print("  Narrow the run with --pipeline, or raise the threshold after review.")
        print("  Nothing was created.")
        return 1

    due = (datetime.datetime.now(datetime.timezone.utc)
           + datetime.timedelta(days=TASK_DUE_DAYS)).isoformat(timespec="seconds")
    print(f"About to create {len(plan)} review tasks, due in {TASK_DUE_DAYS} days.")
    if input("Type 'CREATE TASKS' to confirm: ").strip() != "CREATE TASKS":
        print("Aborted by user. Nothing was created.")
        return 0
    print()

    log_path = df.audit_path("cleanup-deals-execute-tasks.csv")
    created = 0
    with open(log_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["owner_id", "owner", "deals", "task_id", "status"])
        for owner_id, entries in plan:
            resp = create_task(owner_id, entries, due)
            ok = resp.status_code in (200, 201)
            created += ok
            task_id = resp.json().get("id", "") if ok else ""
            status = "created" if ok else f"failed ({resp.status_code})"
            w.writerow([owner_id, active[owner_id], len(entries), task_id, status])
            print(f"  {active[owner_id]}: {status}")
            time.sleep(BATCH_DELAY)

    print()
    print(f"  Tasks created: {created} of {len(plan)}")
    print(f"  Task log: {log_path}")
    print("  Undo: delete the tasks listed in the log. No deal was modified.")
    return 0 if created == len(plan) else 1


# ── Reviewed deletion ────────────────────────────────────────────

def read_marked_ids(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if "id" not in fields or "delete" not in fields:
            raise SystemExit(f"{path} needs an 'id' and a 'delete' column. Start from "
                             "cleanup-deals-before-likely-test.csv and mark rows 'yes'.")
        ids = [r["id"].strip() for r in reader
               if (r.get("delete") or "").strip().lower() in YES and r["id"].strip()]
    return list(dict.fromkeys(ids))


def run_delete(args):
    print(f"Mode: delete reviewed deals from {args.delete_from_csv}")
    print()
    ids = read_marked_ids(args.delete_from_csv)
    print(f"  Rows marked for deletion: {len(ids)}")
    if not ids:
        print("Nothing marked 'yes' in the delete column. Exiting.")
        return 0
    if len(ids) > DELETE_ABORT_THRESHOLD:
        print(f"SAFETY ABORT: {len(ids)} deals exceeds DELETE_ABORT_THRESHOLD ({DELETE_ABORT_THRESHOLD}).")
        print("  Delete in smaller reviewed batches. Nothing was deleted.")
        return 1

    found = df.batch_read(ids)
    missing = [i for i in ids if i not in found]
    synced = [i for i in ids if i in found and df.is_salesforce(found[i])]
    won = [i for i in ids if i in found and i not in synced
           and found[i]["properties"].get("hs_is_closed_won") == "true"]
    targets = [i for i in ids if i in found and i not in synced and i not in won]

    print(f"  Not found (already deleted?): {len(missing)}")
    print(f"  Refused, Salesforce-synced: {len(synced)}")
    print(f"  Refused, closed-won (would rewrite revenue history): {len(won)}")
    print(f"  Deals to delete: {len(targets)}")

    backup = df.audit_path("cleanup-deals-execute-delete-backup.csv")
    with open(backup, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id"] + df.DEAL_PROPERTIES + ["action"])
        w.writeheader()
        for i in ids:
            if i not in found:
                continue
            action = ("refused: salesforce-synced" if i in synced else
                      "refused: closed-won" if i in won else "delete")
            props = found[i].get("properties") or {}
            w.writerow({"id": i, **{p: props.get(p) or "" for p in df.DEAL_PROPERTIES},
                        "action": action})
    print(f"  Backup CSV (written before any change): {backup}")
    print()

    if not targets:
        print("No deals left to delete. Exiting.")
        return 0
    print(f"About to delete {len(targets)} deals. They stay restorable for 90 days.")
    if input("Type 'DELETE' to confirm: ").strip() != "DELETE":
        print("Aborted by user. Nothing was deleted.")
        return 0
    print()

    failed = []
    for i in range(0, len(targets), BATCH_SIZE):
        batch = targets[i:i + BATCH_SIZE]
        resp = df.api("POST", df.deals_path("/batch/archive"),
                      json={"inputs": [{"id": x} for x in batch]})
        if resp.status_code != 204:
            failed.extend(batch)
            print(f"  Batch {i // BATCH_SIZE + 1}: FAILED ({resp.status_code})")
        else:
            print(f"  Batch {i // BATCH_SIZE + 1}: deleted {len(batch)}")
        time.sleep(BATCH_DELAY)

    log_path = df.audit_path("cleanup-deals-execute-deleted.csv")
    with open(log_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["deal_id", "status"])
        for x in targets:
            w.writerow([x, "failed" if x in failed else "deleted"])

    print()
    print(f"  Deleted: {len(targets) - len(failed)}  Failed: {len(failed)}")
    print(f"  Deletion log: {log_path}")
    print("  Restore within 90 days from the deals index page (Restore records).")
    return 0 if not failed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cleanup Deals — Execute")
    parser.add_argument("--stale-days", type=int, default=df.STALE_DAYS_DEFAULT)
    parser.add_argument("--pipeline", help="limit review tasks to one pipeline ID")
    parser.add_argument("--delete-from-csv", metavar="PATH",
                        help="delete only rows marked 'yes' in this CSV's delete column")
    args = parser.parse_args(argv)
    df.authenticate()

    print("=" * 60)
    print("CLEANUP DEALS — EXECUTE")
    print("=" * 60)
    print()
    return run_delete(args) if args.delete_from_csv else run_tasks(args)


if __name__ == "__main__":
    sys.exit(main())
