"""
Cleanup Deals — shared finding definitions.

Imported by before.py, execute.py, and after.py (Python puts the running
script's directory on sys.path, so `import deal_findings` resolves next to
them). Defining the findings once keeps the three stages counting exactly
the same deals.

Every function here is read-only. The only HTTP methods it issues are GET
and POST to /search or /batch/read.
"""

import datetime
import os
import sys
import time

import requests
from dotenv import load_dotenv

# --- Configuration ---
API_VERSION = "2026-09"       # HubSpot date-based API version (see CONTRIBUTING.md)
BASE = "https://api.hubapi.com"
STALE_DAYS_DEFAULT = 60       # open deal with no logged activity for this long
SEARCH_RESULT_CAP = 10_000    # the Search API will not page past this many results
QUERY_DELAY = 0.25            # seconds between search pages (Search API allows 5/s)
MAX_RETRIES = 5
AUDIT_DIR = os.path.join("data", "audit-logs")

# Name tokens that mark a likely test deal. "demo" is deliberately absent:
# real deals are often named after the demo that opened them.
TEST_NAME_TOKENS = ("test", "dummy", "sample", "asdf")

SALESFORCE_ID = "hs_salesforceopportunityid"

DEAL_PROPERTIES = [
    "dealname", "amount", "closedate", "createdate", "dealstage", "pipeline",
    "hubspot_owner_id", "hs_is_closed", "hs_is_closed_won", "closed_lost_reason",
    "notes_last_updated", "num_associated_contacts", SALESFORCE_ID,
]

CSV_FIELDS = [
    "id", "dealname", "amount", "closedate", "dealstage", "pipeline",
    "hubspot_owner_id", "notes_last_updated", "createdate", "closed_lost_reason",
]

HEADERS = {}


# ── Setup ────────────────────────────────────────────────────────

def authenticate():
    """Load HUBSPOT_ACCESS_TOKEN from .env (working directory first, then the
    skill directory) and set the request headers. Exits if the token is missing."""
    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if not token:
        sys.exit("HUBSPOT_ACCESS_TOKEN is not set. Put a HubSpot service key in .env.")
    HEADERS.clear()
    HEADERS.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})


# ── HTTP ─────────────────────────────────────────────────────────

