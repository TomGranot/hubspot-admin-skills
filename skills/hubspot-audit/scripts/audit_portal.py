# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
HubSpot Portal Audit
Read-only audit across eight dimensions: database size, deliverability,
completeness, engagement, duplicates (flagged), owner health,
list/workflow/form health, and deal pipeline health.

Writes a graded markdown report to reports/hubspot-audit-{YYYY-MM-DD}.md.
Every API call is read-only; the script mutates nothing.
"""

import datetime
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
QUERY_DELAY = 0.15  # seconds between count queries


def api(method, path, **kwargs):
    for attempt in range(MAX_RETRIES):
        resp = requests.request(method, f"{BASE}{path}", headers=HEADERS, **kwargs)
        if resp.status_code == 429:
            wait = min(10 * (attempt + 1), 30)
            print(f"    Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        return resp
    return resp


def count(object_type, filters=None):
    """Count records matching filters via the Search API (max total 10,000+)."""
    body = {"limit": 1}
    if filters:
        body["filterGroups"] = [{"filters": filters}]
    resp = api("POST", f"/crm/v3/objects/{object_type}/search", json=body)
    time.sleep(QUERY_DELAY)
    if resp.status_code != 200:
        return None
    return resp.json().get("total", 0)


def f_missing(prop):
    return {"propertyName": prop, "operator": "NOT_HAS_PROPERTY"}


def f_has(prop):
    return {"propertyName": prop, "operator": "HAS_PROPERTY"}


def f_eq(prop, value):
    return {"propertyName": prop, "operator": "EQ", "value": value}


def f_gte(prop, value):
    return {"propertyName": prop, "operator": "GTE", "value": str(value)}


def f_lt(prop, value):
    return {"propertyName": prop, "operator": "LT", "value": str(value)}


def days_ago_ms(days):
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return int(dt.timestamp() * 1000)


def pct(part, whole):
    if not whole or part is None:
        return None
    return 100.0 * part / whole


def grade(p):
    """Letter grade from % of records affected (A < 5% ... F > 50%)."""
    if p is None:
        return "?"
    if p < 5:
        return "A"
    if p < 15:
        return "B"
    if p < 30:
        return "C"
    if p < 50:
        return "D"
    return "F"


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else ("n/a" if n is None else str(n))


print("=" * 60)
print("HUBSPOT PORTAL AUDIT (read-only)")
print("=" * 60)

R = {}  # results

# ── 1. Database size ─────────────────────────────────────────────
print("\n[1/8] Database size...")
R["total_contacts"] = count("contacts")
R["total_companies"] = count("companies")
R["total_deals"] = count("deals")
R["marketing_contacts"] = count("contacts", [f_eq("hs_marketable_status", "true")])
TC, TCO, TD = R["total_contacts"] or 0, R["total_companies"] or 0, R["total_deals"] or 0
print(f"    Contacts: {fmt(TC)}  Companies: {fmt(TCO)}  Deals: {fmt(TD)}")

# ── 2. Email deliverability ──────────────────────────────────────
print("[2/8] Email deliverability...")
R["hard_bounced"] = count("contacts", [f_has("hs_email_hard_bounce_reason_enum")])
R["optout"] = count("contacts", [f_eq("hs_email_optout", "true")])
R["never_emailed"] = count("contacts", [f_missing("hs_email_last_send_date")])
R["bounce_3plus"] = count("contacts", [f_gte("hs_email_bounce", 3)])

# ── 3. Data completeness ─────────────────────────────────────────
print("[3/8] Data completeness...")
for prop in ["email", "company", "industry", "country", "lifecyclestage",
             "hubspot_owner_id", "jobtitle"]:
    R[f"contacts_missing_{prop}"] = count("contacts", [f_missing(prop)])
for prop in ["domain", "industry", "country"]:
    R[f"companies_missing_{prop}"] = count("companies", [f_missing(prop)])

# ── 4. Engagement health ─────────────────────────────────────────
print("[4/8] Engagement health...")
R["opened_90d"] = count("contacts", [f_gte("hs_email_last_open_date", days_ago_ms(90))])
R["never_opened"] = count("contacts", [f_missing("hs_email_last_open_date")])
R["no_activity_365d"] = count("contacts", [
    f_lt("hs_email_last_open_date", days_ago_ms(365))])
R["current_customers"] = count("contacts", [f_eq("hs_current_customer", "true")])
# Lifecycle sanity: contacts HubSpot marks as current customers whose
# lifecycle stage disagrees (uses the hs_current_customer system property).
R["customers_wrong_stage"] = count("contacts", [
    f_eq("hs_current_customer", "true"),
    {"propertyName": "lifecyclestage", "operator": "NEQ", "value": "customer"},
])

# ── 5. Duplicates (flag only) ────────────────────────────────────
print("[5/8] Duplicates: flagged for manual review (exact-duplicate scans")
print("      require full pagination; run /merge-duplicate-companies before.py)")

# ── 6. Owner health ──────────────────────────────────────────────
print("[6/8] Owner health...")
resp = api("GET", "/crm/v3/owners", params={"limit": 100, "archived": "true"})
archived_owners = resp.json().get("results", []) if resp.status_code == 200 else []
R["deactivated_owner_contacts"] = 0
R["deactivated_owners_with_contacts"] = 0
for o in archived_owners[:50]:
    c = count("contacts", [f_eq("hubspot_owner_id", str(o["id"]))])
    if c:
        R["deactivated_owner_contacts"] += c
        R["deactivated_owners_with_contacts"] += 1

# ── 7. List / workflow / form health ─────────────────────────────
print("[7/8] Lists, workflows, forms...")
resp = api("POST", "/crm/v3/lists/search", json={"count": 1})
R["total_lists"] = resp.json().get("total") if resp.status_code == 200 else None

resp = api("GET", "/automation/v4/flows", params={"limit": 100})
if resp.status_code == 200:
    flows = resp.json().get("results", [])
    after = resp.json().get("paging", {}).get("next", {}).get("after")
    while after:
        r2 = api("GET", "/automation/v4/flows", params={"limit": 100, "after": after})
        if r2.status_code != 200:
            break
        flows.extend(r2.json().get("results", []))
        after = r2.json().get("paging", {}).get("next", {}).get("after")
    R["total_workflows"] = len(flows)
    R["active_workflows"] = sum(1 for f in flows if f.get("isEnabled"))
else:
    R["total_workflows"] = R["active_workflows"] = None

resp = api("GET", "/marketing/v3/forms", params={"limit": 100})
R["total_forms"] = len(resp.json().get("results", [])) if resp.status_code == 200 else None

# ── 8. Deal pipeline health ──────────────────────────────────────
print("[8/8] Deal pipeline health...")
R["deals_missing_amount"] = count("deals", [f_missing("amount")])
R["deals_missing_closedate"] = count("deals", [f_missing("closedate")])

# ── Grades ───────────────────────────────────────────────────────
grades = {
    "Email Deliverability": grade(pct((R["hard_bounced"] or 0) + (R["optout"] or 0), TC)),
    "Data Completeness": grade(pct(R["contacts_missing_lifecyclestage"], TC)),
    "Engagement Health": grade(pct(R["never_opened"], TC)),
    "Owner Health": grade(pct(R["contacts_missing_hubspot_owner_id"], TC)),
    "Deal Pipeline Health": grade(pct(R["deals_missing_amount"], TD)),
}

# ── Report ───────────────────────────────────────────────────────
today = datetime.date.today().isoformat()
os.makedirs("reports", exist_ok=True)
path = f"reports/hubspot-audit-{today}.md"


def row(metric, value, total=None):
    p = pct(value, total)
    ptxt = f" | {p:.1f}%" if p is not None else " | —"
    return f"| {metric} | {fmt(value)}{ptxt} |\n"


with open(path, "w") as f:
    f.write(f"# HubSpot CRM Audit Report\n\n**Date:** {today}\n\n")
    f.write("## Executive Summary\n\n| Dimension | Grade |\n|---|---|\n")
    for dim, g in grades.items():
        f.write(f"| {dim} | {g} |\n")
    f.write("\n## 1. Database Size\n\n| Metric | Count | % |\n|---|---|---|\n")
    f.write(row("Total Contacts", TC))
    f.write(row("Total Companies", TCO))
    f.write(row("Total Deals", TD))
    f.write(row("Marketing Contacts", R["marketing_contacts"], TC))
    f.write("\n## 2. Email Deliverability\n\n| Metric | Count | % of contacts |\n|---|---|---|\n")
    f.write(row("Hard Bounced", R["hard_bounced"], TC))
    f.write(row("Globally Unsubscribed", R["optout"], TC))
    f.write(row("Never Emailed", R["never_emailed"], TC))
    f.write(row("3+ Bounces", R["bounce_3plus"], TC))
    f.write("\n## 3. Data Completeness\n\n| Metric | Count | % |\n|---|---|---|\n")
    for prop in ["email", "company", "industry", "country", "lifecyclestage",
                 "hubspot_owner_id", "jobtitle"]:
        f.write(row(f"Contacts missing {prop}", R[f"contacts_missing_{prop}"], TC))
    for prop in ["domain", "industry", "country"]:
        f.write(row(f"Companies missing {prop}", R[f"companies_missing_{prop}"], TCO))
    f.write("\n## 4. Engagement Health\n\n| Metric | Count | % |\n|---|---|---|\n")
    f.write(row("Opened an email in last 90 days", R["opened_90d"], TC))
    f.write(row("Never opened any email", R["never_opened"], TC))
    f.write(row("Last open older than 365 days", R["no_activity_365d"], TC))
    f.write(row("Current customers (hs_current_customer)", R["current_customers"], TC))
    f.write(row("Current customers NOT at Customer stage", R["customers_wrong_stage"], TC))
    f.write("\nPer-email open/click rates come from the marketing email "
            "statistics API (Marketing Hub) or the UI email health dashboard — "
            "not from contact properties.\n")
    f.write("\n## 5. Duplicates\n\nExact-duplicate scans require full pagination; "
            "run `/merge-duplicate-companies` (before.py) for company duplicates "
            "and review contact duplicates in the UI (Contacts > Actions > "
            "Manage duplicates).\n")
    f.write("\n## 6. Owner Health\n\n| Metric | Count | % |\n|---|---|---|\n")
    f.write(row("Deactivated owners still owning contacts",
                R["deactivated_owners_with_contacts"]))
    f.write(row("Contacts owned by deactivated owners",
                R["deactivated_owner_contacts"], TC))
    f.write(row("Contacts with no owner", R["contacts_missing_hubspot_owner_id"], TC))
    f.write("\n## 7. List, Workflow & Form Health\n\n| Metric | Count | % |\n|---|---|---|\n")
    f.write(row("Total lists", R["total_lists"]))
    f.write(row("Total workflows", R["total_workflows"]))
    f.write(row("Active workflows", R["active_workflows"], R["total_workflows"]))
    f.write(row("Forms (first page, up to 100)", R["total_forms"]))
    f.write("\n## 8. Deal Pipeline Health\n\n| Metric | Count | % of deals |\n|---|---|---|\n")
    f.write(row("Deals missing amount", R["deals_missing_amount"], TD))
    f.write(row("Deals missing close date", R["deals_missing_closedate"], TD))
    f.write("\n---\n\nGenerated by `skills/hubspot-audit/scripts/audit_portal.py` "
            "(read-only). Interpret with the grading rubric and skill "
            "prescription in the hubspot-audit skill.\n")

print()
print("=" * 60)
print("AUDIT COMPLETE")
print("=" * 60)
for dim, g in grades.items():
    print(f"  {dim}: {g}")
print(f"\n  Report saved: {path}")
print("  Next: map findings to skills (see SKILL.md Skill Prescription),")
print("  or run /hubspot-implementation-plan for a phased roadmap.")
