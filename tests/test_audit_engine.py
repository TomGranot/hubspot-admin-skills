"""
Offline tests for the 3.0 audit engine. A fake HubSpot evaluates every search
over a synthetic portal with planted defects; the tests assert the engine
finds each one with the planted count, grades on more than one signal, counts
duplicates, reports coverage honestly, scans past the 10,000-result cap, and
renders both report formats.

    uv run --with pytest --with requests --with python-dotenv pytest tests/
"""

import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from fake_hubspot import FakeHubSpot, PLANTED, synthetic_portal, contact, ms  # noqa: E402
import hubspot_admin.client as client_mod  # noqa: E402
from hubspot_admin import Client  # noqa: E402
from hubspot_admin.runner import run_checks, lenses_for, write_reports, report_name  # noqa: E402
from hubspot_admin import search as S  # noqa: E402
from hubspot_admin.findings import registry, Section, Finding  # noqa: E402


@pytest.fixture(autouse=True)
def no_delays(monkeypatch):
    monkeypatch.setattr(client_mod, "SEARCH_DELAY", 0)
    monkeypatch.setattr(client_mod, "GENERAL_DELAY", 0)
    monkeypatch.setattr(client_mod.time, "sleep", lambda s: None)


def make_client(fake):
    return Client("test-token-not-real", session=fake)


@pytest.fixture(scope="module")
def portal_run():
    """One full run over the synthetic portal, shared by the read-only tests."""
    fake = FakeHubSpot(synthetic_portal())
    client = Client("test-token-not-real", session=fake, search_delay=0, general_delay=0)
    findings, sections, ctx = run_checks(client, lenses_for("full"), {"scan": True}, log=lambda *a: None)
    return fake, findings, sections


def by_check(findings):
    return {f.check: f for f in findings}


def section(sections, title):
    return next(s for s in sections if s.title == title)


# ── Registry and scopes ─────────────────────────────────────────

def test_every_check_has_a_lens_section_and_unique_id():
    ids = [c.id for c in registry.checks]
    assert len(ids) == len(set(ids))
    assert {c.lens for c in registry.checks} <= {"shared", "marketing", "sales"}
    assert all(c.section for c in registry.checks)
    assert len(ids) >= 45


def test_scopes_expand_to_lenses():
    assert lenses_for("full") == ("shared", "marketing", "sales")
    assert lenses_for("marketing") == ("shared", "marketing")
    assert lenses_for("sales,marketing") == ("shared", "sales", "marketing")
    with pytest.raises(ValueError):
        lenses_for("finance")
    with pytest.raises(ValueError, match="planned but has no checks"):
        lenses_for("service")
    assert report_name(("shared", "sales")) == "hubspot-sales-audit"
    assert report_name(("shared", "sales", "marketing")) == "hubspot-audit-sales-marketing"


# ── Read-only ───────────────────────────────────────────────────

def test_audit_never_writes(portal_run):
    fake, _, _ = portal_run
    assert all(m == "GET" or p.endswith("/search") for m, p, _, _ in fake.calls)
    object_searches = [p for m, p, _, _ in fake.calls if p.startswith("/crm/objects/")]
    assert object_searches and all("/crm/objects/2026-09/" in p for p in object_searches)


# ── Planted defects are found with the planted counts ───────────

@pytest.mark.parametrize("check_id, planted", [
    ("db.contacts", "contacts_total"),
    ("complete.missing_company", "contacts_missing_company"),
    ("owners.unowned_contacts", "contacts_unowned"),
    ("owners.deactivated_contacts", "contacts_deactivated_owner"),
    ("valid.contact_email_syntax", "contacts_invalid_email"),
    ("complete.missing_email", "contacts_missing_email"),
    ("deliv.hard_bounced", "hard_bounced"),
    ("dupes.contacts_email", "dupes_email_extra"),
    ("dupes.contacts_phone", "dupes_phone_extra"),
    ("dupes.contacts_name_company", "dupes_name_extra"),
    ("companies.missing_domain", "companies_missing_domain"),
    ("dupes.companies_domain", "dupes_company_domain_extra"),
    ("dupes.companies_name", "dupes_company_name_extra"),
    ("deal.missing_amount", "deals_missing_amount"),
    ("velo.past_due", "deals_past_due"),
    ("velo.stale", "deals_stale"),
    ("own.deals_deactivated", "deals_deactivated_owner"),
    ("deal.lost_no_reason", "deals_lost_no_reason"),
    ("deal.amount_outliers", "deals_amount_outliers"),
    ("act.overdue_tasks", "overdue_tasks"),
    ("act.leads_unowned", "unowned_leads"),
    ("pipe.empty", "empty_pipelines"),
    ("pipe.bloated", "bloated_pipelines"),
])
def test_planted_defect_is_counted(portal_run, check_id, planted):
    _, findings, _ = portal_run
    f = by_check(findings)[check_id]
    assert f.ran, f.notes
    assert f.count == PLANTED[planted], (check_id, f.count, f.notes)


