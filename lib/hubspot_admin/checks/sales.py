"""
Sales checks: pipeline configuration, deal data quality, hygiene and velocity,
ownership and handoff, activity and follow-up. Deal findings carry sample
deals and a per-pipeline or per-owner breakdown.
"""

import statistics

from ..findings import Finding, Coverage, check
from ..search import f_missing, f_eq, f_neq, f_gte, f_lt, days_ago_ms

SEC_PIPE = "Pipeline Configuration"
SEC_DEAL = "Deal Data Quality"
SEC_VELO = "Pipeline Hygiene & Velocity"
SEC_OWN = "Sales Ownership & Handoff"
SEC_ACT = "Activity & Follow-up"

OPEN = f_eq("hs_is_closed", "false")
DEAL_EVIDENCE = ["dealname", "amount", "closedate", "dealstage", "pipeline", "hubspot_owner_id"]
DEAL_SCAN_PROPS = ["dealname", "amount", "closedate", "dealstage", "pipeline", "hubspot_owner_id",
                   "createdate", "notes_last_updated", "hs_is_closed"]
MAX_STAGES_PER_PIPELINE = 10
WIN_RATE_WINDOW_DAYS = 90


def stale_days(ctx):
    return int(ctx.options.get("stale_days", 60))


def pipelines(ctx):
    if "pipelines" not in ctx.cache:
        ctx.cache["pipelines"] = ctx.client.get_all(ctx.client.path("pipelines", object="deals"))
    return ctx.cache["pipelines"]


def pipeline_labels(ctx):
    return {p["id"]: p.get("label", p["id"]) for p in (pipelines(ctx) or [])}


def open_deals(ctx):
    if "open_deals" not in ctx.cache:
        ctx.cache["open_deals"] = ctx.count("deals", [OPEN])
    return ctx.cache["open_deals"]


def _deal_check(groups_fn, denominator=open_deals, breakdown_by="pipeline", evidence=DEAL_EVIDENCE,
                root_cause=None):
    def fn(ctx, c):
        groups = groups_fn(ctx)
        n = ctx.count("deals", *groups)
        f = Finding(c.id, c.title, c.section, c.lens, count=n, denominator=denominator(ctx))
        if n:
            f.evidence = ctx.sample("deals", groups, evidence)
            if breakdown_by == "pipeline":
                labels = pipeline_labels(ctx)
                bd = ctx.breakdown("deals", groups, "pipeline", list(labels), "pipeline")
                bd["rows"] = [(labels.get(k, k), v) for k, v in bd["rows"]]
                f.breakdown = bd
            elif breakdown_by == "owner":
                f.breakdown = _owner_breakdown(ctx, groups)
            dom = ctx.dominant(f.breakdown, n)
            if dom and root_cause:
                f.root_causes.append(root_cause.format(pct=f"{dom[2]:.0f}", key=dom[0]))
        return f
    return fn


def _owner_breakdown(ctx, groups, top=5):
    owners = ctx.client.get_all(ctx.client.path("owners"), {"limit": 100}) or []
    names = {str(o["id"]): (f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
                            or o.get("email") or str(o["id"])) for o in owners}
    bd = ctx.breakdown("deals", groups, "hubspot_owner_id", list(names)[: ctx.max_breakdown_queries],
                       "owner", top=top)
    bd["rows"] = [(names.get(k, k), v) for k, v in bd["rows"]]
    return bd


# ── Pipeline configuration ──────────────────────────────────────

@check("pipe.inventory", "Deal pipelines", SEC_PIPE, "sales", graded=False)
def pipeline_inventory(ctx, c):
    ps = pipelines(ctx)
    if ps is None:
        return Finding(c.id, c.title, c.section, c.lens, coverage=Coverage.NO_SCOPE,
                       notes=["Pipelines unreadable: the token needs crm.schemas.deals.read."])
    rows = []
    for p in ps:
        rows.append((p.get("label", p["id"]),
                     ctx.count("deals", [f_eq("pipeline", p["id"])]) or 0))
    ctx.cache["pipeline_deal_counts"] = dict(rows)
    return Finding(c.id, c.title, c.section, c.lens, count=len(ps),
                   breakdown={"by": "pipeline (deals)", "rows": rows, "covered": sum(n for _, n in rows)})


@check("pipe.empty", "Pipelines with zero deals", SEC_PIPE, "sales", fix="cleanup-deals", weight=1.0,
       impact="Empty pipelines confuse reps and reports; they are usually abandoned experiments.")
