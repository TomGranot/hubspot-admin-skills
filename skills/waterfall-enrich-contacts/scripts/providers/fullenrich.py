"""
FullEnrich adapter (default provider).

Waterfall email + phone enrichment across 20+ upstream data sources.
Docs: https://docs.fullenrich.com — verify endpoint/field names against
the current API reference before large runs; this adapter targets the
bulk enrich API.

Auth: Bearer token from FULLENRICH_API_KEY (dashboard > Settings > API).
Billing: credit-based per lookup (phone lookups cost more than email).
The bulk API is asynchronous: submit, then poll until complete.
"""

import os
import time

import requests

BASE = "https://app.fullenrich.com/api/v1"
BATCH_SIZE = 50          # contacts per bulk submission
POLL_INTERVAL = 10       # seconds between polls
POLL_TIMEOUT = 600       # give up after 10 minutes per batch


def _headers():
    key = os.environ.get("FULLENRICH_API_KEY")
    if not key:
        raise SystemExit("FULLENRICH_API_KEY is not set in .env")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def enrich(contacts):
    results = []
    for i in range(0, len(contacts), BATCH_SIZE):
        batch = contacts[i:i + BATCH_SIZE]
        results.extend(_enrich_batch(batch))
    return results


def _enrich_batch(batch):
    payload = {
        "name": "hubspot-admin-skills enrichment",
        "datas": [
            {
                "firstname": c.get("firstname", ""),
                "lastname": c.get("lastname", ""),
                "domain": c.get("domain", ""),
                "company_name": c.get("company", ""),
                "linkedin_url": c.get("linkedin_url", ""),
                "enrich_fields": ["contact.emails", "contact.phones"],
                # custom fields round-trip untouched — used to map results
                # back to HubSpot contact ids
                "custom": {"hubspot_id": c["id"]},
            }
            for c in batch
        ],
    }
    resp = requests.post(f"{BASE}/contact/enrich/bulk", headers=_headers(),
                         json=payload)
    if resp.status_code == 402:
        raise SystemExit("FullEnrich: out of credits (HTTP 402). Aborting.")
    resp.raise_for_status()
    enrichment_id = resp.json().get("enrichment_id") or resp.json().get("id")
    if not enrichment_id:
        raise SystemExit(f"FullEnrich: unexpected submit response: {resp.text[:300]}")

    # Poll for completion
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        r = requests.get(f"{BASE}/contact/enrich/bulk/{enrichment_id}",
                         headers=_headers())
        r.raise_for_status()
        data = r.json()
        status = (data.get("status") or "").upper()
        if status in ("FINISHED", "COMPLETED", "DONE"):
            return _parse(data)
        if status in ("FAILED", "CANCELED"):
            print(f"  FullEnrich batch {enrichment_id} ended with status {status}")
            return []
    print(f"  FullEnrich batch {enrichment_id} timed out after {POLL_TIMEOUT}s")
    return []


def _parse(data):
    out = []
    for item in data.get("datas", []):
        custom = item.get("custom", {})
        contact = item.get("contact", {}) or {}
        emails = contact.get("emails") or []
        phones = contact.get("phones") or []
        rec = {"id": custom.get("hubspot_id"), "source": "fullenrich"}
        # take the highest-confidence (first) result of each type
        if emails:
            rec["email"] = emails[0].get("email", "")
        if phones:
            rec["phone"] = phones[0].get("number", "")
        if rec.get("email") or rec.get("phone"):
            out.append(rec)
    return out
