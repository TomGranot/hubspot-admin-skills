"""
hubspot_admin: the shared library behind the HubSpot Admin Skills scripts.

Scripts stay single-file `uv run` entry points. They reach this package with
one line that resolves `lib/` relative to their own location, which works from
a clone of the repo and from the Claude Code plugin cache alike:

    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "..", "lib"))
    from hubspot_admin import Client, ...

Nothing here hard-codes a portal, an owner, or a property value.
"""

__version__ = "3.0.0a1"

from .client import Client, ApiError  # noqa: F401
from .findings import (  # noqa: F401
    Check, Finding, Evidence, Coverage, Section, check, registry, severity_from_share,
    grade_letter,
)
