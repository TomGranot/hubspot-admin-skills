# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Merge Duplicate Companies — Before State
Find duplicate companies by domain and by name, export groups to CSV.
Note: HubSpot does not support bulk merge via API — merging is manual.
"""

import os
import csv
import time
import requests
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

PAGINATE_DELAY = 0.15  # seconds between paginated requests

print("=" * 60)
print("MERGE DUPLICATE COMPANIES — BEFORE STATE")
print("=" * 60)
print()

# --- Step 1: Export all companies ---
print("Step 1: Fetching all companies (domain + name)...")

all_companies = []
after = None

while True:
    params = {
        "limit": 100,
        "properties": "name,domain,lifecyclestage,num_associated_contacts,num_associated_deals,hubspot_owner_id,createdate",
    }
    if after:
        params["after"] = after

    resp = requests.get(f"{BASE}/crm/v3/objects/companies", headers=headers, params=params)
    if resp.status_code != 200:
        print(f"  Stopped at {len(all_companies)} (status {resp.status_code})")
        break

    data = resp.json()
    for company in data.get("results", []):
        props = company.get("properties", {})
        all_companies.append({
            "id": company["id"],
            "name": (props.get("name") or "").strip(),
            "domain": (props.get("domain") or "").strip().lower(),
            "lifecycle_stage": props.get("lifecyclestage", ""),
            "associated_contacts": props.get("num_associated_contacts", "0"),
            "associated_deals": props.get("num_associated_deals", "0"),
            "owner_id": props.get("hubspot_owner_id", ""),
            "createdate": props.get("createdate", ""),
        })

    paging = data.get("paging", {})
    next_page = paging.get("next", {})
    after = next_page.get("after")

    if not after:
        break
    time.sleep(PAGINATE_DELAY)

print(f"  Total companies fetched: {len(all_companies)}")
print()

# --- Step 2: Find duplicates by domain ---
print("Step 2: Analyzing duplicates by domain...")

domain_groups = defaultdict(list)
for c in all_companies:
    if c["domain"]:
        domain_groups[c["domain"]].append(c)

dup_domain_groups = {d: cs for d, cs in domain_groups.items() if len(cs) > 1}
dup_domain_records = sum(len(cs) for cs in dup_domain_groups.values())

print(f"  Unique domains with duplicates: {len(dup_domain_groups)}")
print(f"  Total records in duplicate domain groups: {dup_domain_records}")
print()

# Top offenders by domain
print("  Top duplicate domains:")
sorted_domains = sorted(dup_domain_groups.items(), key=lambda x: len(x[1]), reverse=True)
for domain, companies in sorted_domains[:15]:
    print(f"    {domain}: {len(companies)} records")
print()

# --- Step 3: Find duplicates by name ---
print("Step 3: Analyzing duplicates by name...")

name_groups = defaultdict(list)
for c in all_companies:
    if c["name"]:
        name_groups[c["name"].lower()].append(c)

dup_name_groups = {n: cs for n, cs in name_groups.items() if len(cs) > 1}
dup_name_records = sum(len(cs) for cs in dup_name_groups.values())

print(f"  Unique names with duplicates: {len(dup_name_groups)}")
print(f"  Total records in duplicate name groups: {dup_name_records}")
print()

# Top offenders by name
print("  Top duplicate names:")
sorted_names = sorted(dup_name_groups.items(), key=lambda x: len(x[1]), reverse=True)
for name, companies in sorted_names[:15]:
    print(f"    {companies[0]['name']}: {len(companies)} records")
print()

# --- Step 4: Save CSVs ---
print("Step 4: Saving audit CSVs...")

output_dir = "data/audit-logs"
os.makedirs(output_dir, exist_ok=True)

# Domain duplicates CSV
domain_csv = os.path.join(output_dir, "duplicate-companies-by-domain.csv")
with open(domain_csv, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["domain", "duplicate_count", "id", "name",
              "lifecycle_stage", "associated_contacts", "associated_deals", "owner_id", "createdate"])
    writer.writeheader()
    for domain, companies in sorted_domains:
        for c in companies:
            writer.writerow({
                "domain": domain,
                "duplicate_count": len(companies),
                **{k: c[k] for k in ["id", "name", "lifecycle_stage", "associated_contacts",
                                      "associated_deals", "owner_id", "createdate"]},
            })

print(f"  Domain duplicates: {domain_csv}")

# Name duplicates CSV
name_csv = os.path.join(output_dir, "duplicate-companies-by-name.csv")
with open(name_csv, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["duplicate_name", "duplicate_count", "id", "name",
              "domain", "lifecycle_stage", "associated_contacts", "associated_deals", "owner_id", "createdate"])
    writer.writeheader()
    for name_lower, companies in sorted_names:
        for c in companies:
            writer.writerow({
                "duplicate_name": name_lower,
                "duplicate_count": len(companies),
                **{k: c[k] for k in ["id", "name", "domain", "lifecycle_stage",
                                      "associated_contacts", "associated_deals", "owner_id", "createdate"]},
            })

print(f"  Name duplicates: {name_csv}")
print()

# --- Summary ---
print("=" * 60)
print("BEFORE STATE SUMMARY")
print("=" * 60)
print(f"  Total companies: {len(all_companies)}")
print(f"  Duplicate domain groups: {len(dup_domain_groups)} (affecting {dup_domain_records} records)")
print(f"  Duplicate name groups: {len(dup_name_groups)} (affecting {dup_name_records} records)")
print(f"  Domain duplicates CSV: {domain_csv}")
print(f"  Name duplicates CSV: {name_csv}")
print()
print("  NOTE: Company merge is manual in HubSpot.")
print("  Use Settings > Data Management > Duplicates to merge pairs.")
print("  Prioritize domain-based duplicates first (higher confidence).")
