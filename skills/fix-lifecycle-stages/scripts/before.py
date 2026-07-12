# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Fix Lifecycle Stages — Before State
Audit lifecycle stage distribution for contacts and companies.
Identify records in disallowed stages and records with no lifecycle stage.

Allowed stages: Lead, MQL, SQL, Opportunity, Customer, Partner
Disallowed stages (will be moved to Lead): Subscriber, Other, Evangelist, (empty)

Outputs:
  1. Full lifecycle stage distribution for contacts and companies
  2. Count of records needing correction
  3. CSV audit trail: before_fix_lifecycle.csv
"""

import csv
import os

import requests
from dotenv import load_dotenv

# ── Configuration ────────────────────────────────────────────────
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

DISALLOWED_STAGES = ["subscriber", "other", "evangelist"]
ALLOWED_STAGES = [
    "lead", "marketingqualifiedlead", "salesqualifiedlead",
    "opportunity", "customer", "partner",
]
ALL_STAGES = ALLOWED_STAGES + DISALLOWED_STAGES

STAGE_LABELS = {
    "subscriber": "Subscriber",
    "lead": "Lead",
    "marketingqualifiedlead": "MQL",
    "salesqualifiedlead": "SQL",
    "opportunity": "Opportunity",
    "customer": "Customer",
    "evangelist": "Evangelist",
    "other": "Other",
    "partner": "Partner",
    "(empty)": "(empty)",
}

CSV_FILE = os.path.join("data", "audit-logs", "before_fix_lifecycle.csv")

# ── Helpers ──────────────────────────────────────────────────────

def search_count(object_type, filters):
    body = {
        "filterGroups": [{"filters": filters}],
        "properties": ["lifecyclestage"],
        "limit": 1,
    }
    resp = requests.post(
        f"{BASE}/crm/v3/objects/{object_type}/search",
        headers=HEADERS, json=body,
    )
    resp.raise_for_status()
    return resp.json()["total"]


# ── Main ─────────────────────────────────────────────────────────

print("=" * 60)
print("BEFORE STATE: Lifecycle Stage Audit")
print("=" * 60)
print()

audit_rows = []

for obj_type, obj_label in [("contacts", "CONTACTS"), ("companies", "COMPANIES")]:
    print(f"{obj_label} — Lifecycle Stage Distribution")
    print("-" * 40)

    totals = {}
    for stage in ALL_STAGES:
        count = search_count(obj_type, [{
            "propertyName": "lifecyclestage",
            "operator": "EQ",
            "value": stage,
        }])
        totals[stage] = count

    # Empty lifecycle stage
    empty_count = search_count(obj_type, [{
        "propertyName": "lifecyclestage",
        "operator": "NOT_HAS_PROPERTY",
    }])
    totals["(empty)"] = empty_count

    grand_total = sum(totals.values())

    for stage, count in sorted(totals.items(), key=lambda x: -x[1]):
        label = STAGE_LABELS.get(stage, stage)
        pct = (count / grand_total * 100) if grand_total else 0
        marker = ""
        if stage in DISALLOWED_STAGES or stage == "(empty)":
            marker = " <-- DISALLOWED"
        print(f"  {label:.<30} {count:>8,} ({pct:5.1f}%){marker}")
        audit_rows.append({
            "object": obj_type, "stage": stage, "label": label,
            "count": count, "disallowed": stage in DISALLOWED_STAGES or stage == "(empty)",
        })

    print(f"  {'TOTAL':.<30} {grand_total:>8,}")
    print()

    to_fix = sum(totals.get(s, 0) for s in DISALLOWED_STAGES) + totals.get("(empty)", 0)
    print(f"  {obj_label.title()} to fix (move to Lead): {to_fix:,}")
    print()

# ── CSV audit trail ──────────────────────────────────────────────
os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["object", "stage", "label", "count", "disallowed"],
    )
    writer.writeheader()
    writer.writerows(audit_rows)
print(f"Audit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
contacts_to_fix = sum(
    row["count"] for row in audit_rows
    if row["object"] == "contacts" and row["disallowed"]
)
companies_to_fix = sum(
    row["count"] for row in audit_rows
    if row["object"] == "companies" and row["disallowed"]
)

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  Contacts to move to Lead:  {contacts_to_fix:,}")
print(f"  Companies to move to Lead: {companies_to_fix:,}")
print(f"  Total records to fix:      {contacts_to_fix + companies_to_fix:,}")
print()
print("Allowed stages: Lead, MQL, SQL, Opportunity, Customer, Partner")
print("Disallowed stages: Subscriber, Other, Evangelist, (empty)")
print()
print("IMPORTANT: HubSpot lifecycle stages are forward-only.")
print("To move a record backward, you must first CLEAR the property,")
print("then SET the new value. The execute script handles this.")
