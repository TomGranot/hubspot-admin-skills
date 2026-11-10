"""
Marketing checks: deliverability, contact completeness (graded per property,
so one healthy field cannot hide five empty ones), engagement, lifecycle
funnel, and list/workflow/form inventory.
"""

from ..context import OBJECT_SOURCES, ANALYTICS_SOURCES
from ..findings import Finding, Coverage, check
from ..search import f_missing, f_has, f_eq, f_neq, f_gte, f_lt, days_ago_ms

SEC_DELIV = "Email Deliverability"
SEC_COMPLETE = "Contact Data Completeness"
SEC_ENGAGE = "Engagement Health"
SEC_FUNNEL = "Lifecycle Funnel"
SEC_ASSETS = "List, Workflow & Form Health"

LIFECYCLE_STAGES = ["subscriber", "lead", "marketingqualifiedlead", "salesqualifiedlead",
                    "opportunity", "customer", "evangelist", "other"]

CONTACT_EVIDENCE = ["email", "lifecyclestage", "hs_object_source", "createdate"]


def _contact_count_check(groups_fn, evidence=CONTACT_EVIDENCE, breakdown_prop="hs_object_source",
                         breakdown_values=OBJECT_SOURCES, denominator="contacts", root_cause=None):
    def fn(ctx, c):
        groups = groups_fn(ctx)
        n = ctx.count("contacts", *groups)
        denom = ctx.total("contacts") if denominator == "contacts" else denominator(ctx)
        f = Finding(c.id, c.title, c.section, c.lens, count=n, denominator=denom)
        if n:
            f.evidence = ctx.sample("contacts", groups, evidence)
            if breakdown_prop:
                f.breakdown = ctx.breakdown("contacts", groups, breakdown_prop, breakdown_values,
                                            "record source" if breakdown_prop == "hs_object_source"
                                            else breakdown_prop)
                dom = ctx.dominant(f.breakdown, n)
                if dom and root_cause:
                    f.root_causes.append(root_cause.format(pct=f"{dom[2]:.0f}", key=dom[0]))
        return f
    return fn


# ── Deliverability ──────────────────────────────────────────────

@check("deliv.marketing_contacts", "Marketing contacts (billable)", SEC_DELIV, "marketing",
       graded=False)
def marketing_contacts(ctx, c):
    n = ctx.count("contacts", [f_eq("hs_marketable_status", "true")])
    ctx.cache["marketing_contacts"] = n
    f = Finding(c.id, c.title, c.section, c.lens, count=n, denominator=ctx.total("contacts"))
    f.notes.append("hs_marketable_status is readable but read-only via API; status changes "
                   "go through a workflow.")
    return f


check("deliv.hard_bounced", "Hard-bounced contacts", SEC_DELIV, "marketing",
      fix="suppress-hard-bounced", weight=3.0,
      impact="Every send to a hard-bounced address tells inbox providers the list is not "
             "maintained; these contacts also bill as marketing contacts.",
      prevention="/bounce-monitoring-workflow sets bounced contacts non-marketing automatically."
      )(_contact_count_check(lambda ctx: [[f_has("hs_email_hard_bounce_reason_enum")]],
                             evidence=["email", "hs_email_hard_bounce_reason_enum",
                                       "hs_marketable_status", "createdate"],
                             root_cause="{pct}% of hard bounces were created by {key}."))

check("deliv.global_unsubscribed", "Globally unsubscribed contacts still marketable", SEC_DELIV,
      "marketing", fix="suppress-global-unsubscribes", weight=2.0,
      impact="Paid for as marketing contacts; can never be emailed.",
      prevention="A workflow on hs_email_optout = true that sets marketing status to "
                 "non-marketing (/suppress-global-unsubscribes builds it)."
      )(_contact_count_check(lambda ctx: [[f_eq("hs_email_optout", "true"),
                                           f_eq("hs_marketable_status", "true")]],
                             evidence=["email", "hs_email_optout", "hs_marketable_status"],
                             breakdown_prop=None))

check("deliv.bounced_3plus", "Contacts with 3+ bounces", SEC_DELIV, "marketing",
      fix="review-bounced-contacts", weight=1.0
      )(_contact_count_check(lambda ctx: [[f_gte("hs_email_bounce", 3)]],
                             evidence=["email", "hs_email_bounce", "hs_email_last_send_date"],
                             breakdown_prop=None))


@check("deliv.never_emailed", "Marketing contacts never sent an email", SEC_DELIV, "marketing",
       graded=False)
