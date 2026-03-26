# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Enrich Company Name — Before State
Count contacts missing the company name property and estimate how many
are fixable by copying the name from an associated company record.

Outputs:
  1. Total contacts in the portal
  2. Contacts missing the company property
  3. Sample-based estimate of fixable vs unfixable (has/lacks association)
  4. CSV audit trail: before_enrich_company_name.csv
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
SAMPLE_SIZE = 500          # contacts to sample for association check
RATE_LIMIT_PAUSE = 0.15    # seconds between paginated requests
CSV_FILE = os.path.join(os.path.dirname(__file__), "before_enrich_company_name.csv")

# ── Helpers ──────────────────────────────────────────────────────

def search_count(filters):
    """Return the total count of contacts matching *filters*."""
    resp = requests.post(SEARCH_URL, headers=HEADERS, json={
        "filterGroups": [{"filters": filters}],
        "limit": 1,
    })
    resp.raise_for_status()
    return resp.json().get("total", 0)


# ── Main ─────────────────────────────────────────────────────────

print("=" * 60)
print("BEFORE STATE: Enrich Company Name from Association")
print("=" * 60)
print()

# Step 1 — total contacts
print("Step 1: Total contacts...")
resp_all = requests.get(
    f"{BASE}/crm/v3/objects/contacts", headers=HEADERS, params={"limit": 1},
)
total_contacts = resp_all.json().get("total", 0) if resp_all.status_code == 200 else 0
print(f"  Total contacts in portal: {total_contacts}")
print()

# Step 2 — contacts missing company
print("Step 2: Contacts missing company name...")
missing_company = search_count([
    {"propertyName": "company", "operator": "NOT_HAS_PROPERTY"},
])
print(f"  Missing company name: {missing_company}")
print()

# Step 3 — contacts with company
print("Step 3: Contacts with company name...")
has_company = search_count([
    {"propertyName": "company", "operator": "HAS_PROPERTY"},
])
print(f"  Has company name: {has_company}")
print()

# Step 4 — sample missing contacts, check associations
print(f"Step 4: Sampling up to {SAMPLE_SIZE} contacts missing company name "
      f"to check company associations...")

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
        print(f"  Search error {resp.status_code} — stopping sample.")
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

print(f"  Sampled: {sampled} contacts missing company name")
if sampled > 0:
    print(f"  With company association:    {has_association} "
          f"({has_association / sampled * 100:.1f}%)")
    print(f"  Without company association: {no_association} "
          f"({no_association / sampled * 100:.1f}%)")
print()

# Extrapolate
est_fixable = int(missing_company * has_association / sampled) if sampled > 0 else 0
est_unfixable = missing_company - est_fixable

print(f"  Estimated fixable (has association): ~{est_fixable}")
print(f"  Estimated not fixable (no association): ~{est_unfixable}")
print()

# ── CSV audit trail ──────────────────────────────────────────────
rows = [
    {"metric": "total_contacts", "value": total_contacts},
    {"metric": "missing_company_name", "value": missing_company},
    {"metric": "has_company_name", "value": has_company},
    {"metric": "sample_size", "value": sampled},
    {"metric": "sample_has_association", "value": has_association},
    {"metric": "sample_no_association", "value": no_association},
    {"metric": "est_fixable", "value": est_fixable},
    {"metric": "est_unfixable", "value": est_unfixable},
]
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["metric", "value"])
    writer.writeheader()
    writer.writerows(rows)
print(f"Audit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
print()
print("=" * 60)
print("BEFORE STATE SUMMARY")
print("=" * 60)
print(f"  Total contacts:          {total_contacts}")
if total_contacts > 0:
    print(f"  Missing company name:    {missing_company} "
          f"({missing_company / total_contacts * 100:.1f}%)")
else:
    print(f"  Missing company name:    {missing_company}")
print(f"  Has company name:        {has_company}")
print(f"  Estimated fixable:       ~{est_fixable}")
print(f"  Estimated not fixable:   ~{est_unfixable}")
print()
print("  This process copies the company name from the associated company")
print("  record onto the contact. It can be done via API batch update or")
print("  via a HubSpot workflow (Copy property action).")
