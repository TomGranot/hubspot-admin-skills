"""
Shared checks: the CRM foundation every lens runs. Database size and growth,
owner health, company completeness, duplicates (counted, from a record scan),
and value validity.
"""

import re
import statistics

from ..context import OBJECT_SOURCES, EMAIL_RE, FREEMAIL
from ..findings import Finding, Coverage, check, severity_from_share
from ..search import f_missing, f_eq, f_gte, days_ago_ms

MAX_OWNERS_CHECKED = 50

CONTACT_SCAN_PROPS = ["email", "firstname", "lastname", "company", "phone", "mobilephone",
                      "hs_object_source", "hs_analytics_source", "createdate",
                      "associatedcompanyid", "lifecyclestage"]
COMPANY_SCAN_PROPS = ["name", "domain", "country", "createdate", "num_associated_contacts",
                      "hs_object_source"]

SEC_SIZE = "Database Size & Growth"
SEC_OWNERS = "Owner Health"
SEC_COMPANY = "Company Data Completeness"
SEC_DUPES = "Duplicates"
SEC_VALID = "Value Validity"

DUPLICATE_UI = ["In HubSpot: Contacts > Actions > Manage duplicates (or Data Management > "
                "Data Quality) reviews HubSpot's own candidates and merges by your merge rules.",
                "For bulk merges by exact key, export the CSV this audit's evidence points to and "
                "merge via the CRM merge endpoint, keeping the oldest record."]


# ── Database size ───────────────────────────────────────────────

@check("db.contacts", "Total contacts", SEC_SIZE, "shared", graded=False)
def contacts_total(ctx, c):
    return Finding(c.id, c.title, c.section, c.lens, count=ctx.total("contacts"))


@check("db.companies", "Total companies", SEC_SIZE, "shared", graded=False)
def companies_total(ctx, c):
    return Finding(c.id, c.title, c.section, c.lens, count=ctx.total("companies"))


@check("db.deals", "Total deals", SEC_SIZE, "shared", graded=False)
def deals_total(ctx, c):
    return Finding(c.id, c.title, c.section, c.lens, count=ctx.total("deals"))


@check("db.contacts_created_90d", "Contacts created in the last 90 days", SEC_SIZE, "shared",
       graded=False)
def contacts_growth(ctx, c):
    n = ctx.count("contacts", [f_gte("createdate", days_ago_ms(90))])
    f = Finding(c.id, c.title, c.section, c.lens, count=n, denominator=ctx.total("contacts"))
    if n:
        f.breakdown = ctx.breakdown("contacts", [[f_gte("createdate", days_ago_ms(90))]],
                                    "hs_object_source", OBJECT_SOURCES, "record source")
    return f


# ── Owner health ────────────────────────────────────────────────

@check("owners.unowned_contacts", "Contacts with no owner", SEC_OWNERS, "shared",
       fix="assign-unowned-contacts", weight=0.5,
       impact="Unowned contacts are nobody's job: no follow-up, no routing, no accountability.",
       prevention="A new-contact workflow that assigns an owner by territory or round robin "
                  "(/new-contact-hygiene-workflow).")
def unowned_contacts(ctx, c):
    groups = [[f_missing("hubspot_owner_id")]]
    n = ctx.count("contacts", *groups)
    f = Finding(c.id, c.title, c.section, c.lens, count=n, denominator=ctx.total("contacts"))
    if n:
        f.evidence = ctx.sample("contacts", groups, ["email", "lifecyclestage", "hs_object_source",
                                                     "createdate"])
        f.breakdown = ctx.breakdown("contacts", groups, "hs_object_source", OBJECT_SOURCES,
                                    "record source")
        dom = ctx.dominant(f.breakdown, n)
        if dom:
            f.root_causes.append(f"{dom[2]:.0f}% of unowned contacts were created by "
                                 f"{dom[0]}: that source does not set an owner.")
    return f


@check("owners.unowned_companies", "Companies with no owner", SEC_OWNERS, "shared",
       fix="cleanup-lead-owners", weight=0.3)
