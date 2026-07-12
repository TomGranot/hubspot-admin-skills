# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Fix Lifecycle Stages — After State
Verify that zero contacts and companies remain in disallowed lifecycle stages.

Disallowed: Subscriber, Other, Evangelist, (empty)

Outputs:
  1. Full lifecycle stage distribution (should show 0 for all disallowed)
  2. PASS/FAIL verdict
  3. CSV audit trail: after_fix_lifecycle.csv
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

CSV_FILE = os.path.join("data", "audit-logs", "after_fix_lifecycle.csv")

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
print("AFTER STATE: Lifecycle Stage Verification")
print("=" * 60)
print()

all_ok = True
audit_rows = []

for obj_type, obj_label in [("contacts", "CONTACTS"), ("companies", "COMPANIES")]:
    print(f"{obj_label}")
    print("-" * 40)

    totals = {}
    for stage in ALL_STAGES:
        count = search_count(obj_type, [{
            "propertyName": "lifecyclestage",
            "operator": "EQ",
            "value": stage,
        }])
        totals[stage] = count

    empty_count = search_count(obj_type, [{
        "propertyName": "lifecyclestage",
        "operator": "NOT_HAS_PROPERTY",
    }])
    totals["(empty)"] = empty_count

    grand_total = sum(totals.values())

    for stage, count in sorted(totals.items(), key=lambda x: -x[1]):
        label = STAGE_LABELS.get(stage, stage)
        pct = (count / grand_total * 100) if grand_total else 0
        status = ""
        if stage in DISALLOWED_STAGES or stage == "(empty)":
            if count > 0:
                status = " STILL PRESENT"
                all_ok = False
            else:
                status = " CLEAR"
        print(f"  {label:.<30} {count:>8,} ({pct:5.1f}%){status}")
        audit_rows.append({
            "object": obj_type, "stage": stage, "label": label,
            "count": count, "status": "FAIL" if (
                (stage in DISALLOWED_STAGES or stage == "(empty)") and count > 0
            ) else "OK",
        })

    print(f"  {'TOTAL':.<30} {grand_total:>8,}")
    print()

# ── CSV audit trail ──────────────────────────────────────────────
os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["object", "stage", "label", "count", "status"],
    )
    writer.writeheader()
    writer.writerows(audit_rows)
print(f"Audit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
print()
print("=" * 60)
if all_ok:
    print("PASS — All disallowed lifecycle stages are empty.")
else:
    print("FAIL — Some disallowed stages still have records. Investigate.")
print("=" * 60)
print()
print("Recommended: Create guard-rail workflows in HubSpot UI:")
print("  1. Contact workflow: if lifecycle = Subscriber/Other/Evangelist/(empty)")
print("     -> clear lifecycle stage -> set to Lead")
print("     (Re-enrollment: ON)")
print("  2. Company workflow: same logic")
