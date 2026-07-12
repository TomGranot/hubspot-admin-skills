# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Engagement Suppression Workflow — After
Verify the workflows created by execute.py exist, and report their
enabled state. Workflows are created disabled: enable them in the UI
after review.
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


SKILL_SLUG = "engagement-suppression-workflow"
PLANNED_NAMES = ["SUNSET: Tier 1 - Flag for Re-engagement (180d, API)", "SUNSET: Tier 2 - Suppress Non-responders (+30d, API)"]

print("=" * 60)
print("AFTER: Engagement Suppression Workflow — verification")
print("=" * 60)
print()

flows = {f.get("name"): f for f in list_all_flows()}
missing, disabled, live = [], [], []

for name in PLANNED_NAMES:
    fl = flows.get(name)
    if not fl:
        missing.append(name)
        print(f"  MISSING: {name}")
    elif fl.get("isEnabled"):
        live.append(name)
        print(f"  ENABLED: {name} (flowId: {fl.get('id')})")
    else:
        disabled.append(name)
        print(f"  CREATED, NOT ENABLED: {name} (flowId: {fl.get('id')})")

print()
if missing:
    print(f"{len(missing)} workflow(s) missing — re-run execute.py or check its output.")
if disabled:
    print(f"{len(disabled)} workflow(s) awaiting review: open Automation > Workflows,")
    print("verify enrollment criteria and actions, then turn them on.")
if live and not missing and not disabled:
    print("SUCCESS: all workflows exist and are enabled.")