def unowned_companies(ctx, c):
    groups = [[f_missing("hubspot_owner_id")]]
    n = ctx.count("companies", *groups)
    f = Finding(c.id, c.title, c.section, c.lens, count=n, denominator=ctx.total("companies"))
    if n:
        f.evidence = ctx.sample("companies", groups, ["name", "domain", "createdate"])
    return f


def archived_owners(ctx):
    if "archived_owners" not in ctx.cache:
        owners = ctx.client.get_all(ctx.client.path("owners"), {"limit": 100, "archived": "true"})
        ctx.cache["archived_owners"] = owners
    return ctx.cache["archived_owners"]


def active_owners(ctx):
    if "active_owners" not in ctx.cache:
        ctx.cache["active_owners"] = ctx.client.get_all(ctx.client.path("owners"), {"limit": 100})
    return ctx.cache["active_owners"]


@check("owners.deactivated_contacts", "Contacts owned by deactivated users", SEC_OWNERS, "shared",
       fix="reassign-deactivated-owners", weight=2.0,
       impact="Records owned by people who left get no follow-up and appear in nobody's view.",
       prevention="Reassign on offboarding: HubSpot prompts for it when a user is removed; "
                  "make it part of the offboarding checklist.")
def deactivated_owner_contacts(ctx, c):
    owners = archived_owners(ctx)
    if owners is None:
        return Finding(c.id, c.title, c.section, c.lens, coverage=Coverage.NO_SCOPE,
                       notes=["Owners API unreadable: the token needs crm.objects.owners.read."])
    checked = owners[:MAX_OWNERS_CHECKED]
    rows, total = [], 0
    for o in checked:
        n = ctx.count("contacts", [f_eq("hubspot_owner_id", str(o["id"]))]) or 0
        if n:
            rows.append((f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
                         or o.get("email") or str(o["id"]), n))
            total += n
    rows.sort(key=lambda r: -r[1])
    f = Finding(c.id, c.title, c.section, c.lens, count=total, denominator=ctx.total("contacts"),
                breakdown={"by": "deactivated owner", "rows": rows[:5], "covered": total})
    f.notes.append(f"{len(owners)} deactivated user{'s' if len(owners) != 1 else ''}; "
                   f"{len(rows)} still own{'s' if len(rows) == 1 else ''} contacts.")
    if len(owners) > MAX_OWNERS_CHECKED:
        f.coverage = Coverage.PARTIAL
        f.notes.append(f"Checked the first {MAX_OWNERS_CHECKED} deactivated users.")
    ctx.cache["deactivated_holders"] = [o for o in checked]
    return f


@check("owners.load_distribution", "Owner load imbalance (top owner's share of owned contacts)",
       SEC_OWNERS, "shared", fix="cleanup-lead-owners", weight=0.5,
       impact="One owner holding most of the database usually means a default assignee is "
              "catching everything a routing rule misses.")
def owner_load(ctx, c):
    owners = active_owners(ctx)
    if owners is None:
        return Finding(c.id, c.title, c.section, c.lens, coverage=Coverage.NO_SCOPE)
    owners = [o for o in owners if o.get("userId")][:MAX_OWNERS_CHECKED]
    loads = []
    for o in owners:
        n = ctx.count("contacts", [f_eq("hubspot_owner_id", str(o["id"]))]) or 0
        loads.append((f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
                      or o.get("email") or str(o["id"]), n))
    loads.sort(key=lambda r: -r[1])
    owned = sum(n for _, n in loads)
    top = loads[0][1] if loads else 0
    f = Finding(c.id, c.title, c.section, c.lens, count=top, denominator=owned,
                breakdown={"by": "owner", "rows": loads[:5], "covered": owned}, scored=True)
    holders = [n for _, n in loads if n]
    f.notes.append(f"{len(loads)} active owners checked; median load "
                   f"{int(statistics.median([n for _, n in loads])) if loads else 0:,} contacts.")
    if len(holders) < 3 or not owned:
        f.severity = 0
        f.notes.append("Fewer than three owners hold contacts, so imbalance is not scored.")
        return f
    # Score the excess over an even split, not the raw share: with 4 owners,
    # 25% each is balanced and 60% for one person is the problem.
    excess = 100.0 * top / owned - 100.0 / len(holders)
    f.severity = severity_from_share(excess, c.weight, top)
    f.threshold = f"top owner's share minus an even {100 / len(holders):.0f}% split, half weight"
    return f