def never_emailed(ctx, c):
    n = ctx.count("contacts", [f_eq("hs_marketable_status", "true"),
                               f_missing("hs_email_last_send_date")])
    return Finding(c.id, c.title, c.section, c.lens, count=n,
                   denominator=ctx.cache.get("marketing_contacts"),
                   notes=["Paying for contacts you never email. Either email them or set them "
                          "non-marketing."])


# ── Contact completeness: one graded check per property ─────────

COMPLETENESS = [
    # property, fix skill, weight, impact
    ("email", "delete-no-email-contacts", 2.0,
     "Unreachable by email, unmatched by most integrations, still billed if marketing."),
    ("lifecyclestage", "fix-lifecycle-stages", 2.0,
     "No lifecycle stage means no funnel reporting and no stage-based automation."),
    ("company", "enrich-company-name", 1.0,
     "Blocks ICP tiering and account-based reporting."),
    ("industry", "enrich-industry", 0.7, "Blocks firmographic segmentation and scoring."),
    ("country", "backfill-geo-data", 0.7, "Blocks territory routing and regional compliance."),
    ("jobtitle", "waterfall-enrich-contacts", 0.5, "Blocks persona segmentation."),
    ("hubspot_owner_id", "assign-unowned-contacts", 0.3, None),
    ("firstname", None, 0.5, "Personalization tokens fall back to defaults."),
]

for _prop, _fix, _weight, _impact in COMPLETENESS:
    check(f"complete.missing_{_prop}", f"Contacts missing {_prop}", SEC_COMPLETE, "marketing",
          fix=_fix, weight=_weight, impact=_impact,
          prevention=f"Make {_prop} required on the forms and imports that create contacts, "
                     "or fill it on creation with /new-contact-hygiene-workflow."
          )(_contact_count_check(lambda ctx, p=_prop: [[f_missing(p)]],
                                 root_cause="{pct}% of these contacts were created by {key}."))


# ── Engagement ──────────────────────────────────────────────────

@check("engage.opened_90d", "Contacts that opened an email in the last 90 days", SEC_ENGAGE,
       "marketing", graded=False)
def opened_90d(ctx, c):
    n = ctx.count("contacts", [f_gte("hs_email_last_open_date", days_ago_ms(90))])
    return Finding(c.id, c.title, c.section, c.lens, count=n,
                   denominator=ctx.cache.get("marketing_contacts") or ctx.total("contacts"))


check("engage.never_opened", "Marketing contacts that never opened any email", SEC_ENGAGE,
      "marketing", fix="suppress-ghost-contacts", weight=0.5,
      impact="Dead weight in the marketing contact tier and a drag on engagement metrics "
             "inbox providers watch.",
      prevention="/engagement-suppression-workflow sunsets contacts after a defined silence."
      )(_contact_count_check(lambda ctx: [[f_eq("hs_marketable_status", "true"),
                                           f_missing("hs_email_last_open_date"),
                                           f_has("hs_email_last_send_date")]],
                             evidence=["email", "hs_email_last_send_date", "createdate"],
                             breakdown_prop="hs_analytics_source",
                             breakdown_values=ANALYTICS_SOURCES,
                             denominator=lambda ctx: ctx.cache.get("marketing_contacts")))

check("engage.dormant_365d", "Marketing contacts whose last open is over a year old", SEC_ENGAGE,
      "marketing", fix="engagement-suppression-workflow", weight=0.7
      )(_contact_count_check(lambda ctx: [[f_eq("hs_marketable_status", "true"),
                                           f_lt("hs_email_last_open_date", days_ago_ms(365))]],
                             evidence=["email", "hs_email_last_open_date"],
                             breakdown_prop=None,
                             denominator=lambda ctx: ctx.cache.get("marketing_contacts")))

check("engage.customers_wrong_stage", "Current customers not at the Customer lifecycle stage",
      SEC_ENGAGE, "marketing", fix="fix-lifecycle-stages", weight=2.0,
      impact="Customers receive prospect nurture and are missing from customer reports.",
      prevention="/lifecycle-progression-workflow sets Customer on closed-won."
      )(_contact_count_check(lambda ctx: [[f_eq("hs_current_customer", "true"),
                                           f_neq("lifecyclestage", "customer")]],
                             evidence=["email", "lifecyclestage", "hs_current_customer"],
                             breakdown_prop="lifecyclestage",
                             breakdown_values=LIFECYCLE_STAGES,
                             denominator=lambda ctx: ctx.count("contacts",
                                                               [f_eq("hs_current_customer",
                                                                     "true")])))


# ── Lifecycle funnel ────────────────────────────────────────────

