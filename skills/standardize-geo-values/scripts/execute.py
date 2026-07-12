# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Standardize Geo Values — Execute
Batch-update country and state values to full names for contacts and companies.

Mapping: abbreviations and common variants -> standardized full names.
Example: "US" / "USA" -> "United States", "NY" -> "New York"

Uses HubSpot batch update API in groups of 100 with rate-limit retry.
Exports CSV audit trail of all changes.
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

BATCH_SIZE = 100
MAX_RETRIES = 5
SAFETY_THRESHOLD = 50_000  # abort if any single mapping exceeds this
PAGINATE_DELAY = 0.15      # seconds between paginated requests
BATCH_DELAY = 0.5          # seconds between batch operations
CSV_FILE = os.path.join("data", "audit-logs", "execute_standardize_geo.csv")

# ── Mapping tables ───────────────────────────────────────────────

COUNTRY_FIXES = {
    "US": "United States",
    "USA": "United States",
    "U.S.": "United States",
    "U.S.A.": "United States",
    "America": "United States",
    "UK": "United Kingdom",
    "GB": "United Kingdom",
    "Great Britain": "United Kingdom",
    "England": "United Kingdom",
    "CA": "Canada",
    "IN": "India",
    "AU": "Australia",
    "DE": "Germany",
    "Deutschland": "Germany",
    "FR": "France",
    "BR": "Brazil",
    "Brasil": "Brazil",
    "IL": "Israel",
    "MX": "Mexico",
    "JP": "Japan",
    "SG": "Singapore",
    "NL": "Netherlands",
    "CH": "Switzerland",
    "IT": "Italy",
    "ES": "Spain",
    "SE": "Sweden",
    "IE": "Ireland",
}

STATE_FIXES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

# ── Helpers ──────────────────────────────────────────────────────