# ── Grading uses every signal ───────────────────────────────────

def test_completeness_cannot_hide_behind_one_healthy_field(portal_run):
    """2.0 graded Contact Data Completeness on lifecycle stage alone, so a
    portal missing company on 60% of contacts got an A. Issue #1."""
    _, findings, sections = portal_run
    f = by_check(findings)
    assert f["complete.missing_lifecyclestage"].share < 2      # lifecycle is fine
    assert f["complete.missing_company"].share == pytest.approx(59.3, abs=0.2)
    assert section(sections, "Contact Data Completeness").grade == "F"


def test_findings_carry_evidence_breakdown_and_root_cause(portal_run):
    _, findings, _ = portal_run
    f = by_check(findings)["owners.unowned_contacts"]
    assert len(f.evidence) == 5
    assert f.evidence[0].url.startswith("https://app.hubspot.com/contacts/12345/record/0-1/")
    assert f.breakdown["rows"][0] == ("IMPORT", 50)
    assert f.root_causes and "IMPORT" in f.root_causes[0]
    assert f.fix == "assign-unowned-contacts" and f.prevention


def test_duplicate_finding_explains_itself(portal_run):
    _, findings, _ = portal_run
    f = by_check(findings)["dupes.contacts_email"]
    assert "3 duplicate groups" in f.notes[0]
    assert len(f.evidence) >= 5         # the biggest groups, three records each
    assert f.fix_steps                  # no merge skill yet: UI steps instead
    g = by_check(findings)["dupes.companies_domain"]
    assert g.fix == "merge-duplicate-companies" and g.severity >= 1


def test_informational_checks_never_affect_grades(portal_run):
    _, findings, sections = portal_run
    f = by_check(findings)
    assert f["db.contacts"].severity == 0 and f["funnel.distribution"].severity == 0
    assert section(sections, "Database Size & Growth").grade == "A"


def test_shared_findings_agree_across_lenses():
    fake = FakeHubSpot(synthetic_portal())
    runs = {}
    for scope in ("marketing", "sales"):
        findings, _, _ = run_checks(make_client(fake), lenses_for(scope), {"scan": True},
                                    log=lambda *a: None)
        runs[scope] = {f.check: (f.count, f.severity) for f in findings if f.lens == "shared"}
    assert runs["marketing"] == runs["sales"] and runs["marketing"]


# ── Coverage is honest ──────────────────────────────────────────

def test_unreadable_objects_are_skipped_not_zero():
    fake = FakeHubSpot(synthetic_portal(), forbidden={"tasks", "leads"})
    findings, sections, _ = run_checks(make_client(fake), lenses_for("sales"), {"scan": False},
                                       log=lambda *a: None)
    f = by_check(findings)
    assert not f["act.overdue_tasks"].ran and f["act.overdue_tasks"].count is None
    assert f["act.leads_unowned"].coverage == "skipped:no_hub"
    assert section(sections, "Activity & Follow-up").grade == "?"


def test_a_skipped_check_caps_the_section_at_b():
    recs = synthetic_portal()
    recs["leads"] = [{"id": "l1", "properties": {"hubspot_owner_id": "1"}}]  # all owned
    recs["tasks"] = []                                                       # nothing overdue
    fake = FakeHubSpot(recs, forbidden={"tasks"})
    _, sections, _ = run_checks(make_client(fake), lenses_for("sales"), {"scan": False},
                                log=lambda *a: None)
    assert section(sections, "Activity & Follow-up").grade == "B"


def test_no_scan_reports_duplicates_as_skipped_not_clean():
    fake = FakeHubSpot(synthetic_portal())
    findings, sections, _ = run_checks(make_client(fake), lenses_for("marketing"), {"scan": False},
                                       log=lambda *a: None)
    f = by_check(findings)["dupes.contacts_email"]
    assert f.coverage == "skipped:disabled" and f.count is None
    assert section(sections, "Duplicates").grade == "?"


def test_a_crashing_check_is_reported_not_fatal(monkeypatch):
    fake = FakeHubSpot(synthetic_portal())
    broken = next(c for c in registry.checks if c.id == "deliv.hard_bounced")
    monkeypatch.setattr(broken, "fn", lambda ctx, c: 1 / 0)
    findings, _, _ = run_checks(make_client(fake), lenses_for("marketing"), {"scan": False},
                                log=lambda *a: None)
    f = by_check(findings)["deliv.hard_bounced"]
    assert f.coverage == "skipped:error" and "ZeroDivisionError" in f.notes[0]


# ── Record scan past the 10k cap ────────────────────────────────

