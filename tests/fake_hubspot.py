"""
A fake HubSpot for offline tests. It holds synthetic records per object type
and evaluates Search API filter groups itself, so checks are exercised end to
end: counts, samples, breakdowns, scans with paging, the 10,000-result cap,
sorts, and BETWEEN segmentation. Everything else (owners, pipelines, flows,
forms, lists, account info) is answered from small fixtures.

Any non-GET call that is not a /search is an assertion failure: the audit
must never write.
"""

import datetime
import re

NOW = datetime.datetime.now(datetime.timezone.utc)


def ms(days_offset):
    return str(int((NOW + datetime.timedelta(days=days_offset)).timestamp() * 1000))


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.text = str(self._payload)

    def json(self):
        return self._payload


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def matches(props, f):
    value, op = props.get(f["propertyName"]), f["operator"]
    present = value not in (None, "")
    if op == "NOT_HAS_PROPERTY":
        return not present
    if op == "HAS_PROPERTY":
        return present
    if op == "EQ":
        return present and str(value).lower() == str(f["value"]).lower()
    if op == "NEQ":
        return not present or str(value).lower() != str(f["value"]).lower()
    if op == "IN":
        return present and str(value) in [str(v) for v in f["values"]]
    if op == "CONTAINS_TOKEN":
        return present and f["value"].lower() in re.split(r"[\s\-_]+", str(value).lower())
    n, a = _num(value), _num(f.get("value"))
    if n is None or a is None:
        return False
    if op == "GTE":
        return n >= a
    if op == "LT":
        return n < a
    if op == "BETWEEN":
        return a <= n <= _num(f["highValue"])
    raise AssertionError(f"fake does not implement {op}")


def match_groups(props, groups):
    if not groups:
        return True
    return any(all(matches(props, f) for f in g["filters"]) for g in groups)


