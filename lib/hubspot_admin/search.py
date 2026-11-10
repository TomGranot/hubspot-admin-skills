"""
Search API helpers: filter builders, exact counts, sample fetches, and a full
record scan that works past the 10,000-result cap by segmenting on createdate.
"""

import datetime
import hashlib
import json
import os
import time

PAGE_SIZE = 200            # Search API maximum page size
RESULT_CAP = 10_000        # the Search API will not page past this many results
MIN_SEGMENT_MS = 60_000    # stop bisecting createdate ranges below one minute


# ── Filters ─────────────────────────────────────────────────────

def f_missing(prop):
    return {"propertyName": prop, "operator": "NOT_HAS_PROPERTY"}


def f_has(prop):
    return {"propertyName": prop, "operator": "HAS_PROPERTY"}


def f_eq(prop, value):
    return {"propertyName": prop, "operator": "EQ", "value": str(value)}


def f_neq(prop, value):
    return {"propertyName": prop, "operator": "NEQ", "value": str(value)}


def f_gte(prop, value):
    return {"propertyName": prop, "operator": "GTE", "value": str(value)}


def f_lt(prop, value):
    return {"propertyName": prop, "operator": "LT", "value": str(value)}


def f_between(prop, lo, hi):
    return {"propertyName": prop, "operator": "BETWEEN", "value": str(lo), "highValue": str(hi)}


def f_in(prop, values):
    return {"propertyName": prop, "operator": "IN", "values": [str(v) for v in values]}


def f_token(prop, token):
    return {"propertyName": prop, "operator": "CONTAINS_TOKEN", "value": token}


def days_ago_ms(days, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return int((now - datetime.timedelta(days=days)).timestamp() * 1000)


def body_for(groups, properties=None, limit=1, sorts=None, after=None):
    """Search body. `groups` is a list of filter lists: filters inside a group
    are ANDed, groups are ORed. Empty groups are dropped."""
    body = {"limit": limit}
    groups = [g for g in (groups or []) if g]
    if groups:
        body["filterGroups"] = [{"filters": g} for g in groups]
    if properties:
        body["properties"] = list(properties)
    if sorts:
        body["sorts"] = sorts
    if after:
        body["after"] = after
    return body


# ── Counts and samples ──────────────────────────────────────────

def count(client, object_type, *groups):
    """Exact total via the Search API. Returns None when the object is
    unreadable so the caller reports n/a rather than a false 0."""
    resp = client.search(object_type, body_for(list(groups), limit=1))
    if resp.status_code != 200:
        return None
    return resp.json().get("total", 0)


def sample(client, object_type, groups, properties, n=5, sorts=None):
    """Up to `n` matching records with the given properties. Returns [] when
    unreadable."""
    resp = client.search(object_type, body_for(groups, properties, limit=min(n, PAGE_SIZE),
                                               sorts=sorts))
    if resp.status_code != 200:
        return []
    return resp.json().get("results", [])[:n]


# ── Full scan ───────────────────────────────────────────────────

def _page_all(client, object_type, groups, properties, cap=RESULT_CAP, on_page=None):
    """Page one query up to the cap. Returns (records, truncated)."""
    out, after = [], None
    while True:
        resp = client.search(object_type, body_for(groups, properties, PAGE_SIZE, after=after))
        if resp.status_code != 200:
            return out, True
        data = resp.json()
        out.extend(data.get("results", []))
        if on_page:
            on_page(len(out))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            return out, False
        if len(out) >= cap:
            return out, True


def _bounds(client, object_type, groups, prop="createdate"):
    """Oldest and newest value of `prop` among matching records, in ms."""
    lo_hi = []
    for direction in ("ASCENDING", "DESCENDING"):
        body = body_for(groups, [prop], 1, sorts=[{"propertyName": prop, "direction": direction}])
        resp = client.search(object_type, body)
        if resp.status_code != 200 or not resp.json().get("results"):
            return None
        value = resp.json()["results"][0].get("properties", {}).get(prop)
        lo_hi.append(_to_ms(value))
    if None in lo_hi:
        return None
    return lo_hi[0], lo_hi[1]


def _to_ms(value):
    if value in (None, ""):
        return None
    if str(value).isdigit():
        return int(value)
    try:
        return int(datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def scan(client, object_type, properties, groups=None, cap=None, on_progress=None):
    """Every record matching `groups`, with `properties`, regardless of the
    10,000-result cap: when a query is too large it is split on createdate
    ranges until each piece fits. Stops after `cap` records when given.

    Returns (records, info) where info = {"total", "fetched", "complete",
    "segments"}. `complete` is False when the cap stopped the scan or a
    segment could not be read."""
    groups = [g for g in (groups or []) if g] or [[]]
    total = count(client, object_type, *groups)
    info = {"total": total, "fetched": 0, "complete": True, "segments": 0}
    if total is None:
        info["complete"] = False
        return [], info
    records = []

    def progress():
        if on_progress:
            on_progress(len(records), total)

    def take(recs, truncated):
        records.extend(recs)
        info["segments"] += 1
        if truncated:
            info["complete"] = False
        progress()

    if total <= RESULT_CAP:
        take(*_page_all(client, object_type, groups, properties, cap=cap or RESULT_CAP))
    else:
        bounds = _bounds(client, object_type, groups)
        if bounds is None:
            take(*_page_all(client, object_type, groups, properties))
        else:
            stack = [bounds]
            while stack and (cap is None or len(records) < cap):
                lo, hi = stack.pop()
                seg = [g + [f_between("createdate", lo, hi)] for g in groups]
                n = count(client, object_type, *seg)
                if n is None:
                    info["complete"] = False
                    continue
                if n == 0:
                    continue
                if n > RESULT_CAP and hi - lo > MIN_SEGMENT_MS:
                    mid = (lo + hi) // 2
                    stack.append((mid + 1, hi))
                    stack.append((lo, mid))
                    continue
                remaining = None if cap is None else max(cap - len(records), 0)
                take(*_page_all(client, object_type, seg, properties,
                                cap=remaining or RESULT_CAP))
    if cap is not None and len(records) >= cap and total > cap:
        info["complete"] = False
        del records[cap:]
    info["fetched"] = len(records)
    return records, info


# ── Cache ───────────────────────────────────────────────────────

def cached_scan(client, object_type, properties, groups=None, cap=None, cache_dir=None,
                ttl_hours=12, on_progress=None):
    """`scan` with a JSONL cache under `cache_dir` keyed on the query. The
    cache may contain PII; keep it under a gitignored data/ directory."""
    if not cache_dir:
        return scan(client, object_type, properties, groups, cap, on_progress)
    key = hashlib.sha1(json.dumps([object_type, sorted(properties), groups, cap],
                                  sort_keys=True).encode()).hexdigest()[:12]
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{object_type}-{key}.jsonl")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl_hours * 3600:
        with open(path) as f:
            header = json.loads(f.readline())
            records = [json.loads(line) for line in f]
        return records, header
    records, info = scan(client, object_type, properties, groups, cap, on_progress)
    with open(path, "w") as f:
        f.write(json.dumps(info) + "\n")
        for r in records:
            f.write(json.dumps(r) + "\n")
    return records, info
