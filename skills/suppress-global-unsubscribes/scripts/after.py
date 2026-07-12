# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Suppress Global Unsubscribes — After State
Verify that globally unsubscribed contacts have been suppressed.
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

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

url = f"{BASE}/crm/v3/objects/contacts/search"

print("=" * 60)
print("SUPPRESS GLOBAL UNSUBSCRIBES — AFTER STATE")
print("=" * 60)
print()

# --- Step 1: Total globally unsubscribed ---
print("Step 1: Total globally unsubscribed contacts...")

resp = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hs_email_optout", "operator": "EQ", "value": "true"},
    ]}],
    "limit": 1,
})
resp.raise_for_status()
total_unsubscribed = resp.json().get("total", 0)
print(f"  Total globally unsubscribed: {total_unsubscribed}")

# --- Step 2: Still marketing? ---
print()
print("Step 2: Unsubscribed AND still marketing...")

resp2 = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hs_email_optout", "operator": "EQ", "value": "true"},
        {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
    ]}],
    "limit": 1,
})
resp2.raise_for_status()
still_marketing = resp2.json().get("total", 0)
suppressed = total_unsubscribed - still_marketing

print(f"  Still marketing: {still_marketing}")
print(f"  Suppressed (non-marketing): {suppressed}")

# --- Compare with before state ---
before_csv = os.path.join("data", "audit-logs", "global-unsubscribes-before.csv")
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
    print("SUCCESS: All globally unsubscribed contacts are now non-marketing.")
else:
    print(f"WARNING: {still_marketing} unsubscribed contacts still have marketing status.")
    print("  Action: Suppress remaining contacts via HubSpot UI.")
print("=" * 60)