# ── Company completeness ────────────────────────────────────────

DOMAIN_STEPS = ["Infer the domain from the associated contacts' email addresses (the common "
                "non-free-mail domain), then set it in bulk from a reviewed CSV.",
                "For the rest, Breeze Intelligence or an external enrichment provider can fill "
                "domain from the company name."]


def _company_missing(prop):
    def fn(ctx, c):
        groups = [[f_missing(prop)]]
        n = ctx.count("companies", *groups)
        f = Finding(c.id, c.title, c.section, c.lens, count=n, denominator=ctx.total("companies"))
        if n and prop == "domain":
            f.fix_steps = DOMAIN_STEPS
        if n:
            f.evidence = ctx.sample("companies", groups, ["name", "domain", "createdate",
                                                          "hs_object_source"])
            f.breakdown = ctx.breakdown("companies", groups, "hs_object_source", OBJECT_SOURCES,
                                        "record source")
            dom = ctx.dominant(f.breakdown, n)
            if dom:
                f.root_causes.append(f"{dom[2]:.0f}% come from {dom[0]}.")
        return f
    return fn


check("companies.missing_domain", "Companies missing domain", SEC_COMPANY, "shared",
      weight=1.0,
      impact="Domain is the key HubSpot deduplicates and auto-associates on; without it a "
             "company cannot be matched to its contacts or enriched.",
      prevention="Require domain on company creation (Settings > Objects > Companies > "
                 "Record customization) and let HubSpot create companies from contact emails."
      )(_company_missing("domain"))
check("companies.missing_industry", "Companies missing industry", SEC_COMPANY, "shared",
      fix="waterfall-enrich-contacts", weight=0.5)(_company_missing("industry"))
check("companies.missing_country", "Companies missing country", SEC_COMPANY, "shared",
      fix="backfill-geo-data", weight=0.5)(_company_missing("country"))


# ── Duplicates (record scan) ────────────────────────────────────

def norm_email(e):
    e = (e or "").strip().lower()
    if "@" not in e:
        return None
    local, _, domain = e.rpartition("@")
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def norm_phone(p):
    digits = re.sub(r"\D", "", p or "")
    if len(digits) < 7:
        return None
    return digits[-10:]  # national significant digits; good enough for exact-match grouping


def norm_domain(d):
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://", "", d).split("/")[0]
    if d.startswith("www."):
        d = d[4:]
    return d or None


def norm_name(n):
    n = (n or "").lower()
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    n = re.sub(r"\b(inc|llc|ltd|limited|gmbh|corp|corporation|co|company|sa|ag|plc|bv|srl)\b",
               " ", n)
    return re.sub(r"\s+", " ", n).strip() or None


def _dupe_groups(records, key):
    groups = {}
    for r in records:
        k = key(r.get("properties") or {})
        if k:
            groups.setdefault(k, []).append(r)
    return {k: v for k, v in groups.items() if len(v) > 1}