class FakeHubSpot:
    CAP = 10_000

    def __init__(self, records=None, forbidden=(), owners=None, archived_owners=None,
                 pipelines=None, flows=None, forms=None, lists_total=42,
                 account=None):
        self.records = records or {}          # object -> [ {id, properties} ]
        self.forbidden = set(forbidden)
        self.owners = owners if owners is not None else [
            {"id": "1", "firstName": "Ada", "lastName": "Lovelace", "userId": 11},
            {"id": "2", "firstName": "Grace", "lastName": "Hopper", "userId": 12},
        ]
        self.archived = archived_owners if archived_owners is not None else [
            {"id": "999", "firstName": "Gone", "lastName": "Person", "userId": 99}]
        self.pipelines = pipelines if pipelines is not None else [
            {"id": "default", "label": "Sales", "stages": [self.stage(i) for i in range(4)]},
            {"id": "legacy", "label": "Legacy", "stages": [self.stage(i) for i in range(14)]},
            {"id": "empty", "label": "Abandoned", "stages": [self.stage(0)]},
        ]
        self.flows = flows if flows is not None else [
            {"id": "f1", "name": "Lead routing", "isEnabled": True, "objectTypeId": "0-1"},
            {"id": "f2", "name": "Copy of test flow", "isEnabled": False, "objectTypeId": "0-1"},
        ]
        self.forms = forms if forms is not None else [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        self.lists_total = lists_total
        self.account = account or {"portalId": 12345, "accountType": "DEVELOPER_TEST"}
        self.calls = []

    @staticmethod
    def stage(i, closed="false"):
        return {"id": f"s{i}", "metadata": {"isClosed": closed}}

    # ── Dispatch ────────────────────────────────────────────────

    def request(self, method, url, headers=None, json=None, params=None, timeout=None):
        path = url.split("api.hubapi.com", 1)[1]
        self.calls.append((method, path, json, params))
        if method != "GET" and not path.endswith("/search"):
            raise AssertionError(f"audit attempted a write: {method} {path}")
        m = re.match(r"^/crm/objects/2026-09/([a-z_]+)/search$", path)
        if m:
            return self.search(m.group(1), json or {})
        if path == "/crm/v3/owners":
            archived = str((params or {}).get("archived", "false")).lower() == "true"
            return FakeResponse(200, {"results": self.archived if archived else self.owners})
        if path == "/crm/v3/pipelines/deals":
            return FakeResponse(200, {"results": self.pipelines})
        if path == "/crm/v3/lists/search":
            return FakeResponse(200, {"total": self.lists_total})
        if path == "/automation/v4/flows":
            return FakeResponse(200, {"results": self.flows})
        if path == "/marketing/v3/forms":
            return FakeResponse(200, {"results": self.forms})
        if path == "/account-info/v3/details":
            return FakeResponse(200, self.account)
        return FakeResponse(404, {"message": f"no fake for {path}"})

    def search(self, obj, body):
        if obj in self.forbidden:
            return FakeResponse(403, {"message": "forbidden"})
        rows = [r for r in self.records.get(obj, [])
                if match_groups(r["properties"], body.get("filterGroups"))]
        for sort in reversed(body.get("sorts") or []):
            prop, desc = sort["propertyName"], sort.get("direction") == "DESCENDING"
            rows.sort(key=lambda r: _num(r["properties"].get(prop)) or 0, reverse=desc)
        total = len(rows)
        offset = int(body.get("after") or 0)
        limit = int(body.get("limit") or 10)
        page = rows[offset: offset + limit]
        props = body.get("properties")
        out = [{"id": r["id"], "properties": ({p: r["properties"].get(p) for p in props}
                                              if props else dict(r["properties"]))}
               for r in page]
        payload = {"total": total, "results": out}
        nxt = offset + limit
        if nxt < total and nxt < self.CAP:
            payload["paging"] = {"next": {"after": str(nxt)}}
        return FakeResponse(200, payload)


# ── A synthetic portal with known defects ───────────────────────

def contact(i, **props):
    base = {"email": f"person{i}@example-co.com", "firstname": f"First{i}", "lastname": f"Last{i}",
            "company": "Example Co", "lifecyclestage": "lead", "hubspot_owner_id": "1",
            "hs_object_source": "FORM", "hs_analytics_source": "ORGANIC_SEARCH",
            "createdate": ms(-(i % 400) - 1), "hs_marketable_status": "true",
            "hs_email_last_send_date": ms(-30), "hs_email_last_open_date": ms(-20),
            "associatedcompanyid": "100"}
    base.update(props)
    return {"id": str(i), "properties": {k: v for k, v in base.items() if v is not None}}


def company(i, **props):
    base = {"name": f"Company {i}", "domain": f"company{i}.com", "industry": "SOFTWARE",
            "country": "US", "createdate": ms(-(i % 300) - 1), "num_associated_contacts": "3",
            "hubspot_owner_id": "1", "hs_object_source": "IMPORT"}
    base.update(props)
    return {"id": str(1000 + i), "properties": {k: v for k, v in base.items() if v is not None}}


def deal(i, closed=False, won=False, **props):
    base = {"dealname": f"Deal {i}", "amount": "1000", "closedate": ms(30), "createdate": ms(-200),
            "notes_last_updated": ms(-2), "notes_next_activity_date": ms(5), "dealstage": "s1",
            "pipeline": "default", "hubspot_owner_id": "1", "num_associated_contacts": "1",
            "hs_is_closed": str(closed).lower(), "hs_is_closed_won": str(won).lower()}
    base.update(props)
    return {"id": str(5000 + i), "properties": {k: v for k, v in base.items() if v is not None}}


def synthetic_portal():
    """1,000 contacts, 100 companies, 40 deals, 10 tasks, 5 leads, defects planted
    with counts the tests assert against. See PLANTED for the expected values."""
    contacts = []
    for i in range(1000):
        props = {}
        if i < 600:
            props["company"] = None                 # 60% missing company
        if i < 50:
            props["hubspot_owner_id"] = None        # 5% unowned
            props["hs_object_source"] = "IMPORT"    # all from one import
        if 50 <= i < 60:
            props["hubspot_owner_id"] = "999"       # deactivated owner
        if 60 <= i < 65:
            props["email"] = "not an email"         # invalid syntax
        if 65 <= i < 70:
            props["email"] = None                   # missing email
        if 70 <= i < 80:
            props["hs_email_hard_bounce_reason_enum"] = "UNKNOWN_USER"
        if 80 <= i < 85:
            props["lifecyclestage"] = "opportunity"
            props["num_associated_deals"] = "0"
        if 85 <= i < 90:
            props["hs_current_customer"] = "true"
            props["lifecyclestage"] = "lead"
        if 90 <= i < 100:
            props["lifecyclestage"] = None
        contacts.append(contact(i, **props))
    # Duplicate groups: 3 by email (one gmail-dot variant), 1 by phone, 1 by name+company
    contacts += [
        contact(2001, email="dup.one@gmail.com"), contact(2002, email="dupone@gmail.com"),
        contact(2003, email="DupOne+promo@gmail.com"),                       # group of 3
        contact(2004, email="two@acme.io"), contact(2005, email="Two@acme.io"),   # group of 2
        contact(2006, email="three@acme.io"), contact(2007, email="three@acme.io"),  # group of 2
        contact(2008, email="p1@x.io", phone="+1 (555) 010-2020"),
        contact(2009, email="p2@x.io", phone="555-010-2020"),                 # phone group of 2
        contact(2010, email="n1@y.io", firstname="Sam", lastname="Lee", company="Acme Inc"),
        contact(2011, email="n2@y.io", firstname="Sam", lastname="Lee", company="Acme, Inc."),
    ]
    companies = [company(i) for i in range(100)]
    for i in range(30):
        companies[i]["properties"]["domain"] = None            # 30% missing domain
    companies += [company(900, domain="www.dupe.com"), company(901, domain="dupe.com"),
                  company(902, domain="https://dupe.com/")]      # domain group of 3
    companies += [company(910, name="Globex Corp", domain="g1.com"),
                  company(911, name="Globex Corporation", domain="g2.com")]   # name group of 2
    deals = [deal(i) for i in range(30)]
    deals += [deal(100, amount=None), deal(101, amount=None),              # missing amount
              deal(102, closedate=ms(-10)), deal(103, closedate=ms(-40)),  # past due
              deal(104, notes_last_updated=ms(-90)),                        # stale
              deal(105, hubspot_owner_id="999"),                            # deactivated owner
              deal(106, closed=True, won=False),                            # lost, no reason
              deal(107, closed=True, won=True, closedate=ms(-5)),
              deal(108, amount="250000"),                                   # outlier
              deal(109, pipeline="legacy")]
    tasks = [{"id": f"t{i}", "properties": {"hs_task_status": "NOT_STARTED",
                                             "hs_timestamp": ms(-3 if i < 4 else 3),
                                             "hs_task_subject": f"Call {i}",
                                             "hubspot_owner_id": "1"}} for i in range(10)]
    leads = [{"id": f"l{i}", "properties": {"hubspot_owner_id": None if i < 2 else "1"}}
             for i in range(5)]
    return {"contacts": contacts, "companies": companies, "deals": deals, "tasks": tasks,
            "leads": leads}


PLANTED = {
    "contacts_total": 1011,
    "contacts_missing_company": 600,
    "contacts_unowned": 50,
    "contacts_deactivated_owner": 10,
    "contacts_invalid_email": 5,
    "contacts_missing_email": 5,
    "hard_bounced": 10,
    "dupes_email_extra": 4,     # groups of 3,2,2 -> 2+1+1
    "dupes_phone_extra": 1,
    "dupes_name_extra": 1,
    "companies_missing_domain": 30,
    "dupes_company_domain_extra": 2,
    "dupes_company_name_extra": 1,
    "deals_missing_amount": 2,
    "deals_past_due": 2,
    "deals_stale": 1,
    "deals_deactivated_owner": 1,
    "deals_lost_no_reason": 1,
    "deals_amount_outliers": 1,
    "overdue_tasks": 4,
    "unowned_leads": 2,
    "empty_pipelines": 1,
    "bloated_pipelines": 1,
}
