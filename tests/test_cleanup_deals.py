"""
Offline tests for the cleanup-deals scripts. No network, no portal, no token:
every HTTP call is answered by a fake HubSpot holding synthetic deals, which
evaluates the scripts' search filters itself so the findings are exercised
end to end.

    uv run --with pytest --with requests --with python-dotenv pytest tests/
"""

import csv
import datetime
import importlib.util
import pathlib
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).parent.parent / "skills/cleanup-deals/scripts"
sys.path.insert(0, str(SCRIPTS))
import deal_findings as df  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(f"cleanup_deals_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


before, execute, after = load("before"), load("execute"), load("after")

NOW = datetime.datetime.now(datetime.timezone.utc)


def day(offset):
    return (NOW + datetime.timedelta(days=offset)).isoformat()


def deal(id, name, owner="901", closed=False, won=False, **props):
    base = {"dealname": name, "hubspot_owner_id": owner, "amount": "1000",
            "closedate": day(30), "createdate": day(-200), "notes_last_updated": day(-2),
            "hs_is_closed": str(closed).lower(), "hs_is_closed_won": str(won).lower(),
            "num_associated_contacts": "1"}
    base.update(props)
    return {"id": str(id), "properties": {k: v for k, v in base.items() if v is not None}}


def synthetic_deals():
    return [
        deal(1, "Acme renewal", closedate=day(-10)),                       # past close date
        deal(2, "Globex expansion", notes_last_updated=day(-90)),          # stale
        deal(3, "Initech pilot", owner="902", amount=None),                # missing amount
        deal(4, "Umbrella lost", owner="902", closed=True),                # lost, no reason
        deal(5, "Test deal please ignore", owner="902"),                   # likely test
        deal(6, "Synced overdue", closedate=day(-10),
             hs_salesforceopportunityid="006SYNTHETIC"),                   # Salesforce: skip
        deal(7, "Healthy deal"),                                           # nothing wrong
        deal(8, "Brand new", notes_last_updated=None, createdate=day(-2)), # new, not stale
        deal(9, "Zero amount", amount="0", num_associated_contacts="0",
             closed=True, closed_lost_reason="Budget"),                    # likely test
        deal(10, "Hooli", owner=None, closedate=day(-5)),                  # no owner
        deal(11, "Left the company", owner="999", closedate=day(-5)),      # inactive owner
        deal(12, "Big win", closed=True, won=True),                        # closed-won
        deal(13, "Synced test", hs_salesforceopportunityid="006SYNTHETIC2"),
    ]


def as_number(value):
    try:
        return int(value)
    except ValueError:
        return int(datetime.datetime.fromisoformat(value).timestamp() * 1000)


def matches(props, f):
    value, op = props.get(f["propertyName"]), f["operator"]
    if op == "NOT_HAS_PROPERTY":
        return value in (None, "")
    if op == "HAS_PROPERTY":
        return value not in (None, "")
    if value in (None, ""):
        return False
    if op == "EQ":
        return value == f["value"]
    if op == "NEQ":
        return value != f["value"]
    if op == "LT":
        return as_number(value) < as_number(f["value"])
    if op == "CONTAINS_TOKEN":
        return f["value"].lower() in value.lower().split()
    raise AssertionError(f"fake HubSpot does not know operator {op}")


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}
        self.text = ""

    def json(self):
        return self._payload


class FakeHubSpot:
    V = df.API_VERSION

    def __init__(self, deals, open_tasks=()):
        self.deals = {d["id"]: d for d in deals}
        self.tasks = [{"properties": {"hs_task_subject": execute.TASK_SUBJECT,
                                      "hubspot_owner_id": o, "hs_task_status": "NOT_STARTED"}}
                      for o in open_tasks]
        self.calls, self.writes = [], []
        self.on_archive = None

    def search(self, records, body):
        groups = body.get("filterGroups", [])
        hits = [r for r in records
                if not groups or any(all(matches(r["properties"], f) for f in g["filters"])
                                     for g in groups)]
        start = int(body.get("after") or 0)
        limit = body.get("limit", 10)
        page = {"total": len(hits), "results": hits[start:start + limit]}
        if start + limit < len(hits):
            page["paging"] = {"next": {"after": str(start + limit)}}
        return page

    def request(self, method, url, headers=None, json=None, params=None, timeout=None):
        path = url.removeprefix(df.BASE)
        self.calls.append((method, path))
        if path == f"/crm/objects/{self.V}/deals/search":
            return FakeResponse(200, self.search(list(self.deals.values()), json))
        if path == f"/crm/objects/{self.V}/deals/batch/read":
            ids = [i["id"] for i in json["inputs"]]
            return FakeResponse(200, {"results": [self.deals[i] for i in ids if i in self.deals]})
        if path == f"/crm/owners/{self.V}":
            return FakeResponse(200, {"results": [
                {"id": "901", "firstName": "Ada", "email": "ada@example.invalid"},
                {"id": "902", "firstName": "Grace", "email": "grace@example.invalid"}]})
        if path == f"/crm/objects/{self.V}/tasks/search":
            return FakeResponse(200, self.search(self.tasks, json))
        if path == f"/crm/objects/{self.V}/tasks" and method == "POST":
            self.writes.append(("create-task", json))
            self.tasks.append({"properties": dict(json["properties"])})
            return FakeResponse(201, {"id": f"task-{len(self.writes)}"})
        if path == f"/crm/objects/{self.V}/deals/batch/archive":
            if self.on_archive:
                self.on_archive()
            ids = [i["id"] for i in json["inputs"]]
            self.writes.append(("archive", ids))
            for i in ids:
                self.deals.pop(i, None)
            return FakeResponse(204)
        raise AssertionError(f"unexpected call: {method} {path}")


