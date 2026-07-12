# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Waterfall Enrich Contacts — After
Re-count enrichment candidates and compare against the before baseline.
Read-only.
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


def count(filters):
    resp = requests.post(f"{BASE}/crm/v3/objects/contacts/search", headers=HEADERS,
                         json={"filterGroups": [{"filters": filters}], "limit": 1})
    resp.raise_for_status()
    time.sleep(0.15)
    return resp.json().get("total", 0)


identity = [
    {"propertyName": "firstname", "operator": "HAS_PROPERTY"},
    {"propertyName": "lastname", "operator": "HAS_PROPERTY"},
    {"propertyName": "company", "operator": "HAS_PROPERTY"},
]

now = {
    "candidates_missing_email": count(identity + [
        {"propertyName": "email", "operator": "NOT_HAS_PROPERTY"}]),
    "candidates_missing_phone": count(identity + [
        {"propertyName": "phone", "operator": "NOT_HAS_PROPERTY"}]),
    "candidates_missing_jobtitle": count(identity + [
        {"propertyName": "jobtitle", "operator": "NOT_HAS_PROPERTY"}]),
}

before_path = os.path.join("data", "audit-logs", "waterfall-enrich-contacts-before.csv")
before = {}
if os.path.exists(before_path):
    with open(before_path) as f:
        for row in csv.DictReader(f):
            before[row["metric"]] = int(row["count"])

print("=" * 60)
print("WATERFALL ENRICH — AFTER")
print("=" * 60)
for metric, val in now.items():
    if metric in before:
        delta = before[metric] - val
        print(f"  {metric}: {before[metric]:,} -> {val:,}  ({delta:+,} enriched)")
    else:
        print(f"  {metric}: {val:,}  (no baseline — run before.py first)")
print()
print("Spot-check 10-20 enriched contacts against the execute audit CSV")
print("(data/audit-logs/waterfall-enrich-contacts-execute.csv) before")
print("trusting the provider at scale.")