@check("funnel.distribution", "Contacts per lifecycle stage", SEC_FUNNEL, "marketing", graded=False)
def funnel_distribution(ctx, c):
    rows = []
    for s in LIFECYCLE_STAGES:
        n = ctx.count("contacts", [f_eq("lifecyclestage", s)])
        if n:
            rows.append((s, n))
    f = Finding(c.id, c.title, c.section, c.lens, count=sum(n for _, n in rows),
                denominator=ctx.total("contacts"),
                breakdown={"by": "lifecycle stage", "rows": rows, "covered": sum(n for _, n in rows)})
    f.notes.append("Stage conversion rates need the hs_date_entered_* properties and a "
                   "cohort window; planned for the next release.")
    return f


check("funnel.opportunity_no_deal", "Opportunity-stage contacts with no deal", SEC_FUNNEL,
      "marketing", fix="fix-lifecycle-stages", weight=1.5,
      impact="The stage says sales is working it; the pipeline says nothing exists.",
      prevention="Set Opportunity from deal creation (HubSpot's lifecycle sync setting), never by hand."
      )(_contact_count_check(lambda ctx: [[f_eq("lifecyclestage", "opportunity"),
                                           f_missing("num_associated_deals")],
                                          [f_eq("lifecyclestage", "opportunity"),
                                           f_eq("num_associated_deals", "0")]],
                             evidence=["email", "lifecyclestage", "hubspot_owner_id"],
                             breakdown_prop=None,
                             denominator=lambda ctx: ctx.count("contacts",
                                                               [f_eq("lifecyclestage",
                                                                     "opportunity")])))


# ── Assets ──────────────────────────────────────────────────────

@check("assets.lists", "Lists", SEC_ASSETS, "marketing", fix="cleanup-lists", graded=False)
def lists_total(ctx, c):
    resp = ctx.client.post(ctx.client.path("lists_search"), json={"count": 1}, allow=(403, 404))
    if resp.status_code != 200:
        return Finding(c.id, c.title, c.section, c.lens, coverage=Coverage.NO_SCOPE,
                       notes=["Lists API unreadable: the token needs crm.lists.read."])
    f = Finding(c.id, c.title, c.section, c.lens, count=resp.json().get("total"))
    f.notes.append("List size, last-updated, and usage in emails or workflows need per-list "
                   "reads; /cleanup-lists does that inventory.")
    return f


@check("assets.workflows_inactive", "Workflows turned off", SEC_ASSETS, "marketing",
       fix="cleanup-workflows", weight=0.3,
       impact="Off workflows are either abandoned or accidentally disabled; both need a look.")
def workflows(ctx, c):
    flows = ctx.client.get_all(ctx.client.path("flows"), {"limit": 100})
    if flows is None:
        return Finding(c.id, c.title, c.section, c.lens, coverage=Coverage.NO_SCOPE,
                       notes=["Workflows API (beta) unreadable: needs the automation scope and a "
                              "tier with workflows."])
    total = len(flows)
    inactive = [fl for fl in flows if not fl.get("isEnabled")]
    f = Finding(c.id, c.title, c.section, c.lens, count=len(inactive), denominator=total)
    f.notes.append(f"{total} workflows, {total - len(inactive)} active.")
    f.notes.append("Enrollment counts and error state are UI-only (Automation > Workflows > "
                   "Details); the API does not expose them.")
    names = [fl for fl in inactive if any(t in (fl.get('name') or '').lower()
                                          for t in ("test", "copy of", "temp", "draft"))]
    if names:
        f.root_causes.append(f"{len(names)} of the off workflows look like tests or copies "
                             "by name.")
    f.breakdown = {"by": "object type", "rows": _tally(inactive, "objectTypeId"), "covered": len(inactive)}
    return f


def _tally(items, key, top=5):
    counts = {}
    for it in items:
        counts[it.get(key) or "(unknown)"] = counts.get(it.get(key) or "(unknown)", 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])[:top]


@check("assets.forms", "Forms", SEC_ASSETS, "marketing", fix="cleanup-forms", graded=False)
def forms_total(ctx, c):
    forms = ctx.client.get_all(ctx.client.path("forms"), {"limit": 100})
    if forms is None:
        return Finding(c.id, c.title, c.section, c.lens, coverage=Coverage.NO_SCOPE,
                       notes=["Forms API unreadable: the token needs forms scope."])
    f = Finding(c.id, c.title, c.section, c.lens, count=len(forms))
    f.notes.append("Submission volume per form is in the next release; /cleanup-forms reads it "
                   "per form today.")
    return f
