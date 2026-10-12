"""
Offline tests for the audit engine. No network, no portal, no token: every
HTTP call is answered by a fake HubSpot with synthetic counts.

    uv run --with pytest --with requests --with python-dotenv pytest tests/
"""

import importlib.util
import json
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).parent.parent / "skills/hubspot-audit/scripts/audit_portal.py"
spec = importlib.util.spec_from_file_location("audit_portal", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeHubSpot:
    """Answers search counts from a table keyed by object type and the set of
    filtered property names; everything else falls back to a default."""

    def __init__(self, totals=None, forbidden=()):
        self.totals = totals or {}
        self.forbidden = set(forbidden)
        self.calls = []

    def request(self, method, url, headers=None, json=None, params=None):
        path = url.removeprefix(audit.BASE)
        self.calls.append((method, path))
        if method != "GET" and not path.endswith("/search"):
            raise AssertionError(f"audit attempted a write: {method} {path}")

        if path.startswith("/crm/v3/objects/") and path.endswith("/search"):
            obj = path.split("/")[4]
            if obj in self.forbidden:
                return FakeResponse(403)
            groups = (json or {}).get("filterGroups", [])
            props = frozenset(f["propertyName"] for g in groups for f in g["filters"])
            return FakeResponse(200, {"total": self.totals.get((obj, props), 10)})
        if path == "/crm/v3/owners":
            return FakeResponse(200, {"results": [{"id": "901"}, {"id": "902"}]})
        if path == "/crm/v3/pipelines/deals":
            stage = lambda i, closed="false": {"id": f"s{i}", "metadata": {"isClosed": closed}}
            return FakeResponse(200, {"results": [
                {"id": "default", "label": "Sales", "stages": [stage(i) for i in range(4)]},
                {"id": "bloated", "label": "Legacy", "stages": [stage(i) for i in range(14)]},
            ]})
        if path == "/crm/v3/lists/search":
            return FakeResponse(200, {"total": 42})
        if path == "/automation/v4/flows":
            return FakeResponse(200, {"results": [{"isEnabled": True}, {"isEnabled": False}]})
        if path == "/marketing/v3/forms":
            return FakeResponse(200, {"results": [{}, {}, {}]})
        return FakeResponse(404)


@pytest.fixture
def portal(monkeypatch):
    fake = FakeHubSpot(totals={
        ("contacts", frozenset()): 1000,
        ("companies", frozenset()): 200,
        ("deals", frozenset()): 400,
        ("deals", frozenset({"hs_is_closed"})): 100,
        ("contacts", frozenset({"email"})): 600,
    })
    monkeypatch.setattr(audit.requests, "request", fake.request)
    monkeypatch.setattr(audit, "QUERY_DELAY", 0)
    return fake


def keys(dims):
    return [d.key for d in dims]


SHARED = ["database_size", "owner_health", "company_data", "duplicates"]


def test_every_dimension_is_tagged_and_scoped():
    assert set(audit.TAGS) == set(audit.DIMENSIONS)
    assert set(audit.TAGS.values()) == {"shared", "marketing", "sales"}


def test_marketing_and_sales_share_the_same_foundation(portal):
    marketing, sales = audit.run("marketing"), audit.run("sales")
    assert keys(marketing)[:4] == keys(sales)[:4] == SHARED
    assert not {d.tag for d in marketing} & {"sales"}
    assert not {d.tag for d in sales} & {"marketing"}
    # The shared numbers are identical whichever lens produced them.
    assert [d.as_dict() for d in marketing[:4]] == [d.as_dict() for d in sales[:4]]


def test_full_scope_is_the_union(portal):
    full = keys(audit.run("full"))
    assert full == SHARED + keys(audit.run("marketing"))[4:] + keys(audit.run("sales"))[4:]


def test_audit_never_writes(portal):
    audit.run("full")
    assert all(m == "GET" or p.endswith("/search") for m, p in portal.calls)


def test_grades_follow_the_rubric():
    assert [audit.grade(p) for p in (0, 4.9, 5, 14.9, 15, 29.9, 30, 49.9, 50, 100)] == \
        ["A", "A", "B", "B", "C", "C", "D", "D", "F", "F"]
    assert audit.grade(None) == "?"


def test_prescription_orders_by_priority_and_dedupes(portal):
    rx = audit.prescription(audit.run("marketing"))
    skills = [r["skill"] for r in rx]
    assert len(skills) == len(set(skills))
    assert [r["priority"] for r in rx] == sorted(r["priority"] for r in rx)
    assert skills[0] == "delete-no-email-contacts"  # P0, largest count


def test_pipeline_config_flags_bloated_pipelines(portal):
    d = next(d for d in audit.run("sales") if d.key == "pipeline_config")
    bloated = next(r for r in d.rows if "more than" in r["metric"])
    assert bloated["value"] == 1 and bloated["total"] == 2


def test_unreadable_objects_report_na_not_zero(monkeypatch):
    fake = FakeHubSpot(forbidden={"tasks", "leads"})
    monkeypatch.setattr(audit.requests, "request", fake.request)
    monkeypatch.setattr(audit, "QUERY_DELAY", 0)
    d = next(d for d in audit.run("sales") if d.key == "sales_activity")
    assert all(r["value"] is None for r in d.rows)
    assert d.grade == "?" and d.notes


def test_main_writes_markdown_and_json(portal, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "test-token-not-real")
    audit.main(["--scope", "sales"])
    md, = (tmp_path / "reports").glob("hubspot-sales-audit-*.md")
    js, = (tmp_path / "reports").glob("hubspot-sales-audit-*.json")
    text = md.read_text()
    assert text.startswith("# HubSpot Sales Audit Report")
    assert "## Prescription" in text and "Email Deliverability" not in text
    data = json.loads(js.read_text())
    assert data["scope"] == "sales" and len(data["dimensions"]) == 9


def test_main_refuses_to_run_without_a_token(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(audit, "load_dotenv", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        audit.main([])
