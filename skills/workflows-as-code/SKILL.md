---
name: workflows-as-code
description: "Export all HubSpot workflows to versioned JSON files via the v4 Automation API, diff exports over time, and restore or recreate workflows from JSON. Treats workflow definitions like code: backed up, reviewable, and recoverable."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: automation-workflows
---

# Workflows as Code

Export every workflow in the portal to JSON files, keep the exports under version control, and restore workflows from JSON when something breaks. HubSpot has no recycle bin for workflows — a deleted or mangled workflow is gone unless you have its definition. This skill gives you that safety net, plus reviewable diffs of what changed between exports.

## Why This Matters

Workflows are production automation, but most portals treat them like disposable UI configuration: no backups, no change history, no review. One mis-click in the workflow editor can silently break lead routing or suppression for weeks. The v4 Automation API supports full read and create of workflow definitions, which makes a code-like lifecycle possible: export → version → diff → restore.

## Prerequisites

- A HubSpot service key (`HUBSPOT_ACCESS_TOKEN` in `.env`; an existing legacy private app token also works) with the `automation` scope (plus sensitive-data scopes if any flows touch sensitive properties)
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- A place to keep exports — a git repository is ideal (`data/workflow-exports/` is gitignored here by default because exports may reference internal names; move them to a private repo if you want history)

## Scripts

Script paths are relative to this skill's directory. Run them from your project directory so `.env`, `data/`, and `reports/` resolve there: prefix each path with wherever this skill is installed (`skills/workflows-as-code/` in a clone of the repo).

| Stage | Script | Run with |
|-------|--------|----------|
| Export | [`scripts/export.py`](./scripts/export.py) | `uv run scripts/export.py` |
| Restore | [`scripts/restore.py`](./scripts/restore.py) | `uv run scripts/restore.py <export-file.json>` |

`export.py` lists all flows via `GET /automation/v4/flows`, fetches each full definition via the batch read endpoint (`POST /automation/v4/flows/batch/read`, falling back to per-flow GETs), and writes one JSON file per workflow plus a manifest. `restore.py` recreates a workflow from an export file via `POST /automation/v4/flows` — **always disabled**, under a "(restored)" name, for review before enabling.

## Execution Pattern

### Stage 1: Plan

1. Decide export cadence: before any workflow cleanup (mandatory — see `/cleanup-workflows`), after building new workflows, and on a schedule (monthly pairs well with `/quarterly-database-cleanup`).
2. Decide where exports live long-term (private git repo recommended).

### Stage 2: Before

Nothing to prepare — the export is read-only. Note the current workflow count from Automation > Workflows for comparison.

### Stage 3: Execute — Export

```bash
uv run scripts/export.py
```

Output layout:

```
data/workflow-exports/<YYYY-MM-DD>/
├── manifest.csv              # flowId, name, type, isEnabled, revisionId, file
├── flow-<flowId>.json        # one full definition per workflow
└── ...
```

To diff two exports:

```bash
diff -u data/workflow-exports/2026-06-01/flow-12345.json \
        data/workflow-exports/2026-07-01/flow-12345.json
```

(Timestamps and revision IDs will differ; meaningful changes show up in `actions` and `enrollmentCriteria`.)

### Stage 3 (alternative): Execute — Restore

To recreate a deleted or broken workflow from an export:

```bash
uv run scripts/restore.py data/workflow-exports/2026-06-01/flow-12345.json
```

The script strips server-assigned fields (`id`, `revisionId`, timestamps), renames the flow with a "(restored)" suffix to avoid name collisions, and creates it **disabled**. Review it in the UI, verify enrollment criteria and actions against the original, then rename and enable.

### Stage 4: After

1. Export: verify the manifest row count matches the portal's workflow count and spot-open one JSON file.
2. Restore: open the restored workflow in Automation > Workflows, compare against the export, then enable.

## Rollback

- Export is read-only — nothing to roll back.
- A restored workflow you do not want: it was created disabled; just delete it.

## Technical Gotchas

1. **The Workflows API is beta.** HubSpot documents it as subject to change, with the current reference at `/automation/v4/2027-03-beta/flows`. The scripts here call the unversioned `/automation/v4/flows` path, which is also covered by v4's end of support on March 30, 2027. Versioned exports are your insurance against exactly this kind of change: keep taking them.
2. **Updating in place requires the current `revisionId`, and drops what you omit.** `PUT` must include the flow's latest `revisionId` and `type`; a stale revision is rejected. Any field left out of the body is removed from the workflow, so omitting an action deletes it. The restore script sidesteps both by creating a new flow instead of updating.
3. **Deleted workflows are not restorable through the API.** HubSpot Support can sometimes recover one. An export taken beforehand is the only restore path you control.
4. **Some actions round-trip imperfectly.** Actions whose field shapes are undocumented (e.g., copy-from-associated-object, notification recipients) export fine but may be rejected on re-create in a different portal. The restore script reports per-action errors; add rejected actions in the UI.
5. **v3 workflow IDs are not v4 flow IDs.** If you have old tooling built on `/automation/v3/workflows`, the v4 API provides workflowId → flowId mapping endpoints for migration. New tooling should use v4 exclusively — v3 is legacy.
6. **Sensitive-data scopes.** Reading workflows that use sensitive properties requires the matching `.sensitive.read` scope for that record type on your service key; creating or deleting them requires `.sensitive.write`.
7. **Exports may contain internal data.** Workflow names, property names, list IDs, and notification text are all in the JSON. Treat exports like configuration secrets — keep them in a private repo.