@pytest.fixture
def portal(monkeypatch, tmp_path):
    fake = FakeHubSpot(synthetic_deals())
    monkeypatch.setattr(df.requests, "request", fake.request)
    monkeypatch.setattr(df, "QUERY_DELAY", 0)
    monkeypatch.setattr(execute, "BATCH_DELAY", 0)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "test-token-not-real")
    return fake


def no_input(prompt=""):
    raise AssertionError("script asked for confirmation when it should have stopped")


def typed(answer):
    return lambda prompt="": answer


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def ids_in(finding):
    return {r["id"] for r in read_csv(f"data/audit-logs/cleanup-deals-before-{finding}.csv")}


def summary(name="before"):
    return {r["finding"]: r for r in read_csv(f"data/audit-logs/cleanup-deals-{name}-summary.csv")}


# ── before.py ────────────────────────────────────────────────────

def test_before_never_writes(portal):
    assert before.main([]) == 0
    assert portal.writes == []
    assert all(m == "GET" or p.endswith(("/search", "/batch/read")) for m, p in portal.calls)


def test_before_exports_one_csv_per_finding(portal):
    before.main([])
    assert ids_in("past-close-date") == {"1", "10", "11"}
    assert ids_in("stale") == {"2"}
    assert ids_in("missing-amount-or-close-date") == {"3"}
    assert ids_in("lost-no-reason") == {"4"}
    assert ids_in("likely-test") == {"5", "9"}
    assert {k: int(r["count"]) for k, r in summary().items()} == {
        "past-close-date": 3, "stale": 1, "missing-amount-or-close-date": 1,
        "lost-no-reason": 1, "likely-test": 2}


def test_salesforce_synced_deals_are_skipped_and_counted(portal):
    before.main([])
    every_id = set().union(*(ids_in(k) for k in df.FINDINGS))
    assert not every_id & {"6", "13"}
    s = summary()
    assert s["past-close-date"]["skipped_salesforce"] == "1"
    assert s["likely-test"]["skipped_salesforce"] == "1"


def test_stale_ignores_deals_too_new_to_have_activity(portal):
    before.main([])
    assert "8" not in ids_in("stale")
    assert "2" not in set().union(*(ids_in(k) for k in df.FINDINGS if k != "stale"))


def test_stale_days_is_configurable(portal):
    before.main(["--stale-days", "120"])
    assert ids_in("stale") == set()
    assert summary()["stale"]["stale_days"] == "120"


def test_likely_test_csv_has_reasons_and_an_empty_review_column(portal):
    before.main([])
    rows = {r["id"]: r for r in read_csv("data/audit-logs/cleanup-deals-before-likely-test.csv")}
    assert rows["5"]["reason"] == "name contains test"
    assert rows["9"]["reason"] == "amount 0 and no associated contacts"
    assert all(r["delete"] == "" for r in rows.values())


# ── execute.py: review tasks ─────────────────────────────────────

def test_execute_creates_one_review_task_per_active_owner(portal, monkeypatch):
    monkeypatch.setattr("builtins.input", typed("CREATE TASKS"))
    assert execute.main([]) == 0
    tasks = [p for kind, p in portal.writes if kind == "create-task"]
    assert sorted(t["properties"]["hubspot_owner_id"] for t in tasks) == ["901", "902"]
    linked = {t["properties"]["hubspot_owner_id"]: {a["to"]["id"] for a in t["associations"]}
              for t in tasks}
    assert linked == {"901": {"1", "2", "9"}, "902": {"3", "4", "5"}}
    assert all(t["associations"][0]["types"][0]["associationTypeId"] == 216 for t in tasks)


def test_execute_never_touches_deals_in_task_mode(portal, monkeypatch):
    monkeypatch.setattr("builtins.input", typed("CREATE TASKS"))
    execute.main([])
    assert {kind for kind, _ in portal.writes} == {"create-task"}
    assert not any("/deals/" in p and not p.endswith(("/search", "/batch/read"))
                   for _, p in portal.calls)


