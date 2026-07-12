"""
Apollo.io adapter.

People match/enrichment from Apollo's B2B database.
Docs: https://docs.apollo.io — verify the bulk people match endpoint and
credit consumption before large runs.

Auth: x-api-key header from APOLLO_API_KEY.
Note: revealing personal emails/phones consumes credits and may require
specific plan features; unrevealed fields come back masked.
"""

import os

import requests

BASE = "https://api.apollo.io/api/v1"
BATCH_SIZE = 10  # bulk_match accepts up to 10 details per call


def _headers():
    key = os.environ.get("APOLLO_API_KEY")
    if not key:
        raise SystemExit("APOLLO_API_KEY is not set in .env")
    return {"x-api-key": key, "Content-Type": "application/json"}


def enrich(contacts):
    results = []
    for i in range(0, len(contacts), BATCH_SIZE):
        batch = contacts[i:i + BATCH_SIZE]
        resp = requests.post(
            f"{BASE}/people/bulk_match",
            headers=_headers(),
            json={
                "reveal_personal_emails": False,
                "details": [
                    {
                        "first_name": c.get("firstname", ""),
                        "last_name": c.get("lastname", ""),
                        "organization_name": c.get("company", ""),
                        "domain": c.get("domain", ""),
                        "email": c.get("email", ""),
                    }
                    for c in batch
                ],
            },
        )
        resp.raise_for_status()
        matches = resp.json().get("matches", [])
        for c, person in zip(batch, matches):
            if not person:
                continue
            rec = {"id": c["id"], "source": "apollo"}
            if person.get("email") and "email_not_unlocked" not in person["email"]:
                rec["email"] = person["email"]
            if person.get("title"):
                rec["jobtitle"] = person["title"]
            org = person.get("organization") or {}
            if org.get("name"):
                rec["company"] = org["name"]
            if len(rec) > 2:
                results.append(rec)
    return results
