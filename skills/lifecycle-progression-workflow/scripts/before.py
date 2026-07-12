# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Lifecycle Progression Workflow — Before
Inventory existing workflows via the v4 Automation API and check for
name collisions with the flows this skill creates.
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

MAX_RETRIES = 5


def api(method, path, **kwargs):
    """Call the HubSpot API with 429 retry. Returns the Response."""
    for attempt in range(MAX_RETRIES):
        resp = requests.request(method, f"{BASE}{path}", headers=HEADERS, **kwargs)
        if resp.status_code == 429:
            wait = min(10 * (attempt + 1), 30)
            print(f"  Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        return resp
    return resp


def list_all_flows():
    """Fetch all workflows via GET /automation/v4/flows (paginated)."""
    flows, after = [], None
    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after
        resp = api("GET", "/automation/v4/flows", params=params)
        if resp.status_code == 403:
            print("403 Forbidden: the Automation API requires the 'automation' scope")
            print("and a plan tier that includes workflows (Marketing/Sales/Service")
            print("Professional or higher). Fall back to the manual UI path in SKILL.md.")
            raise SystemExit(1)
        resp.raise_for_status()
        data = resp.json()
        flows.extend(data.get("results", []))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
        time.sleep(0.15)
    return flows


SKILL_SLUG = "lifecycle-progression-workflow"
PLANNED_NAMES = ["LIFECYCLE: Lead to MQL on Score (API)", "LIFECYCLE: MQL to SQL on Meeting (API)", "LIFECYCLE: SQL to Opportunity on Deal (API)", "LIFECYCLE: Opportunity to Customer on Closed-Won (API)"]

print("=" * 60)
print("BEFORE: Lifecycle Progression Workflow — workflow inventory")
print("=" * 60)
print()

flows = list_all_flows()
enabled = [f for f in flows if f.get("isEnabled")]
print(f"Total workflows in portal: {len(flows)} ({len(enabled)} enabled)")
print()

collisions = [f for f in flows if f.get("name") in PLANNED_NAMES]
if collisions:
    print("NAME COLLISIONS — these planned workflow names already exist:")
    for f in collisions:
        print(f"  - {f.get('name')} (flowId: {f.get('id')}, "
          f"enabled: {f.get('isEnabled')})")
    print("Rename or delete them before running execute.py, or the script")
    print("will skip creating those flows.")
else:
    print("No name collisions with planned workflows:")
    for name in PLANNED_NAMES:
        print(f"  - {name}")

os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
csv_path = os.path.join("data", "audit-logs", f"{SKILL_SLUG}-before.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["flow_id", "name", "is_enabled"])
    w.writeheader()
    for fl in flows:
        w.writerow({"flow_id": fl.get("id"), "name": fl.get("name"),
                    "is_enabled": fl.get("isEnabled")})
print()
print(f"Workflow inventory written to {csv_path}")
print()
print(f"Next step: uv run skills/{SKILL_SLUG}/scripts/execute.py")
