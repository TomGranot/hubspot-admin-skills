# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Sandbox Self-Test — Seed
Create the synthetic fixture set the suite runs against. Every record is
triple-marked so teardown can find it and nothing can be mistaken for real
data:

  - contact emails end in @selftest.hubspot-admin-skills.invalid
    (.invalid is a reserved TLD — these addresses can never receive mail)
  - contact first names start with SELFTEST
  - company names start with "SELFTEST" and domains match selftest-*.invalid

Idempotent: existing fixtures (matched by email / domain) are left in place.
"""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE = "https://api.hubapi.com"
EMAIL_DOMAIN = "selftest.hubspot-admin-skills.invalid"
ALLOWED_ACCOUNT_TYPES = {"DEVELOPER_TEST", "SANDBOX", "STANDARD_SANDBOX", "DEVELOPMENT_SANDBOX"}


def sandbox_headers():
    token = os.environ.get("HUBSPOT_SANDBOX_ACCESS_TOKEN")
    if not token:
        raise SystemExit("HUBSPOT_SANDBOX_ACCESS_TOKEN is not set. Run preflight.py first.")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def assert_sandbox(headers):
    """Same fail-closed gate as preflight — re-checked here in case this
    script is run on its own."""
    resp = requests.get(f"{BASE}/account-info/v3/details", headers=headers, timeout=30)
    if resp.status_code != 200:
        raise SystemExit(f"REFUSED: could not verify account type ({resp.status_code}).")
    account_type = str(resp.json().get("accountType", "")).upper()
    if account_type not in ALLOWED_ACCOUNT_TYPES:
        raise SystemExit(f"REFUSED: accountType '{account_type}' is not a sandbox.")


# ── Fixture matrix ───────────────────────────────────────────────
# One defect per testable skill. Comments name the skill each row exercises.

CONTACTS = [
    # delete-no-email-contacts: a contact with NO email at all.
    {"firstname": "SELFTEST NoEmail", "lastname": "One"},
    # assign-unowned-contacts / audit owner health: contacts with no owner.
    {"email": f"unowned.one@{EMAIL_DOMAIN}",
     "firstname": "SELFTEST Unowned", "lastname": "One",
     "lifecyclestage": "lead"},
    {"email": f"unowned.two@{EMAIL_DOMAIN}",
     "firstname": "SELFTEST Unowned", "lastname": "Two",
     "lifecyclestage": "lead"},
    # fix-lifecycle-stages / new-contact-hygiene flow: lifecycle never set.
    {"email": f"nostage@{EMAIL_DOMAIN}",
     "firstname": "SELFTEST NoStage", "lastname": "One"},
    # standardize-geo-values: three spellings of the same country.
    {"email": f"geo.one@{EMAIL_DOMAIN}",
     "firstname": "SELFTEST Geo", "lastname": "One", "country": "USA"},
    {"email": f"geo.two@{EMAIL_DOMAIN}",
     "firstname": "SELFTEST Geo", "lastname": "Two", "country": "U.S."},
    {"email": f"geo.three@{EMAIL_DOMAIN}",
     "firstname": "SELFTEST Geo", "lastname": "Three", "country": "united states"},
    # enrich-company-name: associated to SELFTEST Acme below, company prop empty.
    {"email": f"nocompany@{EMAIL_DOMAIN}",
     "firstname": "SELFTEST NoCompany", "lastname": "One",
     "_associate_to": "selftest-acme.invalid"},
    # waterfall-enrich-contacts (mock provider): enrichable, missing phone.
    {"email": f"enrichme@{EMAIL_DOMAIN}",
     "firstname": "SELFTEST Enrich", "lastname": "Target",
     "company": "SELFTEST Acme"},
]

COMPANIES = [
    # enrich-company-name source + enrichment domain.
    {"name": "SELFTEST Acme", "domain": "selftest-acme.invalid",
     "industry": "COMPUTER_SOFTWARE"},
    # merge-duplicate-companies: two companies sharing one domain.
    {"name": "SELFTEST Dup Alpha", "domain": "selftest-dup.invalid"},
    {"name": "SELFTEST Dup Beta", "domain": "selftest-dup.invalid"},
]


def find_contact_by_email(headers, email):
    body = {"filterGroups": [{"filters": [
        {"propertyName": "email", "operator": "EQ", "value": email}]}], "limit": 1}
    resp = requests.post(f"{BASE}/crm/v3/objects/contacts/search", headers=headers, json=body)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0]["id"] if results else None


def find_noemail_fixture(headers):
    body = {"filterGroups": [{"filters": [
        {"propertyName": "email", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "firstname", "operator": "EQ", "value": "SELFTEST NoEmail"},
    ]}], "limit": 1}
    resp = requests.post(f"{BASE}/crm/v3/objects/contacts/search", headers=headers, json=body)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0]["id"] if results else None


def main():
    print("=" * 60)
    print("SANDBOX SELF-TEST — SEED")
    print("=" * 60)
    print()

    headers = sandbox_headers()
    assert_sandbox(headers)

    # Companies first so contacts can associate to them.
    company_ids = {}
    print("Companies:")
    for comp in COMPANIES:
        # Companies may legitimately share a domain (that IS the dup fixture),
        # so match on name instead.
        body = {"filterGroups": [{"filters": [
            {"propertyName": "name", "operator": "EQ", "value": comp["name"]}]}], "limit": 1}
        resp = requests.post(f"{BASE}/crm/v3/objects/companies/search", headers=headers, json=body)
        resp.raise_for_status()
        existing = resp.json().get("results", [])
        if existing:
            cid = existing[0]["id"]
            print(f"  {comp['name']:<24} exists (id {cid})")
        else:
            resp = requests.post(f"{BASE}/crm/v3/objects/companies",
                                 headers=headers, json={"properties": comp})
            resp.raise_for_status()
            cid = resp.json()["id"]
            print(f"  {comp['name']:<24} created (id {cid})")
        company_ids[comp["domain"]] = cid
        time.sleep(0.2)

    print()
    print("Contacts:")
    for contact in CONTACTS:
        props = {k: v for k, v in contact.items() if not k.startswith("_")}
        email = props.get("email")
        existing_id = (find_contact_by_email(headers, email) if email
                       else find_noemail_fixture(headers))
        label = email or f"{props['firstname']} {props['lastname']} (no email)"
        if existing_id:
            print(f"  {label:<52} exists (id {existing_id})")
            cid = existing_id
        else:
            resp = requests.post(f"{BASE}/crm/v3/objects/contacts",
                                 headers=headers, json={"properties": props})
            resp.raise_for_status()
            cid = resp.json()["id"]
            print(f"  {label:<52} created (id {cid})")

        assoc_domain = contact.get("_associate_to")
        if assoc_domain and assoc_domain in company_ids:
            resp = requests.put(
                f"{BASE}/crm/v4/objects/contacts/{cid}/associations/default/"
                f"companies/{company_ids[assoc_domain]}",
                headers=headers)
            if resp.status_code not in (200, 201):
                print(f"    WARNING: association failed ({resp.status_code})")
        time.sleep(0.2)

    print()
    print(f"Seeded {len(COMPANIES)} companies and {len(CONTACTS)} contacts.")
    print("Next: uv run skills/sandbox-self-test/scripts/run_suite.py")


if __name__ == "__main__":
    main()
