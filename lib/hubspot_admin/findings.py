"""
The check model: what a check declares, what a finding carries, and how
findings roll up into graded sections.

A Check is a function plus metadata. It receives a Context and returns a
Finding. A Finding is evidence, not just a number: count and share, sample
records, a breakdown, the root causes the check could test, the fix, and the
prevention. Coverage says whether the check ran at all.
"""

from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

LENSES = ("shared", "marketing", "sales", "service", "platform", "commerce")


class Coverage:
    RAN = "ran"
    NO_SCOPE = "skipped:no_scope"      # token cannot read the object
    NO_HUB = "skipped:no_hub"          # portal does not have the hub or object
    NO_API = "skipped:no_api"          # HubSpot exposes this only in the UI
    PARTIAL = "partial"                # ran on a sample or hit a cap
    DISABLED = "skipped:disabled"      # turned off by a flag (e.g. --no-scan)
    ERROR = "skipped:error"


@dataclass
class Evidence:
    id: str
    properties: dict
    url: Optional[str] = None


@dataclass
class Finding:
    check: str
    title: str
    section: str
    lens: str
    count: Optional[int] = None
    denominator: Optional[int] = None
    severity: int = 0                       # 0 ok .. 4 critical
    coverage: str = Coverage.RAN
    evidence: list = field(default_factory=list)       # [Evidence]
    breakdown: dict = field(default_factory=dict)      # {"by": label, "rows": [(key, count)]}
    root_causes: list = field(default_factory=list)    # ranked strings
    fix: Optional[str] = None               # skill slug
    fix_steps: list = field(default_factory=list)      # UI steps when no skill applies
    prevention: Optional[str] = None
    impact: Optional[str] = None
    notes: list = field(default_factory=list)
    threshold: Optional[str] = None
    display: Optional[str] = None           # overrides count in tables (e.g. "12 (3 open)")
    scored: bool = False                    # True when the check set severity itself
    weight: float = 1.0                     # copied from the check, for ranking

    @property
    def share(self):
        if self.count is None or not self.denominator:
            return None
        return 100.0 * self.count / self.denominator

    @property
    def ran(self):
        return self.coverage in (Coverage.RAN, Coverage.PARTIAL)

    def as_dict(self):
        d = asdict(self)
        d["share"] = self.share
        return d


@dataclass
class Check:
    id: str
    title: str
    section: str
    lens: str
    fn: Callable
    fix: Optional[str] = None
    impact: Optional[str] = None
    prevention: Optional[str] = None
    weight: float = 1.0        # multiplies share before severity banding
    graded: bool = True        # informational checks never affect a grade
    requires: tuple = ()       # objects the check needs readable, for coverage reporting
    order: int = 0

    def run(self, ctx) -> Finding:
        try:
            f = self.fn(ctx, self)
        except Exception as e:  # a crashing check is a skipped check, never a crash
            f = Finding(self.id, self.title, self.section, self.lens,
                        coverage=Coverage.ERROR, notes=[f"{type(e).__name__}: {e}"])
        f.check, f.section, f.lens = self.id, self.section, self.lens
        f.title = f.title or self.title
        f.fix = f.fix or self.fix
        f.impact = f.impact or self.impact
        f.prevention = f.prevention or self.prevention
        if f.count is None and f.coverage == Coverage.RAN:
            f.coverage = Coverage.NO_SCOPE
        f.weight = self.weight
        if not self.graded:
            f.severity = 0
        elif f.ran and not f.scored and f.count:
            f.severity = severity_from_share(f.share, self.weight, f.count)
        return f


# ── Registry ────────────────────────────────────────────────────

class Registry:
    def __init__(self):
        self.checks = []

    def add(self, c):
        c.order = len(self.checks)
        self.checks.append(c)

    def for_lenses(self, lenses):
        return [c for c in self.checks if c.lens in lenses]

    def sections(self, lenses):
        seen, out = set(), []
        for c in self.for_lenses(lenses):
            if (c.lens, c.section) not in seen:
                seen.add((c.lens, c.section))
                out.append((c.lens, c.section))
        return out


registry = Registry()


def check(id, title, section, lens, **meta):
    """Decorator registering a check function `fn(ctx, check) -> Finding`."""
    if lens not in LENSES:
        raise ValueError(f"unknown lens {lens!r}")

    def deco(fn):
        registry.add(Check(id=id, title=title, section=section, lens=lens, fn=fn, **meta))
        return fn
    return deco


# ── Scoring ─────────────────────────────────────────────────────

# A handful of records is never critical, whatever share they are of a tiny
# denominator: 1 of 1 closed-lost deals is a note, not an emergency.
MATERIALITY_CAPS = ((3, 1), (10, 2), (50, 3))


def severity_from_share(share, weight=1.0, count=None):
    """0 ok, 1 low, 2 medium, 3 high, 4 critical. Banded on the weighted share
    of affected records, capped by the absolute count (MATERIALITY_CAPS) and,
    for checks weighted under 1, at high: a nice-to-have field is never
    critical. A finding with a count but no denominator is low."""
    if share is None:
        return 1 if count else 0
    s = share * weight
    if s < 1:
        sev = 0
    elif s < 5:
        sev = 1
    elif s < 15:
        sev = 2
    elif s < 30:
        sev = 3
    else:
        sev = 4
    if count is not None:
        for below, cap in MATERIALITY_CAPS:
            if count < below:
                sev = min(sev, cap)
                break
    if weight < 1:
        sev = min(sev, 3)
    return sev


LETTERS = {0: "A", 1: "B", 2: "C", 3: "D", 4: "F"}


def grade_letter(severity):
    return LETTERS.get(severity, "?")


@dataclass
class Section:
    """A graded group of findings: the unit the summary table shows."""
    lens: str
    title: str
    findings: list

    @property
    def ran(self):
        return [f for f in self.findings if f.ran]

    @property
    def skipped(self):
        return [f for f in self.findings if not f.ran]

    @property
    def severity(self):
        graded = [f.severity for f in self.ran]
        return max(graded) if graded else None

    @property
    def grade(self):
        """Worst finding severity. If any check was skipped the section cannot
        grade above B, because an unread problem is not an absent one."""
        sev = self.severity
        if sev is None:
            return "?"
        if self.skipped and sev < 1:
            sev = 1
        return grade_letter(sev)

    @property
    def coverage(self):
        return f"{len(self.ran)}/{len(self.findings)}"

    def as_dict(self):
        return {"lens": self.lens, "title": self.title, "grade": self.grade,
                "severity": self.severity, "coverage": self.coverage,
                "findings": [f.as_dict() for f in self.findings]}


def group_sections(findings, order):
    """Group findings into Sections following `order`, a list of (lens, title)."""
    by = {}
    for f in findings:
        by.setdefault((f.lens, f.section), []).append(f)
    return [Section(lens, title, by.get((lens, title), [])) for lens, title in order
            if (lens, title) in by]