def empty_pipelines(ctx, c):
    ps = pipelines(ctx)
    if ps is None:
        return Finding(c.id, c.title, c.section, c.lens, coverage=Coverage.NO_SCOPE)
    counts = ctx.cache.get("pipeline_deal_counts") or {}
    empty = [p.get("label", p["id"]) for p in ps if counts.get(p.get("label", p["id"]), 0) == 0]
    f = Finding(c.id, c.title, c.section, c.lens, count=len(empty), denominator=len(ps))
    f.fix_steps = ["Settings > Objects > Deals > Pipelines: delete or archive each empty pipeline "
                   "after confirming no automation targets it."] if empty else []
    f.notes = [f"Empty: {', '.join(empty)}"] if empty else []
    return f


@check("pipe.bloated", f"Pipelines with more than {MAX_STAGES_PER_PIPELINE} open stages", SEC_PIPE,
       "sales", fix="cleanup-deals", weight=1.0,
       impact="Too many stages means reps guess which one applies, and stage data stops meaning "
              "anything.")
def bloated_pipelines(ctx, c):
    ps = pipelines(ctx)
    if ps is None:
        return Finding(c.id, c.title, c.section, c.lens, coverage=Coverage.NO_SCOPE)
    bloated = []
    for p in ps:
        open_stages = [s for s in p.get("stages", [])
                       if str(s.get("metadata", {}).get("isClosed", "false")).lower() != "true"]
        if len(open_stages) > MAX_STAGES_PER_PIPELINE:
            bloated.append(f"{p.get('label', p['id'])} ({len(open_stages)} stages)")
    f = Finding(c.id, c.title, c.section, c.lens, count=len(bloated), denominator=len(ps),
                threshold=f"more than {MAX_STAGES_PER_PIPELINE} open stages")
    f.notes = [f"Bloated: {', '.join(bloated)}"] if bloated else []
    return f


# ── Deal data quality ───────────────────────────────────────────

@check("deal.open", "Open deals", SEC_DEAL, "sales", graded=False)
def open_deal_count(ctx, c):
    return Finding(c.id, c.title, c.section, c.lens, count=open_deals(ctx),
                   denominator=ctx.total("deals"))


check("deal.missing_amount", "Open deals missing amount", SEC_DEAL, "sales", fix="cleanup-deals",
      weight=2.0, impact="Contributes zero to every weighted pipeline and forecast report.",
      prevention="Make amount required from the first stage where it should exist "
                 "(Settings > Objects > Deals > Pipelines > stage properties)."
      )(_deal_check(lambda ctx: [[OPEN, f_missing("amount")]],
                    root_cause="{pct}% sit in the {key} pipeline."))

check("deal.missing_closedate", "Open deals missing close date", SEC_DEAL, "sales",
      fix="cleanup-deals", weight=2.0, impact="Invisible to every time-boxed forecast.",
      prevention="Require close date at deal creation; HubSpot defaults it to end of month."
      )(_deal_check(lambda ctx: [[OPEN, f_missing("closedate")]]))

check("deal.no_owner", "Open deals with no owner", SEC_DEAL, "sales", fix="cleanup-lead-owners",
      weight=2.0, impact="Nobody is working it and it is in nobody's forecast."
      )(_deal_check(lambda ctx: [[OPEN, f_missing("hubspot_owner_id")]]))

check("deal.no_contact", "Open deals with no associated contact", SEC_DEAL, "sales",
      fix="cleanup-deals", weight=1.0,
      impact="No buyer on record: sequences, meetings, and attribution have nothing to attach to."
      )(_deal_check(lambda ctx: [[OPEN, f_missing("num_associated_contacts")],
                                 [OPEN, f_eq("num_associated_contacts", "0")]]))


def _lost(ctx):
    return ctx.count("deals", [f_eq("hs_is_closed", "true"), f_eq("hs_is_closed_won", "false")])


check("deal.lost_no_reason", "Closed-lost deals with no loss reason", SEC_DEAL, "sales",
      fix="cleanup-deals", weight=1.0,
      impact="The cheapest win/loss data a team can have, thrown away.",
      prevention="Make closed_lost_reason required on the Closed Lost stage."
      )(_deal_check(lambda ctx: [[f_eq("hs_is_closed", "true"), f_eq("hs_is_closed_won", "false"),
                                  f_missing("closed_lost_reason")]],
                    denominator=_lost,
                    evidence=["dealname", "amount", "closedate", "pipeline", "hubspot_owner_id"]))


