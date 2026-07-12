# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Enrich Industry — After State
Verify that contact industry enrichment worked.

Checks:
  1. Count of contacts with industry (should be significantly higher)
  2. Count still missing
  3. Spot-check: sample contacts with industry and verify it matches company
  4. Industry distribution on contacts (top 15)
  5. CSV audit trail: after_enrich_industry.csv
"""

import csv
import os
import time
from collections import Counter

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

SEARCH_URL = f"{BASE}/crm/v3/objects/contacts/search"
CSV_FILE = os.path.join("data", "audit-logs", "after_enrich_industry.csv")
PAGINATE_DELAY = 0.15  # seconds between paginated requests

# Load before-state baseline
BEFORE_CSV = os.path.join("data", "audit-logs", "before_enrich_industry.csv")
before_has_industry = None
if os.path.exists(BEFORE_CSV):
    os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
    with open(BEFORE_CSV) as f:
        for row in csv.DictReader(f):
            if row["metric"] == "has_industry":
                before_has_industry = int(row["value"])

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
print("AFTER STATE: Verify Contact Industry Enrichment")
print("=" * 60)
print()

# Step 1 — contacts with industry
print("Step 1: Contacts with industry populated...")
has_industry = search_count([
    {"propertyName": "industry", "operator": "HAS_PROPERTY"},
])
print(f"  Has industry: {has_industry}")
if before_has_industry is not None:
    print(f"  Before: {before_has_industry}")
    print(f"  Delta: +{has_industry - before_has_industry}")
print()

# Step 2 — contacts missing industry
print("Step 2: Contacts still missing industry...")
missing_industry = search_count([
    {"propertyName": "industry", "operator": "NOT_HAS_PROPERTY"},
])
print(f"  Still missing industry: {missing_industry}")
print()

# Step 3 — spot-check: verify contact industry matches company
print("Step 3: Spot-check — verifying contact industry matches associated company...")

resp_sample = requests.post(SEARCH_URL, headers=HEADERS, json={
    "filterGroups": [{"filters": [
        {"propertyName": "industry", "operator": "HAS_PROPERTY"},
    ]}],
    "properties": ["email", "firstname", "lastname", "industry"],
    "limit": 20,
})
resp_sample.raise_for_status()
samples = resp_sample.json().get("results", [])

matches = 0
mismatches = 0
no_company = 0

for contact in samples:
    cid = contact["id"]
    contact_industry = contact.get("properties", {}).get("industry", "")

    assoc_resp = requests.get(
        f"{BASE}/crm/v4/objects/contacts/{cid}/associations/companies",
        headers=HEADERS,
    )
    if assoc_resp.status_code != 200:
        no_company += 1
        continue

    assoc_results = assoc_resp.json().get("results", [])
    if not assoc_results:
        no_company += 1
        continue

    company_id = assoc_results[0]["toObjectId"]
    comp_resp = requests.get(
        f"{BASE}/crm/v3/objects/companies/{company_id}",
        headers=HEADERS,
        params={"properties": "industry"},
    )
    if comp_resp.status_code != 200:
        no_company += 1
        continue

    comp_industry = comp_resp.json().get("properties", {}).get("industry", "")
    name = f"{contact.get('properties', {}).get('firstname', '')} " \
           f"{contact.get('properties', {}).get('lastname', '')}".strip()

    if contact_industry == comp_industry:
        matches += 1
        print(f"  MATCH: {name or cid} — {contact_industry}")
    else:
        mismatches += 1
        print(f"  MISMATCH: {name or cid} — contact: {contact_industry}, "
              f"company: {comp_industry}")

    time.sleep(PAGINATE_DELAY)

print()
print(f"  Spot-check results: {matches} matches, {mismatches} mismatches, "
      f"{no_company} no company")
print()

# Step 4 — industry distribution (top 15)
print("Step 4: Contact industry distribution (top 15)...")

industry_counts = Counter()
after_cursor = None
pages_fetched = 0
max_pages = 50  # sample up to 5000 contacts

while pages_fetched < max_pages:
    payload = {
        "filterGroups": [{"filters": [
            {"propertyName": "industry", "operator": "HAS_PROPERTY"},
        ]}],
        "properties": ["industry"],
        "limit": 100,
    }
    if after_cursor:
        payload["after"] = after_cursor

    resp = requests.post(SEARCH_URL, headers=HEADERS, json=payload)
    if resp.status_code != 200:
        break

    data = resp.json()
    for contact in data.get("results", []):
        ind = contact.get("properties", {}).get("industry", "")
        if ind:
            industry_counts[ind] += 1

    after_cursor = data.get("paging", {}).get("next", {}).get("after")
    if not after_cursor:
        break

    pages_fetched += 1
    time.sleep(PAGINATE_DELAY)

print(f"  (Sampled {sum(industry_counts.values())} contacts with industry)")
print()
for industry, count in industry_counts.most_common(15):
    print(f"  {industry}: {count}")

# ── CSV audit trail ──────────────────────────────────────────────
rows = [
    {"metric": "has_industry", "value": has_industry},
    {"metric": "missing_industry", "value": missing_industry},
    {"metric": "spot_check_matches", "value": matches},
    {"metric": "spot_check_mismatches", "value": mismatches},
    {"metric": "spot_check_no_company", "value": no_company},
]
for industry, count in industry_counts.most_common(15):
    rows.append({"metric": f"industry_{industry}", "value": count})

with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["metric", "value"])
    writer.writeheader()
    writer.writerows(rows)
print()
print(f"Audit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
print()
print("=" * 60)
print("AFTER STATE SUMMARY")
print("=" * 60)
if before_has_industry is not None:
    print(f"  Contacts with industry: {has_industry} "
          f"(was {before_has_industry}, delta +{has_industry - before_has_industry})")
else:
    print(f"  Contacts with industry: {has_industry}")
print(f"  Contacts missing industry: {missing_industry}")
print(f"  Spot-check: {matches}/{matches + mismatches} matched company industry")
