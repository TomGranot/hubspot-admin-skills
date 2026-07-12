# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Sandbox Self-Test — Preflight
Verify the token points at a disposable portal (DEVELOPER_TEST or SANDBOX),
probe the scopes the suite needs, and print a go/no-go checklist.

This gate FAILS CLOSED: any error verifying the account type is a refusal.
There is deliberately no override flag.
"""

import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE = "https://api.hubapi.com"

# The suite refuses to run against anything that is not one of these.
ALLOWED_ACCOUNT_TYPES = {"DEVELOPER_TEST", "SANDBOX", "STANDARD_SANDBOX", "DEVELOPMENT_SANDBOX"}


def sandbox_headers():
    """Return auth headers for the sandbox token, refusing production tokens.

    The self-test suite uses its own env var so a production token sitting in
    HUBSPOT_ACCESS_TOKEN can never be picked up by accident.
    """
    token = os.environ.get("HUBSPOT_SANDBOX_ACCESS_TOKEN")
    if not token:
        raise SystemExit(
            "HUBSPOT_SANDBOX_ACCESS_TOKEN is not set.\n"
            "The self-test suite never reads HUBSPOT_ACCESS_TOKEN. Create a free\n"
            "developer test account (Settings > Testing > Developer test accounts),\n"
            "create a private app inside it, and put its token in .env as\n"
            "HUBSPOT_SANDBOX_ACCESS_TOKEN."
        )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def assert_sandbox(headers):
    """Hard gate: the token's portal must be a developer test account or sandbox."""
    try:
        resp = requests.get(f"{BASE}/account-info/v3/details", headers=headers, timeout=30)
    except requests.RequestException as e:
        raise SystemExit(f"REFUSED: could not verify account type ({e}). Failing closed.")
    if resp.status_code != 200:
        raise SystemExit(
            f"REFUSED: could not verify account type "
            f"(GET /account-info/v3/details returned {resp.status_code}). Failing closed.\n"
            "If this is a scope problem, no additional scope should be needed for this\n"
            "endpoint — verify the token itself."
        )
    info = resp.json()
    account_type = str(info.get("accountType", "")).upper()
    if account_type not in ALLOWED_ACCOUNT_TYPES:
        raise SystemExit(
            f"REFUSED: portal {info.get('portalId', '?')} has accountType "
            f"'{account_type or 'unknown'}'.\n"
            "The self-test suite only runs against DEVELOPER_TEST or SANDBOX portals.\n"
            "It seeds, mutates, and deletes data — never point it at production.\n"
            "There is no override."
        )
    return info


SCOPE_PROBES = [
    # (label, method, path, payload, needed by)
    ("Contacts read/search", "POST", "/crm/v3/objects/contacts/search",
     {"limit": 1}, "all suites"),
    ("Companies read/search", "POST", "/crm/v3/objects/companies/search",
     {"limit": 1}, "seed, hygiene suites"),
    ("Owners read", "GET", "/crm/v3/owners?limit=1", None, "before-script smokes"),
    ("Lists read", "GET", "/crm/v3/lists/search?count=1", None, "lists round-trip"),
    ("Automation (v4 flows)", "GET", "/automation/v4/flows?limit=1", None,
     "workflow round-trip, workflows-as-code export"),
]


def main():
    print("=" * 60)
    print("SANDBOX SELF-TEST — PREFLIGHT")
    print("=" * 60)
    print()

    headers = sandbox_headers()
    info = assert_sandbox(headers)

    print(f"  Portal ID:     {info.get('portalId')}")
    print(f"  Account type:  {info.get('accountType')}  (allowed)")
    print(f"  Data location: {info.get('dataHostingLocation', 'unknown')}")
    print()

    print("Scope probes:")
    failures = []
    for label, method, path, payload, needed_by in SCOPE_PROBES:
        if method == "GET":
            resp = requests.get(f"{BASE}{path}", headers=headers, timeout=30)
        else:
            resp = requests.post(f"{BASE}{path}", headers=headers, json=payload, timeout=30)
        ok = resp.status_code in (200, 201)
        status = "OK" if ok else f"FAILED ({resp.status_code})"
        print(f"  {label:<28} {status:<14} needed by: {needed_by}")
        if not ok:
            failures.append(label)
        time.sleep(0.15)

    print()
    if failures:
        print("NO-GO. Grant the missing scopes to the sandbox private app:")
        print("  crm.objects.contacts.read/write, crm.objects.companies.read/write,")
        print("  crm.objects.owners.read, crm.lists.read/write, automation")
        print(f"  (failed probes: {', '.join(failures)})")
        sys.exit(1)

    print("GO. Next steps:")
    print("  uv run skills/sandbox-self-test/scripts/seed.py")
    print("  uv run skills/sandbox-self-test/scripts/run_suite.py")
    print("  uv run skills/sandbox-self-test/scripts/teardown.py")


if __name__ == "__main__":
    main()
