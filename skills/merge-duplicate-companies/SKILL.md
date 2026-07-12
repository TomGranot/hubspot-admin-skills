---
name: merge-duplicate-companies
description: "Identify duplicate company records by domain and name, export audit CSVs for review, and guide merging. API for discovery, third-party tools or manual UI for merging (HubSpot has no bulk merge API)."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: database-hygiene
---

# Merge Duplicate Companies

## Purpose

Duplicate company records fragment contacts, deals, and engagement history across multiple records for the same real-world company. This leads to inaccurate reporting, broken associations, sales confusion, and workflow failures. This skill identifies duplicates by domain and by name, exports prioritized audit CSVs, and guides the user through merging.

## Prerequisites

- A HubSpot private app access token with `crm.objects.companies.read` scope
- Python 3.10+ with `uv` for package management
- A `.env` file containing `HUBSPOT_ACCESS_TOKEN`
- Super Admin permissions for merging in the HubSpot UI

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run skills/merge-duplicate-companies/scripts/before.py` |

Only the detection stage is scripted: `before.py` inventories companies and flags duplicate candidates by domain and normalized name. Merging itself happens one pair at a time in the UI (see Key Constraint).

## Key Constraint

**HubSpot has no bulk merge API.** Merging must happen one pair at a time through the HubSpot UI or via third-party tools. The API is used for discovery, analysis, and audit trail generation.

**HubSpot's built-in Duplicates tool is NOT available on all plan tiers.** Check whether the account has access to Settings > Data Management > Duplicates before relying on it.

## Execution Pattern

This skill follows a 4-stage execution pattern: **Plan -> Before -> Execute -> After**.

### Stage 1: Plan

Before writing any code, confirm with the user:

1. **Confirm intentional duplicates**: Ask whether separate records for regional offices of the same company are intentional. If so, exclude those from merging.
2. **Merging is irreversible.** Once two company records are merged, they cannot be un-merged. The surviving record inherits all associations, but property values from the deleted record may be lost if both have the same property filled in.
3. **Prioritization strategy**: Recommend merging Customer-stage companies first, then Opportunity-stage, then everything else.
4. **Time estimate**: This is the most time-consuming process. Budget 2-4 hours for critical duplicates, 8-12 hours total for full cleanup.

### Stage 2: Before

Fetch all companies, identify duplicate groups by domain and name, and export audit CSVs.

```python
"""
Before State: Identify duplicate companies by domain and by name.
Creates CSV audit logs for review before merging.
"""
import os
import csv
import time
import requests
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# --- Step 1: Fetch all companies ---
print("Fetching all companies...")

all_companies = []
after = None

while True:
    params = {
        "limit": 100,
        "properties": "name,domain,lifecyclestage,num_associated_contacts,"
                       "num_associated_deals,hubspot_owner_id,createdate",
    }
    if after:
        params["after"] = after

    resp = requests.get(
        f"{BASE}/crm/v3/objects/companies",
        headers=headers, params=params,
    )
    if resp.status_code != 200:
        print(f"Stopped at {len(all_companies)} (status {resp.status_code})")
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
    after = paging.get("next", {}).get("after")
    if not after:
        break
    time.sleep(0.05)

print(f"Total companies fetched: {len(all_companies)}")

# --- Step 2: Find duplicates by domain ---
print("\nAnalyzing duplicates by domain...")

domain_groups = defaultdict(list)
for c in all_companies:
    if c["domain"]:
        domain_groups[c["domain"]].append(c)

dup_domain_groups = {d: cs for d, cs in domain_groups.items() if len(cs) > 1}
dup_domain_records = sum(len(cs) for cs in dup_domain_groups.values())

print(f"Unique domains with duplicates: {len(dup_domain_groups)}")
print(f"Total records in duplicate domain groups: {dup_domain_records}")

# Top offenders
sorted_domains = sorted(dup_domain_groups.items(), key=lambda x: len(x[1]), reverse=True)
print("\nTop duplicate domains:")
for domain, companies in sorted_domains[:15]:
    print(f"  {domain}: {len(companies)} records")

# --- Step 3: Find duplicates by name ---
print("\nAnalyzing duplicates by name...")

name_groups = defaultdict(list)
for c in all_companies:
    if c["name"]:
        name_groups[c["name"].lower()].append(c)

dup_name_groups = {n: cs for n, cs in name_groups.items() if len(cs) > 1}
dup_name_records = sum(len(cs) for cs in dup_name_groups.values())

print(f"Unique names with duplicates: {len(dup_name_groups)}")
print(f"Total records in duplicate name groups: {dup_name_records}")

sorted_names = sorted(dup_name_groups.items(), key=lambda x: len(x[1]), reverse=True)
print("\nTop duplicate names:")
for name_lower, companies in sorted_names[:15]:
    print(f"  {companies[0]['name']}: {len(companies)} records")

# --- Step 4: Save CSV audit logs ---
os.makedirs("data/audit-logs", exist_ok=True)

# Domain duplicates CSV
domain_csv = "data/audit-logs/duplicate-companies-by-domain.csv"
with open(domain_csv, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "domain", "duplicate_count", "id", "name", "lifecycle_stage",
        "associated_contacts", "associated_deals", "owner_id", "createdate",
    ])
    writer.writeheader()
    for domain, companies in sorted_domains:
        for c in companies:
            writer.writerow({
                "domain": domain,
                "duplicate_count": len(companies),
                **{k: c[k] for k in [
                    "id", "name", "lifecycle_stage", "associated_contacts",
                    "associated_deals", "owner_id", "createdate",
                ]},
            })