def _dupe_finding(ctx, c, object_type, records, info, key, props, fix=None, steps=None):
    f = Finding(c.id, c.title, c.section, c.lens, denominator=info.get("total"))
    if info.get("disabled"):
        f.coverage = Coverage.DISABLED
        f.notes.append("Record scan disabled (--no-scan). Duplicates need a scan to be counted.")
        return f
    if not records and info.get("total") is None:
        f.coverage = Coverage.NO_SCOPE
        return f
    groups = _dupe_groups(records, key)
    extra = sum(len(v) - 1 for v in groups.values())
    f.count = extra
    f.notes.append(f"{len(groups):,} duplicate groups; {extra:,} records beyond the first "
                   f"in each group. Scanned {info.get('fetched', 0):,} of {info.get('total') or 0:,}.")
    if not info.get("complete"):
        f.coverage = Coverage.PARTIAL
        f.notes.append("Scan was capped or incomplete; counts are a lower bound.")
    if groups:
        biggest = sorted(groups.values(), key=len, reverse=True)
        sample = [r for g in biggest[:3] for r in g[:3]]
        f.evidence = ctx.evidence_from_records(object_type, sample, props)
        f.breakdown = ctx.breakdown_from_records([r for g in groups.values() for r in g],
                                                 "hs_object_source", "record source")
        dom = ctx.dominant(f.breakdown, sum(len(g) for g in groups.values()))
        if dom:
            f.root_causes.append(f"{dom[2]:.0f}% of duplicated records were created by {dom[0]}: "
                                 "that source is not deduplicating on this key.")
    f.fix = fix
    f.fix_steps = steps or []
    return f


def contact_scan(ctx):
    return ctx.scan("contacts", CONTACT_SCAN_PROPS)


def company_scan(ctx):
    return ctx.scan("companies", COMPANY_SCAN_PROPS)


@check("dupes.contacts_email", "Duplicate contacts by normalized email", SEC_DUPES, "shared",
       weight=2.0, impact="Split engagement history, double sends, inflated counts, and "
                          "two reps working one person.",
       prevention="Deduplicate at the source: imports with the email column mapped as the "
                  "unique key; integrations configured to upsert on email.")
def dupes_contacts_email(ctx, c):
    recs, info = contact_scan(ctx)
    return _dupe_finding(ctx, c, "contacts", recs, info, lambda p: norm_email(p.get("email")),
                         ["email", "firstname", "lastname", "hs_object_source", "createdate"],
                         steps=DUPLICATE_UI)


@check("dupes.contacts_phone", "Duplicate contacts by phone number", SEC_DUPES, "shared",
       weight=1.0)
def dupes_contacts_phone(ctx, c):
    recs, info = contact_scan(ctx)
    return _dupe_finding(ctx, c, "contacts", recs, info,
                         lambda p: norm_phone(p.get("phone") or p.get("mobilephone")),
                         ["email", "phone", "firstname", "lastname", "createdate"],
                         steps=DUPLICATE_UI)


@check("dupes.contacts_name_company", "Duplicate contacts by name and company", SEC_DUPES,
       "shared", weight=1.0)
def dupes_contacts_name(ctx, c):
    recs, info = contact_scan(ctx)

    def key(p):
        first, last, comp = (p.get("firstname") or "").strip().lower(), \
                            (p.get("lastname") or "").strip().lower(), norm_name(p.get("company"))
        return f"{first}|{last}|{comp}" if first and last and comp else None
    return _dupe_finding(ctx, c, "contacts", recs, info, key,
                         ["email", "firstname", "lastname", "company", "createdate"],
                         steps=DUPLICATE_UI)


@check("dupes.companies_domain", "Duplicate companies by normalized domain", SEC_DUPES, "shared",
       fix="merge-duplicate-companies", weight=2.0,
       impact="Deal history and contacts split across two account records; reports count "
              "the customer twice.",
       prevention="Let HubSpot create companies from contact email domains and turn off "
                  "company creation in integrations that do not match on domain.")
def dupes_companies_domain(ctx, c):
    recs, info = company_scan(ctx)
    return _dupe_finding(ctx, c, "companies", recs, info,
                         lambda p: norm_domain(p.get("domain")),
                         ["name", "domain", "num_associated_contacts", "createdate"],
                         fix="merge-duplicate-companies")


@check("dupes.companies_name", "Duplicate companies by normalized name (same country)", SEC_DUPES,
       "shared", fix="merge-duplicate-companies", weight=1.0)
