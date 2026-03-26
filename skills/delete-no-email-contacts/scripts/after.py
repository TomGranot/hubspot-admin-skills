# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Delete No-Email Contacts — After State
Verify that no contacts with missing email remain.
"""

import os
import csv
import json
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

search_payload = {
    "filterGroups": [
        {
            "filters": [
                {
                    "propertyName": "email",
                    "operator": "NOT_HAS_PROPERTY",
                }
            ]
        }
    ],
    "properties": ["firstname", "lastname", "createdate", "hs_object_id"],
    "limit": 1,
}

url = f"{BASE}/crm/v3/objects/contacts/search"

print("=" * 60)
print("DELETE NO-EMAIL CONTACTS — AFTER STATE")
print("=" * 60)
print()

response = requests.post(url, headers=headers, json=search_payload)
response.raise_for_status()

data = response.json()
total = data.get("total", 0)

print(f"  Total contacts with no email: {total}")
print()

# Compare with before state CSV if it exists
before_csv = os.path.join(
    os.path.dirname(__file__), "..", "data", "no-email-contacts-before.csv"
)
before_count = 0
if os.path.exists(before_csv):
    with open(before_csv, "r") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        before_count = sum(1 for _ in reader)
    print(f"  Before-state count (from CSV): {before_count}")
    print(f"  Contacts removed: {before_count - total}")
    print()

success = total == 0

print("=" * 60)
if success:
    print("SUCCESS: 0 contacts with no email remain.")
    if before_count:
        print(f"  All {before_count} contacts have been deleted.")
else:
    print(f"WARNING: {total} contacts with no email still exist.")
    print("  Possible causes:")
    print("  - New contacts created since deletion")
    print("  - Some deletions failed (check deletion log)")
    if data.get("results"):
        sample = data["results"][0]
        props = sample.get("properties", {})
        print(f"  Sample: ID {sample['id']}, "
              f"{props.get('firstname', '')} {props.get('lastname', '')}, "
              f"created {props.get('createdate', '')}")
print("=" * 60)
