"""Account-type gate. Anything that must never touch production calls
`assert_sandbox` first. Fails closed: an unreadable account type is a refusal."""

ALLOWED_ACCOUNT_TYPES = {"DEVELOPER_TEST", "SANDBOX", "STANDARD_SANDBOX", "DEVELOPMENT_SANDBOX"}


def account_type(client):
    info = client.account_info()
    return str(info.get("accountType", "")).upper(), info


def is_sandbox(client):
    kind, _ = account_type(client)
    return kind in ALLOWED_ACCOUNT_TYPES


def assert_sandbox(client):
    kind, info = account_type(client)
    if kind not in ALLOWED_ACCOUNT_TYPES:
        raise SystemExit(
            f"REFUSED: portal {info.get('portalId', '?')} has accountType {kind or 'unknown'}. "
            "This only runs against DEVELOPER_TEST or SANDBOX portals. There is no override.")
    return info
