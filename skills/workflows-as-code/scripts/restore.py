# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Workflows as Code — Restore
Recreate a workflow from an export file via POST /automation/v4/flows.

Usage:
  uv run skills/workflows-as-code/scripts/restore.py <export-file.json>

The restored workflow is created DISABLED with a "(restored)" name suffix.
Review it in Automation > Workflows, verify against the export, then
rename and enable.
"""

import json
import os
import sys
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

# Server-assigned / read-only fields that must not be sent on create
STRIP_FIELDS = {
    "id", "revisionId", "createdAt", "updatedAt", "portalId",
    "migrationStatus", "crmObjectCreationStatus", "dataSources",
}

if len(sys.argv) != 2:
    print(__doc__)
    raise SystemExit(1)

path = sys.argv[1]
with open(path) as f:
    flow = json.load(f)

original_name = flow.get("name", "unnamed")
payload = {k: v for k, v in flow.items() if k not in STRIP_FIELDS}
payload["name"] = f"{original_name} (restored)"
payload["isEnabled"] = False

print("=" * 60)
print("WORKFLOWS AS CODE — RESTORE")
print("=" * 60)
print()
print(f"Source file:  {path}")
print(f"Original:     {original_name}")
print(f"Restoring as: {payload['name']} (disabled)")
print()

confirm = input("Type 'RESTORE' to create this workflow: ")
if confirm != "RESTORE":
    print("Aborted by user.")
    raise SystemExit(0)

for attempt in range(5):
    resp = requests.post(f"{BASE}/automation/v4/flows", headers=HEADERS, json=payload)
    if resp.status_code == 429:
        wait = min(10 * (attempt + 1), 30)
        print(f"Rate limited, waiting {wait}s...")
        time.sleep(wait)
        continue
    break

if resp.status_code in (200, 201):
    fid = resp.json().get("id", "unknown")
    print(f"SUCCESS: created flowId {fid} (disabled).")
    print("Open Automation > Workflows, verify enrollment criteria and actions")
    print("against the export, then rename and enable.")
else:
    print(f"FAILED ({resp.status_code}): {resp.text[:500]}")
    print()
    print("Common causes:")
    print("  - An action's field shape is portal-specific (e.g. notification")
    print("    recipients, copy-from-associated-object). Remove that action from")
    print("    the JSON, restore, and re-add it in the UI.")
    print("  - Referenced assets (lists, emails, properties) no longer exist.")
    print("  - Missing 'automation' or sensitive-data scopes on the token.")
    raise SystemExit(1)
