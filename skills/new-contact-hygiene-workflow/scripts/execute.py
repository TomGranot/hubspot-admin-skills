# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
New Contact Hygiene Workflow — Execute
Create the workflows via POST /automation/v4/flows. All flows are created DISABLED
for review in the UI before enabling.
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

# ── Configuration ────────────────────────────────────────────────
DEFAULT_LIFECYCLE_STAGE = "lead"

SKILL_SLUG = "new-contact-hygiene-workflow"
SKILL_TITLE = "New Contact Hygiene"

# ── Filter helpers (Lists/Workflows filter grammar) ──────────────

def prop_known(name):
    return {"filterType": "PROPERTY", "property": name,
            "operation": {"operationType": "ALL_PROPERTY", "operator": "IS_KNOWN"}}


def prop_unknown(name):
    return {"filterType": "PROPERTY", "property": name,
            "operation": {"operationType": "ALL_PROPERTY", "operator": "IS_NOT_KNOWN"}}


def prop_eq_enum(name, value):
    return {"filterType": "PROPERTY", "property": name,
            "operation": {"operationType": "ENUMERATION", "operator": "IS_ANY_OF",
                          "values": [value]}}


def prop_eq_str(name, value):
    return {"filterType": "PROPERTY", "property": name,
            "operation": {"operationType": "MULTISTRING", "operator": "IS_EQUAL_TO",
                          "values": [value]}}


def prop_not_true(name):
    return {"filterType": "PROPERTY", "property": name,
            "operation": {"operationType": "BOOL", "operator": "IS_NOT_EQUAL_TO",
                          "value": True, "includeObjectsWithNoValueSet": True}}


def prop_bool(name, value):
    return {"filterType": "PROPERTY", "property": name,
            "operation": {"operationType": "BOOL", "operator": "IS_EQUAL_TO",
                          "value": value}}


def prop_gte(name, value):
    return {"filterType": "PROPERTY", "property": name,
            "operation": {"operationType": "NUMBER",
                          "operator": "IS_GREATER_THAN_OR_EQUAL_TO", "value": value}}


def prop_older_than(name, days, include_never=False):
    """Property date is more than `days` ago (optionally matching never-set)."""
    return {"filterType": "PROPERTY", "property": name,
            "operation": {"operationType": "TIME_POINT", "operator": "IS_BEFORE",
                          "includeObjectsWithNoValueSet": include_never,
                          "timePoint": {"timeType": "INDEXED",
                                        "timezoneSource": "PORTAL",
                                        "zoneId": os.environ.get("HUBSPOT_TIMEZONE", "UTC"),
                                        "indexReference": {"referenceType": "TODAY"},
                                        "offset": {"amount": -days, "unit": "DAY"}}}}


def and_branch(filters):
    return {"filterBranchType": "AND", "filterBranchOperator": "AND",
            "filters": filters, "filterBranches": []}


def enrollment(filters, re_enroll=False):
    """LIST_BASED enrollment criteria with a single AND filter group."""
    return {"type": "LIST_BASED", "shouldReEnroll": re_enroll,
            "unEnrollObjectsNotMeetingCriteria": False,
            "listFilterBranch": {"filterBranchType": "OR", "filterBranchOperator": "OR",
                                 "filters": [],
                                 "filterBranches": [and_branch(filters)]},
            "reEnrollmentTriggersFilterBranches": []}


def set_property_action(action_id, prop, value, next_id=None):
    a = {"type": "SINGLE_CONNECTION", "actionId": str(action_id),
         "actionTypeId": "0-5", "actionTypeVersion": 0,
         "fields": {"property_name": prop, "value": {"staticValue": value}}}
    if next_id:
        a["connection"] = {"edgeType": "STANDARD", "nextActionId": str(next_id)}
    return a


def set_marketing_status_action(action_id, marketable, next_id=None):
    """Set marketing contact status (actionTypeId 0-31).

    HubSpot does not document this action's fields; this shape follows the
    set-property pattern. If flow creation returns 400, the execute script
    automatically retries without this action — add "Set marketing contact
    status" in the UI during review instead (or build it once in the UI and
    GET /automation/v4/flows/{flowId} to capture the exact fields).
    """
    a = {"type": "SINGLE_CONNECTION", "actionId": str(action_id),
         "actionTypeId": "0-31", "actionTypeVersion": 0,
         "fields": {"value": {"staticValue": "false" if not marketable else "true"}}}
    if next_id:
        a["connection"] = {"edgeType": "STANDARD", "nextActionId": str(next_id)}
    return a