def search_all_ids(search_url, filters):
    """Collect all matching record IDs via paginated search with retry on 429.
    Stops at the HubSpot 10K search-result hard limit.
    """
    all_ids = []
    after = None
    while True:
        payload = {
            "filterGroups": [{"filters": filters}],
            "properties": ["hs_object_id"],
            "limit": 100,
        }
        if after:
            payload["after"] = after

        for attempt in range(MAX_RETRIES):
            resp = requests.post(search_url, headers=HEADERS, json=payload)
            if resp.status_code == 429:
                wait = min(10 * (attempt + 1), 30)
                print(f"      Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        else:
            resp.raise_for_status()

        data = resp.json()
        all_ids.extend(r["id"] for r in data.get("results", []))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
        time.sleep(PAGINATE_DELAY)
    return all_ids


def batch_update(object_type, ids, properties):
    """Batch update records. Returns (success_count, failed_ids)."""
    update_url = f"{BASE}/crm/v3/objects/{object_type}/batch/update"
    success = 0
    failed = []
    total_batches = (len(ids) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(ids), BATCH_SIZE):
        batch = ids[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        payload = {
            "inputs": [{"id": rid, "properties": properties} for rid in batch]
        }
        print(f"    Batch {batch_num}/{total_batches}: "
              f"updating {len(batch)} records...", end=" ")

        for attempt in range(MAX_RETRIES):
            resp = requests.post(update_url, headers=HEADERS, json=payload)
            if resp.status_code == 429:
                wait = min(10 * (attempt + 1), 30)
                print(f"rate limited, waiting {wait}s...", end=" ")
                time.sleep(wait)
                continue
            break

        if resp.status_code in (200, 201):
            success += len(batch)
            print("OK")
        else:
            failed.extend(batch)
            print(f"FAILED ({resp.status_code}: {resp.text[:200]})")
        time.sleep(BATCH_DELAY)

    return success, failed


# ── Main ─────────────────────────────────────────────────────────

print("=" * 60)
print("EXECUTE: Standardize Country & State Values")
print("=" * 60)
print()

audit_log = []

# =====================================================
# STEP 1: Contact countries
# =====================================================
print("STEP 1: Standardize contact country values")
print("-" * 40)

contact_search_url = f"{BASE}/crm/v3/objects/contacts/search"
total_contact_country_fixed = 0
total_contact_country_failed = 0

for variant, correct in COUNTRY_FIXES.items():
    ids = search_all_ids(contact_search_url, [
        {"propertyName": "country", "operator": "EQ", "value": variant},
    ])
    if not ids:
        continue

    if len(ids) > SAFETY_THRESHOLD:
        print(f"  SAFETY: '{variant}' has {len(ids)} contacts — exceeds threshold "
              f"({SAFETY_THRESHOLD}). Skipping.")
        continue

    print(f"  '{variant}' -> '{correct}': {len(ids)} contacts")
    ok, bad = batch_update("contacts", ids, {"country": correct})
    total_contact_country_fixed += ok
    total_contact_country_failed += len(bad)
    audit_log.append({
        "object": "contact", "field": "country",
        "from": variant, "to": correct,
        "found": len(ids), "updated": ok, "failed": len(bad),
    })

print(f"\n  Contact country: {total_contact_country_fixed} fixed, "
      f"{total_contact_country_failed} failed\n")

# =====================================================
# STEP 2: Company countries
# =====================================================
print("STEP 2: Standardize company country values")
print("-" * 40)

company_search_url = f"{BASE}/crm/v3/objects/companies/search"
total_company_country_fixed = 0
total_company_country_failed = 0

for variant, correct in COUNTRY_FIXES.items():
    ids = search_all_ids(company_search_url, [
        {"propertyName": "country", "operator": "EQ", "value": variant},
    ])
    if not ids:
        continue

    if len(ids) > SAFETY_THRESHOLD:
        print(f"  SAFETY: '{variant}' has {len(ids)} companies — exceeds threshold. Skipping.")
        continue

    print(f"  '{variant}' -> '{correct}': {len(ids)} companies")
    ok, bad = batch_update("companies", ids, {"country": correct})
    total_company_country_fixed += ok
    total_company_country_failed += len(bad)
    audit_log.append({
        "object": "company", "field": "country",
        "from": variant, "to": correct,
        "found": len(ids), "updated": ok, "failed": len(bad),
    })

print(f"\n  Company country: {total_company_country_fixed} fixed, "
      f"{total_company_country_failed} failed\n")

# =====================================================
# STEP 3: Contact states
# =====================================================
print("STEP 3: Standardize contact state values")
print("-" * 40)

total_state_fixed = 0
total_state_failed = 0

for abbrev, full_name in STATE_FIXES.items():
    ids = search_all_ids(contact_search_url, [
        {"propertyName": "state", "operator": "EQ", "value": abbrev},
    ])
    if not ids:
        continue

    if len(ids) > SAFETY_THRESHOLD:
        print(f"  SAFETY: '{abbrev}' has {len(ids)} contacts — exceeds threshold. Skipping.")
        continue

    print(f"  '{abbrev}' -> '{full_name}': {len(ids)} contacts")
    ok, bad = batch_update("contacts", ids, {"state": full_name})
    total_state_fixed += ok
    total_state_failed += len(bad)
    audit_log.append({
        "object": "contact", "field": "state",
        "from": abbrev, "to": full_name,
        "found": len(ids), "updated": ok, "failed": len(bad),
    })

print(f"\n  Contact state: {total_state_fixed} fixed, "
      f"{total_state_failed} failed\n")

# ── CSV audit trail ──────────────────────────────────────────────
os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["object", "field", "from", "to", "found", "updated", "failed"],
    )
    writer.writeheader()
    writer.writerows(audit_log)
print(f"Audit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
grand_total = total_contact_country_fixed + total_company_country_fixed + total_state_fixed
grand_failed = total_contact_country_failed + total_company_country_failed + total_state_failed

print()
print("=" * 60)
print("EXECUTION SUMMARY")
print("=" * 60)
print(f"  Contact countries fixed:  {total_contact_country_fixed}")
print(f"  Company countries fixed:  {total_company_country_fixed}")
print(f"  Contact states fixed:     {total_state_fixed}")
print(f"  Total records updated:    {grand_total}")
print(f"  Total failures:           {grand_failed}")
print("=" * 60)