def test_scan_segments_past_the_search_cap():
    big = [contact(i, createdate=ms(-(i % 3650))) for i in range(12_500)]
    fake = FakeHubSpot({"contacts": big})
    client = make_client(fake)
    records, info = S.scan(client, "contacts", ["email", "createdate"])
    assert info["total"] == 12_500 and info["complete"] and info["segments"] > 1
    assert len(records) == 12_500 and len({r["id"] for r in records}) == 12_500


def test_scan_cap_marks_the_result_partial():
    big = [contact(i) for i in range(3_000)]
    fake = FakeHubSpot({"contacts": big})
    records, info = S.scan(make_client(fake), "contacts", ["email"], cap=500)
    assert len(records) == 500 and not info["complete"]


def test_cached_scan_reuses_the_file(tmp_path):
    fake = FakeHubSpot({"contacts": [contact(i) for i in range(50)]})
    client = make_client(fake)
    S.cached_scan(client, "contacts", ["email"], cache_dir=str(tmp_path))
    calls = len(fake.calls)
    records, info = S.cached_scan(client, "contacts", ["email"], cache_dir=str(tmp_path))
    assert len(fake.calls) == calls and len(records) == 50 and info["complete"]


# ── Reports ─────────────────────────────────────────────────────

def test_write_reports_markdown_json_and_history(tmp_path):
    fake = FakeHubSpot(synthetic_portal())
    out = tmp_path / "reports"
    result = write_reports(make_client(fake), lenses_for("sales"), {"scan": True}, out_dir=str(out),
                           log=lambda *a: None)
    md = pathlib.Path(result["markdown"]).read_text()
    assert md.startswith("# HubSpot Sales Audit Report")
    for heading in ("## Summary", "### Grades", "## Top findings", "## Prescription",
                    "# What this audit could not check", "# Method"):
        assert heading in md
    assert "Email Deliverability — grade" not in md and "Deal Data Quality — grade" in md
    assert "Evidence (sample)" in md and "app.hubspot.com/contacts/12345/record/0-3/" in md
    data = json.loads(pathlib.Path(result["json"]).read_text())
    assert data["schema_version"] == 3 and data["scope"] == ["shared", "sales"]
    skills = [p["skill"] for p in data["prescription"]]
    assert len(skills) == len(set(skills)) and "reassign-deactivated-owners" in skills
    assert data["coverage"]["ran"] == data["coverage"]["total"]
    assert (out / "history" / f"shared-sales-{data['date']}.json").exists()


def test_second_run_reports_changes(tmp_path):
    out = tmp_path / "reports"
    recs = synthetic_portal()
    write_reports(make_client(FakeHubSpot(recs)), lenses_for("sales"), {"scan": False},
                  out_dir=str(out), log=lambda *a: None)
    # Rename the history file to yesterday so the second run treats it as previous.
    hist, = (out / "history").glob("*.json")
    prev = json.loads(hist.read_text())
    prev["date"] = "2000-01-01"
    (out / "history" / "shared-sales-2000-01-01.json").write_text(json.dumps(prev))
    hist.unlink()
    for d in recs["deals"]:
        if d["properties"].get("amount") is None:
            d["properties"]["amount"] = "500"            # missing amounts fixed
    result = write_reports(make_client(FakeHubSpot(recs)), lenses_for("sales"), {"scan": False},
                           out_dir=str(out), log=lambda *a: None)
    changes = result["data"]["changes"]
    assert changes["since"] == "2000-01-01"
    assert "deal.missing_amount" in changes["resolved"]
    assert "Since 2000-01-01" in pathlib.Path(result["markdown"]).read_text()


# ── Entry points ────────────────────────────────────────────────

def load_script(name):
    path = ROOT / "skills/hubspot-audit/scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_audit_script_runs_end_to_end(monkeypatch, tmp_path):
    fake = FakeHubSpot(synthetic_portal())
    monkeypatch.setattr(client_mod.requests, "request", fake.request)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "test-token-not-real")
    audit = load_script("audit.py")
    audit.main(["--scope", "marketing", "--no-scan"])
    md, = (tmp_path / "reports").glob("hubspot-marketing-audit-*.md")
    assert "# HubSpot Marketing Audit Report" in md.read_text()


def test_audit_script_refuses_without_token(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
    audit = load_script("audit.py")
    monkeypatch.setattr(audit, "load_token", lambda **k: None)
    with pytest.raises(SystemExit):
        audit.main(["--scope", "sales"])


def test_section_grade_rules():
    ok = Finding("a", "a", "s", "shared", count=0, denominator=10, severity=0)
    skipped = Finding("b", "b", "s", "shared", coverage="skipped:no_scope")
    bad = Finding("c", "c", "s", "shared", count=5, denominator=10, severity=3)
    assert Section("shared", "s", [ok]).grade == "A"
    assert Section("shared", "s", [ok, skipped]).grade == "B"
    assert Section("shared", "s", [ok, bad]).grade == "D"
    assert Section("shared", "s", [skipped]).grade == "?"
