# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Waterfall Enrich Contacts — Before
Count enrichment candidates and preview the cost before spending
provider credits. Read-only.
"""

import csv
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

PROVIDER = os.environ.get("ENRICHMENT_PROVIDER", "fullenrich")
# Informational only — set to your provider's per-contact credit cost
CREDITS_PER_CONTACT = float(os.environ.get("ENRICHMENT_CREDITS_PER_CONTACT", "1"))


def count(filters):
    resp = requests.post(f"{BASE}/crm/v3/objects/contacts/search", headers=HEADERS,
                         json={"filterGroups": [{"filters": filters}], "limit": 1})
    resp.raise_for_status()
    time.sleep(0.15)
    return resp.json().get("total", 0)


print("=" * 60)
print("WATERFALL ENRICH — BEFORE (read-only)")
print("=" * 60)
print()

# Candidates need enough identity for a waterfall lookup: a name plus a
# company or domain. Each row = missing field we could enrich.
identity = [
    {"propertyName": "firstname", "operator": "HAS_PROPERTY"},
    {"propertyName": "lastname", "operator": "HAS_PROPERTY"},
    {"propertyName": "company", "operator": "HAS_PROPERTY"},
]

missing_email = count(identity + [
    {"propertyName": "email", "operator": "NOT_HAS_PROPERTY"}])
missing_phone = count(identity + [
    {"propertyName": "phone", "operator": "NOT_HAS_PROPERTY"}])
missing_title = count(identity + [
    {"propertyName": "jobtitle", "operator": "NOT_HAS_PROPERTY"}])

rows = [
    {"metric": "candidates_missing_email", "count": missing_email},
    {"metric": "candidates_missing_phone", "count": missing_phone},
    {"metric": "candidates_missing_jobtitle", "count": missing_title},
]

print(f"Provider: {PROVIDER}")
print(f"Contacts with name+company but missing email:    {missing_email:,}")
print(f"Contacts with name+company but missing phone:    {missing_phone:,}")
print(f"Contacts with name+company but missing jobtitle: {missing_title:,}")
print()
est = max(missing_email, missing_phone) * CREDITS_PER_CONTACT
print(f"Rough cost ceiling if you enriched every candidate:")
print(f"  ~{est:,.0f} {PROVIDER} credits "
      f"(at {CREDITS_PER_CONTACT} credits/contact — adjust "
      "ENRICHMENT_CREDITS_PER_CONTACT to your plan)")
print()
print("The execute script processes at most MAX_CONTACTS per run "
      "(default 100) precisely so costs stay predictable.")

os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
csv_path = os.path.join("data", "audit-logs", "waterfall-enrich-contacts-before.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["metric", "count"])
    w.writeheader()
    w.writerows(rows)
print(f"\nBaseline written to {csv_path}")
print("Next step: review execute.py configuration, then run it.")
