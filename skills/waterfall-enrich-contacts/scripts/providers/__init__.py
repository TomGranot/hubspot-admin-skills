"""
Provider registry for external contact enrichment.

Every adapter module exposes:

    enrich(contacts: list[dict]) -> list[dict]

Input : [{"id", "email", "firstname", "lastname", "company", "domain",
          "linkedin_url"}, ...]   (missing keys are empty strings)
Output: [{"id", "email", "phone", "jobtitle", "company", "source"}, ...]
        — include only fields the provider actually found; "id" is the
        HubSpot contact id passed in; "source" names the provider.

Select a provider with the ENRICHMENT_PROVIDER env var (default:
fullenrich). Each provider reads its own <PROVIDER>_API_KEY env var.
To add your own, copy _template.py, implement enrich(), and register it
in PROVIDERS below.
"""

import importlib

PROVIDERS = {
    "fullenrich": "fullenrich",
    "apollo": "apollo",
    "hunter": "hunter",
    "dropcontact": "dropcontact",
    # Deterministic fake data, no network, no credits — used by the
    # sandbox-self-test suite. Never point it at production.
    "mock": "mock",
}


def get_provider(name):
    if name not in PROVIDERS:
        raise SystemExit(
            f"Unknown ENRICHMENT_PROVIDER '{name}'. "
            f"Available: {', '.join(sorted(PROVIDERS))}. "
            "To add one, copy providers/_template.py and register it in "
            "providers/__init__.py."
        )
    return importlib.import_module(f"providers.{PROVIDERS[name]}")
