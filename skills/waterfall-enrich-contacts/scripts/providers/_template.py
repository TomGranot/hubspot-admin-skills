"""
Template for a custom enrichment provider adapter.

1. Copy this file to providers/<yourprovider>.py
2. Implement enrich() against your provider's API
3. Register it in providers/__init__.py:  PROVIDERS["yourprovider"] = "yourprovider"
4. Set in .env:  ENRICHMENT_PROVIDER=yourprovider  and  YOURPROVIDER_API_KEY=...

Contract:
  enrich(contacts: list[dict]) -> list[dict]

  Input items (missing values are empty strings):
    {"id": "<hubspot contact id>", "email": "", "firstname": "",
     "lastname": "", "company": "", "domain": "", "linkedin_url": ""}

  Output items — include ONLY fields your provider actually found:
    {"id": "<same hubspot id>", "email": "...", "phone": "...",
     "jobtitle": "...", "company": "...", "source": "yourprovider"}

Rules:
  - Never invent values; omit fields you did not find.
  - Respect the provider's rate limits inside this module.
  - Raise SystemExit with a clear message on auth/credit failures so the
    execute script aborts before touching HubSpot.
"""

import os

import requests  # noqa: F401


def enrich(contacts):
    key = os.environ.get("YOURPROVIDER_API_KEY")
    if not key:
        raise SystemExit("YOURPROVIDER_API_KEY is not set in .env")

    results = []
    for c in contacts:
        # ... call your provider here ...
        # results.append({"id": c["id"], "email": found_email,
        #                 "source": "yourprovider"})
        pass
    return results