@check("deal.amount_outliers", "Open deals with an amount over 10x the pipeline median", SEC_DEAL,
       "sales", fix="cleanup-deals", weight=1.0,
       impact="A single mistyped amount can double the weighted pipeline.")
def amount_outliers(ctx, c):
    recs, info = ctx.scan("deals", DEAL_SCAN_PROPS, groups=[[OPEN]])
    f = Finding(c.id, c.title, c.section, c.lens, denominator=info.get("total"))
    if info.get("disabled"):
        f.coverage = Coverage.DISABLED
        return f
    if not recs and info.get("total") is None:
        f.coverage = Coverage.NO_SCOPE
        return f
    by_pipe = {}
    for r in recs:
        p = r.get("properties") or {}
        try:
            amt = float(p.get("amount") or 0)
        except ValueError:
            continue
        if amt > 0:
            by_pipe.setdefault(p.get("pipeline"), []).append((amt, r))
    outliers = []
    for pipe, items in by_pipe.items():
        med = statistics.median(a for a, _ in items)
        outliers += [r for a, r in items if med and a > 10 * med]
    f.count = len(outliers)
    f.evidence = ctx.evidence_from_records("deals", outliers, DEAL_EVIDENCE)
    f.threshold = "amount > 10 x median open amount in the same pipeline"
    if not info.get("complete"):
        f.coverage = Coverage.PARTIAL
    return f


# ── Hygiene and velocity ────────────────────────────────────────

def _stale_groups(ctx):
    cutoff = days_ago_ms(stale_days(ctx))
    return [[OPEN, f_lt("notes_last_updated", cutoff)],
            [OPEN, f_missing("notes_last_updated"), f_lt("createdate", cutoff)]]


@check("velo.stale", "Open deals with no logged activity in N+ days", SEC_VELO, "sales",
       fix="cleanup-deals", weight=1.5,
       impact="Dead deals inflate the pipeline; or reps are not logging, which is a different "
              "problem with a different fix.",
       prevention="A workflow that creates a task for the owner when an open deal has no "
                  "activity for your stale window.")
def stale_deals(ctx, c):
    f = _deal_check(_stale_groups, breakdown_by="owner",
                    root_cause="{pct}% belong to {key}: check whether they log activity at all.")(ctx, c)
    f.title = f"Open deals with no logged activity in {stale_days(ctx)}+ days"
    f.threshold = f"--stale-days {stale_days(ctx)}"
    return f


check("velo.past_due", "Open deals with a close date in the past", SEC_VELO, "sales",
      fix="cleanup-deals", weight=2.0,
      impact="Wrong by definition: it closed, slipped, or died, and the record says none of those.",
      prevention="Pipeline rule or workflow that pushes close date forward or tasks the owner "
                 "when it passes."
      )(_deal_check(lambda ctx: [[OPEN, f_lt("closedate", days_ago_ms(0))]], breakdown_by="owner"))

check("velo.no_next_activity", "Open deals with no next activity scheduled", SEC_VELO, "sales",
      weight=0.5, fix="cleanup-deals"
      )(_deal_check(lambda ctx: [[OPEN, f_missing("notes_next_activity_date")]],
                    breakdown_by="owner"))


@check("velo.win_rate", f"Win rate, last {WIN_RATE_WINDOW_DAYS} days", SEC_VELO, "sales",
       graded=False)
def win_rate(ctx, c):
    window = days_ago_ms(WIN_RATE_WINDOW_DAYS)
    won = ctx.count("deals", [f_eq("hs_is_closed_won", "true"), f_gte("closedate", window)])
    closed = ctx.count("deals", [f_eq("hs_is_closed", "true"), f_gte("closedate", window)])
    f = Finding(c.id, c.title, c.section, c.lens, count=won, denominator=closed)
    f.notes.append(f"{closed if closed is not None else 'n/a'} deals closed in the window. "
                   "Context only; a healthy win rate on a pipeline full of stale deals usually "
                   "means losses are never closed out.")
    return f


# ── Ownership and handoff ───────────────────────────────────────

@check("own.deals_deactivated", "Open deals owned by deactivated users", SEC_OWN, "sales",
       fix="reassign-deactivated-owners", weight=3.0,
       impact="No follow-up and in nobody's forecast. Reassign before anything else.")
