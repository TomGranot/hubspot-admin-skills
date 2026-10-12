# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
HubSpot Portal Audit
One read-only audit engine, three lenses:

  --scope marketing   shared foundation + marketing dimensions
  --scope sales       shared foundation + sales dimensions
  --scope full        everything (default)

Every dimension is tagged shared, marketing, or sales. The shared dimensions
(database size, owner health, company data, duplicates) run under every scope,
so the marketing and sales audits agree on the numbers they have in common.

Writes a graded markdown report and a JSON twin to reports/:
  full       reports/hubspot-audit-{YYYY-MM-DD}.md
  marketing  reports/hubspot-marketing-audit-{YYYY-MM-DD}.md
  sales      reports/hubspot-sales-audit-{YYYY-MM-DD}.md

Every API call is read-only; the script mutates nothing.
"""

import argparse
import datetime
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

# --- Configuration ---
BASE = "https://api.hubapi.com"
MAX_RETRIES = 5
QUERY_DELAY = 0.25         # seconds between count queries (Search API allows 5/s)
STALE_DEAL_DAYS = 60       # open deal with no logged activity for this long
WIN_RATE_WINDOW_DAYS = 90  # closed deals considered for win rate
MAX_STAGES_PER_PIPELINE = 10  # more than this is flagged as over-engineered
MAX_OWNERS_CHECKED = 50    # deactivated owners checked for orphaned records

SCOPES = {
    "full": ("shared", "marketing", "sales"),
    "marketing": ("shared", "marketing"),
    "sales": ("shared", "sales"),
}
REPORT_NAMES = {
    "full": "hubspot-audit",
    "marketing": "hubspot-marketing-audit",
    "sales": "hubspot-sales-audit",
}
REPORT_TITLES = {
    "full": "HubSpot CRM Audit Report",
    "marketing": "HubSpot Marketing Audit Report",
    "sales": "HubSpot Sales Audit Report",
}

HEADERS = {}


# ── HTTP ─────────────────────────────────────────────────────────

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


def count(object_type, *filter_groups):
    """Count records via the Search API. Filters inside a group are ANDed,
    groups are ORed. Returns None when the object is unreadable (missing
    scope, hub not purchased) so the report shows n/a instead of a false 0."""
    body = {"limit": 1}
    groups = [g for g in filter_groups if g]
    if groups:
        body["filterGroups"] = [{"filters": g} for g in groups]
    resp = api("POST", f"/crm/v3/objects/{object_type}/search", json=body)
    time.sleep(QUERY_DELAY)
    if resp.status_code != 200:
        return None
    return resp.json().get("total", 0)


def get_all(path, params=None):
    """Follow `after` paging on a list endpoint. Returns None if unreadable."""
    params = dict(params or {})
    results = []
    while True:
        resp = api("GET", path, params=params)
        if resp.status_code != 200:
            return None if not results else results
        data = resp.json()
        results.extend(data.get("results", []))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            return results
        params["after"] = after


# ── Filters ──────────────────────────────────────────────────────

def f_missing(prop):
    return {"propertyName": prop, "operator": "NOT_HAS_PROPERTY"}


def f_has(prop):
    return {"propertyName": prop, "operator": "HAS_PROPERTY"}


def f_eq(prop, value):
    return {"propertyName": prop, "operator": "EQ", "value": value}


def f_neq(prop, value):
    return {"propertyName": prop, "operator": "NEQ", "value": value}


def f_gte(prop, value):
    return {"propertyName": prop, "operator": "GTE", "value": str(value)}


def f_lt(prop, value):
    return {"propertyName": prop, "operator": "LT", "value": str(value)}


def days_ago_ms(days):
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return int(dt.timestamp() * 1000)


OPEN_DEAL = f_eq("hs_is_closed", "false")


# ── Scoring ──────────────────────────────────────────────────────

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


class Dimension:
    """One graded section of the report."""

    def __init__(self, key, title, tag):
        self.key, self.title, self.tag = key, title, tag
        self.rows = []       # {metric, value, total, pct, skill}
        self.notes = []
        self.grade_pct = None
        self.graded = False

    def add(self, metric, value, total=None, skill=None, priority=None):
        """Record a metric. `skill` names the skill that fixes a non-zero value."""
        self.rows.append({
            "metric": metric, "value": value, "total": total,
            "pct": pct(value, total), "skill": skill, "priority": priority,
        })
        return value

    def grade_on(self, *parts, total):
        """Grade the dimension on the summed share of `total` that is affected."""
        self.graded = True
        known = [p for p in parts if p is not None]
        self.grade_pct = pct(sum(known), total) if known else None

    @property
    def grade(self):
        return grade(self.grade_pct) if self.graded else "—"

    def as_dict(self):
        return {"key": self.key, "title": self.title, "tag": self.tag,
                "grade": self.grade, "grade_pct": self.grade_pct,
                "rows": self.rows, "notes": self.notes}


# ── Shared dimensions (run under every scope) ────────────────────

def dim_database_size(ctx):
    d = Dimension("database_size", "Database Size", "shared")
    ctx["contacts"] = d.add("Total contacts", count("contacts")) or 0
    ctx["companies"] = d.add("Total companies", count("companies")) or 0
    ctx["deals"] = d.add("Total deals", count("deals")) or 0
    return d


def dim_owner_health(ctx):
    d = Dimension("owner_health", "Owner Health", "shared")
    TC = ctx["contacts"]
    unowned = d.add("Contacts with no owner", count("contacts", [f_missing("hubspot_owner_id")]),
                    TC, "assign-unowned-contacts", 1)
    d.add("Companies with no owner", count("companies", [f_missing("hubspot_owner_id")]),
          ctx["companies"], "cleanup-lead-owners", 2)

    archived = get_all("/crm/v3/owners", {"limit": 100, "archived": "true"}) or []
    ctx["archived_owners"] = archived[:MAX_OWNERS_CHECKED]
    orphaned, holders = 0, 0
    for o in ctx["archived_owners"]:
        c = count("contacts", [f_eq("hubspot_owner_id", str(o["id"]))])
        if c:
            orphaned += c
            holders += 1
    d.add("Deactivated owners still owning contacts", holders)
    d.add("Contacts owned by deactivated owners", orphaned, TC,
          "reassign-deactivated-owners", 1)
    if len(archived) > MAX_OWNERS_CHECKED:
        d.notes.append(f"Checked the first {MAX_OWNERS_CHECKED} of {len(archived)} "
                       "deactivated owners.")
    d.grade_on(unowned, orphaned, total=TC)
    return d


def dim_company_data(ctx):
    d = Dimension("company_data", "Company Data Completeness", "shared")
    TCO = ctx["companies"]
    no_domain = d.add("Companies missing domain", count("companies", [f_missing("domain")]), TCO)
    d.add("Companies missing industry", count("companies", [f_missing("industry")]), TCO,
          "waterfall-enrich-contacts", 2)
    d.add("Companies missing country", count("companies", [f_missing("country")]), TCO,
          "backfill-geo-data", 2)
    d.grade_on(no_domain, total=TCO)
    return d


def dim_duplicates(ctx):
    d = Dimension("duplicates", "Duplicates", "shared")
    d.notes.append(
        "Exact-duplicate scans require full pagination, so they are flagged rather "
        "than counted here. Run `/merge-duplicate-companies` (before.py) for company "
        "duplicates and review contact duplicates in the UI (Contacts > Actions > "
        "Manage duplicates).")
    return d


# ── Marketing dimensions ─────────────────────────────────────────

def dim_deliverability(ctx):
    d = Dimension("deliverability", "Email Deliverability", "marketing")
    TC = ctx["contacts"]
    d.add("Marketing contacts", count("contacts", [f_eq("hs_marketable_status", "true")]), TC)
    hard = d.add("Hard bounced", count("contacts", [f_has("hs_email_hard_bounce_reason_enum")]),
                 TC, "suppress-hard-bounced", 0)
    optout = d.add("Globally unsubscribed", count("contacts", [f_eq("hs_email_optout", "true")]),
                   TC, "suppress-global-unsubscribes", 0)
    d.add("3+ bounces", count("contacts", [f_gte("hs_email_bounce", 3)]),
          TC, "review-bounced-contacts", 2)
    d.add("Never emailed", count("contacts", [f_missing("hs_email_last_send_date")]), TC)
    d.grade_on(hard, optout, total=TC)
    return d


CONTACT_COMPLETENESS = [
    # property, skill, priority
    ("email", "delete-no-email-contacts", 0),
    ("lifecyclestage", "fix-lifecycle-stages", 1),
    ("company", "enrich-company-name", 1),
    ("industry", "enrich-industry", 1),
    ("country", "backfill-geo-data", 2),
    ("jobtitle", "waterfall-enrich-contacts", 2),
]


def dim_contact_data(ctx):
    d = Dimension("contact_data", "Contact Data Completeness", "marketing")
    TC = ctx["contacts"]
    missing = {}
    for prop, skill, prio in CONTACT_COMPLETENESS:
        missing[prop] = d.add(f"Contacts missing {prop}", count("contacts", [f_missing(prop)]),
                              TC, skill, prio)
    d.grade_on(missing["lifecyclestage"], total=TC)
    return d


def dim_engagement(ctx):
    d = Dimension("engagement", "Engagement Health", "marketing")
    TC = ctx["contacts"]
    d.add("Opened an email in last 90 days",
          count("contacts", [f_gte("hs_email_last_open_date", days_ago_ms(90))]), TC)
    never = d.add("Never opened any email",
                  count("contacts", [f_missing("hs_email_last_open_date")]),
                  TC, "suppress-ghost-contacts", 1)
    d.add("Last open older than 365 days",
          count("contacts", [f_lt("hs_email_last_open_date", days_ago_ms(365))]),
          TC, "engagement-suppression-workflow", 2)
    d.add("Current customers (hs_current_customer)",
          count("contacts", [f_eq("hs_current_customer", "true")]), TC)
    # Lifecycle sanity: contacts HubSpot marks as current customers whose
    # lifecycle stage disagrees (uses the hs_current_customer system property).
    d.add("Current customers NOT at Customer stage",
          count("contacts", [f_eq("hs_current_customer", "true"),
                             f_neq("lifecyclestage", "customer")]),
          TC, "fix-lifecycle-stages", 1)
    d.notes.append(
        "Per-email open/click rates come from the marketing email statistics API "
        "(Marketing Hub) or the UI email health dashboard, not from contact properties.")
    d.grade_on(never, total=TC)
    return d


def dim_marketing_assets(ctx):
    d = Dimension("marketing_assets", "List, Workflow & Form Health", "marketing")
    resp = api("POST", "/crm/v3/lists/search", json={"count": 1})
    d.add("Total lists", resp.json().get("total") if resp.status_code == 200 else None,
          skill="cleanup-lists", priority=3)

    flows = get_all("/automation/v4/flows", {"limit": 100})
    total = len(flows) if flows is not None else None
    active = sum(1 for f in flows if f.get("isEnabled")) if flows is not None else None
    d.add("Total workflows", total)
    d.add("Active workflows", active, total)
    d.add("Inactive workflows", None if total is None else total - active, total,
          "cleanup-workflows", 3)

    forms = get_all("/marketing/v3/forms", {"limit": 100})
    d.add("Total forms", len(forms) if forms is not None else None,
          skill="cleanup-forms", priority=3)
    return d


# ── Sales dimensions ─────────────────────────────────────────────

def dim_pipeline_config(ctx):
    d = Dimension("pipeline_config", "Pipeline Configuration", "sales")
    pipelines = get_all("/crm/v3/pipelines/deals")
    if pipelines is None:
        d.add("Deal pipelines", None)
        d.notes.append("Pipelines unreadable: the token needs crm.schemas.deals.read "
                       "(or crm.objects.deals.read).")
        return d
    ctx["pipelines"] = pipelines
    d.add("Deal pipelines", len(pipelines))
    empty, bloated = 0, 0
    for p in pipelines:
        stages = p.get("stages", [])
        open_stages = [s for s in stages
                       if str(s.get("metadata", {}).get("isClosed", "false")).lower() != "true"]
        deals = count("deals", [f_eq("pipeline", p["id"])])
        open_deals = count("deals", [f_eq("pipeline", p["id"]), OPEN_DEAL])
        d.add(f"Pipeline \"{p.get('label', p['id'])}\": deals (open)",
              f"{fmt(deals)} ({fmt(open_deals)})")
        if deals == 0:
            empty += 1
        if len(open_stages) > MAX_STAGES_PER_PIPELINE:
            bloated += 1
    d.add("Pipelines with zero deals", empty, len(pipelines), "cleanup-deals", 3)
    d.add(f"Pipelines with more than {MAX_STAGES_PER_PIPELINE} open stages", bloated,
          len(pipelines), "cleanup-deals", 3)
    d.grade_on(empty, bloated, total=len(pipelines))
    return d


def dim_deal_data(ctx):
    d = Dimension("deal_data", "Deal Data Quality", "sales")
    ctx["open_deals"] = d.add("Open deals", count("deals", [OPEN_DEAL]), ctx["deals"]) or 0
    OD = ctx["open_deals"]
    no_amount = d.add("Open deals missing amount",
                      count("deals", [OPEN_DEAL, f_missing("amount")]), OD, "cleanup-deals", 1)
    no_close = d.add("Open deals missing close date",
                     count("deals", [OPEN_DEAL, f_missing("closedate")]), OD, "cleanup-deals", 1)
    d.add("Open deals with no owner",
          count("deals", [OPEN_DEAL, f_missing("hubspot_owner_id")]), OD,
          "cleanup-lead-owners", 1)
    d.add("Open deals with no associated contact",
          count("deals", [OPEN_DEAL, f_missing("num_associated_contacts")],
                [OPEN_DEAL, f_eq("num_associated_contacts", "0")]), OD, "cleanup-deals", 2)
    d.add("Closed-lost deals with no loss reason",
          count("deals", [f_eq("hs_is_closed", "true"), f_eq("hs_is_closed_won", "false"),
                          f_missing("closed_lost_reason")]),
          count("deals", [f_eq("hs_is_closed", "true"), f_eq("hs_is_closed_won", "false")]),
          "cleanup-deals", 2)
    d.grade_on(no_amount, no_close, total=OD * 2)
    return d


def dim_deal_velocity(ctx):
    d = Dimension("deal_velocity", "Pipeline Hygiene & Velocity", "sales")
    OD = ctx.get("open_deals", 0)
    stale_cut = days_ago_ms(STALE_DEAL_DAYS)
    stale = d.add(f"Open deals with no activity in {STALE_DEAL_DAYS}+ days",
                  count("deals", [OPEN_DEAL, f_lt("notes_last_updated", stale_cut)],
                        [OPEN_DEAL, f_missing("notes_last_updated")]), OD, "cleanup-deals", 1)
    overdue = d.add("Open deals with a close date in the past",
                    count("deals", [OPEN_DEAL, f_lt("closedate", days_ago_ms(0))]),
                    OD, "cleanup-deals", 1)
    d.add("Open deals with no next activity scheduled",
          count("deals", [OPEN_DEAL, f_missing("notes_next_activity_date")]), OD)

    window = days_ago_ms(WIN_RATE_WINDOW_DAYS)
    won = count("deals", [f_eq("hs_is_closed_won", "true"), f_gte("closedate", window)])
    closed = count("deals", [f_eq("hs_is_closed", "true"), f_gte("closedate", window)])
    d.add(f"Deals closed in last {WIN_RATE_WINDOW_DAYS} days", closed)
    d.add(f"Win rate, last {WIN_RATE_WINDOW_DAYS} days", won, closed)
    d.notes.append("Win rate is reported for context and does not affect the grade. "
                   "Forecast accuracy and time-in-stage live in the UI (Forecast tool, "
                   "Deal pipeline waterfall and time-in-stage reports).")
    d.grade_on(stale, overdue, total=OD * 2)
    return d


def dim_sales_ownership(ctx):
    d = Dimension("sales_ownership", "Sales Ownership & Handoff", "sales")
    OD = ctx.get("open_deals", 0)
    orphaned = 0
    for o in ctx.get("archived_owners", []):
        orphaned += count("deals", [OPEN_DEAL, f_eq("hubspot_owner_id", str(o["id"]))]) or 0
    d.add("Open deals owned by deactivated owners", orphaned, OD,
          "reassign-deactivated-owners", 0)

    sales_stages = ("salesqualifiedlead", "opportunity")
    in_sales = sum(count("contacts", [f_eq("lifecyclestage", s)]) or 0 for s in sales_stages)
    unowned = sum(count("contacts", [f_eq("lifecyclestage", s), f_missing("hubspot_owner_id")]) or 0
                  for s in sales_stages)
    d.add("SQL / Opportunity contacts", in_sales, ctx["contacts"])
    d.add("SQL / Opportunity contacts with no owner", unowned, in_sales,
          "assign-unowned-contacts", 0)
    d.add("Opportunity-stage contacts with no deal",
          count("contacts", [f_eq("lifecyclestage", "opportunity"), f_missing("num_associated_deals")],
                [f_eq("lifecyclestage", "opportunity"), f_eq("num_associated_deals", "0")]),
          count("contacts", [f_eq("lifecyclestage", "opportunity")]),
          "fix-lifecycle-stages", 1)
    d.grade_on(orphaned, unowned, total=OD + in_sales)
    return d


def dim_sales_activity(ctx):
    d = Dimension("sales_activity", "Activity & Follow-up", "sales")
    open_tasks = count("tasks", [f_neq("hs_task_status", "COMPLETED")])
    d.add("Open tasks", open_tasks)
    overdue = d.add("Overdue open tasks",
                    count("tasks", [f_neq("hs_task_status", "COMPLETED"),
                                    f_lt("hs_timestamp", days_ago_ms(0))]), open_tasks)
    leads = d.add("Leads (prospecting workspace object)", count("leads"))
    d.add("Leads with no owner", count("leads", [f_missing("hubspot_owner_id")]), leads,
          "cleanup-lead-owners", 2)
    if open_tasks is None or leads is None:
        d.notes.append("n/a rows mean the token lacks that object's read scope or the "
                       "portal does not use it (the leads object needs Sales Hub).")
    d.grade_on(overdue, total=open_tasks)
    return d


DIMENSIONS = [
    dim_database_size, dim_owner_health, dim_company_data, dim_duplicates,   # shared
    dim_deliverability, dim_contact_data, dim_engagement, dim_marketing_assets,  # marketing
    dim_pipeline_config, dim_deal_data, dim_deal_velocity,                   # sales
    dim_sales_ownership, dim_sales_activity,
]
TAGS = {
    dim_database_size: "shared", dim_owner_health: "shared",
    dim_company_data: "shared", dim_duplicates: "shared",
    dim_deliverability: "marketing", dim_contact_data: "marketing",
    dim_engagement: "marketing", dim_marketing_assets: "marketing",
    dim_pipeline_config: "sales", dim_deal_data: "sales", dim_deal_velocity: "sales",
    dim_sales_ownership: "sales", dim_sales_activity: "sales",
}


# ── Report ───────────────────────────────────────────────────────

def prescription(dims):
    """Skills to run, in priority order, from every non-zero finding that maps
    to one. A skill appears once, with its highest-priority finding."""
    best = {}
    for d in dims:
        for r in d.rows:
            if r["skill"] and isinstance(r["value"], int) and r["value"] > 0:
                cur = best.get(r["skill"])
                if cur is None or r["priority"] < cur["priority"]:
                    best[r["skill"]] = {**r, "dimension": d.title}
    return sorted(best.values(), key=lambda r: (r["priority"], -r["value"]))


def render(scope, dims, today):
    out = [f"# {REPORT_TITLES[scope]}\n", f"**Date:** {today}  ", f"**Scope:** {scope}\n",
           "## Executive Summary\n", "| Dimension | Lens | Grade |", "|---|---|---|"]
    for d in dims:
        out.append(f"| {d.title} | {d.tag} | {d.grade} |")

    rx = prescription(dims)
    out.append("\n## Prescription\n")
    if rx:
        out += ["Skills to run, highest priority first:\n",
                "| # | Skill | Why | Records | Priority |", "|---|---|---|---|---|"]
        for i, r in enumerate(rx, 1):
            out.append(f"| {i} | `/{r['skill']}` | {r['metric']} | {fmt(r['value'])} "
                       f"| P{r['priority']} |")
    else:
        out.append("No finding mapped to a fix skill.")

    for i, d in enumerate(dims, 1):
        out.append(f"\n## {i}. {d.title}\n")
        if d.rows:
            out += ["| Metric | Count | % |", "|---|---|---|"]
            for r in d.rows:
                p = f"{r['pct']:.1f}%" if r["pct"] is not None else "—"
                out.append(f"| {r['metric']} | {fmt(r['value'])} | {p} |")
        for n in d.notes:
            out.append(f"\n{n}")
    out.append("\n---\n\nGenerated by `skills/hubspot-audit/scripts/audit_portal.py "
               f"--scope {scope}` (read-only). Grades follow the rubric in the "
               "hubspot-audit skill.\n")
    return "\n".join(out)


def run(scope):
    tags = SCOPES[scope]
    selected = [fn for fn in DIMENSIONS if TAGS[fn] in tags]
    ctx, dims = {}, []
    for i, fn in enumerate(selected, 1):
        print(f"[{i}/{len(selected)}] {fn.__name__.removeprefix('dim_').replace('_', ' ')}...")
        dims.append(fn(ctx))
    return dims


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only HubSpot portal audit.")
    parser.add_argument("--scope", choices=sorted(SCOPES), default="full",
                        help="which lens to audit through (default: full)")
    args = parser.parse_args(argv)

    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if not token:
        sys.exit("HUBSPOT_ACCESS_TOKEN is not set. Add it to .env (see the skill's Setup).")
    HEADERS.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})

    print("=" * 60)
    print(f"HUBSPOT PORTAL AUDIT — scope: {args.scope} (read-only)")
    print("=" * 60)

    dims = run(args.scope)

    today = datetime.date.today().isoformat()
    os.makedirs("reports", exist_ok=True)
    stem = f"reports/{REPORT_NAMES[args.scope]}-{today}"
    with open(f"{stem}.md", "w") as f:
        f.write(render(args.scope, dims, today))
    with open(f"{stem}.json", "w") as f:
        json.dump({"date": today, "scope": args.scope,
                   "dimensions": [d.as_dict() for d in dims],
                   "prescription": prescription(dims)}, f, indent=2)

    print()
    print("=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)
    for d in dims:
        print(f"  {d.title}: {d.grade}")
    print(f"\n  Report saved: {stem}.md")
    print(f"  Data saved:   {stem}.json")
    print("  Next: run /hubspot-implementation-plan for a phased roadmap.")


if __name__ == "__main__":
    main()
