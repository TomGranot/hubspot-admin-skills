"""
Hunter.io adapter.

Email finding by name + domain. Email-only (no phone enrichment).
Docs: https://hunter.io/api-documentation — Email Finder endpoint.

Auth: api_key query param from HUNTER_API_KEY.
"""

import os
import time

import requests

BASE = "https://api.hunter.io/v2"
MIN_SCORE = 80          # discard results below this confidence score
REQUEST_DELAY = 0.6     # Hunter rate-limits per-second on most plans


def _key():
    key = os.environ.get("HUNTER_API_KEY")
    if not key:
        raise SystemExit("HUNTER_API_KEY is not set in .env")
    return key


def enrich(contacts):
    results = []
    for c in contacts:
        if not (c.get("firstname") and c.get("lastname") and c.get("domain")):
            continue  # email finder needs name + domain
        resp = requests.get(f"{BASE}/email-finder", params={
            "domain": c["domain"],
            "first_name": c["firstname"],
            "last_name": c["lastname"],
            "api_key": _key(),
        })
        time.sleep(REQUEST_DELAY)
        if resp.status_code == 429:
            print("  Hunter rate limit hit; waiting 10s...")
            time.sleep(10)
            continue
        if resp.status_code != 200:
            continue
        data = resp.json().get("data", {})
        if data.get("email") and (data.get("score") or 0) >= MIN_SCORE:
            results.append({
                "id": c["id"],
                "email": data["email"],
                "source": f"hunter(score={data.get('score')})",
            })
    return results
