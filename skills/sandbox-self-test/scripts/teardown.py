# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Sandbox Self-Test — Teardown
Delete everything the seed script and suite created, matched strictly by the
selftest markers:

  - contacts whose email ends in @selftest.hubspot-admin-skills.invalid,
    plus the deliberate no-email fixture (firstname prefix SELFTEST)
  - companies whose name starts with SELFTEST
  - lists and workflows whose name starts with [SELFTEST]

Never deletes by "everything in the portal" — only by marker. Writes a CSV
audit log first, and requires typed confirmation.
"""

import csv
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE = "https://api.hubapi.com"
EMAIL_DOMAIN = "selftest.hubspot-admin-skills.invalid"
ALLOWED_ACCOUNT_TYPES = {"DEVELOPER_TEST", "SANDBOX", "STANDARD_SANDBOX", "DEVELOPMENT_SANDBOX"}
BATCH_SIZE = 100
BATCH_DELAY = 0.5


def sandbox_headers():
    token = os.environ.get("HUBSPOT_SANDBOX_ACCESS_TOKEN")
    if not token:
        raise SystemExit("HUBSPOT_SANDBOX_ACCESS_TOKEN is not set. Run preflight.py first.")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def assert_sandbox(headers):
    """Fail-closed gate, re-checked before any deletion (defense in depth)."""
    resp = requests.get(f"{BASE}/account-info/v3/details", headers=headers, timeout=30)
    if resp.status_code != 200:
        raise SystemExit(f"REFUSED: could not verify account type ({resp.status_code}).")
    account_type = str(resp.json().get("accountType", "")).upper()
    if account_type not in ALLOWED_ACCOUNT_TYPES:
        raise SystemExit(f"REFUSED: accountType '{account_type}' is not a sandbox.")


def search_all(headers, object_type, filters, properties):
    out, after = [], None
    while True:
        body = {"filterGroups": [{"filters": filters}],
                "properties": properties, "limit": 100}
        if after:
            body["after"] = after
        resp = requests.post(f"{BASE}/crm/v3/objects/{object_type}/search",
                             headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        out.extend(data.get("results", []))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
        time.sleep(0.15)
    return out


def batch_archive(headers, object_type, ids):
    archived = 0
    for i in range(0, len(ids), BATCH_SIZE):
        batch = ids[i:i + BATCH_SIZE]
        resp = requests.post(f"{BASE}/crm/v3/objects/{object_type}/batch/archive",
                             headers=headers,
                             json={"inputs": [{"id": x} for x in batch]}, timeout=60)
        if resp.status_code == 204:
            archived += len(batch)
        else:
            print(f"  WARNING: batch archive failed ({resp.status_code}): {resp.text[:200]}")
        time.sleep(BATCH_DELAY)
    return archived


def main():
    print("=" * 60)
    print("SANDBOX SELF-TEST — TEARDOWN")
    print("=" * 60)
    print()

    headers = sandbox_headers()
    assert_sandbox(headers)

    # --- Collect marked records ---
    contacts = search_all(
        headers, "contacts",
        [{"propertyName": "email", "operator": "CONTAINS_TOKEN",
          "value": f"*@{EMAIL_DOMAIN}"}],
        ["email", "firstname"])
    contacts += search_all(
        headers, "contacts",
        [{"propertyName": "email", "operator": "NOT_HAS_PROPERTY"},
         {"propertyName": "firstname", "operator": "EQ", "value": "SELFTEST NoEmail"}],
        ["email", "firstname"])
    companies = search_all(
        headers, "companies",
        [{"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": "SELFTEST"}],
        ["name", "domain"])
    # Belt and braces: only keep records that really carry the marker.
    contacts = [c for c in contacts
                if c.get("properties", {}).get("email", "").endswith(f"@{EMAIL_DOMAIN}")
                or str(c.get("properties", {}).get("firstname", "")).startswith("SELFTEST")]
    companies = [c for c in companies
                 if str(c.get("properties", {}).get("name", "")).startswith("SELFTEST")]

    # Suite lists/flows are deleted by their own round-trip cases; sweep strays.
    stray_lists = []
    resp = requests.post(f"{BASE}/crm/v3/lists/search", headers=headers,
                         json={"query": "[SELFTEST]", "count": 100}, timeout=60)
    if resp.status_code == 200:
        stray_lists = [l for l in resp.json().get("lists", [])
                       if str(l.get("name", "")).startswith("[SELFTEST]")]

    stray_flows = []
    after = None
    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after
        resp = requests.get(f"{BASE}/automation/v4/flows", headers=headers,
                            params=params, timeout=60)
        if resp.status_code != 200:
            break
        data = resp.json()
        stray_flows += [f for f in data.get("results", [])
                        if str(f.get("name", "")).startswith("[SELFTEST]")]
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
        time.sleep(0.15)

    total = len(contacts) + len(companies) + len(stray_lists) + len(stray_flows)
    print(f"  Marked contacts:  {len(contacts)}")
    print(f"  Marked companies: {len(companies)}")
    print(f"  Stray [SELFTEST] lists: {len(stray_lists)}")
    print(f"  Stray [SELFTEST] flows: {len(stray_flows)}")
    print()
    if total == 0:
        print("Nothing to tear down.")
        return

    # --- Audit log before deleting ---
    os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
    csv_path = os.path.join("data", "audit-logs", "sandbox-self-test-teardown.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["object_type", "id", "label"])
        for c in contacts:
            w.writerow(["contact", c["id"], c.get("properties", {}).get("email", "(no email)")])
        for c in companies:
            w.writerow(["company", c["id"], c.get("properties", {}).get("name", "")])
        for l in stray_lists:
            w.writerow(["list", l.get("listId"), l.get("name", "")])
        for fl in stray_flows:
            w.writerow(["flow", fl.get("id"), fl.get("name", "")])
    print(f"  Audit log: {csv_path}")
    print()

    confirm = input(f"Delete these {total} selftest objects? Type 'TEARDOWN' to confirm: ")
    if confirm != "TEARDOWN":
        print("Aborted by user.")
        return

    n = batch_archive(headers, "contacts", [c["id"] for c in contacts])
    print(f"  Contacts archived:  {n}")
    n = batch_archive(headers, "companies", [c["id"] for c in companies])
    print(f"  Companies archived: {n}")
    for l in stray_lists:
        requests.delete(f"{BASE}/crm/v3/lists/{l['listId']}", headers=headers, timeout=60)
        time.sleep(0.3)
    print(f"  Lists deleted:      {len(stray_lists)}")
    for fl in stray_flows:
        requests.delete(f"{BASE}/automation/v4/flows/{fl['id']}", headers=headers, timeout=60)
        time.sleep(0.3)
    print(f"  Flows deleted:      {len(stray_flows)}")
    print()
    print("Teardown complete. (Sandbox records are recoverable for 90 days via")
    print("Settings > Data Management > Deleted Objects, same as production.)")


if __name__ == "__main__":
    main()