def test_execute_refuses_without_typed_confirmation(portal, monkeypatch):
    monkeypatch.setattr("builtins.input", typed("yes"))
    assert execute.main([]) == 0
    assert portal.writes == []
    plan = read_csv("data/audit-logs/cleanup-deals-execute-tasks-plan.csv")
    actions = {r["deal_id"]: r["action"] for r in plan}
    assert actions["10"].startswith("skipped: assign an owner")
    assert actions["11"].startswith("skipped: reassign")
    assert "6" not in actions


def test_execute_aborts_above_task_threshold(portal, monkeypatch):
    monkeypatch.setattr(execute, "TASK_ABORT_THRESHOLD", 1)
    monkeypatch.setattr("builtins.input", no_input)
    assert execute.main([]) == 1
    assert portal.writes == []


def test_execute_does_not_duplicate_open_review_tasks(portal, monkeypatch):
    portal.tasks = FakeHubSpot([], open_tasks=["901"]).tasks
    monkeypatch.setattr("builtins.input", typed("CREATE TASKS"))
    execute.main([])
    tasks = [p for kind, p in portal.writes if kind == "create-task"]
    assert [t["properties"]["hubspot_owner_id"] for t in tasks] == ["902"]


# ── execute.py: reviewed deletion ────────────────────────────────

def mark(ids, path="reviewed.csv"):
    before.main([])
    rows = read_csv("data/audit-logs/cleanup-deals-before-likely-test.csv")
    extra = [i for i in ids if i not in {r["id"] for r in rows}]
    rows += [{**{k: "" for k in rows[0]}, "id": i} for i in extra]
    for r in rows:
        r["delete"] = "yes" if r["id"] in ids else ""
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path


def test_delete_only_removes_rows_marked_yes(portal, monkeypatch):
    path = mark(["5"])
    monkeypatch.setattr("builtins.input", typed("DELETE"))
    assert execute.main(["--delete-from-csv", path]) == 0
    assert portal.writes == [("archive", ["5"])]
    assert "9" in portal.deals


def test_delete_writes_backup_before_archiving(portal, monkeypatch):
    path = mark(["5", "9"])
    backup = pathlib.Path("data/audit-logs/cleanup-deals-execute-delete-backup.csv")
    seen = []
    portal.on_archive = lambda: seen.append({r["id"] for r in read_csv(backup)})
    monkeypatch.setattr("builtins.input", typed("DELETE"))
    execute.main(["--delete-from-csv", path])
    assert seen == [{"5", "9"}]


def test_delete_refuses_without_typed_confirmation(portal, monkeypatch):
    path = mark(["5"])
    monkeypatch.setattr("builtins.input", typed("delete"))
    assert execute.main(["--delete-from-csv", path]) == 0
    assert portal.writes == []


def test_delete_aborts_above_threshold_before_any_call(portal, monkeypatch):
    path = mark(["5", "9"])
    monkeypatch.setattr(execute, "DELETE_ABORT_THRESHOLD", 1)
    monkeypatch.setattr("builtins.input", no_input)
    calls = len(portal.calls)
    assert execute.main(["--delete-from-csv", path]) == 1
    assert portal.writes == [] and len(portal.calls) == calls


def test_delete_refuses_salesforce_synced_and_closed_won(portal, monkeypatch):
    path = mark(["5", "12", "13"])
    monkeypatch.setattr("builtins.input", typed("DELETE"))
    execute.main(["--delete-from-csv", path])
    assert portal.writes == [("archive", ["5"])]
    backup = {r["id"]: r["action"] for r in
              read_csv("data/audit-logs/cleanup-deals-execute-delete-backup.csv")}
    assert backup == {"5": "delete", "12": "refused: closed-won",
                      "13": "refused: salesforce-synced"}


def test_delete_requires_a_review_column(portal, tmp_path):
    path = tmp_path / "unreviewed.csv"
    path.write_text("id,dealname\n5,Test deal\n")
    with pytest.raises(SystemExit):
        execute.main(["--delete-from-csv", str(path)])
    assert portal.writes == []


# ── after.py ─────────────────────────────────────────────────────

def test_after_compares_with_before(portal):
    before.main(["--stale-days", "30"])
    portal.deals.pop("5")
    portal.deals["1"]["properties"]["closedate"] = day(20)
    assert after.main([]) == 0
    s = summary("after")
    assert s["likely-test"]["change"] == "-1"
    assert s["past-close-date"]["before"] == "3" and s["past-close-date"]["after"] == "2"
    assert all(m == "GET" or p.endswith(("/search", "/batch/read")) for m, p in portal.calls)


def test_after_runs_without_a_before_summary(portal):
    assert after.main([]) == 0
    assert summary("after")["past-close-date"]["before"] == ""


@pytest.mark.parametrize("script", [before, execute, after])
def test_scripts_refuse_to_run_without_a_token(script, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(df, "load_dotenv", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        script.main([])
