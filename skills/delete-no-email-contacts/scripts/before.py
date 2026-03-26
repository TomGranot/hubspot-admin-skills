# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Delete No-Email Contacts — Before State
Count contacts with no email address and export to CSV for audit.
"""

import os
import csv
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

url = f"{BASE}/crm/v3/objects/contacts/search"

PAGINATE_DELAY = 0.15  # seconds between paginated requests

print("=" * 60)
print("DELETE NO-EMAIL CONTACTS — BEFORE STATE")
print("=" * 60)
print()

# --- Step 1: Count contacts with no email ---
print("Step 1: Counting contacts with no email address...")

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

print(f"  API: POST {url}")
print(f"  Filter: email NOT_HAS_PROPERTY")
print()

response = requests.post(url, headers=headers, json=search_payload)
response.raise_for_status()

data = response.json()
total = data.get("total", 0)

print(f"  Total contacts with no email: {total}")
print()

# --- Step 2: Collect all contacts and export to CSV ---
print("Step 2: Exporting all no-email contacts to CSV...")

all_contacts = []
after = None

while True:
    payload = {
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
        "properties": [
            "firstname", "lastname", "createdate", "lifecyclestage",
            "hubspot_owner_id", "hs_analytics_source",
        ],
        "limit": 100,
    }
    if after:
        payload["after"] = after

    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"  Stopped at {len(all_contacts)} (status {resp.status_code})")
        break

    data = resp.json()
    for contact in data.get("results", []):
        props = contact.get("properties", {})
        all_contacts.append({
            "id": contact["id"],
            "firstname": props.get("firstname", ""),
            "lastname": props.get("lastname", ""),
            "lifecycle_stage": props.get("lifecyclestage", ""),
            "owner_id": props.get("hubspot_owner_id", ""),
            "source": props.get("hs_analytics_source", ""),
            "createdate": props.get("createdate", ""),
        })

    print(f"  Fetched page ({len(data.get('results', []))} contacts, {len(all_contacts)} total)")

    paging = data.get("paging", {})
    next_page = paging.get("next", {})
    after = next_page.get("after")

    if not after:
        break

    time.sleep(PAGINATE_DELAY)

# Save CSV
output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(output_dir, exist_ok=True)

csv_path = os.path.join(output_dir, "no-email-contacts-before.csv")
fieldnames = ["id", "firstname", "lastname", "lifecycle_stage", "owner_id", "source", "createdate"]

with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_contacts)

print(f"\n  Saved {len(all_contacts)} contacts to {csv_path}")
print()

# --- Step 3: Lifecycle stage breakdown ---
print("Step 3: Lifecycle stage breakdown:")
stages = {}
for c in all_contacts:
    s = c["lifecycle_stage"] or "(none)"
    stages[s] = stages.get(s, 0) + 1

for stage, count in sorted(stages.items(), key=lambda x: -x[1]):
    print(f"  {stage}: {count}")

# --- Step 4: Source breakdown ---
print()
print("Step 4: Original source breakdown:")
sources = {}
for c in all_contacts:
    s = c["source"] or "(none)"
    sources[s] = sources.get(s, 0) + 1

for source, count in sorted(sources.items(), key=lambda x: -x[1]):
    print(f"  {source}: {count}")

# --- Summary ---
print()
print("=" * 60)
print("BEFORE STATE SUMMARY")
print("=" * 60)
print(f"  Total contacts with no email: {total}")
print(f"  Contacts exported to CSV: {len(all_contacts)}")
print(f"  Audit CSV: {csv_path}")
print()
print("  Next step: Review the CSV, then run execute.py to delete.")
