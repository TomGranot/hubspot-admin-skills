# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Standardize Geo Values — Before State
Audit current country and state values for contacts and companies.
Shows unique variant values (abbreviations, misspellings) and counts.

Outputs:
  1. Contact country value breakdown
  2. Company country value breakdown
  3. Contact state abbreviation counts
  4. CSV audit trail: before_standardize_geo.csv
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

CSV_FILE = os.path.join("data", "audit-logs", "before_standardize_geo.csv")

# ── Helpers ──────────────────────────────────────────────────────

def search_count(search_url, filters):
    """Run a search and return the total count."""
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
print("BEFORE STATE: Standardize Country & State Values")
print("=" * 60)
print()

audit_rows = []

# =====================================================
# CONTACT COUNTRY VALUES
# =====================================================
print("CONTACT COUNTRY VALUES")
print("-" * 40)

# Known country variants to check
country_variants = [
    "United States", "US", "USA", "U.S.", "U.S.A.", "America",
    "United Kingdom", "UK", "GB", "Great Britain", "England",
    "Canada", "CA",
    "India", "IN",
    "Australia", "AU",
    "Germany", "DE", "Deutschland",
    "France", "FR",
    "Brazil", "BR", "Brasil",
    "Israel", "IL",
    "Mexico", "MX",
    "Japan", "JP",
    "Singapore", "SG",
    "Netherlands", "NL",
    "Switzerland", "CH",
    "Italy", "IT",
    "Spain", "ES",
    "Sweden", "SE",
    "Ireland", "IE",
]

ABBREVIATIONS = {
    "US", "USA", "U.S.", "U.S.A.", "America", "UK", "GB",
    "Great Britain", "England", "CA", "IN", "AU", "DE",
    "Deutschland", "FR", "BR", "Brasil", "IL", "MX", "JP",
    "SG", "NL", "CH", "IT", "ES", "SE", "IE",
}

contact_country_counts = {}
for variant in country_variants:
    count = search_count(url_contacts, [
        {"propertyName": "country", "operator": "EQ", "value": variant},
    ])
    if count > 0:
        contact_country_counts[variant] = count

blank_country = search_count(url_contacts, [
    {"propertyName": "country", "operator": "NOT_HAS_PROPERTY"},
])
has_country = search_count(url_contacts, [
    {"propertyName": "country", "operator": "HAS_PROPERTY"},
])

print(f"  Contacts with country set: {has_country}")
print(f"  Contacts with blank country: {blank_country}")
print()
print("  Country value breakdown:")
for variant, count in sorted(contact_country_counts.items(), key=lambda x: -x[1]):
    flag = " <-- NEEDS STANDARDIZATION" if variant in ABBREVIATIONS else ""
    print(f"    {variant!r}: {count}{flag}")
    audit_rows.append({
        "object": "contact", "field": "country",
        "value": variant, "count": count,
        "needs_fix": variant in ABBREVIATIONS,
    })
print()

# =====================================================
# COMPANY COUNTRY VALUES
# =====================================================
print("COMPANY COUNTRY VALUES")
print("-" * 40)

company_country_counts = {}
for variant in country_variants:
    count = search_count(url_companies, [
        {"propertyName": "country", "operator": "EQ", "value": variant},
    ])
    if count > 0:
        company_country_counts[variant] = count

blank_company_country = search_count(url_companies, [
    {"propertyName": "country", "operator": "NOT_HAS_PROPERTY"},
])
has_company_country = search_count(url_companies, [
    {"propertyName": "country", "operator": "HAS_PROPERTY"},
])

print(f"  Companies with country set: {has_company_country}")
print(f"  Companies with blank country: {blank_company_country}")
print()
print("  Country value breakdown:")
for variant, count in sorted(company_country_counts.items(), key=lambda x: -x[1]):
    flag = " <-- NEEDS STANDARDIZATION" if variant in ABBREVIATIONS else ""
    print(f"    {variant!r}: {count}{flag}")
    audit_rows.append({
        "object": "company", "field": "country",
        "value": variant, "count": count,
        "needs_fix": variant in ABBREVIATIONS,
    })
print()

# =====================================================
# CONTACT STATE VALUES
# =====================================================
print("CONTACT STATE VALUES (checking for abbreviations)")
print("-" * 40)

state_abbrevs = {
    "NY": "New York", "CA": "California", "TX": "Texas", "FL": "Florida",
    "IL": "Illinois", "PA": "Pennsylvania", "OH": "Ohio", "GA": "Georgia",
    "NC": "North Carolina", "NJ": "New Jersey", "VA": "Virginia",
    "WA": "Washington", "MA": "Massachusetts", "AZ": "Arizona",
    "CO": "Colorado", "MD": "Maryland", "MN": "Minnesota", "MO": "Missouri",
    "WI": "Wisconsin", "CT": "Connecticut", "OR": "Oregon",
    "SC": "South Carolina", "LA": "Louisiana", "TN": "Tennessee",
    "IN": "Indiana", "MI": "Michigan", "DC": "District of Columbia",
    "UT": "Utah", "NV": "Nevada", "AL": "Alabama",
}

state_abbrev_counts = {}
total_abbrev_contacts = 0
for abbrev, full_name in state_abbrevs.items():
    count = search_count(url_contacts, [
        {"propertyName": "state", "operator": "EQ", "value": abbrev},
    ])
    if count > 0:
        state_abbrev_counts[abbrev] = (count, full_name)
        total_abbrev_contacts += count

if state_abbrev_counts:
    print(f"  Found {len(state_abbrev_counts)} state abbreviations "
          f"({total_abbrev_contacts} total contacts):")
    for abbrev, (count, full) in sorted(
        state_abbrev_counts.items(), key=lambda x: -x[1][0],
    ):
        print(f"    {abbrev!r} -> {full!r}: {count} contacts")
        audit_rows.append({
            "object": "contact", "field": "state",
            "value": abbrev, "count": count,
            "needs_fix": True,
        })
else:
    print("  No state abbreviations found — all states appear to use full names.")
print()

# Also check a few full state names for reference
print("  Top full state names (reference):")
top_states = [
    "New York", "California", "Texas", "Florida", "Illinois",
    "Virginia", "Georgia", "North Carolina", "New Jersey", "Pennsylvania",
]
for state in top_states:
    count = search_count(url_contacts, [
        {"propertyName": "state", "operator": "EQ", "value": state},
    ])
    if count > 0:
        print(f"    {state!r}: {count}")
print()

# ── CSV audit trail ──────────────────────────────────────────────
os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["object", "field", "value", "count", "needs_fix"],
    )
    writer.writeheader()
    writer.writerows(audit_rows)
print(f"Audit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
total_contact_fixes = sum(
    count for variant, count in contact_country_counts.items()
    if variant in ABBREVIATIONS
)
total_company_fixes = sum(
    count for variant, count in company_country_counts.items()
    if variant in ABBREVIATIONS
)

print()
print("=" * 60)
print("BEFORE STATE SUMMARY")
print("=" * 60)
print(f"  Contact country variants needing fix: {total_contact_fixes}")
print(f"  Company country variants needing fix: {total_company_fixes}")
print(f"  Contact state abbreviations needing fix: {total_abbrev_contacts}")
print(f"  Total records to standardize: "
      f"{total_contact_fixes + total_company_fixes + total_abbrev_contacts}")
print("=" * 60)
