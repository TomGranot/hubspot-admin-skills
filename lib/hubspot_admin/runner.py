"""Run the selected checks against a portal and write the reports."""

import datetime
import json
import os
import time

from . import checks  # noqa: F401  (registers every check)
from . import paths, report
from .context import Context
from .findings import registry

SCOPES = {
    "full": ("shared", "marketing", "sales"),
    "marketing": ("shared", "marketing"),
    "sales": ("shared", "sales"),
    "service": ("shared", "service"),
    "platform": ("shared", "platform"),
    "commerce": ("shared", "commerce"),
}
REPORT_NAMES = {("shared", "marketing", "sales"): "hubspot-audit",
                ("shared", "marketing"): "hubspot-marketing-audit",
                ("shared", "sales"): "hubspot-sales-audit"}
REPORT_TITLES = {"hubspot-audit": "HubSpot CRM Audit Report",
                 "hubspot-marketing-audit": "HubSpot Marketing Audit Report",
                 "hubspot-sales-audit": "HubSpot Sales Audit Report"}


def lenses_for(scope_arg):
    """`--scope full|marketing|sales|service,...` to an ordered lens tuple."""
    wanted = []
    for part in str(scope_arg).split(","):
        part = part.strip()
        if part not in SCOPES:
            raise ValueError(f"unknown scope {part!r}; choose from {', '.join(sorted(SCOPES))}")
        for lens in SCOPES[part]:
            if lens not in wanted:
                wanted.append(lens)
    missing = [l for l in wanted if not registry.for_lenses((l,))]
    if missing:
        raise ValueError(f"the {', '.join(missing)} lens is planned but has no checks yet "
                         "(see docs/rewrite-plan-3.0.md)")
    return tuple(wanted)


def report_name(lenses):
    name = REPORT_NAMES.get(tuple(lenses))
    if name:
        return name
    return "hubspot-audit-" + "-".join(l for l in lenses if l != "shared")


def run_checks(client, lenses, options=None, log=print):
    """Run every registered check for `lenses` in registry order. Returns
    (findings, sections, ctx)."""
    ctx = Context(client, options or {}, log=log)
    ctx.load_account()
    selected = registry.for_lenses(lenses)
    findings = []
    for i, c in enumerate(selected, 1):
        log(f"[{i}/{len(selected)}] {c.title}")
        findings.append(c.run(ctx))
    sections = report.build_sections(findings, registry.sections(lenses))
    return findings, sections, ctx


def write_reports(client, lenses, options=None, out_dir="reports", log=print, command="audit.py"):
    started = time.time()
    findings, sections, ctx = run_checks(client, lenses, options, log)
    today = datetime.date.today().isoformat()
    name = report_name(lenses)
    scope_key = "-".join(lenses)
    previous = report.previous_run(out_dir, scope_key, today)
    meta = {
        "title": REPORT_TITLES.get(name, "HubSpot Audit Report"),
        "date": today, "lenses": list(lenses), "portal_id": ctx.portal_id,
        "api_version": paths.API_VERSION, "requests": client.calls,
        "duration_s": time.time() - started, "command": command,
        "options": {k: v for k, v in (options or {}).items() if k != "cache_dir"},
        "scan_note": ("disabled" if not (options or {}).get("scan", True)
                      else f"capped at {options['scan_cap']:,} records" if (options or {}).get("scan_cap")
                      else "full"),
    }
    os.makedirs(report.history_dir(out_dir), exist_ok=True)
    stem = os.path.join(out_dir, f"{name}-{today}")
    md = report.render_markdown(meta, sections, findings, previous)
    data = report.as_json(meta, sections, findings, previous)
    with open(f"{stem}.md", "w") as f:
        f.write(md)
    with open(f"{stem}.json", "w") as f:
        json.dump(data, f, indent=2, default=str)
    with open(os.path.join(report.history_dir(out_dir), f"{scope_key}-{today}.json"), "w") as f:
        json.dump(data, f, indent=2, default=str)
    return {"markdown": f"{stem}.md", "json": f"{stem}.json", "sections": sections,
            "findings": findings, "data": data}
