---
name: cleanup-deals
description: "Find past-due, stale, incomplete, unexplained-loss, and likely test deals, then route each owner's flagged deals to them as one review task. Never bulk-closes deals; deletes only test deals a person marked in a reviewed CSV. Skips Salesforce-synced deals."
license: MIT
metadata:
  author: tomgranot
  version: "1.2"
  category: ongoing-maintenance
---

# Cleanup Deals

Standardize deal data to make pipeline reporting accurate. Test deals, missing amounts, and stale opportunities distort forecasts and pipeline metrics.

The fix for most bad deal data is a decision only the deal owner can make: is this deal alive, what is it worth, when will it close, why was it lost. So the scripted path here finds the problems precisely and puts them in front of the right person. It does not make those decisions for them.

## Prerequisites

- A HubSpot service key (`HUBSPOT_ACCESS_TOKEN` in `.env`; an existing legacy private app token also works) with:
  - `crm.objects.deals.read` and `crm.objects.owners.read` (all stages)
  - `crm.objects.contacts.write` (HubSpot gates task creation on it; review-task mode only)
  - `crm.objects.deals.write` (reviewed-deletion mode only)
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- Knowledge of which deal pipelines are active and which are synced from Salesforce

## Important: Salesforce Sync Considerations

If deals are synced from Salesforce:
- Do NOT delete or modify synced deals without coordinating with the Salesforce admin.
- Changes in HubSpot may sync back to Salesforce and cause data loss.
- Identify synced deals by checking for the `hs_salesforceopportunityid` property.

Every script sets synced deals aside: they never appear in a finding CSV, never go into a review task, and `execute.py` refuses to delete them even if they are marked in a CSV. `before.py` reports how many were skipped per finding so you can raise them with the Salesforce admin.

## Scripts

