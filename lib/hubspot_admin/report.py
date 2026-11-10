"""
Render an audit run: markdown for people, JSON (schema_version 3) for the
implementation-plan skill, and a diff against the previous run of the same
scope from reports/history/.
"""

import datetime
import glob
import json
import os

from .findings import Coverage, grade_letter, group_sections

SCHEMA_VERSION = 3
MAX_TOP = 7

LENS_TITLES = {"shared": "Shared foundation", "marketing": "Marketing", "sales": "Sales",
               "service": "Service", "platform": "Platform & governance", "commerce": "Commerce"}
SEVERITY_WORDS = {0: "ok", 1: "low", 2: "medium", 3: "high", 4: "critical"}
COVERAGE_WORDS = {
    Coverage.NO_SCOPE: "token lacks the read scope, or the object is unavailable",
    Coverage.NO_HUB: "the portal does not have this hub or object",
    Coverage.NO_API: "HubSpot exposes this only in the UI",
    Coverage.PARTIAL: "ran on part of the data",
    Coverage.DISABLED: "turned off by a flag",
    Coverage.ERROR: "the check failed",
}


def fmt(n):
    if n is None:
        return "n/a"
    if isinstance(n, float):
        return f"{n:,.1f}"
    return f"{n:,}" if isinstance(n, int) else str(n)


def pct(f):
    return f"{f.share:.1f}%" if f.share is not None else "—"


# ── Derived views ───────────────────────────────────────────────

def rank_key(f):
    """Worst severity first, then the weighted share, then the count."""
    return (-f.severity, -((f.share or 0) * f.weight), -(f.count or 0))


def top_findings(findings, n=MAX_TOP):
    graded = [f for f in findings if f.ran and f.severity >= 1 and f.count]
    graded.sort(key=rank_key)
    return graded[:n]


def display_value(prop, value):
    """Epoch-millisecond timestamps read as dates; everything else as is."""
    if value in (None, ""):
        return ""
    s = str(value)
    if s.isdigit() and len(s) == 13:
        try:
            return datetime.datetime.fromtimestamp(int(s) / 1000, datetime.timezone.utc).date().isoformat()
        except (ValueError, OverflowError):
            return s
    if "T" in s and s.endswith("Z") and len(s) >= 20:
        return s[:10]
    return s


def prescription(findings):
    """Skills to run, ordered by the worst finding that names each. One row
    per skill."""
    best = {}
    for f in findings:
        if f.fix and f.ran and f.count and f.severity >= 1:
            cur = best.get(f.fix)
            if cur is None or rank_key(f) < rank_key(cur):
                best[f.fix] = f
    return sorted(best.values(), key=rank_key)


def coverage_summary(findings):
    ran = [f for f in findings if f.ran]
    skipped = {}
    for f in findings:
        if not f.ran:
            skipped.setdefault(f.coverage, []).append(f)
    return ran, skipped


# ── History ─────────────────────────────────────────────────────

def history_dir(out_dir):
    return os.path.join(out_dir, "history")


def previous_run(out_dir, scope_key, before_date):
    files = sorted(glob.glob(os.path.join(history_dir(out_dir), f"{scope_key}-*.json")))
    files = [p for p in files if not p.endswith(f"{scope_key}-{before_date}.json")]
    if not files:
        return None
    with open(files[-1]) as f:
        return json.load(f)


def diff(current_sections, previous):
    """Changes since the previous run: grade changes, counts that moved, new
    and resolved findings. Returns None when there is no previous run."""
    if not previous:
        return None
    prev = {}
    for s in previous.get("sections", []):
        for f in s.get("findings", []):
            prev[f["check"]] = f
    prev_grades = {(s["lens"], s["title"]): s["grade"] for s in previous.get("sections", [])}
    out = {"date": previous.get("date"), "grades": [], "counts": [], "new": [], "resolved": []}
    for s in current_sections:
        g0 = prev_grades.get((s.lens, s.title))
        if g0 and g0 != s.grade:
            out["grades"].append((s.title, g0, s.grade))
        for f in s.findings:
            if not f.ran:
                continue
            p = prev.get(f.check)
            if p is None:
                if f.count:
                    out["new"].append(f)
                continue
            c0 = p.get("count")
            if c0 is None or f.count is None:
                continue
            if c0 and not f.count:
                out["resolved"].append((f, c0))
            elif c0 != f.count and f.severity >= 1:
                out["counts"].append((f, c0, f.count))
    return out