def dupes_companies_name(ctx, c):
    recs, info = company_scan(ctx)

    def key(p):
        n = norm_name(p.get("name"))
        return f"{n}|{(p.get('country') or '').lower()}" if n else None
    return _dupe_finding(ctx, c, "companies", recs, info, key,
                         ["name", "domain", "country", "createdate"],
                         fix="merge-duplicate-companies")


# ── Value validity (record scan) ────────────────────────────────

@check("valid.contact_email_syntax", "Contacts whose email is not a valid address", SEC_VALID,
       "shared", weight=2.0, fix="delete-no-email-contacts",
       impact="Invalid addresses bounce on first send and count as marketing contacts.",
       prevention="Form field validation and import-time checks; HubSpot rejects obvious "
                  "invalid formats on new records but not on imports.")
def invalid_emails(ctx, c):
    recs, info = contact_scan(ctx)
    f = Finding(c.id, c.title, c.section, c.lens, denominator=info.get("total"))
    if info.get("disabled"):
        f.coverage = Coverage.DISABLED
        return f
    if not recs and info.get("total") is None:
        f.coverage = Coverage.NO_SCOPE
        return f
    bad = [r for r in recs if (r.get("properties") or {}).get("email")
           and not EMAIL_RE.match((r["properties"]["email"] or "").strip())]
    f.count = len(bad)
    f.evidence = ctx.evidence_from_records("contacts", bad, ["email", "hs_object_source",
                                                            "createdate"])
    if bad:
        f.breakdown = ctx.breakdown_from_records(bad, "hs_object_source", "record source")
    if not info.get("complete"):
        f.coverage = Coverage.PARTIAL
    f.notes.append("Checks the written format only. Deliverability of a well-formed address "
                   "is a separate question (see Email Deliverability).")
    return f


@check("valid.contact_freemail_share", "Contacts on free-mail domains", SEC_VALID, "shared",
       graded=False)
def freemail_share(ctx, c):
    recs, info = contact_scan(ctx)
    f = Finding(c.id, c.title, c.section, c.lens, denominator=info.get("total"))
    if info.get("disabled") or (not recs and info.get("total") is None):
        f.coverage = Coverage.DISABLED if info.get("disabled") else Coverage.NO_SCOPE
        return f
    n = sum(1 for r in recs if ((r.get("properties") or {}).get("email") or "")
            .rpartition("@")[2].lower() in FREEMAIL)
    f.count = n
    f.notes.append("Context for B2B portals: free-mail contacts rarely match a company and "
                   "skew firmographic enrichment. Not graded.")
    return f


@check("assoc.contacts_without_company_matchable", "Contacts with no company whose email domain "
       "matches an existing company", SEC_VALID, "shared", weight=0.5,
       fix="enrich-company-name",
       impact="Account views and company-level reports miss these people.",
       prevention="Settings > Objects > Companies > 'Automatically create and associate "
                  "companies with contacts'.")
def unassociated_matchable(ctx, c):
    contacts, cinfo = contact_scan(ctx)
    companies, coinfo = company_scan(ctx)
    f = Finding(c.id, c.title, c.section, c.lens, denominator=cinfo.get("total"))
    if cinfo.get("disabled") or coinfo.get("disabled"):
        f.coverage = Coverage.DISABLED
        return f
    if (not contacts and cinfo.get("total") is None) or (not companies and coinfo.get("total") is None):
        f.coverage = Coverage.NO_SCOPE
        return f
    domains = {norm_domain((r.get("properties") or {}).get("domain")) for r in companies}
    domains.discard(None)
    hits = []
    for r in contacts:
        p = r.get("properties") or {}
        if p.get("associatedcompanyid"):
            continue
        dom = (p.get("email") or "").rpartition("@")[2].lower()
        if dom and dom not in FREEMAIL and dom in domains:
            hits.append(r)
    f.count = len(hits)
    f.evidence = ctx.evidence_from_records("contacts", hits, ["email", "company", "createdate"])
    if not (cinfo.get("complete") and coinfo.get("complete")):
        f.coverage = Coverage.PARTIAL
    return f