Script paths are relative to this skill's directory. Run them from your project directory so `.env`, `data/`, and `reports/` resolve there: prefix each path with wherever this skill is installed (`skills/cleanup-deals/` in a clone of the repo).

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run scripts/before.py [--stale-days 60] [--pipeline ID]` |
| Execute | [`scripts/execute.py`](./scripts/execute.py) | `uv run scripts/execute.py` (review tasks) |
| Execute | [`scripts/execute.py`](./scripts/execute.py) | `uv run scripts/execute.py --delete-from-csv PATH` (reviewed test-deal deletion) |
| After | [`scripts/after.py`](./scripts/after.py) | `uv run scripts/after.py` |

`before.py` is read-only: it exports one CSV per finding to `data/audit-logs/cleanup-deals-before-<finding>.csv` plus a summary the After stage compares against. `execute.py` creates one review task per deal owner, or deletes only the test deals a person marked. `after.py` re-counts every finding and prints a before/after table. All three share their finding definitions through [`scripts/deal_findings.py`](./scripts/deal_findings.py), so every stage counts the same deals. The scripts target HubSpot's date-based API version `2026-09` (`API_VERSION` in `deal_findings.py`).

### Findings

| Finding | Definition |
|---------|------------|
| `past-close-date` | Open deal whose `closedate` is before today |
| `stale` | Open deal with no logged activity (`notes_last_updated`) in N days (default 60). A deal with no activity at all counts only once it is older than N days. |
| `missing-amount-or-close-date` | Open deal with no `amount` or no `closedate` |
| `lost-no-reason` | Closed-lost deal with no `closed_lost_reason` |
| `likely-test` | Any deal whose name contains the word test, dummy, sample, or asdf, or with amount 0 and no associated contacts. "demo" is excluded on purpose: real deals are often named after the demo that opened them. |

## Why Execute Does Not Bulk-Close Deals

The obvious script would set every stale or past-due deal to Closed Lost. This skill does not ship one, for four reasons:

1. **Inactivity is not a loss.** `notes_last_updated` only moves when someone logs an activity in HubSpot. Deals worked by phone, from a personal inbox, or in another tool look stale while they are alive. A bulk close marks real pipeline as lost.
2. **A close is not cleanly reversible.** Moving a deal to Closed Lost writes a close date, fires stage-based workflows and notifications, and changes win rate, forecast, and quota attainment reports. Moving it back does not unsend the emails or undo the workflow actions, and the deal's stage history keeps the false loss.
3. **A bulk close destroys the signal it was meant to fix.** A loss reason filled in by a script ("Closed by cleanup") tells you nothing about why deals are lost, which is the reason to collect loss reasons at all.
4. **The owner has the answer.** Amount, close date, next step, and loss reason are facts the rep knows and the CRM does not. Routing each rep one task with their flagged deals gets those facts into the record. A script can only guess them.

Deletion is narrower still: only deals a person marked `yes` in the review column of the likely-test CSV, never Salesforce-synced deals, never closed-won deals (deleting them rewrites revenue history), and at most 100 per run.

## Step-by-Step Instructions

### Stage 1: Plan

Confirm with the user before starting:

1. Which pipelines are in scope, and which are Salesforce-synced (hands off without coordination)? Pass `--pipeline ID` to limit a run to one pipeline.
2. The staleness cutoff (default: 60 days without logged activity; `--stale-days N`).
3. Who receives the review tasks. Every flagged deal's owner gets one task. Deals with no owner or a deactivated owner are listed in the plan CSV but get no task: fix ownership first with `/cleanup-lead-owners` or `/reassign-deactivated-owners`.

### Stage 2: Before

```bash
uv run scripts/before.py
```

Present the counts table to the user, with the number of Salesforce-synced matches skipped. Walk through a few rows of each CSV to confirm the findings are right for this portal (for example, that the test-deal heuristic is not catching real deals).

**If the user wants test deals deleted**, have them open `data/audit-logs/cleanup-deals-before-likely-test.csv`, read the `reason` column, and put `yes` in the `delete` column of each row that is a genuine test deal. Leave every other row blank. Rows without `yes` are never deleted.

### Stage 3: Execute

**Review tasks (the default):**

```bash
uv run scripts/execute.py
```

The script groups the flagged deals by owner, writes the plan to `data/audit-logs/cleanup-deals-execute-tasks-plan.csv`, prints one line per owner, and asks for `CREATE TASKS`. Each owner gets one task, due in 7 days, associated with their flagged deals and listing why each was flagged. Owners who already have an open review task from a previous run are skipped, so re-running does not stack duplicate tasks on a rep. No deal is modified.

**Reviewed test-deal deletion (opt-in):**

```bash
uv run scripts/execute.py --delete-from-csv data/audit-logs/cleanup-deals-before-likely-test.csv
```

The script reads only the rows marked `yes`, re-reads those deals from HubSpot, refuses Salesforce-synced and closed-won deals, writes every deal's current properties to `data/audit-logs/cleanup-deals-execute-delete-backup.csv`, and asks for `DELETE`.

**Manual follow-ups the scripts do not cover:**

1. **Standardize pipeline stages**: ensure all pipelines have consistent stage names and probability percentages (Settings > Objects > Deals > Pipelines).
2. **Remove unused pipelines**: if a pipeline has zero active deals and is not in use, archive or delete it. The sales audit's Pipeline Configuration section lists them.

### Stage 4: After

```bash
uv run scripts/after.py
```

Prints Before, After, and Change per finding, using the stale cutoff and pipeline recorded by `before.py`. Review tasks change nothing on their own, so run this after the task due date: the counts fall as owners work their tasks. A finding that does not move points to a process gap (no required close date, no loss-reason field on the Closed Lost stage) rather than a data gap. See Tips.

## Safety Mechanisms

| Mechanism | Detail |
|-----------|--------|
| **Read-only Before and After** | `before.py` and `after.py` issue only searches and reads. The offline tests assert that neither makes a write call. |
| **No bulk close, no property edits** | `execute.py` has no code path that changes a deal's stage or properties. See "Why Execute Does Not Bulk-Close Deals". |
| **Abort thresholds** | Review tasks: 50 per run (`TASK_ABORT_THRESHOLD`), since each one lands on a person's task queue. Deletion: 100 deals per run (`DELETE_ABORT_THRESHOLD`), checked before any API call. Above either, the script exits without writing. Narrow with `--pipeline`, or raise the constant only after the user reviews the plan. |
| **CSV audit trail** | Task mode writes the full owner-by-deal plan before creating anything, then a log of created task IDs. Deletion mode writes every targeted deal's properties to a backup CSV before archiving, then a per-deal deletion log. |
| **Typed confirmation** | `CREATE TASKS` for review tasks, `DELETE` for deletion. Any other input aborts with nothing changed. |
| **Human review gate for deletion** | Only rows a person marked `yes` in the CSV's `delete` column are deleted. A CSV without that column is refused. |
| **Salesforce and closed-won protection** | Synced deals are excluded from every finding and refused in deletion mode. Closed-won deals are refused in deletion mode. |
| **No duplicate tasks** | Owners with an open task carrying the review subject are skipped on re-runs. |
| **Recovery window** | Deleted deals can be restored for 90 days from the deals index page (Actions > Restore records). Review tasks can be deleted from the task queue. |

## Technical Gotchas

1. **`2026-09` paths have not been run against a live portal.** The scripts use the date-based paths documented for `2026-09` (`/crm/objects/2026-09/deals/search`, `/crm/objects/2026-09/tasks`, `/crm/owners/2026-09`). HubSpot states most v3 contracts carry over but not all, and `2026-09` rejects writes that omit admin-required properties. If a portal requires extra task properties, task creation fails per owner and the log records the status code. Run `/sandbox-self-test` before relying on this on a production portal.
2. **Search API cap.** The Search API will not page past 10,000 results. A finding that hits the cap is marked in the counts table and the summary CSV. Narrow the run with `--pipeline`.
3. **Stale counts can be lower than the sales audit's.** The audit counts every open deal with no activity as stale. This skill excludes deals younger than the cutoff, which have had no time to collect activity.
4. **`CONTAINS_TOKEN` matches whole words.** "Test deal" matches `test`; "Contest renewal" does not. Change `TEST_NAME_TOKENS` in `deal_findings.py` to suit the portal's naming habits.
5. **Task-to-deal association.** Tasks use the HubSpot-defined association type `216` (task to deal), up to 100 deals per task. A task body lists up to 50 deals; owners with more get a count of the rest.
6. **Rate limits.** Searches are paced at 4 per second, under the Search API's separate 5 per second, with backoff on HTTP 429.

## Rollback

- **Review tasks**: delete them from the task queue. The task log (`cleanup-deals-execute-tasks.csv`) lists every created task ID. No deal was changed.
- **Deleted deals**: restorable for 90 days from the deals index page (Actions > Restore records). The backup CSV holds each deal's properties at the time of deletion.
- For Salesforce-synced deals, check the Salesforce recycle bin as well. The scripts refuse to delete them, so this applies only to manual deletions.
- Stage changes and property updates made by owners while working their tasks are ordinary edits, visible in each deal's property history.

## Tips

- Establish a deal hygiene rule: deals without activity for 60 days get an automated reminder to the owner (build a simple workflow).
- Require `amount` and `closedate` as mandatory deal properties to prevent future gaps.
- Make `closed_lost_reason` required on the Closed Lost stage so the `lost-no-reason` count stops growing.
