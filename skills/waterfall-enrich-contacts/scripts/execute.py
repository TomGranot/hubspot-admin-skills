# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Waterfall Enrich Contacts — Execute
Enrich HubSpot contacts through an external provider (FullEnrich by
default) and write results back via batch update.

Safety model:
  - Processes at most MAX_CONTACTS per run (credits cost money)
  - Never overwrites non-empty HubSpot values unless OVERWRITE=true
  - Typed confirmation before spending credits, again before writing
  - Full CSV audit trail (old value + new value per field)
"""

import csv
import os
import time

import requests
from dotenv import load_dotenv

from providers import get_provider

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# ── Configuration ────────────────────────────────────────────────
PROVIDER_NAME = os.environ.get("ENRICHMENT_PROVIDER", "fullenrich")
# Which contact field to target for candidate selection:
#   "phone" | "email" | "jobtitle"
TARGET_FIELD = os.environ.get("ENRICHMENT_TARGET_FIELD", "phone")
# Hard cap per run — enrichment credits cost real money
MAX_CONTACTS = int(os.environ.get("ENRICHMENT_MAX_CONTACTS", "100"))
# Overwrite existing non-empty values? Default: never
OVERWRITE = os.environ.get("ENRICHMENT_OVERWRITE", "false").lower() == "true"
# Fields the provider may write back to HubSpot
WRITABLE_FIELDS = ["email", "phone", "jobtitle"]

BATCH_SIZE = 100
PAGINATE_DELAY = 0.15
BATCH_DELAY = 0.5


print("=" * 60)
print("WATERFALL ENRICH — EXECUTE")
print("=" * 60)
print(f"  Provider:      {PROVIDER_NAME}")
print(f"  Target field:  {TARGET_FIELD}")
print(f"  Max contacts:  {MAX_CONTACTS}")
print(f"  Overwrite:     {OVERWRITE}")
print()

provider = get_provider(PROVIDER_NAME)

# ── Step 1: Select candidates ────────────────────────────────────
print("Step 1: Selecting enrichment candidates...")
candidates = []
after = None
while len(candidates) < MAX_CONTACTS:
    body = {
        "filterGroups": [{"filters": [
            {"propertyName": TARGET_FIELD, "operator": "NOT_HAS_PROPERTY"},
            {"propertyName": "firstname", "operator": "HAS_PROPERTY"},
            {"propertyName": "lastname", "operator": "HAS_PROPERTY"},
            {"propertyName": "company", "operator": "HAS_PROPERTY"},
        ]}],
        "properties": ["email", "firstname", "lastname", "company",
                       "phone", "jobtitle", "website", "hs_linkedin_url"],
        "limit": min(100, MAX_CONTACTS - len(candidates)),
    }
    if after:
        body["after"] = after
    resp = requests.post(f"{BASE}/crm/v3/objects/contacts/search",
                         headers=HEADERS, json=body)
    resp.raise_for_status()
    data = resp.json()
    for r in data.get("results", []):
        p = r.get("properties", {})
        email = p.get("email") or ""
        domain = email.split("@")[-1] if "@" in email else (p.get("website") or "")
        candidates.append({
            "id": r["id"],
            "email": email,
            "firstname": p.get("firstname") or "",
            "lastname": p.get("lastname") or "",
            "company": p.get("company") or "",
            "domain": domain,
            "linkedin_url": p.get("hs_linkedin_url") or "",
            "_current": {f: p.get(f) or "" for f in WRITABLE_FIELDS},
        })
    after = data.get("paging", {}).get("next", {}).get("after")
    if not after:
        break
    time.sleep(PAGINATE_DELAY)

print(f"  Selected {len(candidates)} contacts missing '{TARGET_FIELD}'")
if not candidates:
    print("Nothing to enrich. Exiting.")
    raise SystemExit(0)

# ── Step 2: Confirm before spending credits ──────────────────────
print()
print(f"About to send {len(candidates)} contacts to {PROVIDER_NAME}.")
print("This consumes provider credits (names and company data are shared")
print("with the provider — confirm this is acceptable under your data")
print("processing agreements).")
confirm = input("Type 'ENRICH' to proceed: ")
if confirm != "ENRICH":
    print("Aborted by user. No credits spent, nothing changed.")
    raise SystemExit(0)

# ── Step 3: Enrich ───────────────────────────────────────────────
print()
print(f"Step 3: Enriching via {PROVIDER_NAME} (this can take minutes for")
print("async waterfall providers)...")
found = provider.enrich(candidates)
found_by_id = {str(r["id"]): r for r in found if r.get("id")}
print(f"  Provider returned data for {len(found_by_id)}/{len(candidates)} contacts")

# ── Step 4: Compute writes (no-overwrite unless OVERWRITE) ───────
current_by_id = {c["id"]: c["_current"] for c in candidates}
updates, audit = [], []
for cid, rec in found_by_id.items():
    props = {}
    for field in WRITABLE_FIELDS:
        new = (rec.get(field) or "").strip()
        if not new:
            continue
        old = current_by_id.get(cid, {}).get(field, "")
        if old and not OVERWRITE:
            audit.append({"contact_id": cid, "field": field, "old": old,
                          "new": new, "action": "skipped_existing_value",
                          "source": rec.get("source", PROVIDER_NAME)})
            continue
        props[field] = new
        audit.append({"contact_id": cid, "field": field, "old": old,
                      "new": new, "action": "write",
                      "source": rec.get("source", PROVIDER_NAME)})
    if props:
        updates.append({"id": cid, "properties": props})

print(f"  Planned writes: {len(updates)} contacts "
      f"({sum(1 for a in audit if a['action'] == 'write')} field values)")

if not updates:
    print("No writable results (all found values already present?). Exiting.")
    raise SystemExit(0)

confirm = input("Type 'WRITE' to update HubSpot: ")
if confirm != "WRITE":
    print("Aborted before writing. Provider results discarded.")
    raise SystemExit(0)

# ── Step 5: Batch update HubSpot ─────────────────────────────────
written, failed = 0, 0
for i in range(0, len(updates), BATCH_SIZE):
    batch = updates[i:i + BATCH_SIZE]
    resp = requests.post(f"{BASE}/crm/v3/objects/contacts/batch/update",
                         headers=HEADERS, json={"inputs": batch})
    if resp.status_code in (200, 201):
        written += len(batch)
    else:
        failed += len(batch)
        print(f"  Batch FAILED ({resp.status_code}): {resp.text[:200]}")
    time.sleep(BATCH_DELAY)

# ── Step 6: Audit trail ──────────────────────────────────────────
os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
csv_path = os.path.join("data", "audit-logs", "waterfall-enrich-contacts-execute.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["contact_id", "field", "old", "new",
                                      "action", "source"])
    w.writeheader()
    w.writerows(audit)

print()
print("=" * 60)
print("EXECUTION SUMMARY")
print("=" * 60)
print(f"  Candidates sent to provider: {len(candidates)}")
print(f"  Contacts with results:       {len(found_by_id)}")
print(f"  Contacts updated:            {written}")
print(f"  Failed updates:              {failed}")
print(f"  Audit trail: {csv_path}")
print()
print("  Next step: run after.py to verify, and spot-check enriched")
print("  contacts for accuracy before trusting the provider at scale.")
