# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Suppress Ghost Contacts — After State
Verify that ghost contacts have been suppressed (set to non-marketing).
"""

import os
import csv
import json
import requests
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"

# ── Configuration ──────────────────────────────────────────────
WORST_OFFENDER_THRESHOLD = 15  # Must match the value used in before.py

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

url = f"{BASE}/crm/v3/objects/contacts/search"

GHOST_FILTERS = [
    {"propertyName": "hs_email_delivered", "operator": "GT", "value": "0"},
    {"propertyName": "hs_email_open", "operator": "NOT_HAS_PROPERTY"},
    {"propertyName": "hs_email_bounce", "operator": "NOT_HAS_PROPERTY"},
]

print("=" * 60)
print("SUPPRESS GHOST CONTACTS — AFTER STATE")
print("=" * 60)
print()

# --- Step 1: Total ghost contacts ---
print("Step 1: Total ghost contacts...")

resp = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": GHOST_FILTERS}],
    "limit": 1,
})
resp.raise_for_status()
total_ghosts = resp.json().get("total", 0)
print(f"  Total ghost contacts: {total_ghosts}")

# --- Step 2: Still marketing? ---
print()
print("Step 2: Ghost contacts still marketing...")

resp2 = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": GHOST_FILTERS + [
        {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
    ]}],
    "limit": 1,
})
resp2.raise_for_status()
still_marketing = resp2.json().get("total", 0)
suppressed = total_ghosts - still_marketing

print(f"  Still marketing: {still_marketing}")
print(f"  Suppressed (non-marketing): {suppressed}")

# --- Step 3: Worst offenders still marketing ---
print()
print(f"Step 3: Worst offenders ({WORST_OFFENDER_THRESHOLD}+ delivered) still marketing...")

resp3 = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hs_email_delivered", "operator": "GT", "value": str(WORST_OFFENDER_THRESHOLD)},
        {"propertyName": "hs_email_open", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "hs_email_bounce", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
    ]}],
    "limit": 1,
})
resp3.raise_for_status()
worst_still_marketing = resp3.json().get("total", 0)
print(f"  {WORST_OFFENDER_THRESHOLD}+ delivered, still marketing: {worst_still_marketing}")

# --- Compare with before state ---
before_csv = os.path.join("data", "audit-logs", "ghost-contacts-before.csv")
if os.path.exists(before_csv):
    os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
    with open(before_csv, "r") as f:
        reader = csv.DictReader(f)
        before_contacts = list(reader)
    before_still_marketing = sum(
        1 for c in before_contacts if c.get("marketable_status") != "false"
    )
    print()
    print(f"  Before-state total: {len(before_contacts)}")
    print(f"  Before-state still marketing: {before_still_marketing}")
    print(f"  Newly suppressed: {before_still_marketing - still_marketing}")

# --- Verdict ---
print()
print("=" * 60)
if still_marketing == 0:
    print("SUCCESS: All ghost contacts are now non-marketing.")
elif worst_still_marketing == 0:
    print(f"PARTIAL SUCCESS: Worst offenders ({WORST_OFFENDER_THRESHOLD}+) suppressed.")
    print(f"  {still_marketing} ghost contacts with fewer deliveries still marketing.")
else:
    print(f"WARNING: {still_marketing} ghost contacts still have marketing status.")
    print(f"  Including {worst_still_marketing} worst offenders ({WORST_OFFENDER_THRESHOLD}+ delivered).")
    print("  Action: Suppress remaining contacts via HubSpot UI.")
print("=" * 60)
