# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Sandbox Self-Test — Run Suite
Exercise the toolkit against the seeded sandbox and write a graded report.

Three kinds of cases:
  1. before-smoke   — run every scripted skill's before.py as a subprocess
                      (read-only; asserts exit code 0)
  2. end-to-end     — run a skill's execute script with confirmations piped
                      in, then assert portal state via the Search API
  3. api-roundtrip  — create → verify → delete directly against the API
                      (lists, v4 workflows)

Cases a sandbox cannot simulate are reported SKIPPED with the reason —
never silently omitted. The report goes to reports/selftest-YYYY-MM-DD.md.
Exit code is non-zero if any case FAILED.

Usage:
  uv run skills/sandbox-self-test/scripts/run_suite.py           # run
  uv run skills/sandbox-self-test/scripts/run_suite.py --list    # show plan, no API calls
"""

import datetime
import glob
import os
import subprocess
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE = "https://api.hubapi.com"
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
EMAIL_DOMAIN = "selftest.hubspot-admin-skills.invalid"
ALLOWED_ACCOUNT_TYPES = {"DEVELOPER_TEST", "SANDBOX", "STANDARD_SANDBOX", "DEVELOPMENT_SANDBOX"}
SUBPROCESS_TIMEOUT = 600  # seconds per script


def sandbox_token():
    token = os.environ.get("HUBSPOT_SANDBOX_ACCESS_TOKEN")
    if not token:
        raise SystemExit("HUBSPOT_SANDBOX_ACCESS_TOKEN is not set. Run preflight.py first.")
    return token


def assert_sandbox(headers):
    """Fail-closed gate, re-checked before any mutation (defense in depth)."""
    resp = requests.get(f"{BASE}/account-info/v3/details", headers=headers, timeout=30)
    if resp.status_code != 200:
        raise SystemExit(f"REFUSED: could not verify account type ({resp.status_code}).")
    account_type = str(resp.json().get("accountType", "")).upper()
    if account_type not in ALLOWED_ACCOUNT_TYPES:
        raise SystemExit(f"REFUSED: accountType '{account_type}' is not a sandbox.")


def search_count(headers, object_type, filters):
    body = {"filterGroups": [{"filters": filters}], "limit": 1}
    resp = requests.post(f"{BASE}/crm/v3/objects/{object_type}/search",
                         headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    return resp.json().get("total", 0)


def run_script(rel_path, extra_env=None, stdin_text=""):
    """Run a repo script via uv with the sandbox token standing in for
    HUBSPOT_ACCESS_TOKEN, so the shipped scripts run unmodified."""
    env = dict(os.environ)
    env["HUBSPOT_ACCESS_TOKEN"] = sandbox_token()
    env.update(extra_env or {})
    proc = subprocess.run(
        ["uv", "run", rel_path],
        cwd=REPO_ROOT, env=env, input=stdin_text,
        capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT,
    )
    return proc


# ── Case implementations ─────────────────────────────────────────

def case_before_smoke(headers, script_rel):
    proc = run_script(script_rel)
    if proc.returncode != 0:
        return "FAIL", f"exit {proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}"
    return "PASS", "read-only before script ran clean"


def case_delete_no_email_e2e(headers):
    fixture_filters = [
        {"propertyName": "email", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "firstname", "operator": "EQ", "value": "SELFTEST NoEmail"},
    ]
    if search_count(headers, "contacts", fixture_filters) < 1:
        return "FAIL", "fixture missing — run seed.py first"
    proc = run_script("skills/delete-no-email-contacts/scripts/execute.py",
                      stdin_text="DELETE\n")
    if proc.returncode != 0:
        return "FAIL", f"execute.py exit {proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}"
    time.sleep(5)  # search index catch-up
    remaining = search_count(headers, "contacts", fixture_filters)
    if remaining:
        return "FAIL", f"{remaining} no-email fixture(s) survived deletion"
    return "PASS", "no-email contact found, deleted, verified gone"


def case_enrichment_mock_e2e(headers):
    target_filters = [
        {"propertyName": "email", "operator": "EQ",
         "value": f"enrichme@{EMAIL_DOMAIN}"},
        {"propertyName": "phone", "operator": "HAS_PROPERTY"},
    ]
    proc = run_script(
        "skills/waterfall-enrich-contacts/scripts/execute.py",
        extra_env={"ENRICHMENT_PROVIDER": "mock", "ENRICHMENT_MAX_CONTACTS": "25",
                   "ENRICHMENT_TARGET_FIELD": "phone"},
        stdin_text="ENRICH\nWRITE\n",
    )
    if proc.returncode != 0:
        return "FAIL", f"execute.py exit {proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}"
    time.sleep(5)
    if search_count(headers, "contacts", target_filters) < 1:
        return "FAIL", "mock enrichment ran but the fixture contact has no phone"
    return "PASS", "mock provider enriched the fixture contact's phone (no credits spent)"


def case_workflows_export(headers):
    proc = run_script("skills/workflows-as-code/scripts/export.py")
    if proc.returncode != 0:
        return "FAIL", f"export.py exit {proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}"
    today = datetime.date.today().isoformat()
    out_dir = os.path.join(REPO_ROOT, "data", "workflow-exports", today)
    if not os.path.isdir(out_dir):
        return "FAIL", f"export directory {out_dir} was not created"
    return "PASS", f"exported workflow JSON to data/workflow-exports/{today}/"


def case_list_roundtrip(headers):
    name = "[SELFTEST] List roundtrip"
    payload = {
        "name": name, "objectTypeId": "0-1", "processingType": "DYNAMIC",
        "filterBranch": {
            "filterBranchType": "OR", "filterBranchOperator": "OR", "filters": [],
            "filterBranches": [{
                "filterBranchType": "AND", "filterBranchOperator": "AND",
                "filterBranches": [],
                "filters": [{
                    "filterType": "PROPERTY", "property": "firstname",
                    "operation": {"operationType": "MULTISTRING",
                                  "operator": "CONTAINS", "values": ["SELFTEST"]},
                }],
            }],
        },
    }
    resp = requests.post(f"{BASE}/crm/v3/lists", headers=headers, json=payload, timeout=60)
    if resp.status_code not in (200, 201):
        return "FAIL", f"create returned {resp.status_code}: {resp.text[:300]}"
    list_id = resp.json().get("list", {}).get("listId") or resp.json().get("listId")
    if not list_id:
        return "FAIL", f"create succeeded but no listId in response: {resp.text[:200]}"
    resp = requests.get(f"{BASE}/crm/v3/lists/{list_id}", headers=headers, timeout=60)
    fetched = resp.status_code == 200
    resp = requests.delete(f"{BASE}/crm/v3/lists/{list_id}", headers=headers, timeout=60)
    deleted = resp.status_code in (200, 204)
    if not (fetched and deleted):
        return "FAIL", f"fetched={fetched} deleted={deleted} (listId {list_id})"
    return "PASS", f"dynamic list created, fetched, deleted (listId {list_id})"


def case_workflow_roundtrip(headers):
    name = "[SELFTEST] Workflow roundtrip"
    flow = {
        "type": "CONTACT_FLOW", "objectTypeId": "0-1", "flowType": "WORKFLOW",
        "name": name, "isEnabled": False,
        "startActionId": "1", "nextAvailableActionId": "2",
        "actions": [{
            "type": "SINGLE_CONNECTION", "actionId": "1",
            "actionTypeId": "0-5", "actionTypeVersion": 0,
            "fields": {"property_name": "lifecyclestage",
                       "value": {"staticValue": "lead"}},
        }],
        "enrollmentCriteria": {
            "type": "LIST_BASED", "shouldReEnroll": False,
            "unEnrollObjectsNotMeetingCriteria": False,
            "listFilterBranch": {
                "filterBranchType": "OR", "filterBranchOperator": "OR",
                "filters": [],
                "filterBranches": [{
                    "filterBranchType": "AND", "filterBranchOperator": "AND",
                    "filterBranches": [],
                    "filters": [{
                        "filterType": "PROPERTY", "property": "firstname",
                        "operation": {"operationType": "MULTISTRING",
                                      "operator": "IS_EQUAL_TO",
                                      "values": ["SELFTEST-NEVER-MATCHES"]},
                    }],
                }],
            },
            "reEnrollmentTriggersFilterBranches": [],
        },
    }
    resp = requests.post(f"{BASE}/automation/v4/flows", headers=headers, json=flow, timeout=60)
    if resp.status_code == 403:
        return "SKIP", "Automation API returned 403 — plan tier without workflows"
    if resp.status_code not in (200, 201):
        return "FAIL", f"create returned {resp.status_code}: {resp.text[:300]}"
    flow_id = resp.json().get("id")
    resp = requests.get(f"{BASE}/automation/v4/flows/{flow_id}", headers=headers, timeout=60)
    fetched = resp.status_code == 200 and resp.json().get("isEnabled") is False
    resp = requests.delete(f"{BASE}/automation/v4/flows/{flow_id}", headers=headers, timeout=60)
    deleted = resp.status_code in (200, 204)
    if not (fetched and deleted):
        return "FAIL", f"fetched-disabled={fetched} deleted={deleted} (flowId {flow_id})"
    return "PASS", f"disabled workflow created, verified, deleted (flowId {flow_id})"


# Cases no sandbox can simulate. Reported, never silently dropped.
NOT_SANDBOX_TESTABLE = [
    ("suppress-hard-bounced", "bounce state cannot be fabricated — HubSpot sets "
     "hs_email_hard_bounce_reason_enum only from real send events"),
    ("suppress-global-unsubscribes", "hs_email_optout is set by real unsubscribe "
     "events and cannot be written via API"),
    ("reassign-deactivated-owners", "deactivating a user requires seat/admin "
     "changes outside the API"),
    ("marketing-status changes (all suppress-* skills)", "hs_marketable_status is "
     "read-only via API; the workflow that sets it must be verified manually once"),
]


def main():
    list_only = "--list" in sys.argv

    scripted_before = sorted(glob.glob(os.path.join(REPO_ROOT, "skills", "*", "scripts", "before.py")))
    cases = []
    for path in scripted_before:
        rel = os.path.relpath(path, REPO_ROOT)
        skill = rel.split(os.sep)[1]
        cases.append((f"before-smoke: {skill}", "before-smoke",
                      lambda h, r=rel: case_before_smoke(h, r)))
    cases += [
        ("e2e: delete-no-email-contacts", "end-to-end", case_delete_no_email_e2e),
        ("e2e: waterfall-enrich-contacts (mock provider)", "end-to-end",
         case_enrichment_mock_e2e),
        ("e2e: workflows-as-code export", "end-to-end", case_workflows_export),
        ("api: lists round-trip", "api-roundtrip", case_list_roundtrip),
        ("api: v4 workflow round-trip", "api-roundtrip", case_workflow_roundtrip),
    ]

    print("=" * 60)
    print("SANDBOX SELF-TEST — SUITE")
    print("=" * 60)
    print()

    if list_only:
        print(f"{len(cases)} cases would run (no API calls made):")
        for name, kind, _ in cases:
            print(f"  [{kind:<13}] {name}")
        print()
        print(f"{len(NOT_SANDBOX_TESTABLE)} known-untestable areas would be reported as SKIPPED.")
        return

    token = sandbox_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    assert_sandbox(headers)

    results = []
    for name, kind, fn in cases:
        print(f"{name} ...", end=" ", flush=True)
        try:
            status, detail = fn(headers)
        except Exception as e:  # a crashing case is a failing case
            status, detail = "FAIL", f"exception: {e}"
        print(status)
        results.append({"case": name, "kind": kind, "status": status, "detail": detail})
        time.sleep(0.5)

    for area, reason in NOT_SANDBOX_TESTABLE:
        results.append({"case": f"skip: {area}", "kind": "not-sandbox-testable",
                        "status": "SKIP", "detail": reason})

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")

    today = datetime.date.today().isoformat()
    os.makedirs(os.path.join(REPO_ROOT, "reports"), exist_ok=True)
    report_path = os.path.join(REPO_ROOT, "reports", f"selftest-{today}.md")
    with open(report_path, "w") as f:
        f.write("# Sandbox Self-Test Report\n\n")
        f.write(f"**Date:** {today}\n\n")
        f.write(f"**Result:** {passed} passed, {failed} failed, {skipped} skipped\n\n")
        f.write("| Case | Kind | Status | Detail |\n|---|---|---|---|\n")
        for r in results:
            detail = r["detail"].replace("|", "\\|").replace("\n", " ")
            f.write(f"| {r['case']} | {r['kind']} | {r['status']} | {detail} |\n")
        f.write("\nSKIP entries under *not-sandbox-testable* are permanent, documented "
                "limits of sandbox testing — verify those paths once, manually, on a "
                "real portal (see SKILL.md).\n")

    print()
    print(f"  Passed:  {passed}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Report:  {report_path}")
    print()
    print("Next: uv run skills/sandbox-self-test/scripts/teardown.py")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