def api(method, path, **kwargs):
    """One HubSpot call with backoff on 429. Returns the final response."""
    for attempt in range(MAX_RETRIES):
        resp = requests.request(method, f"{BASE}{path}", headers=HEADERS, timeout=60, **kwargs)
        if resp.status_code == 429:
            wait = min(10 * (attempt + 1), 30)
            print(f"    Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        return resp
    return resp


def deals_path(suffix=""):
    return f"/crm/objects/{API_VERSION}/deals{suffix}"


# ── Filters ──────────────────────────────────────────────────────

def f_eq(prop, value):
    return {"propertyName": prop, "operator": "EQ", "value": str(value)}


def f_lt(prop, value):
    return {"propertyName": prop, "operator": "LT", "value": str(value)}


def f_missing(prop):
    return {"propertyName": prop, "operator": "NOT_HAS_PROPERTY"}


def f_token(prop, token):
    return {"propertyName": prop, "operator": "CONTAINS_TOKEN", "value": token}


def days_ago_ms(days, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return int((now - datetime.timedelta(days=days)).timestamp() * 1000)


OPEN = f_eq("hs_is_closed", "false")
LOST = [f_eq("hs_is_closed", "true"), f_eq("hs_is_closed_won", "false")]


# ── Findings ─────────────────────────────────────────────────────
# Each finding is a list of filter groups (ORed; filters inside a group are
# ANDed). Salesforce-synced deals are not filtered out in the query: they are
# fetched and set aside client-side so the skipped count can be reported.

FINDINGS = {
    "past-close-date": "Open deals with a close date in the past",
    "stale": "Open deals with no logged activity in {stale_days}+ days",
    "missing-amount-or-close-date": "Open deals missing amount or close date",
    "lost-no-reason": "Closed-lost deals with no loss reason",
    "likely-test": "Likely test deals",
}


def finding_groups(key, stale_days=STALE_DAYS_DEFAULT, now=None):
    today = days_ago_ms(0, now)
    cutoff = days_ago_ms(stale_days, now)
    if key == "past-close-date":
        return [[OPEN, f_lt("closedate", today)]]
    if key == "stale":
        # A deal never touched is stale only once it is older than the cutoff;
        # otherwise every deal created this week would be flagged.
        return [[OPEN, f_lt("notes_last_updated", cutoff)],
                [OPEN, f_missing("notes_last_updated"), f_lt("createdate", cutoff)]]
    if key == "missing-amount-or-close-date":
        return [[OPEN, f_missing("amount")], [OPEN, f_missing("closedate")]]
    if key == "lost-no-reason":
        return [LOST + [f_missing("closed_lost_reason")]]
    if key == "likely-test":
        return ([[f_token("dealname", t)] for t in TEST_NAME_TOKENS]
                + [[f_eq("amount", "0"), f_eq("num_associated_contacts", "0")]])
    raise KeyError(key)


def label(key, stale_days=STALE_DAYS_DEFAULT):
    return FINDINGS[key].format(stale_days=stale_days)


def test_reason(props):
    """Why a deal matched likely-test, for the reviewer's CSV column."""
    name = (props.get("dealname") or "").lower()
    hits = [t for t in TEST_NAME_TOKENS if t in name.replace("-", " ").replace("_", " ").split()]
    if hits:
        return "name contains " + "/".join(hits)
    return "amount 0 and no associated contacts"


def search_all(groups, pipeline=None):
    """Page through every deal matching the filter groups. Returns
    (deals, truncated): truncated is True when the Search API cap was hit."""
    if pipeline:
        groups = [g + [f_eq("pipeline", pipeline)] for g in groups]
    body = {"filterGroups": [{"filters": g} for g in groups],
            "properties": DEAL_PROPERTIES, "limit": 100}
    deals, after = [], None
    while True:
        if after:
            body["after"] = after
        resp = api("POST", deals_path("/search"), json=body)
        if resp.status_code != 200:
            raise RuntimeError(f"Deal search failed ({resp.status_code}): {getattr(resp, 'text', '')[:300]}")
        data = resp.json()
        deals.extend(data.get("results", []))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            return deals, False
        if len(deals) >= SEARCH_RESULT_CAP:
            return deals, True
        time.sleep(QUERY_DELAY)


def is_salesforce(deal):
    return bool((deal.get("properties") or {}).get(SALESFORCE_ID))


def collect(stale_days=STALE_DAYS_DEFAULT, pipeline=None, keys=None):
    """Run every finding. Returns {key: {"deals": [...], "skipped": n,
    "truncated": bool}} where deals excludes Salesforce-synced records."""
    out = {}
    for key in keys or FINDINGS:
        found, truncated = search_all(finding_groups(key, stale_days), pipeline)
        kept = [d for d in found if not is_salesforce(d)]
        out[key] = {"deals": kept, "skipped": len(found) - len(kept), "truncated": truncated}
    return out


def row(deal, **extra):
    props = deal.get("properties") or {}
    r = {f: props.get(f) or "" for f in CSV_FIELDS}
    r["id"] = deal["id"]
    r.update(extra)
    return r


def batch_read(ids, properties=DEAL_PROPERTIES):
    """Fetch deals by ID, 100 per call. Returns {id: deal}; missing IDs are absent."""
    found = {}
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        resp = api("POST", deals_path("/batch/read"),
                   json={"inputs": [{"id": x} for x in chunk], "properties": properties})
        if resp.status_code not in (200, 207):
            raise RuntimeError(f"Deal batch read failed ({resp.status_code})")
        for d in resp.json().get("results", []):
            found[str(d["id"])] = d
        time.sleep(QUERY_DELAY)
    return found


def owners():
    """Active owners as {id: "First Last <email>"}, or None if unreadable."""
    result, params = {}, {"limit": 100}
    while True:
        resp = api("GET", f"/crm/owners/{API_VERSION}", params=params)
        if resp.status_code != 200:
            return None
        data = resp.json()
        for o in data.get("results", []):
            name = " ".join(p for p in (o.get("firstName"), o.get("lastName")) if p)
            result[str(o["id"])] = f"{name} <{o.get('email', '')}>".strip()
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            return result
        params["after"] = after


def audit_path(name):
    os.makedirs(AUDIT_DIR, exist_ok=True)
    return os.path.join(AUDIT_DIR, name)