# ── Summary prose ───────────────────────────────────────────────

def summary_paragraphs(sections, findings):
    tops = top_findings(findings, 3)
    paras = []
    if tops:
        f = tops[0]
        paras.append(f"The biggest problem is **{f.title.lower()}**: {fmt(f.count)}"
                     f"{' (' + pct(f) + ')' if f.share is not None else ''}. "
                     f"{f.impact or ''}".strip())
        if len(tops) > 1:
            rest = "; ".join(f"{t.title.lower()} ({fmt(t.count)}, {pct(t)})" for t in tops[1:])
            paras.append(f"Next: {rest}.")
    else:
        paras.append("No graded finding reached the low-severity threshold.")
    healthy = [s.title for s in sections if s.grade == "A"]
    if healthy:
        paras.append("Healthy: " + ", ".join(healthy) + ".")
    return paras


# ── Markdown ────────────────────────────────────────────────────

def render_markdown(meta, sections, findings, previous=None):
    scope = ", ".join(meta["lenses"])
    out = [f"# {meta['title']}\n",
           f"**Date:** {meta['date']}  ",
           f"**Portal:** {meta.get('portal_id') or 'unknown'}  ",
           f"**Scope:** {scope}  ",
           f"**API version:** {meta['api_version']}\n"]

    out.append("## Summary\n")
    out += [p + "\n" for p in summary_paragraphs(sections, findings)]
    ran, skipped = coverage_summary(findings)
    cov = f"Ran {len(ran)} of {len(findings)} checks."
    if skipped:
        cov += " Skipped: " + "; ".join(f"{len(v)} ({COVERAGE_WORDS.get(k, k)})"
                                        for k, v in skipped.items()) + "."
    out.append(cov + "\n")

    d = diff(sections, previous)
    if d:
        bits = []
        if d["new"]:
            bits.append(f"{len(d['new'])} new finding{'s' if len(d['new']) != 1 else ''}")
        if d["resolved"]:
            bits.append(f"{len(d['resolved'])} resolved")
        for title, g0, g1 in d["grades"]:
            bits.append(f"{title} {g0} → {g1}")
        out.append(f"Since {d['date']}: " + (", ".join(bits) if bits else "no change") + ".\n")

    out += ["### Grades\n", "| Section | Lens | Grade | Checks ran |", "|---|---|---|---|"]
    for s in sections:
        out.append(f"| {s.title} | {s.lens} | **{s.grade}** | {s.coverage} |")
    out.append("")

    tops = top_findings(findings)
    if tops:
        out.append("## Top findings\n")
        for i, f in enumerate(tops, 1):
            line = (f"{i}. **{f.title}**: {fmt(f.count)}"
                    f"{' of ' + fmt(f.denominator) + ' (' + pct(f) + ')' if f.share is not None else ''}"
                    f", {SEVERITY_WORDS[f.severity]}.")
            if f.impact:
                line += f" {f.impact}"
            if f.root_causes:
                line += f" {f.root_causes[0]}"
            if f.fix:
                line += f" Fix: `/{f.fix}`."
            out.append(line)
        out.append("")

    rx = prescription(findings)
    out.append("## Prescription\n")
    if rx:
        out += ["Skills to run, worst finding first. Each skill appears once.\n",
                "| # | Skill | Triggered by | Records | Severity |", "|---|---|---|---|---|"]
        for i, f in enumerate(rx, 1):
            out.append(f"| {i} | `/{f.fix}` | {f.title} | {fmt(f.count)} | "
                       f"{SEVERITY_WORDS[f.severity]} |")
    else:
        out.append("No finding mapped to a fix skill.")
    out.append("")

    current_lens = None
    n = 0
    for s in sections:
        if s.lens != current_lens:
            current_lens = s.lens
            out.append(f"# {LENS_TITLES.get(s.lens, s.lens)}\n")
        n += 1
        out.append(f"## {n}. {s.title} — grade {s.grade}\n")
        out += ["| Finding | Count | % | Severity |", "|---|---|---|---|"]
        for f in s.findings:
            if f.ran:
                out.append(f"| {f.title} | {f.display or fmt(f.count)} | {pct(f)} | "
                           f"{SEVERITY_WORDS[f.severity] if f.severity else '—'} |")
            else:
                out.append(f"| {f.title} | n/a | — | skipped |")
        out.append("")
        for f in s.findings:
            if not (f.ran and f.count and (f.evidence or f.breakdown.get("rows") or f.root_causes
                                           or f.fix_steps or f.notes or f.prevention)):
                if f.notes and f.ran:
                    out.append(f"*{f.title}:* " + " ".join(f.notes) + "\n")
                continue
            out.append(f"### {f.title}\n")
            if f.threshold:
                out.append(f"Threshold: {f.threshold}.\n")
            if f.evidence:
                props = list(f.evidence[0].properties.keys())
                out += ["Evidence (sample):\n", "| ID | " + " | ".join(props) + " |",
                        "|" + "---|" * (len(props) + 1)]
                for e in f.evidence:
                    link = f"[{e.id}]({e.url})" if e.url else e.id
                    out.append(f"| {link} | " + " | ".join(display_value(p, e.properties.get(p))
                                                            for p in props) + " |")
                out.append("")
            if f.breakdown.get("rows"):
                out += [f"By {f.breakdown['by']}:\n", "| Value | Count |", "|---|---|"]
                for k, v in f.breakdown["rows"]:
                    out.append(f"| {k} | {fmt(v)} |")
                out.append("")
            if f.root_causes:
                out.append("Why this happens: " + " ".join(f.root_causes) + "\n")
            if f.fix:
                out.append(f"Fix: `/{f.fix}`.\n")
            if f.fix_steps:
                out += ["Fix (UI):\n"] + [f"- {step}" for step in f.fix_steps] + [""]
            if f.prevention:
                out.append(f"Prevention: {f.prevention}\n")
            for note in f.notes:
                out.append(f"{note}\n")

    skipped_all = [f for f in findings if not f.ran]
    out.append("# What this audit could not check\n")
    if skipped_all:
        out += ["| Check | Why | How to get it |", "|---|---|---|"]
        for f in skipped_all:
            out.append(f"| {f.title} | {COVERAGE_WORDS.get(f.coverage, f.coverage)} | "
                       f"{' '.join(f.notes) or 'see the check notes'} |")
    else:
        out.append("Every selected check ran.")
    out.append("")

    out += ["# Method\n",
            f"Read-only. {meta['requests']:,} API requests over {meta['duration_s']:.0f}s. "
            f"Record scans: {meta.get('scan_note', 'enabled')}. "
            "Severity bands on the weighted share of affected records: <1% ok, <5% low, "
            "<15% medium, <30% high, else critical; fewer than 3 records caps at low, fewer than "
            "10 at medium, fewer than 50 at high. A section grades on its worst finding and "
            "cannot grade A while any of its checks was skipped. "
            f"Generated by `{meta['command']}`.\n"]
    return "\n".join(out)


