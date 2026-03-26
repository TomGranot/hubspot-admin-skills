# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Standardize Geo Values — After State
Verify that country and state standardization was successful.
Re-checks all known abbreviations — counts should be zero.

Outputs:
  1. Any remaining non-standard values (should be 0)
  2. Current value distribution for contacts and companies
  3. CSV audit trail: after_standardize_geo.csv
"""

import csv
import os

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

CSV_FILE = os.path.join(os.path.dirname(__file__), "after_standardize_geo.csv")

# ── Helpers ──────────────────────────────────────────────────────

def search_count(search_url, filters):
    resp = requests.post(search_url, headers=HEADERS, json={
        "filterGroups": [{"filters": filters}],
        "limit": 1,
    })
    resp.raise_for_status()
    return resp.json().get("total", 0)


url_contacts = f"{BASE}/crm/v3/objects/contacts/search"
url_companies = f"{BASE}/crm/v3/objects/companies/search"

# ── Main ─────────────────────────────────────────────────────────

print("=" * 60)
print("AFTER STATE: Verify Country & State Standardization")
print("=" * 60)
print()

audit_rows = []
all_ok = True

# Known abbreviations that should now be zero
country_abbrevs = [
    "US", "USA", "U.S.", "U.S.A.", "America",
    "UK", "GB", "Great Britain", "England",
    "CA", "IN", "AU", "DE", "Deutschland",
    "FR", "BR", "Brasil", "IL", "MX", "JP",
    "SG", "NL", "CH", "IT", "ES", "SE", "IE",
]

state_abbrevs = [
    "NY", "CA", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "NJ",
    "VA", "WA", "MA", "AZ", "CO", "MD", "MN", "MO", "WI", "CT",
    "OR", "SC", "LA", "TN", "IN", "MI", "DC", "UT", "NV", "AL",
]

# ── Contact country check ───────────────────────────────────────
print("CONTACT COUNTRY — Remaining non-standard values")
print("-" * 40)

remaining_contact_country = 0
for abbrev in country_abbrevs:
    count = search_count(url_contacts, [
        {"propertyName": "country", "operator": "EQ", "value": abbrev},
    ])
    if count > 0:
        print(f"  STILL PRESENT: {abbrev!r}: {count} contacts")
        remaining_contact_country += count
        all_ok = False
        audit_rows.append({
            "object": "contact", "field": "country",
            "value": abbrev, "remaining": count, "status": "FAIL",
        })

if remaining_contact_country == 0:
    print("  All contact country abbreviations cleared.")
print()

# ── Company country check ────────────────────────────────────────
print("COMPANY COUNTRY — Remaining non-standard values")
print("-" * 40)

remaining_company_country = 0
for abbrev in country_abbrevs:
    count = search_count(url_companies, [
        {"propertyName": "country", "operator": "EQ", "value": abbrev},
    ])
    if count > 0:
        print(f"  STILL PRESENT: {abbrev!r}: {count} companies")
        remaining_company_country += count
        all_ok = False
        audit_rows.append({
            "object": "company", "field": "country",
            "value": abbrev, "remaining": count, "status": "FAIL",
        })

if remaining_company_country == 0:
    print("  All company country abbreviations cleared.")
print()

# ── Contact state check ─────────────────────────────────────────
print("CONTACT STATE — Remaining abbreviations")
print("-" * 40)

remaining_state = 0
for abbrev in state_abbrevs:
    count = search_count(url_contacts, [
        {"propertyName": "state", "operator": "EQ", "value": abbrev},
    ])
    if count > 0:
        print(f"  STILL PRESENT: {abbrev!r}: {count} contacts")
        remaining_state += count
        all_ok = False
        audit_rows.append({
            "object": "contact", "field": "state",
            "value": abbrev, "remaining": count, "status": "FAIL",
        })

if remaining_state == 0:
    print("  All contact state abbreviations cleared.")
print()

# ── Current standardized values ──────────────────────────────────
print("CURRENT STANDARDIZED VALUES (top countries)")
print("-" * 40)

standard_countries = [
    "United States", "United Kingdom", "Canada", "India", "Australia",
    "Germany", "France", "Brazil", "Israel", "Mexico",
]

print("  Contacts:")
for country in standard_countries:
    count = search_count(url_contacts, [
        {"propertyName": "country", "operator": "EQ", "value": country},
    ])
    if count > 0:
        print(f"    {country}: {count}")
print()

print("  Companies:")
for country in standard_countries:
    count = search_count(url_companies, [
        {"propertyName": "country", "operator": "EQ", "value": country},
    ])
    if count > 0:
        print(f"    {country}: {count}")
print()

# ── CSV audit trail ──────────────────────────────────────────────
if not audit_rows:
    audit_rows.append({
        "object": "all", "field": "all",
        "value": "none", "remaining": 0, "status": "PASS",
    })

with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["object", "field", "value", "remaining", "status"],
    )
    writer.writeheader()
    writer.writerows(audit_rows)
print(f"Audit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
print()
print("=" * 60)
if all_ok:
    print("PASS — All country and state values are standardized.")
else:
    print("FAIL — Some non-standard values remain. Review output above.")
    print(f"  Remaining contact country issues: {remaining_contact_country}")
    print(f"  Remaining company country issues: {remaining_company_country}")
    print(f"  Remaining contact state issues:   {remaining_state}")
print("=" * 60)
