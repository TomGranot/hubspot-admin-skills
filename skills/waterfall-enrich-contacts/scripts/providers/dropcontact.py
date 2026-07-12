"""
Dropcontact adapter.

GDPR-compliant B2B email enrichment (algorithmic, no stored database).
Docs: https://developer.dropcontact.com — verify request/poll shapes.

Auth: X-Access-Token header from DROPCONTACT_API_KEY.
The API is asynchronous: submit a batch, then poll with the request_id.
"""

import os
import time

import requests

BASE = "https://api.dropcontact.com/v1"
BATCH_SIZE = 50
POLL_INTERVAL = 15
POLL_TIMEOUT = 600


def _headers():
    key = os.environ.get("DROPCONTACT_API_KEY")
    if not key:
        raise SystemExit("DROPCONTACT_API_KEY is not set in .env")
    return {"X-Access-Token": key, "Content-Type": "application/json"}


def enrich(contacts):
    results = []
    for i in range(0, len(contacts), BATCH_SIZE):
        batch = contacts[i:i + BATCH_SIZE]
        resp = requests.post(f"{BASE}/enrich/all", headers=_headers(), json={
            "data": [
                {
                    "first_name": c.get("firstname", ""),
                    "last_name": c.get("lastname", ""),
                    "company": c.get("company", ""),
                    "website": c.get("domain", ""),
                    "custom_fields": {"hubspot_id": c["id"]},
                }
                for c in batch
            ],
            "siren": False,
            "language": "en",
        })
        resp.raise_for_status()
        request_id = resp.json().get("request_id")
        if not request_id:
            print(f"  Dropcontact: unexpected response: {resp.text[:200]}")
            continue

        deadline = time.time() + POLL_TIMEOUT
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL)
            r = requests.get(f"{BASE}/enrich/all/{request_id}", headers=_headers())
            r.raise_for_status()
            data = r.json()
            if data.get("success") and data.get("data"):
                for c, row in zip(batch, data["data"]):
                    emails = row.get("email") or []
                    rec = {"id": c["id"], "source": "dropcontact"}
                    if emails:
                        rec["email"] = emails[0].get("email", "")
                    if row.get("phone"):
                        rec["phone"] = row["phone"]
                    if len(rec) > 2:
                        results.append(rec)
                break
        else:
            print(f"  Dropcontact batch {request_id} timed out")
    return results
