# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Enrich Company Name — After State
Re-count contacts missing the company name property and measure coverage
improvement against the before-state baseline.

Run this after the enrichment workflow/script has had time to process.
"""

import csv
import os
import time

import requests
from dotenv import load_dotenv

# ── Configuration ────────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

SEARCH_URL = f"{BASE}/crm/v3/objects/contacts/search"
SAMPLE_SIZE = 200
RATE_LIMIT_PAUSE = 0.15    # seconds between paginated requests
CSV_FILE = os.path.join(os.path.dirname(__file__), "after_enrich_company_name.csv")

# Load before-state baseline if available
BEFORE_CSV = os.path.join(os.path.dirname(__file__), "before_enrich_company_name.csv")
before_missing = None
if os.path.exists(BEFORE_CSV):
    with open(BEFORE_CSV) as f:
        for row in csv.DictReader(f):
            if row["metric"] == "missing_company_name":
                before_missing = int(row["value"])

# ── Helpers ──────────────────────────────────────────────────────

def search_count(filters):
    resp = requests.post(SEARCH_URL, headers=HEADERS, json={
        "filterGroups": [{"filters": filters}],
        "limit": 1,
    })
    resp.raise_for_status()
    return resp.json().get("total", 0)


# ── Main ─────────────────────────────────────────────────────────

print("=" * 60)
print("AFTER STATE: Enrich Company Name from Association")
print("=" * 60)
print()

# Step 1 — totals
print("Step 1: Total contacts...")
resp_all = requests.get(
    f"{BASE}/crm/v3/objects/contacts", headers=HEADERS, params={"limit": 1},
)
total_contacts = resp_all.json().get("total", 0) if resp_all.status_code == 200 else 0
print(f"  Total contacts in portal: {total_contacts}")
print()

# Step 2 — missing
print("Step 2: Contacts still missing company name...")
missing_company = search_count([
    {"propertyName": "company", "operator": "NOT_HAS_PROPERTY"},
])
print(f"  Missing company name: {missing_company}")
print()

# Step 3 — has
print("Step 3: Contacts with company name...")
has_company = search_count([
    {"propertyName": "company", "operator": "HAS_PROPERTY"},
])
print(f"  Has company name: {has_company}")
print()

# Step 4 — sample remaining missing contacts
print("Step 4: Sampling remaining contacts missing company name...")

sampled = 0
has_association = 0
no_association = 0
after = None

while sampled < SAMPLE_SIZE:
    payload = {
        "filterGroups": [{"filters": [
            {"propertyName": "company", "operator": "NOT_HAS_PROPERTY"},
        ]}],
        "properties": ["email", "firstname", "lastname", "company"],
        "limit": 100,
    }
    if after:
        payload["after"] = after

    resp = requests.post(SEARCH_URL, headers=HEADERS, json=payload)
    if resp.status_code != 200:
        break

    data = resp.json()
    results = data.get("results", [])
    if not results:
        break

    for contact in results:
        cid = contact["id"]
        assoc_resp = requests.get(
            f"{BASE}/crm/v4/objects/contacts/{cid}/associations/companies",
            headers=HEADERS,
        )
        if assoc_resp.status_code == 200 and assoc_resp.json().get("results"):
            has_association += 1
        else:
            no_association += 1

        sampled += 1
        if sampled >= SAMPLE_SIZE:
            break
        time.sleep(RATE_LIMIT_PAUSE)

    after = data.get("paging", {}).get("next", {}).get("after")
    if not after:
        break

if sampled > 0:
    print(f"  Sampled: {sampled} contacts still missing company name")
    print(f"  With company association:    {has_association} "
          f"({has_association / sampled * 100:.1f}%)")
    print(f"  Without company association: {no_association} "
          f"({no_association / sampled * 100:.1f}%)")
else:
    print("  No contacts to sample (all have company name now!)")
print()

# ── CSV audit trail ──────────────────────────────────────────────
rows = [
    {"metric": "total_contacts", "value": total_contacts},
    {"metric": "missing_company_name", "value": missing_company},
    {"metric": "has_company_name", "value": has_company},
    {"metric": "sample_size", "value": sampled},
    {"metric": "sample_has_association", "value": has_association},
    {"metric": "sample_no_association", "value": no_association},
]
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["metric", "value"])
    writer.writeheader()
    writer.writerows(rows)
print(f"Audit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
print()
print("=" * 60)
print("AFTER STATE SUMMARY")
print("=" * 60)
print(f"  Total contacts: {total_contacts}")

if before_missing is not None:
    enriched = before_missing - missing_company
    print(f"  Before: {before_missing} missing company name")
    print(f"  After:  {missing_company} missing company name")
    print(f"  Enriched: {enriched} contacts "
          f"({enriched / before_missing * 100:.1f}% of originally missing)"
          if before_missing > 0 else "")
else:
    print(f"  Missing company name: {missing_company}")
    print("  (Run before.py first to capture a baseline for comparison)")

print(f"  Has company name: {has_company}")
print()

if sampled > 0 and has_association > 0:
    print(f"  WARNING: {has_association}/{sampled} sampled contacts still missing company name")
    print("  despite having a company association. The workflow may still be processing,")
    print("  or there may be company records without a name property.")
elif before_missing is not None and missing_company < before_missing:
    print("  SUCCESS: Enrichment has improved company name coverage.")
    if missing_company > 0:
        print(f"  Remaining {missing_company} contacts likely have no associated company.")
else:
    print("  NOTE: Numbers unchanged — workflow may still be processing.")
    print("  Re-run this script in a few hours.")
print("=" * 60)
