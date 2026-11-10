"""
The Context a check receives: the client, portal totals, cached scans, and
helpers for evidence (sample records with deep links) and breakdowns.
"""

import re

from . import search as S
from .findings import Evidence

OBJECT_URL_SEGMENT = {"contacts": "0-1", "companies": "0-2", "deals": "0-3", "tickets": "0-5"}

# Enumerations HubSpot uses for "where did this record come from". Breakdowns
# count per value with one Search call each, since the API has no group-by.
OBJECT_SOURCES = ["IMPORT", "API", "FORM", "INTEGRATION", "CRM_UI", "SALESFORCE",
                  "WORKFLOWS", "CONVERSATIONS", "EMAIL_INTEGRATION", "MEETINGS",
                  "MOBILE_IOS", "MOBILE_ANDROID", "BIDEN", "AUTOMATION_PLATFORM"]
ANALYTICS_SOURCES = ["ORGANIC_SEARCH", "PAID_SEARCH", "EMAIL_MARKETING", "SOCIAL_MEDIA",
                     "REFERRALS", "OTHER_CAMPAIGNS", "DIRECT_TRAFFIC", "OFFLINE", "PAID_SOCIAL"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
FREEMAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com",
            "live.com", "msn.com", "protonmail.com", "proton.me", "gmx.com", "gmx.de",
            "web.de", "yandex.ru", "mail.ru", "qq.com", "163.com"}


class Context:
    def __init__(self, client, options=None, log=None):
        self.client = client
        self.options = options or {}
        self.log = log or (lambda *a: None)
        self.totals = {}          # object -> total count
        self.cache = {}           # arbitrary shared values between checks
        self.scans = {}           # object -> (records, info)
        self.portal_id = None
        self.account = {}
        self.max_breakdown_queries = self.options.get("max_breakdown_queries", 12)
        self.sample_size = self.options.get("sample_size", 5)

    # ── Portal ──────────────────────────────────────────────────

    def load_account(self):
        self.account = self.client.account_info() or {}
        self.portal_id = self.account.get("portalId")
        return self.account

    def total(self, object_type):
        if object_type not in self.totals:
            self.totals[object_type] = S.count(self.client, object_type)
        return self.totals[object_type]

    def count(self, object_type, *groups):
        return S.count(self.client, object_type, *groups)

    def record_url(self, object_type, record_id):
        seg = OBJECT_URL_SEGMENT.get(object_type)
        if not (self.portal_id and seg):
            return None
        return f"https://app.hubspot.com/contacts/{self.portal_id}/record/{seg}/{record_id}"

    # ── Evidence ────────────────────────────────────────────────

    def sample(self, object_type, groups, properties, n=None, sorts=None):
        """Sample records for a finding, as Evidence with deep links."""
        n = n or self.sample_size
        recs = S.sample(self.client, object_type, groups, properties, n=n, sorts=sorts)
        return [Evidence(r["id"], {p: (r.get("properties") or {}).get(p) for p in properties},
                         self.record_url(object_type, r["id"])) for r in recs]

    def evidence_from_records(self, object_type, records, properties, n=None):
        n = n or self.sample_size
        return [Evidence(r["id"], {p: (r.get("properties") or {}).get(p) for p in properties},
                         self.record_url(object_type, r["id"])) for r in records[:n]]

    # ── Breakdowns ──────────────────────────────────────────────

    def breakdown(self, object_type, groups, prop, values, label=None, top=5):
        """Count the finding per value of `prop` (one Search call per value,
        capped). Returns {"by": label, "rows": [(value, count)], "covered": n}."""
        rows = []
        for v in values[: self.max_breakdown_queries]:
            n = self.count(object_type, *[g + [S.f_eq(prop, v)] for g in (groups or [[]])])
            if n:
                rows.append((v, n))
        rows.sort(key=lambda r: -r[1])
        return {"by": label or prop, "rows": rows[:top], "covered": sum(n for _, n in rows)}

    def breakdown_from_records(self, records, prop, label=None, top=5, transform=None):
        counts = {}
        for r in records:
            v = (r.get("properties") or {}).get(prop) or "(none)"
            if transform:
                v = transform(v)
            counts[v] = counts.get(v, 0) + 1
        rows = sorted(counts.items(), key=lambda kv: -kv[1])[:top]
        return {"by": label or prop, "rows": rows, "covered": sum(counts.values())}

    @staticmethod
    def dominant(breakdown, finding_count, threshold=0.4):
        """The top breakdown value when it explains more than `threshold` of
        the finding; otherwise None. Used to state a root cause only when the
        data supports it."""
        rows = (breakdown or {}).get("rows") or []
        if not rows or not finding_count:
            return None
        key, n = rows[0]
        if n / finding_count >= threshold:
            return key, n, 100.0 * n / finding_count
        return None

    # ── Scans ───────────────────────────────────────────────────

    def scan(self, object_type, properties, groups=None):
        """Full record scan, shared between checks in one run. Honors the
        `scan` (bool) and `scan_cap` (int) options."""
        key = (object_type, tuple(sorted(properties)))
        if key in self.scans:
            return self.scans[key]
        if not self.options.get("scan", True):
            self.scans[key] = ([], {"complete": False, "disabled": True, "total": None,
                                    "fetched": 0})
            return self.scans[key]
        self.log(f"    scanning {object_type} ({', '.join(properties)})")
        records, info = S.cached_scan(
            self.client, object_type, properties, groups,
            cap=self.options.get("scan_cap"),
            cache_dir=self.options.get("cache_dir"),
            ttl_hours=self.options.get("cache_ttl_hours", 12),
            on_progress=lambda n, t: self.log(f"      {n:,}/{t:,}") if n % 5000 == 0 else None)
        self.scans[key] = (records, info)
        return self.scans[key]