def orphaned_deals(ctx, c):
    owners = ctx.cache.get("archived_owners")
    if owners is None:
        owners = ctx.client.get_all(ctx.client.path("owners"), {"limit": 100, "archived": "true"})
        ctx.cache["archived_owners"] = owners
    if owners is None:
        return Finding(c.id, c.title, c.section, c.lens, coverage=Coverage.NO_SCOPE)
    rows, total, sample = [], 0, []
    for o in owners[:50]:
        groups = [[OPEN, f_eq("hubspot_owner_id", str(o["id"]))]]
        n = ctx.count("deals", *groups) or 0
        if n:
            total += n
            rows.append((f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
                         or o.get("email") or str(o["id"]), n))
            if len(sample) < ctx.sample_size:
                sample += ctx.sample("deals", groups, DEAL_EVIDENCE, n=ctx.sample_size - len(sample))
    rows.sort(key=lambda r: -r[1])
    return Finding(c.id, c.title, c.section, c.lens, count=total, denominator=open_deals(ctx),
                   evidence=sample,
                   breakdown={"by": "deactivated owner", "rows": rows[:5], "covered": total})


def _sales_stage_contacts(ctx):
    return sum(ctx.count("contacts", [f_eq("lifecyclestage", s)]) or 0
               for s in ("salesqualifiedlead", "opportunity"))


@check("own.unowned_sales_contacts", "SQL / Opportunity contacts with no owner", SEC_OWN, "sales",
       fix="assign-unowned-contacts", weight=3.0,
       impact="Marketing handed them over and nobody caught them.",
       prevention="Routing on lifecycle change to SQL (/lifecycle-progression-workflow).")
def unowned_sales_contacts(ctx, c):
    groups = [[f_eq("lifecyclestage", s), f_missing("hubspot_owner_id")]
              for s in ("salesqualifiedlead", "opportunity")]
    n = ctx.count("contacts", *groups)
    f = Finding(c.id, c.title, c.section, c.lens, count=n, denominator=_sales_stage_contacts(ctx))
    if n:
        f.evidence = ctx.sample("contacts", groups, ["email", "lifecyclestage", "company",
                                                     "createdate"])
    return f


# ── Activity and follow-up ──────────────────────────────────────

@check("act.overdue_tasks", "Overdue open tasks", SEC_ACT, "sales", weight=1.0,
       fix="cleanup-deals",
       impact="Follow-ups that were promised and did not happen.")
def overdue_tasks(ctx, c):
    open_tasks = ctx.count("tasks", [f_neq("hs_task_status", "COMPLETED")])
    if open_tasks is None:
        return Finding(c.id, c.title, c.section, c.lens, coverage=Coverage.NO_SCOPE,
                       notes=["Tasks unreadable: the token needs crm.objects.tasks.read."])
    groups = [[f_neq("hs_task_status", "COMPLETED"), f_lt("hs_timestamp", days_ago_ms(0))]]
    n = ctx.count("tasks", *groups)
    f = Finding(c.id, c.title, c.section, c.lens, count=n, denominator=open_tasks)
    f.notes.append(f"{open_tasks:,} open tasks.")
    if n:
        f.evidence = ctx.sample("tasks", groups, ["hs_task_subject", "hs_timestamp",
                                                  "hubspot_owner_id"])
        owners = ctx.client.get_all(ctx.client.path("owners"), {"limit": 100}) or []
        names = {str(o["id"]): (f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
                                or str(o["id"])) for o in owners}
        bd = ctx.breakdown("tasks", groups, "hubspot_owner_id",
                           list(names)[: ctx.max_breakdown_queries], "owner")
        bd["rows"] = [(names.get(k, k), v) for k, v in bd["rows"]]
        f.breakdown = bd
    return f


@check("act.leads_unowned", "Leads with no owner", SEC_ACT, "sales", fix="cleanup-lead-owners",
       weight=2.0)
def unowned_leads(ctx, c):
    leads = ctx.count("leads")
    if leads is None:
        return Finding(c.id, c.title, c.section, c.lens, coverage=Coverage.NO_HUB,
                       notes=["The leads object needs Sales Hub and crm.objects.leads.read."])
    n = ctx.count("leads", [f_missing("hubspot_owner_id")])
    f = Finding(c.id, c.title, c.section, c.lens, count=n, denominator=leads)
    f.notes.append(f"{leads:,} leads in the prospecting workspace.")
    return f