def contact_flow(name, filters, actions, re_enroll=False):
    return {"type": "CONTACT_FLOW", "objectTypeId": "0-1", "flowType": "WORKFLOW",
            "name": name, "isEnabled": False,
            "startActionId": actions[0]["actionId"],
            "nextAvailableActionId": str(len(actions) + 1),
            "actions": actions,
            "enrollmentCriteria": enrollment(filters, re_enroll)}

FLOWS = [
    # The API-expressible core: default lifecycle stage for new contacts.
    # The copy-from-associated-company actions and the no-company notification
    # branch are added in the UI during review (their action fields are not
    # documented in the v4 API; see SKILL.md).
    contact_flow(
        name="HYGIENE: Default Lifecycle Stage for New Contacts (API)",
        filters=[
            prop_known("createdate"),
            prop_unknown("lifecyclestage"),
        ],
        actions=[set_property_action(1, "lifecyclestage", DEFAULT_LIFECYCLE_STAGE)],
        re_enroll=True,
    ),
]

# ── Main ─────────────────────────────────────────────────────────

print("=" * 60)
print(f"EXECUTE: {SKILL_TITLE} — create workflows via v4 API")
print("=" * 60)
print()
print("All workflows are created DISABLED. Review each one in")
print("Automation > Workflows and turn it on only after inspection.")
print()

existing = {f.get("name") for f in list_all_flows()}
audit = []

for flow in FLOWS:
    name = flow["name"]
    print(f"Creating: {name}...", end=" ")
    if name in existing:
        print("SKIPPED (a flow with this name already exists)")
        audit.append({"name": name, "flow_id": "existing", "status": "skipped"})
        continue

    resp = api("POST", "/automation/v4/flows", json=flow)

    if resp.status_code == 400 and any(a.get("actionTypeId") == "0-31"
                                       for a in flow["actions"]):
        # The undocumented set-marketing-status action may be rejected.
        # Retry without it; the user adds that action in the UI during review.
        print("400 — retrying without the set-marketing-status action...", end=" ")
        trimmed = [a for a in flow["actions"] if a.get("actionTypeId") != "0-31"]
        for a in trimmed:
            if a.get("connection") and not any(
                    b["actionId"] == a["connection"]["nextActionId"] for b in trimmed):
                a.pop("connection")
        flow2 = dict(flow, actions=trimmed,
                     startActionId=trimmed[0]["actionId"],
                     nextAvailableActionId=str(len(trimmed) + 1))
        resp = api("POST", "/automation/v4/flows", json=flow2)
        if resp.status_code in (200, 201):
            fid = resp.json().get("id", "unknown")
            print(f"OK (flowId: {fid})")
            print("  ACTION NEEDED: add the 'Set marketing contact status' action")
            print("  to this workflow in the UI before enabling it.")
            audit.append({"name": name, "flow_id": fid,
                          "status": "created_without_marketing_status_action"})
            time.sleep(0.5)
            continue

    if resp.status_code in (200, 201):
        fid = resp.json().get("id", "unknown")
        print(f"OK (flowId: {fid})")
        audit.append({"name": name, "flow_id": fid, "status": "created"})
    else:
        print(f"FAILED ({resp.status_code}: {resp.text[:300]})")
        print("  If the payload shape was rejected: build this workflow once in")
        print("  the UI, GET /automation/v4/flows/{flowId}, and adapt this script")
        print("  to the exact field shapes your portal returns.")
        audit.append({"name": name, "flow_id": "",
                      "status": f"failed_{resp.status_code}"})
    time.sleep(0.5)

os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
csv_path = os.path.join("data", "audit-logs", f"{SKILL_SLUG}-execute.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["name", "flow_id", "status"])
    w.writeheader()
    w.writerows(audit)

print()
print(f"Audit trail written to {csv_path}")
print()
print("Next steps:")
print("  1. Open Automation > Workflows and review each created workflow.")
print("  2. Add the UI-only pieces noted in SKILL.md (if any).")
print("  3. Turn each workflow on, choosing whether to enroll existing records.")
print(f"  4. Run: uv run skills/{SKILL_SLUG}/scripts/after.py")
