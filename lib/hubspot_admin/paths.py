"""
Every HubSpot endpoint the toolkit calls, in one place.

HubSpot moved to date-based API versions in 2026. Not every resource has a
confirmed date-based path yet, and the toolkit must not guess: a wrong path is
a 404 that looks like a missing scope. Each entry records which path is in use
and whether it has been verified against a live portal on the current version.

    API_VERSION  the date-based version new paths target
    VERIFIED     resources confirmed on API_VERSION (cleanup-deals, 2026-10)
    LEGACY       resources still on their pre-2026 path until verified

v4 endpoints are unsupported from 2027-03-30 and v1-v3 are enforced from
2027-09. Move an entry from LEGACY to a date-based path only after a run of
/sandbox-self-test on that path.
"""

API_VERSION = "2026-09"

# Date-based paths (verified on a developer test account).
VERIFIED = {
    "object": "/crm/objects/{version}/{object}",
    "object_search": "/crm/objects/{version}/{object}/search",
    "object_batch_read": "/crm/objects/{version}/{object}/batch/read",
    "object_batch_update": "/crm/objects/{version}/{object}/batch/update",
    "object_batch_archive": "/crm/objects/{version}/{object}/batch/archive",
}

# Paths not yet re-verified on a date-based version. These are the paths the
# 2.0 scripts used and are known to work today.
LEGACY = {
    "owners": "/crm/v3/owners",
    "pipelines": "/crm/v3/pipelines/{object}",
    "properties": "/crm/v3/properties/{object}",
    "lists_search": "/crm/v3/lists/search",
    "flows": "/automation/v4/flows",
    "forms": "/marketing/v3/forms",
    "account_info": "/account-info/v3/details",
    "schemas": "/crm/v3/schemas",
}


def resolve(name, **params):
    """Path for a named resource. Raises KeyError for an unknown name."""
    template = VERIFIED.get(name) or LEGACY[name]
    return template.format(version=API_VERSION, **params)
