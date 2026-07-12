# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Workflows as Code — Export
Export every workflow's full JSON definition via the v4 Automation API.

Writes one JSON file per workflow plus a manifest.csv into
data/workflow-exports/<YYYY-MM-DD>/.
"""

import csv
import datetime
import json
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
    for attempt in range(MAX_RETRIES):
        resp = requests.request(method, f"{BASE}{path}", headers=HEADERS, **kwargs)
        if resp.status_code == 429:
            wait = min(10 * (attempt + 1), 30)
            print(f"  Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        return resp
    return resp


print("=" * 60)
print("WORKFLOWS AS CODE — EXPORT")
print("=" * 60)
print()

# --- Step 1: List all flows ---
print("Step 1: Listing all workflows...")
summaries, after = [], None
while True:
    params = {"limit": 100}
    if after:
        params["after"] = after
    resp = api("GET", "/automation/v4/flows", params=params)
    if resp.status_code == 403:
        print("403 Forbidden: the Automation API requires the 'automation' scope and")
        print("a plan tier that includes workflows. Cannot export.")
        raise SystemExit(1)
    resp.raise_for_status()
    data = resp.json()
    summaries.extend(data.get("results", []))
    after = data.get("paging", {}).get("next", {}).get("after")
    if not after:
        break
    time.sleep(0.15)

print(f"  Found {len(summaries)} workflows")
print()

# --- Step 2: Fetch full definitions ---
print("Step 2: Fetching full definitions...")
flows = {}

# Try the batch read endpoint first (100 per call), fall back to per-flow GETs.
BATCH = 100
batch_supported = True
for i in range(0, len(summaries), BATCH):
    chunk = summaries[i:i + BATCH]
    if batch_supported:
        resp = api("POST", "/automation/v4/flows/batch/read", json={
            "inputs": [{"flowId": str(s["id"]), "type": "FLOW_ID"} for s in chunk],
        })
        if resp.status_code in (200, 201):
            for fl in resp.json().get("results", []):
                flows[str(fl["id"])] = fl
            print(f"  Batch read {min(i + BATCH, len(summaries))}/{len(summaries)}")
            time.sleep(0.3)
            continue
        print(f"  Batch read unavailable ({resp.status_code}); "
              "falling back to per-flow GETs")
        batch_supported = False
    for s in chunk:
        fid = str(s["id"])
        if fid in flows:
            continue
        r = api("GET", f"/automation/v4/flows/{fid}")
        if r.status_code == 200:
            flows[fid] = r.json()
        else:
            print(f"  WARNING: could not fetch flow {fid} ({r.status_code})")
        time.sleep(0.15)

print(f"  Fetched {len(flows)} full definitions")
print()

# --- Step 3: Write export files + manifest ---
today = datetime.date.today().isoformat()
out_dir = os.path.join("data", "workflow-exports", today)
os.makedirs(out_dir, exist_ok=True)

manifest = []
for fid, fl in sorted(flows.items()):
    fname = f"flow-{fid}.json"
    with open(os.path.join(out_dir, fname), "w") as f:
        json.dump(fl, f, indent=2, sort_keys=True)
    manifest.append({
        "flow_id": fid,
        "name": fl.get("name", ""),
        "type": fl.get("type", ""),
        "is_enabled": fl.get("isEnabled", ""),
        "revision_id": fl.get("revisionId", ""),
        "file": fname,
    })

with open(os.path.join(out_dir, "manifest.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["flow_id", "name", "type", "is_enabled",
                                      "revision_id", "file"])
    w.writeheader()
    w.writerows(manifest)

print("=" * 60)
print("EXPORT SUMMARY")
print("=" * 60)
print(f"  Workflows listed:   {len(summaries)}")
print(f"  Definitions saved:  {len(flows)}")
print(f"  Export directory:   {out_dir}")
print()
print("  Keep exports in a PRIVATE repository — they contain workflow")
print("  names, property names, and notification text.")