# ── JSON ────────────────────────────────────────────────────────

def as_json(meta, sections, findings, previous=None):
    d = diff(sections, previous)
    return {
        "schema_version": SCHEMA_VERSION,
        "date": meta["date"],
        "scope": meta["lenses"],
        "portal_id": meta.get("portal_id"),
        "api_version": meta["api_version"],
        "sections": [s.as_dict() for s in sections],
        "top_findings": [f.check for f in top_findings(findings)],
        "prescription": [{"skill": f.fix, "check": f.check, "title": f.title, "count": f.count,
                          "share": f.share, "severity": f.severity, "section": f.section}
                         for f in prescription(findings)],
        "coverage": {"ran": sum(1 for f in findings if f.ran), "total": len(findings),
                     "skipped": [{"check": f.check, "reason": f.coverage} for f in findings
                                 if not f.ran]},
        "changes": None if not d else {
            "since": d["date"],
            "grades": [{"section": t, "from": a, "to": b} for t, a, b in d["grades"]],
            "counts": [{"check": f.check, "from": a, "to": b} for f, a, b in d["counts"]],
            "new": [f.check for f in d["new"]],
            "resolved": [f.check for f, _ in d["resolved"]],
        },
        "method": {"requests": meta["requests"], "duration_s": meta["duration_s"],
                   "options": meta.get("options", {})},
    }


def build_sections(findings, order):
    return group_sections(findings, order)


__all__ = ["render_markdown", "as_json", "build_sections", "previous_run", "diff",
           "prescription", "top_findings", "grade_letter", "history_dir",
           "datetime"]
