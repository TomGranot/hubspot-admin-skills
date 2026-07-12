"""
Mock enrichment provider — for self-testing and dry runs only.

Returns deterministic fake values derived from the input contact. Makes no
network calls and spends no credits. Used by the sandbox-self-test suite
(ENRICHMENT_PROVIDER=mock) to exercise the waterfall-enrich-contacts
pipeline end-to-end without a paid provider account.

Never use this against a production portal: the values it writes are fake
by design (phone numbers come from the reserved 555-01xx fiction range).
"""


def enrich(contacts):
    results = []
    for i, c in enumerate(contacts):
        results.append({
            "id": c["id"],
            "phone": f"+1555010{i % 100:02d}",
            "jobtitle": "Selftest Officer",
            "source": "mock",
        })
    return results
