# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Enrich Industry — Before State
Count contacts missing the industry property and estimate how many can be
enriched by copying the value from an associated company record.

Also checks the 'industry' property on contacts vs the alternate
'industry_name' property some portals use (custom property).

Outputs:
  1. Contacts with / without industry
  2. Sample-based estimate of fixable contacts (company has industry)
  3. CSV audit trail: before_enrich_industry.csv
"""

import csv
import os
import time

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
SAMPLE_SIZE = 300
RATE_LIMIT_PAUSE = 0.15    # seconds between paginated requests
CSV_FILE = os.path.join("data", "audit-logs", "before_enrich_industry.csv")

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
print("BEFORE STATE: Enrich Contact Industry from Company")
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

# Step 2 — contacts with industry
print("Step 2: Contacts with 'industry' property populated...")
has_industry = search_count([
    {"propertyName": "industry", "operator": "HAS_PROPERTY"},
])
print(f"  Has industry: {has_industry}")
print()

# Step 3 — contacts missing industry
print("Step 3: Contacts missing 'industry' property...")
missing_industry = search_count([
    {"propertyName": "industry", "operator": "NOT_HAS_PROPERTY"},
])
print(f"  Missing industry: {missing_industry}")
print()

# Step 3b — check for alternate 'industry_name' custom property
print("Step 3b: Checking for alternate 'industry_name' custom property...")
prop_resp = requests.get(
    f"{BASE}/crm/v3/properties/contacts/industry_name", headers=HEADERS,
)
if prop_resp.status_code == 200:
    has_industry_name = search_count([
        {"propertyName": "industry_name", "operator": "HAS_PROPERTY"},
    ])
    print(f"  'industry_name' property exists. Contacts with value: {has_industry_name}")
else:
    has_industry_name = 0
    print("  'industry_name' property does not exist in this portal.")
print()

# Step 4 — sample contacts missing industry, check company associations
print(f"Step 4: Sampling up to {SAMPLE_SIZE} contacts missing industry...")

sampled = 0
has_company_with_industry = 0
has_company_no_industry = 0
no_company = 0
after = None

while sampled < SAMPLE_SIZE:
    payload = {
        "filterGroups": [{"filters": [
            {"propertyName": "industry", "operator": "NOT_HAS_PROPERTY"},
        ]}],
        "properties": ["email", "firstname", "lastname", "industry"],
        "limit": 100,
    }
    if after:
        payload["after"] = after

    resp = requests.post(SEARCH_URL, headers=HEADERS, json=payload)
    if resp.status_code != 200:
        print(f"  Search API error: {resp.status_code}")
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
        if assoc_resp.status_code == 200:
            assoc_results = assoc_resp.json().get("results", [])
            if assoc_results:
                company_id = assoc_results[0]["toObjectId"]
                comp_resp = requests.get(
                    f"{BASE}/crm/v3/objects/companies/{company_id}",
                    headers=HEADERS,
                    params={"properties": "industry"},
                )
                if comp_resp.status_code == 200:
                    comp_industry = comp_resp.json().get("properties", {}).get("industry")
                    if comp_industry:
                        has_company_with_industry += 1
                    else:
                        has_company_no_industry += 1
                else:
                    has_company_no_industry += 1
            else:
                no_company += 1
        else:
            no_company += 1

        sampled += 1
        if sampled >= SAMPLE_SIZE:
            break
        time.sleep(RATE_LIMIT_PAUSE)

    after = data.get("paging", {}).get("next", {}).get("after")
    if not after:
        break

if sampled > 0:
    print(f"  Sampled: {sampled} contacts missing industry")
    print(f"  Company has industry:     {has_company_with_industry} "
          f"({has_company_with_industry / sampled * 100:.1f}%)")
    print(f"  Company missing industry: {has_company_no_industry} "
          f"({has_company_no_industry / sampled * 100:.1f}%)")
    print(f"  No company association:   {no_company} "
          f"({no_company / sampled * 100:.1f}%)")
print()

est_fixable = int(missing_industry * has_company_with_industry / sampled) if sampled > 0 else 0
print(f"  Estimated fixable contacts: ~{est_fixable}")
print()

# ── CSV audit trail ──────────────────────────────────────────────
rows = [
    {"metric": "total_contacts", "value": total_contacts},
    {"metric": "has_industry", "value": has_industry},
    {"metric": "missing_industry", "value": missing_industry},
    {"metric": "has_industry_name_property", "value": has_industry_name},
    {"metric": "sample_size", "value": sampled},
    {"metric": "sample_company_has_industry", "value": has_company_with_industry},
    {"metric": "sample_company_no_industry", "value": has_company_no_industry},
    {"metric": "sample_no_company", "value": no_company},
    {"metric": "est_fixable", "value": est_fixable},
]
os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
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
print(f"  Total contacts: {total_contacts}")
print(f"  Has industry: {has_industry}")
print(f"  Missing industry: {missing_industry}")
print(f"  Sample-based estimate:")
print(f"    Fixable (company has industry):  ~{est_fixable}")
print(f"    Not fixable:                     ~{missing_industry - est_fixable}")
print()
print("  This process copies the industry value from the associated")
print("  company record to the contact record via API batch updates.")
