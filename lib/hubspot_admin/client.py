"""
HTTP client for HubSpot's REST API: service-key auth, pacing, retry on 429
and 5xx, versioned paths, and the `warnings` array HubSpot returns on
normalized inputs since the 2026-09 version.

The client is deliberately thin. It knows nothing about checks or skills.
"""

import os
import sys
import time

import requests

from . import paths

BASE = "https://api.hubapi.com"
MAX_RETRIES = 5
SEARCH_DELAY = 0.22      # seconds between Search API calls (hard limit: 5 per second)
GENERAL_DELAY = 0.05     # seconds between other calls; tier limits are per 10 seconds


class ApiError(RuntimeError):
    def __init__(self, status, path, body=""):
        super().__init__(f"HubSpot returned {status} for {path}: {body[:300]}")
        self.status, self.path, self.body = status, path, body


def load_token(env_var="HUBSPOT_ACCESS_TOKEN", script_file=None):
    """Read the token from `.env` in the working directory, then the skill
    directory next to `script_file`. Returns None if unset."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # dotenv is in every script's PEP 723 block
        load_dotenv = None
    if load_dotenv:
        load_dotenv()
        if script_file:
            load_dotenv(os.path.join(os.path.dirname(os.path.abspath(script_file)), "..", ".env"))
    return os.environ.get(env_var)


class Client:
    def __init__(self, token, base=BASE, search_delay=None, general_delay=None,
                 session=None, log=None):
        if not token:
            raise ValueError("a HubSpot access token is required")
        self.base = base
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        # Resolved at call time so tests can zero the module constants.
        self.search_delay = SEARCH_DELAY if search_delay is None else search_delay
        self.general_delay = GENERAL_DELAY if general_delay is None else general_delay
        self.session = session or requests
        self.log = log or (lambda msg: print(msg, file=sys.stderr))
        self.calls = 0
        self.warnings = []     # (path, warning) pairs HubSpot attached to responses

    # ── Core ────────────────────────────────────────────────────

    def request(self, method, path, *, ok=(200,), allow=(), **kwargs):
        """One call with backoff. Returns the Response. Raises ApiError on a
        status outside `ok` unless it is in `allow` (e.g. 403 for an optional
        object), in which case the response is returned for the caller."""
        kwargs.setdefault("timeout", 60)
        resp = None
        for attempt in range(MAX_RETRIES):
            resp = self.session.request(method, f"{self.base}{path}", headers=self.headers, **kwargs)
            self.calls += 1
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = min(2 ** attempt * 2, 30)
                self.log(f"    HTTP {resp.status_code} on {path}, retrying in {wait}s")
                time.sleep(wait)
                continue
            break
        if resp.status_code in ok or resp.status_code in allow:
            self._collect_warnings(path, resp)
            return resp
        raise ApiError(resp.status_code, path, getattr(resp, "text", ""))

    def _collect_warnings(self, path, resp):
        try:
            data = resp.json()
        except Exception:
            return
        if isinstance(data, dict) and data.get("warnings"):
            for w in data["warnings"]:
                self.warnings.append((path, w))

    def get(self, path, **kwargs):
        resp = self.request("GET", path, **kwargs)
        time.sleep(self.general_delay)
        return resp

    def post(self, path, **kwargs):
        resp = self.request("POST", path, **kwargs)
        time.sleep(self.general_delay)
        return resp

    # ── Paths ───────────────────────────────────────────────────

    @staticmethod
    def path(name, **params):
        return paths.resolve(name, **params)

    # ── Paging ──────────────────────────────────────────────────

    def get_all(self, path, params=None, allow=(403, 404)):
        """Follow `after` paging on a GET list endpoint. Returns None when the
        first page is unreadable (missing scope, hub not purchased)."""
        params = dict(params or {})
        params.setdefault("limit", 100)
        results = []
        while True:
            resp = self.get(path, params=params, allow=allow)
            if resp.status_code != 200:
                return None if not results else results
            data = resp.json()
            results.extend(data.get("results", []))
            after = data.get("paging", {}).get("next", {}).get("after")
            if not after:
                return results
            params["after"] = after

    # ── CRM Search ──────────────────────────────────────────────

    def search(self, object_type, body, allow=(403, 404, 400)):
        """One Search API call, paced under 5 requests per second. Returns the
        Response (status may be in `allow`)."""
        resp = self.request("POST", self.path("object_search", object=object_type),
                            json=body, allow=allow)
        time.sleep(self.search_delay)
        return resp

    def account_info(self):
        resp = self.get(self.path("account_info"), allow=(403,))
        return resp.json() if resp.status_code == 200 else {}