print(f"\nDomain duplicates CSV: {domain_csv}")

# Name duplicates CSV
name_csv = "data/audit-logs/duplicate-companies-by-name.csv"
with open(name_csv, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "duplicate_name", "duplicate_count", "id", "name", "domain",
        "lifecycle_stage", "associated_contacts", "associated_deals",
        "owner_id", "createdate",
    ])
    writer.writeheader()
    for name_lower, companies in sorted_names:
        for c in companies:
            writer.writerow({
                "duplicate_name": name_lower,
                "duplicate_count": len(companies),
                **{k: c[k] for k in [
                    "id", "name", "domain", "lifecycle_stage",
                    "associated_contacts", "associated_deals",
                    "owner_id", "createdate",
                ]},
            })

print(f"Name duplicates CSV: {name_csv}")
```

**Present findings to the user.** Key data points:
- Total duplicate domain groups and affected records
- Total duplicate name groups and affected records
- Top offenders by domain and name
- CSVs for manual review

### Stage 3: Execute

This stage is primarily manual. Guide the user through the merging process.

**Option A: HubSpot Built-In Duplicates Tool (if available)**

1. Navigate to **Settings > Data Management > Duplicates > Companies**
2. HubSpot shows suggested duplicate pairs ranked by confidence
3. For each pair, click **Review** to see side-by-side comparison
4. Select the "primary" (surviving) record based on:
   - More associated contacts
   - More associated deals
   - More recent activity
   - Has a company owner
   - More complete property data
5. Click **Merge**
6. Process ~50 pairs at a time; HubSpot loads the next batch automatically

**Prioritization order:**
1. Customer-stage company duplicates (highest value data)
2. Opportunity-stage company duplicates
3. Everything else (Leads, Subscribers)

**Option B: Manual search-and-merge for top offenders**

For companies with many duplicates (4+ records):

1. Search for the company by name in **Contacts > Companies**
2. Identify the "winner" record (most associations, deals, activity)
3. Open the winner record > **Actions** > **Merge**
4. Search for the duplicate > select it > choose property values > **Merge**
5. Repeat until only one record remains

**Option C: Third-party deduplication tools**

For large-scale merging, recommend:
- **Dedupely** (dedupely.com) -- HubSpot-native integration, bulk merge
- **Insycle** (insycle.com) -- Data management platform with dedup
- **Koalify** (koalify.com) -- HubSpot duplicate management

These tools can automate bulk merges that would take hours manually.

**Prevention: Configure auto-association after merging**

```
Settings > Data Management > Companies (or Settings > Objects > Companies)
Enable: "Create and associate companies with contacts"
Set unique identifier: Company domain name
```

This prevents future duplicates by using domain-based matching instead of name-based.

### Stage 4: After

Re-run the Before State analysis and compare duplicate counts.

```python
"""
After State: Verify duplicate reduction.
"""
# Re-fetch all companies and re-run duplicate analysis
# Compare:
#   - Number of duplicate domain groups (should decrease)
#   - Number of duplicate name groups (should decrease)
#   - Top offenders (should be resolved)

# Also verify merged records:
# For each known duplicate that was merged, search for the company
# and confirm only one record exists with all expected associations.
```

**Manual verification:**
1. Search for top offenders by name (should show only 1 record each)
2. Open merged records and verify contacts and deals from both originals appear
3. Check Settings > Data Management > Duplicates -- count should be significantly lower

## Safety Mechanisms

| Mechanism | Detail |
|-----------|--------|
| **CSV audit trail** | Complete export of all companies with duplicate group annotations before any merging. |
| **Prioritized approach** | Customer and Opportunity companies merged first to protect highest-value data. |
| **Review before merge** | CSVs enable team review before any irreversible merges happen. |
| **Confirmation prompt** | Present duplicate analysis to the user and wait for explicit confirmation before instructing merges. |
| **No auto-merge** | This skill never merges automatically. All merges require manual human decision. |

## Technical Gotchas

1. **HubSpot has no bulk merge API.** There is no programmatic way to merge companies. All merges happen through the UI or third-party tools.

2. **Merging is irreversible.** Once merged, records cannot be split apart. When in doubt, skip a pair and revisit later.

3. **Property conflicts**: When both records have a value for the same property, HubSpot keeps the value from the "primary" record. Review important properties (phone, address, industry) before confirming.

4. **Companies endpoint uses GET, not POST/search.** To list all companies, use `GET /crm/v3/objects/companies` with pagination, not the Search API. The Search API works too but is slower for full exports.

5. **Domain normalization**: Always lowercase and strip whitespace from domains before grouping. `Example.com` and `example.com` are the same company.

6. **Name-based duplicates have higher false-positive rates.** "State University" might match multiple genuinely different institutions. Domain-based duplicates are more reliable.

7. **Contact reassociation**: After merging, verify that contacts from both original records appear under the surviving record. HubSpot should handle this automatically, but spot-check.

8. **The Duplicates tool is plan-tier dependent.** Not all HubSpot plans include it. Check availability before instructing the user to navigate there.

## Rollback

- **Company merges cannot be unmerged.** HubSpot has no unmerge for companies — the only recovery is recreating the secondary company manually from the before CSV and re-associating its contacts and deals.
- This is why the before CSV export and per-pair human review are mandatory.

## Setup

Create a `.env` file in the repo root:

```
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx
```

No package install is needed — scripts carry PEP 723 inline metadata and run with [`uv`](https://github.com/astral-sh/uv), which resolves dependencies automatically:

```bash
uv run skills/merge-duplicate-companies/scripts/before.py
```
